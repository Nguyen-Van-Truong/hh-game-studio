import Phaser from 'phaser';
import './style.css';
import { BattleWorld } from './sim/world';
import { InputManager } from './client/input';
import { AudioBus } from './client/audio';
import { Effects } from './client/effects';
import { registerServiceWorker } from './client/pwa';
import { clamp } from './sim/math';
import type { Fighter } from './sim/types';
const VIEW_W=960, VIEW_H=540, FIXED_DT=1/60;

class MainScene extends Phaser.Scene {
  private readonly audio = new AudioBus();
  private readonly inputs = new InputManager();
  private readonly world = new BattleWorld(0x53414a32, 'local');
  private readonly effects = new Effects();
  private gfx!: Phaser.GameObjects.Graphics;
  private hudLeft!: Phaser.GameObjects.Text;
  private hudRight!: Phaser.GameObjects.Text;
  private nameLeft!: Phaser.GameObjects.Text;
  private nameRight!: Phaser.GameObjects.Text;
  private statusText!: Phaser.GameObjects.Text;
  private statusLine!: HTMLElement;
  private floaterTexts: Phaser.GameObjects.Text[] = [];
  private accumulator = 0;
  private started = false;

  constructor() { super('main'); }

  create(): void {
    this.gfx = this.add.graphics();
    this.hudLeft = this.add.text(30, 18, '', { fontFamily: 'Arial, sans-serif', fontSize: '13px', color: '#dffaff', fontStyle: 'bold' }).setDepth(4);
    this.hudRight = this.add.text(VIEW_W - 30, 18, '', { fontFamily: 'Arial, sans-serif', fontSize: '13px', color: '#ffe7e7', fontStyle: 'bold', align: 'right' }).setOrigin(1, 0).setDepth(4);
    this.add.text(VIEW_W / 2, 26, 'RELAY YARD // LOCAL 2P // ROUND 01', { fontFamily: 'Arial, sans-serif', fontSize: '11px', color: '#8aa1bb', letterSpacing: 2 }).setOrigin(0.5, 0).setDepth(4);
    this.nameLeft = this.add.text(0, 0, 'NOVA', { fontFamily: 'Arial, sans-serif', fontSize: '10px', color: '#9deeff', fontStyle: 'bold', stroke: '#07101f', strokeThickness: 3 }).setOrigin(0.5, 1).setDepth(4);
    this.nameRight = this.add.text(0, 0, 'VOLT', { fontFamily: 'Arial, sans-serif', fontSize: '10px', color: '#ffbad0', fontStyle: 'bold', stroke: '#07101f', strokeThickness: 3 }).setOrigin(0.5, 1).setDepth(4);
    this.statusText = this.add.text(VIEW_W / 2, VIEW_H - 24, 'CLICK TO DEPLOY', { fontFamily: 'Arial, sans-serif', fontSize: '11px', color: '#8aa1bb', letterSpacing: 1 }).setOrigin(0.5).setDepth(4);
    this.statusLine = document.querySelector<HTMLElement>('#status-line') ?? document.body;
    for (let i = 0; i < 8; i += 1) this.floaterTexts.push(this.add.text(0, 0, '', { fontFamily: 'Arial, sans-serif', fontSize: '12px', color: '#ffffff', fontStyle: 'bold', stroke: '#07101f', strokeThickness: 3 }).setOrigin(0.5).setDepth(5).setVisible(false));
    const startButton = document.querySelector<HTMLButtonElement>('#start-button');
    startButton?.addEventListener('click', () => { this.started = true; this.audio.unlock(); this.audio.start(); this.statusLine.textContent = 'LOCAL 2P · P pause · R redeploy · Q/5 weapon'; document.querySelector('#start-gate')?.classList.add('is-hidden'); document.querySelector('#touch-controls')?.setAttribute('aria-hidden', 'false'); });
    window.addEventListener('keydown', (event) => { if (event.code === 'KeyR' && this.world.roundOver) { this.world.reset(); this.effects.clear(); } if (event.code === 'KeyP' && this.started) this.setPaused(!this.world.paused); });
    document.addEventListener('visibilitychange', () => { if (document.hidden && this.started) this.setPaused(true); });
    document.querySelector<HTMLButtonElement>('#mute-toggle')?.addEventListener('click', () => { this.audio.toggleMute(); document.querySelector('#mute-toggle')?.classList.toggle('is-active', this.audio.muted); });
    document.querySelector<HTMLButtonElement>('#motion-toggle')?.addEventListener('click', () => { const reduced = document.documentElement.classList.toggle('reduced-motion'); this.effects.reduced = reduced; localStorage.setItem('superagent-reduced-motion', reduced ? '1' : '0'); document.querySelector('#motion-toggle')?.classList.toggle('is-active', reduced); });
    if (localStorage.getItem('superagent-reduced-motion') === '1') { document.documentElement.classList.add('reduced-motion'); this.effects.reduced = true; document.querySelector('#motion-toggle')?.classList.add('is-active'); }
    this.scale.on('resize', () => this.cameras.main.setViewport(0, 0, VIEW_W, VIEW_H));
    this.render();
  }

