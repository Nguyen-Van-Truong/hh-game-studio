package Code.Particles
{
   [Embed(source="/_assets/assets.swf", symbol="symbol744")]
   public class blood_gib_trace extends particle_base
   {
      private var _s:Number;
      
      private var _a:Number;
      
      public function blood_gib_trace(param1:particle_data)
      {
         super();
         _a = 1;
         _s = 1;
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         _a -= game_speed * 0.07;
         _s += game_speed * 0.04;
         this.alpha = _a;
         this.scaleX = _s;
         this.scaleY = _s;
         if(_a <= 0.4)
         {
            EndParticle();
         }
      }
   }
}

