# WP-M-1-c — WAL crash / fault-injection POC

Spike crate: `experiments/wal-spike/` (standalone `Cargo.toml`). Not production.

Rust used to compile: rustc 1.93.1, cargo 1.93.1.

## Record format

One **atomic JSONL record per txn** (not begin/commit two lines). File:
`.gs/wal/wal.jsonl` (append-only).

```json
{"seq":1,"kind":"txn","txn_id":"t-000001","command_id":"01…","actor_id":"act_01",
 "base_revision":"r-000000","new_revision":"r-000001",
 "commands":[{"method":"counter.inc","params":{"delta":5}}],
 "inverses":[{"method":"counter.inc","params":{"delta":-5}}],
 "schema_version":1,"ts":"<unix-millis>","crc32":"a1b2c3d4"}
```

- `commands` / `inverses`: **full** normalized method+params (replayable; not a digest).
- `crc32`: 8 lowercase hex digits, CRC-32 (crc32fast) over the UTF-8 JSON of the
  same object **with `crc32` omitted** (struct field order, compact serde_json).
- Tiny document: `counter: i64` + `entities: BTreeMap<String, i64>`.
  Methods: `counter.inc`, `entity.set`, `entity.delete`. One txn bumps revision once.

ACK cursor (needed so a flushed-but-unapplied record is not treated as committed):
`.gs/ack.jsonl` append-only, last complete line wins
`{"seq":1,"revision":"r-000001"}`.

Autosave: `.gs/autosave/<scene>.<ts>.json` + `<scene>.<ts>.sidecar.json`
`{last_committed_seq, revision, doc_sha256}` via **tmp + fsync + rename**.

## Fsync policy

**Default: every record** (MASTER 5.5 / Appendix A). After each WAL append and
each ACK append: `File::sync_data()` (Rust equivalent of `fdatasync`). Autosave
tmp files are also `sync_data`'d before rename.

Relaxed group-commit (100ms) is **not** implemented in this POC. Measure on this
machine is in “Test evidence” below. If p50 fsync/txn > 2ms on SSD, production
may consider group-commit — that belongs in `docs/DECISIONS.md` at G1, not here.

## How the 4 crash cases are simulated

Real `kill -9` is awkward and racy on Windows. Each test **closes/truncates at
the same durable moment** as a crash: the bytes left on disk match that instant.

| Case | Moment | Simulation |
|------|--------|------------|
| **(a)** mid-record write | process dies while the JSONL line is half-written | write `len/2` bytes of the line, `sync_data`, return `Error::Crash`. No apply, no ACK. |
| **(b)** after write+flush, before apply | record is durable; apply/ACK never ran | full line + `sync_data`, then return `Error::Crash`. In-memory doc unchanged; ACK log unchanged. |
| **(c)** mid tmp+rename autosave | tmp document+sidecar exist; dest names do not | write+sync `*.json.tmp` and `*.sidecar.json.tmp`, skip `rename`, return `Error::Crash`. |
| **(d)** between two records | txn1 ACK'd; txn2 never started | drop `Session` after ACK of record 1 (no second `commit`). |

Recovery after each: `Session::open` again → document revision == last ACK;
no lost ACK'd txn; no apply of un-ACK'd txn.

## Recovery algorithm

1. Read ACK cursor (last complete `ack.jsonl` line; partial last line ignored).
2. Scan WAL: parse each JSONL line, verify `crc32`.
   - **Truncated tail** (incomplete last line, or last line crc-fail and nothing
     after): cut the file at the last good ACK'd byte. Do not apply the tail.
   - **Corrupt middle** (bad/incomplete record with another record after it):
     **stop**. Do not guess, do not skip, do not apply later records.
3. Load latest autosave whose sidecar parses and `doc_sha256` matches. Ignore
   `*.tmp` and sidecar-less/hash-mismatch files. If none (or newer than ACK),
   start from empty document.
4. Replay WAL records with `last_committed_seq < seq <= last_ack.seq`. Verify
   `base_revision` chain. **Never apply `seq > last_ack.seq`** (case (b)).
5. Truncate WAL to the end of the last ACK'd record (drops (a) partial tail and
   (b) flushed-un-ACK'd complete record).
6. Resulting in-memory document revision must equal the ACK cursor.

I2 order on the live path: validate → write record → FLUSH → apply → persist ACK
→ return ACK to caller.

## Test evidence

Date: 2026-08-16. rustc 1.93.1 / cargo 1.93.1. Windows.

```
cargo fmt --check          # ok
cargo clippy --all-targets -- -D warnings   # ok
cargo test -- --nocapture
```

```
running 4 tests
test document::tests::validate_rejects_unknown_method ... ok
test record::tests::crc_round_trip_and_tamper ... ok
test document::tests::apply_then_inverses_restores_document ... ok
test recovery_unit::unacked_complete_record_is_not_in_cut_length ... ok
test result: ok. 4 passed; 0 failed

running 7 tests
test crash_a_mid_record_write ... ok
test crash_b_after_flush_before_apply ... ok
test crash_c_mid_tmp_rename_autosave ... ok
test crash_d_between_two_records ... ok
test i6_corrupt_middle_stops ... ok
test happy_path_replay_from_autosave_plus_wal ... ok
fsync-every-record: 20 txn in 101.055ms (5.05275ms/txn)
test fsync_overhead_smoke ... ok
test result: ok. 7 passed; 0 failed
```

Four MASTER 5.5 cases: **all pass**.

| Case | Recovered revision | Un-ACK'd applied? | ACK'd lost? |
|------|--------------------|-------------------|-------------|
| (a) mid-record | last ACK (`r-000002`) | no | no |
| (b) flush then crash before apply | last ACK (`r-000001`) | no (flushed seq=2 cut) | no |
| (c) mid autosave rename | last ACK (`r-000002`, replayed from older autosave + WAL) | no | no |
| (d) between records | last ACK (`r-000001`) | n/a (seq=2 never written) | no |

I6 extra: `i6_corrupt_middle_stops` — bad crc on the middle line → `Error::CorruptMiddle`, no guess.

Fsync overhead (debug, this machine): **~5.1 ms/txn** for 20 commits (WAL `sync_data` + ACK `sync_data` each). Appendix A target “if >2ms/txn on SSD → consider group-commit” — flag for G1 / `docs/DECISIONS.md`, not changed in this spike. Default remains every-record.
