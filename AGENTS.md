# PaperLens project rules

- Start each task with [implementation status](docs/implementation_status.md) and the relevant section of [plan.md](plan.md). Read other files as the task requires.
- Use the 11 course requirements in the status file as the grading contract and follow M0–M5 in plan order. Build paper review first. Release requires paper review and idea exploration with refinement in one authenticated deployment.
- CrewAI owns orchestration and review. Google ADK owns remote retrieval and its session. Use only these two agent frameworks and the official A2A and MCP protocols.
- Implement only the requested slice. Preserve user changes and reuse working code and existing tests.
- Verify unfamiliar SDK APIs against the installed version and matching official docs.
- Use fixtures for routine tests and invoke live smoke tests separately. Keep live credentials, paper text, and secrets out of logs and Git.
- At each checkpoint record the exact command, observed outcome, evidence location, blocker, and next action. Distinguish fixture, live, and unverified evidence.
