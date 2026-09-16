"""Mint one actual Linux baseline; never relabel old engine output."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,sys
from dataclasses import asdict

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def save(path,value):
 path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def child(studio,output):
 sys.path.insert(0,str(studio.parent))
 owner=load("frozen_validation_baseline",studio/"godot-addon/validation_owner.py")
 recipe=json.loads((output/"recipe.json").read_bytes())
 script=recipe["script"].encode("utf-8")
 assert script == (b"extends Node3D\n@export var fixture_value: int = 9\n"
   b"@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n"
   b"@export var enabled: bool = false\n")
 bundle=owner.factory.compose(owner.factory.DEFAULT_SCENE,script,
   scene_revision="sha256:"+hashlib.sha256(owner.factory.DEFAULT_SCENE).hexdigest(),
   engine_sha256=owner.executor.BINARY_SHA256)
 assert bundle.files["scenes/fixture.tscn"].decode("utf-8")==recipe["scene"]
 evidence=output/"owned";evidence.mkdir()
 with owner.ValidationOwner(evidence) as issuer:
  receipt=issuer.validate("baseline.actual",bundle)
  observation=issuer.observation(receipt,bundle)
  final,semantic_receipt=issuer.bind_semantics(receipt,bundle)
  facts=issuer.semantic_observation(semantic_receipt,final)
  record=issuer._records[receipt.command_id]
  executor=record.directory/"executor"
  result=json.loads((executor/"result.json").read_bytes())
  stdout=(executor/"engine-stdout.txt").read_bytes().decode("utf-8")
  stderr=(executor/"engine-stderr.txt").read_bytes().decode("utf-8")
  baseline={"result":result,"stdout":stdout,"stderr":stderr,"scene":recipe["scene"],"script":recipe["script"]}
  save(output/"baseline.json",baseline)
  save(output/"receipt.json",asdict(receipt));save(output/"semantic-receipt.json",asdict(semantic_receipt))
  save(output/"observation.json",observation);save(output/"semantic-observation.json",facts)
  save(output/"validation-snapshot.json",issuer.snapshot())
 print(json.dumps({"native_baseline":True,"run_id":result["run_id"],"public_ack":False}))
 return 0

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--studio",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--child",action="store_true");args=parser.parse_args()
 studio=args.studio.resolve();output=args.output.resolve()
 if args.child:return child(studio,output)
 sys.path.insert(0,str(studio.parent));owner=load("live_validation_freeze",studio/"godot-addon/validation_owner.py")
 files,digest=owner.source_release();source=output/"source/studio"
 for name,expected in files.items():
  raw=(studio/name).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("source changed during freeze")
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 recipe=json.loads((studio/"tests/godot/fixtures/validation-run-semantic-baseline.json").read_bytes())
 save(output/"recipe.json",{k:recipe[k] for k in ("scene","script")})
 save(output/"source-closure.json",{"files":files,"validation_source_release_sha256":digest,"helper_sha256":sha(Path(__file__))})
 runner=load("baseline_owned_runner",source/"build/bootstrap/run_fixture.py")
 env=dict(os.environ);env["HH_STUDIO_LINUX_GODOT"]=str(studio/".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64")
 host=runner.run_process([sys.executable,"-B",str(Path(__file__).resolve()),"--child","--studio",str(source),"--output",str(output)],cwd=source,output=output,timeout=120,label="baseline",env=env)
 stable=all(sha(source/name)==expected for name,expected in files.items())
 passed=host["exit_code"]==host["wrapper_exit_code"]==0 and host["tree_verified"] is True and host["timed_out"] is False and stable and (output/"baseline.json").is_file()
 save(output/"capture.json",{"passed":passed,"host":host,"snapshot_unchanged":stable,"validation_source_release_sha256":digest,"public_ack":False,"scope":"actual Linux baseline only"})
 print(json.dumps({"passed":passed,"host":host}))
 return 0 if passed else 2
if __name__=="__main__":raise SystemExit(main())
