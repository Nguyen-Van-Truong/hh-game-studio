# PROJECT_BRIEF

## genre

- **value:** dialogue novel
- **player fantasy:** choose two branches and reach an ending
- **out of scope:** combat, inventory

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

- **devices:** keyboard
- **actions:** advance, choose, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** character busts and a text box
- **palette / silhouette notes:** high contrast UI
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** quiet piano
- **SFX set:** advance, choice, end
- **bus layout:** Master / Music / SFX
- **license source:** original

## save

- **needed:** yes
- **slots / autosave:** autosave node id
- **location:** user data
- **contents:** current node and flags

## acceptance

- two choices lead to distinct ending labels
- advance never skips a required choice
- tests define the graph before bulk portraits
