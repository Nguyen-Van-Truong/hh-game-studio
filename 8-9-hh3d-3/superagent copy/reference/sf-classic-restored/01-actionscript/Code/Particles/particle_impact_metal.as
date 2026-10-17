package Code.Particles
{
   [Embed(source="/_assets/assets.swf", symbol="symbol200")]
   public class particle_impact_metal extends particle_base
   {
      private var Scale:Number = 0;
      
      private var speedX:Number = 0;
      
      private var speedY:Number = 0;
      
      public function particle_impact_metal(param1:particle_data)
      {
         var _loc2_:Number = NaN;
         Scale = 0;
         speedY = 0;
         speedX = 0;
         super();
         speedX = param1.ParticleVec.x;
         speedY = param1.ParticleVec.y;
         _loc2_ = Math.sqrt(speedX * speedX + speedY * speedY);
         if(_loc2_ > 1)
         {
            speedX *= 1 / _loc2_;
            speedY *= 1 / _loc2_;
         }
         Scale = 0.7;
         this.scaleX = Scale;
         this.scaleY = Scale;
         this.alpha = 0.7;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         this.y += speedY * game_speed;
         this.x += speedX * game_speed;
         this.alpha -= 0.1 * game_speed;
         if(this.alpha <= 0)
         {
            EndParticle();
         }
      }
   }
}

