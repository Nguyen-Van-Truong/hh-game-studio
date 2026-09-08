I'll read only the authorized HH2 and sibling plan files, then audit them as a read-only critic with a single self-contained TXT plan.Authorized files are in `hh-3d/hh-3d-2/zdoc`; I'll read those plus the sibling HH World plan next.Next I’ll pull roadmap, quality gates, and geography so the 32 WP IDs and DoD can be checked against the proposed single-file plan.HH2-CRITIC-DRAFT TXT | 2026-09-08 Asia/Saigon | PLAN_ONLY | model=cursor-grok-4.6-xhigh-fast | NO_RUNTIME
ROLE=read-only consolidation critic. Coordinator=sole writer of the future canonical file. VF 33/50 unrelated.

==============================================================================
0. AUTHORITY (after coordinator freeze, not this stdout)
==============================================================================
CANONICAL=one TXT under hh-3d/hh-3d-2/zdoc/ (product root). One writer, file lease, revision sha256 of full bytes, STATUS block may bounded-append only with prev_hash+row_id; no errata appendix.
SUPERSEDES for this scope: hh-3d-2/zdoc/00–09, PROGRESS.md, hoan-hao/zdoc/8-9-hh-world-2-*.txt, 5-9 masters. Old files=HISTORY/evidence only; do not delete.
AGENTS.md + 00-START-HERE.md become thin pointers AFTER hash verify. No second checkbox table.
PLAN_SCOPE=hh-3d/hh-3d-2. Shared tools code=hh-3d/hh-3d-2/studio/. Forbidden: godot/dogfood/superfighters, VF 4.7.1 pin/addons, hh-3d/app live edits, Hoàn Hảo service writes, Snake.
EXECUTION_AUTHORIZATION=PLAN_ONLY until owner “start”; then CURRENT=first unticked ID in §1.
IDs kept: H2-P0-01…H2-P9-02 (32). Add ST01–ST08 (8). One status table=40 rows.

==============================================================================
1. STATUS (all PLANNED; implementation NOT_STARTED)
==============================================================================
ST01 pin/isolation | dep: owner start | studio lock Godot 4.7.2-std+templates full commit/SHA256; Blender pin TBD; isolate VF
ST02 safety kernel | ST01 | path/lease/token/main-thread/schema; no write
ST03 atomic ACK | ST02 | UndoRedo+temp+rename+readback; crash/partial fail
ST04 semantic cmds | ST03 | mutating editor API; unique command_id
ST05 runner/packer | ST02 | headless/CI; fail-closed evidence; host exit≠caller 0
ST06 glTF contract | ST01 | Blender→glTF scale1m/Y-up/bones/license; no runtime Blender
ST07 import gate | ST04+ST06 | Godot import validate; not bulk art
ST08 agent drain | ST03+ST05 | one writer; Stop/Pause drain; editor≠Play
H2-P0-01 toolchain | owner start | Godot 4.7.2 Linux x86_64 room headless; no VF change
H2-P0-02 devices | P0-01 | SKU/presets/Q IDs; missing Android=gap not fake
H2-P0-03 bootstrap | P0-02 | menu/quit/first-run Solo no login wall
H2-P1-01 editor consume | P0-03+ST01–05+ST08 | game dock uses studio; no duplicate DoD tick
H2-P1-02 net spike | P0-03 | 1 headless+2 clients; scenes/user_dir split; // P1-01
H2-P1-03 Godot gate | P1-02 | Q01-B Win+≥1 real Android 0/8/32; 64=render stress only
H2-P2-01 control | P1-03+P1-01 | move/camera/touch; Q03-A
H2-P2-02 look-dev | P2-01+ST07 | 1 hero rig; not P5 bulk
H2-P2-03 fish Solo | P2-02 | local quota/save; no cloud mailbox
H2-P2-04 house/shop Solo | P2-03 | namespaces≠Online
H2-P3-01 API/PG | P1-03+P2-03 | pin Node+PG major; DB-D1 contract; D2 drill=P6-02
H2-P3-02 admit/TLS | P3-01 | tickets; UDP block fail-closed; no plaintext
H2-P3-03 room auth | P3-02 | 60→30Hz; award after durable attempt
H2-P3-04 ledger | P3-03 | 1 TX debit/credit/outbox; exactly-once+dedupe
H2-P4-01 friends/AOI | P3-04 | party4 house8 plaza32; takeover=rebind+CAS+fence
H2-P4-02 shop | P4-01 | last-item race; stale price reconfirm
H2-P4-03 house Online | P4-02 | no Solo import
H2-P4-04 chat/mod | P4-03 | chat off until operator path
H2-P5-01 bulk art | P4-04+P1-03 | after perf gate
H2-P5-02 a11y/stream | P5-01
H2-P5-03 Q01-F | P5-02 | Win+mid+low Android 20min thermal
H2-P6-01 Q04-C | P5-03 | 32 interactive net clients Linux/transport pin; ≠64 dummies
H2-P6-02 WAN/ops | P6-01 | DB-D2 sync standby; no auto-async
H2-P6-03 v0.1 human | P6-02 | Q03-H 5; Q04-W2 8; no agent names
H2-P7-01 rights | P6-03 | allowlist source; no Google rip; no HH write
H2-P7-02 convert | P7-01 | WGS84→local m; roundtrip≤0.10m fixture
H2-P7-03 adapters | P7-02 | fixtures first; live API UNVERIFIED until probed
H2-P8-01 1 VN district | P7-03 | topology-like; not 1:1 country
H2-P8-02 100–300 multi-room | P8-01 | measured r_node+cost; Q04-P pack
H2-P8-03 RC v0.2 | P8-02
H2-P9-01 sign/publish | P8-03 | real owner approval
H2-P9-02 observe | P9-01 | propose 64+/cells/voice/IAP/iOS/Web; not done

