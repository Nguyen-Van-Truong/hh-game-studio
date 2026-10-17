package Code.Particles
{
   [Embed(source="/_assets/assets.swf", symbol="symbol163")]
   public class particle_impact_wood extends particle_base
   {
      private var Scale:Number = 0;
      
      private var speedX:Number = 0;
      
      private var speedY:Number = 0;
      
      public function particle_impact_wood(param1:particle_data)
      {
         Scale = 0;
         speedY = 0;
         speedX = 0;
         super();
         speedX = param1.ParticleVec.x * 0.1;
         if(Math.sqrt(speedX * speedX) > 1)
         {
            speedX /= Math.sqrt(speedX * speedX);
         }
         speedY = -0.1;
         Scale = 0.7;
         this.scaleX = Scale;
         this.scaleY = Scale;
         this.alpha = 0.5;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         speedY += 0.025 * game_speed;
         this.y += speedY * game_speed;
         this.x += speedX * game_speed;
         this.alpha -= 0.03 * game_speed;
         this.scaleX += 0.03 * game_speed;
         this.scaleY += 0.03 * game_speed;
         if(this.alpha <= 0)
         {
            EndParticle();
         }
      }
   }
}

