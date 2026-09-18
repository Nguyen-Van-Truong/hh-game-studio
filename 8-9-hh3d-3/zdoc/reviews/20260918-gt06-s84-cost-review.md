# S84 census cost arms — independent bounded evidence review

AUTHORITY=0. PREPARATION_REVIEW_ONLY=1. FORMAL_ACCEPTANCE=false. This is not a
GT-06 acceptance critic or a TICK verdict. Read after all three cost arms were
reported terminal on2026-09-18. Only this file was written; no engine, test,
runtime/helper/raw edit, process control or commit was performed.

**The three arms provide sufficient causal evidence of substantial probe
allocation overhead, and of a materially cheaper compact baseline, to justify
one new compact full-sequence diagnostic.** They do not prove the original
S81 +2 ObjectDB defect fixed, do not establish that all of S82's122851328-byte
RSS increase came from its census, and do not supply a benchmark sample. No
additional original-engine rerun is needed merely to repair the original
collector's post-run assertion summary.

## What was checked

Paths are relative to `8-9-hh3d-3/`. For arm `A` in
`original`, `sham`, `compact`, raw root `RA` is
`studio/.local/reviews/gt06-s84-cost-A-01/`; outer receipt root `OA` is
`zdoc/reviews/20260918-gt06-s84-probe-cost/A-01/`.

I read the executed `measure_cost.py`/`cost_phases.gd` source copies, effective
copied plugins, invocations, all nine observation records and corresponding
native cost records, native census/index metadata, import/editor captures,
actual target-exit files, cleanup records and outer captures/logs. Bounded
hash checks confirmed:

- every observation's native payload equals its `project/benchmark/out/cost-NN.json`
  and SHA256; native phase/run/PID binding and the three host ACK contents agree;
- each helper copy equals its invocation digest;
- each effective copied plugin equals its initial-project digest;
- all three declared51-file base maps are identical;
- each import/editor `process-exit.json` equals its capture's actual target exit.