  update(_time: number, delta: number): void {
    if (this.started) {
      this.inputs.pollGamepads();
      const frameDelta = Math.min(delta / 1000, 0.25);
      this.accumulator += frameDelta;
      while (this.accumulator >= FIXED_DT) { const p1Input = this.inputs.consume('p1'); const p2Input = this.inputs.consume('p2'); this.world.step(p1Input, p2Input); this.effects.handle(this.world.events, this.audio); this.accumulator -= FIXED_DT; }
    }
    this.effects.update(delta);
    this.render();
  }

  private render(): void {
    const g = this.gfx;
    const shake = this.effects.shake;
    this.cameras.main.setScroll(shake > 0 ? (Math.random() - 0.5) * shake : 0, shake > 0 ? (Math.random() - 0.5) * shake : 0);
    g.clear();
    this.drawBackground(g);
    this.drawHudChrome(g);
    this.drawArena(g);
    this.drawShard(g);
    this.drawCrates(g);
    this.drawPickups(g);
    this.drawFires(g);
    this.drawProjectiles(g);
    this.drawGrenades(g);
    this.drawEffectRings(g);
    this.drawFighter(g, this.world.p1);
    this.drawFighter(g, this.world.p2);
    this.drawParticles(g);
    this.drawFloaters();
    this.updateHud();
  }

  private drawBackground(g: Phaser.GameObjects.Graphics): void {
    // Original cobalt industrial interior: high contrast, readable at a small browser viewport.
    g.fillStyle(0x02030a, 1); g.fillRect(0, 0, VIEW_W, VIEW_H);
    g.fillStyle(0x07114a, 1); g.fillRect(0, 58, VIEW_W, 420);
    for (let y = 72; y < 474; y += 44) {
      for (let x = -18; x < VIEW_W + 18; x += 58) {
        const band = Math.floor((y - 72) / 44); const col = Math.floor((x + 18) / 58);
        const dark = (band + col) % 3 === 0;
        g.fillStyle(dark ? 0x08135a : 0x0b1a70, 0.98); g.fillRect(x, y, 48, 34);
        g.lineStyle(2, dark ? 0x1225a2 : 0x1b31be, 0.95); g.strokeRect(x + 1, y + 1, 46, 32);
        g.lineStyle(1, 0x2c55e7, 0.55); g.lineBetween(x + 6, y + 27, x + 42, y + 27);
        if ((band * 5 + col) % 4 === 0) { g.fillStyle(0x4c6dff, 0.8); g.fillRect(x + 8, y + 8, 6, 3); g.fillStyle(0x26d6ff, 0.7); g.fillRect(x + 18, y + 8, 11, 3); }
      }
    }
    g.fillStyle(0x0c1c68, 1); g.fillRect(0, 58, 22, 420); g.fillRect(938, 58, 22, 420);
    g.lineStyle(5, 0x1834b8, 0.95); g.lineBetween(30, 60, 930, 60); g.lineBetween(30, 60, 30, 478); g.lineBetween(930, 60, 930, 478);
    g.lineStyle(2, 0x5f7dff, 0.75); g.lineBetween(42, 86, 918, 86); g.lineBetween(42, 206, 918, 206);
    g.fillStyle(0x122a91, 0.88); g.fillRect(252, 92, 456, 96); g.lineStyle(2, 0x3058e9, 0.9); g.strokeRect(252, 92, 456, 96);
    for (const x of [270, 304, 656, 690]) { g.fillStyle(0x5fdfff, 0.8); g.fillRect(x, 112, 17, 4); g.fillStyle(0xf4cc65, 0.75); g.fillRect(x, 128, 26, 3); }
    g.fillStyle(0x02030a, 0.48); g.fillRect(0, 452, VIEW_W, 88);
    g.fillStyle(0x0520a5, 0.9); g.fillRect(0, 452, VIEW_W, 26); g.lineStyle(2, 0x2d6cff, 0.75); g.lineBetween(0, 452, VIEW_W, 452);
    g.fillStyle(0x23ddff, 0.16); g.fillCircle(782, 116, 96); g.fillStyle(0x23ddff, 0.13); g.fillCircle(782, 116, 56);
    g.lineStyle(2, 0x315b87, 0.7); g.lineBetween(0, 208, 960, 208); g.lineBetween(0, 212, 960, 212);
    g.lineStyle(1, 0x5ce8ff, 0.32); g.lineBetween(260, 70, 260, 182); g.lineBetween(700, 70, 700, 182);
    for (const x of [286, 316, 646, 676]) { g.fillStyle(0x6de6ff, 0.2); g.fillCircle(x, 208, 9); g.fillStyle(0x6de6ff, 0.95); g.fillRect(x - 2, 206, 4, 4); }
  }

