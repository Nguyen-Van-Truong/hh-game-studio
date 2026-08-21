# Negative fixtures for tools/godot/policy_validate.py --self-test.
#
# fail_*.toml MUST be rejected. Do not put sk-/ghp_/PAT blobs in these files;
# fail_secret.toml uses a non-placeholder session_token (E_SECRET) so the tree
# scanner can walk this directory.

Each `fail_*.toml` is otherwise a complete policy with one defect:

| File | Expected code |
|------|----------------|
| `fail_path_dotdot.toml` | `E_PATH_DOTDOT` |
| `fail_path_absolute.toml` | `E_PATH_ABSOLUTE` |
| `fail_arbitrary_shell.toml` | `E_ARBITRARY_SHELL` |
| `fail_secret.toml` | `E_SECRET` |
| `fail_addon_jail.toml` | `E_ADDON_JAIL` |

Pass case: repo `.hh-agent/policy.example.toml`.

Runtime A8 jail (dotdot, absolute, junction/symlink, device, overlong, addon lock)
is executed by `tests/bootstrap/test_policy.py` against the sidecar policy engine.
