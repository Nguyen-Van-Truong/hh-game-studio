import type { Floater, Particle, SimEvent } from '../sim/types';
import type { AudioBus } from './audio';

export interface EffectRing {
  x: number;
  y: number;
  life: number;
  readonly maxLife: number;
  readonly radius: number;
  readonly color: number;
  readonly width: number;
}

export class Effects {
  particles: Particle[]=[];
  floaters: Floater[]=[];
  rings: EffectRing[]=[];
  shake=0;
  reduced=false;
  clear(): void {this.particles.length=this.floaters.length=this.rings.length=0;this.shake=0;}
  handle(events: readonly SimEvent[],audio: AudioBus): void {
    for(const e of events) {
      if(e.kind==='shot')audio.shoot();
      if(e.kind==='hit' || e.kind==='break')audio.hit();
      if(e.kind==='melee')audio.melee();
      if(e.kind==='throw')audio.grenade();
      if(e.kind==='land')audio.land();
      if(e.kind==='pickup')audio.pickup();
      if(e.kind==='power')audio.power();
      if(e.kind==='explode')audio.explode();
      if(e.kind==='jump')audio.jump();
      if(e.kind==='result')audio.result();
      if(e.text) {if(this.floaters.length>=8)this.floaters.shift();this.floaters.push({x:e.x,y:e.y-32,life:70,text:e.text,color:e.kind==='hit'?'#ff8e9f':'#c5ffe4'});}
      const ringLife = this.reduced ? 8 : e.kind==='explode' ? 24 : e.kind==='hit' ? 14 : e.kind==='melee' ? 10 : 12;
      const ringRadius = e.kind==='explode' ? 76 : e.kind==='hit' ? 28 : e.kind==='melee' ? 34 : 20;
      if(this.rings.length>=32)this.rings.shift();
      this.rings.push({x:e.x,y:e.y,life:ringLife,maxLife:ringLife,radius:ringRadius,color:e.color,width:e.kind==='explode'?4:2});
      const count=this.reduced?3:e.kind==='explode'?40:e.kind==='shot'?8:12;
      for(let i=0;i<count;i++) {
        if(this.particles.length>=180)this.particles.shift();
        const angle=Math.random()*Math.PI*2, speed=Math.random()*(e.kind==='explode'?7:3.5),life=12+Math.random()*26;
        this.particles.push({x:e.x,y:e.y,vx:Math.cos(angle)*speed,vy:Math.sin(angle)*speed,life,maxLife:life,size:e.kind==='explode'?3+Math.random()*5:1+Math.random()*3,color:i%4===0?0xffffff:e.color,gravity:0.08});
      }
      if(!this.reduced && (e.kind==='hit' || e.kind==='explode')) this.shake=Math.max(this.shake,e.kind==='explode'?8:3);
    }
  }
  update(delta: number): void {
    const dt=Math.min(3,delta/16.6667);
    this.shake=Math.max(0,this.shake-dt*0.4);
    for(let i=this.particles.length-1;i>=0;i--){const p=this.particles[i];p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=p.gravity*dt;p.life-=dt;if(p.life<=0)this.particles.splice(i,1);}
    for(let i=this.floaters.length-1;i>=0;i--){const f=this.floaters[i];f.y-=0.35*dt;f.life-=dt;if(f.life<=0)this.floaters.splice(i,1);}
    for(let i=this.rings.length-1;i>=0;i--){const ring=this.rings[i];ring.life-=dt;if(ring.life<=0)this.rings.splice(i,1);}
  }
}
