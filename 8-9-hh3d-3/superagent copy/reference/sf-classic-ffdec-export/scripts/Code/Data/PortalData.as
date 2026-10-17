package Code.Data
{
   import Code.Box2D.Common.Math.*;
   import flash.geom.Point;
   import flash.geom.Rectangle;
   
   public class PortalData
   {
      private var _inverseY:Boolean = false;
      
      private var _portal:Rectangle;
      
      private var _targetPortal:Rectangle;
      
      private var _triggerVelocity:Point;
      
      private var _inverseX:Boolean = false;
      
      public function PortalData(param1:Rectangle, param2:Rectangle, param3:Point, param4:Boolean, param5:Boolean)
      {
         _inverseX = false;
         _inverseY = false;
         super();
         _portal = param1;
         _targetPortal = param2;
         _triggerVelocity = param3;
         _inverseX = param4;
         _inverseY = param5;
      }
      
      public function GetTargetPositionFromCurrent(param1:Number, param2:Number) : b2Vec2
      {
         return new b2Vec2((_targetPortal.x + _targetPortal.width / 2) / 30,(_targetPortal.y + param2 - _portal.y) / 30);
      }
      
      public function get InverseY() : Boolean
      {
         return _inverseY;
      }
      
      public function get TriggerVelocity() : Point
      {
         return _triggerVelocity;
      }
      
      public function get InverseX() : Boolean
      {
         return _inverseX;
      }
      
      public function PointInsidePortal(param1:Number, param2:Number) : Boolean
      {
         if(param1 > _portal.x && param1 < _portal.x + _portal.width)
         {
            if(param2 > _portal.y && param2 < _portal.y + _portal.height)
            {
               return true;
            }
         }
         return false;
      }
   }
}

