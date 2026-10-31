# Chibi R5 Blender heads

The source is `chibi_r5_heads.blend`, authored by `tools/build_chibi_blender_heads.py`.
Each named mesh is one character/expression cell. Faces, ink ribbons, asymmetric
hair clumps, cel shadow patches, eyes and accessories are editable planar Blender
meshes ordered on Z. Materials use emission, with an orthographic pixel camera.
The atlas uses no raster reference extraction, spheres, cylinders, or plastic
lighting. The existing master sheet supplies visual direction only.

## Rebuild

From the Superagent directory, run the pinned Blender:

```powershell
& ../studio/.local/tooling/blender-5.2.3-windows-x64/blender.exe --background --factory-startup --disable-autoexec --offline-mode --python tools/build_chibi_blender_heads.py
```

Use a single Blender process for this project path. The builder validates the
22 IDs against the data registry, stages output, hashes it, then replaces the
atlas and manifest. The `.blend` is saved before publication. No Godot process is
launched by the builder.

## Runtime contract

- Atlas: `assets/sprites/chibi_brawler/r5_heads/head_atlas.png`, 1024 × 3072 RGBA.
- Seven expressions plus blink across columns, 22 base characters plus two
  transformation rows (`goku_awakened`, `naruto_awakened`); all cells 128².
- Facing right; mirror the whole cell for left. Transparent cell margins remain.
- Density: 12.8 pixels/world unit, or `units_per_pixel = 0.078125`.
- Skull center pivot: `(64, 73)` pixels. Draw the cell in world rectangle
  `(-5, -5.703125, 10, 10)` relative to the skull center.
- Skull reference: y 27..119 = 92px = 7.1875 world units (rounding of 7.2u).
- Neck anchor `(66, 119)`; maximum designed hair extension 24px = 1.875u.
- `manifest.json` provides every rect/pivot, identity topology and source hashes.

Johnny has asymmetric dark hair and a distinct orange forelock. Other identities
include a buzzcut, slick undercut/glasses, ponytail, violet bob, scarred mohawk,
field/patrol/straw hats, ginger/dark beards, visor, blond quiff, bandana, clown
tufts/nose, sun spikes, temple implant, silver bangs, teal waves/fin, dragon spikes,
fox headband/whiskers and a bare skull. The transformation rows retain their
underlying identity while using golden hair / teal eyes or gold / red eyes.
Mouth and eye geometry change for the seven expressions. Final aesthetic
acceptance still needs the live camera/menu/HUD review.

## Provenance and scope

Polygon geometry and rendering code are original. Recognizable anime character
designs remain third-party intellectual property: these files are an internal
art study and do not assert public-release clearance. The `.blend` path in the
manifest records provenance only; `.gdignore` excludes authoring sources from
Godot asset import.
