package Superfighters_fla
{
   import Code.Main;
   import com.newgrounds.components.APIConnector;
   import com.newgrounds.components.MedalPopup;
   import flash.display.MovieClip;
   import flash.display.SimpleButton;
   import flash.events.Event;
   import flash.events.MouseEvent;
   import flash.events.ProgressEvent;
   import flash.net.URLRequest;
   import flash.net.navigateToURL;
   import flash.text.TextField;
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public dynamic class MainTimeline extends MovieClip
   {
      public var __id0_:APIConnector;
      
      public var medal_popup:MedalPopup;
      
      public var canStart:Boolean;
      
      public var myTextField:TextField;
      
      public var playBtn:SimpleButton;
      
      public var minWaitTimer:Number;
      
      public var loadTxt:TextField;
      
      public var mythologic_link:SimpleButton;
      
      public var _game:Main;
      
      public var loadingDone:Boolean;
      
      public function MainTimeline()
      {
         super();
         __setProp___id0__Main_NGAPI_1();
      }
      
      public function LoadingProgress(param1:ProgressEvent) : void
      {
         myTextField.text = Math.round(param1.bytesLoaded / param1.bytesTotal * 100) + " %";
      }
      
      internal function __setProp___id0__Main_NGAPI_1() : *
      {
         try
         {
            __id0_["componentInspectorSetting"] = true;
         }
         catch(e:Error)
         {
         }
         __id0_.movieId = "19514:ooXYUlX0";
         __id0_.debugMode = false;
         __id0_.encryptionKey = "Jp0oTAzeMyODj8FfcbtczVgSyokCAs6W";
         __id0_.movieVersion = "";
         __id0_.showConnectingPopup = false;
         __id0_.useErrorPopup = true;
         __id0_.useMedalPopup = true;
         __id0_.useFakeSession = true;
         try
         {
            __id0_["componentInspectorSetting"] = false;
         }
         catch(e:Error)
         {
         }
      }
      
      public function LoadingDone(param1:Event) : void
      {
         loadingDone = true;
         if(canStart)
         {
            gotoAndStop(3);
         }
         else
         {
            myTextField.text = "LOADING";
         }
      }
      
      public function playBtnClick(param1:MouseEvent) : void
      {
         playBtn.removeEventListener(MouseEvent.CLICK,playBtnClick);
         gotoAndStop(6);
      }
      
      public function linkEvent(param1:MouseEvent) : void
      {
         var targetURL:URLRequest = null;
         var e:MouseEvent = param1;
         try
         {
            targetURL = new URLRequest("http://mythologicinteractive.com");
            navigateToURL(targetURL,"_blank");
         }
         catch(e:Error)
         {
         }
      }
      
      public function WaitTimeOver() : void
      {
         clearInterval(minWaitTimer);
         canStart = true;
         if(loadingDone)
         {
            gotoAndStop(3);
         }
      }
   }
}

