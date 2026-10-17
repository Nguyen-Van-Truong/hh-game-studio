package Code.Handler
{
   import Code.Box2D.Common.Math.b2Vec2;
   import Code.Box2D.Dynamics.*;
   import flash.geom.Rectangle;
   
   public class Portals
   {
      private var m_world:b2World;
      
      private var tmpVel:b2Vec2;
      
      private var _portals:Array;
      
      private var _Handler_Output:OutputTrace;
      
      private var _bodyInPortals:Array;
      
      private var _Handler_Players:PlayersKeeper;
      
      public function Portals(param1:b2World, param2:PlayersKeeper, param3:OutputTrace)
      {
         super();
         m_world = param1;
         _Handler_Players = param2;
         _Handler_Output = param3;
         _portals = new Array();
         _bodyInPortals = new Array();
         _Handler_Output.Trace("Portals Handler Created");
      }
      
      public function Update() : void
      {
         var _loc1_:int = 0;
         var _loc2_:* = undefined;
         var _loc3_:Rectangle = null;
         var _loc4_:* = undefined;
         var _loc5_:* = undefined;
         var _loc6_:int = 0;
         var _loc7_:b2Body = null;
         var _loc8_:int = 0;
         var _loc9_:b2Vec2 = null;
         _loc1_ = int(_bodyInPortals.length - 1);
         while(_loc1_ >= 0)
         {
            _loc7_ = _bodyInPortals[_loc1_];
            if(!_loc7_.IsSleeping())
            {
               _loc3_ = new Rectangle(_loc7_.GetUserData().objectData.ShapeMC.x - _loc7_.GetUserData().objectData.ShapeMC.width / 2,_loc7_.GetUserData().objectData.ShapeMC.y - _loc7_.GetUserData().objectData.ShapeMC.height / 2,_loc7_.GetUserData().objectData.ShapeMC.width,_loc7_.GetUserData().objectData.ShapeMC.height);
               _loc4_ = false;
               _loc5_ = 0;
               while(_loc5_ < _portals.length)
               {
                  if(Boolean(_portals[_loc5_].PointInsidePortal(_loc3_.x,_loc3_.y)) || Boolean(_portals[_loc5_].PointInsidePortal(_loc3_.x + _loc3_.width,_loc3_.y)) || Boolean(_portals[_loc5_].PointInsidePortal(_loc3_.x,_loc3_.y + _loc3_.height)) || Boolean(_portals[_loc5_].PointInsidePortal(_loc3_.x + _loc3_.width,_loc3_.y + _loc3_.height)))
                  {
                     _loc4_ = true;
                     _loc5_ = _portals.length;
                  }
                  _loc5_++;
               }
               if(!_loc4_)
               {
                  _loc7_.GetUserData().objectData.InPortal = false;
                  _bodyInPortals.splice(_loc1_,1);
               }
            }
            _loc1_--;
         }
         _loc2_ = 0;
         while(_loc2_ < _portals.length)
         {
            _loc6_ = 0;
            while(_loc6_ < _Handler_Players.Players.length)
            {
               if(_Handler_Players.Players[_loc6_].PortalSpeedX > 0)
               {
                  if(_portals[_loc2_].PointInsidePortal(_Handler_Players.Players[_loc6_].PosX(),_Handler_Players.Players[_loc6_].PosY() - 6))
                  {
                     if(_Handler_Players.Players[_loc6_].PortalDirectionX < 0 && _portals[_loc2_].TriggerVelocity.x < 0 || _Handler_Players.Players[_loc6_].PortalDirectionX > 0 && _portals[_loc2_].TriggerVelocity.x > 0)
                     {
                        if(Boolean(_portals[_loc2_].AllowPlayers) || Boolean(_Handler_Players.Players[_loc6_].Bot))
                        {
                           _loc9_ = _portals[_loc2_].GetTargetPositionFromCurrent(_Handler_Players.Players[_loc6_].PosX(),_Handler_Players.Players[_loc6_].PosY());
                           _Handler_Players.Players[_loc6_].SetCoordinates(_loc9_.x * 30,_loc9_.y * 30,_portals[_loc2_].InverseX,_portals[_loc2_].AllowPlayers);
                           _Handler_Players.RecalculateCamArea(3,true);
                           _Handler_Output.Trace("Portal " + _loc2_ + " Activated");
                        }
                        else
                        {
                           _Handler_Players.Players[_loc6_].SetCoordinates(_portals[_loc2_].GetSideOfPortal(-_Handler_Players.Players[_loc6_].PortalDirectionX),_Handler_Players.Players[_loc6_].PosY(),true);
                        }
                     }
                  }
               }
               _loc6_++;
            }
            _loc8_ = 0;
            while(_loc8_ < m_world.AllDynamicObjectList.length)
            {
               _loc7_ = m_world.AllDynamicObjectList[_loc8_];
               if(_portals[_loc2_].PointInsidePortal(_loc7_.GetPosition().x * 30,_loc7_.GetPosition().y * 30))
               {
                  if(_loc7_.GetLinearVelocity().Length() > 1)
                  {
                     if(_loc7_.GetLinearVelocity().x < -0.1 && _portals[_loc2_].TriggerVelocity.x < 0 || _loc7_.GetLinearVelocity().x > 0.1 && _portals[_loc2_].TriggerVelocity.x > 0 || _loc7_.GetLinearVelocity().y < 0 && _portals[_loc2_].TriggerVelocity.y < 0 || _loc7_.GetLinearVelocity().y > 0 && _portals[_loc2_].TriggerVelocity.y > 0)
                     {
                        _loc7_.GetUserData().objectData.ThroughPortal = true;
                        _loc7_.SetXForm(_portals[_loc2_].GetTargetPositionFromCurrent(_loc7_.GetPosition().x * 30,_loc7_.GetPosition().y * 30),_loc7_.GetAngle());
                        if(_portals[_loc2_].InverseX)
                        {
                           tmpVel = _loc7_.GetLinearVelocity();
                           tmpVel.x *= -1;
                           _loc7_.SetLinearVelocity(tmpVel);
                        }
                        if(_portals[_loc2_].InverseY)
                        {
                           tmpVel = _loc7_.GetLinearVelocity();
                           tmpVel.y *= -1;
                           _loc7_.SetLinearVelocity(tmpVel);
                        }
                        _Handler_Output.Trace("Portal " + _loc2_ + " Activated");
                        if(_loc7_.GetUserData().objectData.CanGibb)
                        {
                           if(!_loc7_.GetUserData().objectData.InPortal)
                           {
                              _Handler_Output.Trace("Object " + _loc7_.GetUserData().IDNumber + " is overlapping portal " + _loc2_);
                              _loc7_.GetUserData().objectData.CollisionMC.x = 9999;
                              _loc7_.GetUserData().objectData.CollisionMC.y = 9999;
                              _loc7_.GetUserData().objectData.InPortal = true;
                              _bodyInPortals.push(_loc7_);
                           }
                        }
                     }
                  }
               }
               _loc8_++;
            }
            _loc2_++;
         }
      }
      
      public function SetMapPortals(param1:Array) : void
      {
         _portals = param1;
      }
      
      public function CheckBodyInsidePortal(param1:b2Body) : void
      {
         var _loc2_:Rectangle = null;
         var _loc3_:* = undefined;
         if(param1.IsDynamic() == true)
         {
            if(Boolean(param1.GetUserData().objectData.DrawHitBox) || Boolean(param1.GetUserData().objectData.DrawCloudBox))
            {
               _Handler_Output.Trace("Checking Object " + param1.GetUserData().IDNumber + " for portal overlapping");
               _loc2_ = new Rectangle(param1.GetUserData().objectData.ShapeMC.x - param1.GetUserData().objectData.ShapeMC.width / 2,param1.GetUserData().objectData.ShapeMC.y - param1.GetUserData().objectData.ShapeMC.height / 2,param1.GetUserData().objectData.ShapeMC.width,param1.GetUserData().objectData.ShapeMC.height);
               _loc3_ = 0;
               while(_loc3_ < _portals.length)
               {
                  if(Boolean(_portals[_loc3_].PointInsidePortal(_loc2_.x,_loc2_.y)) || Boolean(_portals[_loc3_].PointInsidePortal(_loc2_.x + _loc2_.width,_loc2_.y)) || Boolean(_portals[_loc3_].PointInsidePortal(_loc2_.x,_loc2_.y + _loc2_.height)) || Boolean(_portals[_loc3_].PointInsidePortal(_loc2_.x + _loc2_.width,_loc2_.y + _loc2_.height)))
                  {
                     _Handler_Output.Trace("Object " + param1.GetUserData().IDNumber + " is overlapping portal " + _loc3_);
                     param1.GetUserData().objectData.CollisionMC.x = 9999;
                     param1.GetUserData().objectData.CollisionMC.y = 9999;
                     param1.GetUserData().objectData.InPortal = true;
                     _bodyInPortals.push(param1);
                     return;
                  }
                  _loc3_++;
               }
            }
         }
      }
   }
}

