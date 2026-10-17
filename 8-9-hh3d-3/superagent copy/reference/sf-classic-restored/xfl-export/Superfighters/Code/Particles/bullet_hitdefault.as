package Code.Particles
{
   import flash.display.MovieClip;
   
   public class bullet_hitdefault extends particle_base
   {
      private var _speedX:Number;
      
      private var _speedY:Number;
      
      private var _s:Number;
      
      private var _mc:MovieClip;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _a:Number;
      
      public function bullet_hitdefault(param1:particle_data)
      {
         super();
         _mc = new smoke_trace_light_01();
         _a = 0.8;
         _mc.alpha = _a;
         _posX = 0;
         _posY = 0;
         _speedX = Math.random() * 1.2 - 0.6;
         _speedY = Math.random() * 1.2 - 0.6;
         _s = 1;
         this.addChild(_mc);
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _posX += _speedX * game_speed;
         _posY += _speedY * game_speed;
         _a -= game_speed * 0.04;
         _s += game_speed * 0.01;
         if(_a <= 0)
         {
            EndParticle();
         }
         else
         {
            _mc.scaleX = _s;
            _mc.scaleY = _s;
            _mc.alpha = _a;
            _mc.x = _posX;
            _mc.y = _posY;
         }
      }
   }
}

