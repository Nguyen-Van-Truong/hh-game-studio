# GT07 final critic package — matrix 20261007-04

`AUTHORITY=0`; `GT07=IN_PROGRESS`; this package is ready for two independent
read-only critics and is not a coordinator acceptance signature. The final
matrix is terminal `COMPLETE` with **30/30 PASS**. The exact package manifest
must remain byte-for-byte unchanged while critics review it.

## Frozen identity

- Matrix: `gt07-final-matrix-gt07-m1-final-20261007-04`
- Source closure: `e48e936933540e1a518310636919ebe7e27a6d230d98c0aeed5cac3bf0afa85d`
- Matrix closure: `f8221ec248c6c75e00a5d385b09e5ba8e9ef0cf1ca2acfa6353f50a40a371692`
- Final source/review/raw manifest:
  `studio/.local/reviews/gt07-final-critic-package-20261007-04/final-source-review-raw-manifest.json`
- Manifest SHA-256: `5d97343e7262e4c54f70f0135ffda1045b71c6cf13223321cf4b373e6f1714cc`
- Package JSON SHA-256: `d47adf479c7670044fbfa06b746ca967cb84d1755c59c8d4a695b4d357b5ef46`
- Metadata archive SHA-256:
  `1be6f6882bf9476459314ff9b895ef3306a7d1c2544d84b22b767743659f64ad`

The manifest records the source freeze, matrix manifest, supervisor and target
exit receipts, every row receipt, every raw tree hash, binary pins, and the
requirement map. Raw evidence remains immutable under
`studio/.local/reviews/`; the archive is metadata only and does not replace
the raw trees.

## Terminal evidence

Supervisor directory:
`studio/.local/reviews/gt07-final-supervisor-20261007-06/`

- supervisor actual exit `0`; helper exit `0`
- `tree_verified=true`, Job closed, zero active members, no retained handle
- all 30 row receipts have actual exit `0`
- exact Scheduled Task was removed after terminal closeout; XML, registration,
  start, return and deletion evidence remain in the supervisor directory

## Verification command

Run from the repository root without starting an engine:

```powershell
python -B -c "import json; p='studio/.local/reviews/gt07-final-matrix-gt07-m1-final-20261007-04/manifest.json'; m=json.load(open(p)); assert m['state']=='COMPLETE' and len(m['rows'])==30 and all(r['status']=='PASS' for r in m['rows'])"
```

The package builder is read-only with respect to source and is retained at
`zdoc/reviews/20261003-gt07-integration/build_final_manifest.py` for reproducing
the manifest construction. Rebuilding it creates a new timestamped manifest;
critics must review the frozen hash above, not silently replace it.

## Instructions to both critics

Each critic must use a different model, read the same frozen manifest and raw
receipts without mutation, recompute the listed hashes, inspect actual exits
and Job/tree/handle cleanup, and verify requirement-to-artifact mapping. Each
must write an explicit `TICK=yes` or `TICK=no` for manifest hash
`5d97343e7262e4c54f70f0135ffda1045b71c6cf13223321cf4b373e6f1714cc`.

One critic, a changed source/manifest hash, a PASS banner, or a partial row
prefix cannot authorize GT07. GT08–GT10 remain planned until both critics
explicitly approve this exact hash.
