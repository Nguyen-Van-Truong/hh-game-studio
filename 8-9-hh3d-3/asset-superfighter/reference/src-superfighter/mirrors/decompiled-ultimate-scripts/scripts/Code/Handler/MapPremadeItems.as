package Code.Handler
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Box2D.Dynamics.Contacts.*;
   import Code.Box2D.Dynamics.Joints.*;
   import Code.Data.BodyData;
   import Code.Data.BodyDataExplosiveBarrel;
   import Code.Data.ButtonData;
   import Code.Data.MaterialData;
   import Code.Data.MaterialsData;
   import Code.Data.Players.PlayerCharacter;
   import Code.Data.Rope;
   import Code.Particles.particle_data;
   import fl.motion.Color;
   import flash.display.MovieClip;
   import flash.geom.Point;
   
   public class MapPremadeItems
   {
      private var _material:MaterialsData;
      
      private var _static_mc:MovieClip;
      
      private var _Handler_Fires:Fires;
      
      private var _Handler_Effects:Effects;
      
      private var _queue:Array;
      
      private var _weapon_mc:MovieClip;
      
      private var _scrap_mc:MovieClip;
      
      private var _ground:b2Body;
      
      private var _locked:Boolean = false;
      
      private var _debrisFadeFunction:Function;
      
      private var _Handler_Deconstructer:Deconstructer;
      
      private var _dynamic_mc:MovieClip;
      
      private var _Handler_Sounds:Sounds;
      
      private var _static_world_hitbox_mc:MovieClip;
      
      private var m_world:b2World;
      
      private var _static_objects_hitbox_mc:MovieClip;
      
      private var _objects_mc:MovieClip;
      
      private var _nullUpdateFunction:Function;
      
      private var _idGiver:int = 0;
      
      private var _static_ladder_hitbox_mc:MovieClip;
      
      private var _object_shape_container_mc:MovieClip;
      
      private var _static_world_cloud_hitbox_mc:MovieClip;
      
      private var _Handler_Output:OutputTrace;
      
      private var _static_objects_cloud_hitbox_mc:MovieClip;
      
      private var _Handler_Explosions:Explosions;
      
      private var _debrisUpdateFunction:Function;
      
      private var _Handler_BasicOverlays:BasicOverlays;
      
      public function MapPremadeItems(param1:OutputTrace)
      {
         _material = new MaterialsData();
         _locked = false;
         _queue = new Array();
         _idGiver = 0;
         _debrisUpdateFunction = function(param1:b2Body, param2:Number):void
         {
            if(param1.GetUserData().objectData.ObjectTimer == 0)
            {
               param1.GetUserData().objectData.ObjectTimer = 5;
            }
            else
            {
               param1.GetUserData().objectData.ObjectTimer = param1.GetUserData().objectData.ObjectTimer - param2;
               if(param1.GetUserData().objectData.ObjectTimer <= 0)
               {
                  param1.GetUserData().objectData.BulletTransparent = false;
                  m_world.RemoveObjectFromLists(param1);
                  m_world.AddObjectToLists(param1);
                  param1.GetUserData().objectData.UpdateFunction = _debrisFadeFunction;
               }
            }
         };
         _debrisFadeFunction = function(param1:b2Body, param2:Number):void
         {
            param1.GetUserData().objectData.ObjectTimer = param1.GetUserData().objectData.ObjectTimer + param2;
            if(param1.GetUserData().objectData.ObjectTimer >= 240)
            {
               param1.GetUserData().alpha = 1 - (param1.GetUserData().objectData.ObjectTimer - 240) / 50;
               if(param1.GetUserData().objectData.ObjectTimer >= 290)
               {
                  param1.GetUserData().objectData.ForceDestruction();
               }
            }
         };
         _nullUpdateFunction = function(param1:b2Body, param2:Number):void
         {
         };
         super();
         _Handler_Output = param1;
         _Handler_Output.Trace("Premade Items Created");
      }
      
      public function CreateGroundCircle(param1:MaterialData, param2:Number, param3:Number, param4:Number, param5:Array = null) : b2Body
      {
         var _loc6_:b2Body = null;
         var _loc7_:b2BodyDef = null;
         var _loc8_:b2CircleDef = null;
         param4 += 0.5 / 30;
         _loc7_ = new b2BodyDef();
         _loc7_.position.Set(param2,param3);
         _loc7_.userData = new Object();
         _loc7_.userData.IDNumber = GenerateID();
         _loc7_.userData.material = param1;
         _loc7_.userData.tiltValue = 0;
         _loc7_.userData.allowCover = false;
         if(param5 == null)
         {
            _loc7_.userData.shapeMC = DrawCircleMC(param4 * 30,16711935);
         }
         else if(param5[0] == "CLOUD")
         {
            _loc7_.userData.shapeMC = DrawCircleMC(param4 * 30,16711782);
         }
         else if(param5[0] == "LADDER")
         {
            _loc7_.userData.shapeMC = DrawCircleMC(param4 * 30,16737894);
         }
         else
         {
            _loc7_.userData.shapeMC = DrawCircleMC(param4 * 30,16711935);
            param5 = null;
         }
         _loc7_.userData.shapeMC.x = param2 * 30;
         _loc7_.userData.shapeMC.y = param3 * 30;
         (_loc8_ = new b2CircleDef()).radius = param4;
         _loc8_.friction = _loc7_.userData.material.Friction;
         _loc8_.restitution = _loc7_.userData.material.Restitution;
         _loc8_.density = 0;
         if(param5 != null)
         {
            if(param5[0] == "LADDER")
            {
               _loc8_.filter.categoryBits = 2;
               _loc8_.filter.maskBits = 1;
               _loc7_.userData.isLadder = true;
            }
            if(param5[0] == "CLOUD")
            {
               _loc8_.filter.isCloud = true;
               _loc8_.userData.isCloud = true;
            }
         }
         _loc6_ = m_world.CreateBody(_loc7_);
         _loc6_.CreateShape(_loc8_);
         _loc6_.SetMassFromShapes();
         _loc6_.SetUserData(_loc7_.userData);
         if(param5 == null)
         {
            _static_world_hitbox_mc.addChild(_loc6_.GetUserData().shapeMC);
         }
         else if(param5[0] == "CLOUD")
         {
            _static_world_cloud_hitbox_mc.addChild(_loc6_.GetUserData().shapeMC);
         }
         else if(param5[0] == "LADDER")
         {
            _static_ladder_hitbox_mc.addChild(_loc6_.GetUserData().shapeMC);
         }
         return _loc6_;
      }
      
      private function IncreaseCorners(param1:Array) : Array
      {
         var _loc2_:* = undefined;
         _loc2_ = 0;
         while(_loc2_ < param1.length)
         {
            if(param1[_loc2_][0] < 0)
            {
               param1[_loc2_][0] -= 0.5 / 30;
            }
            else if(param1[_loc2_][0] > 0)
            {
               param1[_loc2_][0] += 0.5 / 30;
            }
            if(param1[_loc2_][1] < 0)
            {
               param1[_loc2_][1] -= 0.5 / 30;
            }
            else if(param1[_loc2_][1] > 0)
            {
               param1[_loc2_][1] += 0.5 / 30;
            }
            _loc2_++;
         }
         return param1;
      }
      
      public function UpdateHandlers(param1:Effects, param2:Explosions, param3:Sounds, param4:BasicOverlays) : void
      {
         _Handler_Effects = param1;
         _Handler_Explosions = param2;
         _Handler_Sounds = param3;
         _Handler_BasicOverlays = param4;
      }
      
      public function LinkToFire(param1:Fires) : void
      {
         _Handler_Fires = param1;
      }
      
      public function Unlock() : void
      {
         var _loc1_:int = 0;
         _locked = false;
         if(_queue.length > 0)
         {
            _loc1_ = 0;
            while(_loc1_ < _queue.length)
            {
               if(_queue[0] == "B")
               {
                  AddBox(_queue[1],_queue[2],_queue[3],_queue[4],_queue[5],_queue[6],_queue[7]);
               }
               else if(_queue[0] == "C")
               {
                  AddCircle(_queue[1],_queue[2],_queue[3],_queue[4],_queue[5],_queue[6],_queue[7]);
               }
               else if(_queue[0] == "P")
               {
                  AddPolygon(_queue[1],_queue[2],_queue[3],_queue[4],_queue[5],_queue[6],_queue[7]);
               }
               _loc1_++;
            }
            _queue = new Array();
         }
      }
      
      public function AddGlass(param1:Point, param2:Point) : b2Body
      {
         var _loc3_:Point = null;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:b2Body = null;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:MovieClip = null;
         _loc3_ = new Point(param1.x + (param2.x - param1.x) * 0.5,param1.y + (param2.y - param1.y) * 0.5);
         _loc4_ = Math.sqrt(Math.pow(param2.x - param1.x,2) + Math.pow(param2.y - param1.y,2));
         _loc4_ = _loc4_ * 30;
         _loc5_ = Math.atan2(param2.y - param1.y,param2.x - param1.x);
         _loc6_ = AddBox("SOLID_GLASS_01",_loc3_.x,_loc3_.y,_loc5_,new b2Vec2(),0,[_loc4_,3]);
         _loc7_ = _loc4_ / 2 % 6 / 2;
         _loc8_ = -_loc4_ / 2;
         while(_loc8_ < _loc4_ / 2 - 6)
         {
            (_loc9_ = new window_seg()).x = _loc8_ + _loc7_;
            _loc9_.rotation = 90;
            _loc6_.GetUserData().addChild(_loc9_);
            _loc8_ += 6;
         }
         AddRevoluteJoint(Ground,_loc6_,new b2Vec2(param1.x,param1.y));
         AddRevoluteJoint(Ground,_loc6_,new b2Vec2(param2.x,param2.y));
         return _loc6_;
      }
      
      public function UpdateMCs(param1:MovieClip, param2:MovieClip, param3:MovieClip) : void
      {
         _static_mc = param1;
         _dynamic_mc = param2;
         _object_shape_container_mc = param3;
         _objects_mc = MovieClip(_dynamic_mc.getChildByName("OBJECTS"));
         _scrap_mc = MovieClip(_dynamic_mc.getChildByName("SCRAP"));
         _weapon_mc = MovieClip(_dynamic_mc.getChildByName("WEAPONS"));
         _static_ladder_hitbox_mc = MovieClip(_static_mc.getChildByName("LADDER_HITBOX"));
         _static_world_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_HITBOX"));
         _static_world_cloud_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_CLOUD_HITBOX"));
         _static_objects_cloud_hitbox_mc = MovieClip(_static_world_cloud_hitbox_mc.getChildByName("OBJECTS_CLOUD_HITBOX"));
         _static_objects_hitbox_mc = MovieClip(_static_world_hitbox_mc.getChildByName("OBJECTS_HITBOX"));
      }
      
      public function CreateGroundBox(param1:MaterialData, param2:Number, param3:Number, param4:Number, param5:Number, param6:Number, param7:Array = null) : b2Body
      {
         var _loc8_:b2Body = null;
         var _loc9_:b2BodyDef = null;
         var _loc10_:b2PolygonDef = null;
         param5 += 0.5 / 30;
         param6 += 0.5 / 30;
         _loc9_ = new b2BodyDef();
         _loc9_.position.Set(param2,param3);
         _loc9_.angle = param4;
         _loc9_.userData = new Object();
         _loc9_.userData.IDNumber = GenerateID();
         _loc9_.userData.material = param1;
         _loc9_.userData.tiltValue = 0;
         _loc9_.userData.allowCover = false;
         if(param7 == null)
         {
            _loc9_.userData.shapeMC = DrawBoxMC(param5 * 30,param6 * 30,16711935);
         }
         else if(param7[0] == "CLOUD")
         {
            _loc9_.userData.shapeMC = DrawBoxMC(param5 * 30,param6 * 30,16711782);
         }
         else if(param7[0] == "LADDER")
         {
            _loc9_.userData.shapeMC = DrawBoxMC(param5 * 30,param6 * 30,16737894);
         }
         else
         {
            _loc9_.userData.shapeMC = DrawBoxMC(param5 * 30,param6 * 30,16711935);
            param7 = null;
         }
         _loc9_.userData.shapeMC.x = param2 * 30;
         _loc9_.userData.shapeMC.y = param3 * 30;
         _loc9_.userData.shapeMC.rotation = param4 * (180 / Math.PI);
         _loc10_ = new b2PolygonDef();
         _loc10_.SetAsBox(param5 / 2,param6 / 2);
         _loc10_.friction = _loc9_.userData.material.Friction;
         _loc10_.restitution = _loc9_.userData.material.Restitution;
         _loc10_.density = 0;
         if(param7 != null)
         {
            if(param7[0] == "LADDER")
            {
               _loc10_.filter.categoryBits = 2;
               _loc10_.filter.maskBits = 1;
               _loc9_.userData.isLadder = true;
            }
            if(param7[0] == "CLOUD")
            {
               _loc10_.filter.isCloud = true;
               _loc9_.userData.isCloud = true;
            }
         }
         _loc8_ = m_world.CreateBody(_loc9_);
         _loc8_.CreateShape(_loc10_);
         _loc8_.SetMassFromShapes();
         _loc8_.SetUserData(_loc9_.userData);
         if(param7 == null)
         {
            _static_world_hitbox_mc.addChild(_loc8_.GetUserData().shapeMC);
         }
         else if(param7[0] == "CLOUD")
         {
            _static_world_cloud_hitbox_mc.addChild(_loc8_.GetUserData().shapeMC);
         }
         else if(param7[0] == "LADDER")
         {
            _static_ladder_hitbox_mc.addChild(_loc8_.GetUserData().shapeMC);
         }
         return _loc8_;
      }
      
      public function AddPolygon(param1:String, param2:Number, param3:Number, param4:Number, param5:b2Vec2, param6:Number, param7:Array = null, param8:Boolean = false) : b2Body
      {
         var addGrenadeIndicator:Boolean = false;
         var tmp_mc:MovieClip = null;
         var body:b2Body = null;
         var bodyDef:b2BodyDef = null;
         var boxDef:b2PolygonDef = null;
         var corners:Array = null;
         var shapeScale:Number = NaN;
         var i:* = undefined;
         var isRanged:Boolean = false;
         var isMelee:Boolean = false;
         var isThrowable:Boolean = false;
         var isPowerup:Boolean = false;
         var isHealth:Boolean = false;
         var color:Color = null;
         var type:String = param1;
         var PosX:Number = param2;
         var PosY:Number = param3;
         var Angle:Number = param4;
         var Velocity:b2Vec2 = param5;
         var AngularVelocity:Number = param6;
         var optionalValues:Array = param7;
         var reversed:Boolean = param8;
         if(_locked)
         {
            _queue.push("P",type,PosX,PosY,Angle,Velocity,AngularVelocity,optionalValues);
            return null;
         }
         addGrenadeIndicator = false;
         boxDef = new b2PolygonDef();
         bodyDef = new b2BodyDef();
         bodyDef.position.Set(PosX,PosY);
         bodyDef.angle = Angle;
         shapeScale = 1;
         switch(type.toUpperCase())
         {
            case "WPN_SWORD":
            case "WPN_AXE":
            case "WPN_SLOWMO_05":
            case "WPN_SLOWMO_10":
            case "WPN_PILLS":
            case "WPN_MEDKIT":
            case "WPN_MACHETE":
            case "WPN_GRENADES":
            case "WPN_MOLOTOVS":
            case "WPN_SNIPER":
            case "WPN_MAGNUM":
            case "WPN_SHOTGUN":
            case "WPN_RIFLE":
            case "WPN_UZI":
            case "WPN_BAZOOKA":
            case "WPN_FLAMETHROWER":
            case "WPN_PISTOL":
               isRanged = false;
               isMelee = false;
               isThrowable = false;
               isPowerup = false;
               isHealth = false;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               switch(type.toUpperCase())
               {
                  case "WPN_PILLS":
                     bodyDef.userData = new wpn_pills();
                     bodyDef.userData.gotoAndStop(1);
                     isHealth = true;
                     corners = new Array([-4 / 30,-4 / 30],[4 / 30,-4 / 30],[4 / 30,4 / 30],[-4 / 30,4 / 30]);
                     break;
                  case "WPN_MEDKIT":
                     bodyDef.userData = new wpn_medkit();
                     bodyDef.userData.gotoAndStop(1);
                     isHealth = true;
                     corners = new Array([-5 / 30,-3 / 30],[5 / 30,-3 / 30],[5 / 30,3 / 30],[-5 / 30,3 / 30]);
                     break;
                  case "WPN_SLOWMO_10":
                     bodyDef.userData = new wpn_slowmo_10();
                     bodyDef.userData.gotoAndStop(1);
                     isPowerup = true;
                     corners = new Array([-4 / 30,-4 / 30],[4 / 30,-4 / 30],[4 / 30,4 / 30],[-4 / 30,4 / 30]);
                     break;
                  case "WPN_SLOWMO_05":
                     bodyDef.userData = new wpn_slowmo_05();
                     bodyDef.userData.gotoAndStop(1);
                     isPowerup = true;
                     corners = new Array([-4 / 30,-4 / 30],[4 / 30,-4 / 30],[4 / 30,4 / 30],[-4 / 30,4 / 30]);
                     break;
                  case "WPN_MACHETE":
                     bodyDef.userData = new wpn_machete();
                     bodyDef.userData.gotoAndStop(1);
                     isMelee = true;
                     corners = new Array([-7 / 30,-1 / 30],[7 / 30,-1 / 30],[7 / 30,1 / 30],[-7 / 30,1 / 30]);
                     break;
                  case "WPN_SWORD":
                     bodyDef.userData = new wpn_sword();
                     bodyDef.userData.gotoAndStop(1);
                     isMelee = true;
                     corners = new Array([-10 / 30,-1 / 30],[10 / 30,-1 / 30],[10 / 30,1 / 30],[-10 / 30,1 / 30]);
                     break;
                  case "WPN_AXE":
                     bodyDef.userData = new wpn_axe();
                     bodyDef.userData.gotoAndStop(1);
                     isMelee = true;
                     corners = new Array([-8 / 30,-2 / 30],[8 / 30,-3 / 30],[8 / 30,3 / 30],[5 / 30,3 / 30],[-8 / 30,-1 / 30]);
                     break;
                  case "WPN_MOLOTOVS":
                     bodyDef.userData = new wpn_molotovs();
                     bodyDef.userData.gotoAndStop(1);
                     isThrowable = true;
                     corners = new Array([-5.5 / 30,-3 / 30],[5.5 / 30,-3 / 30],[5.5 / 30,3 / 30],[-5.5 / 30,3 / 30]);
                     break;
                  case "WPN_GRENADES":
                     bodyDef.userData = new wpn_grenades();
                     bodyDef.userData.gotoAndStop(1);
                     isThrowable = true;
                     corners = new Array([-5 / 30,-2 / 30],[5 / 30,-2 / 30],[5 / 30,2 / 30],[-5 / 30,2 / 30]);
                     break;
                  case "WPN_FLAMETHROWER":
                     bodyDef.userData = new wpn_flamethrower();
                     bodyDef.userData.gotoAndStop(1);
                     isRanged = true;
                     corners = new Array([-3 / 30,-3 / 30],[3 / 30,-3 / 30],[3 / 30,3 / 30],[-3 / 30,3 / 30]);
                     break;
                  case "WPN_MAGNUM":
                     bodyDef.userData = new wpn_magnum();
                     isRanged = true;
                     corners = new Array([-3 / 30,-1 / 30],[4 / 30,-1 / 30],[4 / 30,0 / 30],[-2 / 30,2 / 30],[-3 / 30,2 / 30]);
                     break;
                  case "WPN_PISTOL":
                     bodyDef.userData = new wpn_pistol();
                     isRanged = true;
                     corners = new Array([-2 / 30,-1 / 30],[4 / 30,-1 / 30],[4 / 30,0 / 30],[-1 / 30,2 / 30],[-2 / 30,2 / 30]);
                     break;
                  case "WPN_RIFLE":
                     bodyDef.userData = new wpn_rifle();
                     isRanged = true;
                     corners = new Array([-10 / 30,-1 / 30],[-3 / 30,-2 / 30],[2 / 30,-2 / 30],[9 / 30,-1 / 30],[9 / 30,1 / 30],[3 / 30,3 / 30],[1 / 30,3 / 30],[-10 / 30,1 / 30]);
                     break;
                  case "WPN_UZI":
                     bodyDef.userData = new wpn_uzi();
                     isRanged = true;
                     corners = new Array([-3 / 30,-2 / 30],[3 / 30,-2 / 30],[4 / 30,-1 / 30],[0 / 30,4 / 30],[-1 / 30,4 / 30],[-3 / 30,0 / 30]);
                     break;
                  case "WPN_SHOTGUN":
                     bodyDef.userData = new wpn_shotgun();
                     isRanged = true;
                     corners = new Array([-7 / 30,0 / 30],[-3 / 30,-1 / 30],[9 / 30,-1 / 30],[7 / 30,1 / 30],[-5 / 30,2 / 30],[-7 / 30,2 / 30]);
                     break;
                  case "WPN_SNIPER":
                     bodyDef.userData = new wpn_sniper();
                     isRanged = true;
                     corners = new Array([-11 / 30,-1 / 30],[-1 / 30,-4 / 30],[1 / 30,-4 / 30],[12 / 30,-1 / 30],[12 / 30,0 / 30],[1 / 30,2 / 30],[-5 / 30,2 / 30],[-11 / 30,1 / 30]);
                     break;
                  case "WPN_BAZOOKA":
                     bodyDef.userData = new wpn_bazooka();
                     isRanged = true;
                     corners = new Array([-11 / 30,-1 / 30],[10 / 30,-1 / 30],[10 / 30,1 / 30],[4 / 30,3.5 / 30],[-11 / 30,1 / 30]);
               }
               bodyDef.userData.indicator.gotoAndStop(1);
               color = new Color();
               color.brightness = PlayerCharacter.BRIGHTNESS;
               bodyDef.userData.transform.colorTransform = color;
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.isWeapon = true;
               bodyDef.userData.isRanged = isRanged;
               bodyDef.userData.isThrowable = isThrowable;
               bodyDef.userData.isMelee = isMelee;
               bodyDef.userData.isPowerup = isPowerup;
               bodyDef.userData.isHealth = isHealth;
               bodyDef.userData.objectData.Kickable = false;
               bodyDef.userData.weaponData = null;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               bodyDef.userData.objectData.UserValues = [0];
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  var b:b2Body = param1;
                  var game_speed:Number = param2;
                  if(b.GetUserData().objectData.UserValues[0] == 0)
                  {
                     b.GetUserData().objectData.MC.indicator.visible = false;
                     if(b.IsSleeping())
                     {
                        b.GetUserData().objectData.UserValues[0] = 1;
                     }
                     if(b.GetUserData().weaponData.Ammo <= 0)
                     {
                        if(b.GetUserData().objectData.UserValues[1] == undefined)
                        {
                           b.GetUserData().objectData.UserValues[1] = 0;
                           b.GetUserData().objectData.UserValues[2] = b.GetLinearVelocity().x;
                        }
                        else if(b.GetUserData().objectData.UserValues[1] == 0)
                        {
                           if(b.GetLinearVelocity().x != b.GetUserData().objectData.UserValues[2])
                           {
                              b.GetUserData().objectData.UserValues[1] = 1;
                           }
                        }
                        else
                        {
                           b.GetUserData().objectData.UserValues[1] = b.GetUserData().objectData.UserValues[1] + 1;
                           if(b.GetUserData().objectData.UserValues[1] > 12)
                           {
                              b.GetUserData().objectData.UpdateFunction = _debrisFadeFunction;
                              b.GetUserData().objectData.ObjectTimer = 240;
                           }
                        }
                     }
                  }
                  else if(b.GetUserData().objectData.UserValues[0] == 1)
                  {
                     b.GetUserData().objectData.MC.indicator.visible = true;
                     b.SetXForm(new b2Vec2(b.GetPosition().x,b.GetPosition().y - 4 / 30),0);
                     b.PutToSleep();
                     b.GetUserData().objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
                     {
                     };
                     if(b.GetUserData().weaponData.Ammo <= 0)
                     {
                        b.GetUserData().objectData.ForceDestruction();
                     }
                  }
               };
               tmp_mc = _weapon_mc;
               break;
            case "GRENADE_THROWN":
               addGrenadeIndicator = true;
               shapeScale = 0.7;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new wpn_grenade_thrown();
               corners = new Array([-2 / 30,-1 / 30],[-1 / 30,-2 / 30],[1 / 30,-2 / 30],[2 / 30,-1 / 30],[2 / 30,1 / 30],[1 / 30,2 / 30],[-1 / 30,2 / 30],[-1 / 30,2 / 30]);
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,10,10,false);
               bodyDef.userData.objectData.IsActiveHazard = true;
               bodyDef.userData.objectData.IsBulletHazard = true;
               bodyDef.userData.objectData.IsThrowableObject = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 3.5;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.UserValues = optionalValues;
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  param1.GetUserData().objectData.UserValues[0] = param1.GetUserData().objectData.UserValues[0] - param2;
                  if(param1.GetUserData().objectData.UserValues[0] <= 0)
                  {
                     param1.GetUserData().objectData.ForceDestruction();
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  _Handler_Sounds.PlaySoundAt_Box2DScale("barrel_explosion",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Explosions.TriggerExplosionAt_Box2DScale("",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _weapon_mc;
               break;
            case "MOLOTOV_THROWN":
               addGrenadeIndicator = true;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new wpn_molotov_thrown();
               corners = new Array([-2 / 30,-1 / 30],[-1 / 30,-2 / 30],[1 / 30,-2 / 30],[2 / 30,-1 / 30],[2 / 30,1 / 30],[1 / 30,2 / 30],[-1 / 30,2 / 30],[-1 / 30,2 / 30]);
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.isMolotov = true;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,0,10,0,10,10,false);
               bodyDef.userData.objectData.IsActiveHazard = true;
               bodyDef.userData.objectData.IsBulletHazard = true;
               bodyDef.userData.objectData.IsThrowableObject = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.UserValues = new Array(optionalValues[1],0);
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:particle_data = null;
                  param1.GetUserData().objectData.UserValues[1] = param1.GetUserData().objectData.UserValues[1] - param2;
                  if(param1.GetUserData().objectData.UserValues[1] <= 0)
                  {
                     _loc3_ = new b2Vec2();
                     _loc3_.x = 0;
                     _loc3_.y = -5 / 30;
                     _loc4_ = param1.GetWorldPoint(_loc3_);
                     (_loc5_ = new particle_data("FIRE",_loc4_.x,_loc4_.y)).ScaleX = 0.75;
                     _loc5_.ScaleY = 0.75;
                     _Handler_Effects.AddParticle_Box2DScale(_loc5_);
                     param1.GetUserData().objectData.UserValues[1] = 1;
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustmolotov",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Sounds.PlaySoundAt_Box2DScale("fireburst",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Fires.TriggerFireAt_Box2DScale("MOLOTOV",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _weapon_mc;
               break;
            case "STATUE":
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new statue();
               bodyDef.userData.material = _material.Ground;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = false;
               bodyDef.userData.objectData.CanSmoke = false;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.Kickable = false;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-6.5 / 30,-3 / 30],[6 / 30,-3 / 30],[8 / 30,9 / 30],[-6.5 / 30,9 / 30]);
               tmp_mc = _objects_mc;
               break;
            case "HANGING_LAMP":
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new hanging_lamp();
               bodyDef.userData.gotoAndStop(1);
               corners = new Array([-5 / 30,1 / 30],[-3.5 / 30,-2 / 30],[0 / 30,-3 / 30],[3.5 / 30,-2 / 30],[5 / 30,1 / 30]);
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,5,10,0.05,10,10);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "HANGING_LAMP_B":
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new hanging_lamp();
               bodyDef.userData.gotoAndStop(2);
               corners = new Array([-5 / 30,1 / 30],[-3.5 / 30,-2 / 30],[0 / 30,-3 / 30],[3.5 / 30,-2 / 30],[5 / 30,1 / 30]);
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,5,1,1,1,1,true);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "COMP_SCREEN":
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new comp_screen();
               corners = new Array([-4.5 / 30,-5 / 30],[4.5 / 30,-5 / 30],[4.5 / 30,3 / 30],[2.5 / 30,5 / 30],[-2.5 / 30,5 / 30],[-4.5 / 30,3 / 30]);
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,10,0);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.OnlyBurnWhileWake = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.Strength = 1;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  _Handler_Sounds.PlaySoundAt_Box2DScale("COMP_EXPLODE",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Effects.AddEffectAt_Box2DScale("EXPLOSION_CIRCLE",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _objects_mc;
               break;
            case "CHAIR":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new chair();
               corners = new Array([-2 / 30,-6 / 30],[3.5 / 30,0 / 30],[3.5 / 30,4 / 30],[-3.5 / 30,4 / 30],[-3.5 / 30,-6 / 30]);
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerFragile = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.35;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:Number = NaN;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:b2Vec2 = null;
                  var _loc6_:b2Body = null;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustwood",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = Number(param1.GetUserData().objectData.ObjectSmokeGrade);
                  if(_loc2_ < 2)
                  {
                     _loc2_ = 1;
                  }
                  _loc3_ = param1.GetLinearVelocity();
                  (_loc4_ = new b2Vec2()).x = -6 / 30;
                  _loc4_.y = 0 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_01",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = -0.5 / 30;
                  _loc4_.y = -3.5 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_02",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = 6 / 30;
                  _loc4_.y = 0 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_03",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
               };
               tmp_mc = _objects_mc;
               break;
            case "TABLE_DEBRIS_01":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new table_debris_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-1 / 30,-4 / 30],[3 / 30,-4 / 30],[0 / 30,4 / 30],[-1 / 30,4 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "TABLE_DEBRIS_02":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new table_debris_02();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-3.5 / 30,-0.5 / 30],[3.5 / 30,-0.5 / 30],[4.5 / 30,0.5 / 30],[-4.5 / 30,0.5 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "TABLE_DEBRIS_03":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new table_debris_03();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-2 / 30,-4 / 30],[1 / 30,-4 / 30],[1 / 30,4 / 30],[0 / 30,4 / 30],[-2 / 30,-3 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "GLASS_SHARD_1":
               corners = new Array([-2 / 30,2 / 30],[0 / 30,-2 / 30],[2 / 30,2 / 30]);
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new glass_shard_1();
               bodyDef.userData.material = _material.Glass;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,5,0,0,1,1);
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.1;
               bodyDef.userData.objectData.Strength = 1;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
               break;
            case "TUTORIAL_TARGET_DEBRIS_01":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new tutorial_target_debris_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([0 / 30,-5 / 30],[2 / 30,-5 / 30],[2 / 30,1 / 30],[1 / 30,2 / 30],[-2 / 30,2 / 30],[-2 / 30,0 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "TUTORIAL_TARGET_DEBRIS_02":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new tutorial_target_debris_02();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([0 / 30,-1 / 30],[3 / 30,-1 / 30],[3 / 30,1 / 30],[-3 / 30,1 / 30],[-3 / 30,0 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "TUTORIAL_TARGET_DEBRIS_03":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new tutorial_target_debris_03();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([1 / 30,-2 / 30],[3 / 30,0 / 30],[0 / 30,2 / 30],[-3 / 30,-2 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "CRATE_DEBRIS_01":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new crate_debris_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-4 / 30,-2 / 30],[4 / 30,-2 / 30],[4 / 30,2 / 30],[-2 / 30,4 / 30],[-4 / 30,4 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "CRATE_DEBRIS_02":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new crate_debris_02();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-4 / 30,-1 / 30],[1 / 30,-1 / 30],[4 / 30,0 / 30],[4 / 30,1 / 30],[-3 / 30,1 / 30],[-4 / 30,0 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "CRATE_DEBRIS_03":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new crate_debris_03();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,1,30,1);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-5 / 30,-1 / 30],[6 / 30,-1 / 30],[5 / 30,1 / 30],[-6 / 30,1 / 30]);
               tmp_mc = _scrap_mc;
               break;
            case "BARREL_DEBRIS_02":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new barrel_debris_02();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,0,30,1);
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.OnlyBurnWhileWake = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-2 / 30,-2 / 30],[1 / 30,-2 / 30],[1 / 30,2 / 30],[-1 / 30,2 / 30]);
               tmp_mc = _scrap_mc;
               break;
            default:
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new error_mc();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50);
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               corners = new Array([-5 / 30,-5 / 30],[5 / 30,-5 / 30],[5 / 30,5 / 30],[-5 / 30,5 / 30]);
               tmp_mc = _scrap_mc;
         }
         if(reversed)
         {
            MovieClip(bodyDef.userData).scaleX = -1;
            corners = ReverseCorners(corners);
         }
         bodyDef.userData.IDNumber = GenerateID();
         bodyDef.userData.tiltValue = 0;
         corners = IncreaseCorners(corners);
         boxDef.vertexCount = corners.length;
         i = 0;
         while(i < corners.length)
         {
            boxDef.vertices[i] = new b2Vec2(corners[i][0],corners[i][1]);
            i++;
         }
         boxDef.friction = bodyDef.userData.material.Friction;
         boxDef.density = bodyDef.userData.material.Density;
         boxDef.restitution = bodyDef.userData.material.Restitution;
         if(bodyDef.userData.objectData.DrawHitBox)
         {
            bodyDef.userData.objectData.CollisionMC = DrawPolyMC(corners);
            bodyDef.userData.objectData.CollisionMC.x = PosX * 30;
            bodyDef.userData.objectData.CollisionMC.y = PosY * 30;
            _static_objects_hitbox_mc.addChild(bodyDef.userData.objectData.CollisionMC);
         }
         if(bodyDef.userData.objectData.DrawShapeMC)
         {
            bodyDef.userData.objectData.ShapeMC = DrawPolyMC(corners,65280,0.4);
            bodyDef.userData.objectData.ShapeMC.x = PosX * 30;
            bodyDef.userData.objectData.ShapeMC.y = PosY * 30;
            bodyDef.userData.objectData.ShapeMC.scaleX = shapeScale;
            bodyDef.userData.objectData.ShapeMC.scaleY = shapeScale;
            _object_shape_container_mc.addChild(bodyDef.userData.objectData.ShapeMC);
         }
         bodyDef.userData.x = PosX * 30;
         bodyDef.userData.y = PosY * 30;
         tmp_mc.addChild(bodyDef.userData);
         body = m_world.CreateBody(bodyDef);
         body.CreateShape(boxDef);
         body.SetMassFromShapes();
         body.SetUserData(bodyDef.userData);
         body.SetLinearVelocity(Velocity);
         body.SetAngularVelocity(AngularVelocity);
         body.GetUserData().objectData.Body = body;
         _Handler_Output.Trace(type.toUpperCase() + " created at (" + Math.round(bodyDef.userData.x) + ", " + Math.round(bodyDef.userData.y) + ")");
         m_world.AddObjectToLists(body);
         if(addGrenadeIndicator)
         {
            _Handler_BasicOverlays.AddOverlay(body,new grenade_marker());
         }
         return body;
      }
      
      public function set SetdbgDraw(param1:MovieClip) : void
      {
      }
      
      public function AddObject(param1:String, param2:Number, param3:Number, param4:Number, param5:b2Vec2, param6:Number, param7:Array = null) : b2Body
      {
         var _loc8_:Array = null;
         var _loc9_:int = 0;
         var _loc10_:Boolean = false;
         var _loc11_:String = null;
         _loc8_ = GetData(param1);
         _loc9_ = Math.floor(Math.random() * _loc8_.length);
         _loc10_ = false;
         _loc11_ = _loc8_[_loc9_].toUpperCase();
         if(_loc11_.substr(_loc11_.length - 2,2) == "_R")
         {
            _loc11_ = _loc11_.substr(0,_loc11_.length - 2);
            _loc10_ = true;
         }
         switch(_loc11_)
         {
            case "BUTTON_01":
            case "SOLID_INVISIBLE_METAL_GIB":
            case "SOLID_INVISIBLE_METAL":
            case "SPARK":
            case "EMPTY_SHELL_SMALL":
            case "EMPTY_SHELL_SHOTGUN":
            case "EMPTY_SHELL_BIG":
            case "ELEVATOR_01":
            case "LIFT_01":
            case "LIFT_SMALL_01":
            case "BARREL_EXPLOSIVE":
            case "BARREL_WRECK":
            case "BARREL":
            case "GASCAN":
            case "CHAR_GIB_01":
            case "CHAR_GIB_02":
            case "CHAR_GIB_03":
            case "CHAR_GIB_04":
            case "CHAR_GIB_05":
            case "FILECAB":
            case "POOL_TABLE":
            case "CRATE_HANGING":
            case "CRATE_HANGING_HOLDER":
            case "COMP":
            case "DESK":
            case "DESK_1":
            case "LAMP_1":
            case "LAMP_1_B":
            case "BARREL_DEBRIS_03":
            case "BARREL_DEBRIS_01":
            case "BEACHBALL_FLAT":
            case "CRATE":
            case "PAPER":
            case "TABLE":
            case "TABLE_SMALL":
               return AddBox(_loc11_,param2,param3,param4,param5,param6,param7,_loc10_);
            case "COMFY_CHAIR":
            case "ROLLING_PIPE":
            case "BEACHBALL":
            case "STATUE_GLOBE":
            case "TUTORIAL_TARGET":
            case "WINDMILL_PROPELLER":
            case "PLATFORM_MOTOR":
               return AddCircle(_loc11_,param2,param3,param4,param5,param6,param7,_loc10_);
            case "WPN_SWORD":
            case "WPN_AXE":
            case "WPN_MACHETE":
            case "WPN_GRENADES":
            case "WPN_MOLOTOVS":
            case "WPN_SNIPER":
            case "WPN_SHOTGUN":
            case "WPN_RIFLE":
            case "WPN_UZI":
            case "WPN_MAGNUM":
            case "WPN_BAZOOKA":
            case "WPN_FLAMETHROWER":
            case "WPN_PISTOL":
            case "WPN_SLOWMO_05":
            case "WPN_SLOWMO_10":
            case "WPN_PILLS":
            case "WPN_MEDKIT":
            case "COMP_SCREEN":
            case "HANGING_LAMP":
            case "HANGING_LAMP_B":
            case "CHAIR":
            case "STATUE":
            case "GRENADE_THROWN":
            case "MOLOTOV_THROWN":
            case "TABLE_DEBRIS_01":
            case "TABLE_DEBRIS_02":
            case "TABLE_DEBRIS_03":
            case "CRATE_DEBRIS_01":
            case "CRATE_DEBRIS_02":
            case "CRATE_DEBRIS_03":
            case "TUTORIAL_TARGET_DEBRIS_01":
            case "TUTORIAL_TARGET_DEBRIS_02":
            case "TUTORIAL_TARGET_DEBRIS_03":
            case "BARREL_DEBRIS_02":
               return AddPolygon(_loc11_,param2,param3,param4,param5,param6,param7,_loc10_);
            default:
               return null;
         }
      }
      
      private function GetData(param1:String) : Array
      {
         var _loc2_:Array = null;
         var _loc3_:String = null;
         var _loc4_:int = 0;
         if(param1.charAt(param1.length) != ",")
         {
            param1 += ",";
         }
         _loc2_ = new Array();
         _loc3_ = "";
         _loc4_ = 0;
         while(_loc4_ < param1.length)
         {
            if(param1.charAt(_loc4_) == ",")
            {
               _loc2_.push(_loc3_);
               _loc3_ = "";
            }
            else
            {
               _loc3_ += param1.charAt(_loc4_).toString();
            }
            _loc4_++;
         }
         return _loc2_;
      }
      
      public function get Ground() : b2Body
      {
         return _ground;
      }
      
      private function ReverseCorners(param1:Array) : Array
      {
         var _loc2_:Array = null;
         var _loc3_:int = 0;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         _loc2_ = new Array();
         _loc3_ = int(param1.length - 1);
         while(_loc3_ >= 0)
         {
            _loc4_ = -param1[_loc3_][0];
            _loc5_ = Number(param1[_loc3_][1]);
            _loc2_.push([_loc4_,_loc5_]);
            _loc3_--;
         }
         return _loc2_;
      }
      
      public function AddBox(param1:String, param2:Number, param3:Number, param4:Number, param5:b2Vec2, param6:Number, param7:Array = null, param8:Boolean = false) : b2Body
      {
         var tmp_mc:MovieClip = null;
         var size:Point = null;
         var body:b2Body = null;
         var bodyDef:b2BodyDef = null;
         var boxDef:* = undefined;
         var type:String = param1;
         var PosX:Number = param2;
         var PosY:Number = param3;
         var Angle:Number = param4;
         var Velocity:b2Vec2 = param5;
         var AngularVelocity:Number = param6;
         var optionalValues:Array = param7;
         var reversed:Boolean = param8;
         if(_locked)
         {
            _queue.push("B",type,PosX,PosY,Angle,Velocity,AngularVelocity,optionalValues);
            return null;
         }
         size = new Point(0,0);
         boxDef = new b2PolygonDef();
         bodyDef = new b2BodyDef();
         bodyDef.position.x = PosX;
         bodyDef.position.y = PosY;
         bodyDef.angle = Angle;
         switch(type.toUpperCase())
         {
            case "BUTTON_01":
               size.x = 4;
               size.y = 4;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new blank_mc();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.isButton = true;
               bodyDef.userData.buttonData = new ButtonData();
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "SOLID_GLASS_01":
               size.x = optionalValues[0];
               size.y = optionalValues[1];
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new blank_mc();
               bodyDef.userData.material = _material.Glass;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,5,10,0.05,10,10);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.PlayerFragile = true;
               bodyDef.userData.objectData.IsGlass = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.KickPower = 1.4;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.IsThrowableFragile = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.objectData.Strength = 0;
               bodyDef.userData.objectData.UserValues = optionalValues;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:b2Vec2 = null;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:Number = NaN;
                  var _loc6_:int = 0;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustglass",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = param1.GetLinearVelocity();
                  _loc3_ = new b2Vec2();
                  _loc5_ = Number(bodyDef.userData.objectData.UserValues[0]);
                  _loc6_ = -_loc5_ / 2;
                  while(_loc6_ < _loc5_ / 2)
                  {
                     _loc3_.x = _loc6_ / 30;
                     _loc3_.y = 0;
                     _loc4_ = param1.GetWorldPoint(_loc3_);
                     AddPolygon("GLASS_SHARD_1",_loc4_.x,_loc4_.y,Math.random() * Math.PI,new b2Vec2(_loc2_.x + Math.random() - 0.5,_loc2_.y + Math.random() - 0.5),Math.random() * Math.PI);
                     _loc6_ += 6;
                  }
               };
               tmp_mc = _objects_mc;
               break;
            case "SOLID_INVISIBLE_METAL_GIB":
               size.x = optionalValues[0];
               size.y = optionalValues[1];
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new blank_mc();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanKnockDownPlayer = false;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "SOLID_INVISIBLE_METAL":
               size.x = optionalValues[0];
               size.y = optionalValues[1];
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new blank_mc();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanKnockDownPlayer = false;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "SPARK":
               size.x = 1;
               size.y = 1;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new spark();
               bodyDef.userData.material = _material.Spark;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.ObjectTimer = 18 + Math.random() * 6;
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  param1.GetUserData().objectData.ObjectTimer = param1.GetUserData().objectData.ObjectTimer - param2;
                  if(param1.GetUserData().objectData.ObjectTimer <= 0)
                  {
                     param1.GetUserData().objectData.ForceDestruction();
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
               break;
            case "EMPTY_SHELL_SMALL":
            case "EMPTY_SHELL_SHOTGUN":
            case "EMPTY_SHELL_BIG":
               size.y = 1;
               size.x = 2;
               switch(type.toUpperCase())
               {
                  case "EMPTY_SHELL_SMALL":
                     bodyDef.userData = new empty_shell_small();
                     break;
                  case "EMPTY_SHELL_SHOTGUN":
                     bodyDef.userData = new empty_shell_shotgun();
                     break;
                  case "EMPTY_SHELL_BIG":
                     bodyDef.userData = new empty_shell_big();
                     size.x = 3;
                     break;
                  default:
                     bodyDef.userData = new error_mc();
               }
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData.material = _material.Shell;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.ObjectTimer = 24;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  param1.GetUserData().objectData.ObjectTimer = param1.GetUserData().objectData.ObjectTimer - param2;
                  if(param1.GetUserData().objectData.ObjectTimer <= 0)
                  {
                     param1.GetUserData().objectData.ForceDestruction();
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _Handler_Effects.EffectMCFront;
               break;
            case "ELEVATOR_01":
               size.x = 41;
               size.y = 44;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new elevator_01();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "LIFT_SMALL_01":
               size.x = 25;
               size.y = 6;
               boxDef.filter.isElevator = true;
               boxDef.filter.isGhost = true;
               bodyDef.userData = new lift_small_01();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.IsElevator = true;
               bodyDef.userData.objectData.DrawCloudBox = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.PartOfStaticWorld = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.CanKnockDownPlayer = false;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "LIFT_01":
               size.x = 35;
               size.y = 7;
               boxDef.filter.isElevator = true;
               boxDef.filter.isGhost = true;
               bodyDef.userData = new lift_01();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.IsElevator = true;
               bodyDef.userData.objectData.DrawCloudBox = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.PartOfStaticWorld = true;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.CanKnockDownPlayer = false;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "BEACHBALL_FLAT":
               size.x = 4;
               size.y = 2;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new beachball();
               bodyDef.userData.gotoAndStop(2);
               bodyDef.fixedRotation = true;
               bodyDef.userData.material = _material.Beachball;
               bodyDef.userData.material.Restitution = 0.1;
               bodyDef.userData.material.Density = 50;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,20,0,1,0,0);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.2;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisFadeFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "CRATE_HANGING_HOLDER":
               size.x = 9;
               size.y = 6;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new crate_hanging_holder();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,6,1,0,1,1,false);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.Strength = 1;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "CRATE_HANGING":
               size.x = 27;
               size.y = 14;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new crate_hanging();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.BotPreferJump = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "LAMP_1":
               size.x = 21;
               size.y = 5;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new lamp_1();
               bodyDef.userData.material = _material.ElectricLamp;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,1,10,10,10,false);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerFragile = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:b2Vec2 = null;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:int = 0;
                  var _loc5_:b2Body = null;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustglass",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Sounds.PlaySoundAt_Box2DScale("ELECTRIC_SPARK",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Effects.AddEffectAt_Box2DScale("ELECTRIC_SPARK",param1.GetPosition().x,param1.GetPosition().y + 5 / 30);
                  _loc2_ = new b2Vec2();
                  _loc4_ = -10;
                  while(_loc4_ <= 10)
                  {
                     _loc2_.x = _loc4_ / 30;
                     _loc2_.y = 0;
                     _loc3_ = param1.GetWorldPoint(_loc2_);
                     AddPolygon("GLASS_SHARD_1",_loc3_.x,_loc3_.y,Math.random() * Math.PI,new b2Vec2(Math.random() * 2 - 1,Math.random()),Math.random() * Math.PI);
                     AddBox("SPARK",_loc3_.x,_loc3_.y + 0.1,0,new b2Vec2(Math.random() * 10 - 5,Math.random()),Math.random() * Math.PI);
                     _loc4_ += 5;
                  }
                  _loc5_ = AddObject("LAMP_1_B",param1.GetPosition().x,param1.GetPosition().y,0,new b2Vec2(),0);
                  AddLimitedJoint(Ground,_loc5_,_loc5_.GetPosition(),0,0);
               };
               tmp_mc = _objects_mc;
               break;
            case "LAMP_1_B":
               size.x = 21;
               size.y = 5;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new lamp_1_b();
               bodyDef.userData.material = _material.ElectricLamp;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "GASCAN":
               size.x = 7;
               size.y = 9;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new gascan();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyDataExplosiveBarrel(bodyDef.userData,_Handler_Deconstructer,50,0,0.7,100,100);
               bodyDef.userData.objectData.IsBurningHazard = true;
               bodyDef.userData.objectData.IsExplosionHazard = true;
               bodyDef.userData.objectData.IsBulletHazard = true;
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.FireLifeSpan = 6;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.objectData.Strength = 5;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  _Handler_Sounds.PlaySoundAt_Box2DScale("fireburst",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Fires.TriggerFireAt_Box2DScale("GASCAN",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _objects_mc;
               break;
            case "BARREL_EXPLOSIVE":
               size.x = 9;
               size.y = 13;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new barrel_01();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyDataExplosiveBarrel(bodyDef.userData,_Handler_Deconstructer,50,0,0.7,100,100);
               bodyDef.userData.objectData.IsBurningHazard = true;
               bodyDef.userData.objectData.IsExplosionHazard = true;
               bodyDef.userData.objectData.IsBulletHazard = true;
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.FireLifeSpan = 6;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.objectData.Strength = 30;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  _Handler_Sounds.PlaySoundAt_Box2DScale("barrel_explosion",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Sounds.PlaySoundAt_Box2DScale("fireburst",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Fires.AddFireToObject(AddBox("barrel_wreck",param1.GetPosition().x,param1.GetPosition().y,param1.GetAngle(),new b2Vec2(param1.GetLinearVelocity().x + Math.random() * 12 - 6,param1.GetLinearVelocity().y - 1),param1.GetAngularVelocity() + Math.random() * 4 - 2));
                  _Handler_Fires.TriggerFireAt_Box2DScale("BARREL",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Explosions.TriggerExplosionAt_Box2DScale("",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _objects_mc;
               break;
            case "BARREL_WRECK":
               size.x = 9;
               size.y = 13;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new barrel_03();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50,0,0,0,0);
               bodyDef.userData.objectData.IsBurningHazard = true;
               bodyDef.userData.objectData.IsExplosionHazard = true;
               bodyDef.userData.objectData.IsImpactHazard = true;
               bodyDef.userData.objectData.IsBulletHazard = true;
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.objectData.Strength = 30;
               bodyDef.userData.objectData.ObjectTimer = 6;
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  if(param1.GetUserData().objectData.ObjectTimer > 0)
                  {
                     param1.GetUserData().objectData.ObjectTimer = param1.GetUserData().objectData.ObjectTimer - param2;
                  }
                  if(param1.GetUserData().objectData.ObjectTimer <= 0)
                  {
                     if(param1.IsSleeping())
                     {
                        bodyDef.userData.objectData.SetResistance(100,1,100,100);
                     }
                     else
                     {
                        bodyDef.userData.objectData.SetResistance(100,0,100,100);
                     }
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:b2Vec2 = null;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:b2Body = null;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("barrel_explosion",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = param1.GetLinearVelocity();
                  _loc3_ = new b2Vec2();
                  _loc3_.x = -1.5 / 30;
                  _loc3_.y = -1.5 / 30;
                  _loc4_ = param1.GetWorldPoint(_loc3_);
                  _loc5_ = AddPolygon("barrel_debris_02",_loc4_.x,_loc4_.y,param1.GetAngle(),new b2Vec2(_loc2_.x + Math.random() * 2 - 1,_loc2_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc5_);
                  }
                  _loc3_.x = 2.5 / 30;
                  _loc3_.y = -2.5 / 30;
                  _loc4_ = param1.GetWorldPoint(_loc3_);
                  _loc5_ = AddBox("barrel_debris_01",_loc4_.x,_loc4_.y,param1.GetAngle(),new b2Vec2(_loc2_.x + Math.random() * 2 - 1,_loc2_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc5_);
                  }
                  _loc3_.x = -0.5 / 30;
                  _loc3_.y = 5 / 30;
                  _loc4_ = param1.GetWorldPoint(_loc3_);
                  _loc5_ = AddBox("barrel_debris_03",_loc4_.x,_loc4_.y,param1.GetAngle(),new b2Vec2(_loc2_.x + Math.random() * 2 - 1,_loc2_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc5_);
                  }
                  _Handler_Explosions.TriggerExplosionAt_Box2DScale("",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _objects_mc;
               break;
            case "COMP":
               size.x = 5;
               size.y = 10;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new comp();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,10,0,false);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.OnlyBurnWhileWake = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.Strength = 1;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  _Handler_Sounds.PlaySoundAt_Box2DScale("COMP_EXPLODE",param1.GetPosition().x,param1.GetPosition().y);
                  _Handler_Effects.AddEffectAt_Box2DScale("EXPLOSION_CIRCLE",param1.GetPosition().x,param1.GetPosition().y);
               };
               tmp_mc = _objects_mc;
               break;
            case "BARREL":
               size.x = 9;
               size.y = 13;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new barrel_02();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.objectData.Strength = 30;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "TRASHCAN":
               size.x = 9;
               size.y = 13;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new trashcan();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.objectData.Strength = 30;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "CHAR_GIB_01":
            case "CHAR_GIB_02":
            case "CHAR_GIB_03":
            case "CHAR_GIB_04":
            case "CHAR_GIB_05":
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               switch(type.toUpperCase())
               {
                  case "CHAR_GIB_01":
                     size.x = 5;
                     size.y = 4;
                     bodyDef.userData = new char_gib_01();
                     break;
                  case "CHAR_GIB_02":
                     size.x = 5;
                     size.y = 3;
                     bodyDef.userData = new char_gib_02();
                     break;
                  case "CHAR_GIB_03":
                     size.x = 3;
                     size.y = 5;
                     bodyDef.userData = new char_gib_03();
                     break;
                  case "CHAR_GIB_04":
                     size.x = 4;
                     size.y = 3;
                     bodyDef.userData = new char_gib_04();
                     break;
                  case "CHAR_GIB_05":
                     size.x = 4;
                     size.y = 3;
                     bodyDef.userData = new char_gib_05();
               }
               bodyDef.userData.material = _material.Ragdoll;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,0,1,0,0);
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.8;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.Strength = 30;
               bodyDef.userData.objectData.UserValues = [40,PosX,PosY];
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  var _loc3_:Number = NaN;
                  var _loc4_:Number = NaN;
                  var _loc5_:Number = NaN;
                  var _loc6_:Number = NaN;
                  var _loc7_:Number = NaN;
                  var _loc8_:Number = NaN;
                  if(param1.GetUserData().objectData.UserValues[0] > 0)
                  {
                     param1.GetUserData().objectData.UserValues[0] = param1.GetUserData().objectData.UserValues[0] - param2;
                     if(!param1.IsSleeping())
                     {
                        if(!param1.GetUserData().objectData.ThroughPortal)
                        {
                           _loc3_ = param1.GetPosition().x - param1.GetUserData().objectData.UserValues[1];
                           _loc4_ = param1.GetPosition().y - param1.GetUserData().objectData.UserValues[2];
                           _loc5_ = Math.sqrt(_loc3_ * _loc3_ + _loc4_ * _loc4_);
                           if(_loc5_ >= 0.2)
                           {
                              _loc6_ = _loc3_ / _loc5_;
                              _loc7_ = _loc4_ / _loc5_;
                              _loc8_ = 0;
                              while(_loc8_ <= _loc5_)
                              {
                                 _Handler_Effects.AddEffectAt_Box2DScale("BLOOD_GIB_TRACE",param1.GetPosition().x - _loc6_ * _loc8_,param1.GetPosition().y - _loc7_ * _loc8_);
                                 _loc8_ += 0.2;
                              }
                              param1.GetUserData().objectData.UserValues[1] = param1.GetPosition().x;
                              param1.GetUserData().objectData.UserValues[2] = param1.GetPosition().y;
                           }
                        }
                        else
                        {
                           param1.GetUserData().objectData.UserValues[1] = param1.GetPosition().x;
                           param1.GetUserData().objectData.UserValues[2] = param1.GetPosition().y;
                           param1.GetUserData().objectData.ThroughPortal = false;
                        }
                     }
                  }
                  else
                  {
                     param1.GetUserData().objectData.UpdateFunction = _debrisFadeFunction;
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
               break;
            case "FILECAB":
               size.x = 11;
               size.y = 13;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new filecab_01();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.material.BulletHitEffect = "FILECAB_HIT";
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CrushDamage = 35;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "DESK_1":
               size.x = 25;
               size.y = 12;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new desk_1();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,100,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = false;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.CrushDamage = 35;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.5;
               bodyDef.userData.objectData.BotPreferJump = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "DESK":
               size.x = 25;
               size.y = 12;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new desk();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,100,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = false;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.CrushDamage = 35;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.5;
               bodyDef.userData.objectData.BotPreferJump = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "POOL_TABLE":
               size.x = 40;
               size.y = 12;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new pool_table_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,100,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = false;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.CrushDamage = 35;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.5;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "PAPER":
               size.x = 7;
               size.y = 7;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new paper();
               bodyDef.userData.material = _material.Paper;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,20,0,4,1,500);
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 1;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UserValues = [5];
               bodyDef.userData.objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  if(param1.GetUserData().objectData.ObjectTimer == 0)
                  {
                     param1.GetUserData().objectData.ObjectTimer = 6;
                  }
                  else
                  {
                     param1.GetUserData().objectData.ObjectTimer = param1.GetUserData().objectData.ObjectTimer - param2;
                     if(param1.GetUserData().objectData.ObjectTimer <= 0)
                     {
                        param1.GetUserData().objectData.BulletTransparent = false;
                        m_world.RemoveObjectFromLists(param1);
                        m_world.AddObjectToLists(param1);
                     }
                  }
               };
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:b2Vec2 = null;
                  var _loc3_:b2Body = null;
                  if(param1.GetUserData().objectData.UserValues[0] > 0 && param1.GetUserData().objectData.LastDamage != BodyData.DAMAGE_EXPLOSION)
                  {
                     _Handler_Effects.AddParticle_Box2DScale(new particle_data("PAPER_HIT",param1.GetPosition().x,param1.GetPosition().y));
                     _loc2_ = param1.GetLinearVelocity();
                     _loc2_.x *= 0.2;
                     _loc2_.y *= 0.2;
                     _loc3_ = AddObject("PAPER",param1.GetPosition().x,param1.GetPosition().y,param1.GetAngle(),_loc2_,param1.GetAngularVelocity());
                     _loc3_.GetUserData().objectData.UserValues[0] = param1.GetUserData().objectData.UserValues[0] - 1;
                     if(param1.GetUserData().objectData.ObjectOnFire)
                     {
                        _Handler_Fires.AddFireToObject(_loc3_);
                     }
                     else
                     {
                        _Handler_Fires.AddSmokeToObject(_loc3_,param1.GetUserData().objectData.ObjectSmokeGrade);
                     }
                  }
                  else
                  {
                     _Handler_Effects.AddParticle_Box2DScale(new particle_data("PAPER_HIT",param1.GetPosition().x + (Math.random() * 8 - 4) / 30,param1.GetPosition().y - (Math.random() * 6 - 3) / 30));
                     _Handler_Effects.AddParticle_Box2DScale(new particle_data("PAPER_HIT",param1.GetPosition().x - (Math.random() * 8 - 4) / 30,param1.GetPosition().y + (Math.random() * 6 - 3) / 30));
                     _Handler_Effects.AddParticle_Box2DScale(new particle_data("PAPER_HIT",param1.GetPosition().x - (Math.random() * 8 - 4) / 30,param1.GetPosition().y + (Math.random() * 6 - 3) / 30));
                  }
               };
               tmp_mc = _scrap_mc;
               break;
            case "BARREL_DEBRIS_03":
               size.x = 2;
               size.y = 3;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new barrel_debris_03();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,0,30,1);
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.OnlyBurnWhileWake = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
               break;
            case "BARREL_DEBRIS_01":
               size.x = 2;
               size.y = 5;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new barrel_debris_01();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,30,0,0,30,1);
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.OnlyBurnWhileWake = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.Strength = 3;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.objectData.UpdateFunction = _debrisUpdateFunction;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
               break;
            case "CRATE":
               size.x = 14;
               size.y = 14;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new crate_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40,1,1,0.8,2);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerFragile = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.7;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:Number = NaN;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:b2Vec2 = null;
                  var _loc6_:b2Body = null;
                  var _loc7_:Number = NaN;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustwood",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = Number(param1.GetUserData().objectData.ObjectSmokeGrade);
                  if(_loc2_ < 2)
                  {
                     _loc2_ = 1;
                  }
                  _loc3_ = param1.GetLinearVelocity();
                  (_loc4_ = new b2Vec2()).x = -3 / 30;
                  _loc4_.y = -5 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("crate_debris_01",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = 4 / 30;
                  _loc4_.y = -1 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("crate_debris_02",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = -1 / 30;
                  _loc4_.y = 5 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("crate_debris_03",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3 + 1),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  if(Math.random() < 0.2)
                  {
                     _loc4_.x = 0;
                     _loc4_.y = 0;
                     _loc5_ = param1.GetWorldPoint(_loc4_);
                     _loc7_ = Math.random();
                     if(_loc7_ < 0.25)
                     {
                        AddObject("BEACHBALL",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3 + 1),Math.random() * Math.PI * 2 - Math.PI);
                     }
                     else if(_loc7_ < 0.5)
                     {
                        AddObject("PAPER",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3 + 1),Math.random() * Math.PI * 2 - Math.PI);
                        AddObject("PAPER",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3 + 1),Math.random() * Math.PI * 2 - Math.PI);
                     }
                     else if(_loc7_ < 0.75)
                     {
                        AddObject("COMP",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3 + 1),Math.random() * Math.PI * 2 - Math.PI);
                     }
                     else if(_loc7_ <= 1)
                     {
                        AddObject("COMP_SCREEN",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 3 + 1),Math.random() * Math.PI * 2 - Math.PI);
                     }
                  }
               };
               tmp_mc = _objects_mc;
               break;
            case "TABLE":
               size.x = 18;
               size.y = 10;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new table_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerFragile = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.95;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:Number = NaN;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:b2Vec2 = null;
                  var _loc6_:b2Body = null;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustwood",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = Number(param1.GetUserData().objectData.ObjectSmokeGrade);
                  if(_loc2_ < 2)
                  {
                     _loc2_ = 1;
                  }
                  _loc3_ = param1.GetLinearVelocity();
                  (_loc4_ = new b2Vec2()).x = -6 / 30;
                  _loc4_.y = 0 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_01",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = -0.5 / 30;
                  _loc4_.y = -3.5 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_02",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = 6 / 30;
                  _loc4_.y = 0 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_03",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
               };
               tmp_mc = _objects_mc;
               break;
            case "TABLE_SMALL":
               size.x = 13;
               size.y = 7;
               boxDef.filter.categoryBits = 2;
               bodyDef.userData = new table_small_01();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,40);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerFragile = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 0.95;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:Number = NaN;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:b2Vec2 = null;
                  var _loc6_:b2Body = null;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustwood",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = Number(param1.GetUserData().objectData.ObjectSmokeGrade);
                  if(_loc2_ < 2)
                  {
                     _loc2_ = 1;
                  }
                  _loc3_ = param1.GetLinearVelocity();
                  (_loc4_ = new b2Vec2()).x = -5 / 30;
                  _loc4_.y = 0 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_01",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = -0.5 / 30;
                  _loc4_.y = -3 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_02",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
                  _loc4_.x = 5 / 30;
                  _loc4_.y = 0 / 30;
                  _loc5_ = param1.GetWorldPoint(_loc4_);
                  _loc6_ = AddPolygon("table_debris_03",_loc5_.x,_loc5_.y,param1.GetAngle(),new b2Vec2(_loc3_.x + Math.random() * 4 - 2,_loc3_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  if(param1.GetUserData().objectData.ObjectOnFire)
                  {
                     _Handler_Fires.AddFireToObject(_loc6_);
                  }
                  else
                  {
                     _Handler_Fires.AddSmokeToObject(_loc6_,_loc2_);
                  }
               };
               tmp_mc = _objects_mc;
               break;
            default:
               size.x = 10;
               size.y = 10;
               boxDef.filter.categoryBits = 2;
               boxDef.filter.maskBits = 1;
               bodyDef.userData = new error_mc();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50);
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
         }
         if(reversed)
         {
            bodyDef.userData.scaleX = -1;
         }
         bodyDef.userData.IDNumber = GenerateID();
         bodyDef.userData.tiltValue = 0;
         size.x += 1;
         size.y += 1;
         boxDef.SetAsBox(size.x / 60,size.y / 60);
         boxDef.density = bodyDef.userData.material.Density;
         boxDef.friction = bodyDef.userData.material.Friction;
         boxDef.restitution = bodyDef.userData.material.Restitution;
         if(Boolean(bodyDef.userData.objectData.DrawHitBox) || Boolean(bodyDef.userData.objectData.DrawCloudBox))
         {
            if(type.toUpperCase() == "TABLE")
            {
               bodyDef.userData.objectData.CollisionMC = DrawBoxMC(size.x,5,255,1,0,-2.5);
            }
            else if(type.toUpperCase() == "TABLE_SMALL")
            {
               bodyDef.userData.objectData.CollisionMC = DrawBoxMC(size.x,5,255,1,0,-2);
            }
            else
            {
               bodyDef.userData.objectData.CollisionMC = DrawBoxMC(size.x,size.y);
            }
            bodyDef.userData.objectData.CollisionMC.x = PosX * 30;
            bodyDef.userData.objectData.CollisionMC.y = PosY * 30;
            bodyDef.userData.objectData.CollisionMC.rotation = Angle * (180 / Math.PI);
            if(bodyDef.userData.isLadder == true)
            {
               _static_ladder_hitbox_mc.addChild(bodyDef.userData.objectData.CollisionMC);
            }
            else if(bodyDef.userData.objectData.DrawHitBox)
            {
               _static_objects_hitbox_mc.addChild(bodyDef.userData.objectData.CollisionMC);
            }
            else if(bodyDef.userData.objectData.DrawCloudBox)
            {
               _static_objects_cloud_hitbox_mc.addChild(bodyDef.userData.objectData.CollisionMC);
            }
         }
         if(bodyDef.userData.objectData.DrawShapeMC)
         {
            if(bodyDef.userData.isLadder == true)
            {
               bodyDef.userData.objectData.ShapeMC = DrawBoxMC(size.x,size.y,16737894,0.4);
            }
            else if(type.toUpperCase() == "TABLE")
            {
               bodyDef.userData.objectData.ShapeMC = DrawBoxMC(size.x,5,255,1,0,-2.5);
            }
            else if(type.toUpperCase() == "TABLE_SMALL")
            {
               bodyDef.userData.objectData.ShapeMC = DrawBoxMC(size.x,5,255,1,0,-2);
            }
            else
            {
               bodyDef.userData.objectData.ShapeMC = DrawBoxMC(size.x,size.y,65280,0.4);
            }
            bodyDef.userData.objectData.ShapeMC.x = PosX * 30;
            bodyDef.userData.objectData.ShapeMC.y = PosY * 30;
            bodyDef.userData.objectData.ShapeMC.rotation = Angle * (180 / Math.PI);
            _object_shape_container_mc.addChild(bodyDef.userData.objectData.ShapeMC);
         }
         bodyDef.userData.x = PosX * 30;
         bodyDef.userData.y = PosY * 30;
         bodyDef.userData.rotation = Angle * (180 / Math.PI);
         tmp_mc.addChild(bodyDef.userData);
         body = m_world.CreateBody(bodyDef);
         body.CreateShape(boxDef);
         body.SetMassFromShapes();
         body.SetUserData(bodyDef.userData);
         body.SetLinearVelocity(Velocity);
         body.SetAngularVelocity(AngularVelocity);
         body.GetUserData().objectData.Body = body;
         _Handler_Output.Trace(type.toUpperCase() + " created at (" + Math.round(bodyDef.userData.x) + ", " + Math.round(bodyDef.userData.y) + ")");
         if(type.toUpperCase() == "SPARK")
         {
            body.SetBullet(true);
            if(Velocity.LengthSquared() == 0)
            {
               body.SetLinearVelocity(new b2Vec2(Math.random() * 12 - 6,Math.random() * 10 - 8));
            }
         }
         m_world.AddObjectToLists(body);
         return body;
      }
      
      public function DrawCircleMC(param1:Number, param2:uint = 255, param3:Number = 1) : MovieClip
      {
         var _loc4_:MovieClip = null;
         _loc4_ = new MovieClip();
         _loc4_.graphics.lineStyle(0.5,0,1,false,"none");
         _loc4_.graphics.beginFill(param2,param3);
         _loc4_.graphics.drawCircle(0,0,param1);
         _loc4_.graphics.endFill();
         return _loc4_;
      }
      
      public function AddCircle(param1:String, param2:Number, param3:Number, param4:Number, param5:b2Vec2, param6:Number, param7:Array = null, param8:Boolean = false) : b2Body
      {
         var tmp_mc:MovieClip = null;
         var body:b2Body = null;
         var bodyDef:b2BodyDef = null;
         var circleDef:b2CircleDef = null;
         var radius:Number = NaN;
         var boxDef:* = undefined;
         var type:String = param1;
         var PosX:Number = param2;
         var PosY:Number = param3;
         var Angle:Number = param4;
         var Velocity:b2Vec2 = param5;
         var AngularVelocity:Number = param6;
         var optionalValues:Array = param7;
         var reversed:Boolean = param8;
         if(_locked)
         {
            _queue.push("C",type,PosX,PosY,Angle,Velocity,AngularVelocity,optionalValues);
            return null;
         }
         circleDef = new b2CircleDef();
         radius = 1;
         bodyDef = new b2BodyDef();
         bodyDef.position.x = PosX;
         bodyDef.position.y = PosY;
         switch(type.toUpperCase())
         {
            case "ROLLING_PIPE":
               radius = 27;
               circleDef.filter.categoryBits = 2;
               bodyDef.userData = new rolling_pipe();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.material.Density = 9999;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "STATUE_GLOBE":
               radius = 17;
               circleDef.filter.categoryBits = 2;
               bodyDef.userData = new statue_globe();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "WINDMILL_PROPELLER":
               radius = 20.5;
               circleDef.filter.categoryBits = 2;
               bodyDef.userData = new windmill_propeller();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanGibb = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanBlockFire = true;
               bodyDef.userData.objectData.CanBlockExplosions = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "TUTORIAL_TARGET":
               radius = 5.5;
               circleDef.filter.categoryBits = 2;
               circleDef.filter.maskBits = 1;
               bodyDef.userData = new tutorial_target();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,5,0,1,1,1,false);
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:b2Vec2 = null;
                  var _loc3_:b2Vec2 = null;
                  var _loc4_:b2Vec2 = null;
                  var _loc5_:b2Body = null;
                  _Handler_Sounds.PlaySoundAt_Box2DScale("bustwood",param1.GetPosition().x,param1.GetPosition().y);
                  _loc2_ = param1.GetLinearVelocity();
                  _loc3_ = new b2Vec2();
                  _loc3_.x = -2.5 / 30;
                  _loc3_.y = -2.5 / 30;
                  _loc4_ = param1.GetWorldPoint(_loc3_);
                  _loc5_ = AddPolygon("tutorial_target_debris_01",_loc4_.x,_loc4_.y,param1.GetAngle(),new b2Vec2(_loc2_.x + Math.random() * 4 - 2,_loc2_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  _loc3_.x = 3.5 / 30;
                  _loc3_.y = -0.5 / 30;
                  _loc4_ = param1.GetWorldPoint(_loc3_);
                  _loc5_ = AddPolygon("tutorial_target_debris_02",_loc4_.x,_loc4_.y,param1.GetAngle(),new b2Vec2(_loc2_.x + Math.random() * 4 - 2,_loc2_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
                  _loc3_.x = -0.5 / 30;
                  _loc3_.y = 4.5 / 30;
                  _loc4_ = param1.GetWorldPoint(_loc3_);
                  _loc5_ = AddPolygon("tutorial_target_debris_03",_loc4_.x,_loc4_.y,param1.GetAngle(),new b2Vec2(_loc2_.x + Math.random() * 4 - 2,_loc2_.y - Math.random() * 2),Math.random() * Math.PI * 2 - Math.PI);
               };
               tmp_mc = _objects_mc;
               break;
            case "BEACHBALL":
               radius = 6;
               circleDef.filter.categoryBits = 2;
               bodyDef.userData = new beachball();
               bodyDef.userData.gotoAndStop(1);
               bodyDef.userData.material = _material.Beachball;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,20,0,1,20,50);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.CanGibb = false;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.objectData.KickPower = 1.3;
               bodyDef.userData.objectData.KickWeightCalculation = true;
               bodyDef.userData.objectData.CanCarryFire = true;
               bodyDef.userData.objectData.CanBlockFire = false;
               bodyDef.userData.objectData.CanBlockExplosions = false;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.PlayerBounce = false;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
                  var _loc2_:b2Vec2 = null;
                  _loc2_ = new b2Vec2(param1.GetLinearVelocity().x * 0.2,param1.GetLinearVelocity().y * 0.2);
                  AddObject("BEACHBALL_FLAT",param1.GetPosition().x,param1.GetPosition().y,0,_loc2_,0);
               };
               tmp_mc = _objects_mc;
               break;
            case "COMFY_CHAIR":
               radius = 6.5;
               circleDef.filter.categoryBits = 2;
               bodyDef.userData = new comfy_chair();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = true;
               bodyDef.userData.objectData.CanBurn = true;
               bodyDef.userData.objectData.OnlyBurnWhileWake = true;
               bodyDef.userData.objectData.CrushDamage = 25;
               bodyDef.userData.objectData.CanSmoke = true;
               bodyDef.userData.objectData.AffectedByExplosions = true;
               bodyDef.userData.objectData.LaserVisibleOnObject = true;
               bodyDef.userData.objectData.Kickable = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            case "PLATFORM_MOTOR":
               radius = 30;
               circleDef.filter.categoryBits = 8;
               circleDef.filter.maskBits = 8;
               bodyDef.userData = new blank_mc();
               bodyDef.userData.material = _material.Metal;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,10,0,0,0,0,true);
               bodyDef.userData.objectData.DrawHitBox = false;
               bodyDef.userData.objectData.DrawShapeMC = false;
               bodyDef.userData.objectData.BulletTransparent = true;
               bodyDef.userData.objectData.LaserTransparent = true;
               bodyDef.userData.objectData.AimTransparent = true;
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _objects_mc;
               break;
            default:
               radius = 5;
               circleDef.filter.categoryBits = 2;
               circleDef.filter.maskBits = 1;
               bodyDef.userData = new error_mc();
               bodyDef.userData.material = _material.Wood;
               bodyDef.userData.objectData = new BodyData(bodyDef.userData,_Handler_Deconstructer,50);
               bodyDef.userData.onDestruction = function(param1:b2Body):void
               {
               };
               tmp_mc = _scrap_mc;
         }
         if(reversed)
         {
            bodyDef.userData.scaleX = -1;
         }
         bodyDef.userData.IDNumber = GenerateID();
         bodyDef.userData.tiltValue = 0;
         radius += 0.5;
         circleDef.radius = radius / 30;
         circleDef.density = bodyDef.userData.material.Density;
         circleDef.friction = bodyDef.userData.material.Friction;
         circleDef.restitution = bodyDef.userData.material.Restitution;
         if(bodyDef.userData.objectData.DrawHitBox)
         {
            bodyDef.userData.objectData.CollisionMC = DrawCircleMC(circleDef.radius * 30);
            bodyDef.userData.objectData.CollisionMC.x = PosX * 30;
            bodyDef.userData.objectData.CollisionMC.y = PosY * 30;
            _static_objects_hitbox_mc.addChild(bodyDef.userData.objectData.CollisionMC);
         }
         if(bodyDef.userData.objectData.DrawShapeMC)
         {
            bodyDef.userData.objectData.ShapeMC = DrawCircleMC(circleDef.radius * 30,65280,0.4);
            bodyDef.userData.objectData.ShapeMC.x = PosX * 30;
            bodyDef.userData.objectData.ShapeMC.y = PosY * 30;
            _object_shape_container_mc.addChild(bodyDef.userData.objectData.ShapeMC);
         }
         bodyDef.userData.x = PosX * 30;
         bodyDef.userData.y = PosY * 30;
         tmp_mc.addChild(bodyDef.userData);
         body = m_world.CreateBody(bodyDef);
         body.CreateShape(circleDef);
         if(type.toUpperCase() == "COMFY_CHAIR")
         {
            boxDef = new b2PolygonDef();
            boxDef.filter.categoryBits = 2;
            boxDef.SetAsOrientedBox(14 / 60,9 / 60,new b2Vec2(0,3.5 / 30),0);
            boxDef.density = bodyDef.userData.material.Density;
            boxDef.friction = bodyDef.userData.material.Friction;
            boxDef.restitution = bodyDef.userData.material.Restitution;
            body.CreateShape(boxDef);
         }
         body.SetMassFromShapes();
         body.SetUserData(bodyDef.userData);
         body.SetLinearVelocity(Velocity);
         body.SetAngularVelocity(AngularVelocity);
         body.GetUserData().objectData.Body = body;
         _Handler_Output.Trace(type.toUpperCase() + " created at (" + Math.round(bodyDef.userData.x) + ", " + Math.round(bodyDef.userData.y) + ")");
         m_world.AddObjectToLists(body);
         return body;
      }
      
      public function AddDistanceJoint(param1:b2Body, param2:b2Body, param3:b2Vec2, param4:b2Vec2) : b2DistanceJoint
      {
         var _loc5_:b2DistanceJointDef = null;
         _loc5_ = new b2DistanceJointDef();
         _loc5_.Initialize(param1,param2,param3,param4);
         return m_world.CreateJoint(_loc5_) as b2DistanceJoint;
      }
      
      public function AddGearJoint(param1:b2Body, param2:b2Body, param3:*, param4:*, param5:Number) : b2GearJoint
      {
         var _loc6_:b2GearJointDef = null;
         (_loc6_ = new b2GearJointDef()).body1 = param1;
         _loc6_.body2 = param2;
         _loc6_.joint1 = param3;
         _loc6_.joint2 = param4;
         _loc6_.ratio = param5;
         return m_world.CreateJoint(_loc6_) as b2GearJoint;
      }
      
      public function AddPrismaticJoint(param1:b2Body, param2:b2Body, param3:b2Vec2, param4:b2Vec2) : b2PrismaticJoint
      {
         var _loc5_:b2PrismaticJointDef = null;
         _loc5_ = new b2PrismaticJointDef();
         _loc5_.Initialize(param1,param2,param3,param4);
         return m_world.CreateJoint(_loc5_) as b2PrismaticJoint;
      }
      
      public function DrawBoxMC(param1:Number, param2:Number, param3:uint = 255, param4:Number = 1, param5:Number = 0, param6:Number = 0) : MovieClip
      {
         var _loc7_:MovieClip = null;
         _loc7_ = new MovieClip();
         _loc7_.graphics.lineStyle(0.5,0,1,false,"none");
         _loc7_.graphics.beginFill(param3,param4);
         _loc7_.graphics.moveTo(-param1 / 2 + param5,-param2 / 2 + param6);
         _loc7_.graphics.lineTo(param1 / 2 + param5,-param2 / 2 + param6);
         _loc7_.graphics.lineTo(param1 / 2 + param5,param2 / 2 + param6);
         _loc7_.graphics.lineTo(-param1 / 2 + param5,param2 / 2 + param6);
         _loc7_.graphics.lineTo(-param1 / 2 + param5,-param2 / 2 + param6);
         _loc7_.graphics.endFill();
         return _loc7_;
      }
      
      public function AddRevoluteJoint(param1:b2Body, param2:b2Body, param3:b2Vec2) : b2RevoluteJoint
      {
         var _loc4_:b2RevoluteJointDef = null;
         _loc4_ = new b2RevoluteJointDef();
         _loc4_.Initialize(param1,param2,param3);
         return m_world.CreateJoint(_loc4_) as b2RevoluteJoint;
      }
      
      public function AddLimitedJoint(param1:b2Body, param2:b2Body, param3:b2Vec2, param4:Number, param5:Number) : b2RevoluteJoint
      {
         var _loc6_:b2RevoluteJointDef = null;
         (_loc6_ = new b2RevoluteJointDef()).lowerAngle = -param4 / (180 / Math.PI);
         _loc6_.upperAngle = param5 / (180 / Math.PI);
         _loc6_.enableLimit = true;
         _loc6_.Initialize(param1,param2,param3);
         return m_world.CreateJoint(_loc6_) as b2RevoluteJoint;
      }
      
      public function Lock() : void
      {
         _locked = true;
      }
      
      public function AddRevoluteMotor(param1:b2Body, param2:b2Body, param3:b2Vec2, param4:Number, param5:Number) : b2RevoluteJoint
      {
         var _loc6_:b2RevoluteJointDef = null;
         (_loc6_ = new b2RevoluteJointDef()).motorSpeed = param4;
         _loc6_.maxMotorTorque = param5;
         _loc6_.enableMotor = true;
         _loc6_.Initialize(param1,param2,param3);
         return m_world.CreateJoint(_loc6_) as b2RevoluteJoint;
      }
      
      public function get Material() : MaterialsData
      {
         return _material;
      }
      
      public function set Setb2World(param1:b2World) : void
      {
         m_world = param1;
         _ground = m_world.GetGroundBody();
      }
      
      public function set LinkDeconstructer(param1:Deconstructer) : void
      {
         _Handler_Deconstructer = param1;
      }
      
      public function DrawPolyMC(param1:Array, param2:uint = 255, param3:Number = 1) : MovieClip
      {
         var _loc4_:MovieClip = null;
         var _loc5_:* = undefined;
         _loc4_ = new MovieClip();
         _loc4_.graphics.lineStyle(0.5,0,1,false,"none");
         _loc4_.graphics.beginFill(param2,param3);
         _loc4_.graphics.moveTo(param1[0][0] * 30,param1[0][1] * 30);
         _loc5_ = 1;
         while(_loc5_ < param1.length)
         {
            _loc4_.graphics.lineTo(param1[_loc5_][0] * 30,param1[_loc5_][1] * 30);
            _loc5_++;
         }
         _loc4_.graphics.lineTo(param1[0][0] * 30,param1[0][1] * 30);
         _loc4_.graphics.endFill();
         return _loc4_;
      }
      
      public function AddHangingLamp(param1:Point, param2:Number) : Rope
      {
         var lampPoint:Point = null;
         var lamp:b2Body = null;
         var rope:Rope = null;
         var layer_mc:MovieClip = null;
         var ceilPoint:Point = param1;
         var lineLength:Number = param2;
         lampPoint = new Point(ceilPoint.x,ceilPoint.y + lineLength);
         lamp = AddObject("HANGING_LAMP",lampPoint.x / 30,(lampPoint.y + 4) / 30,0,new b2Vec2(0,0),0);
         AddDistanceJoint(Ground,lamp,new b2Vec2(ceilPoint.x / 30,ceilPoint.y / 30),new b2Vec2(lamp.GetPosition().x,lamp.GetPosition().y - 4 / 30));
         lamp.ApplyForce(new b2Vec2(Math.random() * 4 - 2,Math.random()),new b2Vec2(lamp.GetPosition().x,lamp.GetPosition().y));
         rope = new Rope(Ground,lamp,new b2Vec2(ceilPoint.x / 30,ceilPoint.y / 30),new b2Vec2(lampPoint.x / 30,lampPoint.y / 30));
         layer_mc = MovieClip(_dynamic_mc.getChildByName("OBJECTS"));
         layer_mc.addChild(rope.MC);
         lamp.GetUserData().onDestruction = function(param1:b2Body):void
         {
            var _loc2_:b2Vec2 = null;
            var _loc3_:b2Vec2 = null;
            var _loc4_:b2Body = null;
            _Handler_Sounds.PlaySoundAt_Box2DScale("bustglass",param1.GetPosition().x,param1.GetPosition().y);
            _Handler_Sounds.PlaySoundAt_Box2DScale("ELECTRIC_SPARK",param1.GetPosition().x,param1.GetPosition().y);
            _Handler_Effects.AddEffectAt_Box2DScale("ELECTRIC_SPARK",param1.GetPosition().x,param1.GetPosition().y);
            _loc2_ = new b2Vec2();
            _loc2_.x = 0;
            _loc2_.y = 4 / 30;
            _loc3_ = param1.GetWorldPoint(_loc2_);
            AddBox("SPARK",_loc3_.x,_loc3_.y,0,new b2Vec2(Math.random() * 10 - 5,Math.random()),Math.random() * Math.PI);
            AddBox("SPARK",_loc3_.x - 1 / 30,_loc3_.y,0,new b2Vec2(Math.random() * 10 - 5,Math.random()),Math.random() * Math.PI);
            AddBox("SPARK",_loc3_.x + 1 / 30,_loc3_.y,0,new b2Vec2(Math.random() * 10 - 5,Math.random()),Math.random() * Math.PI);
            AddBox("SPARK",_loc3_.x - 2 / 30,_loc3_.y,0,new b2Vec2(Math.random() * 10 - 5,Math.random()),Math.random() * Math.PI);
            AddBox("SPARK",_loc3_.x + 2 / 30,_loc3_.y,0,new b2Vec2(Math.random() * 10 - 5,Math.random()),Math.random() * Math.PI);
            rope.Remove();
            _loc4_ = AddObject("HANGING_LAMP_B",param1.GetPosition().x,param1.GetPosition().y,param1.GetAngle(),param1.GetLinearVelocity(),param1.GetAngularVelocity());
            _loc2_.x = 0;
            _loc2_.y = -4 / 30;
            _loc3_ = param1.GetWorldPoint(_loc2_);
            AddDistanceJoint(Ground,_loc4_,new b2Vec2(ceilPoint.x / 30,ceilPoint.y / 30),new b2Vec2(_loc3_.x,_loc3_.y));
            rope.BuildRope(Ground,_loc4_,new b2Vec2(ceilPoint.x / 30,ceilPoint.y / 30),new b2Vec2(_loc3_.x,_loc3_.y));
            layer_mc.addChild(rope.MC);
         };
         return rope;
      }
      
      private function GenerateID() : int
      {
         _idGiver += 1;
         return _idGiver;
      }
      
      public function CreateGroundPolygon(param1:MaterialData, param2:Number, param3:Number, param4:Number, param5:Array, param6:Array = null) : b2Body
      {
         var _loc7_:b2Body = null;
         var _loc8_:b2BodyDef = null;
         var _loc9_:* = undefined;
         var _loc10_:* = undefined;
         param5 = IncreaseCorners(param5);
         _loc9_ = new b2PolygonDef();
         _loc8_ = new b2BodyDef();
         _loc8_.position.Set(param2,param3);
         _loc8_.angle = param4;
         _loc8_.userData = new Object();
         _loc8_.userData.IDNumber = GenerateID();
         _loc8_.userData.material = param1;
         _loc8_.userData.tiltValue = 0;
         _loc8_.userData.allowCover = false;
         if(param6 == null)
         {
            _loc8_.userData.shapeMC = DrawPolyMC(param5,16711935);
         }
         else if(param6[0] == "CLOUD")
         {
            _loc8_.userData.shapeMC = DrawPolyMC(param5,16711782);
         }
         else if(param6[0] == "LADDER")
         {
            _loc8_.userData.shapeMC = DrawPolyMC(param5,16737894);
         }
         else
         {
            _loc8_.userData.shapeMC = DrawPolyMC(param5,16711935);
            param6 = null;
         }
         _loc8_.userData.shapeMC.x = param2 * 30;
         _loc8_.userData.shapeMC.y = param3 * 30;
         _loc8_.userData.shapeMC.rotation = param4 * (180 / Math.PI);
         _loc9_.vertexCount = param5.length;
         _loc10_ = 0;
         while(_loc10_ < param5.length)
         {
            _loc9_.vertices[_loc10_] = new b2Vec2(param5[_loc10_][0],param5[_loc10_][1]);
            _loc10_++;
         }
         _loc9_.friction = _loc8_.userData.material.Friction;
         _loc9_.restitution = _loc8_.userData.material.Restitution;
         _loc9_.density = 0;
         if(param6 != null)
         {
            if(param6[0] == "LADDER")
            {
               _loc9_.filter.categoryBits = 2;
               _loc9_.filter.maskBits = 1;
               _loc8_.userData.isLadder = true;
            }
            if(param6[0] == "CLOUD")
            {
               _loc9_.filter.isCloud = true;
               _loc8_.userData.isCloud = true;
            }
         }
         _loc7_ = m_world.CreateBody(_loc8_);
         _loc7_.CreateShape(_loc9_);
         _loc7_.SetMassFromShapes();
         _loc7_.SetUserData(_loc8_.userData);
         if(param6 == null)
         {
            _static_world_hitbox_mc.addChild(_loc7_.GetUserData().shapeMC);
         }
         else if(param6[0] == "CLOUD")
         {
            _static_world_cloud_hitbox_mc.addChild(_loc7_.GetUserData().shapeMC);
         }
         else if(param6[0] == "LADDER")
         {
            _static_ladder_hitbox_mc.addChild(_loc7_.GetUserData().shapeMC);
         }
         return _loc7_;
      }
   }
}