Parallel (not extra status): after P0-03, P1-02 // P1-01; P3-01 foundation after P1-03, domain schema after P2-03. Accept never skips upstream gates.

==============================================================================
2. ST BUILD/VERIFY/DoD (new; 06 has no ST IDs)
==============================================================================
ST01 BUILD: engine.lock+blender.lock under studio/; official hashes; IGNORE VF cache. VERIFY: --version match; path unicode; checksum fail-closed. DoD: two critics; rollback old binary.
ST02 BUILD: lease owner/expiry/FIFO; token loopback; allowlist under hh-3d-2; reject symlink/escape. VERIFY: EX28-class conflict/stale. DoD: zero writes in this WP.
ST03 BUILD: UndoRedo main thread; multi-file journal; temp+rename. VERIFY: crash mid-save; undo hash. DoD: readback ACK; 2 critics.
ST04 BUILD: typed commands+schema. VERIFY: dup command_id/payload mismatch=conflict. DoD: no partial scene.
ST05 BUILD: packer parses host exit/leftovers. VERIFY: stale/missing evidence reject. DoD: kill≠PASS.
ST06 BUILD: export preset+license ledger. VERIFY: unit/axis/bone fixture. DoD: no trademark/PT assets.
ST07 BUILD: import settings contract. VERIFY: bad glTF reject; placeholder labeled. DoD: not Q03-R final.
ST08 BUILD: editor vs Play user_dir; Stop drains. VERIFY: two writers fail. DoD: P2 mutation blocked until ACCEPTED.

Coordinator MUST paste H2 BUILD/VERIFY/DoD from 06-ROADMAP + EX01–EX36 + DB-D1–D4 + Q00–Q06 into the same TXT (too large for this critic stdout). Do not leave “see old file” as acceptance.

==============================================================================
3. PRODUCT/ARCH MINIMAL (not MMO)
==============================================================================
Play Together-like beats only from public player pages: walk, avatar, emote, party/invite, activity, collect, house, plaza. No HAEGIN backend/CCU/AOI inferred.
v0.1: authored 256–400m Việt stylized; 1 skeleton, 3 presets, 6 outfits/6 emotes; 1 fishing; party4/house8/plaza TARGET32; Win+Android; no voice/IAP/UGC mesh/GPS/country map.
Modes: Solo≠Online namespaces; Public opt-in; shop listing lives if owner offline; avatar↔avatar needs spawn ACK; listing buy=ledger auth.
Stack: Godot client+Linux headless same pin; TS modular monolith+PostgreSQL; room sim≠API ledger. No per-feature microservices, no PostGIS per frame, no GPU on room host, no Redis until measured queue, no seamless cells.

Already-specified (do not reopen as new design): same-room takeover=one registry TX rebind hold+CAS epoch+fence, occupied unchanged at cap32; cross-room fail keeps old session; award recover same attempt_id+quota reservation, no reroll if result committed; Solo inventory-full=local; attempt quota expiry vs late result=one winner; fencing+exactly-once; deletion tombstones outside PITR domain+replay before traffic; RPO0 ACK only if sync standby survived one DB host, no auto async; replica/health read ≠ mutation ACK; UDP blocked=fail-closed; offline/stale price=no silent buy; geo rights before acquire.

==============================================================================
4. CAPACITY (math OK; numbers are illustrations)
==============================================================================
Targets: 32/room; 100–300 CCU = many rooms, not one plaza; not 10k seeing all; client GPU only.
Formula (master §7.1): rooms_predict=min(rooms_cpu,ram,net,…); CPU_budget=capacity_cpu_equiv*1000*0.60; rooms_cpu=floor(budget/(cpu_ms_tick*30)); N+1=ceil(required_rooms/r_node)+1 reconnect spare, not live migrate.
Worked example labeled hypothetical: 4 CPU-eq→2400ms/s; 6ms/tick→180ms/s→13 rooms; 10GiB/0.6→16; 1Gbps*70% / (32*30kB/s)→91; min=13 ≠ promised 416 CCU. 1000@cap32 occ1 r_node8 →5 nodes N+1; occ0.6→8. UNVERIFIED until Q04-C/Q04-P.
vCPU/SMT/burstable ≠ dedicated physical; steal/credit must be measured on same SKU as cpu_ms_tick.
30+10 kB/s = design target, not wire proof. Cost worksheet only SKU/region/date quotes at P6/P8; no prices in plan.

