package FlashAd_fla
{
   import com.newgrounds.API;
   import flash.display.MovieClip;
   import flash.display.SimpleButton;
   import flash.events.MouseEvent;
   
   public dynamic class NewgroundsAPIAsset_FlashAd_Container_2 extends MovieClip
   {
      public var adMask:MovieClip;
      
      public var ngLinkButton:SimpleButton;
      
      public function NewgroundsAPIAsset_FlashAd_Container_2()
      {
         super();
      }
      
      public function onNGLinkClicked(param1:MouseEvent) : void
      {
         API.loadNewgrounds();
      }
   }
}

