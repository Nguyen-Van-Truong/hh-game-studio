# S202 symbol-path htrace diagnostic

S202 used a fresh diagnostic ID to try Microsoft symbol resolution. The Godot target, helper and CDB exited 0 and the owned Job closed. The raw CDB output records the symbol-store rejection `not a valid store`; the copied runner also looked for `HH_S202_COMPLETE` while the fixture emitted `HH_S200_COMPLETE`, leaving its derived native-completion list empty. This package retains the raw evidence and is diagnostic-only. The timeout, baseline, profile, counter gate and GT06 acceptance contract remain unchanged.
