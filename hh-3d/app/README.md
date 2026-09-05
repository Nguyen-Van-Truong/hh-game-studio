# HH World

Local web map proof. Display name: **HH World**.

This is an authored 400 m approximation around Bến Thành, Ho Chi Minh City
(center 10.7725, 106.6980). It is not a live map, not OSM, not a digital twin,
and not 1:1.

## Open

Preview (the player URL):

```text
http://127.0.0.1:4175/
```

Do not use 4173 (Hòn Gió demo) or 4174.

```bash
cd hh-3d/app/data-pipeline
python build_authored_fixture.py
python validate_fixture.py

cd ../web
npm ci
npm run typecheck
npm test
npm run build
npm run preview
```

Dev server if needed: `http://127.0.0.1:5175/` (`npm run dev`).
Start only one HH World preview.

## Honesty

- Authored geometry and fictionalized place names
- UI must show `approx` and `Map data as of`
- Local bookmarks only; no login
- No Cesium, Google tiles, Unreal, or map fetch

See `PROGRESS.txt` and `decision-records/2026-09-03-r0-wp0-hh-world-web.txt`.
