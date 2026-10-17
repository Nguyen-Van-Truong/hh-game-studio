package Code.Box2D.Dynamics.Contacts
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.Math.*;
   
   public class b2ContactResult
   {
      public var normal:b2Vec2;
      
      public var position:b2Vec2;
      
      public var shape1:b2Shape;
      
      public var shape2:b2Shape;
      
      public var normalImpulse:Number;
      
      public var tangentImpulse:Number;
      
      public var id:b2ContactID;
      
      public function b2ContactResult()
      {
         position = new b2Vec2();
         normal = new b2Vec2();
         id = new b2ContactID();
         super();
      }
   }
}

