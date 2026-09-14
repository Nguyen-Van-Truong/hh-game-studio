# GT-02 cross-language golden vectors

The fixture `studio/protocol/vectors/jcs-vectors.json` is locked to RFC 8785
JCS and records number, Unicode, UTF-16 key-order, escaping and payload digest
cases. Python consumes the vectors through the vendored implementation and
Node 24.10.0 consumes the same file with an independent recursive serializer.

Verification:

```text
python -m unittest discover -s 8-9-hh3d-3/studio/tests/protocol -p 'test_golden_vectors.py' -v
Ran 2 tests ... OK
```

This proves Python/Node agreement for the checked vectors. Godot has not yet
consumed them, so the GT-02 Godot cross-language check remains pending. The
vendored implementation carries its Apache-2.0 notice beside the source.
