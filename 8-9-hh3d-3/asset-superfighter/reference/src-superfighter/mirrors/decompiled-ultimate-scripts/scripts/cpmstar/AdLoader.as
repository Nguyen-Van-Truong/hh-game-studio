package cpmstar
{
   import flash.display.DisplayObject;
   import flash.display.Loader;
   import flash.display.MovieClip;
   import flash.display.Sprite;
   import flash.events.KeyboardEvent;
   import flash.net.URLRequest;
   import flash.system.ApplicationDomain;
   import flash.system.LoaderContext;
   import flash.system.Security;
   import flash.text.TextField;
   import flash.text.TextFormat;
   import flash.utils.clearInterval;
   import flash.utils.getTimer;
   import flash.utils.setInterval;
   
   public class AdLoader extends MovieClip
   {
      public static var maxTime:int = 300000;
      
      public static var lastTime:int = 0;
      
      public static var running:Boolean = false;
      
      private var ad:DisplayObject;
      
      public function AdLoader(param1:int, param2:int, param3:Boolean, param4:Boolean = false)
      {
         var t:int;
         var self:MovieClip;
         var poolid:int = param1;
         var subpoolid:int = param2;
         var onlyOverlays:Boolean = param3;
         var addChildAds:Boolean = param4;
         super();
         if(running)
         {
            return;
         }
         stop();
         if(lastTime != 0)
         {
            t = getTimer() - lastTime;
            if(t <= maxTime)
            {
               trace("CPM AD# TIMEOUT");
               return;
            }
            lastTime = getTimer();
            trace("CPM AD# SHOW");
         }
         else
         {
            lastTime = getTimer();
         }
         running = true;
         addEventListener(AdEvent.INIT,adEventInit);
         addEventListener(AdEvent.ERROR,adEventError);
         addEventListener(AdEvent.LEAVE_BEHIND,adEventLeaveBehind);
         addEventListener(AdEvent.NO_AD,adEventNoAd);
         addEventListener(AdEvent.OVERLAY_COMPLETE,adEventOverlayComplete);
         addEventListener(AdEvent.OVERLAY_STARTED,adEventOverlayStarted);
         addEventListener(AdEvent.SKIP_ALLOWED,adEventSkipAllowed);
         addEventListener(AdEvent.SKIPPED,adEventSkipped);
         graphics.beginFill(0,0.9);
         graphics.drawRect(0,0,1000,1000);
         graphics.endFill();
         self = this;
         addEventListener("addedToStage",function():void
         {
            var adSkip:int;
            var onKeyUp:Function;
            var skip:Function;
            var skipBtn:Sprite;
            var skipText:TextField;
            var i:int;
            trace("CPM AD# ADDED");
            ad = loadAd(poolid,subpoolid,addChildAds);
            ad.x = stage.stageWidth / 2 - 150;
            ad.y = stage.stageHeight / 2 - 125;
            addChild(ad);
            if(onlyOverlays)
            {
               ad.x = -3000;
               ad.y = -2500;
            }
            else
            {
               adSkip = 10;
               skip = function():void
               {
                  stage.removeEventListener("keyUp",onKeyUp,false);
                  removeAdSwf();
               };
               onKeyUp = function(param1:KeyboardEvent):void
               {
                  if(adSkip > -1)
                  {
                     return;
                  }
                  if(param1.keyCode == 32)
                  {
                     skip();
                  }
               };
               stage.addEventListener("keyUp",onKeyUp,false,1000000,false);
               skipBtn = new Sprite();
               skipBtn.graphics.beginFill(0,0.00001);
               skipBtn.graphics.drawRect(0,0,240,36);
               skipBtn.graphics.endFill();
               skipBtn.useHandCursor = true;
               skipBtn.buttonMode = true;
               skipBtn.visible = false;
               skipBtn.addEventListener("click",function():void
               {
                  skip();
               });
               skipText = new TextField();
               skipText.defaultTextFormat = new TextFormat("Arial",16,16777215,true,null,null,null,null,"center");
               skipText.selectable = false;
               skipText.width = stage.stageWidth;
               skipText.antiAliasType = "normal";
               skipText.text = "A";
               skipText.y = 10;
               skipText.text = ("You can skip this ad in " + adSkip).toUpperCase();
               addChild(skipText);
               skipBtn.x = stage.stageWidth / 2 - skipBtn.width / 2;
               skipBtn.y = 5;
               addChild(skipBtn);
               i = int(setInterval(function():void
               {
                  adSkip--;
                  if(adSkip == -1)
                  {
                     clearInterval(i);
                     skipBtn.visible = true;
                     skipText.text = "Skip Ad (Press \"SPACE\")".toUpperCase();
                     return;
                  }
                  skipText.text = ("You can skip this ad in " + adSkip).toUpperCase();
               },1000));
            }
         });
         addEventListener("removedFromStage",function():void
         {
            trace("CPM AD# REMOVED");
            running = false;
         });
      }
      
      public static function loadAd(param1:int, param2:int, param3:Boolean) : DisplayObject
      {
         Security.allowDomain("server.cpmstar.com");
         Security.allowDomain("cdn.cpmstar.com");
         Security.allowDomain("cdn2.cpmstar.com");
         Security.allowDomain("cdn3.cpmstar.com");
         var _loc7_:String = "http://server.cpmstar.com/adviewas3.swf";
         var _loc5_:Loader = new Loader();
         var _loc4_:ApplicationDomain = ApplicationDomain.currentDomain;
         var _loc6_:LoaderContext = new LoaderContext(false,_loc4_);
         _loc5_.load(new URLRequest(_loc7_ + "?poolid=" + param1 + "&subpoolid=" + param2 + (param3 ? "" : "&blockchildads=1")),_loc6_);
         return _loc5_;
      }
      
      private function removeAdSwf() : void
      {
         removeChild(ad);
         parent.removeChild(this);
      }
      
      private function adEventInit(param1:AdEvent) : void
      {
         trace("CPM# adEventInit");
      }
      
      private function adEventError(param1:AdEvent) : void
      {
         trace("CPM# adEventError");
         removeAdSwf();
      }
      
      private function adEventLeaveBehind(param1:AdEvent) : void
      {
         trace("CPM# adEventLeaveBehind");
         removeAdSwf();
      }
      
      private function adEventNoAd(param1:AdEvent) : void
      {
         trace("CPM# adEventNoAd");
         removeAdSwf();
      }
      
      private function adEventOverlayComplete(param1:AdEvent) : void
      {
         trace("CPM# adEventOverlayComplete");
         removeAdSwf();
      }
      
      private function adEventOverlayStarted(param1:AdEvent) : void
      {
         trace("CPM# adEventOverlayStarted");
      }
      
      private function adEventSkipAllowed(param1:AdEvent) : void
      {
         trace("CPM# adEventSkipAllowed");
      }
      
      private function adEventSkipped(param1:AdEvent) : void
      {
         trace("CPM# adEventSkipped");
         removeAdSwf();
      }
   }
}

