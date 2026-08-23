# PROJECT_BRIEF

## genre

- **value:** match-3 puzzle
- **player fantasy:** clear one board by matching three
- **out of scope:** live events, coins shop

## camera

- **mode:** fixed
- **zoom / limits:** 1.0
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** no

## input

- **devices:** mouse
- **actions:** select, swap, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** gem icons with high contrast
- **palette / silhouette notes:** jewel primaries
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** calm loop
- **SFX set:** select, match, drop
- **bus layout:** Master / Music / SFX
- **license source:** original

## save

- **needed:** yes
- **slots / autosave:** autosave last board
- **location:** user data
- **contents:** score and remaining moves

## acceptance

- swapping two adjacent gems that match removes them
- invalid swaps bounce back
- tests define match rules before bulk gem art
