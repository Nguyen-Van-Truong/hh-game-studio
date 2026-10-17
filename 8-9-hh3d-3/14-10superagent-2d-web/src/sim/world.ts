import { EMPTY, SeededRng, frame, has, hash, pressed, type Action, type InputFrame, type PlayerId } from './contract';
import { approach, clamp, overlaps, segmentRect } from './math';
import type { Crate, EventKind, Fighter, Fire, Grenade, Ladder, Pickup, Platform, Projectile, SimEvent } from './types';

export const RULESET = 'neon-relay-v2';
export type Mode = 'bot' | 'local';
export const MAP: readonly Platform[] = [
  {x:0,y:478,w:444,h:62}, {x:516,y:478,w:444,h:62},
  {x:54,y:365,w:254,h:18}, {x:654,y:365,w:252,h:18},
  {x:338,y:286,w:284,h:16,oneWay:true}, {x:392,y:400,w:176,h:12,oneWay:true},
];
export const LADDERS: readonly Ladder[] = [
  {x:470,y:286,w:34,h:114}, {x:168,y:365,w:28,h:113}, {x:766,y:365,w:28,h:113},
];
const GRAVITY = 0.42;
const makeProps = (): Crate[] => [
  {x:210,y:442,w:42,h:36,hp:30,broken:false,drop:'medkit',material:'crate',vx:0,vy:0},
  {x:708,y:329,w:40,h:36,hp:30,broken:false,drop:'ammo',material:'crate',vx:0,vy:0},
  {x:566,y:442,w:42,h:36,hp:30,broken:false,drop:'weapon',material:'crate',vx:0,vy:0},
  {x:826,y:320,w:10,h:45,hp:12,broken:false,drop:'ammo',material:'glass',vx:0,vy:0},
  {x:618,y:444,w:26,h:34,hp:20,broken:false,drop:'ammo',material:'barrel',vx:0,vy:0},
];

/** The sole gameplay state. No browser, renderer, wall clock, audio or unseeded RNG. */
export class BattleWorld {
  readonly platforms = MAP;
  readonly ladders = LADDERS;
  readonly crates = makeProps();
  readonly pickups: Pickup[] = [];
  readonly projectiles: Projectile[] = [];
  readonly grenades: Grenade[] = [];
  readonly fires: Fire[] = [];
  readonly events: SimEvent[] = [];
  readonly p1 = this.makeFighter('p1',154);
  readonly p2 = this.makeFighter('p2',806);
  readonly seed: number;
  readonly mode: Mode;
  private rng: SeededRng;
  private botPrevious: readonly Action[] = [];
  private eventId = 0;
  private slowPhase = 0;
  tick = 0;
  paused = false;
  roundOver = false;
  winner: PlayerId | null = null;
  slowTicks = 0;
  shard = {x:480,y:254,active:true,respawn:0};

  constructor(seed = 1396787762, mode: Mode = 'local') { this.seed=seed>>>0; this.rng=new SeededRng(this.seed); this.mode=mode; }
  private makeFighter(id: PlayerId, x: number): Fighter {
    return {id,name:id==='p1'?'NOVA':'VOLT',color:id==='p1'?0x52e5ff:0xff7398,glow:0xffd166,accent:id==='p1'?0x1b8eff:0xd92c90,spawnX:x,x,y:430,vx:0,vy:0,facing:id==='p1'?1:-1,health:100,ammo:12,grenades:2,grounded:false,climbing:false,hurtTimer:0,attackCooldown:0,shootCooldown:0,invulnerable:0,flash:0,score:0,weapon:'pulse',slowTimer:0,dropTimer:0,crouching:false,rollTimer:0,rollCooldown:0,lastDown:-100,aim:0,coyote:0,jumpBuffer:0};
  }
  reset(): void {
    Object.assign(this.p1,this.makeFighter('p1',154)); Object.assign(this.p2,this.makeFighter('p2',806));
    this.crates.splice(0,this.crates.length,...makeProps());
    this.pickups.length=this.projectiles.length=this.grenades.length=this.fires.length=this.events.length=0;
    this.tick=0; this.paused=false; this.roundOver=false; this.winner=null; this.slowTicks=0; this.slowPhase=0;
    this.shard={x:480,y:254,active:true,respawn:0}; this.rng=new SeededRng(this.seed); this.botPrevious=[]; this.eventId=0;
  }
  setPaused(value: boolean): void { this.paused=value; this.events.length=0; }
  private emit(kind: EventKind,x: number,y: number,color=0xffd166,text=''): void { this.events.push({id:++this.eventId,tick:this.tick,kind,x,y,color,text}); }

