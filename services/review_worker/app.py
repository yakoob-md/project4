"""Run one M0 CrewAI task with evidence acquired over MCP and A2A."""
import asyncio
import base64
import hashlib
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import date
from uuid import UUID

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState
from crewai import Agent, Crew, LLM, Task
from crewai.flow.flow import Flow, start
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from services.m0_contracts import BUNDLE_MEDIA_TYPE, PDF_TOOL, SEARCH_TOOL, PdfEvidence, RetrievalRequest
from services.m0_trace import stage, traceparent, tracer
from services.review_worker.artifact import read_bundle
from services.review_worker.roles import logical_roles

@asynccontextmanager
async def lifespan(_app):
    from services.m1_storage import migrate
    from services.review_worker.paper_review import process_paper_jobs

    worker = None
    if os.getenv("DATABASE_URL"):
        await asyncio.to_thread(migrate)
        worker = asyncio.create_task(process_paper_jobs())
    try:
        yield
    finally:
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


app = FastAPI(title="PaperLens CrewAI worker", lifespan=lifespan)
telemetry = tracer("paperlens-worker")
logger = logging.getLogger(__name__)
PUBLIC_PDF = "https://arxiv.org/pdf/2005.11401"


async def parse_pdf(run_id, pdf):
    with stage(telemetry, "worker.mcp.parse_pdf", run_id):
        async with httpx.AsyncClient(timeout=25) as transport:
            url = os.getenv("MCP_SERVER_URL", "http://mcp-tools:9000/mcp")
            async with streamable_http_client(url, http_client=transport) as (read, write, _):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    result = await session.call_tool(PDF_TOOL, {
                        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
                        "run_id": str(run_id),
                        "traceparent": traceparent(),
                    })
                    if result.isError:
                        raise RuntimeError("MCP PDF tool failed")
                    evidence = PdfEvidence.model_validate(result.structuredContent)
                    if evidence.sha256 != hashlib.sha256(pdf).hexdigest():
                        raise ValueError("MCP PDF checksum mismatch")
                    return evidence, initialized.protocolVersion


async def delegate(request):
    url = os.getenv("A2A_AGENT_URL", "http://literature-adk:8001")
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=5)) as transport:
        with stage(telemetry, "worker.a2a.discover", request.run_id):
            card = await A2ACardResolver(transport, url).get_agent_card()
            if (
                card.name != "paperlens_literature"
                or BUNDLE_MEDIA_TYPE not in card.default_output_modes
                or not any(skill.id == SEARCH_TOOL for skill in card.skills)
                or len(card.supported_interfaces) != 1
            ):
                raise ValueError("Unexpected ADK Agent Card")
            interface = card.supported_interfaces[0]
            if interface.protocol_binding != "JSONRPC" or interface.url.rstrip("/") != url.rstrip("/"):
                raise ValueError("Unexpected ADK protocol interface")
        with stage(telemetry, "worker.a2a.send", request.run_id):
            client = await create_client(card, client_config=ClientConfig(
                streaming=False, polling=False, httpx_client=transport,
                accepted_output_modes=[BUNDLE_MEDIA_TYPE],
            ))
            message = Message(
                role=Role.ROLE_USER, message_id=str(request.run_id),
                parts=[Part(text=request.model_dump_json())],
                metadata={"traceparent": traceparent()},
            )
            try:
                async for event in client.send_message(SendMessageRequest(message=message)):
                    if event.HasField("task") and event.task.status.state == TaskState.TASK_STATE_COMPLETED:
                        task = event.task
                        if len(task.artifacts) != 1:
                            raise ValueError("Expected one A2A artifact")
                        bundle = read_bundle(task.artifacts[0], request)
                        return bundle, {
                            "card": card.name, "task_id": task.id, "state": "completed",
                            "binding": interface.protocol_binding, "protocol_version": interface.protocol_version,
                            "media_type": BUNDLE_MEDIA_TYPE, "bundle_id": str(bundle.bundle_id),
                        }
            finally:
                await client.close()
            raise RuntimeError("A2A did not return a completed retrieval task")


