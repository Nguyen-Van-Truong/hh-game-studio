package FlashAd_fla
{
   import flash.display.MovieClip;
   import flash.events.Event;
   
   public dynamic class NewgroundsAPIAsset_Load_Indicator_5 extends MovieClip
   {
      public function NewgroundsAPIAsset_Load_Indicator_5()
      {
         super();
      }
      
      public function onEnterFrame(param1:Event) : void
      {
         if(visible && Boolean(stage))
         {
            rotation += 30;
         }
         else
         {
            removeEventListener(Event.ENTER_FRAME,this.onEnterFrame);
         }
      }
   }
}

