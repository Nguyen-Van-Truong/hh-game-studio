# S104 versioned native-save reader

Date: 2026-09-19 (Asia/Saigon)

This is a read-only derived revalidation of the exact S103 raw bytes. It did
not launch Godot, alter a raw capture, alter the formal source, or convert a
diagnostic into a benchmark sample.

## Narrow correction

The S103 reader rejected every complete row because it required
`process_entry_frame == save_process_exit_frame`. The emitted marker contract
allows the authored frame to advance during save dispatch. `read_native_save_v104.py`
keeps the original source/profile/run/PID/cycle/sequence/hash bindings and the
next-dispatch equality, while accepting the observed monotonic order:

`process_entry_frame <= save_process_exit_frame < next_process_entry_frame == next_process_exit_frame`.

The signal frame remains bounded by the process-entry and next-process-exit
frames. The versioned reader is evidence tooling only; the formal runtime
source and acceptance gates are unchanged.

## Same-input results

| input | complete rows | reader classification | threshold crossings | lifecycle |
|---|---:|---|---:|---|
| `gt06-s103-prefix-preflight-06` | 100/100 | `OBSERVED_NATIVE_INTERVALS` | 0 | diagnostic forced stop recorded |
| `gt06-s103-prefix-01` | 600/600 | `OBSERVED_NATIVE_INTERVALS` | 0 | diagnostic forced stop recorded |

The derived output retains `formal_acceptance=false` and
`eligible_for_dataset=false`. It also retains the missing natural target exit;
no PASS, no no-leak claim, and no engine causation is inferred. The longest
prefix gap remains 728.622 ms (batch 1); batch 5 is 642.433 ms.

## Hashes

* `read_native_save_v104.py` — `9f4d59895a4e3da5f82b371e04c27223321b473fbd829b9cff70d53d1fb553cc`
* `preflight-06.reader-v104.json` — `ae298bb4e5932b4c9ca86a10b57fe4f2a6754fe233f744e661ea1d3c1d4bdd32`
* `prefix-01.reader-v104.json` — `d247f42e2fd4ab27821600f12ae2a5f63361a5ab9682331dee27e433eecccbb4`

Next action remains attribution-only: inspect retained handle identity if
needed, then prove a narrow repair before any formal retry. Keep the original
10 fresh pairs x 35 batches gate and all prior failures.
