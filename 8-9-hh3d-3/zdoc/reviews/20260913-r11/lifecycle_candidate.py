"""GT01 lifecycle candidate: offline install A/B, activate, rollback and lock probes."""
from __future__ import annotations
import hashlib, importlib.util, json, tempfile, zipfile, os, subprocess, sys, time
from pathlib import Path

HERE=Path(__file__).resolve().parent; BOOT=HERE.parents[2]/"studio"/"build"/"bootstrap"
spec=importlib.util.spec_from_file_location("install_toolchain", BOOT/"install_toolchain.py"); inst=importlib.util.module_from_spec(spec); spec.loader.exec_module(inst)

def fixture(base: Path, tag: str):
    archive=base/f"pkg-{tag}.zip"; console=f"Godot-{tag}-console.exe"; gui=f"Godot-{tag}.exe"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(console,("console-"+tag).encode()); z.writestr(gui,("gui-"+tag).encode()); z.writestr("LICENSE.txt",b"MIT")
    raw=archive.read_bytes(); h256=hashlib.sha256(raw).hexdigest(); h512=hashlib.sha512(raw).hexdigest(); sums=base/f"sums-{tag}.txt"; sums.write_text(h512+"  "+archive.name+"\n")
    version="4.7.2-stable"
    lock={"schema":"HH-STUDIO-TOOLCHAIN-LOCK-2","status":"CANDIDATE","godot":{"version":version,"source_tag":version,"source":"https://github.com/godotengine/godot-builds/releases/tag/"+version,"source_commit":"a"*40,"source_commit_url":"https://api.github.com/repos/godotengine/godot/git/ref/tags/"+version,"archive":{"name":archive.name,"url":"https://github.com/godotengine/godot-builds/releases/download/"+version+"/"+archive.name,"sha256":h256,"sha512":h512,"size_bytes":len(raw)},"sha512_sums":{"url":"https://github.com/godotengine/godot-builds/releases/download/"+version+"/SHA512-SUMS.txt","sha256":hashlib.sha256(sums.read_bytes()).hexdigest()},"console_executable":console,"gui_executable":gui,"console_sha256":hashlib.sha256(("console-"+tag).encode()).hexdigest(),"gui_sha256":hashlib.sha256(("gui-"+tag).encode()).hexdigest()}}
    lock_path=base/f"lock-{tag}.json"; lock_path.write_text(json.dumps(lock)); return archive,sums,lock_path

def run():
    with tempfile.TemporaryDirectory(prefix="gt01-r11-") as td:
        b=Path(td); root=b/"root"; a=fixture(b,"4.7.2-stable-a"); c=fixture(b,"4.7.2-stable-b")
        ra=inst.install(*a,root); rb=inst.install(*c,root)
        s1=inst.activate(root,ra["receipt"],"NONE"); s2=inst.activate(root,rb["receipt"],s1["state_token"]); back=inst.rollback(root,s2["state_token"],s2["transition_id"])
        stale=False
        try: inst.rollback(root,s2["state_token"],s2["transition_id"])
        except inst.InstallError: stale=True
        # Exercise the replacement check instead of recording an unverified
        # claim.  The lease must refuse to remove metadata changed while held.
        replacement = False
        try:
            with inst.lease(root):
                lock = root / '.mutation.lock'
                lock.write_text(lock.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        except inst.InstallError:
            replacement = True
        report={"status":"CANDIDATE","run_id":"GT01-R11-LIFECYCLE-20260913","package_a":ra["receipt"],"package_b":rb["receipt"],"rollback_current":back["current"],"stale_transition_rejected":stale,"replacement_lock_rejected":replacement,"probes_not_executed":["manual edit reconciliation","live owner recovery","crashed owner recovery"],"limits":["synthetic packages only","no real engine execution","cooperative lock/process identity"]}
        out=HERE/"lifecycle-candidate.json"; out.write_text(json.dumps(report,indent=2)+"\n"); return report

if __name__=="__main__": print(json.dumps(run(),indent=2))
