# Review rubric — Kho Bí Ẩn (R8-WP6 / G5)

Human only. Leave every sign-off blank until a person plays.
This file is not a G5 tick. Windowed Godot and agent soaks are
plan §7.3, not this rubric.

Relic-reached is win. Door-open is not win. Key pickup is not win.

| Area | Accept when | Fail / send back | Sign |
|------|-------------|------------------|------|
| gameplay | 4-dir move, interact, key, door, relic-reached win, warden lose, Restart new run, Continue restores an unfinished v1 slot | Softlock, wrong win flag, cannot finish start→key→door→relic→win without the editor | |
| visual | Sprites/tiles read at 1280x720; not a color-rect-only release; no PLACEHOLDER ship art | Solid-color stand-ins only, cutoff HUD, unreadable key/door/relic | |
| audio | Master / Music / SFX; pickup, door, caught, win, lose, interact make sound | Silent key / door / caught on the critical path | |
| UX | Title, Pause, Resume, Win, Lose, Restart without a mouse; one-line hint; keyboard+gamepad | Must use the mouse on the critical path; focus trap; unreadable text | |
| stability | About 10 minutes continuous play; no blocker, no save loss | Crash, blocker, wiped slot, cannot Restart | |
| autonomy | Person only watches / reviews. No owner clicks to author the game | Reviewer had to edit scenes, scripts, or assets to make the loop work | |
| evidence | Recreate hashes, pin 4.7.1-stable, critic notes, review build, known issues | Missing hashes, invented API key, claimed G5 without play | |

If a row fails, return to the WP that owns it. Do not open R9
because unit/E2E boxes are green.

- gameplay loop → R8-WP2
- art / animation / audio / license pin → R8-WP3
- HUD / pause / buses / polish → R8-WP4
- soak / save / stuck / seeded bash → R8-WP5
- fresh recreate / hashes / review export package → R8-WP6
