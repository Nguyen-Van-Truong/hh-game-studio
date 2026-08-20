# Negative fixtures for tools/godot/policy_validate.py --self-test.
#
# fail_*.toml MUST be rejected. test_no_secrets.py skips these files so the
# fake sk-/ghp_/token= values are not treated as a repo leak.

Each `fail_*.toml` is otherwise a complete policy with one defect:

| File | Expected code |
|------|----------------|
| `fail_path_dotdot.toml` | `E_PATH_DOTDOT` |
| `fail_path_absolute.toml` | `E_PATH_ABSOLUTE` |
| `fail_arbitrary_shell.toml` | `E_ARBITRARY_SHELL` |
| `fail_secret.toml` | `E_SECRET` |

Pass case: repo `.hh-agent/policy.example.toml`.
