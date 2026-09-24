# S238 — GT07–GT10 capability catalog (read-only)

This packet inventories source scaffolding while GT06 remains the current valid work package with zero accepted full runs. It does not open, tick, or dispatch GT07–GT10, and it is not GT06 evidence. Paths are observed from the current checkout with per-file hashes; caches and generated `.godot`/`__pycache__` files are excluded.

The catalog separates present scaffolding from acceptance still unproven. GT08 still requires a real Android device and clean Windows/Linux target matrix. An unavailable `adb` command would be an environment gap, not proof that a device is absent.

Verify without starting an engine:

`python -B zdoc/reviews/20260924-gt07-10-capability-catalog-s238/verify.py`
