run_id=HONGIO-DEMO-20260831-ASIA-SAIGON-01
command_id=cmd.hongio-demo.wp7.smoke.1
started_at=2026-08-31T14:35:32+07:00
timezone=Asia/Saigon
product=Hòn Gió interactive WebGL demo
not_a_real_map=true
not_vault_fighters=true

source_hash_sha256=b6c0914811df84f18090ef36f055a9af8035b2bd26db32beae3e07e46b2e3050
lockfile_sha256=c5dc0932db0c22fd938127a7c79da66b4acc3b2e900b207a999a4dd1ddd4cf63
lockfile_git_hash=a87ae30640431a1b3e83b75b63babbcbdd239c6c
hash_scope=hh-3d/demo files except node_modules, dist, evidence

os=Windows 10.0.26200
node=v24.10.0
npm=11.6.1
browser=Google Chrome headless (installed Chrome)
viewports=1280x720, 1024x768, 390x844

repro=
  cd hh-3d/demo
  npm ci
  npm run typecheck
  npm run build
  npm run preview -- --host 127.0.0.1
  open http://127.0.0.1:4173/

screenshots=
  overview-1280x720.png — running production preview, Overview
  overview-1024x768.png — running production preview
  overview-390x844.png — running production preview, narrow
  select-lighthouse.png — running preview with ?select=lighthouse
  fallback.png — running preview with ?fallback=1

results=
  boot: PASS (canvas + header Hòn Gió + Interactive demo)
  loading: PASS (does not stick; fallback useful)
  presets: PASS (four typed buttons, distinct views)
  select/card/close: PASS (object card + Close; Escape implemented)
  quality: PASS (Quality low/high; DPR/shadows/instances change)
  resize: PASS at 1280 and 1024; narrow stacks UI without white screen
  fallback: PASS (landmark names + descriptions + how to continue)
  fps: UNMEASURED (/?debug=1 stayed UNMEASURED under headless virtual time; no hardcoded 60)
  desktop orbit p95: UNMEASURED
  low-tier cheaper: UNMEASURED in milliseconds; structurally fewer instances, no shadows, DPR 1

known_gaps=
  - Headless Chrome reports prefers-reduced-motion, so idle bob is off in these shots
  - Production chunk is >500 kB because three + r3f + drei are bundled
  - Narrow viewport UI covers more of the diorama than desktop
  - D0-WP9 and HH World / real-application plans were not opened
