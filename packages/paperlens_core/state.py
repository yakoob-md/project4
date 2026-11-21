STAGES=("queued","parsing","auditing","claim_extraction","planning","retrieving","reviewing","challenging","revising","closing","validating","synthesizing","publishing","completed")
STATUSES=("queued","running","quota_wait","needs_input","failed","cancelling","cancelled","completed","evidence_pack_ready")
def advance(current:str,target:str)->str:
    if current not in STAGES or target not in STAGES or STAGES.index(target)!=STAGES.index(current)+1: raise ValueError("invalid stage transition")
    return target
