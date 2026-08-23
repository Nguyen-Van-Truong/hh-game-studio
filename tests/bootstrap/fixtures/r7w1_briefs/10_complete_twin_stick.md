# PROJECT_BRIEF

## genre

- **value:** twin-stick shooter
- **player fantasy:** dodge and shoot one arena wave
- **out of scope:** online arena, loot boxes

## camera

- **mode:** follow
- **zoom / limits:** 1.2
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** no

## input

- **devices:** keyboard
- **actions:** move, fire, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** neon shapes on dark ground
- **palette / silhouette notes:** magenta vs cyan
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** pulse loop
- **SFX set:** shot, hit, wave-clear
- **bus layout:** Master / Music / SFX
- **license source:** original

## save

- **needed:** no
- **slots / autosave:** none
- **location:** none
- **contents:** none

## acceptance

- player can move and fire in different directions
- one wave of three enemies can be cleared
- tests encode hit detection before bulk VFX
