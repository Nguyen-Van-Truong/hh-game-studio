package Code.Box2D.Collision.Shapes
{
   import Code.Box2D.Common.Math.*;
   
   public class b2FilterData
   {
      public var categoryBits:uint = 1;
      
      public var isGhost:Boolean = false;
      
      public var isCloud:Boolean = false;
      
      public var maskBits:uint = 65535;
      
      public var groupIndex:int = 0;
      
      public var isElevator:Boolean = false;
      
      public function b2FilterData()
      {
         categoryBits = 1;
         maskBits = 65535;
         groupIndex = 0;
         isCloud = false;
         isElevator = false;
         isGhost = false;
         super();
      }
      
      public function Copy() : b2FilterData
      {
         var _loc1_:b2FilterData = null;
         _loc1_ = new b2FilterData();
         _loc1_.categoryBits = categoryBits;
         _loc1_.maskBits = maskBits;
         _loc1_.groupIndex = groupIndex;
         _loc1_.isCloud = isCloud;
         _loc1_.isElevator = isElevator;
         _loc1_.isGhost = isGhost;
         return _loc1_;
      }
   }
}

