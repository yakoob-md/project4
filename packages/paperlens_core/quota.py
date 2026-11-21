from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

class QuotaWait(RuntimeError):
    def __init__(self,resume_after:datetime): super().__init__("model quota exhausted"); self.resume_after=resume_after

@dataclass
class ModelBudget:
    calls:int
    tokens:int

class QuotaGovernor:
    def __init__(self,max_calls:int=28,max_tokens:int=70_000): self.limit=ModelBudget(max_calls,max_tokens); self.used=ModelBudget(0,0)
    def reserve(self,prompt_tokens:int,max_output_tokens:int):
        requested=prompt_tokens+max_output_tokens
        if self.used.calls+1>self.limit.calls or self.used.tokens+requested>self.limit.tokens: raise QuotaWait(datetime.now(timezone.utc)+timedelta(minutes=1))
        self.used.calls+=1; self.used.tokens+=requested; return requested
    def release(self,reserved:int,actual_tokens:int=0): self.used.tokens=max(0,self.used.tokens-reserved+actual_tokens)
