# Scrap Yard scene generator

Regenerate `games/scrap-yard/scenes/main.gscene.json`:

```
python tools/scrap-yard/gen_scene.py
```

Run from the repo root. The script writes canonical-safe floats only
(`0.25` / `0.5` / `0.75` / `1.5` / …) so `gs-player --project` pack accepts
the scene.
