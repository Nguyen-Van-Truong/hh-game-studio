# GT-01 closure remint (r15)

`closure_manifest.py` is a read-only generator and verifier for the final GT-01
source closure. It includes the pinned bootstrap runtime, both fixtures, every
bootstrap test, and the fixture/bootstrap documentation. Paths are repository
relative; caches, `.godot`, evidence, temporary files and runtime output are
excluded. The aggregate `source_closure_sha256` is canonical and excludes the
generation timestamp.

Generate and verify from the repository root:

```text
python 8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/closure_manifest.py generate
python 8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/closure_manifest.py verify --manifest 8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/source-closure-manifest.json
python -m unittest 8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/test_closure_manifest.py -q
```

This package does not launch Godot/Blender and cannot promote GT-01. Official
serial runtime evidence must be reminted after this closure is frozen, then
two independent critics must review the same closure hash.
