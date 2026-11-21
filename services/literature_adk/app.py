"""M0 ADK retrieval agent and official A2A transport."""
import logging
import os
from uuid import uuid4

from a2a.helpers import new_data_part, new_task
from a2a.server.agent_execution import AgentExecutor
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from services.m0_contracts import (
    BUNDLE_MEDIA_TYPE, SEARCH_TOOL, EvidenceBundle, LiteratureResult, RetrievalRequest,
)
from services.m0_trace import stage, traceparent, tracer

telemetry = tracer("paperlens-adk")
logger = logging.getLogger(__name__)


class LiteratureAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        request = RetrievalRequest.model_validate_json(ctx.user_content.parts[0].text)
        with stage(telemetry, "adk.retrieve", request.run_id):
            url = os.getenv("MCP_SERVER_URL", "http://mcp-tools:9000/mcp")
            with stage(telemetry, "adk.mcp.search_literature", request.run_id):
                async with streamable_http_client(url) as (read, write):
                    async with ClientSession(read, write, read_timeout_seconds=25) as session:
                        initialized = await session.initialize()
                        result = await session.call_tool(SEARCH_TOOL, {
                            "query": request.query,
                            "cutoff": request.cutoff.isoformat(),
                            "run_id": str(request.run_id),
                            "traceparent": traceparent(),
                        })
                        if result.is_error:
                            raise RuntimeError("MCP literature tool failed")
                        evidence = LiteratureResult.model_validate(result.structured_content)
            bundle = EvidenceBundle(
                **evidence.model_dump(), **request.model_dump(), bundle_id=uuid4(),
                tool=SEARCH_TOOL, mcp_protocol=initialized.protocol_version,
            )
        yield Event(
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=bundle.model_dump_json())]),
            actions=EventActions(state_delta={"bundle_id": str(bundle.bundle_id)}),
        )


class RetrievalExecutor(AgentExecutor):
    """Map a single A2A task to a fresh ADK session and a typed data artifact."""

    def __init__(self, runner):
        self.runner = runner

    async def execute(self, context, event_queue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await event_queue.enqueue_event(new_task(
            context.task_id, context.context_id, TaskState.TASK_STATE_SUBMITTED,
        ))
        await updater.start_work()
        try:
            request = RetrievalRequest.model_validate_json(context.message.parts[0].text)
            parent = context.message.metadata["traceparent"] if "traceparent" in context.message.metadata else None
            with stage(telemetry, "adk.a2a.execute", request.run_id, parent):
                session = await self.runner.session_service.create_session(
                    app_name=self.runner.app_name, user_id="paperlens-m0",
                )
                output = None
                try:
                    async for event in self.runner.run_async(
                        user_id=session.user_id, session_id=session.id,
                        new_message=types.Content(
                            role="user", parts=[types.Part(text=request.model_dump_json())],
                        ),
                    ):
                        if event.is_final_response() and event.content:
                            output = event.content.parts[0].text
                    bundle = EvidenceBundle.model_validate_json(output)
                    await updater.add_artifact(
                        name="EvidenceBundle",
                        artifact_id=str(bundle.bundle_id),
                        parts=[new_data_part(bundle.model_dump(mode="json"), BUNDLE_MEDIA_TYPE)],
                    )
                finally:
                    await self.runner.session_service.delete_session(
                        app_name=session.app_name, user_id=session.user_id, session_id=session.id,
                    )
        except Exception as exc:
            logger.warning("M0 ADK retrieval failed (%s)", type(exc).__name__)
            await updater.failed()
        else:
            await updater.complete()

    async def cancel(self, context, event_queue):
        raise NotImplementedError("M0 does not support cancellation")


literature = LiteratureAgent(
    name="paperlens_literature",
    description="Retrieve dated academic evidence through arXiv MCP search.",
)
host = os.getenv("A2A_ADVERTISED_HOST", "literature-adk")
app = to_a2a(
    literature, host=host, port=8001,
    agent_card=AgentCard(
        name=literature.name,
        description=literature.description,
        version="0.1.0",
        capabilities=AgentCapabilities(),
        supported_interfaces=[AgentInterface(
            url=f"http://{host}:8001/", protocol_binding="JSONRPC", protocol_version="1.0",
        )],
        default_input_modes=["text/plain"],
        default_output_modes=[BUNDLE_MEDIA_TYPE],
        skills=[AgentSkill(
            id=SEARCH_TOOL, name="Literature retrieval", description=literature.description,
            tags=["retrieval"], input_modes=["text/plain"], output_modes=[BUNDLE_MEDIA_TYPE],
        )],
    ),
    agent_executor_factory=RetrievalExecutor,
)
