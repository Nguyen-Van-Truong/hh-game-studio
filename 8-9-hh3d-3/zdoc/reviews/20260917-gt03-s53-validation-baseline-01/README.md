# S53 actual Linux validation baseline

AUTHORITY=0. This is an input fixture for verifier unit tests, not a publication
receipt, acceptance decision or replacement for a fresh candidate validation.

The bounded native run `hh-gt03-a6f58f6686e14137b91243e08d2aa11d` completed with
host child/wrapper exit 0, clean Docker process facts and verified owned tree.
It used `ValidationOwner.validate`, then the registered `bind_semantics` and
`semantic_observation` APIs over the exact frozen source release
`7ca9aec02710dee4894676f1af74f3774b2d00564361092a266f71e41bc333a3`.

The existing fixture recipe is unchanged: DEFAULT_SCENE and declarative values
fixture_value=9, move_speed=2.25, turn_speed=90.0, enabled=false. Actual result,
stdout and stderr were copied into the shared fixture only after successful
native capture. `previous-fixture.json` preserves its S52 predecessor.
`fixture-provenance.json` binds old/new SHA256 and this actual run ID.

Focused `test_validation_owner.py` passed 19/19 after replacement. The baseline
does not grant public authority and cannot be relabeled for a different plugin
or source release.
