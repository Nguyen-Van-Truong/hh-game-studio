# GT06 coordinator handoff — S175

`PLAN_HASH=743ea5e003de81f75ad41c1938b6d1b7c51fb09d06009652f262a5e906e6f0b6`

`SOURCE_HASH=fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde`

`PROFILE_SHA256=0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`

`GT06_STATUS=IN_PROGRESS; ACCEPTED_FULL_RUNS=0; AUTHORITY=0`

`HANDOFF_ID=gt06-s175-coordinator-handoff-01`

`RUN_ID=NONE_FOR_HANDOFF; COMMAND_ID=NONE_FOR_HANDOFF`

## New boundary evidence

S175 is read-only official symbol availability evidence at
`zdoc/reviews/20260923-gt06-s175-official-symbol-boundary`.
Godot's official build documentation says official binaries omit debugging
symbols and that Windows MSVC symbols are emitted as a separate PDB. The
official 4.7.2 release lists Android native-symbol archives but no matching
Windows PDB/debug-symbol asset. The pinned Windows binary has SHA-256
`c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643`.

No matching local symbol file is present in the scoped tooling/review folders.
A custom symbol build would change the pinned stock runtime, so it is not an
admissible GT06 retry. S169–S171 remain diagnostic-only with unresolved owner
module/offset and `AUTHORITY=0`; their raw evidence is unchanged.

## Decision and resume condition

Keep `WAITING_EXTERNAL_INPUT`. Do not rerun S169–S171, reinstall WinDbg, or
start formal 10x35. Resume only after owner-provided matching symbols or a
supported ownership-attribution integration is available. Then run one fresh-ID
bounded attribution fixture, verify actual target/helper exits and cleanup, and
open formal GT06 only if that fixture has full authority.

GT06 still requires ten fresh host/editor pairs with five warmup and thirty
measured batches, complete dataset/hash/exit/tree/job/handle evidence, and two
independent same-hash critics with `PASS/TICK=yes`.

`PROCESS_EXIT=NOT_APPLICABLE_FOR_HANDOFF; LEFTOVER_PROCESS=0`
