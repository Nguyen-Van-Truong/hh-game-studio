HH World data pipeline (local authored proof)
NETWORKING=OFF
FETCH=NO

This folder does not download OSM, Overture, Cesium, or Google tiles.

Commands:
  python hh-3d/app/data-pipeline/build_authored_fixture.py
  python hh-3d/app/data-pipeline/validate_fixture.py

Canonical fixture:
  fixtures/ben-thanh-400m.authored.geojson
Published copy (must match byte-for-byte):
  ../web/public/data/ben-thanh-400m.authored.geojson
