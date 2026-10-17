package Code.Particles
{
   public class fire_effect_ground extends particle_base
   {
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _velX:Number;
      
      private var _a:Number;
      
      public function fire_effect_ground(param1:particle_data)
      {
         super();
         this.gotoAndStop(Math.round(Math.random() * (this.totalFrames - 1)) + 1);
         this.scaleX = 1.25;
         this.scaleY = 1.25;
         _a = 1;
         _posX = param1.PosX;
         _posY = param1.PosY - 2;
         _velX = Math.random() - 0.5;
         _velX *= 1.2;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _posX += game_speed * _velX;
         _a -= game_speed * 0.04;
         _posY -= game_speed * 0.01;
         this.x = _posX;
         this.y = _posY;
         this.alpha = _a;
         if(_a <= 0.4)
         {
            EndParticle();
         }
      }
   }
}

