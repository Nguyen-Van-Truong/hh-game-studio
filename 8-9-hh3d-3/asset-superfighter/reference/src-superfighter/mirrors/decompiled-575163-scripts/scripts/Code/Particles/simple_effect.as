package Code.Particles
{
   import flash.display.MovieClip;
   
   public class simple_effect extends particle_base
   {
      private var _mc:MovieClip;
      
      public function simple_effect(param1:MovieClip)
      {
         super();
         _mc = param1;
         this.addChild(_mc);
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         ProgressAnimationFor(_mc);
         if(CurrentFrame >= _mc.totalFrames)
         {
            EndParticle();
         }
      }
   }
}