==============================================================================
5. MAX 10 CRITICAL IMPROVEMENTS (WP/gate/validation)
==============================================================================
1) WP=plan-file | Gate=hash+lease | Val=sha256(file), single STATUS, old 00–09/8-9 marked HISTORY. Fixes dual tables (06 vs 8-9 snapshot) and “supplement vs supersede”.
2) WP=ST01–08 vs H2-P1-01 | Gate=path+one DoD | Val=ALLOWED studio/ + addon consume; P1-01 cannot re-tick UndoRedo already passed in ST03. Resolves A02 tools/addons vs studio/.
3) WP=ST06–07 | Gate=DCC optional | Val=Blender pin in ST01 or official skip-to-Godot look-dev; no Blender server. Blender absent from 01–03/05–07/8-9.
4) WP=H2-P8-02 add Q04-P | Gate=pack 1→2→4 rooms same Linux SKU | Val=k empirical ≤rooms_predict; forbids 13*32 arithmetic CCU. Q04-C stays one room×32.
5) WP=H2-P0-02+P6-01 | Gate=CPU-equiv method | Val=publish CPU-time vs wall, steal%, burst window; burstable SKU cannot be official Q04-C.
6) WP=H2-P6-01+P8-02 | Gate=PROOF_CLASS | Val=Q01=client render; Q04-C=interactive sockets+tick p95≤16/p99≤25ms 60min; editor/Blender FPS invalid; payload vs pcap wire separate; 64 dummies≠WAN.
7) WP=H2-P8-02 | Gate=fleet inputs | Val=required_rooms includes house/activity instances + occupancy<1 + 30s reconnect holds; N+1 node-loss reconnect drill, not seamless.
8) WP=H2-P8-02 cost | Gate=no invented price | Val=quote lines with SKU/region/date/currency or COST_UNVERIFIED; 30-day TB math only after measured b_down.
9) WP=order | Gate=safety→write, perf→bulk | Val=packer rejects P2 semantic diffs if ST03/ST08 not ACCEPTED; rejects P5-01 bulk if P1-03 Q01-B GAP; ST06 before bulk meshes.
10) WP=H2-P3-01 | Gate=PG major pin | Val=not docs/current (critic 08-09 saw PG18); DB-D2 remote-WAL-flush+fail-closed fixture here, single-host-loss drill P6-02; liveness≠ready-for-protected-write.

==============================================================================
6. CONTRADICTIONS / SOURCE CONFLICTS
==============================================================================
C1: User single TXT vs 8-9 “R3 keeps order, R4–R10 keep design, don’t blindly merge”. Resolve=copy bodies in, freeze old hashes, don’t dual-tick.
C2: hh-3d-2/AGENTS.md still calls 8-9 mandatory supplement / no second progress table — already contradicted by 8-9 STT + 06 table.
C3: P1-01 ALLOWED game/addons/hh_world_tools vs proposed studio/.
C4: Root AGENTS.md VF6-WP5 vs this product; workers must not open VF.
C5: D05 “docs only this round” vs same file later local WP grant — keep PLAN_ONLY until start.
C6: T01–T03 cited in 06 but 04-GODOT-TOOLS.md not in this read set — ST must not silently alias T-codes.
C7: Two-repo links (hoan-hao zdoc → hh-game-studio) break without sibling checkout; canonical must live in hh-3d-2.

==============================================================================
FACTS
- Read: 01/02/03/05/06/07 + sibling 8-9 TXT. Code/runtime/installs not run. VF route unused.
- 32 H2 IDs match 06 and 8-9 STT. ST01–08 do not exist yet. All PLANNED. CURRENT if start=H2-P0-01 (ST01 same wave).
- Last REVISE items listed by user are present in 8-9 §4–6 / EX01,07,09 / DB-D1–D4 / A05–A06.
- Capacity arithmetic in §7.1 checks out as hypothetical. Headless dedicated-server docs do not size CCU (Godot exporting-for-dedicated-servers; no HAEGIN backend proof).
- GPU room server not required by these docs.

PROPOSALS
- Coordinator writes one leased TXT with §0–1, full inlined H2+EX+Q+DB, ST01–08, Q04-P, PROOF_CLASS, studio ALLOWED, then pointer-only AGENTS/START.
- Minimal room+monolith; 100–300 via more rooms; gameplay Win/Android before VN map (P7 after P6-03).

UNVERIFIED
- Godot 4.7.2 full commit/SHA256 (prefix only in 01). Engine/DTLS/ENet matrix on Win/Android/Linux. FPS, tick, wire B/s, r_node, RTO, prices, Hoàn Hảo live APIs, OSM rights for chosen polygon, Blender version, human fun. S16–S18 web re-read this pass=not done (max2 unused; prior 08-09 research jobs resource_exhausted). Independent review of this draft=none.
