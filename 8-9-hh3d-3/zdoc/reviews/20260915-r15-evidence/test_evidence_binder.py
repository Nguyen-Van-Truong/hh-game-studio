import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("binder", HERE/"evidence_binder.py"); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class BinderTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); base=Path(self.t.name); self.repo=base/"repo"; self.studio=self.repo/"8-9-hh3d-3"/"studio"; (self.studio/"fixtures").mkdir(parents=True)
  (self.studio/"fixtures"/"fixture.txt").write_text("frozen",encoding="utf8"); (self.studio/"toolchain.lock.json").write_text("lock",encoding="utf8")
  self.pack=base/"pack"; self.pack.mkdir(); records={}
  for rel in ("fixtures/fixture.txt","toolchain.lock.json"):
   p=self.studio/rel; records[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
  self.records=records; rows=[{"path":mod.PREFIX+p,"sha256":d,"required":True,"exists":True,"regular":True,"symlink":False,"reparse":False,"hard_links":1} for p,d in records.items()]
  self.manifest=self.pack/"manifest.json"; self.manifest.write_text(json.dumps({"schema":"HH3D-GT01-SOURCE-CLOSURE-2","status":"CANDIDATE","gaps":[],"required_files":rows}),encoding="utf8")
  self.evidence_path=self.pack/"evidence.json"; self._write_evidence()
 def tearDown(self): self.t.cleanup()
 def _write_evidence(self,status="CANDIDATE",**changes):
  logs={}
  trace={"result":"PASS","phase":"QUITTING","sim_tick":10,"observations":[{"label":"menu","phase":"MENU","sim_tick":0,"body":[0,0],"focus":"StartButton"},{"label":"start","phase":"PLAY","sim_tick":1,"body":[0,0],"focus":"StartButton"},{"label":"moved","phase":"PLAY","sim_tick":7,"body":[1,0],"focus":"StartButton"},{"label":"paused_frozen","phase":"PAUSED","sim_tick":8,"body":[1,0],"focus":"StartButton"},{"label":"resumed","phase":"PLAY","sim_tick":9,"body":[1,0],"focus":"StartButton"},{"label":"quitting","phase":"QUITTING","sim_tick":10,"body":[1,0],"focus":"StartButton"}]}
  for lane,text in {"import":"","parse":"","trace-headless":"GT01_TRACE "+json.dumps(trace,separators=(",",":"))+"\n"}.items():
   out=f"{lane}-stdout.txt"; err=f"{lane}-stderr.txt"; host=f"{lane}-host.json"; (self.pack/out).write_text(text,encoding="utf8"); (self.pack/err).write_text("",encoding="utf8"); (self.pack/host).write_text(json.dumps({"target_pid":100+len(logs)//3,"exit_code":0,"started_at":"2026-01-01T00:00:01+00:00"}),encoding="utf8")
   logs[out]=hashlib.sha256((self.pack/out).read_bytes()).hexdigest(); logs[err]=hashlib.sha256((self.pack/err).read_bytes()).hexdigest(); logs[host]=hashlib.sha256((self.pack/host).read_bytes()).hexdigest()
  runs=[]
  for i,lane in enumerate(("import","parse","trace-headless"),1):
   argv={"import":["Godot","--headless","--import"],"parse":["Godot","--headless","--check-only","--script","res://scripts/trace.gd"],"trace-headless":["Godot","--headless","--script","res://scripts/trace.gd"]}[lane]
   runs.append({"lane":lane,"wrapper_pid":i,"target_pid":100+i-1,"started_at":"2026-01-01T00:00:00+00:00","argv":argv,"exit_code":0,"wrapper_exit_code":0,"timed_out":False,"tree_verified":True,"ownership":"process_group","stdout":f"{lane}-stdout.txt","stderr":f"{lane}-stderr.txt","host":f"{lane}-host.json"})
  trace_line="GT01_TRACE "+json.dumps(trace,separators=(",",":"))+"\n"
  ev={"schema":"hh-gt01-bootstrap-evidence-v2","status":status,"run_id":"R","command_id":"C","source_manifest":dict(self.records),"source_closure_sha256":mod.closure_sha256(self.records),"checks":{"all":True},"runs":runs,"log_hashes":logs,"trace_lines":[trace_line.rstrip("\n")]}
  ev["runs"][0]["host"]="import-host.json"; ev["runs"][1]["host"]="parse-host.json"; ev["runs"][2]["host"]="trace-headless-host.json"; ev.update(changes); self.evidence_path.write_text(json.dumps(ev),encoding="utf8")
 def bind(self): return mod.bind(self.manifest,self.evidence_path,self.repo)
 def test_candidate_binds_without_upgrade(self):
  r=self.bind(); self.assertEqual(r["status"],"READY_FOR_CRITIC"); self.assertEqual(json.loads(self.evidence_path.read_text())["status"],"CANDIDATE")
 def test_rejects_diagnostic_unknown_accepted(self):
  for status in ("DIAGNOSTIC","UNKNOWN","ACCEPTED"): self._write_evidence(status=status); self.assertEqual(self.bind()["status"],"GAP")
  self._write_evidence()
 def test_rejects_exact_closure_or_caller_hash_mismatch(self):
  e=json.loads(self.evidence_path.read_text()); e["source_closure_sha256"]="0"*64; self.evidence_path.write_text(json.dumps(e)); self.assertEqual(self.bind()["status"],"GAP")
 def test_rejects_path_traversal_and_stale_log(self):
  e=json.loads(self.evidence_path.read_text()); e["runs"][0]["stdout"]="../escape.txt"; self.evidence_path.write_text(json.dumps(e)); self.assertEqual(self.bind()["status"],"GAP")
  self._write_evidence(); (self.pack/"trace-headless-stdout.txt").write_text("changed",encoding="utf8"); self.assertEqual(self.bind()["status"],"GAP")
 def test_rejects_host_exit_disagreement_and_trace_semantics(self):
  e=json.loads(self.evidence_path.read_text()); h=self.pack/"trace-headless-host.json"; h.write_text(json.dumps({"target_pid":999,"exit_code":0,"started_at":"2026-01-01T00:00:01+00:00"})); e["log_hashes"]["trace-headless-host.json"]=hashlib.sha256(h.read_bytes()).hexdigest(); self.evidence_path.write_text(json.dumps(e)); self.assertEqual(self.bind()["status"],"GAP")
 def test_rejects_lane_alias_and_unbound_reported_trace(self):
  e=json.loads(self.evidence_path.read_text()); e["runs"][1]["lane"]="trace-headless-check"; self.evidence_path.write_text(json.dumps(e)); self.assertEqual(self.bind()["status"],"GAP")
  self._write_evidence(); e=json.loads(self.evidence_path.read_text()); e["trace_lines"]=["GT01_TRACE stale"]; self.evidence_path.write_text(json.dumps(e)); self.assertEqual(self.bind()["status"],"GAP")
 def test_rejects_invalid_utf8_stream(self):
  self._write_evidence(); p=self.pack/"import-stdout.txt"; p.write_bytes(b"\xff"); self.assertEqual(self.bind()["status"],"GAP")

if __name__=="__main__": unittest.main()
