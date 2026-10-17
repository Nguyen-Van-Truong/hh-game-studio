package Superfighters_fla
{
   import flash.display.MovieClip;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol2216")]
   public dynamic class billboard_805 extends MovieClip
   {
      public function billboard_805()
      {
         super();
         addFrameScript(0,frame1);
      }
      
      internal function frame1() : *
      {
         this.gotoAndStop(Math.floor(Math.random() * (this.totalFrames - 0.0001)) + 1);
      }
   }
}

