# GT06 S207 source-closure correction

Authority: 0. This is a metadata erratum; it does not change the benchmark
gate and does not accept the running campaign.

S205's coordinator preflight called `source_files()` before importing the
fixture's dynamic dependencies. That produced an incomplete 50-file candidate
closure (`8aca87d44e3a1cbbf0feb558403948da5a71bec6f5761174729a6dc24e8d3b1b`).
The formal campaign entry point loads the fixture before binding its source
files, and its retained `campaign.json` correctly records the complete
53-file closure `c7ced0ef818fd816a9fddc83841d1a6c06b5b1dec39bf4e69de4a28663f91de7`.

The three omitted dynamic dependencies are `godot-addon/bundle_staging.py`,
`godot-addon/bundle_v2.py`, and `godot-addon/fixture_profile.py`. Their bytes
are unchanged; the correction only fixes the preflight interpretation. The
campaign keeps its fresh ID and raw evidence. Acceptance remains false until
the complete campaign, final manifest, actual exits/trees/Jobs/handles, and
two same-hash critics pass.
