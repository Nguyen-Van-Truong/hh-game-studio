package Code.Handler
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import flash.display.MovieClip;
   
   public class BasicOverlays
   {
      private var _overlayLayer:MovieClip;
      
      private var _list:Array;
      
      public function BasicOverlays(param1:MovieClip)
      {
         super();
         _overlayLayer = param1;
         _list = new Array();
      }
      
      public function AddOverlay(param1:b2Body, param2:MovieClip) : void
      {
         var _loc3_:Array = null;
         param2.x = param1.GetPosition().x * 30;
         param2.y = param1.GetPosition().y * 30;
         _overlayLayer.addChild(param2);
         _loc3_ = new Array();
         _loc3_.push(param1);
         _loc3_.push(param2);
         _list.push(_loc3_);
      }
      
      public function Update() : void
      {
         var _loc1_:int = 0;
         if(_list.length <= 0)
         {
            return;
         }
         _loc1_ = int(_list.length - 1);
         while(_loc1_ >= 0)
         {
            if(_list[_loc1_][0].GetUserData().destroyed == true)
            {
               _overlayLayer.removeChild(_list[_loc1_][1]);
               _list.splice(_loc1_,1);
            }
            else
            {
               _list[_loc1_][1].x = _list[_loc1_][0].GetPosition().x * 30;
               _list[_loc1_][1].y = _list[_loc1_][0].GetPosition().y * 30;
            }
            _loc1_--;
         }
      }
   }
}

