package Code.Particles
{
   import flash.display.MovieClip;
   import flash.events.Event;
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public class particle_base extends MovieClip
   {
      private var updateFunc:Function;
      
      private var _updateTimer:Number;
      
      private var _game_speed:Number = 1;
      
      private var _curr_frame:Number = 1;
      
      public function particle_base()
      {
         _game_speed = 1;
         _curr_frame = 1;
         super();
      }
      
      public function EndParticle() : void
      {
         if(isNaN(_updateTimer))
         {
            this.removeEventListener(Event.ENTER_FRAME,Update);
         }
         else
         {
            clearInterval(_updateTimer);
         }
         if(this.parent != null)
         {
            this.parent.removeChild(this);
         }
      }
      
      public function set game_speed(param1:Number) : void
      {
         _game_speed = param1;
      }
      
      public function set CurrentFrame(param1:int) : void
      {
         _curr_frame = param1;
      }
      
      public function ProgressAnimationFor(param1:MovieClip) : void
      {
         _curr_frame += _game_speed;
         param1.gotoAndStop(CurrentFrame);
      }
      
      public function get CurrentFrame() : int
      {
         return Math.round(_curr_frame + 0.001);
      }
      
      public function SetUpdateEvent(param1:Function) : void
      {
         updateFunc = param1;
         this.addEventListener(Event.ENTER_FRAME,Update,false,0,true);
      }
      
      public function get game_speed() : Number
      {
         return _game_speed;
      }
      
      public function ProgressAnimation() : void
      {
         _curr_frame += _game_speed;
         this.gotoAndStop(CurrentFrame);
      }
      
      private function Update(param1:Event) : void
      {
         updateFunc();
         this.removeEventListener(Event.ENTER_FRAME,Update);
         _updateTimer = setInterval(updateFunc,1000 / 24);
      }
   }
}

