package Code.Box2D.Dynamics
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.Contacts.*;
   import Code.Data.ContactData;
   import Code.Particles.*;
   
   public class b2ContactListener
   {
      private var _ContactData:ContactData;
      
      private var vec:b2Vec2;
      
      public function b2ContactListener()
      {
         super();
      }
      
      public function Remove(param1:b2ContactPoint) : void
      {
      }
      
      private function CheckConveyorBelt(param1:b2ContactPoint) : void
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         if(param1.shape1.GetBody().GetUserData().isConveyorBelt == true)
         {
            if(!param1.shape2.GetBody().IsStatic())
            {
               if(Math.abs(param1.shape2.GetBody().GetLinearVelocity().x) < Math.abs(param1.shape1.GetBody().GetUserData().conveyorBeltSpeedX))
               {
                  _loc2_ = _ContactData.game_speed * param1.shape1.GetBody().GetUserData().conveyorBeltSpeedX * param1.shape2.GetBody().GetMass();
                  _loc3_ = _ContactData.game_speed * param1.shape1.GetBody().GetUserData().conveyorBeltSpeedY * param1.shape2.GetBody().GetMass();
                  param1.shape2.GetBody().ApplyImpulse(new b2Vec2(_loc2_,_loc3_),new b2Vec2(param1.position.x,param1.position.y));
               }
            }
         }
      }
      
      public function SetHandler(param1:ContactData) : *
      {
         _ContactData = param1;
         vec = new b2Vec2();
      }
      
      public function Add(param1:b2ContactPoint) : void
      {
         var _loc2_:b2Vec2 = null;
         var _loc3_:b2Vec2 = null;
         var _loc4_:Number = NaN;
         _loc2_ = param1.shape1.GetBody().GetLinearVelocityFromWorldPoint(param1.position);
         _loc3_ = param1.shape2.GetBody().GetLinearVelocityFromWorldPoint(param1.position);
         vec = _loc2_.Copy();
         vec.Subtract(_loc3_);
         _loc4_ = Number(vec.Length());
         if(_loc4_ >= 2)
         {
            CheckBodyImpact(param1.shape1.GetBody(),param1.shape2.GetBody(),param1,_loc2_,_loc4_);
         }
         if(!param1.shape1.GetBody().IsStatic() && !param1.shape2.GetBody().IsStatic())
         {
            if(Boolean(param1.shape1.GetBody().GetUserData().objectData.IsGlass))
            {
               param1.shape1.GetBody().GetUserData().objectData.ForceDestruction();
            }
            if(Boolean(param1.shape2.GetBody().GetUserData().objectData.IsGlass))
            {
               param1.shape2.GetBody().GetUserData().objectData.ForceDestruction();
            }
         }
      }
      
      public function Persist(param1:b2ContactPoint) : void
      {
         CheckConveyorBelt(param1);
      }
      
      private function CheckBodyImpact(param1:b2Body, param2:b2Body, param3:b2ContactPoint, param4:b2Vec2, param5:Number) : void
      {
         if(!param1.IsStatic())
         {
            param1.WakeUp();
            _ContactData.Handler_Sounds.PlaySoundAt_Box2DScale(param1.GetUserData().material.BounceImpactSound,param1.GetPosition().x,param1.GetPosition().y);
            param1.GetUserData().objectData.Damage_Impact(param5);
         }
         if(!param2.IsStatic())
         {
            param2.WakeUp();
            _ContactData.Handler_Sounds.PlaySoundAt_Box2DScale(param2.GetUserData().material.BounceImpactSound,param2.GetPosition().x,param2.GetPosition().y);
            param2.GetUserData().objectData.Damage_Impact(param5);
         }
         if(!param2.IsStatic() && !param1.IsStatic())
         {
            if(Boolean(param1.GetUserData().material.ImpactEffectConditionFullfilled(param2.GetUserData().material.Type)))
            {
               _ContactData.Handler_Effects.AddParticle_Box2DScale(new particle_data(param1.GetUserData().material.ImpactEffect,param3.position.x,param3.position.y,param4));
            }
         }
         else
         {
            if(Boolean(param1.GetUserData().material.ImpactEffectConditionFullfilled(param2.GetUserData().material.Type)))
            {
               _ContactData.Handler_Effects.AddParticle_Box2DScale(new particle_data(param1.GetUserData().material.ImpactEffect,param3.position.x,param3.position.y,param4));
            }
            if(Boolean(param2.GetUserData().material.ImpactEffectConditionFullfilled(param1.GetUserData().material.Type)))
            {
               _ContactData.Handler_Effects.AddParticle_Box2DScale(new particle_data(param2.GetUserData().material.ImpactEffect,param3.position.x,param3.position.y,param4));
            }
         }
      }
      
      public function Result(param1:b2ContactResult) : void
      {
      }
   }
}

