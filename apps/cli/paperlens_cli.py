import argparse, json, os, time
from pathlib import Path
import httpx

def client():
    return httpx.Client(base_url=os.getenv("PAPERLENS_URL","http://127.0.0.1:8000"),headers={"Authorization":"Bearer "+os.environ.get("PAPERLENS_TOKEN","")},timeout=120)

def main():
    parser=argparse.ArgumentParser(prog="paperlens"); sub=parser.add_subparsers(dest="command",required=True)
    review=sub.add_parser("review"); review.add_argument("paper"); review.add_argument("--question",default="Review this paper"); review.add_argument("--cutoff",default=time.strftime("%Y-%m-%d")); review.add_argument("--out")
    get=sub.add_parser("get"); get.add_argument("run_id")
    args=parser.parse_args()
    with client() as api:
        if args.command=="review":
            with Path(args.paper).open("rb") as stream: response=api.post("/api/v1/reviews",data={"mode":"paper","question":args.question,"cutoff":args.cutoff},files={"pdf":("paper.pdf",stream,"application/pdf")})
        else: response=api.get("/api/v1/reviews/"+args.run_id)
        response.raise_for_status(); result=response.json()
    rendered=json.dumps(result,indent=2)
    if getattr(args,"out",None): Path(args.out).write_text(rendered,encoding="utf-8")
    else: print(rendered)

if __name__=="__main__": main()
