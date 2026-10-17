package Code.Particles
{
   import flash.display.MovieClip;
   
   public class muzzle_weapon_smoke extends particle_base
   {
      private var _s:Number;
      
      private var _mc:MovieClip;
      
      private var _velY:Number;
      
      private var _posX:Number;
      
      private var _changeX:Number;
      
      private var _changeY:Number;
      
      private var _posY:Number;
      
      private var _velX:Number;
      
      private var _a:Number;
      
      public function muzzle_weapon_smoke(param1:particle_data)
      {
         super();
         _changeX = Math.cos(param1.Rotation * (Math.PI / 180)) * 0.05;
         _changeY = Math.sin(param1.Rotation * (Math.PI / 180)) * 0.07;
         _velX = 0.4 + Math.random() * 0.3;
         _velY = Math.random() * 0.6 - 0.3;
         _posX = 0;
         _posY = 0;
         _a = 0.7;
         _s = 1;
         _mc = new smoke_weapon_muzzle();
         _mc.alpha = 0.6;
         this.addChild(_mc);
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _velY -= _changeX * game_speed;
         _velX -= _changeY * game_speed;
         _posX += _velX * game_speed;
         _posY += _velY * game_speed;
         _mc.x = _posX;
         _mc.y = _posY;
         _a -= 0.05 * game_speed;
         _s += 0.04 * game_speed;
         _mc.alpha = _a;
         _mc.scaleX = _s;
         _mc.scaleY = _s;
         if(_a <= 0.1)
         {
            EndParticle();
         }
      }
   }
}

