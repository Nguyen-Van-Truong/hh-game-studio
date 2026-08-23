# PROJECT_BRIEF

## genre

- **value:** side-scroll platformer
- **player fantasy:** jump across two rooms to a flag
- **out of scope:** wall jump, water levels

## camera

- **mode:** side-scroll
- **zoom / limits:** 1.5
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** yes

## input

- **devices:** keyboard
- **actions:** move, jump, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** chunky 16px tiles
- **palette / silhouette notes:** night blues
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** short chiptune loop
- **SFX set:** jump, land, flag
- **bus layout:** Master / Music / SFX
- **license source:** CC0

## save

- **needed:** no
- **slots / autosave:** none
- **location:** none
- **contents:** none

## acceptance

- player can jump onto a platform without falling through
- flag contact ends the slice
- tests encode the jump before bulk tileset painting
