package Code.Data.Players
{
   import flash.geom.Rectangle;
   
   public class PlayerAreaData
   {
      private var _left:Number;
      
      private var _bottom:Number;
      
      private var _top:Number;
      
      private var _right:Number;
      
      public function PlayerAreaData(param1:Rectangle)
      {
         super();
         _top = param1.y;
         _left = param1.x;
         _bottom = param1.y + param1.height;
         _right = param1.x + param1.width;
      }
      
      public function get Bottom() : Number
      {
         return _bottom;
      }
      
      public function get Left() : Number
      {
         return _left;
      }
      
      public function get Top() : Number
      {
         return _top;
      }
      
      public function get Right() : Number
      {
         return _right;
      }
   }
}

