# GT06 Formal25 critic package

## Trạng thái

Formal25 đã hoàn tất hai pair trên cùng source closure. Bằng chứng benchmark
đạt các kiểm tra lắp ghép và verifier offline, nhưng GT-06 vẫn **chưa
ACCEPTED**. Coordinator không ký thay critic. Owner cần chuyển nguyên gói này
cho hai phiên review độc lập, dùng hai model khác nhau, cùng source/profile/
dataset hash, rồi lưu nguyên văn hai báo cáo trước khi quyết định nghiệm thu.

- Formal ID: `gt06-o4-formal-25`
- Pair 0: `gt06-o4-formal-25.r00.a01`, 35 mẫu, actual child/editor/import exit 0
- Pair 1: `gt06-o4-formal-25.r01.a01`, 35 mẫu, actual child/editor/import exit 0
- Source closure: `727f9039c1cc83239f5ef1daff13de5e92e37b5ba442e64be8341ca058800b58`
- Profile: `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`
- Dataset SHA-256: `3b0da65e10ea4425bd06d4c2ef7a446dde171a1e0b56fd125301ed1b6ea0a15a`
- Summary SHA-256: `9b8e70f91ac4c08cabe592c96387aa3d88ed01038788fc4a90dda19fe88e84a2`
- Campaign capture SHA-256: `fb6c877d06667ddb293d3961bc90aa46ad43b48541a3c26e1d88cf1f84d1c914`

Raw evidence remains under
`8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25/` and its supervisor
directory. The F-tier archive and manifest are:

- `studio/.local/reviews/gt06-o4-formal-25-f-tier.zip`
- `studio/.local/reviews/gt06-o4-formal-25-critic-package/raw-manifest.json`
- ZIP SHA-256: `0e4e8e94d5860c1b3ba6cf63b84cb15de31ebd2cd3e724e035b2dbfd174572a2`
- Raw manifest SHA-256: `49f7e497e9282cc77fd194542a76a37c4e5fc682e53caff969b29b828cbd7996`

The exact formal Scheduler task reached Ready with result 0, its instances were
empty, and the exact task was deleted only after terminal closeout. XML,
registration/start/return and deletion receipts remain in the supervisor raw
directory. No old run was resumed, and no old raw verdict was overwritten.

## Independent verification performed

The following read-only checks were run after the campaign ended:

1. `benchmark_assembly.assemble_run` rebuilt both runs from their immutable
   `assembly-manifest.json`; each returned 35 samples and the expected source
   and profile binding.
2. `assemble_dataset` rebuilt the two-run dataset byte-for-byte equal to the
   stored `dataset.json`; `benchmark_profile.summarize_dataset` returned
   `status=PASS`, with no failures or gaps.
3. The campaign verifier replayed source closure, snapshot hashes, campaign
   capture, run captures, actual exits, natural tree exits, Job active count,
   zero/closed state and retained-handle flags. It also rechecked the O7 host
   prerequisite: 49 batches, 1832.842787 active seconds, watchdog verified,
   maximum gap 444.9745 ms, and O7 metrics pass.

Reproducible read-only command:

```text
PYTHONPATH=8-9-hh3d-3 python -B 8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25-critic-package/verify.py --studio 8-9-hh3d-3/studio
```

The command does not start Godot, Blender, Docker, a campaign, or a retry. It
needs the original workstation paths and retained O7 control inputs.

## Review boundaries

Formal25 proves the benchmark lane (F13/F14 evidence), not all functional
gameplay requirements. F01–F12 and TQ00 remain separate authority-0 functional
packets and need their own source pins, postconditions, true exits, cleanup and
critic review. In particular, the older S133 functional closure
`1a2b2b392a39afc7dc0052b66a96f751c2b41261b38f6d0bedc9346913f8db16` and helper
freeze `eab399...` must not be relabeled as Formal25. Formal25's fixture HTTP
lane and direct native fixture cycles do not by themselves prove an authored
game, full product gameplay, Blender asset publication, Android export or
human playtest.

Pending artifacts: `critic-01.json` and `critic-02.json`. Until both reports
explicitly say `TICK=yes` for these exact hashes, GT06 remains unaccepted and
GT07 remains closed.
