# Scrap Yard art generator

Regenerate every project PNG and `games/scrap-yard/assets/index.json`:

```
python tools/art-gen/gen_scrap_yard_art.py
```

Run from the repo root. No pip packages are required (stdlib `zlib` + `struct` write RGBA8 PNGs).

To edit a sprite, open `gen_scrap_yard_art.py`, find its ASCII map (one character per pixel), and change characters. The sprite's palette dict above the maps says what each character paints; `.` is always transparent. Re-run the command to overwrite the PNGs and `tools/art-gen/contact_sheet.png`.