def groq_llm():
    return LLM(
        model=os.getenv("CREWAI_MODEL", "openai/gpt-oss-20b").removeprefix("groq/"),
        provider="openai", base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"], timeout=35, max_retries=0,
    )


async def confirm(run_id, parsed, bundle):
    with stage(telemetry, "worker.crewai.confirm", run_id) as span:
        llm = groq_llm()
        agent = Agent(
            role="Orchestrator", goal="Confirm ingestion and retrieval evidence",
            backstory="PaperLens protocol smoke reviewer", llm=llm,
            max_retry_limit=0, verbose=False,
        )
        acknowledgment = f"{bundle.bundle_id} {bundle.passages[0].id}"
        task = Task(
            description=(
                f"The PDF has {len(parsed.passages)} locatable passages. "
                f"The validated {bundle.provider} bundle has {len(bundle.passages)} records. "
                f"To acknowledge the first record, return exactly: {acknowledgment}"
            ),
            expected_output="The bundle UUID and first literature record ID, separated by one space.",
            agent=agent,
        )
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        output = await crew.kickoff_async()
        if output.raw.strip() != acknowledgment:
            raise ValueError("CrewAI did not acknowledge the selected evidence")
        usage = crew.usage_metrics
        if usage is None or usage.total_tokens <= 0:
            raise ValueError("Model usage was not reported")
        span.set_attribute("gen_ai.request.model", llm.model)
        span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", usage.completion_tokens)
        return {"provider": "Groq", "model": llm.model, **usage.model_dump()}


class InteropFlow(Flow):
    def __init__(self, run_id: UUID):
        super().__init__(tracing=False)
        self.run_id = run_id
        self.step = "start"

    @start()
    async def run_spike(self):
        with stage(telemetry, "worker.m0", self.run_id) as span:
            self.step = "download_pdf"
            async with httpx.AsyncClient(timeout=20) as transport:
                response = await transport.get(PUBLIC_PDF)
                response.raise_for_status()
            self.step = PDF_TOOL
            parsed, parser_protocol = await parse_pdf(self.run_id, response.content)
            self.step = "a2a_retrieve"
            request = RetrievalRequest(
                run_id=self.run_id, query="dense passage retrieval", cutoff=date(2020, 5, 21),
            )
            bundle, a2a = await delegate(request)
            if not bundle.passages:
                raise RuntimeError("M0 live check requires a successful literature result")
            self.step = "crewai_confirm"
            usage = await confirm(self.run_id, parsed, bundle)
            return {
                "run_id": str(self.run_id),
                "trace_id": format(span.get_span_context().trace_id, "032x"),
                "pdf": {
                    "url": PUBLIC_PDF, "sha256": parsed.sha256, "tool": PDF_TOOL,
                    "passages": len(parsed.passages), "mcp_protocol": parser_protocol,
                },
                "a2a": a2a,
                "literature": {"provider": bundle.provider, "tool": bundle.tool,
                               "records": len(bundle.passages), "mcp_protocol": bundle.mcp_protocol},
                "crewai": {"tasks": 1, "consumed_bundle_id": str(bundle.bundle_id), "usage": usage},
                "adk": {"model_calls": 0},
            }


@app.exception_handler(RequestValidationError)
async def reject_invalid_request(request, exc):
    return JSONResponse(status_code=422, content={"detail": "Expected a UUID run ID"})


@app.get("/health")
def health():
    return {"status": "ok", "framework": "CrewAI", "roles": logical_roles()}


@app.post("/interop")
async def interop(run_id: UUID):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(503, detail={"stage": "crewai_confirm", "error": "missing Groq key"})
    flow = InteropFlow(run_id)
    try:
        return await flow.kickoff_async()
    except Exception as exc:
        logger.warning("M0 run %s failed at %s (%s)", run_id, flow.step, type(exc).__name__)
        raise HTTPException(502, detail={"run_id": str(run_id), "stage": flow.step,
                                         "error": type(exc).__name__}) from None
