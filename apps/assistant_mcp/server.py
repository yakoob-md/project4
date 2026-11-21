import os
import httpx
from mcp.server.mcpserver import MCPServer

mcp=MCPServer("PaperLens assistant interface")
def request(method,path,**kwargs):
    headers={"Authorization":"Bearer "+os.getenv("PAPERLENS_TOKEN","")}
    with httpx.Client(base_url=os.getenv("PAPERLENS_URL","http://web:8080"),headers=headers,timeout=180) as client:
        response=client.request(method,path,**kwargs); response.raise_for_status(); return response.json()

@mcp.tool()
def explore_idea(text:str,question:str,cutoff:str)->dict:
    """Submit a research idea and return its evidence-grounded run."""
    return request("POST","/api/v1/reviews",data={"mode":"idea","text":text,"question":question,"cutoff":cutoff})

@mcp.tool()
def get_run(run_id:str)->dict:
    """Return a PaperLens review run by identifier."""
    return request("GET",f"/api/v1/reviews/{run_id}")

@mcp.tool()
def get_evidence_pack(run_id:str)->dict:
    """Return compact, evidence-only JSON for an authenticated review."""
    return request("GET",f"/api/v1/reviews/{run_id}/evidence-pack")

@mcp.tool()
def ask_library(question:str)->dict:
    """Answer only from exact passages in the authenticated library."""
    return request("POST","/api/v1/library/ask",json={"question":question})

@mcp.tool()
def draft_related_work(topic:str)->dict:
    """Draft citation-linked related-work sentences from library evidence."""
    return request("POST","/api/v1/drafts",json={"topic":topic})

@mcp.tool()
def list_library()->list[dict]:
    """List papers in the authenticated research library."""
    return request("GET","/api/v1/library/papers")

if __name__=="__main__": mcp.run(transport="stdio")
