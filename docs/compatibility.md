# Compatibility & Dependency Matrix

| Component | Target Version | Current Local Status | Notes |
|---|---|---|---|
| Python | 3.12.9 | Installed (System) | Supported baseline |
| Node.js | v24.2.0 | Installed (System) | Frontend build tool |
| FastAPI | 0.110.0 | Verified in isolated dependency directory | Eight-test suite passed |
| Uvicorn | 0.27.0 | Installed | ASGI server |
| Pydantic | 2.13.4 | Verified with FastAPI 0.110.0 | Contract validation tests passed |
| pypdf | 5.1.0 | Installed | PDF text extraction & locators |
| httpx | 0.27.2 | Installed | HTTP client for APIs & A2A |
| Docker | 29.7.2 | Installed (Daemon stopped) | Production containerization |

## M0 protocol images

The table above is the legacy host baseline. Docker 29.7.2 was running for M0. Each M0 image passed `python -m pip check`.

| Service | Framework and protocol pins | Validation and transport |
| --- | --- | --- |
| Review worker | CrewAI 1.15.44, A2A SDK 1.3.1, MCP 1.30.0 | Pydantic 2.12.5, HTTPX 0.28.1, FastAPI 0.165.0, Uvicorn 0.54.0 |
| Literature agent | Google ADK 2.15.0, A2A SDK 1.3.1, MCP 2.3.0 | Pydantic 2.14.4, Uvicorn 0.54.0 |
| MCP tools | MCP 2.3.0 | Pydantic 2.13.4, HTTPX 0.28.1, pypdf 5.1.0 |

All three images use the OTLP HTTP exporter 1.45.2. CrewAI constrains its MCP client to 1.x. Separate images keep the dependency sets compatible while both clients use MCP Streamable HTTP. ADK uses a deterministic custom retrieval agent. CrewAI makes the only model call through its native OpenAI-compatible connection to Groq. Explicit `provider="openai"` preserves the full Groq model ID, including its vendor prefix.

[ADK custom agents](https://adk.dev/agents/custom-agents/) · [A2A Python client](https://a2a-protocol.org/dev/sdk/python/api/a2a.client.html) · [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) · [Langfuse OTLP ingestion](https://langfuse.com/integrations/native/opentelemetry)

