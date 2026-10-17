package Code.Handler
{
   import Code.Data.SlowmoData;
   import fl.motion.*;
   import flash.display.MovieClip;
   import flash.events.*;
   
   public class Slowmo
   {
      private var _currSlowmoFactor:Number;
      
      private var _heartbeatTimer:int;
      
      private var _slomo_rectangle:MovieClip;
      
      private var _Handler_Effects:Effects;
      
      private var _stage:*;
      
      private var _gamePaused:Boolean = false;
      
      private var _slowmotionArray:Array;
      
      private var _curve:Number = 0;
      
      private var _Handler_Output:OutputTrace;
      
      private var _Handler_Sounds:Sounds;
      
      private var _brightness:Number = 0;
      
      public function Slowmo(param1:OutputTrace, param2:Effects, param3:Sounds, param4:MovieClip, param5:*)
      {
         _brightness = 0;
         _curve = 0;
         _gamePaused = false;
         super();
         _Handler_Output = param1;
         _Handler_Effects = param2;
         _Handler_Sounds = param3;
         _slomo_rectangle = param4;
         _stage = param5;
         _heartbeatTimer = 0;
         _stage.addEventListener(Event.RESIZE,OnStageResize);
         DrawRectangle(_stage.stageWidth,_stage.stageHeight);
         _slowmotionArray = new Array();
         _currSlowmoFactor = 1;
      }
      
      public function set GamePaused(param1:Boolean) : void
      {
         _gamePaused = param1;
         if(param1)
         {
            _Handler_Effects.SetSlowmotion(0);
         }
         else
         {
            _Handler_Effects.SetSlowmotion(_currSlowmoFactor);
         }
      }
      
      private function OnStageResize(param1:Event) : void
      {
         DrawRectangle(_stage.stageWidth,_stage.stageHeight);
      }
      
      public function AddSlowmotion(param1:SlowmoData, param2:Boolean = false, param3:int = -1) : void
      {
         _slowmotionArray.push([param1,param2,param3]);
         if(param2)
         {
            _brightness = 1;
         }
      }
      
      public function get Slowmotion() : Number
      {
         if(_gamePaused)
         {
            return 0;
         }
         return _currSlowmoFactor;
      }
      
      public function Stop() : void
      {
         _stage.removeEventListener(Event.RESIZE,OnStageResize);
      }
      
      public function Update() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:int = 0;
         var _loc3_:Boolean = false;
         var _loc4_:int = 0;
         if(_gamePaused)
         {
            return;
         }
         _loc1_ = Number(_currSlowmoFactor);
         _loc2_ = _slowmotionArray.length - 1;
         while(_loc2_ >= 0)
         {
            _slowmotionArray[_loc2_][0].ProgressTime();
            if(Boolean(_slowmotionArray[_loc2_][0].Completed))
            {
               _slowmotionArray.splice(_loc2_,1);
            }
            _loc2_--;
         }
         _loc3_ = false;
         _currSlowmoFactor = 1;
         _loc4_ = 0;
         while(_loc4_ < _slowmotionArray.length)
         {
            if(_slowmotionArray[_loc4_][0].CurrentSlowmotion < _currSlowmoFactor)
            {
               _currSlowmoFactor = _slowmotionArray[_loc4_][0].CurrentSlowmotion;
            }
            if(_slowmotionArray[_loc4_][1] == true)
            {
               _loc3_ = true;
            }
            _loc4_++;
         }
         if(_loc3_)
         {
            _heartbeatTimer -= 1;
            if(_heartbeatTimer <= 0)
            {
               _heartbeatTimer = 28;
               _Handler_Sounds.PlaySound("HEARTBEAT",0,0);
            }
            if(_brightness > 0.18)
            {
               _brightness -= 0.08;
               if(_brightness < 0.18)
               {
                  _brightness = 0.18;
                  _curve = Math.PI / 2;
               }
            }
            else
            {
               _curve += 0.13;
               if(_curve > Math.PI)
               {
                  _curve = 0;
               }
               _brightness = 0.12 + Math.sin(_curve) * 0.06;
            }
            SetAlpha(_slomo_rectangle,_brightness);
         }
         else if(_brightness != 0)
         {
            if(_brightness > 0)
            {
               _brightness -= 0.02;
               if(_brightness < 0)
               {
                  _brightness = 0;
               }
            }
            else if(_brightness < 0)
            {
               _brightness += 0.02;
               if(_brightness > 0)
               {
                  _brightness = 0;
               }
            }
            SetAlpha(_slomo_rectangle,_brightness);
         }
         if(_loc1_ != _currSlowmoFactor)
         {
            _Handler_Output.Trace("Slowmotion: " + Math.round(_currSlowmoFactor * 100) / 100);
            _Handler_Effects.SetSlowmotion(_currSlowmoFactor);
         }
      }
      
      private function DrawRectangle(param1:Number, param2:Number) : void
      {
         _slomo_rectangle.graphics.clear();
         _slomo_rectangle.graphics.moveTo(0,0);
         _slomo_rectangle.graphics.beginFill(16777215);
         _slomo_rectangle.graphics.lineTo(param1 + 1,0);
         _slomo_rectangle.graphics.lineTo(param1 + 1,param2 + 1);
         _slomo_rectangle.graphics.lineTo(0,param2 + 1);
         _slomo_rectangle.graphics.lineTo(0,0);
         _slomo_rectangle.graphics.endFill();
         SetAlpha(_slomo_rectangle,_brightness);
         _slomo_rectangle.x = -(param1 - 800) * 0.5;
         _slomo_rectangle.y = -(param2 - 600) * 0.5;
      }
      
      private function SetBrightness(param1:MovieClip, param2:Number) : void
      {
         var _loc3_:Color = null;
         _loc3_ = new Color();
         _loc3_.brightness = param2;
         param1.transform.colorTransform = _loc3_;
      }
      
      public function RemoveSlowmotion(param1:int) : void
      {
         var _loc2_:int = 0;
         _loc2_ = _slowmotionArray.length - 1;
         while(_loc2_ >= 0)
         {
            if(_slowmotionArray[_loc2_][2] == param1)
            {
               _slowmotionArray.splice(_loc2_,1);
            }
            _loc2_--;
         }
      }
      
      private function SetAlpha(param1:MovieClip, param2:Number) : void
      {
         param1.alpha = param2;
      }
   }
}

