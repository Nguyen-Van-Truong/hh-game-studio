# R0-WP1 critic — 2026-08-20

Independent critic. Did not tick, commit, push, or repair.

## Verdict

**PASS-WITH-GAPS**

Core freeze is real: annotated tag + archive branch both point at
`698e6088cc6d2c0a9a7b74021de409d46e5971aa`, not at WP1
`7cf0a26846cf995c27e2dcaaff24547fdfdae80c`. Tagged tree is 354 files of the
old engine. DoD “phục hồi nguyên trạng” for that engine holds. Decision
`GODOT-REBOOT-2026-08-20` is in git, not chat-only.

Do **not** tick. Do **not** start R0-WP2 until LOG exists and the P1s below
are fixed or explicitly waived.

## What git actually shows (not the implementer story)

| Ref | SHA |
|-----|-----|
| `legacy-rust-engine-2026-08-20^{}` (annotated tag) | `698e6088cc6d2c0a9a7b74021de409d46e5971aa` |
| `archive/legacy-rust-engine-2026-08-20` | `698e6088cc6d2c0a9a7b74021de409d46e5971aa` |
| Claimed WP1 | `7cf0a26846cf995c27e2dcaaff24547fdfdae80c` |
| `main` / `origin/main` **now** | `50e069347c50da6ad97542c3359bdddc4e66287a` |

The “reboot files still dirty” claim is **false at critic time**. After WP1,
`50e06934` committed `AGENTS.md` + `zdocs/20-8-godot-agent-autopilot-plan.txt`
and that commit was **pushed**. Worktree is clean. Tag/archive branch were
**not** pushed.

## P0

None that break engine recovery or tag identity.

## P1

1. **Freeze SHA-256 for `docs/DECISIONS.md` is unreproducible.** README claims
   `a3c5e706cf06d277a381dea9c298e3f831aaf7822ef61eb32e531f039a8081a5`.
   Applying `legacy/reboot-worktree.patch` onto `698e608:docs/DECISIONS.md`
   yields git blob `bf983ff168785b5437747e36a39bcaab37960fdc` (matches the
   patch `index` dest, **not stored in the object DB**) and SHA-256
   `775be944baf3916af4c77057a76e239bd1453acf2e593214bde24aee34ada496` (LF).
   WP1/current file hashes to `f19625b148acac05b1f267f0b83623b0bd865d049fc40594b160bf1769ffb6ea`
   (worktree CRLF). None equal the claimed digest. Verify “inventory/patch
   hash có kết quả” is a **failed check**, not a pass. AGENTS/20-8 hashes
   match the smudged worktree; DECISIONS does not match patch or commit.

2. **Named freeze refs are local-only.** `git ls-remote origin` has
   `refs/heads/main` @ `50e06934` and **zero**
   `refs/tags/legacy-rust-engine-2026-08-20` /
   `refs/heads/archive/legacy-rust-engine-2026-08-20`. A GitHub clone cannot
   `git checkout legacy-rust-engine-2026-08-20`. SHA `698e608` is still an
   ancestor, so recovery by hash works; the WP deliverable was the tag/branch
   **names**. Pushing `main` without the archive refs is an incomplete freeze
   publish.

3. **Post-WP1 commit `50e06934` is not R0-WP2 and stole WP2 files.**
   Message: “Updated AGENTS.md and DECISIONS.md …” — **DECISIONS.md did not
   change** in that commit. Diff is TRANSITION stanza + the 20-8 plan.
   No `R0-WP2:` prefix. No `LEGACY / NON-AUTHORITATIVE` banners on the 16-8
   plans. No `AUTHORITATIVE_PLAN=1` singleton test. Do not tick WP2 off this
   commit. It does, however, put the 20-8 plan into git (good), so the
   earlier “untracked authoritative plan” hole is closed **after** WP1, not
   by WP1.

4. **LOG empty. A20 / §7.2 / §13.4.** R0-WP1 checkbox is still `[ ]`.
   There is no 5–15 line LOG. Coordinator must not tick on archive mechanics
   alone.

5. **WP1 patch is not a full reboot-file sidecar.** Spec: lưu patch của file
   user/reboot. Patch is AGENTS + pre-pointer DECISIONS only. 20-8 plan was
   untracked at freeze and absent from the patch. Mitigated later by
   `50e06934`, not by the WP1 allowlist.

## P2

