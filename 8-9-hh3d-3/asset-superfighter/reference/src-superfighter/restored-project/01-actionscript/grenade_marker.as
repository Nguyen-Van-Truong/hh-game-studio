package
{
   import flash.display.MovieClip;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol499")]
   public dynamic class grenade_marker extends MovieClip
   {
      public function grenade_marker()
      {
         super();
         addFrameScript(4,frame5);
      }
      
      internal function frame5() : *
      {
         stop();
      }
   }
}