  step(p1Input: InputFrame = EMPTY, p2Input: InputFrame = EMPTY): void {
    this.events.length=0;
    if(this.paused || this.roundOver) return;
    this.tick++;
    const botInput=this.mode==='bot'?this.botFrame():p2Input;
    if(this.slowTicks>0) this.slowTicks--;
    this.slowPhase=(this.slowPhase+1)%2;
    this.updateProps();
    this.updateFighter(this.p1,p1Input,this.p2);
    this.updateFighter(this.p2,botInput,this.p1);
    if(this.slowTicks===0 || this.slowPhase===0) { this.updateProjectiles(); this.updateGrenades(); }
    this.updatePickups(); this.updateFire();
    if(this.shard.active) {
      for(const f of [this.p1,this.p2]) if(this.shard.active && f.health>0 && overlaps(f.x,f.y,24,44,this.shard.x,this.shard.y,24,24)) {
        f.score++; f.ammo=Math.min(24,f.ammo+6); f.grenades=Math.min(3,f.grenades+1); f.health=Math.min(100,f.health+12);
        this.shard.active=false; this.shard.respawn=360; this.emit('pickup',f.x,f.y,0x70e1a1,'RELAY +1');
      }
    } else if(--this.shard.respawn<=0) this.shard.active=true;
    if(this.p1.health<=0 || this.p2.health<=0 || this.tick>=10800) {
      this.roundOver=true;
      const a=this.p1.health<=0?0:this.p1.health+this.p1.score*5;
      const b=this.p2.health<=0?0:this.p2.health+this.p2.score*5;
      this.winner=a===b?null:a>b?'p1':'p2';
      this.emit('result',480,215,0xffe08a,this.winner?`${this.winner==='p1'?'NOVA':'VOLT'} WINS`:'DRAW');
    }
  }

  /** Bot requests the same actions as human input; never mutates a body directly. */
  private botFrame(): InputFrame {
    const b=this.p2,t=this.p1,a: Action[]=[];
    const goal=this.shard.active && (b.ammo<4 || b.health<55 || this.tick%900<330)?this.shard:t;
    const dx=goal.x-b.x,dy=goal.y-b.y;
    if(Math.abs(dx)>42) a.push(dx>0?'right':'left');
    if(dy<-35) {
      const ladder=this.ladders.filter(l=>l.y< b.y+22).sort((l,r)=>Math.abs(l.x+l.w/2-b.x)-Math.abs(r.x+r.w/2-b.x))[0];
      if(ladder && Math.abs(ladder.x+ladder.w/2-b.x)<24) a.push('up');
      else if(b.grounded && this.tick%55===0) a.push('jump');
    }
    if(b.grounded && ((b.x>395 && b.x<550 && b.y>425) || this.crates.some(c=>!c.broken && Math.abs(c.x+c.w/2-b.x)<54 && Math.abs(c.y-b.y)<45))) a.push('jump');
    const facingTarget=(t.x-b.x)*b.facing>0;
    if(Math.abs(t.x-b.x)<53 && Math.abs(t.y-b.y)<40) a.push('melee');
    if(Math.abs(t.x-b.x)<520 && Math.abs(t.y-b.y)<28 && facingTarget && this.tick%27===0) a.push('shoot');
    if(Math.abs(t.x-b.x)<230 && facingTarget && this.tick%211===0) a.push('throw');
    if(b.score>0 && b.health<65 && this.tick%90===0) a.push('power');
    if(b.grounded && this.tick%130===0 && Math.abs(t.x-b.x)<200) a.push('roll');
    const result=frame(a,this.botPrevious); this.botPrevious=result.held; return result;
  }

