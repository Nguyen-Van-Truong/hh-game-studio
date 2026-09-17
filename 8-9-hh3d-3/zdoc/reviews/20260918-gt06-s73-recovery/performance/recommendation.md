Read-only production performance study — GT-06 S73, 2026-09-18

**Recommendation:** use `hashlib.sha512()` only for the private in-memory
fingerprint in `VerifiedJournal._snapshot`, retaining the existing 65,536-byte
read loop. The paired synthetic measurement found a material improvement
without adding native handles, retaining journal bodies in RAM, changing a
transaction boundary, or changing the persisted SHA-256 record checksums.
This is a candidate implementation choice, not a benchmark or acceptance PASS.

The coordinator owns the production edit and all subsequent validation. This
worker read production sources, wrote the seven artifacts listed below, and
ran only three isolated hashing harnesses. It launched no Godot/Blender,
studio unit suite, HTTP host, or native campaign and changed no production
file, core contract, plan, gate, or raw failure evidence. No critic role or
acceptance signature is claimed.

Initial repository HEAD was `a15cd42c5fcfa8d7c07faabd9c0247a7ab5040ac`.
Tracked status was clean when the study started; existing untracked review
artifacts were left alone. The baseline production hashes recorded in
`hash-scan-results.json` were:

- `studio/host/replay/verified_journal.py`: `3bdc1414166c132236149629b14bde456d142578cc3d08e0fd1faf5a4285d5eb`
- `studio/host/core/journal.py`: `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6`
- `studio/host/core/transport.py`: `1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0`

**Measured evidence.** Each harness generated its own deterministic 32 MiB
synthetic file under this directory. Every measured operation included open,
regular-file/single-link checks, before/after fstat, reading and hashing every
byte, cap/overflow handling, flush, fsync, and close. Measurements used a warm
file cache, a fixed randomized method order, and this workstation's Python
3.11.9. They excluded writer-lock acquisition, JSON replay, index lookup,
append, HTTP, and engines. Raw sample order, per-method samples, dataset
digests and harness hashes are in the JSON results. All host-observed process
exits were 0. The three reported harness wall times sum to 14.806 seconds.
The synthetic files were removed by their exact-path cleanup blocks; none
remains or belongs in Git.

First matrix, eleven measurements per method (`hash-scan-results.json`):

| SHA-256 scan implementation | Median ms per 32 MiB |
| --- | ---: |
| Existing allocating read, 64 KiB | 79.373 |
| Allocating read, 1 MiB | 85.877 |
| readinto, 64 KiB | 80.473 |
| readinto, 256 KiB | 76.541 |
| readinto, 1 MiB | 78.630 |
| readinto, 4 MiB | 78.076 |

The best buffer-only median improvement was about 3.6%, with overlapping
sample ranges. It does not establish a useful fix for the observed HTTP
timeout. Keeping the existing loop is simpler and isolates the meaningful
change.

Second matrix, nine measurements per method (`fingerprint-results.json`):

| Private fingerprint and scan | Median ms per 32 MiB |
| --- | ---: |
| SHA-256, existing 64 KiB read | 82.392 |
| SHA-256, 256 KiB readinto | 77.660 |
| SHA-512, 256 KiB readinto | 56.435 |
| BLAKE2b-256, 256 KiB readinto | 80.853 |
| BLAKE2s-256, 256 KiB readinto | 148.377 |

All candidate fingerprints detected a first-byte mutation with unchanged
length and exactly restored mtime. The harness also checked independent
`copy()` followed by append. These are hashing sanity checks, not replacements
for the production journal regression suite.

Final paired matrix, nine randomized rounds (`sha512-paired-results.json`):

| Private fingerprint and scan | Median ms | Min–max ms |
| --- | ---: | ---: |
| SHA-256, existing 64 KiB read | 76.177 | 74.323–88.977 |
| SHA-512, same 64 KiB read | 56.900 | 53.354–80.753 |
| SHA-512, 256 KiB readinto | 51.372 | 50.429–59.264 |

For the unchanged read loop, the ratio of medians shows 25.3% less scan time.
The median reduction calculated within individual paired rounds is 29.96%;
these are different statistics and should not be substituted for one another.
The larger-buffer SHA-512 result offers additional potential but is unnecessary
for the smallest candidate and still does not establish HTTP performance.

