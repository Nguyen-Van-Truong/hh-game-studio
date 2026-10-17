package Code.Particles
{
   import flash.display.MovieClip;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol156")]
   public class smoke_trace_effect extends particle_base
   {
      private var _speedX:Number;
      
      private var _speedY:Number;
      
      private var _s:Number;
      
      private var _mc:MovieClip;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _a:Number;
      
      public function smoke_trace_effect(param1:particle_data)
      {
         super();
         if(param1.DataArray[0] == 2)
         {
            _mc = new smoke_trace_01();
         }
         else if(param1.DataArray[0] == 1)
         {
            _mc = new smoke_trace_light_01();
         }
         else
         {
            _mc = new error_mc();
         }
         _a = 0.6;
         _mc.alpha = _a;
         _posX = 0;
         _posY = 0;
         _speedX = param1.ParticleVec.x * 0.1;
         _speedY = param1.ParticleVec.y * 0.1;
         _s = 0.8;
         this.addChild(_mc);
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _posX += _speedX * game_speed;
         _posY += (_speedY - 0.5) * game_speed;
         _a -= game_speed * 0.05;
         _s += game_speed * 0.02;
         if(_a <= 0.1)
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