  private updateFighter(f: Fighter,input: InputFrame,target: Fighter): void {
    if(f.health<=0) return;
    for(const key of ['attackCooldown','shootCooldown','invulnerable','hurtTimer','flash','dropTimer','rollTimer','rollCooldown','jumpBuffer'] as const) f[key]=Math.max(0,f[key]-1);
    const direction=Number(has(input,'right'))-Number(has(input,'left'));
    if(direction) f.facing=direction>0?1:-1;
    f.crouching=has(input,'down') && f.grounded;
    f.aim=has(input,'shoot')?(Number(has(input,'down'))-Number(has(input,'up')))*0.65:0;
    if(pressed(input,'weapon')) { f.weapon=f.weapon==='pulse'?'scatter':'pulse'; this.emit('pickup',f.x,f.y,0x8fd7ff,f.weapon.toUpperCase()); }
    const onOneWay=this.platforms.some(p=>p.oneWay && Math.abs(f.y+22-p.y)<2 && f.x>p.x-12 && f.x<p.x+p.w+12);
    const doubleDown=pressed(input,'down') && this.tick-f.lastDown<18;
    if(pressed(input,'down')) f.lastDown=this.tick;
    if(onOneWay && has(input,'down') && (pressed(input,'jump') || doubleDown)) { f.dropTimer=20; f.y+=3; f.vy=2; f.grounded=false; f.coyote=0; }
    else if(pressed(input,'jump') || (pressed(input,'up') && !this.findLadder(f))) f.jumpBuffer=7;
    if(f.grounded) f.coyote=6; else f.coyote=Math.max(0,f.coyote-1);
    if(pressed(input,'roll') && f.rollCooldown===0 && f.grounded) { f.rollTimer=17; f.rollCooldown=55; f.invulnerable=Math.max(f.invulnerable,10); }
    const ladder=this.findLadder(f);
    if(ladder && (has(input,'up') || has(input,'down')) && !has(input,'shoot') && f.dropTimer===0) f.climbing=true;
    if(!ladder || direction || pressed(input,'jump')) f.climbing=false;
    const rate=this.slowTicks>0?0.5:1;
    if(f.climbing && ladder) {
      f.vx=0; f.vy=0; f.x=ladder.x+ladder.w/2; f.y+=(Number(has(input,'down'))-Number(has(input,'up')))*2.5*rate;
      f.grounded=false;
      if(f.y<=ladder.y-22) { f.y=ladder.y-22; f.grounded=true; f.climbing=false; }
      if(f.y>=ladder.y+ladder.h-22) { f.y=ladder.y+ladder.h-22; f.grounded=true; f.climbing=false; }
    } else {
      if(f.jumpBuffer>0 && f.coyote>0) { f.vy=-10.4; f.grounded=false; f.coyote=0; f.jumpBuffer=0; this.emit('jump',f.x,f.y+22,f.color); }
      if(f.rollTimer>0) f.vx=f.facing*6;
      else if(f.hurtTimer===0) f.vx=approach(f.vx,direction*(f.crouching?1.8:4.2),(f.grounded?0.85:0.42)*rate);
      else f.vx*=0.98;
      const oldBottom=f.y+22,oldX=f.x;
      f.x=clamp(f.x+f.vx*rate,18,942);
      for(const c of this.crates) if(!c.broken && overlaps(f.x,f.y,24,42,c.x+c.w/2,c.y+c.h/2,c.w,c.h)) {
        if(oldX+12<=c.x+1) { f.x=c.x-12; c.vx+=f.vx*0.12; }
        else if(oldX-12>=c.x+c.w-1) { f.x=c.x+c.w+12; c.vx+=f.vx*0.12; }
      }
      f.vy=Math.min(12,f.vy+GRAVITY*rate); f.y+=f.vy*rate; f.grounded=false;
      const surfaces=[...this.platforms,...this.crates.filter(c=>!c.broken)].sort((a,b)=>a.y-b.y);
      for(const p of surfaces) if(f.x+12>p.x && f.x-12<p.x+p.w && oldBottom<=p.y+0.01 && f.y+22>=p.y && f.vy>=0 && !('oneWay' in p && p.oneWay && f.dropTimer>0)) {
        if(f.vy>5) this.emit('land',f.x,p.y,f.color);
        f.y=p.y-22; f.vy=0; f.grounded=true; break;
      }
    }
    if(f.y>585) { f.health=Math.max(0,f.health-35); f.x=f.spawnX; f.y=430; f.vx=f.vy=0; f.invulnerable=45; f.climbing=false; this.emit('hit',f.x,f.y,0xff5c77,'-35 PIT'); }
    if((has(input,'melee') || pressed(input,'melee')) && f.attackCooldown===0 && f.rollTimer===0) {
      f.attackCooldown=23; this.emit('melee',f.x+f.facing*24,f.y,f.color);
      if((target.x-f.x)*f.facing>=-5 && Math.abs(target.x-f.x)<58 && Math.abs(target.y-f.y)<40) this.damage(target,f.facing*5,f.grounded?14:18);
      for(const c of this.crates) if(!c.broken && Math.abs(c.x+c.w/2-f.x)<58 && Math.abs(c.y+c.h/2-f.y)<40) this.hitProp(c,15,f.facing*2);
    }
    if(has(input,'shoot') && f.shootCooldown===0 && f.ammo>0 && f.rollTimer===0) this.shoot(f);
    if(pressed(input,'throw') && f.grenades>0) { f.grenades--; this.grenades.push({x:f.x+f.facing*18,y:f.y-14,vx:f.facing*4.6+f.vx*0.25,vy:-6.3,fuse:76,owner:f.id}); this.emit('throw',f.x,f.y,f.color); }
    if(pressed(input,'power') && f.score>0) { f.score--; f.health=Math.min(100,f.health+22); this.slowTicks=180; this.emit('power',f.x,f.y,0x70e1a1,'OVERCHARGE · TIME DILATION'); }
  }
  private findLadder(f: Fighter): Ladder | undefined { return this.ladders.find(l=>Math.abs(f.x-l.x-l.w/2)<23 && f.y>=l.y-24 && f.y<=l.y+l.h-18); }
  private damage(f: Fighter,impulse: number,amount: number): void {
    if(f.invulnerable>0 || f.health<=0) return;
    f.health=Math.max(0,f.health-amount); f.vx=impulse; f.vy=-3.2; f.hurtTimer=12; f.invulnerable=12; f.flash=6; f.climbing=false;
    this.emit('hit',f.x,f.y,f.color,`-${amount}`);
  }
  private shoot(f: Fighter): void {
    f.ammo--; f.shootCooldown=f.weapon==='scatter'?32:15;
    for(const spread of f.weapon==='scatter'?[-0.18,0,0.18]:[0]) {
      const a=f.aim+spread+(this.rng.next()-0.5)*0.035;
      this.projectiles.push({x:f.x+f.facing*20,y:f.y-(f.crouching?0:8),vx:Math.cos(a)*f.facing*12,vy:Math.sin(a)*12,life:f.weapon==='scatter'?24:75,owner:f.id,damage:f.weapon==='scatter'?12:10});
    }
    this.emit('shot',f.x+f.facing*24,f.y-8,f.color);
  }
  private updateProjectiles(): void {
    for(let i=this.projectiles.length-1;i>=0;i--) {
      const b=this.projectiles[i], nx=b.x+b.vx,ny=b.y+b.vy,target=b.owner==='p1'?this.p2:this.p1;
      const collisions: {t:number;type:'fighter'|'prop'|'wall';prop?:Crate}[]=[];
      const ft=segmentRect(b.x,b.y,nx,ny,target.x-12,target.y-(target.crouching?5:22),24,target.crouching?27:44);
      if(ft!==null) collisions.push({t:ft,type:'fighter'});
      for(const c of this.crates) if(!c.broken) { const t=segmentRect(b.x,b.y,nx,ny,c.x,c.y,c.w,c.h); if(t!==null) collisions.push({t,type:'prop',prop:c}); }
      for(const p of this.platforms) { const t=segmentRect(b.x,b.y,nx,ny,p.x,p.y,p.w,p.h); if(t!==null) collisions.push({t,type:'wall'}); }
      const hit=collisions.sort((a,b)=>a.t-b.t)[0];
      if(hit) {
        if(hit.type==='fighter') this.damage(target,Math.sign(b.vx)*3,b.damage);
        else if(hit.prop) this.hitProp(hit.prop,b.damage,Math.sign(b.vx)*1.2);
        else this.emit('break',b.x+b.vx*hit.t,b.y+b.vy*hit.t,0x8fd7ff);
        this.projectiles.splice(i,1); continue;
      }
      b.x=nx; b.y=ny; if(--b.life<=0 || b.x<0 || b.x>960 || b.y>560 || b.y<0) this.projectiles.splice(i,1);
    }
  }
  private updateGrenades(): void {
    for(let i=this.grenades.length-1;i>=0;i--) {
      const g=this.grenades[i],bottom=g.y+5; g.vy+=0.3024; g.x+=g.vx; g.y+=g.vy;
      if(g.x<6 || g.x>954) { g.vx*=-0.6; g.x=clamp(g.x,6,954); }
      for(const p of [...this.platforms,...this.crates.filter(c=>!c.broken)]) if(bottom<=p.y && g.y+5>=p.y && g.x>p.x && g.x<p.x+p.w && g.vy>0) { g.y=p.y-5; g.vy*=-0.45; g.vx*=0.8; break; }
      if(--g.fuse<=0) { this.grenades.splice(i,1); this.explode(g.x,g.y); }
    }
  }
  private explode(x: number,y: number): void {
    this.emit('explode',x,y,0xffb45e);
    for(const f of [this.p1,this.p2]) { const d=Math.hypot(f.x-x,f.y-y); if(d<112) this.damage(f,f.x>x?6:-6,d<58?35:18); }
    for(const c of this.crates) if(!c.broken && Math.hypot(c.x+c.w/2-x,c.y+c.h/2-y)<100) this.hitProp(c,40,c.x>x?5:-5);
  }
  private hitProp(c: Crate,amount: number,impulse: number): void {
    c.hp-=amount; if(c.material!=='glass') c.vx+=impulse;
    if(c.hp>0) return;
    c.broken=true; this.emit('break',c.x+c.w/2,c.y+c.h/2,c.material==='glass'?0x8fd7ff:0xffb15c);
    if(c.material==='barrel') { this.fires.push({x:c.x+c.w/2,y:c.y+c.h,life:420}); this.explode(c.x+c.w/2,c.y+c.h/2); }
    if(c.material==='crate') this.pickups.push({x:c.x+c.w/2,y:c.y+c.h-16,kind:c.drop,life:900});
  }
  private updateProps(): void {
    for(const c of this.crates) if(!c.broken && c.material!=='glass') {
      const oldBottom=c.y+c.h; c.vy=Math.min(12,c.vy+0.42); c.x=clamp(c.x+c.vx,0,960-c.w); c.y+=c.vy; c.vx*=0.9;
      for(const p of this.platforms) if(oldBottom<=p.y+0.01 && c.y+c.h>=p.y && c.x+c.w>p.x && c.x<p.x+p.w && c.vy>=0) { c.y=p.y-c.h; c.vy=0; break; }
      if(c.y>585) c.broken=true;
    }
  }
  private updatePickups(): void {
    for(let i=this.pickups.length-1;i>=0;i--) {
      const p=this.pickups[i]; let collected=false;
      for(const f of [this.p1,this.p2]) if(f.health>0 && overlaps(f.x,f.y,24,44,p.x,p.y,24,24)) {
        if(p.kind==='medkit') f.health=Math.min(100,f.health+28);
        if(p.kind==='ammo') { f.ammo=Math.min(24,f.ammo+8); f.grenades=Math.min(3,f.grenades+1); }
        if(p.kind==='weapon') { f.weapon='scatter'; f.ammo=Math.min(24,f.ammo+6); }
        this.emit('pickup',p.x,p.y,0x70e1a1,p.kind==='medkit'?'+28 MEDKIT':p.kind.toUpperCase()); collected=true; break;
      }
      if(collected || --p.life<=0) this.pickups.splice(i,1);
    }
  }
  private updateFire(): void {
    for(let i=this.fires.length-1;i>=0;i--) {
      const fire=this.fires[i];
      for(const f of [this.p1,this.p2]) if(Math.abs(f.x-fire.x)<36 && Math.abs(f.y+22-fire.y)<32 && this.tick%30===0) this.damage(f,f.x>fire.x?2:-2,5);
      if(--fire.life<=0) this.fires.splice(i,1);
    }
  }
  snapshot() {
    return JSON.parse(JSON.stringify({ruleset:RULESET,seed:this.seed,mode:this.mode,tick:this.tick,paused:this.paused,roundOver:this.roundOver,winner:this.winner,rng:this.rng.state,botPrevious:this.botPrevious,eventId:this.eventId,slowTicks:this.slowTicks,slowPhase:this.slowPhase,p1:this.p1,p2:this.p2,crates:this.crates,projectiles:this.projectiles,grenades:this.grenades,pickups:this.pickups,shard:this.shard,fires:this.fires})) as Record<string,unknown>;
  }
  hash(): string { return hash(this.snapshot()); }
}
