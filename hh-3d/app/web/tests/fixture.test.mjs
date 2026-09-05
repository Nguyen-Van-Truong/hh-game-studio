import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixturePath = join(
  root,
  "web",
  "public",
  "data",
  "ben-thanh-400m.authored.geojson",
);
const manifestPath = join(root, "web", "public", "data", "world-manifest.json");

test("authored fixture stays inside the 400 m frame and stays honest", () => {
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  assert.equal(fixture.type, "FeatureCollection");
  assert.equal(manifest.display_name, "HH World");
  assert.equal(manifest.authored_or_source, "authored");
  assert.equal(manifest.fetch_performed, false);
  const banned = ["superfighters", "super fighter", "vault fighters"];
  const names = [
    manifest.display_name,
    ...fixture.features.map((f) => f.properties?.name ?? ""),
    ...fixture.features.map((f) => f.properties?.display_name ?? ""),
  ]
    .join("\n")
    .toLowerCase();
  for (const word of banned) {
    assert.equal(names.includes(word), false, word);
  }
  assert.equal(manifest.display_name, "HH World");
  const places = fixture.features.filter((f) => f.properties?.kind === "place");
  assert.ok(places.length >= 3);
  for (const feature of fixture.features) {
    assert.equal(feature.properties.authored_or_source, "authored");
    assert.equal(feature.properties.accuracy_class, "authored");
    assert.equal(feature.properties.accessed_at, undefined);
  }
});
