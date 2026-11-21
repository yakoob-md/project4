from crewai import Agent

ROLE_SPECS=(
    ("Orchestrator","Create a bounded review plan and delegate literature retrieval."),
    ("Novelty & Gap","Compare contribution claims with eligible prior work."),
    ("Methodology & Feasibility","Assess design, controls, assumptions and reproducibility."),
    ("Dataset & Evidence","Assess data, metrics, uncertainty and claim-result alignment."),
    ("Limitations & Critique","Challenge unsupported findings and close one revision round."),
    ("Communication","Render validated findings without adding factual claims."),
)
REMOTE_ROLE="Literature Retrieval"

def crew_agents(model:str):
    return [Agent(role=role,goal=goal,backstory="PaperLens evidence-grounded specialist",llm=model,max_retry_limit=0,verbose=False) for role,goal in ROLE_SPECS]

def logical_roles()->list[str]: return [role for role,_ in ROLE_SPECS]+[REMOTE_ROLE]
