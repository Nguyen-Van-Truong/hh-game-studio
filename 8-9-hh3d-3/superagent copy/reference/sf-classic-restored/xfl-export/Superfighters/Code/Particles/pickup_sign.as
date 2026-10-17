package Code.Particles
{
   public class pickup_sign extends particle_base
   {
      internal var a:Number = 1;
      
      internal var time:int = 0;
      
      public function pickup_sign(param1:particle_data)
      {
         var _loc2_:String = null;
         time = 0;
         a = 1;
         super();
         _loc2_ = param1.Effect.substr(7,param1.Effect.length - 7);
         this.gotoAndStop(_loc2_);
         SetUpdateEvent(UpdateParticle);
      }
      
      private function UpdateParticle() : *
      {
         this.y -= 0.5;
         a -= 0.04;
         this.alpha = a;
         ++time;
         if(time >= 24)
         {
            EndParticle();
         }
      }
   }
}

