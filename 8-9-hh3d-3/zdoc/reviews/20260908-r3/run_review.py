"""Independent Cursor ask-mode review, bounded host run, exact input hashes."""
from pathlib import Path
import argparse, datetime, hashlib, json, os, re, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8")
P=argparse.ArgumentParser()
P.add_argument("prompt"); P.add_argument("stem"); P.add_argument("--seconds",type=int,default=420)
P.add_argument("--freeze",default="freeze-s4.json")
a=P.parse_args(); out=Path(__file__).resolve().parent; root=out.parents[2]; z=root/"zdoc"
if not re.fullmatch(r"[a-z0-9-]+",a.stem): raise SystemExit("invalid output stem")
prefix=out/a.stem
if prefix.with_suffix(".host.json").exists() or prefix.with_suffix(".stdout").exists():
    raise SystemExit("review identifier already used")
manifest=json.loads((out/a.freeze).read_text(encoding="utf-8"))
def fingerprints():
    return {f["path"]:hashlib.sha256((z/f["path"]).read_bytes()).hexdigest() for f in manifest["files"]}
expected={f["path"]:f["sha256"] for f in manifest["files"]}
if fingerprints()!=expected: raise SystemExit("source differs from freeze")
prompt=(out/a.prompt).read_text(encoding="utf-8-sig")
cmd=["pwsh","-NoProfile","-File",r"C:\Users\truon\AppData\Local\cursor-agent\agent.ps1",
     "--workspace",str(root),"--model","cursor-grok-4.6-xhigh-fast",
     "--mode","ask","--trust","--print","--output-format","json",prompt]
started=datetime.datetime.now().astimezone().isoformat(); now=time.monotonic()
status={"configured_model":"cursor-grok-4.6-xhigh-fast","mode":"ask","started_at":started,
        "freeze":a.freeze,"input_hashes":expected,"proof_class":"PLAN_DESIGN",
        "verdict_present":False,"timeout":False}
env=os.environ.copy(); env["PYTHONIOENCODING"]="utf-8"; env["NO_COLOR"]="1"
with prefix.with_suffix(".stdout").open("xb") as stdout, prefix.with_suffix(".stderr").open("xb") as stderr:
    proc=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    status["pid"]=proc.pid
    prefix.with_suffix(".started.json").write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
    try: code=proc.wait(timeout=a.seconds)
    except subprocess.TimeoutExpired:
        status["timeout"]=True
        # Only our still-running process and descendants, never another matching name.
        if proc.poll() is None:
            killed=subprocess.run(["taskkill","/PID",str(proc.pid),"/T","/F"],capture_output=True,timeout=20)
            status["cleanup_exit"]=killed.returncode
        code=proc.wait(timeout=20)
status.update(exit=code,elapsed_s=round(time.monotonic()-now,2),
              ended_at=datetime.datetime.now().astimezone().isoformat(),
              input_unchanged=fingerprints()==expected)
raw=prefix.with_suffix(".stdout").read_text(encoding="utf-8-sig",errors="replace")
err=prefix.with_suffix(".stderr").read_text(encoding="utf-8-sig",errors="replace")
status["stdout_bytes"]=len(raw.encode());status["stderr_excerpt"]=err[:1600]
if code==0 and not status["timeout"] and status["input_unchanged"]:
    try:
        parsed=json.loads(raw)
        report=parsed.get("result")
        status["reported_model"]=parsed.get("model")
        status["session_id"]=parsed.get("session_id")
        if isinstance(report,str) and not parsed.get("is_error",False):
            prefix.with_suffix(".md").write_text(report+"\n",encoding="utf-8")
            verdict=re.search(r"VERDICT\s*[:=]\s*(ACCEPT|REVISE|INSUFFICIENT_EVIDENCE)",report)
            status["verdict_present"]=bool(verdict)
            if verdict: status["verdict"]=verdict.group(1)
        else: status["result_error"]="missing string result or error flag"
    except Exception as e: status["parse_error"]=str(e)
prefix.with_suffix(".host.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(status,ensure_ascii=False,indent=2))
sys.exit(0 if status["verdict_present"] else 1)
