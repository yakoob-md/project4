import json
from services.mcp_tools.audit import check_percentages, hygiene_checks, reproducibility_checklist

cases=[
    ("percent_sum",lambda:check_percentages([55,50]).status=="fail"),
    ("test_tuning",lambda:any(x.check_id=="test_set_tuning" and x.status=="fail" for x in hygiene_checks("We tuned on the test set."))),
    ("missing_ablation",lambda:{x.check_id:x.status for x in reproducibility_checklist("We report a random seed.")}["ablation"]=="inconclusive"),
]
def main():
    results={name:bool(check()) for name,check in cases}; passed=sum(results.values())
    print(json.dumps({"passed":passed,"total":len(results),"recall":passed/len(results),"cases":results},indent=2))
    raise SystemExit(0 if passed==len(results) else 1)
if __name__=="__main__":main()
