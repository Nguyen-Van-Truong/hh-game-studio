import { frame, type Action, type InputFrame, type PlayerId } from '../sim/contract';

export const KEYMAP: Record<string,[PlayerId,Action]> = {
  KeyA:['p1','left'],KeyD:['p1','right'],KeyW:['p1','up'],KeyS:['p1','down'],Space:['p1','jump'],KeyJ:['p1','melee'],KeyK:['p1','shoot'],KeyL:['p1','throw'],Semicolon:['p1','power'],Slash:['p1','power'],KeyQ:['p1','weapon'],ShiftLeft:['p1','roll'],
  ArrowLeft:['p2','left'],ArrowRight:['p2','right'],ArrowUp:['p2','up'],ArrowDown:['p2','down'],Numpad0:['p2','jump'],Numpad1:['p2','melee'],Numpad2:['p2','shoot'],Numpad3:['p2','throw'],Numpad4:['p2','power'],Numpad5:['p2','weapon'],ShiftRight:['p2','roll'],
  Digit1:['p2','melee'],Digit2:['p2','shoot'],Digit3:['p2','throw'],Digit4:['p2','power'],Digit5:['p2','weapon'],
};
/** Source ownership prevents one released pointer/key from cancelling another. */
export class InputSources {
  private sources=new Map<string,[PlayerId,Action]>();
  private previous: Record<PlayerId,readonly Action[]>={p1:[],p2:[]};
  private taps: Record<PlayerId,Set<Action>>={p1:new Set(),p2:new Set()};
  set(source: string,player: PlayerId,action: Action): void { if(!this.actions(player).includes(action)) this.taps[player].add(action); this.sources.set(source,[player,action]); }
  release(source: string): void { this.sources.delete(source); }
  clear(): void { this.sources.clear(); this.previous={p1:[],p2:[]}; this.taps.p1.clear(); this.taps.p2.clear(); }
  private actions(player: PlayerId): Action[] { return [...new Set([...this.sources.values()].filter(x=>x[0]===player).map(x=>x[1]))]; }
  consume(player: PlayerId): InputFrame {
    const held=this.actions(player), f=frame(held,this.previous[player]);
    const result=Object.freeze({...f,pressed:Object.freeze([...new Set([...f.pressed,...this.taps[player]])])});
    this.previous[player]=f.held; this.taps[player].clear(); return result;
  }
}
export class InputManager extends InputSources {
  constructor() {
    super();
    window.addEventListener('keydown',e=>{
      if(e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      const mapped=KEYMAP[e.code]; if(mapped) {e.preventDefault();this.set(`key:${e.code}`,...mapped);}
    });
    window.addEventListener('keyup',e=>this.release(`key:${e.code}`));
    window.addEventListener('blur',()=>this.clear());
    document.querySelectorAll<HTMLButtonElement>('[data-action]').forEach(button=>{
      const action=button.dataset.action as Action;
      button.addEventListener('pointerdown',e=>{e.preventDefault();button.setPointerCapture(e.pointerId);this.set(`touch:${e.pointerId}`,'p1',action);button.classList.add('is-held');});
      const release=(e:PointerEvent):void=>{this.release(`touch:${e.pointerId}`);button.classList.remove('is-held');};
      button.addEventListener('pointerup',release);button.addEventListener('pointercancel',release);button.addEventListener('lostpointercapture',release);
    });
  }
  override clear(): void { super.clear(); document.querySelectorAll('.is-held').forEach(e=>e.classList.remove('is-held')); }
  pollGamepads(): void {
    const pads=navigator.getGamepads?.()??[];
    const controls: [number,Action][]=[[0,'jump'],[1,'melee'],[2,'shoot'],[3,'throw'],[4,'roll'],[5,'power'],[12,'up'],[13,'down'],[14,'left'],[15,'right']];
    for(let i=0;i<2;i++) {
      const pad=pads[i], player:PlayerId=i===0?'p1':'p2';
      for(const [button,action] of controls) {const id=`pad:${i}:${button}`;if(pad?.buttons[button]?.pressed)this.set(id,player,action);else this.release(id);}
      for(const [id,value,action] of [['x-',(pad?.axes[0]??0)<-0.3,'left'],['x+',(pad?.axes[0]??0)>0.3,'right']] as const) {const source=`pad:${i}:${id}`;if(value)this.set(source,player,action);else this.release(source);}
    }
  }
}