  private drawHudChrome(g: Phaser.GameObjects.Graphics): void {
    const left = this.world.p1;
    const right = this.world.p2;
    g.fillStyle(0x07111f, 0.86); g.fillRoundedRect(16, 12, 270, 42, 8); g.fillRoundedRect(VIEW_W - 286, 12, 270, 42, 8);
    g.lineStyle(1, 0x52e5ff, 0.42); g.strokeRoundedRect(16, 12, 270, 42, 8); g.lineStyle(1, 0xff7398, 0.42); g.strokeRoundedRect(VIEW_W - 286, 12, 270, 42, 8);
    g.fillStyle(0x52e5ff, 0.22); g.fillRect(28, 43, 150, 4); g.fillStyle(0x52e5ff, 0.9); g.fillRect(28, 43, 150 * clamp(left.health / 100, 0, 1), 4);
    g.fillStyle(0xff7398, 0.22); g.fillRect(VIEW_W - 178, 43, 150, 4); g.fillStyle(0xff7398, 0.9); g.fillRect(VIEW_W - 178 + 150 * (1 - clamp(right.health / 100, 0, 1)), 43, 150 * clamp(right.health / 100, 0, 1), 4);
    g.fillStyle(0x70e1a1, 0.18); g.fillCircle(VIEW_W / 2, 42, 9); g.lineStyle(1, 0x70e1a1, 0.52); g.strokeCircle(VIEW_W / 2, 42, 9);
  }

  private drawArena(g: Phaser.GameObjects.Graphics): void {
    for (const platform of this.world.platforms) {
      g.fillStyle(0x91a7b8, 0.98); g.fillRect(platform.x, platform.y, platform.w, platform.h); g.fillStyle(0xdce8e9, 0.96); g.fillRect(platform.x, platform.y, platform.w, 4); g.fillStyle(0x25344c, 1); g.fillRect(platform.x, platform.y + 7, platform.w, platform.h - 7); g.lineStyle(1, 0x547ca1, 0.8); for (let x = platform.x + 14; x < platform.x + platform.w; x += 32) g.lineBetween(x, platform.y + 8, x - 10, platform.y + platform.h - 2);
      g.fillStyle(0x0b21a0, 0.85); g.fillRect(platform.x, platform.y + platform.h - 3, platform.w, 3); g.lineStyle(1, 0xb8d7e0, 0.55); g.strokeRect(platform.x + 1, platform.y + 1, platform.w - 2, platform.h - 2);
      if (platform.oneWay) { g.lineStyle(2, 0xffd166, 0.92); for (let x = platform.x + 8; x < platform.x + platform.w; x += 18) g.lineBetween(x, platform.y + 8, x + 6, platform.y + 2); }
    }
    for (const ladder of this.world.ladders) { g.lineStyle(5, 0xb7d7df, 0.95); g.lineBetween(ladder.x + 7, ladder.y, ladder.x + 7, ladder.y + ladder.h); g.lineBetween(ladder.x + ladder.w - 7, ladder.y, ladder.x + ladder.w - 7, ladder.y + ladder.h); g.lineStyle(2, 0x236aff, 0.92); for (let y = ladder.y + 10; y < ladder.y + ladder.h; y += 14) g.lineBetween(ladder.x + 7, y, ladder.x + ladder.w - 7, y); }
    g.fillStyle(0x263b59, 0.98); g.fillRect(0, 478, 444, 62); g.fillRect(516, 478, 444, 62); g.fillStyle(0xdce8e9, 0.95); g.fillRect(0, 478, 444, 5); g.fillRect(516, 478, 444, 5); g.fillStyle(0x0c2bb4, 0.92); g.fillRect(0, 502, 444, 38); g.fillRect(516, 502, 444, 38); g.lineStyle(2, 0x5fdfff, 0.72); g.lineBetween(0, 478, 444, 478); g.lineBetween(516, 478, VIEW_W, 478);
    g.fillStyle(0x1a0711, 0.98); g.fillRect(444, 480, 72, 60); g.fillStyle(0xff5d3e, 0.16); g.fillRect(444, 480, 72, 60); g.lineStyle(2, 0xff6a3d, 0.86); g.lineBetween(444, 480, 516, 480); g.lineBetween(444, 494, 516, 494); for (let x = 452; x < 516; x += 16) { g.fillStyle(0xff8b3d, 0.7); g.fillTriangle(x, 536, x + 7, 510, x + 14, 536); }
  }

