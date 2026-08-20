# PROJECT_BRIEF template

Copy this file to `PROJECT_BRIEF.md` for a real game. **This is the schema
template**, not the R8 dogfood brief (`godot/dogfood/kho-bi-an/` is a later WP).

Do **not** put secrets, API keys, account passwords, tokens, or `.env` values
here. Missing credentials are stop-gate **E1** (plan §0.4), not brief fields.

When a field is unset, follow **assumption policy** below rather than asking
the owner for every default.

---

## genre

- **value:** (e.g. top-down 2D action-adventure / puzzle / platformer)
- **player fantasy:**
- **out of scope:** (systems the agent must not add without E4)

## camera

- **mode:** (e.g. top-down / side-scroll / fixed / follow)
- **zoom / limits:**
- **multi-camera:** no | yes (describe)

## resolution

- **base design resolution:** (e.g. 1280×720)
- **stretch mode:** (viewport / canvas_items / ignore)
- **aspect:** (keep / expand / ignore)
- **integer scale:** yes | no

## input

- **devices:** keyboard | gamepad | mouse | touch (list)
- **actions:** (move, interact, pause, …)
- **remap UI:** required | not in v1

## platform

- **ship target:** Windows desktop (this repo’s R9 default)
- **also-run:** (editor Play / export templates)
- **store / signing:** never implied; that is **E3**

## art

- **style:**
- **palette / silhouette notes:**
- **placeholder policy:** assets labeled `PLACEHOLDER` must not ship in release
- **AI / generated assets:** require a source/prompt/license manifest; no secret
  prompts that embed credentials

## audio

- **music:**
- **SFX set:**
- **bus layout:** (Master / Music / SFX)
- **license source:** (original / CC0 / purchased — purchase is **E2**)

## save

- **needed:** yes | no
- **slots / autosave:**
- **location:** under user data, not the project tree
- **contents:** (progress, settings, …) — never store tokens here

## content / license

- **original vs third-party:**
- **allowed licenses for shipped content:** (prefer MIT / CC0 / owned)
- **forbidden:** unlicensed rips; unpaid commercial packs (**E2**)
- **attribution file:** (e.g. `NOTICE.md` in the game project)

## performance

- **target GPU class:**
- **frame budget:** (e.g. 60 fps at base resolution)
- **entity / draw caps (soft):**
- **do not cite unverified numbers as facts** (invariant A13 / A16 spirit)

## acceptance

Replace these with measurable checks. Happy path must not say “the owner clicks”.

- **vertical slice:**
- **play session:** (e.g. 10 minutes, no blocker)
- **tests:** GUT unit + MCP/E2E evidence from the pin in `docs/VERSIONS_GODOT.md`
- **export:** Windows build smoke (later R9); no addon/token/evidence in the game

## assumption policy

The agent may fill unspecified details without asking, in this order
(plan §6.2):

1. Godot 4.7.1-stable conventions and pinned templates
2. easiest to test and revert
3. fewest dependencies and public Editor API only
4. better player-facing quality when cost is comparable

Write each assumption to `.hh-agent/evidence/<run>/assumptions.md` and continue.

**STOP and ask the owner only for E1–E4** (plan §0.4 / §6.5):

| Gate | Stop when |
|------|-----------|
| **E1** | secret, account, or API key the machine does not already have |
| **E2** | money, paid quota, or buying assets/licenses |
| **E3** | code signing, store upload, public publish, or sending project data off-machine |
| **E4** | brief contradicts itself, or genre / audience / scope must change |

Pause is always available and takes priority over new mutations (A10, A14).
Destructive slices need a recoverable checkpoint first (A10).
