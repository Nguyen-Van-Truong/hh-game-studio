package Code.Box2D.Collision
{
   import Code.Box2D.Common.Math.*;
   
   public class ClipVertex
   {
      public var v:b2Vec2;
      
      public var id:b2ContactID;
      
      public function ClipVertex()
      {
         v = new b2Vec2();
         id = new b2ContactID();
         super();
      }
   }
}