**Why the one-line factory change fits the existing boundaries.** The
`_verified_hash` field is confined to `verified_journal.py`: it is compared
internally and extended after an accepted local append. It is neither
serialized nor exported. `Journal._checksum` and the accepted serializer
remain SHA-256. SHA-512 is a standard `hashlib` constructor with the same
update/copy/digest interface; the private result becomes 64 rather than 32
bytes. See the [official Python hashlib documentation](https://docs.python.org/3/library/hashlib.html).

All existing safety mechanisms must remain intact:

- `Journal._mutating` and `lease_guard` retain the same permanent writer-guard
  boundaries, namespace checks, reloads, lease checks, and uncertainty rules.
- Every reload still reads all old bytes; no mtime-only, size-only, tail-only,
  hash-chain-only, or sidecar-only fast path is introduced. Replaced files,
  size changes and policy changes still invalidate the cache.
- A changed fingerprint still invokes accepted complete parsing before its
  recovery fsync, retaining checksum/truncation error precedence. A matching
  fingerprint still requires the recovery fsync before a receipt is exposed.
- Local append uses the accepted serializer and fsync, then copies and extends
  the same private hash algorithm. Failures still invalidate the cache.
  Dedupe indexes, pending reservations, archived receipts, tombstones, retry
  horizons and limits remain unchanged.
- Transport admission, durable pending/terminal records, post-effect readback,
  Stop admission closure/drain, and UNKNOWN/reconcile semantics do not change.
  The client timeout and all status, latency, RSS and campaign gates stay fixed.

`VerifiedJournal` is used by both `benchmark_commands.py` and the actual
`studio/host/replay/service.py`. Therefore a new candidate requires relevant
service/HTTP/adversary evidence as well as journal regressions and a new
benchmark closure; old S71 samples cannot be relabeled or resumed as its proof.

**Limits and rejected alternatives.** Full history work remains linear in
journal size for each operation and quadratic across growing fixed-size
batches. This study does not measure tail latency, disk-cold scans, antivirus,
lock contention, late-run HTTP behavior, or a full 10×35 campaign. It cannot
promise that a 25–30% scan reduction eliminates a rare two-second response loss
or meets the unchanged full profile. The coordinator's large-journal HTTP
check, affected regressions, and fresh native campaign must decide that.

A full raw byte arena was considered but not built or measured. The plan's
explicit rule that persistent results/tombstones must not all remain in RAM
rules it out here; preallocating/touching 64 MiB would also add that memory to
the resident baseline. It must not be introduced through an interpretation
that silently changes this contract. Compound admission transactions could
remove some repeated scans but require separate accepted-core/transport design
and equivalence review; this study does not propose such a change now.

Windows CNG SHA-256 was researched as a same-algorithm alternative, then left
unmeasured at the coordinator's direction once SHA-512 showed useful portable
gains. An unrun draft was removed. There is no CNG performance evidence or
production wrapper. CNG would add provider/hash lifecycle and failure handling:
Microsoft documents explicit [hash creation/cleanup](https://learn.microsoft.com/en-us/windows/win32/seccng/creating-a-hash-with-cng)
and an independent [duplicate hash object](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptduplicatehash)
for non-destructive digest/copy behavior. That complexity is unnecessary for
the current candidate.

**Reproduction and explicit stage allowlist.** From repository root, run each
script with `python -B -X utf8` and its path below, with other measurement
lanes stopped. Each harness has a bounded deadline/watchdog and only writes
inside this study directory. The paired harness imports only the neighboring
fingerprint harness; none imports studio code. The following seven files are
the entire study handoff; do not stage a directory wholesale or any synthetic
`.bin` payload:

1. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/recommendation.md`
2. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/hash_scan_microbench.py`
3. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/hash-scan-results.json`
4. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/fingerprint_microbench.py`
5. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/fingerprint-results.json`
6. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/sha512_paired_microbench.py`
7. `8-9-hh3d-3/zdoc/reviews/20260918-gt06-s73-recovery/performance/sha512-paired-results.json`
