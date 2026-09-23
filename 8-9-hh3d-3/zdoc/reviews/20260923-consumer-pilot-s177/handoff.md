# S177 handoff — consumer proof remains provisional

GT01–GT05 stay accepted. GT06 has zero accepted full runs; GT07–GT10 remain unopened. Attribution is diagnostic, not an additional acceptance gate. Do not retry unchanged S162–S175 or change the 10x35 verifier.

GT03 authored three nodes and saved/read back the map through authenticated commands. GT04 authored/exported the selected Blender GLB through authenticated writer/publication commands. The native exits and cleanup bind to the selected artifacts. The GT03 author-parent receipt is absent; the GT04 outer collector failed after native success. Neither gap is relabeled as parent success.

The Godot consumer uses these exact inputs. Its 11 checks cover live movement, pickup/UI, 12-frame pause, resume, immutable save/load/corruption recovery and deterministic 60-frame replay with a changed-input control. Native parse/runtime exits and helper exits are 0. Its original stdout-marker collector failure is retained; the derived verdict reads the GUI log. This is application input injection, not an HH Studio runtime-control or general-writer proof.

## Stable provenance

- Implementation first committed at `ee9d5aaf`; metadata correction audited from `6a5f75f1`.
- `manifest-s177-v2.json` is the current exact-byte packet. Older v1 and summary remain historical and their identified drift is recorded in `integrity-errata.json`.
- Source runtime bytes match the executed snapshot, including original trailing newlines. Hash-preserving Git attributes cover source and evidence. No native rerun was used to repair metadata.
- `raw-archive.json` binds a verified, local-only archive of all 1,000 original raw members. No originals were deleted. Retrieve/verify that archive for full native receipts; Git carries selected evidence and hashes only.
- Verify frozen Git bytes with `python -B 8-9-hh3d-3/consumer-pilot/verify_packet.py --ref HEAD`. Add `--with-archive` on this machine to check the local archive.

## Remaining work

Pilot acceptance and independent review are open. The last worker attempt failed because its refresh token was revoked; do not fabricate a review or spin retries. Coordinator can inspect the supported GT06 runtime control/capture entry point and reuse the existing authored inputs. Capability gaps are listed in `consumer-pilot/CAPABILITIES.md`. No full tooling or game completion is claimed.