1. **Unsigned tag.** `git tag -v` → `error: no signature found`. Spec does
   not require GPG. Acceptable gap, not a P0.

2. **`git fsck --full` dangling tree `288378fc9de0b4d913ceb6078ec2cf421fda2453`.**
   Older **subset** of the engine (no `gs-player`, no `games/`, no
   `legacy/`). Not an error. Not required to recover `698e608`. Ignore for
   DoD; do not delete objects hoping it “cleans” the archive.

3. **`AGENTS.md` freeze hash is mixed EOL** (54 CRLF + 15 LF) matching the
   worktree smudge, not blob `e2b6eb6`. Fragile. Recheck after any checkout.

4. **README recovery `git checkout legacy-rust-engine-2026-08-20` from current
   clean `main` will drop the now-tracked 20-8 plan from the worktree.** SHA
   in README is correct (do not “fix” it). Recover engine in a separate
   worktree; get the plan back with `git checkout main`.

5. No force-push. `origin/main` fast-forwarded `698e608` → `7cf0a26` →
   `50e06934`. A15 rewrite: not found.

## Checklist (attack)

1. Annotated tag, not lightweight. Message forbids WP-M6/M7/M8. **PASS**
2. `tag^{}` == `698e608` == archive branch ≠ `7cf0a26`. **PASS**
3. Tagged `AGENTS.md` has no TRANSITION; tagged `DECISIONS.md` has no
   GODOT-REBOOT heading. **PASS**
4. Tagged tree has both 16-8 zdocs, `crates/`, `games/`; no `zdocs/20-8-…`,
   no `legacy/`, no `target/`. 354 files. Inventory counts match README.
   **PASS**
5. WP1 allowlist: `docs/DECISIONS.md`, `legacy/README.md`,
   `legacy/reboot-worktree.patch` only. **PASS**
6. Patch is freeze-time AGENTS+DECISIONS vs `698e608`, not a fake 20-8
   archive. README admits the plan was untracked. Checkout of the **tag**
   does not require the 20-8 plan for engine recovery. After `50e06934`,
   checkout of the tag **does** remove the plan from the worktree because it
   is tracked on `main`. Engine DoD still holds. **GAP (see P1.5 / P2.4)**
7. Duplicate `GODOT-REBOOT` heading? **No.** One heading, completed in WP1
   with `legacy_base_commit` / tag / branch. Not a second decision.
8. `git fsck`: no errors. Dangling tree: P2, not a recovery blocker.
9. Unsigned tag: P2, not P0.
10. Remote: main updated by fast-forward; tag/archive **not** on origin. No
    force-push detected.

## Should coordinator tick R0-WP1?

**no**

## Should coordinator proceed to R0-WP2?

**no** (dependency is a ticked R0-WP1). After LOG + P1.1/P1.2, WP2 must
resume from `50e06934` and finish banners/test; do not wrap that commit as
WP2.

## Minimal repair (implementer, not critic)

1. Recompute SHA-256 of the **exact** freeze DECISIONS bytes (patch result
   or document that the hash is of a mixed-EOL worktree file) and correct
   `legacy/README.md`. Do not retag `698e608`.
2. Push **without force**:
   `git push origin refs/tags/legacy-rust-engine-2026-08-20`
   `git push origin archive/legacy-rust-engine-2026-08-20`
3. Paste a §13.4 LOG under R0-WP1 (commands, SHAs, fsck, clone-from-tag
   evidence, remaining gaps). Then tick.
4. Leave `50e06934` in place. Next WP is R0-WP2 from current `main`.

## Git commands run (abridged)

```
git cat-file -t legacy-rust-engine-2026-08-20          # tag
git rev-parse 'legacy-rust-engine-2026-08-20^{}'       # 698e608…
git rev-parse archive/legacy-rust-engine-2026-08-20    # 698e608…
git tag -v legacy-rust-engine-2026-08-20               # error: no signature found
git diff-tree --name-status 7cf0a26                    # M DECISIONS, A README, A patch
git ls-tree -r --name-only 698e608 | measure            # 354
git cat-file -e 698e608:zdocs/16-8-…                    # both plans exist
git fsck --full                                        # dangling tree 288378fc only
git ls-remote origin                                   # only refs/heads/main @ 50e06934
git clone -b archive/legacy-rust-engine-2026-08-20 …   # HEAD 698e608, 354 files, no 20-8
```
