package Superfighters_fla
{
   import Code.*;
   import com.newgrounds.components.APIConnector;
   import flash.accessibility.*;
   import flash.display.*;
   import flash.errors.*;
   import flash.events.*;
   import flash.filters.*;
   import flash.geom.*;
   import flash.media.*;
   import flash.net.*;
   import flash.system.*;
   import flash.text.*;
   import flash.ui.*;
   import flash.utils.*;
   
   public dynamic class MainTimeline extends MovieClip
   {
      public var __id0_:APIConnector;
      
      public var myTextField:TextField;
      
      public var playBtn:SimpleButton;
      
      public var __setPropDict:Dictionary;
      
      public var loadTxt:TextField;
      
      public var mythologic_link:SimpleButton;
      
      public var _game:Main;
      
      public function MainTimeline()
      {
         __setPropDict = new Dictionary(true);
         super();
         addFrameScript(0,frame1,1,frame2,2,frame3,3,frame4,5,frame6);
      }
      
      internal function frame3() : *
      {
         if(__setPropDict[__id0_] == undefined || !(int(__setPropDict[__id0_]) >= 1 && int(__setPropDict[__id0_]) <= 4))
         {
            __setPropDict[__id0_] = currentFrame;
            __setProp___id0__Loader_LoaderVisuals_1();
         }
         gotoAndStop(1);
      }
      
      public function LoadingProgress(param1:ProgressEvent) : void
      {
         myTextField.text = Math.round(param1.bytesLoaded / param1.bytesTotal * 100) + " %";
      }
      
      internal function frame1() : *
      {
         if(__setPropDict[__id0_] == undefined || !(int(__setPropDict[__id0_]) >= 1 && int(__setPropDict[__id0_]) <= 4))
         {
            __setPropDict[__id0_] = currentFrame;
            __setProp___id0__Loader_LoaderVisuals_1();
         }
         stop();
         myTextField = loadTxt;
         this.loaderInfo.addEventListener(Event.COMPLETE,LoadingDone);
         this.loaderInfo.addEventListener(ProgressEvent.PROGRESS,LoadingProgress);
         mythologic_link.addEventListener(MouseEvent.CLICK,linkEvent);
      }
      
      internal function frame6() : *
      {
         _game = new Main(stage,this);
         stop();
      }
      
      internal function frame4() : *
      {
         if(__setPropDict[__id0_] == undefined || !(int(__setPropDict[__id0_]) >= 1 && int(__setPropDict[__id0_]) <= 4))
         {
            __setPropDict[__id0_] = currentFrame;
            __setProp___id0__Loader_LoaderVisuals_1();
         }
         playBtn.addEventListener(MouseEvent.CLICK,playBtnClick);
      }
      
      internal function frame2() : *
      {
         if(__setPropDict[__id0_] == undefined || !(int(__setPropDict[__id0_]) >= 1 && int(__setPropDict[__id0_]) <= 4))
         {
            __setPropDict[__id0_] = currentFrame;
            __setProp___id0__Loader_LoaderVisuals_1();
         }
         gotoAndStop(1);
      }
      
      public function LoadingDone(param1:Event) : void
      {
         gotoAndStop(4);
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
      
      public function playBtnClick(param1:MouseEvent) : void
      {
         gotoAndStop("Game","Game");
      }
      
      internal function __setProp___id0__Loader_LoaderVisuals_1() : *
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
   }
}

