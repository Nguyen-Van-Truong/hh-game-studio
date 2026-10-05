# Superagent Classic — Vault Fighters reuse audit

Scope: read-only lessons from `godot/dogfood/superfighters/docs/reference-ledger.md`
and `godot/dogfood/superfighters/KNOWN_ISSUES.md`. No Vault Fighters code,
scene, sprite, audio, map, screenshot, or data is copied into Superagent.
This audit is guidance for SA-01 and does not provide Y8 evidence.

## What can be reused as process knowledge

- Keep a row-level provenance ledger. A later tuning or parity statement must
  name a row ID and a source class. A page listing, a secondary write-up and a
  product assumption are different classes; a secondary source cannot be
  presented as live play.
- Keep source and observation separate. The Vault ledger calls out that a live
  listing can prove a control label while not proving hold-to-aim, camera math,
  exact map geometry, timing, or a combat rule. Superagent therefore seeds those
  details as `UNVERIFIED` and requires a dated clean-room play observation.
- Preserve the clean-room boundary. Public page text can guide functional
  questions; packages, embeds, screenshots, sprites, audio and code are not
  inputs to implementation or art.
- Treat functional parity and expression as separate decisions. Superagent can
  compare control and gameplay roles after measurement, while character art,
  audio, names, tile language and exact map geometry remain original. An owner
  exemption can cover presentation only and cannot waive a functional gap.
- Record deterministic test traces with tick, pressed/held/released state and a
  seed. A deterministic product test is evidence of our implementation; it is
  not evidence that Y8 has the same timing until the reference side is measured.
- Label coverage honestly. Smoke, fixture, synthetic input and assumption rows
  are useful engineering checks but do not establish AI quality or Y8 parity.
  Do not promote such rows to `MATCHED` without independent reference evidence.
- Keep an explicit unknowns list. The source ledger flags hold-to-aim, roll,
  jump/crouch, exact mode names, map landmarks and several roster/rule details
  as unobserved or unavailable. These remain open in `reference-ledger.tsv`
  until SA-02 fills them or provides evidence for `NOT_IN_CURRENT`.

## Reuse decisions

| Material | Decision | Reason |
|---|---|---|
| Reference row IDs and status vocabulary | Adapt as process pattern only | Provenance is useful; product values and statuses are not evidence for Superagent. |
| Numeric tuning values, map names/landmarks, weapon stats | Do not copy | They are product-specific assumptions or expression and may not be observed Y8 facts. |
| Godot scripts, scene structure, data files, tests, traces | Do not port | SA-01 is a clean-room product; copying implementation would violate scope and muddle ownership. |
| Sprite sheets, audio, captures, title/UI text | Do not copy | Original expression and release identity must remain separate. |
| Failure lessons in KNOWN_ISSUES | Adapt as guardrails | Keep assumptions labeled, avoid fixture-only claims, and retain evidence/exit records. |

No item above is marked `OBSERVED`, `IMPLEMENTED`, or `MATCHED` by this audit.
The SA-01 ledger is intentionally seeded `UNVERIFIED`; the checker must fail a
parity gate until the observation package exists.
