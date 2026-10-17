package Code.Particles
{
   import flash.display.MovieClip;
   
   public class fire_effect_bazooka_rocket extends particle_base
   {
      private var _s:Number;
      
      private var _mc:MovieClip;
      
      private var _velY:Number;
      
      private var _percentage:Number;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _velX:Number;
      
      private var _a:Number;
      
      public function fire_effect_bazooka_rocket(param1:particle_data)
      {
         super();
         _mc = new trace_bazooka_rocket();
         this.addChild(_mc);
         _a = 1;
         _s = 1;
         this.scaleX = _s;
         this.scaleY = _s;
         _posX = param1.PosX;
         _posY = param1.PosY;
         _velX = param1.ParticleVec.x + Math.random() * 2 - 1;
         _velX *= 0.4;
         _velY = param1.ParticleVec.y - Math.random();
         _velY *= 0.4;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _posY += game_speed * _velY;
         _posX += game_speed * _velX;
         _a -= game_speed * 0.04;
         _velY -= game_speed * 0.15;
         _s += game_speed * 0.03;
         this.y = _posY;
         this.x = _posX;
         this.alpha = _a;
         this.scaleX = _s;
         this.scaleY = _s;
         if(_a <= 0.4)
         {
            EndParticle();
         }
         else
         {
            _percentage = 1 - (_a - 0.4) / 0.6;
            _mc.gotoAndStop(Math.ceil(_mc.totalFrames * _percentage));
         }
      }
   }
}

