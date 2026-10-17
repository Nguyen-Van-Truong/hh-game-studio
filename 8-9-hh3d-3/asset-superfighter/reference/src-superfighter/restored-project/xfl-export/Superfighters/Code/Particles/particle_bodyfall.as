package Code.Particles
{
   public class particle_bodyfall extends particle_base
   {
      private var Scale:Number = 0;
      
      private var speedX:Number = 0;
      
      private var speedY:Number = 0;
      
      public function particle_bodyfall(param1:particle_data)
      {
         Scale = 0;
         speedY = 0;
         speedX = 0;
         super();
         speedX = Math.random() * 0.4 - 0.2;
         speedY = Math.random() * 0.6 - 0.4;
         Scale = 1;
         this.scaleX = Scale;
         this.scaleY = Scale;
         this.alpha = 0.5;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         speedY += 0.002 * game_speed;
         this.y += speedY * game_speed;
         this.x += speedX * game_speed;
         this.alpha -= 0.04 * game_speed;
         Scale += 0.04 * game_speed;
         this.scaleX = Scale;
         this.scaleY = Scale;
         if(this.alpha <= 0.1)
         {
            EndParticle();
         }
      }
   }
}

