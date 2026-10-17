package Code.Particles
{
   import flash.display.MovieClip;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol482")]
   public class fire_effect_flamethrower extends particle_base
   {
      private var _mc:MovieClip;
      
      private var _velY:Number;
      
      private var _percentage:Number;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _velX:Number;
      
      private var _a:Number;
      
      public function fire_effect_flamethrower(param1:particle_data)
      {
         super();
         this.scaleX = 1;
         this.scaleY = 1;
         _mc = new fire_01_flamethrower();
         this.addChild(_mc);
         _a = 1;
         _posX = param1.PosX;
         _posY = param1.PosY;
         _velX = param1.ParticleVec.x;
         _velX *= 0.16;
         _velY = param1.ParticleVec.y - 0.4;
         _velY *= 0.16;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _posY += game_speed * _velY;
         _posX += game_speed * _velX;
         _a -= game_speed * 0.07;
         _velY -= game_speed * 0.2;
         this.y = _posY;
         this.x = _posX;
         this.alpha = _a;
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

