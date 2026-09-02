run_id=HONGIO-DEMO-20260831-ASIA-SAIGON-02
command_id=cmd.hongio-demo.visible-first-paint.1
started_at=2026-08-31T15:04:00+07:00
timezone=Asia/Saigon
product=Hòn Gió interactive WebGL demo
not_a_real_map=true
not_vault_fighters=true

working_url=http://127.0.0.1:4173/
stale_url=http://127.0.0.1:4174/ (down; leftover when 4173 was busy)

repro=
  cd hh-3d/demo
  npm run typecheck
  npm run build
  npm run preview -- --host 127.0.0.1 --port 4173
  open http://127.0.0.1:4173/

commands=
  npm run typecheck → exit 0
  npm run build → exit 0
  npm run preview -- --host 127.0.0.1 --port 4173 → running
  node evidence/capture-running-app.mjs → exit 0

screenshots_on_disk=
  evidence/overview-1280x720.png (103039 bytes) — island + header + hints + camera nav
  evidence/overview-1024x768.png (100167 bytes)
  evidence/overview-390x844.png (62059 bytes)
  evidence/select-lighthouse.png (115329 bytes) — object card Hải đăng sọc
  evidence/fallback.png (51888 bytes) — /?fallback=1 static view

probe=
  title=Hòn Gió — Interactive demo
  header=Hòn Gió / Interactive demo
  hints=Kéo/xoay để xem. Cuộn để zoom. Bấm landmark. Bấm Overview.
  canvas=1280x720 css, 1920x1080 buffer
  buttons=Hải đăng sọc, Bến gỗ, Thúng neo, Nhà mái ngói, Overview, Harbor, Lighthouse, Island, Quality: high, Show static view

fps=UNMEASURED
not_plan_tick=true
