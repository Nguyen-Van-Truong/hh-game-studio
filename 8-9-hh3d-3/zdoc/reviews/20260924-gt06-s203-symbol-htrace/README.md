# S203 symbol-path and htrace boundary repair

S203 is a fresh bounded diagnostic after S202. It used an absolute symbol cache, one `.reload /f` command per module, and a matching S203 fixture marker. CDB attached to the verified Godot target; the target, helper and CDB exited 0 and the owned Job closed. The htrace differential still produced header-only OPEN records with PID/TID and no stack-address frame lines. The result remains Authority 0 and diagnostic-only; GT06 timeout, baseline, profile, counter gate and acceptance contract are unchanged.
