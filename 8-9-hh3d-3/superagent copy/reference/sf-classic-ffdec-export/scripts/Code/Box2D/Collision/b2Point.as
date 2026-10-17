package Code.Box2D.Collision
{
   import Code.Box2D.Common.Math.*;
   
   public class b2Point
   {
      public var p:b2Vec2;
      
      public function b2Point()
      {
         p = new b2Vec2();
         super();
      }
      
      public function GetFirstVertex(param1:b2XForm) : b2Vec2
      {
         return p;
      }
      
      public function Support(param1:b2XForm, param2:Number, param3:Number) : b2Vec2
      {
         return p;
      }
   }
}

