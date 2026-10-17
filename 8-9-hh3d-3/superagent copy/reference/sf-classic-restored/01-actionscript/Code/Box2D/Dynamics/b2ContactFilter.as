package Code.Box2D.Dynamics
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.Contacts.*;
   
   public class b2ContactFilter
   {
      public static var b2_defaultFilter:b2ContactFilter = new b2ContactFilter();
      
      public function b2ContactFilter()
      {
         super();
      }
      
      public function ShouldCollide(param1:b2Shape, param2:b2Shape) : Boolean
      {
         var _loc3_:b2FilterData = null;
         var _loc4_:b2FilterData = null;
         var _loc5_:Boolean = false;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         var _loc12_:Number = NaN;
         _loc3_ = param1.GetFilterData();
         _loc4_ = param2.GetFilterData();
         if(_loc3_.isCloud)
         {
            if(param1.m_body.GetAngle() != 0)
            {
               _loc6_ = param1.m_body.GetPosition().x - param2.m_body.GetPosition().x;
               _loc7_ = param1.m_body.GetPosition().y - param2.m_body.GetPosition().y;
               _loc8_ = Math.cos(-param1.m_body.GetAngle());
               _loc9_ = Math.sin(-param1.m_body.GetAngle());
               _loc10_ = _loc6_ * _loc8_ + _loc7_ * -_loc9_;
               _loc11_ = _loc6_ * _loc9_ + _loc7_ * _loc8_;
               _loc12_ = Math.atan2(_loc11_,_loc10_);
               if(_loc12_ < -0.35 && _loc12_ > -2.79)
               {
                  return false;
               }
            }
            else if(param2.m_body.GetLinearVelocity().y < 0)
            {
               if(param1.m_body.GetPosition().y < param2.m_body.GetPosition().y - param2.m_body.GetLinearVelocity().y)
               {
                  return false;
               }
            }
         }
         else if(_loc3_.isElevator)
         {
            if(param2.m_body.GetPosition().y >= param1.m_body.GetPosition().y)
            {
               return false;
            }
         }
         else if(_loc4_.isGhost)
         {
            if(param1.m_body.IsStatic())
            {
               return false;
            }
         }
         if(!param1.m_body.IsStatic() && !param2.m_body.IsStatic())
         {
            if(Boolean(param1.m_body.GetUserData().objectData.IsThrowableFragile) && Boolean(param2.m_body.GetUserData().objectData.IsThrowableObject))
            {
               param1.m_body.GetUserData().objectData.ForceDestruction();
               return false;
            }
            if(Boolean(param2.m_body.GetUserData().objectData.IsThrowableFragile) && Boolean(param1.m_body.GetUserData().objectData.IsThrowableObject))
            {
               param2.m_body.GetUserData().objectData.ForceDestruction();
               return false;
            }
         }
         if(!param1.m_body.IsStatic())
         {
            if(param1.m_body.GetUserData().objectData.IgnoreCoverID != -1)
            {
               if(param2.m_body.GetUserData().IDNumber == param1.m_body.GetUserData().objectData.IgnoreCoverID)
               {
                  return false;
               }
            }
         }
         if(!param2.m_body.IsStatic())
         {
            if(param2.m_body.GetUserData().objectData.IgnoreCoverID != -1)
            {
               if(param1.m_body.GetUserData().IDNumber == param2.m_body.GetUserData().objectData.IgnoreCoverID)
               {
                  return false;
               }
            }
         }
         if(_loc3_.groupIndex == _loc4_.groupIndex && _loc3_.groupIndex != 0)
         {
            return _loc3_.groupIndex > 0;
         }
         return (_loc3_.maskBits & _loc4_.categoryBits) != 0 && (_loc3_.categoryBits & _loc4_.maskBits) != 0;
      }
   }
}