No mismatch was found in those checks. This is not a full raw inventory/source
rehash or a fresh execution of the existing validators. The captured base is
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`, with
profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
Each native index reports one batch with **one semantic cycle**,
`completed=true`, `benchmark_complete=false`, `formal_acceptance=false`.
No1000-command HTTP batch or35-batch campaign was run in these arms.

| Arm | Effective copied plugin SHA256 |
| --- | --- |
| Original | `3a4ddefd20f9706c4d12f7f4df19c2f76c3eb42cd79657c8719dc151b2fbc233` |
| Sham | `de120b58ca50d033e980bc4ad425761727ec9c18c53bf4fb316f1a45fd80e27e` |
| Compact | `956510b443c5c6087f3a84078377ce2e8f9785ed32e8b6244db24208e353ed52` |

Common `cost_phases.gd` is
`e3d5059bf485a9ac07a2f59c11a57652dbab4a8a98a9e82638e3dd6e189bef68`.
Original probe is
`6221092c70591d89b42aa8c00298198299a716edc7c25b8b4813db5d771fe556`;
compact probe is
`20ed7e62658c247265a8165024682efac78ae9c475a810bb6368e8fe9c75dd40`.

## Intervention order and measured differences

The native cost phase publishes `before`, waits until the retained-handle OS
sample has been written and ACKed, executes either the census or sham, then
waits2s before publishing `retained`. After its external sample/ACK it clears
only probe containers, waits2s, and publishes `released`. Editor frames and
heartbeat continue between phases. Thus the initial OS read genuinely precedes
the intervention; the retained and released observations occur after the
respective function returns. The release callback does not clear scene trees,
editor state or logs, trim RSS, or free game/editor objects.

All values below come directly from `RA/observation-00/01/02.json`:

| Arm | Before RSS bytes | Retained RSS bytes | Released RSS bytes | Retained − before |
| --- | ---: | ---: | ---: | ---: |
| Original | 749113344 | 867033088 | 867033088 | +117919744 /112.4570MiB |
| Sham | 748994560 | 748773376 | 748355584 | −221184 /−0.2109MiB |
| Compact | 747802624 | 750215168 | 750215168 | +2412544 /2.3008MiB |

| Arm | Before Godot static bytes | Retained static bytes | Released static bytes | Retained − before | Retained − released |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 418169243 | 521416975 | 449723667 | +103247732 | 71693308 |
| Sham | 418168947 | 418179899 | 418189467 | +10952 | −9568 |
| Compact | 418194395 | 423450079 | 418996759 | +5255684 | 4453320 |

The intervention increases original RSS15.7412% versus compact0.3226% in
these particular processes. Compact's raw retained RSS increment is about2.05%
of the original increment; this comparison describes these arms, not a
predicted campaign percentage. Godot static memory is a separate supplemental
measurement, not a substituted RSS baseline or gate.

The original's retained static allocation rises about98.46MiB; releasing its
probe containers is followed by a68.37MiB decrease. Sham moves by only about
10KiB over the corresponding first interval. Compact rises about5.01MiB and
falls4.25MiB on release. These controlled interventions, separate fresh
processes, and the sham give substantially stronger allocation evidence than
the earlier S82 before/after correlation alone.

RSS does not fall at the released observation in either census arm. Original
static memory also remains31554424 bytes above its before value; compact
remains802364 bytes above. Therefore do not claim that all allocations were
released, that the residual is a proven leak, or that a particular allocator/
working-set mechanism has been isolated. The recordings have three phase
samples, approximately2s after each action, rather than a long residence-time
curve or private-commit/page-fault trace.

## Timing and coverage of the compact candidate

`RA/project/benchmark/out/object-0000.json` gives collection-only duration:
original820954us versus compact521009us. That field excludes later aggregation,
serialization and publication. Before→retained phase intervals are3063.604ms,
2032.200ms and2610.680ms for original/sham/compact; these also include the fixed
2s wait, ACK/poll scheduling and phase work. Their differences are not a precise
CPU-time decomposition. Native index maximum heartbeat gaps are1061.879ms,
505.010ms and609.571ms respectively. These are short diagnostic observations,
not a full workload latency verdict.

Original census finds27401 identities and compact27402. The class histograms
differ only by one `SceneTreeTimer`; both include146 Tree/RichTextLabel summary
descriptors, and the sorted per-owner TreeItem count values match. Both
censuses preserve exact before/after ObjectDB count inside their collection:
71046 original,71047 compact. This shows comparable reachable coverage, not
identical cross-process object identities or identical asynchronous editor
state. Both leave43645 ObjectDB entries outside their partial census.

The implemented compact collector is **ID→class dictionaries plus146 summary
descriptors**, not the earlier proposed PackedInt64Array design. It still
stringifies IDs and serializes a large initial membership map; its baseline
JSON843157 bytes is similar to the original842615 bytes. The demonstrated
improvement comes from avoiding ordinary full descriptors across the27402
identities, not from smaller output or zero allocation. Its raw fields report
`retained_ordinary_descriptors=0` and146 descriptors collected.

Preserve its explicit coverage limits: changed ordinary properties/child text
are not detected; old owner/path/text for ordinary removals is unavailable;
full descriptors are produced for newly appeared IDs, and exact Tree/
RichTextLabel summaries are compared. This is sufficient to investigate
reachable membership growth, but not to declare all unchanged-ID content or
all ObjectDB entries unchanged.

The separate compact worker's `compact-baseline-01.stdout.json` and
`tests-01-run.json` record baseline arithmetic validation and seven synthetic
contract tests. I read those reports; I did not rerun them. Their checks do
not establish a native second-growth census. These cost arms likewise execute
only the initial census and release path. Keep that limitation when integrating
the full-sequence caller and analyzing later added/removed rows.

## Original collector failure is real and separable from native completion

| Arm | Native editor actual exit | Cost collector actual exit | Outer helper exit |
| --- | --- | --- | --- |
| Original | PID18412,0 | PID43228,1 | PID40816,0 |
| Sham | PID48524,0 | PID43496,0 | PID39204,0 |
| Compact | PID21472,0 | PID43920,0 | PID5544,0 |

Native import exits are23448/0,7944/0,40276/0 respectively. All read import/
editor captures report natural tree exit, closed/zero untainted Jobs and no
retained Job handle; editor captures also bind released wrapper handles.
Their stderr files are empty, and the bounded stdout warning/error/leak scan
found no matching lines. Each `RA/cleanup.json` records no cleanup errors,
closed owner and no retained probe handle. Outer captures record a verified
owned tree and no timeout. These observations are kept separate from any
unrecorded current-PID census; process absence alone would not replace exits.

The original frozen harness SHA is
`193719fae8ab03ed44a5081195399cbbdeb7243854f0641abdc7b5d00acec14f`.
`Ooriginal/cost-stderr.txt` points to its line108 assertion that every phase's
ObjectDB count equal the before phase. Its observations are71046→71050→71055.
Sham and compact each record71047→71051→71055. Across-phase equality is thus
not supported even in the sham. This does not explain every object change or
certify leak freedom; it makes that assertion unsuitable as a cost-evidence
completion condition.

The frozen source shows the assertion occurs after `owner.finish()`, native
capture verification, clean-stderr check and one-batch check, but before later
source/helper rechecks and `result.json` publication. Original has
`failure.json` and no successful `result.json`; its collector exit1 must stay1.
The raw phase/native/capture data survive and can support a **separate derived
summary**, with any previously skipped source/helper checks performed offline
against the frozen artifacts and reported separately. Never relabel the
original invocation as having completed those statements.

Sham and compact execute harness SHA
`835bb732dcefb697b2847238c250068c98a326ecde9ef888d7e4e7dfc810f69f`.
The bounded source diff adds sham selection/its no-op and removes the final
across-phase equality assertion; original/compact collection phase ordering
is otherwise retained. Keep both helper versions. The derived correction must
preserve the executed old helper, assertion traceback and collector exit;
there is no reason to rerun the original engine just to manufacture a green
collector result.

## Decision and claim boundaries

Proceeding to one new compact HTTP→native→joint-ACK diagnostic is justified by
this cost evidence, provided the coordinator freezes its effective helper/
caller/project hashes, preserves the compact scope fields, leaves the A/B
clear callback out of the full-sequence flow, and keeps the caller's post-return
counter/ACK validation. Do not transplant the original S83 analyzer's full-row
removal assumptions into compact snapshots. A new run ID must retain base and
overlay identities separately; any parser/import integration check is scoped
to that new composition, not a repeat of these terminal cost arms.

The original gate/profile, RSS warm baseline,1000-command/100-cycle sequence,
counter limits, timing limits and35-batch maximum remain unchanged. Additional
probe-side memory observations may explain failures but never replace or
correct official samples. This diagnostic is explicitly ineligible for
acceptance; a521ms collector and its retained2.3MiB increase in a short arm do
not guarantee that it stays below any gate later in the full workload.

The cost experiment uses one semantic cycle near startup, sequential arm order
and one execution per arm. It has no randomized/repeated population, no
500-cycle/HTTP-conditioned state, and no later growth-trigger execution. It
supports an engineering decision to use the cheaper probe, not a universal
memory bound. Additional short repetition is warranted only if new evidence
contradicts this effect or the integration changes the collector materially.

In particular, **reject** the claim that S82's entire122851328-byte rise is
now proven census-only. Original cost RSS rises117919744 bytes in a different
editor history; the numerical similarity supports the hypothesis but is not
byte-for-byte causal accounting. S82's separate2044.2252ms first host-response
interval also remains unexplained. Neither result fixes or explains S81's
unmodified-run ObjectDB71128→71130 growth at batch15. A later nonreproduction
does not close that gap.

GT-06 still requires ten fresh complete35-batch pairs, successful original
gates/ownership, a final source/artifact seal and two new independent
same-manifest critics. This bounded review supplies none of those acceptance
verdicts.