  private drawShard(g: Phaser.GameObjects.Graphics): void {
    if (!this.world.shard.active) return;
    const y = this.world.shard.y + Math.sin(this.world.tick * 0.08) * 4; g.fillStyle(0x70e1a1, 0.16); g.fillCircle(this.world.shard.x, y, 25); g.fillStyle(0x70e1a1, 0.95); g.fillTriangle(this.world.shard.x, y - 16, this.world.shard.x + 11, y, this.world.shard.x, y + 16); g.fillTriangle(this.world.shard.x, y - 16, this.world.shard.x - 11, y, this.world.shard.x, y + 16); g.lineStyle(2, 0xe5fff0, 0.8); g.strokeTriangle(this.world.shard.x, y - 14, this.world.shard.x + 9, y, this.world.shard.x, y + 14);
  }

  private drawCrates(g: Phaser.GameObjects.Graphics): void {
    for (const crate of this.world.crates) if (!crate.broken) {
      if (crate.material === 'glass') { g.fillStyle(0x66d9ff, 0.18); g.fillRect(crate.x, crate.y, crate.w, crate.h); g.lineStyle(2, 0xbfefff, 0.9); g.strokeRect(crate.x + 1, crate.y + 1, crate.w - 2, crate.h - 2); g.lineStyle(1, 0x4fa7ff, 0.78); g.lineBetween(crate.x + 2, crate.y + crate.h - 2, crate.x + crate.w - 2, crate.y + 2); g.lineBetween(crate.x + 3, crate.y + 5, crate.x + crate.w - 3, crate.y + crate.h - 6); }
      else if (crate.material === 'barrel') { g.fillStyle(0x751f2d, 1); g.fillRect(crate.x, crate.y, crate.w, crate.h); g.fillStyle(0xb7352d, 0.45); g.fillRect(crate.x + 3, crate.y + 3, crate.w - 6, crate.h - 6); g.lineStyle(2, 0xff6b43, 0.9); g.strokeRect(crate.x + 1, crate.y + 1, crate.w - 2, crate.h - 2); g.lineStyle(2, 0xffd166, 0.72); g.lineBetween(crate.x + 4, crate.y + 9, crate.x + crate.w - 4, crate.y + 9); g.lineBetween(crate.x + 4, crate.y + crate.h - 9, crate.x + crate.w - 4, crate.y + crate.h - 9); g.fillStyle(0xffe7a0, 0.95); g.fillRect(crate.x + crate.w / 2 - 2, crate.y + 4, 4, 4); }
      else { g.fillStyle(0x7d2d26, 1); g.fillRect(crate.x, crate.y, crate.w, crate.h); g.fillStyle(0xb9472e, 0.78); g.fillRect(crate.x + 3, crate.y + 3, crate.w - 6, crate.h - 6); g.lineStyle(2, 0xffb15c, 0.95); g.strokeRect(crate.x + 1, crate.y + 1, crate.w - 2, crate.h - 2); g.lineStyle(2, 0x321b27, 0.85); g.lineBetween(crate.x + 6, crate.y + 7, crate.x + crate.w - 6, crate.y + crate.h - 7); g.lineBetween(crate.x + crate.w - 6, crate.y + 7, crate.x + 6, crate.y + crate.h - 7); g.fillStyle(0xffe0a5, 0.9); g.fillRect(crate.x + 5, crate.y + 4, 3, 3); g.fillRect(crate.x + crate.w - 8, crate.y + crate.h - 7, 3, 3); }
    }
  }

