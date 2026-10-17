package Code.Handler
{
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Data.*;
   import flash.display.*;
   import flash.geom.*;
   import flash.utils.*;
   
   public class Fires
   {
      private var _burn_timer:Number = 96;
      
      private var _in_fire_test_mc:MovieClip;
      
      private var _static_mc:MovieClip;
      
      private var _Handler_Effects:Effects;
      
      private var _fire_nodes:Array;
      
      private var _firePlayerObjectTimer:Number;
      
      private var _fire_mc:MovieClip;
      
      private var _Handler_Camera:Cam;
      
      private var _fireObjectFireDamageTimer:Number;
      
      private var _fireTimer:Number;
      
      private var _dynamic_mc:MovieClip;
      
      private var _update_sequence:int = 1;
      
      private var game_speed:Number = 1;
      
      private var _Handler_Players:PlayersKeeper;
      
      private var _Handler_Sounds:Sounds;
      
      private var _static_objects_hitbox_mc:MovieClip;
      
      private var _letFireDrop:Boolean = false;
      
      private var _static_world_hitbox_mc:MovieClip;
      
      private var m_world:b2World;
      
      private var _smoke_packages:Array;
      
      private var _object_shape_container_mc:MovieClip;
      
      private var _Handler_Output:OutputTrace;
      
      private var _static_objects_cloud_hitbox_mc:MovieClip;
      
      private var _static_world_cloud_hitbox_mc:MovieClip;
      
      public function Fires(param1:ExplosionData, param2:MovieClip)
      {
         _burn_timer = 96;
         _update_sequence = 1;
         _letFireDrop = false;
         game_speed = 1;
         super();
         _Handler_Output = param1.Handler_Output;
         _Handler_Camera = param1.Handler_Camera;
         _Handler_Players = param1.Handler_Players;
         _Handler_Effects = param1.Handler_Effects;
         _Handler_Sounds = param1.Handler_Sounds;
         _static_mc = param1.static_mc;
         _dynamic_mc = param1.dynamic_mc;
         m_world = param1.m_world;
         _object_shape_container_mc = param2;
         _static_world_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_HITBOX"));
         _static_objects_hitbox_mc = MovieClip(_static_world_hitbox_mc.getChildByName("OBJECTS_HITBOX"));
         _static_world_cloud_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_CLOUD_HITBOX"));
         _static_objects_cloud_hitbox_mc = MovieClip(_static_world_cloud_hitbox_mc.getChildByName("OBJECTS_CLOUD_HITBOX"));
         _fire_mc = new MovieClip();
         _static_mc.addChild(_fire_mc);
         _smoke_packages = new Array();
         _fire_nodes = new Array();
         _in_fire_test_mc = new MovieClip();
         _in_fire_test_mc.graphics.lineStyle(0.5,16711680,1);
         _in_fire_test_mc.graphics.beginFill(16711680,0.5);
         _in_fire_test_mc.graphics.moveTo(-4,0);
         _in_fire_test_mc.graphics.lineTo(-4,-16);
         _in_fire_test_mc.graphics.lineTo(4,-16);
         _in_fire_test_mc.graphics.lineTo(4,0);
         _in_fire_test_mc.graphics.lineTo(4,0);
         _in_fire_test_mc.graphics.endFill();
         _fireTimer = setInterval(UpdateFires,1000 / 24);
         _firePlayerObjectTimer = setInterval(PlayerObjectOverlap,42);
         _fireObjectFireDamageTimer = setInterval(ObjectFireDamage,84);
         _Handler_Output.Trace("Fire Handler Created");
      }
      
      private function CollisionFireBlock(param1:Point) : Boolean
      {
         var _loc2_:b2Body = null;
         if(Boolean(CollisionStatic(param1)) || Boolean(CollisionStaticCloud(param1)))
         {
            return true;
         }
         _loc2_ = m_world.GetDynamicBodyAt(param1.x,param1.y,true);
         if(_loc2_ != null)
         {
            if(Boolean(_loc2_.GetUserData().objectData.CanBlockFire))
            {
               return true;
            }
         }
         return false;
      }
      
      private function PlayerOverlap() : void
      {
         var _loc1_:int = 0;
         var _loc2_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < _Handler_Players.Players.length)
         {
            if(!_Handler_Players.Players[_loc1_].State.Gone)
            {
               if(_fire_mc.hitTestObject(_Handler_Players.Players[_loc1_].CollisionMC))
               {
                  _loc2_ = _fire_nodes.length - 1;
                  while(_loc2_ >= 0)
                  {
                     if(_fire_nodes[_loc2_].Owner != _loc1_)
                     {
                        if(_fire_nodes[_loc2_].PlayerNR != _loc1_)
                        {
                           if(Boolean(_fire_nodes[_loc2_].FireArea.hitTestObject(_Handler_Players.Players[_loc1_].CollisionMC)))
                           {
                              if(Boolean(_fire_nodes[_loc2_].IsFlamethrower))
                              {
                                 _Handler_Players.Players[_loc1_].State.BurnState += 20;
                              }
                              _Handler_Players.Players[_loc1_].FireContact(true,3);
                              _loc2_ = -1;
                           }
                        }
                     }
                     _loc2_--;
                  }
               }
               PlayerInFire(_loc1_);
            }
            _loc1_++;
         }
      }
      
      private function ObjectOverlap() : void
      {
         var _loc1_:b2Body = null;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < m_world.BurnObjectList.length)
         {
            _loc1_ = m_world.BurnObjectList[_loc2_];
            if(!_loc1_.GetUserData().objectData.ObjectOnFire)
            {
               if(_fire_mc.hitTestObject(_loc1_.GetUserData().objectData.ShapeMC))
               {
                  _loc3_ = _fire_nodes.length - 1;
                  while(_loc3_ >= 0)
                  {
                     if(Boolean(_fire_nodes[_loc3_].FireArea.hitTestObject(_loc1_.GetUserData().objectData.ShapeMC)))
                     {
                        AddFireToObject(_loc1_);
                        _loc3_ = -1;
                     }
                     _loc3_--;
                  }
               }
            }
            _loc2_++;
         }
      }
      
      private function CollisionStaticCloud(param1:Point) : Boolean
      {
         if(Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(param1.x,param1.y,true)) && !_static_objects_cloud_hitbox_mc.hitTestPoint(param1.x,param1.y,true))
         {
            return true;
         }
         return false;
      }
      
      public function AddFireToObject(param1:b2Body) : void
      {
         var _loc2_:FireNodeData = null;
         if(Boolean(param1.GetUserData().objectData.CanBurn))
         {
            if(!param1.GetUserData().objectData.ObjectOnFire)
            {
               _loc2_ = new FireNodeData(_Handler_Effects,_fire_mc,_burn_timer,0,0,0,0);
               _loc2_.BurnBody(param1);
               _fire_nodes.push(_loc2_);
               param1.GetUserData().objectData.ObjectOnFire = true;
            }
         }
      }
      
      private function ObjectFireDamage() : void
      {
         var _loc1_:b2Body = null;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < m_world.CanTakeFireDamageList.length)
         {
            _loc1_ = m_world.CanTakeFireDamageList[_loc2_];
            if(_fire_mc.hitTestObject(_loc1_.GetUserData().objectData.ShapeMC))
            {
               _loc3_ = _fire_nodes.length - 1;
               while(_loc3_ >= 0)
               {
                  if(Boolean(_fire_nodes[_loc3_].FireArea.hitTestObject(_loc1_.GetUserData().objectData.ShapeMC)))
                  {
                     if(Boolean(_fire_nodes[_loc3_].IsFlamethrower))
                     {
                        _loc1_.GetUserData().objectData.Damage_Fire(game_speed * 6);
                     }
                     else
                     {
                        _loc1_.GetUserData().objectData.Damage_Fire(game_speed * 2);
                     }
                     _loc3_ = -1;
                  }
                  _loc3_--;
               }
            }
            _loc2_++;
         }
      }
      
      private function UpdateFires() : void
      {
         var _loc1_:b2Body = null;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:Number = NaN;
         var _loc5_:int = 0;
         var _loc6_:Boolean = false;
         var _loc7_:Point = null;
         var _loc8_:int = 0;
         var _loc9_:int = 0;
         var _loc10_:FireNodeData = null;
         if(_smoke_packages.length > 0)
         {
            _loc3_ = 0;
            while(_loc3_ < _smoke_packages.length)
            {
               _smoke_packages[_loc3_].Update(game_speed);
               if(Boolean(_smoke_packages[_loc3_].SmokePackageCompleted))
               {
                  _smoke_packages.splice(_loc3_,1);
               }
               _loc3_++;
            }
         }
         _loc2_ = _fire_nodes.length - 1;
         while(_loc2_ >= 0)
         {
            _fire_nodes[_loc2_].Update(game_speed);
            if(Boolean(_fire_nodes[_loc2_].InAir))
            {
               if(!_fire_nodes[_loc2_].IsFlamethrower)
               {
                  _fire_nodes[_loc2_].VelX *= 0.9 + 0.1 * (1 - game_speed);
               }
               else
               {
                  _fire_nodes[_loc2_].VelX *= 0.93 + 0.07 * (1 - game_speed);
               }
               if(Boolean(_fire_nodes[_loc2_].SlowingDown))
               {
                  if(!_fire_nodes[_loc2_].IsFlamethrower)
                  {
                     _fire_nodes[_loc2_].VelY *= 0.9 + 0.1 * (1 - game_speed);
                  }
                  else
                  {
                     _fire_nodes[_loc2_].VelY *= 0.95 + 0.05 * (1 - game_speed);
                  }
                  if(Math.abs(_fire_nodes[_loc2_].TotalVel) <= 2)
                  {
                     _fire_nodes[_loc2_].SlowingDown = false;
                  }
               }
               else
               {
                  _fire_nodes[_loc2_].VelY += 0.2 * game_speed;
               }
               _loc4_ = 1;
               _loc4_ = Math.round(_fire_nodes[_loc2_].TotalVel / 4);
               if(_loc4_ < 1)
               {
                  _loc4_ = 1;
               }
               _loc5_ = 0;
               while(_loc5_ < _loc4_)
               {
                  _fire_nodes[_loc2_].PosX += _fire_nodes[_loc2_].VelX * game_speed / _loc4_;
                  _fire_nodes[_loc2_].PosY += _fire_nodes[_loc2_].VelY * game_speed / _loc4_;
                  _loc6_ = _fire_nodes[_loc2_].VelY < 0;
                  if(Boolean(_fire_nodes[_loc2_].PassCloud))
                  {
                     _loc6_ = true;
                  }
                  _loc7_ = new Point(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY);
                  if(Boolean(CollisionStatic(_loc7_)) || Boolean(CollisionStaticCloud(_loc7_)) && !_loc6_)
                  {
                     _loc8_ = 0;
                     while(_loc8_ < 10)
                     {
                        _fire_nodes[_loc2_].PosX -= _fire_nodes[_loc2_].VelX * game_speed / (_loc4_ * 4);
                        _fire_nodes[_loc2_].PosY -= _fire_nodes[_loc2_].VelY * game_speed / (_loc4_ * 4);
                        _loc7_ = new Point(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY);
                        if(!CollisionStatic(_loc7_) && !CollisionStaticCloud(_loc7_))
                        {
                           _loc8_ = 10;
                        }
                        _loc8_++;
                     }
                     if(_letFireDrop)
                     {
                        _loc7_ = new Point(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY + 2);
                        if(Boolean(CollisionStatic(_loc7_)) || Boolean(CollisionStaticCloud(_loc7_)) && !_loc6_)
                        {
                           _fire_nodes[_loc2_].InAir = false;
                        }
                        else
                        {
                           _fire_nodes[_loc2_].VelY = 0;
                           if(_fire_nodes[_loc2_].VelX < 0)
                           {
                              _fire_nodes[_loc2_].VelX = 0.1;
                           }
                           else if(_fire_nodes[_loc2_].VelX > 0)
                           {
                              _fire_nodes[_loc2_].VelX = -0.1;
                           }
                        }
                     }
                     else
                     {
                        _fire_nodes[_loc2_].InAir = false;
                     }
                  }
                  else if(_object_shape_container_mc.hitTestPoint(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY,true))
                  {
                     _loc1_ = m_world.GetFireCarrierAt(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY);
                     if(_loc1_ != null)
                     {
                        _loc9_ = 0;
                        while(_loc9_ < 10)
                        {
                           _fire_nodes[_loc2_].PosX -= _fire_nodes[_loc2_].VelX * game_speed / (_loc4_ * 4);
                           _fire_nodes[_loc2_].PosY -= _fire_nodes[_loc2_].VelY * game_speed / (_loc4_ * 4);
                           if(!_loc1_.m_userData.objectData.ShapeMC.hitTestPoint(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY,true))
                           {
                              _loc9_ = 10;
                           }
                           _loc9_++;
                        }
                        if(_letFireDrop)
                        {
                           if(Boolean(_loc1_.m_userData.objectData.ShapeMC.hitTestPoint(_fire_nodes[_loc2_].PosX,_fire_nodes[_loc2_].PosY + 2,true)))
                           {
                              _fire_nodes[_loc2_].InAir = false;
                           }
                           else
                           {
                              _fire_nodes[_loc2_].VelY = 0;
                              if(_fire_nodes[_loc2_].VelX < 0)
                              {
                                 _fire_nodes[_loc2_].VelX = 0.1;
                              }
                              else if(_fire_nodes[_loc2_].VelX > 0)
                              {
                                 _fire_nodes[_loc2_].VelX = -0.1;
                              }
                           }
                        }
                        else
                        {
                           _fire_nodes[_loc2_].InAir = false;
                        }
                        if(!_fire_nodes[_loc2_].InAir)
                        {
                           _fire_nodes[_loc2_].FollowBody(_loc1_,_loc1_.GetLocalPoint(new b2Vec2(_fire_nodes[_loc2_].PosX / 30,_fire_nodes[_loc2_].PosY / 30)));
                        }
                     }
                  }
                  _loc5_++;
               }
               _fire_nodes[_loc2_].UpdateMC();
               if(!_fire_nodes[_loc2_].InAir)
               {
                  _loc10_ = GetNearbyFireNode(_fire_nodes[_loc2_]);
                  if(_loc10_ != null)
                  {
                     if(_fire_nodes[_loc2_].BurnTimer > _loc10_.BurnTimer)
                     {
                        _loc10_.BurnTimer = _fire_nodes[_loc2_].BurnTimer;
                     }
                     _fire_nodes[_loc2_].End();
                  }
               }
            }
            if(Boolean(_fire_nodes[_loc2_].FireNodeCompleted))
            {
               _fire_nodes.splice(_loc2_,1);
            }
            _loc2_--;
         }
      }
      
      private function PlayerObjectOverlap() : void
      {
         _update_sequence += 1;
         if(_update_sequence > 2)
         {
            _update_sequence = 1;
         }
         if(_update_sequence == 1)
         {
            ObjectOverlap();
         }
         else if(_update_sequence == 2)
         {
            PlayerOverlap();
         }
      }
      
      private function CollisionStatic(param1:Point) : Boolean
      {
         if(Boolean(_static_world_hitbox_mc.hitTestPoint(param1.x,param1.y,true)) && !_static_objects_hitbox_mc.hitTestPoint(param1.x,param1.y,true))
         {
            return true;
         }
         return false;
      }
      
      public function AddSmokeToObject(param1:b2Body, param2:Number) : void
      {
         var _loc3_:SmokePackageDataDynamic = null;
         if(Boolean(param1.GetUserData().objectData.CanSmoke))
         {
            if(param2 > param1.GetUserData().objectData.ObjectSmokeGrade)
            {
               param1.GetUserData().objectData.ObjectSmokeGrade = param2;
               _loc3_ = new SmokePackageDataDynamic(_Handler_Effects);
               _loc3_.SetSmokeElementAt(param1);
               _smoke_packages.push(_loc3_);
            }
         }
      }
      
      public function Stop() : void
      {
         clearInterval(_fireTimer);
         clearInterval(_firePlayerObjectTimer);
         clearInterval(_fireObjectFireDamageTimer);
      }
      
      public function AddFlame(param1:Number, param2:Number, param3:Number, param4:int) : void
      {
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:b2Vec2 = null;
         _loc5_ = param3 * (Math.PI / 180);
         _loc6_ = 9 + Math.random() * 1;
         _loc7_ = new b2Vec2(Math.cos(_loc5_) * _loc6_,Math.sin(_loc5_) * _loc6_);
         _fire_nodes.push(new FireNodeData(_Handler_Effects,_fire_mc,_burn_timer,param1,param2,_loc7_.x,_loc7_.y,param4,1));
      }
      
      public function TriggerFireAt(param1:String, param2:Number, param3:Number) : void
      {
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:int = 0;
         var _loc11_:Number = NaN;
         var _loc12_:Number = NaN;
         var _loc13_:Number = NaN;
         var _loc14_:Number = NaN;
         var _loc15_:Number = NaN;
         var _loc16_:Number = NaN;
         var _loc17_:int = 0;
         var _loc18_:Boolean = false;
         var _loc19_:Point = null;
         var _loc20_:int = 0;
         _Handler_Output.Trace("Fire Triggered At (" + param2 + ", " + param3 + ")");
         if(_static_world_hitbox_mc.hitTestPoint(param2,param3,true))
         {
            if(!_static_objects_hitbox_mc.hitTestPoint(param2,param3,true))
            {
               _Handler_Output.Trace("Fire triggered inside a static object. Aborting fire");
               return;
            }
         }
         _loc8_ = 3;
         _loc9_ = 0.5;
         _loc10_ = 22;
         _loc11_ = 20;
         switch(param1.toUpperCase())
         {
            case "GASCAN":
            case "BARREL":
               _loc11_ = 16;
               _loc8_ = 2.2;
               _loc9_ = 0.4;
               _loc10_ = 18;
         }
         _loc12_ = 0;
         while(_loc12_ < _loc10_)
         {
            _loc4_ = Math.PI / (_loc10_ / 2) * _loc12_;
            _loc7_ = _loc8_ + Math.random() * _loc9_;
            _loc5_ = Math.cos(_loc4_) * _loc7_;
            _loc6_ = Math.sin(_loc4_) * _loc7_ - Math.random() * 0.5;
            _fire_nodes.push(new FireNodeData(_Handler_Effects,_fire_mc,_burn_timer,param2 + Math.cos(_loc4_) * 3,param3 + Math.sin(_loc4_) * 3,_loc5_,_loc6_));
            _loc12_++;
         }
         _loc17_ = 0;
         while(_loc17_ < _Handler_Players.Players.length)
         {
            _loc13_ = param2;
            _loc14_ = param3;
            _loc15_ = _Handler_Players.Players[_loc17_].MidPosX() - param2;
            _loc16_ = _Handler_Players.Players[_loc17_].MidPosY() - param3;
            if(Math.sqrt(_loc15_ * _loc15_ + _loc16_ * _loc16_) <= _loc11_)
            {
               _loc5_ = _loc15_ / _loc11_;
               _loc6_ = _loc16_ / _loc11_;
               _loc18_ = false;
               _loc19_ = new Point(param2,param3);
               _loc20_ = 1;
               while(_loc20_ <= _loc11_)
               {
                  _loc19_.x += _loc5_;
                  _loc19_.y += _loc6_;
                  if(CollisionFireBlock(_loc19_))
                  {
                     _loc18_ = true;
                     _loc20_ = _loc11_ + 1;
                  }
                  _loc20_++;
               }
               if(!_loc18_)
               {
                  _Handler_Players.Players[_loc17_].State.BurnState = 100;
                  PlayerInFire(_loc17_);
               }
            }
            _loc17_++;
         }
      }
      
      public function TriggerFireAt_Box2DScale(param1:String, param2:Number, param3:Number) : void
      {
         param2 = Math.round(param2 * 30);
         param3 = Math.round(param3 * 30);
         TriggerFireAt(param1,param2,param3);
      }
      
      private function GradToRad(param1:Number) : Number
      {
         return Math.PI / 180 * param1;
      }
      
      private function GetNearbyFireNode(param1:FireNodeData) : FireNodeData
      {
         var _loc2_:FireNodeData = null;
         var _loc3_:Number = NaN;
         var _loc4_:int = 0;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         _loc2_ = null;
         _loc3_ = 3;
         _loc4_ = 0;
         while(_loc4_ < _fire_nodes.length)
         {
            if(Boolean(_fire_nodes[_loc4_].CanBeMerged))
            {
               if(_fire_nodes[_loc4_] != param1)
               {
                  _loc5_ = _fire_nodes[_loc4_].PosX - param1.PosX;
                  _loc6_ = _fire_nodes[_loc4_].PosY - param1.PosY;
                  _loc7_ = Math.sqrt(_loc5_ * _loc5_ + _loc6_ * _loc6_);
                  if(_loc7_ < _loc3_)
                  {
                     _loc3_ = _loc7_;
                     _loc2_ = _fire_nodes[_loc4_];
                  }
               }
            }
            _loc4_++;
         }
         return _loc2_;
      }
      
      private function PlayerInFire(param1:int) : void
      {
         var _loc2_:FireNodeData = null;
         if(_Handler_Players.Players[param1].State.BurnState > 0)
         {
            if(!_Handler_Players.Players[param1].State.FireRank1Attached && _Handler_Players.Players[param1].State.BurnState >= _Handler_Players.Players[param1].State.FireRank1Minimum)
            {
               _loc2_ = new FireNodeData(_Handler_Effects,_fire_mc,_burn_timer,0,0,0,0);
               _loc2_.BurnPlayer(_Handler_Players.Players[param1],param1,1);
               _Handler_Players.Players[param1].State.FireRank1Attached = true;
               _fire_nodes.push(_loc2_);
            }
            if(!_Handler_Players.Players[param1].State.FireRank2Attached && _Handler_Players.Players[param1].State.BurnState >= _Handler_Players.Players[param1].State.FireRank2Minimum)
            {
               _loc2_ = new FireNodeData(_Handler_Effects,MovieClip(_dynamic_mc.getChildByName("EFFECTS2")),_burn_timer,0,0,0,0);
               _loc2_.BurnPlayer(_Handler_Players.Players[param1],param1,2);
               _Handler_Players.Players[param1].State.FireRank2Attached = true;
               _fire_nodes.push(_loc2_);
            }
         }
      }
      
      public function Update(param1:Number) : void
      {
         game_speed = param1;
      }
      
      public function PlayerPosInFire(param1:Number, param2:Number) : Boolean
      {
         var _loc3_:int = 0;
         if(_fire_nodes.length <= 0)
         {
            return false;
         }
         _in_fire_test_mc.x = param1;
         _in_fire_test_mc.y = param2;
         if(_fire_mc.hitTestObject(_in_fire_test_mc))
         {
            _loc3_ = _fire_nodes.length - 1;
            while(_loc3_ >= 0)
            {
               if(Boolean(_fire_nodes[_loc3_].FireArea.hitTestObject(_in_fire_test_mc)))
               {
                  return true;
               }
               _loc3_--;
            }
         }
         return false;
      }
   }
}

