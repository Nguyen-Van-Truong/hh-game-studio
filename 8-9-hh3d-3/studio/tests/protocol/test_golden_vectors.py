from __future__ import annotations
import json, subprocess, unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.protocol import canonical_json, canonical_bytes


class GoldenVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "protocol/vectors/jcs-vectors.json").read_text(encoding="utf-8"))

    def test_python_vectors(self):
        for case in self.data["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(canonical_json(case["input"]), case["canonical"])
                if "payload_sha256" in case:
                    self.assertEqual("sha256:" + __import__("hashlib").sha256(canonical_bytes(case["input"])).hexdigest(), case["payload_sha256"])

    def test_node_consumer_when_available(self):
        script = r'''const fs=require('fs'); const d=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
function canon(x){if(Array.isArray(x))return '['+x.map(canon).join(',')+']'; if(x&&typeof x==='object')return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canon(x[k])).join(',')+'}'; return JSON.stringify(x);}
for(const c of d.cases){const got=canon(c.input); if(got!==c.canonical){console.error(c.id+' mismatch'); process.exit(2);}}
'''
        try:
            result = subprocess.run(["node", "-e", script, str(ROOT / "protocol/vectors/jcs-vectors.json")], capture_output=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.skipTest("Node runtime unavailable")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