  private drawPickups(g: Phaser.GameObjects.Graphics): void {
    for (const pickup of this.world.pickups) {
      const color = pickup.kind === 'medkit' ? 0x70e1a1 : pickup.kind === 'ammo' ? 0xffd166 : 0x8fd7ff;
      g.fillStyle(color, 0.16); g.fillCircle(pickup.x, pickup.y, 18); g.fillStyle(color, 0.95); g.fillRoundedRect(pickup.x - 9, pickup.y - 9, 18, 18, 5);
      g.lineStyle(2, 0x081020, 0.72); g.lineBetween(pickup.x - 5, pickup.y, pickup.x + 5, pickup.y); if (pickup.kind === 'medkit') g.lineBetween(pickup.x, pickup.y - 5, pickup.x, pickup.y + 5);
    }
  }

  private drawFires(g: Phaser.GameObjects.Graphics): void {
    for (const fire of this.world.fires) { const pulse = 0.7 + Math.sin(this.world.tick * 0.18 + fire.x) * 0.18; g.fillStyle(0xff3d4f, 0.2); g.fillCircle(fire.x, fire.y - 15, 28); g.fillStyle(0xff4a2b, 0.95); g.fillTriangle(fire.x, fire.y - 42 * pulse, fire.x + 16, fire.y, fire.x - 16, fire.y); g.fillStyle(0xff7b2e, 0.98); g.fillTriangle(fire.x + 2, fire.y - 31 * pulse, fire.x + 11, fire.y, fire.x - 8, fire.y); g.fillStyle(0xffef83, 1); g.fillTriangle(fire.x, fire.y - 22 * pulse, fire.x + 6, fire.y, fire.x - 6, fire.y); g.fillStyle(0xd8e2ff, 0.18); g.fillCircle(fire.x - 8, fire.y - 45, 6); }
  }

  private drawProjectiles(g: Phaser.GameObjects.Graphics): void { for (const bullet of this.world.projectiles) { g.fillStyle(0xfff5c8, 0.18); g.fillCircle(bullet.x, bullet.y, 10); g.fillStyle(0xfff5c8, 1); g.fillCircle(bullet.x, bullet.y, 3); g.lineStyle(2, bullet.damage < 9 ? 0x8fd7ff : 0xffc56d, 0.65); g.lineBetween(bullet.x - bullet.vx * 1.6, bullet.y - bullet.vy * 1.6, bullet.x - bullet.vx * 0.35, bullet.y - bullet.vy * 0.35); } }
  private drawGrenades(g: Phaser.GameObjects.Graphics): void { for (const grenade of this.world.grenades) { g.fillStyle(0xff4d6d, 0.16); g.fillCircle(grenade.x, grenade.y, 15); g.fillStyle(0xff4d6d, 1); g.fillCircle(grenade.x, grenade.y, 6); g.lineStyle(2, 0xffe08a, 0.9); g.lineBetween(grenade.x, grenade.y - 7, grenade.x + 4, grenade.y - 10); } }

