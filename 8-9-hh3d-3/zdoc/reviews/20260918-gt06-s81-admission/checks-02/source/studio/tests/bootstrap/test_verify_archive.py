import hashlib, importlib.util, json, os, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('verify_archive', ROOT/'build/bootstrap/verify_archive.py')
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)

class VerifyArchiveTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.archive = self.d/'Godot_v4.7.2-stable_win64.exe.zip'; self.archive.write_bytes(b'archive-bytes')
        self.name = self.archive.name
        self.sums = self.d/'SHA512-SUMS.txt'
        h512 = hashlib.sha512(self.archive.read_bytes()).hexdigest()
        self.sums.write_text(f'{h512} *{self.name}\n00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000  other.zip\n', encoding='utf-8')
        self.lock = self.d/'lock.json'
        b=self.archive.read_bytes(); s=self.sums.read_bytes()
        self.obj={'schema':'HH-STUDIO-TOOLCHAIN-LOCK-2','status':'CANDIDATE','godot':{
          'version':'4.7.2-stable','source_tag':'4.7.2-stable','source_commit':'e'*40,
          'source':'https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable',
          'source_commit_url':'https://api.github.com/repos/godotengine/godot/git/ref/tags/4.7.2-stable',
          'archive':{'name':self.name,'url':f'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/{self.name}','sha256':hashlib.sha256(b).hexdigest(),'sha512':h512,'size_bytes':len(b)},
          'sha512_sums':{'url':'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt','sha256':hashlib.sha256(s).hexdigest()}}}
        self.write()
    def write(self): self.lock.write_text(json.dumps(self.obj), encoding='utf-8')
    def test_valid(self): self.assertEqual(v.verify_archive(self.lock,self.archive,self.sums)['status'],'VERIFIED_BYTES_ONLY')
    def test_provenance_is_bound(self):
        self.obj['godot']['source_tag']='4.7.1-stable'; self.write()
        with self.assertRaises(v.VerificationError): v.verify_archive(self.lock,self.archive,self.sums)
    def test_duplicate_sum_filename_rejected(self):
        h=hashlib.sha512(self.archive.read_bytes()).hexdigest(); self.sums.write_text(f'{h} *{self.name}\n{h} *{self.name}\n', encoding='utf-8')
        with self.assertRaises(v.VerificationError): v.verify_archive(self.lock,self.archive,self.sums)
    def test_unsafe_sum_filename_rejected(self):
        h=hashlib.sha512(self.archive.read_bytes()).hexdigest(); self.sums.write_text(f'{h} *../{self.name}\n', encoding='utf-8')
        self.obj['godot']['sha512_sums']['sha256']=hashlib.sha256(self.sums.read_bytes()).hexdigest(); self.write()
        with self.assertRaises(v.VerificationError): v.verify_archive(self.lock,self.archive,self.sums)
    def test_hardlink_rejected(self):
        link=self.d/'alias.zip'
        try: os.link(self.archive, link)
        except (OSError, NotImplementedError): self.skipTest('hard links unavailable')
        with self.assertRaises(v.VerificationError): v.verify_archive(self.lock,link,self.sums)

if __name__ == '__main__': unittest.main()

