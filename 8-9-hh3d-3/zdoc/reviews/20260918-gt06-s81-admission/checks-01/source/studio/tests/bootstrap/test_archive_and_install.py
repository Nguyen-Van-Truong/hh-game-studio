import hashlib, importlib.util, json, tempfile, time, unittest, zipfile, os, subprocess, sys
from pathlib import Path
BASE=Path(__file__).parents[2]/'build/bootstrap'
def load(name):
 s=importlib.util.spec_from_file_location(name,BASE/(name+'.py')); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
v=load('verify_archive'); i=load('install_toolchain')
class ArchiveAndInstallTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.r=Path(self.t.name); self.a=self.r/'Godot_v4.7.2-stable_win64.exe.zip'; self.s=self.r/'SHA512-SUMS.txt'; self.l=self.r/'lock.json'
  with zipfile.ZipFile(self.a,'w',compression=zipfile.ZIP_DEFLATED) as z:
   z.writestr('Godot_v4.7.2-stable_win64_console.exe',b'console'); z.writestr('Godot_v4.7.2-stable_win64.exe',b'gui'); z.writestr('LICENSE.txt',b'MIT')
  b=self.a.read_bytes(); h256=hashlib.sha256(b).hexdigest(); h512=hashlib.sha512(b).hexdigest(); sums=(h512+'  '+self.a.name+'\n').encode(); self.s.write_bytes(sums)
  lock={'schema':'HH-STUDIO-TOOLCHAIN-LOCK-2','status':'CANDIDATE','godot':{'version':'4.7.2-stable','source_tag':'4.7.2-stable','source':'https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable','source_commit':'e'*40,'source_commit_url':'https://api.github.com/repos/godotengine/godot/git/ref/tags/4.7.2-stable','archive':{'name':self.a.name,'url':'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/'+self.a.name,'sha256':h256,'sha512':h512,'size_bytes':len(b)},'sha512_sums':{'url':'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt','sha256':hashlib.sha256(sums).hexdigest()},'console_executable':'Godot_v4.7.2-stable_win64_console.exe','gui_executable':'Godot_v4.7.2-stable_win64.exe','console_sha256':hashlib.sha256(b'console').hexdigest(),'gui_sha256':hashlib.sha256(b'gui').hexdigest()}}; self.l.write_text(json.dumps(lock),encoding='utf8'); self.lock=lock
 def tearDown(self): self.t.cleanup()
 def _synthetic_package(self, root, marker):
  """Create a second immutable fixture package with a self-consistent receipt."""
  pkg_id=hashlib.sha256(marker.encode()).hexdigest(); d=root/'packages'/pkg_id; d.mkdir(parents=True)
  payload=(marker+'-payload').encode(); (d/'payload.bin').write_bytes(payload)
  files={'payload.bin':{'sha256':hashlib.sha256(payload).hexdigest(),'size_bytes':len(payload)}}
  manifest={'schema':'HH3D-BOOTSTRAP-PACKAGE-1','package':pkg_id,'version':'4.7.2-stable','lock_sha256':'0'*64,'files':files}
  (d/'manifest.json').write_bytes(i.encode(manifest))
  return {'package':pkg_id,'manifest_sha256':hashlib.sha256((d/'manifest.json').read_bytes()).hexdigest()}
 def test_verify_and_install_activate_rollback(self):
  got=v.verify_archive(self.l,self.a,self.s); self.assertEqual(got['status'],'VERIFIED_BYTES_ONLY')
  out=i.install(self.a,self.s,self.l,self.r/'state'); rec=out['receipt']; self.assertEqual(out['status'],'INSTALLED_NOT_ACTIVATED')
  root=self.r/'state'; first=i.activate(root,rec,'NONE')
  rec_b=self._synthetic_package(root,'package-B')
  second=i.activate(root,rec_b,first['state_token']); self.assertNotEqual(first['state_token'],second['state_token'])
  with self.assertRaises(i.InstallError): i.rollback(root,second['state_token'],'0'*32)
  self.assertEqual(i.state_token(root),second['state_token'])
  back=i.rollback(root,second['state_token'],second['transition_id']); self.assertEqual(back['status'],'ROLLED_BACK')
  self.assertEqual(back['current'],rec)

 def test_state_rejects_stale_expected_transition_and_manual_edit(self):
  root=self.r/'state'; root.mkdir(); (root/'packages').mkdir()
  state={'schema':'HH3D-BOOTSTRAP-ACTIVE-1','revision':1,'transition_id':'a'*32,'operation':'ROLLED_BACK','current':None,'previous':None}
  (root/i.STATE).write_bytes(i.encode(state)); token=i.state_token(root)
  tampered=dict(state,operation='ACTIVATED')
  (root/i.STATE).write_bytes(i.encode(tampered))
  tampered_token=i.state_token(root)
  with self.assertRaises(i.InstallError): i.read_state(root,tampered_token)
  (root/i.STATE).write_bytes(i.encode(state)); self.assertIsNotNone(i.read_state(root,token))
 def test_corrupt_or_duplicate_sums_rejected(self):
  self.s.write_text(self.s.read_text()+'\n'+self.s.read_text(),encoding='utf8'); self.assertRaises(v.VerificationError,v.verify_archive,self.l,self.a,self.s)
 def test_traversal_lock_rejected(self):
  self.lock['godot']['archive']['name']='../x.zip'; self.l.write_text(json.dumps(self.lock),encoding='utf8'); self.assertRaises(v.VerificationError,v.verify_archive,self.l,self.a,self.s)
 def test_stale_lock_recovery_requires_dead_owner_and_age(self):
  root=self.r/'lock-root'; root.mkdir(); lock=root/'.mutation.lock'; lock.write_text(json.dumps({'pid':999999999,'created_ns':time.time_ns()-400_000_000_000,'nonce':'x'}),encoding='utf8')
  token=hashlib.sha256(lock.read_bytes()).hexdigest()
  self.assertRaises(i.InstallError,i.recover_lock,root,expected_lock=token)
 def test_invalid_pid_and_ttl_refused_without_mutation(self):
  root=self.r/'lock-root'; root.mkdir(); lock=root/'.mutation.lock'; lock.write_text(json.dumps({'schema':i.LOCK_SCHEMA,'pid':0,'process_start':'linux:x:1','created_ns':time.time_ns()-400_000_000_000,'nonce':'0'*32}),encoding='utf8')
  token=hashlib.sha256(lock.read_bytes()).hexdigest()
  self.assertRaises(i.InstallError,i.recover_lock,root,expected_lock=token)
  self.assertTrue(lock.exists())
  self.assertRaises(i.InstallError,i.recover_lock,root,expected_lock=token,max_age_seconds=-1)
 def test_live_owner_survives_recovery_probe(self):
  root=self.r/'live'; root.mkdir()
  with i.lease(root):
   lock=root/'.mutation.lock'; token=hashlib.sha256(lock.read_bytes()).hexdigest()
   self.assertRaises(i.InstallError,i.recover_lock,root,expected_lock=token,max_age_seconds=0)
  self.assertFalse((root/'.mutation.lock').exists())

 def test_subprocess_live_owner_survives_recovery_probe(self):
  root=self.r/'sub-live'; root.mkdir()
  script="import sys,time; sys.path.insert(0, %r); import install_toolchain as i; root=__import__('pathlib').Path(%r);\nwith i.lease(root):\n print('READY',flush=True); time.sleep(30)" % (str(BASE),str(root))
  p=subprocess.Popen([sys.executable,'-c',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(p.stdout.readline().strip(),'READY'); lock=root/'.mutation.lock'; token=hashlib.sha256(lock.read_bytes()).hexdigest()
   with self.assertRaises(i.InstallError): i.recover_lock(root,expected_lock=token,max_age_seconds=0)
   self.assertIsNone(p.poll())
  finally:
   p.terminate(); p.wait(timeout=5); p.stdout.close(); p.stderr.close()

 def test_crashed_subprocess_lease_is_recoverable(self):
  root=self.r/'sub-crash'; root.mkdir()
  script="import sys,os; sys.path.insert(0, %r); import install_toolchain as i; root=__import__('pathlib').Path(%r);\nwith i.lease(root):\n print('READY',flush=True); os._exit(23)" % (str(BASE),str(root))
  p=subprocess.Popen([sys.executable,'-c',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  self.assertEqual(p.stdout.readline().strip(),'READY'); self.assertEqual(p.wait(timeout=5),23)
  lock=root/'.mutation.lock'; token=hashlib.sha256(lock.read_bytes()).hexdigest()
  out=i.recover_lock(root,expected_lock=token,max_age_seconds=0)
  self.assertEqual(out['status'],'STALE_LOCK_RECOVERED'); self.assertFalse(lock.exists()); p.stdout.close(); p.stderr.close()
 def test_replaced_lock_is_never_deleted(self):
  root=self.r/'replace'; root.mkdir()
  with self.assertRaises(i.InstallError):
   with i.lease(root):
    path=root/'.mutation.lock'; old=path.read_bytes()
    path.write_bytes(old.replace(b'"nonce":"',b'"nonce":"f'))
  self.assertTrue(path.exists())
 def test_publish_replace_failure_leaves_active_unchanged(self):
  root=self.r/'publish'; root.mkdir()
  initial={'schema':'HH3D-BOOTSTRAP-ACTIVE-1','revision':1,'transition_id':'a','operation':'ACTIVATED','current':None,'previous':None}
  (root/i.STATE).write_bytes(i.encode(initial)); before=(root/i.STATE).read_bytes()
  candidate=dict(initial,revision=2,transition_id='b',operation='ROLLED_BACK')
  original=i.os.replace
  try:
   i.os.replace=lambda *_args: (_ for _ in ()).throw(OSError('simulated replace failure'))
   with self.assertRaises(OSError): i.publish(root,candidate,i.state_token(root))
  finally: i.os.replace=original
  self.assertEqual((root/i.STATE).read_bytes(),before)
if __name__=='__main__': unittest.main(verbosity=2)