  private drawFighter(g: Phaser.GameObjects.Graphics, fighter: Fighter): void {
    // Pixel-cluster fighter: authored from rectangles/lines so the silhouette stays crisp and original.
    const flash = fighter.flash > 0 ? 0xffffff : fighter.color;
    const x = Math.round(fighter.x); const y = Math.round(fighter.y); const facing = fighter.facing; const crouch = fighter.crouching ? 7 : 0;
    const moving = Math.abs(fighter.vx) > 0.2; const run = fighter.grounded && moving ? Math.sin(this.world.tick * 0.42 + (fighter.id === 'p2' ? 1.7 : 0)) * 4 : 0;
    const lean = clamp(fighter.vx * 0.7, -4, 4); const dark = 0x090c18; const ink = 0x05070f;
    g.fillStyle(fighter.glow, 0.22); g.fillEllipse(x, y + 28, 72, 18); g.fillStyle(ink, 0.75); g.fillEllipse(x, y + 27, 40, 9);
    if (fighter.invulnerable > 0) { g.fillStyle(0xffffff, 0.06); g.fillCircle(x, y - 3, 37 + Math.sin(this.world.tick * 0.25) * 2); }
    // Boots and split-leg pose.
    g.lineStyle(7, fighter.accent, 1); g.lineBetween(x - 8, y + 14 + crouch, x - 13 + run, y + 34 + crouch); g.lineBetween(x + 8, y + 14 + crouch, x + 13 - run, y + 34 + crouch);
    g.lineStyle(3, dark, 1); g.lineBetween(x - 14 + run, y + 34 + crouch, x - 21 + run, y + 34 + crouch); g.lineBetween(x + 14 - run, y + 34 + crouch, x + 21 - run, y + 34 + crouch);
    // Backpack silhouette and armored torso.
    g.fillStyle(dark, 1); g.fillRect(x - 18 + lean, y - 9 + crouch, 36, 31 - crouch); g.fillStyle(flash, 1); g.fillRect(x - 13 + lean, y - 7 + crouch, 26, 25 - crouch);
    g.fillStyle(fighter.accent, 1); g.fillRect(x - 15 + lean, y - 4 + crouch, 4, 18 - crouch); g.fillRect(x + 11 + lean, y - 4 + crouch, 4, 18 - crouch); g.fillStyle(fighter.glow, 0.95); g.fillRect(x - 10 + lean, y + 1 + crouch, 20, 3); g.fillStyle(0x07111f, 0.85); g.fillRect(x - 9 + lean, y + 7 + crouch, 18, 3); g.fillRect(x - 6 + lean, y + 13 + crouch, 12, 3);
    // Helmet, visor and antenna read as a distinct MUGEN-like head sprite.
    g.fillStyle(dark, 1); g.fillRect(x - 15 + lean, y - 31 + crouch, 30, 23); g.fillStyle(fighter.accent, 1); g.fillRect(x - 11 + lean, y - 28 + crouch, 22, 17); g.fillStyle(fighter.glow, 0.9); g.fillRect(x - 8 + lean, y - 25 + crouch, 16, 3); g.fillStyle(0x09111f, 1); g.fillRect(facing > 0 ? x + 1 + lean : x - 13 + lean, y - 23 + crouch, 13, 7); g.fillStyle(0xeaffff, 0.95); g.fillRect(facing > 0 ? x + 5 + lean : x - 9 + lean, y - 21 + crouch, 6, 2); g.lineStyle(2, fighter.glow, 0.95); g.lineBetween(x - 8 + lean, y - 30 + crouch, x - 3 + lean, y - 36 + crouch); g.fillStyle(fighter.glow, 0.95); g.fillRect(x - 4 + lean, y - 38 + crouch, 4, 3);
    // Arms, weapon, recoil and attack pose.
    const armReach = fighter.attackCooldown > 14 ? 34 : fighter.weapon === 'scatter' ? 31 : 28;
    g.lineStyle(7, flash, 1); g.lineBetween(x + facing * 8 + lean, y - 1 + crouch, x + facing * armReach + lean, y - 8 + crouch); g.lineStyle(3, fighter.glow, 1); g.lineBetween(x + facing * (armReach - 2) + lean, y - 8 + crouch, x + facing * (armReach + 10) + lean, y - 9 + crouch);
    g.fillStyle(dark, 1); g.fillRect(x + facing * (armReach + 6) + lean - (facing > 0 ? 0 : 9), y - 13 + crouch, 12, 7); g.fillStyle(fighter.glow, 1); g.fillRect(x + facing * (armReach + 14) + lean - (facing > 0 ? 0 : 4), y - 11 + crouch, 5, 3);
    if (fighter.weapon === 'scatter') { g.lineStyle(3, 0x8fd7ff, 1); g.lineBetween(x + facing * (armReach + 4) + lean, y - 16 + crouch, x + facing * (armReach + 18) + lean, y - 16 + crouch); }
    if (fighter.shootCooldown > (fighter.weapon === 'scatter' ? 26 : 11)) { g.fillStyle(0xfff5c8, 0.35); g.fillCircle(x + facing * (armReach + 20), y - 9 + crouch, 10); g.fillStyle(0xfff5c8, 1); g.fillTriangle(x + facing * (armReach + 14), y - 14 + crouch, x + facing * (armReach + 32), y - 9 + crouch, x + facing * (armReach + 14), y - 4 + crouch); }
    if (fighter.rollTimer > 0) { g.lineStyle(3, 0xffd166, 0.95); g.strokeCircle(x, y + 1, 34); g.lineStyle(1, 0xfff5c8, 0.8); g.strokeCircle(x, y + 1, 26); }
    if (fighter.invulnerable > 0) { g.lineStyle(2, 0xffffff, 0.75); g.strokeCircle(x, y - 3, 39 + Math.sin(this.world.tick * 0.25) * 2); }
  }

