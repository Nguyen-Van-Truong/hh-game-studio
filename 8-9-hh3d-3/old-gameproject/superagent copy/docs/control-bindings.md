# Superagent Classic controls

This is the owner-approved keyboard layout for the Classic test build. It is
an implementation choice for this clean-room game; the reference ledger keeps
the keys observed in the Y8 reference unchanged so that observations are not
rewritten as if they used this layout.

## Two players on one keyboard

| Player | Move | Punch | Shoot | Throw | Power slot |
| --- | --- | --- | --- | --- | --- |
| P1 | W A S D | J | K | L | `;` |
| P2 | Arrow keys | Numpad 1 | Numpad 2 | Numpad 3 | Numpad 4 |

The P2 keypad bindings use Godot's keypad keycodes and assume Num Lock is on.
They are distinct from the top-row `1 2 3 4` keys. The current input contract
still reports semantic actions (`p1_punch`, `p2_shoot`, and so on), so combat,
movement, held state, pressed edges, released edges, and future combo checks do
not depend on a key label.

The Classic roster deliberately has no character-specific special move or
passive. These four action slots retain the same semantic roles for every
ordinary character. Any contextual combination will be documented as an
action mapping after it has a real implementation and postcondition; this
table alone is not evidence of a mechanic.

## Reserved special-character layout

The provisional movement lab uses double-tap left/right then hold to sprint
and double-tap down to drop through a one-way platform. Direction release,
reversal, crouch, ladder entry or interruption ends sprint. Shared stamina is
spent by sprint and regenerates faster while stationary; it is not a hero
resource or passive. The tap window, speed and stamina rates are engineering
seeds awaiting reference calibration.

The following keys are reserved and remain inactive in Classic:

| Player | Reserved four-skill keys |
| --- | --- |
| P1 | `U I O P` |
| P2 | Numpad `5 6 7 8` (Num Lock on) |

They belong to the owner-locked SA-14 variant phase. Special characters may
later have four named skills, at most one passive in the first design pass,
and per-character health, mana, or another resource only when the design needs
it. They are not implemented, balanced, or accepted by the Classic gates.

## Verification boundary

The keycode values are pinned from Godot 4.7.2 and are checked by the input
contract/SceneTree tests. Those synthetic events prove routing and keypad
identity, not every physical keyboard's Num Lock or ghosting behavior. The
reference key/action observations in `docs/reference-ledger.tsv` remain
reference evidence and are compared through semantic action correspondence
after this approved remap; the remap does not waive timing, combat, world, or
mode parity gates.
