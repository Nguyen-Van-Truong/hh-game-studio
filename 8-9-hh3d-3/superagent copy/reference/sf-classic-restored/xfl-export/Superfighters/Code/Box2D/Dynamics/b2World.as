package Code.Box2D.Dynamics
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.Contacts.*;
   import Code.Box2D.Dynamics.Joints.*;
   
   public class b2World
   {
      public static var m_continuousPhysics:Boolean;
      
      public static var m_warmStarting:Boolean;
      
      public static var m_positionCorrection:Boolean;
      
      private static var s_jointColor:b2Color = new b2Color(0.5,0.8,0.8);
      
      private static var s_coreColor:b2Color = new b2Color(0.9,0.6,0.6);
      
      private static var s_xf:b2XForm = new b2XForm();
      
      private var _laser_solid_list:Array;
      
      private var _aim_solid_list:Array;
      
      public var m_contactList:b2Contact;
      
      private var _weapon_list:Array;
      
      private var _stair_object_list:Array;
      
      public var m_broadPhase:b2BroadPhase;
      
      public var m_allowSleep:Boolean;
      
      public var m_contactListener:b2ContactListener;
      
      public var m_blockAllocator:*;
      
      public var m_bodyCount:int;
      
      private var _hazards_list:Array;
      
      public var m_contactCount:int;
      
      public var m_contactFilter:b2ContactFilter;
      
      private var _fire_carrier_list:Array;
      
      private var _part_of_static_world:Array;
      
      public var m_contactManager:b2ContactManager;
      
      public var m_gravity:b2Vec2;
      
      public var m_stackAllocator:*;
      
      private var _molotov_list:Array;
      
      public var m_inv_dt0:Number;
      
      private var _burn_object_list:Array;
      
      private var _static_covers:Array;
      
      private var _bullet_solid_list:Array;
      
      private var _conveyor_list:Array;
      
      public var m_boundaryListener:b2BoundaryListener;
      
      public var m_destructionListener:b2DestructionListener;
      
      private var _is_glass_list:Array;
      
      private var _all_dynamic_object_list:Array;
      
      public var m_lock:Boolean;
      
      private var _button_list:Array;
      
      public var m_positionIterationCount:int;
      
      public var m_jointCount:int;
      
      private var _dynamic_hitbox_object_list:Array;
      
      public var FallAsleepBody:Function;
      
      public var m_groundBody:b2Body;
      
      private var _ladder_list:Array;
      
      private var _dynamic_object_list:Array;
      
      private var _static_object_list:Array;
      
      private var _can_take_fire_damage_list:Array;
      
      private var _static_rotated_cloud_list:Array;
      
      public var m_bodyList:b2Body;
      
      public var m_jointList:b2Joint;
      
      public var m_debugDraw:b2DebugDraw;
      
      public function b2World(param1:b2AABB, param2:b2Vec2, param3:Boolean)
      {
         var _loc4_:b2BodyDef = null;
         _dynamic_object_list = new Array();
         _all_dynamic_object_list = new Array();
         _dynamic_hitbox_object_list = new Array();
         _static_object_list = new Array();
         _stair_object_list = new Array();
         _conveyor_list = new Array();
         _weapon_list = new Array();
         _button_list = new Array();
         _ladder_list = new Array();
         _burn_object_list = new Array();
         _fire_carrier_list = new Array();
         _bullet_solid_list = new Array();
         _laser_solid_list = new Array();
         _aim_solid_list = new Array();
         _molotov_list = new Array();
         _can_take_fire_damage_list = new Array();
         _static_covers = new Array();
         _hazards_list = new Array();
         _static_rotated_cloud_list = new Array();
         _is_glass_list = new Array();
         _part_of_static_world = new Array();
         FallAsleepBody = function(param1:b2Body):void
         {
         };
         m_contactManager = new b2ContactManager();
         super();
         m_destructionListener = null;
         m_boundaryListener = null;
         m_contactFilter = b2ContactFilter.b2_defaultFilter;
         m_contactListener = null;
         m_debugDraw = null;
         m_bodyList = null;
         m_contactList = null;
         m_jointList = null;
         m_bodyCount = 0;
         m_contactCount = 0;
         m_jointCount = 0;
         m_positionCorrection = true;
         m_warmStarting = true;
         m_continuousPhysics = true;
         m_allowSleep = param3;
         m_gravity = param2;
         m_lock = false;
         m_inv_dt0 = 0;
         m_contactManager.m_world = this;
         m_broadPhase = new b2BroadPhase(param1,m_contactManager);
         _loc4_ = new b2BodyDef();
         m_groundBody = CreateBody(_loc4_);
      }
      
      public function get LadderList() : Array
      {
         return _ladder_list;
      }
      
      private function RemoveObject(param1:b2Body, param2:Array) : void
      {
         var _loc3_:* = undefined;
         _loc3_ = 0;
         while(_loc3_ < param2.length)
         {
            if(param2[_loc3_].GetUserData().IDNumber == param1.GetUserData().IDNumber)
            {
               param2.splice(_loc3_,1);
            }
            _loc3_++;
         }
      }
      
      public function GetStairBodyAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < _stair_object_list.length)
         {
            _loc3_ = _stair_object_list[_loc4_];
            if(_loc3_.GetUserData().shapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function get ButtonList() : Array
      {
         return _button_list;
      }
      
      public function get DynamicHitBoxObjectList() : Array
      {
         return _dynamic_hitbox_object_list;
      }
      
      public function SetDebugDraw(param1:b2DebugDraw) : void
      {
         m_debugDraw = param1;
      }
      
      public function SetContinuousPhysics(param1:Boolean) : void
      {
         m_continuousPhysics = param1;
      }
      
      public function GetProxyCount() : int
      {
         return m_broadPhase.m_proxyCount;
      }
      
      public function GetAimSolidAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < AimSolidList.length)
         {
            _loc3_ = AimSolidList[_loc4_];
            if(_loc3_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function GetFireCarrierAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:Array = null;
         var _loc4_:b2Body = null;
         var _loc5_:* = undefined;
         _loc3_ = FireCarrierList;
         _loc5_ = 0;
         while(_loc5_ < _loc3_.length)
         {
            _loc4_ = _loc3_[_loc5_];
            if(_loc4_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc4_;
            }
            _loc5_++;
         }
         return null;
      }
      
      public function GetContactCount() : int
      {
         return m_contactCount;
      }
      
      public function get IsGlassList() : Array
      {
         return _is_glass_list;
      }
      
      public function Solve(param1:b2TimeStep) : void
      {
         var _loc2_:b2Body = null;
         var _loc3_:b2Island = null;
         var _loc4_:b2Contact = null;
         var _loc5_:b2Joint = null;
         var _loc6_:int = 0;
         var _loc7_:Array = null;
         var _loc8_:b2Body = null;
         var _loc9_:int = 0;
         var _loc10_:int = 0;
         var _loc11_:b2Body = null;
         var _loc12_:b2ContactEdge = null;
         var _loc13_:b2JointEdge = null;
         var _loc14_:Boolean = false;
         m_positionIterationCount = 0;
         _loc3_ = new b2Island(m_bodyCount,m_contactCount,m_jointCount,m_stackAllocator,m_contactListener,FallAsleepBody);
         _loc2_ = m_bodyList;
         while(_loc2_)
         {
            _loc2_.m_flags &= ~b2Body.e_islandFlag;
            _loc2_ = _loc2_.m_next;
         }
         _loc4_ = m_contactList;
         while(_loc4_)
         {
            _loc4_.m_flags &= ~b2Contact.e_islandFlag;
            _loc4_ = _loc4_.m_next;
         }
         _loc5_ = m_jointList;
         while(_loc5_)
         {
            _loc5_.m_islandFlag = false;
            _loc5_ = _loc5_.m_next;
         }
         _loc6_ = m_bodyCount;
         _loc7_ = new Array(_loc6_);
         _loc8_ = m_bodyList;
         while(_loc8_)
         {
            if(!(_loc8_.m_flags & (b2Body.e_islandFlag | b2Body.e_sleepFlag | b2Body.e_frozenFlag)))
            {
               if(!_loc8_.IsStatic())
               {
                  _loc3_.Clear();
                  _loc9_ = 0;
                  var _loc15_:*;
                  _loc7_[_loc15_ = _loc9_++] = _loc8_;
                  _loc8_.m_flags |= b2Body.e_islandFlag;
                  while(_loc9_ > 0)
                  {
                     _loc2_ = _loc7_[--_loc9_];
                     _loc3_.AddBody(_loc2_);
                     _loc2_.m_flags &= ~b2Body.e_sleepFlag;
                     if(!_loc2_.IsStatic())
                     {
                        _loc12_ = _loc2_.m_contactList;
                        while(_loc12_)
                        {
                           if(!(_loc12_.contact.m_flags & (b2Contact.e_islandFlag | b2Contact.e_nonSolidFlag)))
                           {
                              if(_loc12_.contact.m_manifoldCount != 0)
                              {
                                 _loc3_.AddContact(_loc12_.contact);
                                 _loc12_.contact.m_flags |= b2Contact.e_islandFlag;
                                 _loc11_ = _loc12_.other;
                                 if(!(_loc11_.m_flags & b2Body.e_islandFlag))
                                 {
                                    var _loc16_:*;
                                    _loc7_[_loc16_ = _loc9_++] = _loc11_;
                                    _loc11_.m_flags |= b2Body.e_islandFlag;
                                 }
                              }
                           }
                           _loc12_ = _loc12_.next;
                        }
                        _loc13_ = _loc2_.m_jointList;
                        while(_loc13_)
                        {
                           if(_loc13_.joint.m_islandFlag != true)
                           {
                              _loc3_.AddJoint(_loc13_.joint);
                              _loc13_.joint.m_islandFlag = true;
                              _loc11_ = _loc13_.other;
                              if(!(_loc11_.m_flags & b2Body.e_islandFlag))
                              {
                                 _loc7_[_loc16_ = _loc9_++] = _loc11_;
                                 _loc11_.m_flags |= b2Body.e_islandFlag;
                              }
                           }
                           _loc13_ = _loc13_.next;
                        }
                     }
                  }
                  _loc3_.Solve(param1,m_gravity,m_positionCorrection,m_allowSleep);
                  if(_loc3_.m_positionIterationCount > m_positionIterationCount)
                  {
                     m_positionIterationCount = _loc3_.m_positionIterationCount;
                  }
                  _loc10_ = 0;
                  while(_loc10_ < _loc3_.m_bodyCount)
                  {
                     _loc2_ = _loc3_.m_bodies[_loc10_];
                     if(_loc2_.IsStatic())
                     {
                        _loc2_.m_flags &= ~b2Body.e_islandFlag;
                     }
                     _loc10_++;
                  }
               }
            }
            _loc8_ = _loc8_.m_next;
         }
         _loc2_ = m_bodyList;
         while(_loc2_)
         {
            if(!(_loc2_.m_flags & (b2Body.e_sleepFlag | b2Body.e_frozenFlag)))
            {
               if(!_loc2_.IsStatic())
               {
                  _loc14_ = _loc2_.SynchronizeShapes();
                  if(_loc14_ == false && m_boundaryListener != null)
                  {
                     m_boundaryListener.Violation(_loc2_);
                  }
               }
            }
            _loc2_ = _loc2_.m_next;
         }
         m_broadPhase.Commit();
      }
      
      public function get ConveyorList() : Array
      {
         return _conveyor_list;
      }
      
      public function get MolotovList() : Array
      {
         return _molotov_list;
      }
      
      public function Validate() : void
      {
         m_broadPhase.Validate();
      }
      
      public function GetBulletSolidAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < BulletSolidList.length)
         {
            _loc3_ = BulletSolidList[_loc4_];
            if(_loc3_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function SetWarmStarting(param1:Boolean) : void
      {
         m_warmStarting = param1;
      }
      
      public function RemoveObjectFromLists(param1:b2Body) : void
      {
         if(param1.IsDynamic())
         {
            if(!param1.GetUserData().objectData.DrawShapeMC)
            {
               return;
            }
            RemoveObject(param1,_all_dynamic_object_list);
            if(param1.GetUserData().isWeapon == true)
            {
               RemoveObject(param1,_weapon_list);
            }
            else if(param1.GetUserData().isButton == true)
            {
               RemoveObject(param1,_button_list);
            }
            else if(param1.GetUserData().isLadder == true)
            {
               RemoveObject(param1,_ladder_list);
            }
            else
            {
               RemoveObject(param1,_dynamic_object_list);
               if(!param1.GetUserData().objectData.BulletTransparent)
               {
                  RemoveObject(param1,_bullet_solid_list);
               }
               if(!param1.GetUserData().objectData.LaserTransparent || Boolean(param1.GetUserData().objectData.LaserVisibleOnObject))
               {
                  RemoveObject(param1,_laser_solid_list);
               }
               if(!param1.GetUserData().objectData.AimTransparent)
               {
                  RemoveObject(param1,_aim_solid_list);
               }
               if(Boolean(param1.GetUserData().objectData.DrawHitBox) || Boolean(param1.GetUserData().objectData.DrawCloudBox))
               {
                  RemoveObject(param1,_dynamic_hitbox_object_list);
               }
               if(param1.GetUserData().objectData.IsGlass)
               {
                  RemoveObject(param1,_is_glass_list);
               }
               if(param1.GetUserData().objectData.CanBurn)
               {
                  RemoveObject(param1,_burn_object_list);
               }
               else if(param1.GetUserData().objectData.ResistanceFire > 0)
               {
                  RemoveObject(param1,_can_take_fire_damage_list);
               }
               if(param1.GetUserData().objectData.CanBeHazard)
               {
                  RemoveObject(param1,_hazards_list);
               }
               if(param1.GetUserData().objectData.PartOfStaticWorld)
               {
                  RemoveObject(param1,_part_of_static_world);
               }
               if(param1.GetUserData().objectData.CanCarryFire)
               {
                  RemoveObject(param1,_fire_carrier_list);
               }
               if(param1.GetUserData().tiltValue != 0)
               {
                  RemoveObject(param1,_stair_object_list);
               }
               if(param1.GetUserData().isMolotov == true)
               {
                  RemoveObject(param1,_molotov_list);
               }
            }
         }
         else
         {
            RemoveObject(param1,_static_object_list);
            if(param1.GetUserData().tiltValue != 0)
            {
               RemoveObject(param1,_stair_object_list);
            }
            if(param1.GetUserData().isConveyorBelt == true)
            {
               RemoveObject(param1,_conveyor_list);
            }
            if(param1.GetUserData().isLadder == true)
            {
               RemoveObject(param1,_ladder_list);
            }
            if(param1.GetUserData().allowCover == true)
            {
               RemoveObject(param1,_static_covers);
            }
            if(param1.GetUserData().isCloud == true && param1.GetAngle() != 0)
            {
               RemoveObject(param1,_static_rotated_cloud_list);
            }
         }
      }
      
      public function SetPositionCorrection(param1:Boolean) : void
      {
         m_positionCorrection = param1;
      }
      
      public function get AimSolidList() : Array
      {
         return _aim_solid_list;
      }
      
      public function GetLaserSolidAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < LaserSolidList.length)
         {
            _loc3_ = LaserSolidList[_loc4_];
            if(_loc3_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function SetContactListener(param1:b2ContactListener) : void
      {
         m_contactListener = param1;
      }
      
      public function SetBoundaryListener(param1:b2BoundaryListener) : void
      {
         m_boundaryListener = param1;
      }
      
      public function GetStaticCoverAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < StaticCovers.length)
         {
            _loc3_ = StaticCovers[_loc4_];
            if(_loc3_.GetUserData().shapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function GetRotatedCloudAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:Array = null;
         var _loc4_:b2Body = null;
         var _loc5_:* = undefined;
         _loc3_ = _static_rotated_cloud_list;
         _loc5_ = 0;
         while(_loc5_ < _loc3_.length)
         {
            _loc4_ = _loc3_[_loc5_];
            if(_loc4_.GetUserData().shapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc4_;
            }
            _loc5_++;
         }
         return null;
      }
      
      public function GetJointCount() : int
      {
         return m_jointCount;
      }
      
      public function get LaserSolidList() : Array
      {
         return _laser_solid_list;
      }
      
      public function get FireCarrierList() : Array
      {
         return _fire_carrier_list;
      }
      
      public function Refilter(param1:b2Shape) : void
      {
         param1.RefilterProxy(m_broadPhase,param1.m_body.m_xf);
      }
      
      public function GetLadderBodyAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < _ladder_list.length)
         {
            _loc3_ = _ladder_list[_loc4_];
            if(_loc3_.GetUserData().shapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function get StairObjectList() : Array
      {
         return _stair_object_list;
      }
      
      public function SetContactFilter(param1:b2ContactFilter) : void
      {
         m_contactFilter = param1;
      }
      
      public function DrawDebugData() : void
      {
         var _loc1_:uint = 0;
         var _loc2_:int = 0;
         var _loc3_:b2Body = null;
         var _loc4_:b2Shape = null;
         var _loc5_:b2Joint = null;
         var _loc6_:b2BroadPhase = null;
         var _loc7_:b2Vec2 = null;
         var _loc8_:b2Vec2 = null;
         var _loc9_:b2Vec2 = null;
         var _loc10_:b2Color = null;
         var _loc11_:b2XForm = null;
         var _loc12_:b2AABB = null;
         var _loc13_:b2AABB = null;
         var _loc14_:Array = null;
         var _loc15_:* = false;
         if(m_debugDraw == null)
         {
            return;
         }
         m_debugDraw.m_sprite.graphics.clear();
         _loc1_ = m_debugDraw.GetFlags();
         _loc7_ = new b2Vec2();
         _loc8_ = new b2Vec2();
         _loc9_ = new b2Vec2();
         _loc10_ = new b2Color(0,0,0);
         _loc12_ = new b2AABB();
         _loc13_ = new b2AABB();
         _loc14_ = [new b2Vec2(),new b2Vec2(),new b2Vec2(),new b2Vec2()];
         if(_loc1_ & b2DebugDraw.e_shapeBit)
         {
            _loc15_ = (_loc1_ & b2DebugDraw.e_coreShapeBit) == b2DebugDraw.e_coreShapeBit;
            _loc3_ = m_bodyList;
            while(_loc3_)
            {
               _loc11_ = _loc3_.m_xf;
               _loc4_ = _loc3_.GetShapeList();
               while(_loc4_)
               {
                  if(_loc3_.IsStatic())
                  {
                     DrawShape(_loc4_,_loc11_,new b2Color(0,0,0),_loc15_);
                  }
                  _loc4_ = _loc4_.m_next;
               }
               _loc3_ = _loc3_.m_next;
            }
         }
      }
      
      public function AddObjectToLists(param1:b2Body) : void
      {
         if(param1.IsDynamic())
         {
            if(!param1.GetUserData().objectData.DrawShapeMC)
            {
               return;
            }
            _all_dynamic_object_list.push(param1);
            if(param1.GetUserData().isWeapon == true)
            {
               _weapon_list.push(param1);
            }
            else if(param1.GetUserData().isButton == true)
            {
               _button_list.push(param1);
            }
            else if(param1.GetUserData().isLadder == true)
            {
               _ladder_list.push(param1);
            }
            else
            {
               _dynamic_object_list.push(param1);
               if(!param1.GetUserData().objectData.BulletTransparent)
               {
                  _bullet_solid_list.push(param1);
               }
               if(!param1.GetUserData().objectData.LaserTransparent || Boolean(param1.GetUserData().objectData.LaserVisibleOnObject))
               {
                  _laser_solid_list.push(param1);
               }
               if(!param1.GetUserData().objectData.AimTransparent)
               {
                  _aim_solid_list.push(param1);
               }
               if(Boolean(param1.GetUserData().objectData.DrawHitBox) || Boolean(param1.GetUserData().objectData.DrawCloudBox))
               {
                  _dynamic_hitbox_object_list.push(param1);
               }
               if(param1.GetUserData().objectData.IsGlass)
               {
                  _is_glass_list.push(param1);
               }
               if(param1.GetUserData().objectData.CanBurn)
               {
                  _burn_object_list.push(param1);
               }
               else if(param1.GetUserData().objectData.ResistanceFire > 0)
               {
                  _can_take_fire_damage_list.push(param1);
               }
               if(param1.GetUserData().objectData.CanBeHazard)
               {
                  _hazards_list.push(param1);
               }
               if(param1.GetUserData().objectData.PartOfStaticWorld)
               {
                  _part_of_static_world.push(param1);
               }
               if(param1.GetUserData().objectData.CanCarryFire)
               {
                  _fire_carrier_list.push(param1);
               }
               if(param1.GetUserData().tiltValue != 0)
               {
                  _stair_object_list.push(param1);
               }
               if(param1.GetUserData().isMolotov == true)
               {
                  _molotov_list.push(param1);
               }
            }
         }
         else if(param1.GetUserData() != null)
         {
            _static_object_list.push(param1);
            if(param1.GetUserData().tiltValue != 0)
            {
               _stair_object_list.push(param1);
            }
            if(param1.GetUserData().isConveyorBelt == true)
            {
               _conveyor_list.push(param1);
            }
            if(param1.GetUserData().isLadder == true)
            {
               _ladder_list.push(param1);
            }
            if(param1.GetUserData().allowCover == true)
            {
               _static_covers.push(param1);
            }
            if(param1.GetUserData().isCloud == true && param1.GetAngle() != 0)
            {
               _static_rotated_cloud_list.push(param1);
            }
         }
      }
      
      public function get AllDynamicObjectList() : Array
      {
         return _all_dynamic_object_list;
      }
      
      public function DestroyBody(param1:b2Body) : void
      {
         var _loc2_:b2JointEdge = null;
         var _loc3_:b2Shape = null;
         var _loc4_:b2JointEdge = null;
         var _loc5_:b2Shape = null;
         if(m_lock == true)
         {
            return;
         }
         _loc2_ = param1.m_jointList;
         while(_loc2_)
         {
            _loc4_ = _loc2_;
            _loc2_ = _loc2_.next;
            if(m_destructionListener)
            {
               m_destructionListener.SayGoodbyeJoint(_loc4_.joint);
            }
            DestroyJoint(_loc4_.joint);
         }
         _loc3_ = param1.m_shapeList;
         while(_loc3_)
         {
            _loc5_ = _loc3_;
            _loc3_ = _loc3_.m_next;
            if(m_destructionListener)
            {
               m_destructionListener.SayGoodbyeShape(_loc5_);
            }
            _loc5_.DestroyProxy(m_broadPhase);
            b2Shape.Destroy(_loc5_,m_blockAllocator);
         }
         if(param1.m_prev)
         {
            param1.m_prev.m_next = param1.m_next;
         }
         if(param1.m_next)
         {
            param1.m_next.m_prev = param1.m_prev;
         }
         if(param1 == m_bodyList)
         {
            m_bodyList = param1.m_next;
         }
         --m_bodyCount;
      }
      
      public function DrawShape(param1:b2Shape, param2:b2XForm, param3:b2Color, param4:Boolean) : void
      {
         var _loc5_:b2Color = null;
         var _loc6_:b2CircleShape = null;
         var _loc7_:b2Vec2 = null;
         var _loc8_:Number = NaN;
         var _loc9_:b2Vec2 = null;
         var _loc10_:int = 0;
         var _loc11_:b2PolygonShape = null;
         var _loc12_:int = 0;
         var _loc13_:Array = null;
         var _loc14_:Array = null;
         var _loc15_:Array = null;
         _loc5_ = s_coreColor;
         switch(param1.m_type)
         {
            case b2Shape.e_circleShape:
               _loc6_ = param1 as b2CircleShape;
               _loc7_ = b2Math.b2MulX(param2,_loc6_.m_localPosition);
               _loc8_ = _loc6_.m_radius;
               _loc9_ = param2.R.col1;
               m_debugDraw.DrawSolidCircle(_loc7_,_loc8_,_loc9_,param3);
               if(param4)
               {
                  m_debugDraw.DrawCircle(_loc7_,_loc8_ - b2Settings.b2_toiSlop,_loc5_);
               }
               break;
            case b2Shape.e_polygonShape:
               _loc11_ = param1 as b2PolygonShape;
               _loc12_ = _loc11_.GetVertexCount();
               _loc13_ = _loc11_.GetVertices();
               _loc14_ = new Array(b2Settings.b2_maxPolygonVertices);
               _loc10_ = 0;
               while(_loc10_ < _loc12_)
               {
                  _loc14_[_loc10_] = b2Math.b2MulX(param2,_loc13_[_loc10_]);
                  _loc10_++;
               }
               m_debugDraw.DrawSolidPolygon(_loc14_,_loc12_,param3);
               if(param4)
               {
                  _loc15_ = _loc11_.GetCoreVertices();
                  _loc10_ = 0;
                  while(_loc10_ < _loc12_)
                  {
                     _loc14_[_loc10_] = b2Math.b2MulX(param2,_loc15_[_loc10_]);
                     _loc10_++;
                  }
                  m_debugDraw.DrawPolygon(_loc14_,_loc12_,_loc5_);
               }
         }
      }
      
      public function DrawJoint(param1:b2Joint) : void
      {
         var _loc2_:b2Body = null;
         var _loc3_:b2Body = null;
         var _loc4_:b2XForm = null;
         var _loc5_:b2XForm = null;
         var _loc6_:b2Vec2 = null;
         var _loc7_:b2Vec2 = null;
         var _loc8_:b2Vec2 = null;
         var _loc9_:b2Vec2 = null;
         var _loc10_:b2Color = null;
         var _loc11_:b2PulleyJoint = null;
         var _loc12_:b2Vec2 = null;
         var _loc13_:b2Vec2 = null;
         _loc2_ = param1.m_body1;
         _loc3_ = param1.m_body2;
         _loc4_ = _loc2_.m_xf;
         _loc5_ = _loc3_.m_xf;
         _loc6_ = _loc4_.position;
         _loc7_ = _loc5_.position;
         _loc8_ = param1.GetAnchor1();
         _loc9_ = param1.GetAnchor2();
         _loc10_ = s_jointColor;
         switch(param1.m_type)
         {
            case b2Joint.e_distanceJoint:
               m_debugDraw.DrawSegment(_loc8_,_loc9_,_loc10_);
               break;
            case b2Joint.e_pulleyJoint:
               _loc11_ = param1 as b2PulleyJoint;
               _loc12_ = _loc11_.GetGroundAnchor1();
               _loc13_ = _loc11_.GetGroundAnchor2();
               m_debugDraw.DrawSegment(_loc12_,_loc8_,_loc10_);
               m_debugDraw.DrawSegment(_loc13_,_loc9_,_loc10_);
               m_debugDraw.DrawSegment(_loc12_,_loc13_,_loc10_);
               break;
            case b2Joint.e_mouseJoint:
               m_debugDraw.DrawSegment(_loc8_,_loc9_,_loc10_);
               break;
            default:
               if(_loc2_ != m_groundBody)
               {
                  m_debugDraw.DrawSegment(_loc6_,_loc8_,_loc10_);
               }
               m_debugDraw.DrawSegment(_loc8_,_loc9_,_loc10_);
               if(_loc3_ != m_groundBody)
               {
                  m_debugDraw.DrawSegment(_loc7_,_loc9_,_loc10_);
               }
         }
      }
      
      public function GetGroundBody() : b2Body
      {
         return m_groundBody;
      }
      
      public function ResetLists() : void
      {
         _dynamic_hitbox_object_list = new Array();
         _dynamic_object_list = new Array();
         _all_dynamic_object_list = new Array();
         _static_object_list = new Array();
         _stair_object_list = new Array();
         _conveyor_list = new Array();
         _weapon_list = new Array();
         _button_list = new Array();
         _ladder_list = new Array();
         _burn_object_list = new Array();
         _fire_carrier_list = new Array();
         _bullet_solid_list = new Array();
         _aim_solid_list = new Array();
         _laser_solid_list = new Array();
         _molotov_list = new Array();
         _can_take_fire_damage_list = new Array();
         _static_covers = new Array();
         _hazards_list = new Array();
         _static_rotated_cloud_list = new Array();
         _is_glass_list = new Array();
         _part_of_static_world = new Array();
      }
      
      public function Query(param1:b2AABB, param2:Array, param3:int) : int
      {
         var _loc4_:Array = null;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         _loc4_ = new Array(param3);
         _loc5_ = m_broadPhase.QueryAABB(param1,_loc4_,param3);
         _loc6_ = 0;
         while(_loc6_ < _loc5_)
         {
            param2[_loc6_] = _loc4_[_loc6_];
            _loc6_++;
         }
         return _loc5_;
      }
      
      public function get StaticObjectList() : Array
      {
         return _static_object_list;
      }
      
      public function SolveTOI(param1:b2TimeStep) : void
      {
         var _loc2_:b2Body = null;
         var _loc3_:b2Shape = null;
         var _loc4_:b2Shape = null;
         var _loc5_:b2Body = null;
         var _loc6_:b2Body = null;
         var _loc7_:b2ContactEdge = null;
         var _loc8_:b2Island = null;
         var _loc9_:int = 0;
         var _loc10_:Array = null;
         var _loc11_:b2Contact = null;
         var _loc12_:b2Contact = null;
         var _loc13_:Number = NaN;
         var _loc14_:b2Body = null;
         var _loc15_:int = 0;
         var _loc16_:b2TimeStep = null;
         var _loc17_:int = 0;
         var _loc18_:Number = NaN;
         var _loc19_:Number = NaN;
         var _loc20_:b2Body = null;
         var _loc21_:Boolean = false;
         _loc8_ = new b2Island(m_bodyCount,b2Settings.b2_maxTOIContactsPerIsland,0,m_stackAllocator,m_contactListener,FallAsleepBody);
         _loc9_ = m_bodyCount;
         _loc10_ = new Array(_loc9_);
         _loc2_ = m_bodyList;
         while(_loc2_)
         {
            _loc2_.m_flags &= ~b2Body.e_islandFlag;
            _loc2_.m_sweep.t0 = 0;
            _loc2_ = _loc2_.m_next;
         }
         _loc11_ = m_contactList;
         while(_loc11_)
         {
            _loc11_.m_flags &= ~(b2Contact.e_toiFlag | b2Contact.e_islandFlag);
            _loc11_ = _loc11_.m_next;
         }
         while(true)
         {
            _loc12_ = null;
            _loc13_ = 1;
            _loc11_ = m_contactList;
            for(; _loc11_; _loc11_ = _loc11_.m_next)
            {
               if(!(_loc11_.m_flags & (b2Contact.e_slowFlag | b2Contact.e_nonSolidFlag)))
               {
                  _loc18_ = 1;
                  if(_loc11_.m_flags & b2Contact.e_toiFlag)
                  {
                     _loc18_ = _loc11_.m_toi;
                  }
                  else
                  {
                     _loc3_ = _loc11_.m_shape1;
                     _loc4_ = _loc11_.m_shape2;
                     _loc5_ = _loc3_.m_body;
                     _loc6_ = _loc4_.m_body;
                     if((_loc5_.IsStatic() || _loc5_.IsSleeping()) && (_loc6_.IsStatic() || _loc6_.IsSleeping()))
                     {
                        continue;
                     }
                     _loc19_ = _loc5_.m_sweep.t0;
                     if(_loc5_.m_sweep.t0 < _loc6_.m_sweep.t0)
                     {
                        _loc19_ = _loc6_.m_sweep.t0;
                        _loc5_.m_sweep.Advance(_loc19_);
                     }
                     else if(_loc6_.m_sweep.t0 < _loc5_.m_sweep.t0)
                     {
                        _loc19_ = _loc5_.m_sweep.t0;
                        _loc6_.m_sweep.Advance(_loc19_);
                     }
                     _loc18_ = b2TimeOfImpact.TimeOfImpact(_loc11_.m_shape1,_loc5_.m_sweep,_loc11_.m_shape2,_loc6_.m_sweep);
                     if(_loc18_ > 0 && _loc18_ < 1)
                     {
                        _loc18_ = (1 - _loc18_) * _loc19_ + _loc18_;
                        if(_loc18_ > 1)
                        {
                           _loc18_ = 1;
                        }
                     }
                     _loc11_.m_toi = _loc18_;
                     _loc11_.m_flags |= b2Contact.e_toiFlag;
                  }
                  if(Number.MIN_VALUE < _loc18_ && _loc18_ < _loc13_)
                  {
                     _loc12_ = _loc11_;
                     _loc13_ = _loc18_;
                  }
               }
            }
            if(_loc12_ == null || 1 - 100 * Number.MIN_VALUE < _loc13_)
            {
               break;
            }
            _loc3_ = _loc12_.m_shape1;
            _loc4_ = _loc12_.m_shape2;
            _loc5_ = _loc3_.m_body;
            _loc6_ = _loc4_.m_body;
            _loc5_.Advance(_loc13_);
            _loc6_.Advance(_loc13_);
            _loc12_.Update(m_contactListener);
            _loc12_.m_flags &= ~b2Contact.e_toiFlag;
            if(_loc12_.m_manifoldCount != 0)
            {
               _loc14_ = _loc5_;
               if(_loc14_.IsStatic())
               {
                  _loc14_ = _loc6_;
               }
               _loc8_.Clear();
               _loc15_ = 0;
               var _loc22_:*;
               _loc10_[_loc22_ = _loc15_++] = _loc14_;
               _loc14_.m_flags |= b2Body.e_islandFlag;
               while(_loc15_ > 0)
               {
                  _loc2_ = _loc10_[--_loc15_];
                  _loc8_.AddBody(_loc2_);
                  _loc2_.m_flags &= ~b2Body.e_sleepFlag;
                  if(!_loc2_.IsStatic())
                  {
                     _loc7_ = _loc2_.m_contactList;
                     while(_loc7_)
                     {
                        if(_loc8_.m_contactCount != _loc8_.m_contactCapacity)
                        {
                           if(!(_loc7_.contact.m_flags & (b2Contact.e_islandFlag | b2Contact.e_slowFlag | b2Contact.e_nonSolidFlag)))
                           {
                              if(_loc7_.contact.m_manifoldCount != 0)
                              {
                                 _loc8_.AddContact(_loc7_.contact);
                                 _loc7_.contact.m_flags |= b2Contact.e_islandFlag;
                                 _loc20_ = _loc7_.other;
                                 if(!(_loc20_.m_flags & b2Body.e_islandFlag))
                                 {
                                    if(_loc20_.IsStatic() == false)
                                    {
                                       _loc20_.Advance(_loc13_);
                                       _loc20_.WakeUp();
                                    }
                                    var _loc23_:*;
                                    _loc10_[_loc23_ = _loc15_++] = _loc20_;
                                    _loc20_.m_flags |= b2Body.e_islandFlag;
                                 }
                              }
                           }
                        }
                        _loc7_ = _loc7_.next;
                     }
                  }
               }
               (_loc16_ = new b2TimeStep()).dt = (1 - _loc13_) * param1.dt;
               _loc16_.inv_dt = 1 / _loc16_.dt;
               _loc16_.maxIterations = param1.maxIterations;
               _loc8_.SolveTOI(_loc16_);
               _loc17_ = 0;
               while(_loc17_ < _loc8_.m_bodyCount)
               {
                  _loc2_ = _loc8_.m_bodies[_loc17_];
                  _loc2_.m_flags &= ~b2Body.e_islandFlag;
                  if(!(_loc2_.m_flags & (b2Body.e_sleepFlag | b2Body.e_frozenFlag)))
                  {
                     if(!_loc2_.IsStatic())
                     {
                        _loc21_ = _loc2_.SynchronizeShapes();
                        if(_loc21_ == false && m_boundaryListener != null)
                        {
                           m_boundaryListener.Violation(_loc2_);
                        }
                        _loc7_ = _loc2_.m_contactList;
                        while(_loc7_)
                        {
                           _loc7_.contact.m_flags &= ~b2Contact.e_toiFlag;
                           _loc7_ = _loc7_.next;
                        }
                     }
                  }
                  _loc17_++;
               }
               _loc17_ = 0;
               while(_loc17_ < _loc8_.m_contactCount)
               {
                  _loc11_ = _loc8_.m_contacts[_loc17_];
                  _loc11_.m_flags &= ~(b2Contact.e_toiFlag | b2Contact.e_islandFlag);
                  _loc17_++;
               }
               m_broadPhase.Commit();
            }
         }
      }
      
      public function GetJointList() : b2Joint
      {
         return m_jointList;
      }
      
      public function SetGravity(param1:b2Vec2) : void
      {
         m_gravity = param1;
      }
      
      public function GetBodyList() : b2Body
      {
         return m_bodyList;
      }
      
      public function GetGlassAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:Array = null;
         var _loc4_:b2Body = null;
         var _loc5_:* = undefined;
         _loc3_ = _is_glass_list;
         _loc5_ = 0;
         while(_loc5_ < _loc3_.length)
         {
            _loc4_ = _loc3_[_loc5_];
            if(_loc4_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc4_;
            }
            _loc5_++;
         }
         return null;
      }
      
      public function get CanTakeFireDamageList() : Array
      {
         return _can_take_fire_damage_list;
      }
      
      public function GetPairCount() : int
      {
         return m_broadPhase.m_pairManager.m_pairCount;
      }
      
      public function get HazardsList() : Array
      {
         return _hazards_list;
      }
      
      public function get StaticRotatedCloudList() : Array
      {
         return _static_rotated_cloud_list;
      }
      
      public function get StaticCovers() : Array
      {
         return _static_covers;
      }
      
      public function CreateJoint(param1:b2JointDef) : b2Joint
      {
         var _loc2_:b2Joint = null;
         var _loc3_:b2Body = null;
         var _loc4_:b2Shape = null;
         _loc2_ = b2Joint.Create(param1,m_blockAllocator);
         _loc2_.m_prev = null;
         _loc2_.m_next = m_jointList;
         if(m_jointList)
         {
            m_jointList.m_prev = _loc2_;
         }
         m_jointList = _loc2_;
         ++m_jointCount;
         _loc2_.m_node1.joint = _loc2_;
         _loc2_.m_node1.other = _loc2_.m_body2;
         _loc2_.m_node1.prev = null;
         _loc2_.m_node1.next = _loc2_.m_body1.m_jointList;
         if(_loc2_.m_body1.m_jointList)
         {
            _loc2_.m_body1.m_jointList.prev = _loc2_.m_node1;
         }
         _loc2_.m_body1.m_jointList = _loc2_.m_node1;
         _loc2_.m_node2.joint = _loc2_;
         _loc2_.m_node2.other = _loc2_.m_body1;
         _loc2_.m_node2.prev = null;
         _loc2_.m_node2.next = _loc2_.m_body2.m_jointList;
         if(_loc2_.m_body2.m_jointList)
         {
            _loc2_.m_body2.m_jointList.prev = _loc2_.m_node2;
         }
         _loc2_.m_body2.m_jointList = _loc2_.m_node2;
         if(param1.collideConnected == false)
         {
            _loc3_ = param1.body1.m_shapeCount < param1.body2.m_shapeCount ? param1.body1 : param1.body2;
            _loc4_ = _loc3_.m_shapeList;
            while(_loc4_)
            {
               _loc4_.RefilterProxy(m_broadPhase,_loc3_.m_xf);
               _loc4_ = _loc4_.m_next;
            }
         }
         return _loc2_;
      }
      
      public function DestroyJoint(param1:b2Joint) : void
      {
         var _loc2_:Boolean = false;
         var _loc3_:b2Body = null;
         var _loc4_:b2Body = null;
         var _loc5_:b2Body = null;
         var _loc6_:b2Shape = null;
         _loc2_ = param1.m_collideConnected;
         if(param1.m_prev)
         {
            param1.m_prev.m_next = param1.m_next;
         }
         if(param1.m_next)
         {
            param1.m_next.m_prev = param1.m_prev;
         }
         if(param1 == m_jointList)
         {
            m_jointList = param1.m_next;
         }
         _loc3_ = param1.m_body1;
         _loc4_ = param1.m_body2;
         _loc3_.WakeUp();
         _loc4_.WakeUp();
         if(param1.m_node1.prev)
         {
            param1.m_node1.prev.next = param1.m_node1.next;
         }
         if(param1.m_node1.next)
         {
            param1.m_node1.next.prev = param1.m_node1.prev;
         }
         if(param1.m_node1 == _loc3_.m_jointList)
         {
            _loc3_.m_jointList = param1.m_node1.next;
         }
         param1.m_node1.prev = null;
         param1.m_node1.next = null;
         if(param1.m_node2.prev)
         {
            param1.m_node2.prev.next = param1.m_node2.next;
         }
         if(param1.m_node2.next)
         {
            param1.m_node2.next.prev = param1.m_node2.prev;
         }
         if(param1.m_node2 == _loc4_.m_jointList)
         {
            _loc4_.m_jointList = param1.m_node2.next;
         }
         param1.m_node2.prev = null;
         param1.m_node2.next = null;
         b2Joint.Destroy(param1,m_blockAllocator);
         --m_jointCount;
         if(_loc2_ == false)
         {
            _loc5_ = _loc3_.m_shapeCount < _loc4_.m_shapeCount ? _loc3_ : _loc4_;
            _loc6_ = _loc5_.m_shapeList;
            while(_loc6_)
            {
               _loc6_.RefilterProxy(m_broadPhase,_loc5_.m_xf);
               _loc6_ = _loc6_.m_next;
            }
         }
      }
      
      public function get BurnObjectList() : Array
      {
         return _burn_object_list;
      }
      
      public function GetStaticBodyAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:b2Body = null;
         var _loc4_:* = undefined;
         _loc4_ = 0;
         while(_loc4_ < _static_object_list.length)
         {
            _loc3_ = _static_object_list[_loc4_];
            if(_loc3_.GetUserData().shapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc3_;
            }
            _loc4_++;
         }
         return null;
      }
      
      public function GetPartWorldAt(param1:Number, param2:Number) : b2Body
      {
         var _loc3_:Array = null;
         var _loc4_:b2Body = null;
         var _loc5_:* = undefined;
         _loc3_ = _part_of_static_world;
         _loc5_ = 0;
         while(_loc5_ < _loc3_.length)
         {
            _loc4_ = _loc3_[_loc5_];
            if(_loc4_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc4_;
            }
            _loc5_++;
         }
         return null;
      }
      
      public function SetDestructionListener(param1:b2DestructionListener) : void
      {
         m_destructionListener = param1;
      }
      
      public function CreateBody(param1:b2BodyDef) : b2Body
      {
         var _loc2_:b2Body = null;
         if(m_lock == true)
         {
            return null;
         }
         _loc2_ = new b2Body(param1,this);
         _loc2_.m_prev = null;
         _loc2_.m_next = m_bodyList;
         if(m_bodyList)
         {
            m_bodyList.m_prev = _loc2_;
         }
         m_bodyList = _loc2_;
         ++m_bodyCount;
         return _loc2_;
      }
      
      public function get BulletSolidList() : Array
      {
         return _bullet_solid_list;
      }
      
      public function Step(param1:Number, param2:int) : void
      {
         var _loc3_:b2TimeStep = null;
         m_lock = true;
         _loc3_ = new b2TimeStep();
         _loc3_.dt = param1;
         _loc3_.maxIterations = param2;
         if(param1 > 0)
         {
            _loc3_.inv_dt = 1 / param1;
         }
         else
         {
            _loc3_.inv_dt = 0;
         }
         _loc3_.dtRatio = m_inv_dt0 * param1;
         _loc3_.positionCorrection = m_positionCorrection;
         _loc3_.warmStarting = m_warmStarting;
         m_contactManager.Collide();
         if(_loc3_.dt > 0)
         {
            Solve(_loc3_);
         }
         if(m_continuousPhysics && _loc3_.dt > 0)
         {
            SolveTOI(_loc3_);
         }
         m_inv_dt0 = _loc3_.inv_dt;
         m_lock = false;
      }
      
      public function UpdateObjectLists() : void
      {
         var _loc1_:b2Body = null;
         ResetLists();
         _loc1_ = m_bodyList;
         while(_loc1_)
         {
            AddObjectToLists(_loc1_);
            _loc1_ = _loc1_.m_next;
         }
      }
      
      public function GetBodyCount() : int
      {
         return m_bodyCount;
      }
      
      public function get WeaponList() : Array
      {
         return _weapon_list;
      }
      
      public function get DynamicObjectList() : Array
      {
         return _dynamic_object_list;
      }
      
      public function GetDynamicBodyAt(param1:Number, param2:Number, param3:Boolean) : b2Body
      {
         var _loc4_:Array = null;
         var _loc5_:b2Body = null;
         var _loc6_:* = undefined;
         if(param3)
         {
            _loc4_ = DynamicObjectList;
         }
         else
         {
            _loc4_ = DynamicHitBoxObjectList;
         }
         _loc6_ = 0;
         while(_loc6_ < _loc4_.length)
         {
            _loc5_ = _loc4_[_loc6_];
            if(_loc5_.GetUserData().objectData.ShapeMC.hitTestPoint(param1,param2,true))
            {
               return _loc5_;
            }
            _loc6_++;
         }
         return null;
      }
   }
}

