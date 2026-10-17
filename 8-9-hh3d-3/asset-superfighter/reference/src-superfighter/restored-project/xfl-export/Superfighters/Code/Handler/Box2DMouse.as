package Code.Handler
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Box2D.Dynamics.Contacts.*;
   import Code.Box2D.Dynamics.Joints.*;
   import flash.display.MovieClip;
   import flash.geom.Point;
   
   public class Box2DMouse
   {
      private var m_world:b2World;
      
      private var mousePVec:b2Vec2;
      
      private var m_timeStep:Number;
      
      private var mouseYWorldPhys:Number;
      
      private var mouseYWorld:Number;
      
      private var _Handler_Mouse:InputMouse;
      
      private var m_body:b2Body;
      
      private var m_mouseJoint:b2MouseJoint;
      
      private var mouseXWorldPhys:Number;
      
      private var mouseXWorld:Number;
      
      public function Box2DMouse(param1:InputMouse, param2:b2World, param3:MovieClip)
      {
         mousePVec = new b2Vec2();
         super();
         _Handler_Mouse = param1;
         m_world = param2;
      }
      
      public function MouseDrag() : void
      {
         var _loc1_:b2MouseJointDef = null;
         var _loc2_:b2Vec2 = null;
         if(_Handler_Mouse.MouseIsDown() && !m_mouseJoint)
         {
            m_body = GetBodyAtMouse();
            if(m_body)
            {
               _loc1_ = new b2MouseJointDef();
               _loc1_.body1 = m_world.GetGroundBody();
               _loc1_.body2 = m_body;
               _loc1_.target.Set(mouseXWorldPhys,mouseYWorldPhys);
               _loc1_.maxForce = 300 * m_body.GetMass();
               _loc1_.timeStep = m_timeStep;
               m_mouseJoint = m_world.CreateJoint(_loc1_) as b2MouseJoint;
               m_body.GetUserData().locked = true;
               m_body.WakeUp();
            }
         }
         if(!_Handler_Mouse.MouseIsDown())
         {
            if(m_mouseJoint)
            {
               m_body.GetUserData().locked = false;
               m_world.DestroyJoint(m_mouseJoint);
               m_mouseJoint = null;
               m_body = null;
            }
         }
         if(m_mouseJoint)
         {
            _loc2_ = new b2Vec2(mouseXWorldPhys,mouseYWorldPhys);
            m_mouseJoint.SetTarget(_loc2_);
         }
      }
      
      private function GetBodyAtMouse(param1:Boolean = false) : b2Body
      {
         var _loc2_:b2AABB = null;
         var _loc3_:int = 0;
         var _loc4_:Array = null;
         var _loc5_:int = 0;
         var _loc6_:b2Body = null;
         var _loc7_:int = 0;
         var _loc8_:b2Shape = null;
         var _loc9_:Boolean = false;
         mousePVec.Set(mouseXWorldPhys,mouseYWorldPhys);
         _loc2_ = new b2AABB();
         _loc2_.lowerBound.Set(mouseXWorldPhys - 0.001,mouseYWorldPhys - 0.001);
         _loc2_.upperBound.Set(mouseXWorldPhys + 0.001,mouseYWorldPhys + 0.001);
         _loc3_ = 10;
         _loc4_ = new Array();
         _loc5_ = m_world.Query(_loc2_,_loc4_,_loc3_);
         _loc6_ = null;
         _loc7_ = 0;
         while(_loc7_ < _loc5_)
         {
            if(_loc4_[_loc7_].GetBody().IsStatic() == false || param1)
            {
               _loc8_ = _loc4_[_loc7_] as b2Shape;
               _loc9_ = _loc8_.TestPoint(_loc8_.GetBody().GetXForm(),mousePVec);
               if(_loc9_)
               {
                  _loc6_ = _loc8_.GetBody();
                  break;
               }
            }
            _loc7_++;
         }
         return _loc6_;
      }
      
      public function MouseInteract() : void
      {
         var _loc1_:b2Body = null;
         var _loc2_:b2Vec2 = null;
         var _loc3_:b2Vec2 = null;
         _loc1_ = GetBodyAtMouse(false);
         if(_loc1_)
         {
            _loc2_ = new b2Vec2();
            _loc3_ = new b2Vec2();
            _loc2_.Set(0,-6 * _loc1_.GetMass());
            _loc3_.x = GetMouseXWorldPhys();
            _loc3_.y = GetMouseYWorldPhys();
            _loc1_.WakeUp();
            _loc1_.ApplyImpulse(_loc2_,_loc3_);
         }
      }
      
      public function GetMouseXWorldPhys() : Number
      {
         return mouseXWorldPhys;
      }
      
      public function MouseDestroy(param1:Boolean = false) : void
      {
         var _loc2_:b2Body = null;
         if(!_Handler_Mouse.MouseIsDown())
         {
            _loc2_ = GetBodyAtMouse(false);
            if(_loc2_)
            {
               if(param1)
               {
                  if(_loc2_.m_userData.objectData.DrawHitBox)
                  {
                     _loc2_.m_userData.objectData.CollisionMC.parent.removeChild(_loc2_.m_userData.objectData.CollisionMC);
                  }
                  _loc2_.m_userData.parent.removeChild(_loc2_.m_userData);
                  m_world.DestroyBody(_loc2_);
               }
               else
               {
                  _loc2_.GetUserData().objectData.ForceDestruction();
               }
               return;
            }
         }
      }
      
      public function UpdateMouseWorld(param1:Point, param2:Number, param3:Number) : void
      {
         m_timeStep = param3;
         _Handler_Mouse.UpdateMouse(param1,param2);
         mouseXWorldPhys = _Handler_Mouse.MouseX() / 30;
         mouseYWorldPhys = _Handler_Mouse.MouseY() / 30;
         mouseXWorld = _Handler_Mouse.MouseX();
         mouseYWorld = _Handler_Mouse.MouseY();
      }
      
      public function GetMouseYWorldPhys() : Number
      {
         return mouseYWorldPhys;
      }
   }
}

