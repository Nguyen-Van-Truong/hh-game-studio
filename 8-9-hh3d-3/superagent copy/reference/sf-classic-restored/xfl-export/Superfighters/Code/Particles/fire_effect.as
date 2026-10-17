package Code.Particles
{
   import flash.display.MovieClip;
   
   public class fire_effect extends particle_base
   {
      private var _mc:MovieClip;
      
      private var _percentage:Number;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _velX:Number;
      
      private var _a:Number;
      
      public function fire_effect(param1:particle_data)
      {
         var _loc2_:Number = NaN;
         super();
         this.scaleX = 1.25;
         this.scaleY = 1.25;
         _loc2_ = Math.round(Math.random() * 2) + 1;
         switch(_loc2_)
         {
            case 1:
               _mc = new fire_01();
               break;
            case 2:
               _mc = new fire_02();
               break;
            case 3:
               _mc = new fire_03();
         }
         this.addChild(_mc);
         _a = 1;
         _posX = param1.PosX;
         _posY = param1.PosY;
         _velX = Math.random() - 0.5;
         _velX *= 0.7;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _posY -= game_speed * 1.2;
         _posX += game_speed * _velX;
         _a -= game_speed * 0.04;
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

