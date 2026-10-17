# Relay Yard visual pass — 2026-10-15

All three images were generated with the built-in OpenAI ImageGen tool. Only the project's original courier/mechanic sheets were supplied as identity references. No reference-game image, sprite, code or sound is included. PNGs are unmodified generated outputs; cropping uses source rectangles in metadata/renderers. Generated raster is not a substitute for the layered editable source required by SA-10.

## Action extension

Saved asset: `characters/shared/fire_throw_v2.png` (1774×887 RGBA). Source output: `exec-254b4f59-4b13-498e-9caf-e37b3adee586.png`.

Prompt: Original transparent 2×4 sprite action extension; row 1 blue-haired courier with teal jacket/tan scarf/navy pants/brown boots, row 2 auburn ponytail mechanic with rust jacket/teal scarf/navy pants/dark boots. Both facing right. Columns: two-arm empty-handed pistol aim, recoil, throw windup, throw follow-through. Crisp arcade anime pixel art, broad clusters, restrained tones, readable at 60 pixels tall, no weapons/ground/text. Preserve supplied original character identities and proportions.

The `visual.json` schema v2 selects an atlas, region, standing scale, foot and grip per frame. Upper-body aim articulation, roll/hit/power in-betweens, layered source and visual approval remain pending. The throw windup is reserved: current gameplay releases immediately, so presentation starts on follow-through and cannot delay combat.

## Industrial background

Saved asset: `backgrounds/relay_hall_v2.png`. Source output: `exec-5de8d676-52ea-49a1-8346-5e56d85306ae.png`.

Prompt: Original 16:9 side-on industrial relay maintenance hall at night, cobalt/teal restrained arcade pixel art; unequal bays with ribbed electrical cabinets, recessed central ventilation turbine, warm amber service light, secondary pipes/rivets/diagonal bracing, overhead beam/work lights. Upper quarter quiet for HUD; dark continuous background in lower half with no floors/platforms/ladders/characters/foreground props/text/logos. Three depth layers, clear broad shapes, original architecture, no existing layout copied.

## Object atlas

Saved asset: `props/relay_objects_v2.png` (1536×1024 RGBA). Source output: `exec-b56d991d-a3cd-4fb5-bdf3-66e784a6b60c.png`.

Prompt: Original transparent 2×2 front-view pixel-art object atlas: honey oak plank crate with diagonal brace/black corner straps; red-orange explosive barrel with steel hoops and a cream hazard diamond; dark teal wide armored cover cabinet with vents/amber status lights; glass panel with dark border, blue glass, diagonal reflections and a corner crack. Limited four-tone materials, bold clusters readable at 32–50 pixels high, whole isolated objects, no ground/shadow/text/logos/isometric perspective.

## Runtime contract

Fighter physics, map coordinates, combat timing and deterministic snapshots are unchanged. Weapons use one renderer for held art, pickups and HUD. New props keep existing displayed bounds; the provisional prop/gameplay geometry still needs the SA-06 review. No visual acceptance or reference parity is implied by image generation or headless tests.
