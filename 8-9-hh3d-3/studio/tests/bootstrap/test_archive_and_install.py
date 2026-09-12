import hashlib, importlib.util, json, tempfile, unittest, zipfile
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
  lock={'schema':'HH-STUDIO-TOOLCHAIN-LOCK-2','status':'CANDIDATE','godot':{'version':'4.7.2-stable','archive':{'name':self.a.name,'url':'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/'+self.a.name,'sha256':h256,'sha512':h512,'size_bytes':len(b)},'sha512_sums':{'sha256':hashlib.sha256(sums).hexdigest()},'console_executable':'Godot_v4.7.2-stable_win64_console.exe','gui_executable':'Godot_v4.7.2-stable_win64.exe','console_sha256':hashlib.sha256(b'console').hexdigest(),'gui_sha256':hashlib.sha256(b'gui').hexdigest()}}; self.l.write_text(json.dumps(lock),encoding='utf8'); self.lock=lock
 def tearDown(self): self.t.cleanup()
 def test_verify_and_install_activate_rollback(self):
  got=v.verify_archive(self.l,self.a,self.s); self.assertEqual(got['status'],'VERIFIED_BYTES_ONLY')
  out=i.install(self.a,self.s,self.l,self.r/'state'); rec=out['receipt']; self.assertEqual(out['status'],'INSTALLED_NOT_ACTIVATED')
  first=i.activate(self.r/'state',rec,'NONE'); second=i.activate(self.r/'state',rec,first['state_token']); self.assertNotEqual(first['state_token'],second['state_token'])
  back=i.rollback(self.r/'state',second['state_token'],second['transition_id']); self.assertEqual(back['status'],'ROLLED_BACK')
 def test_corrupt_or_duplicate_sums_rejected(self):
  self.s.write_text(self.s.read_text()+'\n'+self.s.read_text(),encoding='utf8'); self.assertRaises(v.VerificationError,v.verify_archive,self.l,self.a,self.s)
 def test_traversal_lock_rejected(self):
  self.lock['godot']['archive']['name']='../x.zip'; self.l.write_text(json.dumps(self.lock),encoding='utf8'); self.assertRaises(v.VerificationError,v.verify_archive,self.l,self.a,self.s)
if __name__=='__main__': unittest.main(verbosity=2)

