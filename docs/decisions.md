# Architecture Decision Records (ADRs)

## ADR-001: Architecture Alignment & Framework Split
* **Date:** 2026-11-21
* **Context:** Course requirements mandate both CrewAI and Google ADK, linked via official A2A and MCP boundaries.
* **Decision:**
  * CrewAI Flow handles application orchestration, specialist reviews, and bounded critique.
  * Google ADK handles independent literature retrieval, exposed via an Agent Card over A2A HTTP.
  * FastMCP exposes document parsing and literature APIs as standardized tools.
* **Status:** Accepted.

## ADR-002: Evidence Grounding and Citation Integrity
* **Date:** 2026-11-21
* **Context:** Peer review agents are prone to hallucinating citations or empirical findings.
* **Decision:**
  * Every finding must strictly quote verbatim text from a frozen `SourcePassage` identified by an exact `passage_id` and locator (page/paragraph).
  * Synthesized reports pass through a deterministic validator that hard-rejects any claim with an unverified quote or missing source.
* **Status:** Accepted.

## ADR-003: Dual-Mode First Release
* **Date:** 2026-11-21
* **Context:** The project requires both Paper Review and Research Idea Exploration in a unified deployment.
* **Decision:**
  * The frontend presents "Review a Paper" and "Explore a Research Idea" as equal entry points.
  * Idea mode produces research briefs and enables a "Refine and Rerun" loop linking child runs to parents without losing history.
* **Status:** Accepted.

