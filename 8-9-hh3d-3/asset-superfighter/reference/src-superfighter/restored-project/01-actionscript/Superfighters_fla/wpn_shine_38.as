package Superfighters_fla
{
   import flash.display.MovieClip;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol218")]
   public dynamic class wpn_shine_38 extends MovieClip
   {
      public function wpn_shine_38()
      {
         super();
         addFrameScript(0,frame1,20,frame21);
      }
      
      internal function frame1() : *
      {
         gotoAndPlay(5 + Math.floor(Math.random() * 12));
      }
      
      internal function frame21() : *
      {
         gotoAndPlay(2);
      }
   }
}

