package Code.Particles
{
   import flash.display.MovieClip;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol584")]
   public class particle_blood extends particle_base
   {
      private var _mc:MovieClip;
      
      private var _velY:Number;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _velX:Number;
      
      private var _a:Number;
      
      public function particle_blood(param1:particle_data)
      {
         super();
         _velX = Math.random() * 1 - 0.5 + param1.ParticleVec.x;
         _velY = Math.random() * 0.8 - 2;
         _posX = 0;
         _posY = 0;
         _a = 1;
         switch(param1.DataArray[0])
         {
            case 0:
               _mc = new blood_particle_big();
               break;
            case 1:
               _mc = new blood_particle_small();
               break;
            default:
               _mc = new blood_particle_small();
         }
         this.addChild(_mc);
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _velY += 0.3 * game_speed;
         _posX += _velX * game_speed;
         _posY += _velY * game_speed;
         _mc.x = _posX;
         _mc.y = _posY;
         _a -= 0.04 * game_speed;
         if(_a < 0.5)
         {
            _mc.alpha = 1 - (0.5 - _a) / 0.3;
         }
         if(_a <= 0.2)
         {
            EndParticle();
         }
      }
   }
}

