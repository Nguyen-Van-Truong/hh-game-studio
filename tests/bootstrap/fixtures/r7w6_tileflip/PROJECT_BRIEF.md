# PROJECT_BRIEF

One-screen Tile Flip Memory for R7-WP6. Independent of the R8 dogfood
title and the R7-WP1 corpus.

## genre

- **value:** memory tile-flip
- **player fantasy:** flip two tiles, remember the pair, clear a 2x2 board
- **out of scope:** campaign, shop, online, 3D, top-down exploration

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
- **actions:** ui_left, ui_right, ui_up, ui_down, ui_accept
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** high-contrast ColorRect tiles, no bulk sprite sheet
- **palette / silhouette notes:** cyan pair and orange pair
- **placeholder policy:** ColorRects are the product look for this slice
- **AI / generated assets:** none

## audio

- **music:** none in v1
- **SFX set:** optional flip click
- **bus layout:** Master / Music / SFX
- **license source:** original / silent

## save

- **needed:** no
- **slots / autosave:** none
- **location:** none
- **contents:** none

## acceptance

- keyboard cursor plus accept flips a tile
- matching pair increments matches
- two matching pairs set won on the 2x2 board
- Play session uses hh_agent_runtime
