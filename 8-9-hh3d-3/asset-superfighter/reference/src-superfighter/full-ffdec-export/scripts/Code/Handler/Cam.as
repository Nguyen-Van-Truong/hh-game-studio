package Code.Handler
{
   import flash.display.MovieClip;
   import flash.geom.*;
   
   public class Cam
   {
      public static const sizeIncrease:Number = 40;
      
      private var _gui_holder_mc:MovieClip;
      
      private var _posTarget:Point;
      
      private var _stage:*;
      
      private var _speedX:Number = 0;
      
      private var _speedY:Number = 0;
      
      private var _screenHeight:Number;
      
      private var _showAll:Boolean = false;
      
      private var _posSpeed:Point;
      
      private var _dynamic_mc:MovieClip;
      
      private var _menu_mc:MovieClip;
      
      private var _scaleTarget:Number = 1;
      
      private var _fullScreenMode:Boolean = false;
      
      private var _Handler_Players:PlayersKeeper;
      
      private var _fullScreenDivider:Number = 0;
      
      private var _scaleSpeed:Number = 0;
      
      private var __cam_override_done:Boolean = true;
      
      private var _mapArea:Rectangle;
      
      private var _zoomStepsLeft:Number = 0;
      
      private var _camArea:Rectangle;
      
      private var _extraScreenToVanish:Number = 0;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _Handler_Output:OutputTrace;
      
      private var _screenWidth:Number;
      
      public function Cam(param1:*, param2:MovieClip, param3:MovieClip, param4:MovieClip, param5:OutputTrace, param6:PlayersKeeper)
      {
         _speedX = 0;
         _speedY = 0;
         _scaleTarget = 1;
         _posTarget = new Point(0,0);
         _scaleSpeed = 0;
         _posSpeed = new Point(0,0);
         _zoomStepsLeft = 0;
         _camArea = new Rectangle();
         _showAll = false;
         _extraScreenToVanish = 0;
         _fullScreenMode = false;
         _fullScreenDivider = 0;
         __cam_override_done = true;
         super();
         _stage = param1;
         _dynamic_mc = param2;
         _gui_holder_mc = param3;
         _menu_mc = param4;
         _Handler_Output = param5;
         _Handler_Players = param6;
      }
      
      public function set ShowAll(param1:Boolean) : void
      {
         _showAll = param1;
      }
      
      public function RecalculateCamArea(param1:int = 8, param2:Boolean = false) : void
      {
         var _loc3_:Rectangle = null;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         if(!param2)
         {
            if(!__cam_override_done)
            {
               return;
            }
         }
         else
         {
            __cam_override_done = false;
         }
         if(!_showAll)
         {
            _loc3_ = _Handler_Players.GetCamArea();
         }
         else
         {
            _loc3_ = new Rectangle(_mapArea.x,_mapArea.y,_mapArea.width,_mapArea.height);
         }
         _loc4_ = sizeIncrease * 4;
         _loc5_ = sizeIncrease * 3;
         _loc3_.x -= _loc4_ / 2;
         _loc3_.y -= _loc5_ / 2;
         _loc3_.width += _loc4_;
         _loc3_.height += _loc5_;
         if(_loc3_.width > _mapArea.width)
         {
            _loc3_.width = _mapArea.width;
         }
         if(_loc3_.height > _mapArea.height)
         {
            _loc3_.height = _mapArea.height;
         }
         if(_loc3_.x < _mapArea.x)
         {
            _loc3_.x = _mapArea.x;
         }
         if(_loc3_.x + _loc3_.width > _mapArea.x + _mapArea.width)
         {
            _loc3_.x = _mapArea.x + _mapArea.width - _loc3_.width;
         }
         if(_loc3_.y < _mapArea.y)
         {
            _loc3_.y = _mapArea.y;
         }
         if(_loc3_.y + _loc3_.height > _mapArea.y + _mapArea.height)
         {
            _loc3_.y = _mapArea.y + _mapArea.height - _loc3_.height;
         }
         _loc6_ = 1 / (_loc3_.height / 600);
         if(_fullScreenMode)
         {
            _loc7_ = _extraScreenToVanish * (1 / _loc6_);
            _loc4_ = _loc7_ / 3 * 4;
            _loc5_ = _loc7_;
            _loc3_.x += _loc4_ / 4;
            _loc3_.y += _loc5_ / 4;
            _loc3_.width -= _loc4_;
            _loc3_.height -= _loc5_;
            _loc6_ = 1 / (_loc3_.height / _fullScreenDivider);
         }
         _scaleTarget = _loc6_;
         _posTarget.x = -_loc3_.x * _loc6_;
         _posTarget.y = -_loc3_.y * _loc6_;
         _camArea = _loc3_;
         _zoomStepsLeft = param1;
         _posSpeed.x = (_posTarget.x - _dynamic_mc.x) / _zoomStepsLeft;
         _posSpeed.y = (_posTarget.y - _dynamic_mc.y) / _zoomStepsLeft;
         _scaleSpeed = (_scaleTarget - _dynamic_mc.scaleX) / _zoomStepsLeft;
      }
      
      public function SetScreenResulotion(param1:Number = 800, param2:Number = 600) : void
      {
         _screenWidth = param1;
         _screenHeight = param2;
         if(param2 < 768)
         {
            _fullScreenMode = false;
         }
         else
         {
            _fullScreenMode = true;
            switch(param2)
            {
               case 768:
                  _fullScreenDivider = 500;
                  break;
               case 1050:
                  _fullScreenDivider = 250;
                  break;
               default:
                  _fullScreenDivider = 250 + (1050 - param2) * (1 / 1.128);
            }
         }
         _extraScreenToVanish = param2 - 600;
         _gui_holder_mc.scaleX = param1 / 800;
         _gui_holder_mc.scaleY = param2 / 600;
         _gui_holder_mc.x = -(param1 - 800) / 2;
         _gui_holder_mc.y = -(param2 - 600) / 2;
         _menu_mc.scaleX = param1 / 800;
         _menu_mc.scaleY = param2 / 600;
         _menu_mc.x = -(param1 - 800) / 2;
         _menu_mc.y = -(param2 - 600) / 2;
         _Handler_Output.Trace("Your resulotion: " + param1 + "x" + param2);
         RecalculateCamArea(1);
      }
      
      public function Initialize() : void
      {
         SetScreenResulotion(_stage.stageWidth,_stage.stageHeight);
      }
      
      public function get ShowAll() : Boolean
      {
         return _showAll;
      }
      
      public function IsInside(param1:Point) : Boolean
      {
         return true;
      }
      
      public function SetMapArea(param1:Rectangle) : void
      {
         _mapArea = param1;
         _Handler_Players.SetMapArea(param1);
         RecalculateCamArea();
      }
      
      public function get MapArea() : Rectangle
      {
         return _mapArea;
      }
      
      public function Update(param1:Number) : void
      {
         if(_zoomStepsLeft > 0)
         {
            _dynamic_mc.x += _posSpeed.x * param1;
            _dynamic_mc.y += _posSpeed.y * param1;
            _dynamic_mc.scaleX += _scaleSpeed * param1;
            _dynamic_mc.scaleY += _scaleSpeed * param1;
            _zoomStepsLeft -= 1 * param1;
            if(_zoomStepsLeft <= 0)
            {
               __cam_override_done = true;
            }
         }
      }
   }
}

