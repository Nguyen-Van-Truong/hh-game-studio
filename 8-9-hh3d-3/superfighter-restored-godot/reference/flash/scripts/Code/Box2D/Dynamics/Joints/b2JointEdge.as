package Code.Box2D.Dynamics.Joints
{
   import Code.Box2D.Dynamics.b2Body;
   
   public class b2JointEdge
   {
      public var joint:b2Joint;
      
      public var other:b2Body;
      
      public var next:b2JointEdge;
      
      public var prev:b2JointEdge;
      
      public function b2JointEdge()
      {
         super();
      }
   }
}

