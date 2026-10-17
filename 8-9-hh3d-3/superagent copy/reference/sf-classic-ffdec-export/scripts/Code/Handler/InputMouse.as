package Code.Handler
{
   import flash.events.*;
   import flash.geom.Point;
   
   public class InputMouse
   {
      private var _mouseDown:Boolean = false;
      
      private var _mouseX:Number = 0;
      
      private var _mouseY:Number = 0;
      
      private var _stage:*;
      
      public function InputMouse(param1:*)
      {
         _mouseDown = false;
         _mouseX = 0;
         _mouseY = 0;
         super();
         _stage = param1;
         _stage.addEventListener(MouseEvent.MOUSE_DOWN,mouseDownHandler);
         _stage.addEventListener(MouseEvent.MOUSE_UP,mouseUpHandler);
      }
      
      public function MouseX() : Number
      {
         return _mouseX;
      }
      
      private function mouseDownHandler(param1:MouseEvent) : void
      {
         _mouseDown = true;
      }
      
      private function mouseUpHandler(param1:MouseEvent) : void
      {
         _mouseDown = false;
      }
      
      public function MouseIsDown() : Boolean
      {
         return _mouseDown;
      }
      
      public function MouseY() : Number
      {
         return _mouseY;
      }
      
      public function UpdateMouse(param1:Point, param2:Number) : void
      {
         var _loc3_:Number = NaN;
         _loc3_ = 1 / param2;
         _mouseX = _loc3_ * (_stage.mouseX - param1.x);
         _mouseY = _loc3_ * (_stage.mouseY - param1.y);
      }
   }
}