  private drawEffectRings(g: Phaser.GameObjects.Graphics): void {
    for (const ring of this.effects.rings) {
      const progress = 1 - clamp(ring.life / ring.maxLife, 0, 1);
      const alpha = clamp(ring.life / ring.maxLife, 0, 1) * 0.78;
      g.lineStyle(ring.width, ring.color, alpha);
      g.strokeCircle(ring.x, ring.y, 4 + ring.radius * progress);
    }
  }

  private drawParticles(g: Phaser.GameObjects.Graphics): void { for (const p of this.effects.particles) { const alpha = clamp(p.life / p.maxLife, 0, 1); g.fillStyle(p.color, alpha * 0.9); g.fillCircle(p.x, p.y, p.size * (0.65 + alpha * 0.35)); } }
  private drawFloaters(): void {
    for (let i = 0; i < this.floaterTexts.length; i += 1) {
      const label = this.floaterTexts[i];
      const floater = this.effects.floaters[i];
      if (!floater) { label.setVisible(false); continue; }
      label.setVisible(true).setPosition(floater.x, floater.y).setText(floater.text).setColor(floater.color).setAlpha(clamp(floater.life / 22, 0, 1));
    }
  }

  private updateHud(): void {
    const left = this.world.p1; const right = this.world.p2; this.hudLeft.setText(`${left.name}   ${Math.ceil(left.health).toString().padStart(3, '0')} HP   ${left.weapon.toUpperCase()}   A${left.ammo.toString().padStart(2, '0')}  R${left.score}`); this.hudRight.setText(`R${right.score}  A${right.ammo.toString().padStart(2, '0')}   ${right.weapon.toUpperCase()}   ${Math.ceil(right.health).toString().padStart(3, '0')} HP   ${right.name}`);
    this.statusText.setText(this.world.roundOver ? `ROUND OVER — PRESS R TO REDEPLOY` : this.world.paused ? 'PAUSED — PRESS P TO RESUME' : `TICK ${this.world.tick.toString().padStart(5, '0')}  ·  HASH ${this.world.hash().slice(0, 8)}  ·  SHARD ${this.world.shard.active ? 'LIVE' : 'RESPAWNING'}`);
    this.nameLeft.setPosition(left.x, left.y - 31); this.nameRight.setPosition(right.x, right.y - 31); this.nameLeft.setColor(left.health < 35 ? '#ff7a89' : '#9deeff'); this.nameRight.setColor(right.health < 35 ? '#ff7a89' : '#ffbad0');
    this.statusLine.textContent = this.world.roundOver ? 'Round over · press R to redeploy' : this.world.paused ? 'Paused · press P to resume' : this.started ? 'LOCAL 2P · P to pause · R to redeploy' : 'Awaiting deployment';
    this.hudLeft.setColor(left.health < 35 ? '#ff7a89' : '#dffaff'); this.hudRight.setColor(right.health < 35 ? '#ff7a89' : '#ffe7e7');
  }

  private setPaused(value: boolean): void { this.world.setPaused(value); }
}

declare global {
  interface Window { webkitAudioContext?: typeof AudioContext; }
}

new Phaser.Game({
  type: Phaser.AUTO,
  width: VIEW_W,
  height: VIEW_H,
  parent: 'game-root',
  backgroundColor: '#080d22',
  render: { antialias: true, pixelArt: false, roundPixels: true },
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH, width: VIEW_W, height: VIEW_H },
  scene: [MainScene],
});

registerServiceWorker();
