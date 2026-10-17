package Code.Handler
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Box2D.Dynamics.Joints.*;
   import Code.Data.*;
   import Code.Data.Weapons.*;
   import Code.Particles.*;
   import flash.display.*;
   import flash.geom.*;
   
   public class Maps
   {
      public static var TOTAL_MAPS:int = 5;
      
      private var MapStart:Function;
      
      private var _static_mc:MovieClip;
      
      private var mapArea:Rectangle;
      
      public var TutorialOver:Boolean = false;
      
      private var pathGrid:PathGrid;
      
      private var _Handler_Effects:Effects;
      
      private var _mapStartTimer:int = 2;
      
      private var playerSpawns:Array;
      
      private var portals:Array;
      
      private var weaponSpawns:Array;
      
      public var MapUpdate:Function;
      
      private var m_contactListener:b2ContactListener;
      
      public var Handler_WorldItems:MapPremadeItems;
      
      private var _dynamic_mc:MovieClip;
      
      private var _Handler_Players:PlayersKeeper;
      
      private var _Handler_Sounds:Sounds;
      
      private var m_world:b2World;
      
      private var _Handler_Weapons:Weapons;
      
      private var mapGraphic:MapGraphic;
      
      private var _Handler_Output:OutputTrace;
      
      public var MapEnd:Function;
      
      public function Maps(param1:OutputTrace)
      {
         TutorialOver = false;
         _mapStartTimer = 2;
         super();
         Handler_WorldItems = new MapPremadeItems(param1);
         _Handler_Output = param1;
         _Handler_Output.Trace("Maps Handler Created");
      }
      
      public function GetWeaponSpawns(param1:Number = 0) : Array
      {
         return weaponSpawns;
      }
      
      public function GetLevelMC(param1:String) : MovieClip
      {
         var _loc2_:MovieClip = null;
         _loc2_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName(param1));
         if(_loc2_ == null)
         {
         }
         return _loc2_;
      }
      
      private function GenerateMapTutorial() : void
      {
         var instructions:MovieClip = null;
         var t_1_logic:MapLogic = null;
         var t_1_initialized:Boolean = false;
         var t_1_moved_right:Boolean = false;
         var t_1_moved_left:Boolean = false;
         var t_1_p_prev_x:Number = NaN;
         var t_2_logic:MapLogic = null;
         var t_2_jumped:Boolean = false;
         var t_2_crouched:Boolean = false;
         var t_3_logic:MapLogic = null;
         var t_4_logic:MapLogic = null;
         var t_4_initialized:Boolean = false;
         var t_4_moved_right:Boolean = false;
         var t_4_moved_left:Boolean = false;
         var t_4_p_prev_x:Number = NaN;
         var t_5_logic:MapLogic = null;
         var wpnPosX:Number = NaN;
         var tutorial_weapon:b2Body = null;
         var t_6_logic:MapLogic = null;
         var t_8_targets:Array = null;
         var t_7_logic:MapLogic = null;
         var t_8_logic:MapLogic = null;
         var t_10_targets:Array = null;
         var t_9_logic:MapLogic = null;
         var t_10_logic:MapLogic = null;
         var t_12_targets:Array = null;
         var t_11_logic:MapLogic = null;
         var t_12_logic:MapLogic = null;
         var tutorial_crate:b2Body = null;
         var t_13_logic:MapLogic = null;
         var t_14_logic:MapLogic = null;
         var t_15_logic:MapLogic = null;
         mapArea = new Rectangle(1,-25,347,260);
         playerSpawns = new Array(new Point(169,198));
         weaponSpawns = new Array();
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-34 / 30,105 / 30,0,110 / 30,358 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,196 / 30,-35 / 30,0,452 / 30,104 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,183.5 / 30,254 / 30,0,469 / 30,92 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,389 / 30,103 / 30,0,122 / 30,381 / 30,new Array("NONE"));
         pathGrid.AddNode(new PathNode("",26,204,"",null));
         pathGrid.AddNode(new PathNode("",60,204,"",null));
         pathGrid.AddNode(new PathNode("",94,204,"",null));
         pathGrid.AddNode(new PathNode("",129,204,"",null));
         pathGrid.AddNode(new PathNode("",163,204,"",null));
         pathGrid.AddNode(new PathNode("",198,204,"",null));
         pathGrid.AddNode(new PathNode("",231,204,"",null));
         pathGrid.AddNode(new PathNode("",266,204,"",null));
         pathGrid.AddNode(new PathNode("",298,204,"",null));
         pathGrid.AddNode(new PathNode("",323,204,"",null));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         TutorialOver = false;
         instructions = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("INSTRUCTIONS"));
         t_1_logic = new MapLogic();
         t_1_logic.RefireInterval = 40;
         t_1_initialized = false;
         t_1_moved_right = false;
         t_1_moved_left = false;
         t_1_logic.OnUpdate = function():void
         {
            if(!t_1_initialized)
            {
               _Handler_Players.Players[0].State.CurrentRangeWeapon = null;
               _Handler_Players.Players[0].State.CurrentThrowableWeapon.Ammo = 0;
               _Handler_Players.Players[0].UpdateGUI();
               t_1_initialized = true;
            }
            else
            {
               if(t_1_p_prev_x - 1 > _Handler_Players.Players[0].MidPosX())
               {
                  t_1_moved_left = true;
               }
               else if(t_1_p_prev_x + 1 < _Handler_Players.Players[0].MidPosX())
               {
                  t_1_moved_right = true;
               }
               if(t_1_moved_left && t_1_moved_right)
               {
                  t_1_logic.Stop();
                  instructions.gotoAndStop(2);
                  t_2_logic.Start();
               }
            }
            t_1_p_prev_x = _Handler_Players.Players[0].MidPosX();
         };
         t_1_logic.Start();
         t_2_logic = new MapLogic();
         t_2_logic.RefireInterval = 40;
         t_2_jumped = false;
         t_2_crouched = false;
         t_2_logic.OnUpdate = function():void
         {
            if(Boolean(_Handler_Players.Players[0].State.Jumping))
            {
               t_2_jumped = true;
            }
            if(Boolean(_Handler_Players.Players[0].State.Kneeling))
            {
               t_2_crouched = true;
            }
            if(t_2_jumped && t_2_crouched)
            {
               t_2_logic.Stop();
               instructions.gotoAndStop(3);
               t_3_logic.Start();
            }
         };
         t_3_logic = new MapLogic();
         t_3_logic.RefireInterval = 80;
         t_3_logic.OnUpdate = function():void
         {
            if(Boolean(_Handler_Players.Players[0].State.Rolling))
            {
               t_3_logic.Stop();
               instructions.gotoAndStop(4);
               t_4_logic.Start();
            }
         };
         t_4_logic = new MapLogic();
         t_4_logic.RefireInterval = 40;
         t_4_initialized = false;
         t_4_moved_right = false;
         t_4_moved_left = false;
         t_4_logic.OnUpdate = function():void
         {
            if(!t_4_initialized)
            {
               t_4_initialized = true;
            }
            else if(Boolean(_Handler_Players.Players[0].State.Sprinting))
            {
               if(t_4_p_prev_x - 0.5 > _Handler_Players.Players[0].MidPosX())
               {
                  t_4_moved_left = true;
               }
               else if(t_4_p_prev_x + 0.5 < _Handler_Players.Players[0].MidPosX())
               {
                  t_4_moved_right = true;
               }
               if(t_4_moved_left && t_4_moved_right)
               {
                  t_4_logic.Stop();
                  instructions.gotoAndStop(5);
                  t_5_logic.Start();
               }
            }
            t_4_p_prev_x = _Handler_Players.Players[0].MidPosX();
         };
         t_5_logic = new MapLogic();
         t_5_logic.RefireInterval = 80;
         t_5_logic.OnUpdate = function():void
         {
            if(Boolean(_Handler_Players.Players[0].State.Diving))
            {
               t_5_logic.Stop();
               instructions.gotoAndStop(6);
               if(_Handler_Players.Players[0].MidPosX() < 170)
               {
                  playerSpawns = new Array(new Point(_Handler_Players.Players[0].MidPosX() + 60,198));
               }
               else
               {
                  playerSpawns = new Array(new Point(_Handler_Players.Players[0].MidPosX() - 60,198));
               }
               _Handler_Players.AddBot(3,0,1);
               _Handler_Players.Players[1].Stop();
               t_6_logic.Start();
            }
         };
         t_6_logic = new MapLogic();
         t_6_logic.OnUpdate = function():void
         {
            if(_Handler_Players.Players[1].State.HP <= 0)
            {
               t_6_logic.Stop();
               if(_Handler_Players.Players[0].MidPosX() < 170)
               {
                  wpnPosX = _Handler_Players.Players[0].MidPosX() + 60;
               }
               else
               {
                  wpnPosX = _Handler_Players.Players[0].MidPosX() - 60;
               }
               tutorial_weapon = Handler_WorldItems.AddPolygon("wpn_pistol",wpnPosX / 30,203 / 30,0,new b2Vec2(),0);
               tutorial_weapon.GetUserData().weaponData = _Handler_Weapons.Pistol;
               tutorial_weapon.GetUserData().weaponData.InfiniteAmmo = true;
               tutorial_weapon.PutToSleep();
               instructions.gotoAndStop(7);
               t_7_logic.Start();
            }
         };
         t_8_targets = new Array();
         t_7_logic = new MapLogic();
         t_7_logic.OnUpdate = function():void
         {
            var _loc1_:MovieClip = null;
            if(tutorial_weapon.GetUserData().destroyed == true)
            {
               t_7_logic.Stop();
               instructions.gotoAndStop(8);
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_1"));
               t_8_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_2"));
               t_8_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_3"));
               t_8_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               t_8_targets[0].PutToSleep();
               t_8_targets[1].PutToSleep();
               t_8_targets[2].PutToSleep();
               t_8_logic.Start();
            }
         };
         t_8_logic = new MapLogic();
         t_8_logic.OnUpdate = function():void
         {
            var _loc1_:int = 0;
            _loc1_ = 0;
            while(_loc1_ < t_8_targets.length)
            {
               if(t_8_targets[_loc1_].GetUserData().destroyed != true)
               {
                  return;
               }
               _loc1_++;
            }
            t_8_logic.Stop();
            if(_Handler_Players.Players[0].MidPosX() < 170)
            {
               wpnPosX = _Handler_Players.Players[0].MidPosX() + 60;
            }
            else
            {
               wpnPosX = _Handler_Players.Players[0].MidPosX() - 60;
            }
            tutorial_weapon = Handler_WorldItems.AddPolygon("wpn_rifle",wpnPosX / 30,203 / 30,0,new b2Vec2(),0);
            tutorial_weapon.GetUserData().weaponData = _Handler_Weapons.Rifle;
            tutorial_weapon.GetUserData().weaponData.InfiniteAmmo = true;
            tutorial_weapon.PutToSleep();
            instructions.gotoAndStop(9);
            t_9_logic.Start();
         };
         t_10_targets = new Array();
         t_9_logic = new MapLogic();
         t_9_logic.OnUpdate = function():void
         {
            var _loc1_:MovieClip = null;
            if(tutorial_weapon.GetUserData().destroyed == true)
            {
               t_9_logic.Stop();
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_1"));
               t_10_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_3"));
               t_10_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_4"));
               t_10_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET_R",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("TARGET_5"));
               t_10_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET_R",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               t_10_targets[0].PutToSleep();
               t_10_targets[1].PutToSleep();
               t_10_targets[2].PutToSleep();
               t_10_targets[3].PutToSleep();
               instructions.gotoAndStop(10);
               t_10_logic.Start();
            }
         };
         t_10_logic = new MapLogic();
         t_10_logic.OnUpdate = function():void
         {
            var _loc1_:int = 0;
            _loc1_ = 0;
            while(_loc1_ < t_10_targets.length)
            {
               if(t_10_targets[_loc1_].GetUserData().destroyed != true)
               {
                  return;
               }
               _loc1_++;
            }
            t_10_logic.Stop();
            if(_Handler_Players.Players[0].MidPosX() < 170)
            {
               wpnPosX = 170 + 40;
            }
            else
            {
               wpnPosX = 170 - 40;
            }
            tutorial_weapon = Handler_WorldItems.AddPolygon("wpn_grenades",wpnPosX / 30,203 / 30,0,new b2Vec2(),0);
            tutorial_weapon.GetUserData().weaponData = _Handler_Weapons.Grenades;
            tutorial_weapon.GetUserData().weaponData.InfiniteAmmo = true;
            tutorial_weapon.PutToSleep();
            instructions.gotoAndStop(11);
            t_11_logic.Start();
         };
         t_12_targets = new Array();
         t_11_logic = new MapLogic();
         t_11_logic.RefireInterval = 40;
         t_11_logic.OnUpdate = function():void
         {
            var _loc1_:MovieClip = null;
            if(_Handler_Players.Players[0].State.CurrentRangeWeapon != null && !_Handler_Players.Players[0].State.Aiming)
            {
               _Handler_Players.Players[0].State.CurrentRangeWeapon = null;
               _Handler_Players.Players[0].UpdateGUI();
            }
            if(tutorial_weapon.GetUserData().destroyed == true)
            {
               t_11_logic.Stop();
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("GRENADE_1"));
               t_12_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("GRENADE_2"));
               t_12_targets.push(Handler_WorldItems.AddObject("TUTORIAL_TARGET_R",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0));
               t_12_targets[0].PutToSleep();
               t_12_targets[1].PutToSleep();
               instructions.gotoAndStop(12);
               t_12_logic.Start();
            }
         };
         t_12_logic = new MapLogic();
         t_12_logic.OnUpdate = function():void
         {
            var _loc1_:int = 0;
            var _loc2_:MovieClip = null;
            _loc1_ = 0;
            while(_loc1_ < t_12_targets.length)
            {
               if(t_12_targets[_loc1_].GetUserData().destroyed != true)
               {
                  return;
               }
               _loc1_++;
            }
            t_12_logic.Stop();
            _loc2_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("CRATE"));
            tutorial_crate = Handler_WorldItems.AddObject("CRATE",_loc2_.x / 30,_loc2_.y / 30,0,new b2Vec2(),0);
            instructions.gotoAndStop(13);
            t_13_logic.Start();
         };
         t_13_logic = new MapLogic();
         t_13_logic.RefireInterval = 40;
         t_13_logic.OnUpdate = function():void
         {
            var _loc1_:MovieClip = null;
            if(_Handler_Players.Players[0].State.CurrentThrowableWeapon.Ammo > 0 && !_Handler_Players.Players[0].State.Aiming)
            {
               _Handler_Players.Players[0].State.CurrentThrowableWeapon.InfiniteAmmo = false;
               _Handler_Players.Players[0].State.CurrentThrowableWeapon.Ammo = 0;
               _Handler_Players.Players[0].UpdateGUI();
            }
            if(Boolean(tutorial_crate.GetUserData().destroyed))
            {
               _loc1_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("CRATE"));
               tutorial_crate = Handler_WorldItems.AddObject("CRATE",_loc1_.x / 30,_loc1_.y / 30,0,new b2Vec2(),0);
            }
            if(Boolean(_Handler_Players.Players[0].State.TakingCover))
            {
               t_13_logic.Stop();
               if(_Handler_Players.Players[0].MidPosX() < 170)
               {
                  wpnPosX = _Handler_Players.Players[0].MidPosX() + 65;
               }
               else
               {
                  wpnPosX = _Handler_Players.Players[0].MidPosX() - 65;
               }
               tutorial_weapon = Handler_WorldItems.AddPolygon("wpn_rifle",(wpnPosX - 15) / 30,203 / 30,0,new b2Vec2(),0);
               tutorial_weapon.GetUserData().weaponData = _Handler_Weapons.Rifle;
               tutorial_weapon.PutToSleep();
               tutorial_weapon = Handler_WorldItems.AddPolygon("WPN_SLOWMO_10",(wpnPosX + 15) / 30,203 / 30,0,new b2Vec2(),0);
               tutorial_weapon.GetUserData().weaponData = _Handler_Weapons.Slowmo10;
               tutorial_weapon.PutToSleep();
               instructions.gotoAndStop(14);
               t_14_logic.Start();
            }
         };
         t_14_logic = new MapLogic();
         t_14_logic.OnUpdate = function():void
         {
            if(tutorial_weapon.GetUserData().destroyed == true)
            {
               t_14_logic.Stop();
               instructions.gotoAndStop(15);
               t_15_logic.Start();
            }
         };
         t_15_logic = new MapLogic();
         t_15_logic.OnUpdate = function():void
         {
            if(_Handler_Players.Players[0].State.CurrentPowerupWeapon == null)
            {
               t_15_logic.Stop();
               instructions.gotoAndStop(16);
               TutorialOver = true;
            }
         };
         MapUpdate = function(param1:Number):void
         {
            var _loc2_:MovieClip = null;
            if(_Handler_Players.Players[0].State.HP <= 0)
            {
               _loc2_ = MovieClip(MovieClip(_dynamic_mc.getChildByName("LEVEL")).getChildByName("REVIVE"));
               _Handler_Players.Players[0].Revive(_loc2_.x,_loc2_.y);
            }
         };
         MapEnd = function():void
         {
            t_1_logic.Stop();
            t_2_logic.Stop();
            t_3_logic.Stop();
            t_4_logic.Stop();
            t_5_logic.Stop();
            t_6_logic.Stop();
            t_7_logic.Stop();
            t_8_logic.Stop();
            t_9_logic.Stop();
            t_10_logic.Stop();
            t_11_logic.Stop();
            t_12_logic.Stop();
            t_13_logic.Stop();
            t_14_logic.Stop();
            t_15_logic.Stop();
         };
      }
      
      public function UpdateWorldObjectList() : void
      {
         m_world.UpdateObjectLists();
      }
      
      public function UpdateMCs(param1:MovieClip, param2:MovieClip, param3:MovieClip) : void
      {
         _static_mc = param1;
         _dynamic_mc = param2;
         Handler_WorldItems.UpdateMCs(_static_mc,_dynamic_mc,param3);
      }
      
      private function GenerateMap04Mall() : void
      {
         var rampL:b2Body = null;
         var rampR:b2Body = null;
         var mall_elevator_01_back:b2Body = null;
         var mall_elevator_01_part:b2Body = null;
         var mall_motor_1:b2Body = null;
         var mall_motor_1_joint:b2RevoluteJoint = null;
         var mall_elevator_1_anchor:b2Vec2 = null;
         var mall_motor_1_anchor:b2Vec2 = null;
         var btn_01:b2Body = null;
         var btn_02:b2Body = null;
         var btn_03:b2Body = null;
         var mall_elevator_logic_up:MapLogic = null;
         var mall_elevator_logic_down:MapLogic = null;
         mapArea = new Rectangle(-539,-424,1098,821);
         playerSpawns = new Array(new Point(403,19),new Point(404,-44),new Point(309,143),new Point(-114,19),new Point(-241,-45),new Point(-272,148),new Point(19,149),new Point(-43,-45),new Point(70,-44),new Point(55,20));
         portals = new Array(new PortalData(new Rectangle(-177,5,12,23),new Rectangle(-199,91,12,23),new Point(-1,0),false,false),new PortalData(new Rectangle(-199,91,12,23),new Rectangle(-177,5,12,23),new Point(1,0),false,false),new PortalData(new Rectangle(463,6,11,22),new Rectangle(463,-58,11,22),new Point(1,0),true,false),new PortalData(new Rectangle(463,-58,11,22),new Rectangle(463,6,11,22),new Point(1,0),true,false));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,114 / 30,-133 / 30,0,new Array([2 / 30,2 / 30],[-3 / 30,2 / 30],[-3 / 30,0 / 30],[-1 / 30,-2 / 30],[2 / 30,-2 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,151.5 / 30,-133 / 30,0,5 / 30,4 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,221.5 / 30,-133 / 30,0,5 / 30,4 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,291.5 / 30,-133 / 30,0,5 / 30,4 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,329 / 30,-133 / 30,0,new Array([-2 / 30,2 / 30],[-2 / 30,-2 / 30],[1 / 30,-2 / 30],[3 / 30,0 / 30],[3 / 30,2 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,-295 / 30,-133 / 30,0,new Array([-3 / 30,2 / 30],[-3 / 30,0 / 30],[-1 / 30,-2 / 30],[2 / 30,-2 / 30],[2 / 30,2 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-257.5 / 30,-133 / 30,0,5 / 30,4 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,-220 / 30,-133 / 30,0,new Array([-2 / 30,2 / 30],[-2 / 30,-2 / 30],[1 / 30,-2 / 30],[3 / 30,0 / 30],[3 / 30,2 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-46.5 / 30,-32 / 30,0,129 / 30,8 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,69.5 / 30,-32 / 30,0,39 / 30,8 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-258.5 / 30,-33 / 30,0,127 / 30,6 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-182 / 30,-15.5 / 30,0,34 / 30,41 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-154.5 / 30,-32 / 30,0,22 / 30,8 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-188 / 30,48 / 30,0,22 / 30,86 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-182 / 30,116 / 30,0,34 / 30,4 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-176 / 30,88.5 / 30,0,22 / 30,59 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-105 / 30,43.5 / 30,0,164 / 30,31 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,22.5 / 30,50.5 / 30,0,133 / 30,45 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,22.5 / 30,98.5 / 30,0,133 / 30,9 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-36 / 30,184.5 / 30,0,572 / 30,51 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,447 / 30,185 / 30,0,156 / 30,52 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-345.5 / 30,187 / 30,0,84 / 30,46 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-403.5 / 30,54.5 / 30,0,75 / 30,311 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-366 / 30,-134 / 30,0,80 / 30,107 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-318 / 30,-80 / 30,0,8 / 30,39 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,-321 / 30,-101 / 30,0,new Array([7 / 30,21 / 30],[-15 / 30,21 / 30],[-5 / 30,-23 / 30],[7 / 30,-11 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,-74 / 30,-107 / 30,0,new Array([-123 / 30,15 / 30],[-123 / 30,-5 / 30],[-111 / 30,-17 / 30],[155 / 30,-17 / 30],[167 / 30,-5 / 30],[167 / 30,15 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-52 / 30,-153 / 30,0,266 / 30,68 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,426.5 / 30,65.5 / 30,0,145 / 30,75 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,480.5 / 30,132 / 30,0,35 / 30,70 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,422.5 / 30,-32 / 30,0,137 / 30,8 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,398 / 30,-152 / 30,0,72 / 30,70 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,394 / 30,-105 / 30,0,new Array([-44 / 30,13 / 30],[-44 / 30,-7 / 30],[-32 / 30,-19 / 30],[69 / 30,-19 / 30],[69 / 30,13 / 30]),new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,477 / 30,-91 / 30,0,28 / 30,65 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,483 / 30,-47 / 30,0,17 / 30,34 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,478 / 30,-14 / 30,0,30 / 30,38 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,483 / 30,18 / 30,0,17 / 30,37 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-318 / 30,49 / 30,0,8 / 30,170 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,345 / 30,47.5 / 30,0,18 / 30,207 / 30,new Array("LADDER"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,95 / 30,99 / 30,0,8 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,123 / 30,99 / 30,0,8 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,95 / 30,129 / 30,0,8 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,123 / 30,129 / 30,0,8 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,-212 / 30,124 / 30,0,new Array([-7 / 30,10 / 30],[-11 / 30,10 / 30],[-11 / 30,9 / 30],[8 / 30,-10 / 30],[11 / 30,-10 / 30],[11 / 30,-8 / 30]),new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-200.5 / 30,115 / 30,0,7 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,-54.5 / 30,101 / 30,0,21 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,317.5 / 30,180.5 / 30,0,157 / 30,59 / 30,new Array("NONE"));
         rampL = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,236 / 30,156 / 30,0,new Array([-6 / 30,3 / 30],[2 / 30,-5 / 30],[3 / 30,-5 / 30],[3 / 30,3 / 30]),new Array("NONE"));
         rampL.GetUserData().tiltValue = -2;
         rampR = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,399 / 30,157 / 30,0,new Array([6 / 30,2 / 30],[-3 / 30,2 / 30],[-3 / 30,-6 / 30],[-2 / 30,-6 / 30]),new Array("NONE"));
         rampR.GetUserData().tiltValue = 2;
         if(65 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("BARREL_EXPLOSIVE",313 / 30,146 / 30,1.5707963267948966,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("BARREL,BARREL_EXPLOSIVE",387 / 30,143 / 30,0,new b2Vec2(),0);
         }
         if(20 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE",249 / 30,128 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",264 / 30,128 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",249 / 30,113 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",264 / 30,113 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",257 / 30,98 / 30,0,new b2Vec2(),0);
         }
         Handler_WorldItems.AddObject("CRATE",249 / 30,143 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE",264 / 30,143 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL,CRATE",279 / 30,143 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE",455 / 30,152 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE",440 / 30,152 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE",450 / 30,137 / 30,-1.5707963267948966,new b2Vec2(),0);
         Handler_WorldItems.AddObject("TABLE",369 / 30,146 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,BARREL,BARREL_WRECK",140 / 30,152 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE",160 / 30,154 / 30,1.5707963267948966,new b2Vec2(),0);
         mall_elevator_01_back = Handler_WorldItems.AddBox("ELEVATOR_01",-344.5 / 30,-54 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddPrismaticJoint(Handler_WorldItems.Ground,mall_elevator_01_back,new b2Vec2(-344.5 / 30,-54 / 30),new b2Vec2(0,1));
         mall_elevator_01_part = Handler_WorldItems.AddBox("SOLID_INVISIBLE_METAL",-363 / 30,-54 / 30,0,new b2Vec2(),0,new Array(2,42));
         Handler_WorldItems.AddLimitedJoint(mall_elevator_01_part,mall_elevator_01_back,new b2Vec2(-363 / 30,-54 / 30),0,0);
         mall_elevator_01_part = Handler_WorldItems.AddBox("SOLID_INVISIBLE_METAL",-360.5 / 30,-73.5 / 30,0,new b2Vec2(),0,new Array(7,3));
         Handler_WorldItems.AddLimitedJoint(mall_elevator_01_part,mall_elevator_01_back,new b2Vec2(-360.5 / 30,-73.5 / 30),0,0);
         mall_elevator_01_part = Handler_WorldItems.AddBox("SOLID_INVISIBLE_METAL_GIB",-344.5 / 30,-34.5 / 30,0,new b2Vec2(),0,new Array(39,3));
         Handler_WorldItems.AddLimitedJoint(mall_elevator_01_part,mall_elevator_01_back,new b2Vec2(-344.5 / 30,-34.5 / 30),0,0);
         mall_elevator_01_part = Handler_WorldItems.AddBox("SOLID_INVISIBLE_METAL",-328.5 / 30,-73.5 / 30,0,new b2Vec2(),0,new Array(7,3));
         Handler_WorldItems.AddLimitedJoint(mall_elevator_01_part,mall_elevator_01_back,new b2Vec2(-328.5 / 30,-73.5 / 30),0,0);
         mall_elevator_01_part = Handler_WorldItems.AddBox("SOLID_INVISIBLE_METAL",-326 / 30,-68 / 30,0,new b2Vec2(),0,new Array(2,14));
         Handler_WorldItems.AddLimitedJoint(mall_elevator_01_part,mall_elevator_01_back,new b2Vec2(-326 / 30,-68 / 30),0,0);
         mall_motor_1 = Handler_WorldItems.AddCircle("PLATFORM_MOTOR",-344.5 / 30,-300 / 30,0,new b2Vec2(),0);
         mall_motor_1_joint = Handler_WorldItems.AddRevoluteMotor(Handler_WorldItems.Ground,mall_motor_1,new b2Vec2(-344.5 / 30,-300 / 30),-0.3,1000);
         mall_elevator_1_anchor = new b2Vec2(-344.5 / 30,-54 / 30);
         mall_motor_1_anchor = new b2Vec2(-344.5 / 30,-397.5 / 30);
         Handler_WorldItems.AddDistanceJoint(mall_elevator_01_back,mall_motor_1,mall_elevator_1_anchor,mall_motor_1_anchor);
         btn_01 = Handler_WorldItems.AddBox("BUTTON_01",-312 / 30,-50 / 30,0,new b2Vec2(),0);
         btn_01.ForceSleep();
         btn_01.GetUserData().buttonData.OnActivationSound = "SND_PLACEHOLDER";
         btn_01.GetUserData().buttonData.Enabled = false;
         btn_02 = Handler_WorldItems.AddBox("BUTTON_01",-312 / 30,145 / 30,0,new b2Vec2(),0);
         btn_02.ForceSleep();
         btn_02.GetUserData().buttonData.OnActivationSound = "SND_PLACEHOLDER";
         btn_03 = Handler_WorldItems.AddBox("BUTTON_01",-360 / 30,-50 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddLimitedJoint(btn_03,mall_elevator_01_back,new b2Vec2(-360 / 30,-50 / 30),0,0);
         btn_03.GetUserData().buttonData.OnActivationSound = "SND_PLACEHOLDER";
         mall_elevator_logic_up = new MapLogic();
         mall_elevator_logic_down = new MapLogic();
         btn_01.GetUserData().buttonData.OnActivation = function():void
         {
            if(mall_motor_1_joint.GetJointAngle() > 3.1 && mall_motor_1_joint.GetJointAngle() < 3.2)
            {
               _Handler_Output.Trace("Elevator: Sending Up");
               btn_01.GetUserData().buttonData.Enabled = false;
               btn_02.GetUserData().buttonData.Enabled = false;
               btn_03.GetUserData().buttonData.Enabled = false;
               mall_elevator_logic_up.Start();
               mall_motor_1_joint.SetMotorSpeed(-0.3);
               mall_motor_1.WakeUp();
               mall_elevator_01_back.WakeUp();
            }
         };
         btn_02.GetUserData().buttonData.OnActivation = function():void
         {
            if(mall_motor_1_joint.GetJointAngle() > -0.1 && mall_motor_1_joint.GetJointAngle() < 0.1)
            {
               _Handler_Output.Trace("Elevator: Sending Down");
               btn_01.GetUserData().buttonData.Enabled = false;
               btn_02.GetUserData().buttonData.Enabled = false;
               btn_03.GetUserData().buttonData.Enabled = false;
               mall_elevator_logic_down.Start();
               mall_motor_1_joint.SetMotorSpeed(0.3);
               mall_motor_1.WakeUp();
               mall_elevator_01_back.WakeUp();
            }
         };
         btn_03.GetUserData().buttonData.OnActivation = function():void
         {
            if(mall_motor_1_joint.GetJointAngle() > 3.1 && mall_motor_1_joint.GetJointAngle() < 3.2)
            {
               _Handler_Output.Trace("Elevator: Sending Up");
               btn_01.GetUserData().buttonData.Enabled = false;
               btn_02.GetUserData().buttonData.Enabled = false;
               btn_03.GetUserData().buttonData.Enabled = false;
               mall_elevator_logic_up.Start();
               mall_motor_1_joint.SetMotorSpeed(-0.3);
               mall_motor_1.WakeUp();
               mall_elevator_01_back.WakeUp();
            }
            if(mall_motor_1_joint.GetJointAngle() > -0.1 && mall_motor_1_joint.GetJointAngle() < 0.1)
            {
               _Handler_Output.Trace("Elevator: Sending Down");
               btn_01.GetUserData().buttonData.Enabled = false;
               btn_02.GetUserData().buttonData.Enabled = false;
               btn_03.GetUserData().buttonData.Enabled = false;
               mall_elevator_logic_down.Start();
               mall_motor_1_joint.SetMotorSpeed(0.3);
               mall_motor_1.WakeUp();
               mall_elevator_01_back.WakeUp();
            }
         };
         mall_elevator_logic_down.OnUpdate = function():void
         {
            if(mall_motor_1_joint.GetJointAngle() > 3.1 && mall_motor_1_joint.GetJointAngle() < 3.2)
            {
               _Handler_Output.Trace("Elevator: Destination Reached: Bottom");
               btn_01.GetUserData().buttonData.Enabled = true;
               btn_03.GetUserData().buttonData.Enabled = true;
               mall_elevator_logic_down.Stop();
            }
         };
         mall_elevator_logic_up.OnUpdate = function():void
         {
            if(mall_motor_1_joint.GetJointAngle() > -0.1 && mall_motor_1_joint.GetJointAngle() < 0.1)
            {
               _Handler_Output.Trace("Elevator: Destination Reached: Top");
               btn_02.GetUserData().buttonData.Enabled = true;
               btn_03.GetUserData().buttonData.Enabled = true;
               mall_elevator_logic_up.Stop();
            }
         };
         mall_motor_1_joint.SetLimits(0,Math.PI);
         mall_motor_1_joint.EnableLimit(true);
         MapUpdate = function(param1:Number):void
         {
         };
         MapEnd = function():void
         {
            mall_elevator_logic_up.Stop();
            mall_elevator_logic_down.Stop();
         };
      }
      
      public function UpdatePathGrid() : void
      {
         pathGrid.UpdatePathGrid();
      }
      
      public function Stop() : void
      {
         pathGrid.Stop();
         MapEnd();
      }
      
      private function CreateElevator(param1:b2Body, param2:Number, param3:Number) : void
      {
         var _loc4_:b2Body = null;
         var _loc5_:b2RevoluteJoint = null;
         var _loc6_:b2Vec2 = null;
         var _loc7_:b2Vec2 = null;
         Handler_WorldItems.AddPrismaticJoint(Handler_WorldItems.Ground,param1,param1.GetPosition(),new b2Vec2(0,1));
         _loc4_ = Handler_WorldItems.AddCircle("PLATFORM_MOTOR",param1.GetPosition().x,param1.GetPosition().y - param2 / 30 * 2,0,new b2Vec2(),0);
         _loc4_.GetUserData().visible = false;
         _loc5_ = Handler_WorldItems.AddRevoluteMotor(Handler_WorldItems.Ground,_loc4_,_loc4_.GetPosition(),param3,9999);
         _loc6_ = param1.GetPosition();
         _loc7_ = new b2Vec2(_loc4_.GetPosition().x,_loc4_.GetPosition().y + param2 / 30 * 0.5);
         Handler_WorldItems.AddDistanceJoint(param1,_loc4_,_loc6_,_loc7_);
      }
      
      private function GenerateMapHazardous() : void
      {
         var stair:b2Body = null;
         var crate_hanging_2:b2Body = null;
         var crate_hanging_1:b2Body = null;
         var lamp1:b2Body = null;
         var lamp2:b2Body = null;
         var lamp3:b2Body = null;
         var lamp4:b2Body = null;
         var lift_small:b2Body = null;
         var lamp5:b2Body = null;
         var lamp6:b2Body = null;
         var lamp7:b2Body = null;
         var lamp8:b2Body = null;
         var crate_hanging_3:b2Body = null;
         var lift_1:b2Body = null;
         var lift_2:b2Body = null;
         var closness:Number = NaN;
         var holder1:b2Body = null;
         var holder2:b2Body = null;
         var holder3:b2Body = null;
         var ropeh1:Rope = null;
         var ropeh2:Rope = null;
         var ropeh3:Rope = null;
         var layer_mc:MovieClip = null;
         var rope1:Rope = null;
         var rope2:Rope = null;
         var rope3:Rope = null;
         var rope4:Rope = null;
         var rope5:Rope = null;
         var rope6:Rope = null;
         var rope7:Rope = null;
         var rope8:Rope = null;
         var rope9:Rope = null;
         var rope10:Rope = null;
         var nextBubble:int = 0;
         mapArea = new Rectangle(0,-45,600,450);
         playerSpawns = new Array(new Point(402,290),new Point(378,290),new Point(320,191),new Point(248,123),new Point(326,116),new Point(430,168),new Point(558,168),new Point(495,168),new Point(104,281),new Point(49,114),new Point(157,112),new Point(107,215),new Point(159,216),new Point(244,191),new Point(388,180));
         weaponSpawns = new Array(new WeaponSpawnData(257,125,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(320,195,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(389,291,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(502,169,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(137,217,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(94,125,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)));
         portals = new Array(new PortalData(new Rectangle(567,276,22,24),new Rectangle(567,150,20,24),new Point(1,0),true,false),new PortalData(new Rectangle(567,150,20,24),new Rectangle(567,276,22,24),new Point(1,0),true,false),new PortalData(new Rectangle(15,226,20,24),new Rectangle(15,106,20,24),new Point(-1,0),true,false),new PortalData(new Rectangle(15,106,20,24),new Rectangle(15,226,20,24),new Point(-1,0),true,false));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,389.5 / 30,305 / 30,0,73 / 30,18 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,566 / 30,307 / 30,0,106 / 30,14 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,492 / 30,180 / 30,0,150 / 30,12 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,592 / 30,225 / 30,0,50 / 30,102 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,603 / 30,288 / 30,0,28 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,602 / 30,162 / 30,0,30 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,592 / 30,123.5 / 30,0,50 / 30,53 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,517 / 30,49 / 30,0,200 / 30,96 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,423.5 / 30,117.5 / 30,0,13 / 30,41 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,296 / 30,17.5 / 30,0,242 / 30,33 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,168.5 / 30,76.5 / 30,0,13 / 30,35 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,88 / 30,30 / 30,0,174 / 30,58 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,18 / 30,82.5 / 30,0,34 / 30,47 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,8 / 30,118 / 30,0,14 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,88 / 30,136 / 30,0,174 / 30,12 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,18 / 30,184 / 30,0,34 / 30,84 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,8 / 30,238 / 30,0,14 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,22 / 30,282 / 30,0,42 / 30,64 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,126 / 30,300 / 30,0,58 / 30,28 / 30,new Array("NONE"));
         stair = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,66 / 30,289 / 30,0,new Array([-23 / 30,-39 / 30],[-18 / 30,-39 / 30],[31 / 30,-3 / 30],[31 / 30,24 / 30],[-23 / 30,24 / 30]),new Array("NONE"));
         stair.GetUserData().tiltValue = 2;
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,92.5 / 30,235.5 / 30,-0.7853981633974483,34 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,137.5 / 30,224 / 30,0,69 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,258 / 30,132 / 30,0,66 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,320 / 30,202 / 30,0,70 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,361.5 / 30,229 / 30,0,13 / 30,81 / 30,new Array("LADDER"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,297.5 / 30,144.5 / 30,0,13 / 30,59 / 30,new Array("LADDER"));
         if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",528 / 30,293 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE",544 / 30,293 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,CRATE",537 / 30,277 / 30,1.5707963267948966,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("CRATE,BARREL",533 / 30,293 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",547 / 30,293 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,GASCAN",487 / 30,293 / 30,0,new b2Vec2(),0);
         }
         if(33 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",123 / 30,279 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,BARREL",139 / 30,279 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("BARREL,BARREL_EXPLOSIVE,CRATE,NONE",134 / 30,281 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,NONE",120 / 30,281 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL",129 / 30,266 / 30,0,new b2Vec2(),0);
         }
         if(25 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE",325 / 30,289 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",343 / 30,289 / 30,0,new b2Vec2(),0);
         }
         if(40 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE",61 / 30,123 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",79 / 30,123 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",120 / 30,123 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,FILECAB,BARREL_EXPLOSIVE,BARREL",139 / 30,123 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,NONE",71 / 30,108 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,NONE,GASCAN",131 / 30,108 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,BARREL,NONE,CRATE",97 / 30,123 / 30,0,new b2Vec2(),0);
         }
         else
         {
            if(50 >= Math.random() * 100)
            {
               Handler_WorldItems.AddObject("TABLE",124 / 30,125 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("CHAIR_R",139 / 30,126 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("TABLE",66.5 / 30,125 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("FILECAB",82.5 / 30,123.5 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",63 / 30,115.5 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",129 / 30,115.5 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",118 / 30,115.5 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",81.5 / 30,112.5 / 30,0,new b2Vec2(),0);
            }
            else
            {
               if(50 >= Math.random() * 100)
               {
                  Handler_WorldItems.AddObject("COMP_SCREEN",119 / 30,112 / 30,0,new b2Vec2(),0);
                  Handler_WorldItems.AddObject("COMP",140 / 30,125 / 30,0,new b2Vec2(),0);
               }
               else
               {
                  Handler_WorldItems.AddObject("PAPER",129 / 30,113.5 / 30,0,new b2Vec2(),0);
                  Handler_WorldItems.AddObject("PAPER",119.5 / 30,113.5 / 30,0,new b2Vec2(),0);
                  Handler_WorldItems.AddObject("FILECAB",144 / 30,123 / 30,0,new b2Vec2(),0);
               }
               Handler_WorldItems.AddObject("DESK_1",69 / 30,124 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("COMP_SCREEN",64 / 30,112 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("COMP",84 / 30,125 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",74 / 30,113 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("DESK_1",124 / 30,124 / 30,0,new b2Vec2(),0);
            }
            Handler_WorldItems.AddObject("CHAIR",106 / 30,126 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CHAIR",49.5 / 30,126 / 30,0,new b2Vec2(),0);
         }
         if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("DESK",538 / 30,168 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",444 / 30,166 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("TABLE_SMALL",459 / 30,171 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR,FILECAB",474 / 30,166 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR,CHAIR",516 / 30,166 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE,PAPER",460 / 30,164 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMP_SCREEN",533 / 30,156 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMP",544 / 30,156 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",451 / 30,167 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,FILECAB",469 / 30,167 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",486 / 30,167 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,CRATE",525 / 30,167 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,CRATE",542 / 30,167 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,CRATE,NONE",477 / 30,152 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,NONE",459 / 30,152 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,GASCAN,NONE,CRATE",533 / 30,152 / 30,0,new b2Vec2(),0);
         }
         crate_hanging_2 = Handler_WorldItems.AddObject("CRATE_HANGING",388 / 30,194 / 30,0,new b2Vec2(),0);
         crate_hanging_1 = Handler_WorldItems.AddObject("CRATE_HANGING",326 / 30,130 / 30,0,new b2Vec2(),0);
         lamp1 = Handler_WorldItems.AddObject("LAMP_1",53.5 / 30,61.5 / 30,0,new b2Vec2(),0);
         lamp2 = Handler_WorldItems.AddObject("LAMP_1",84 / 30,61.5 / 30,0,new b2Vec2(),0);
         lamp3 = Handler_WorldItems.AddObject("LAMP_1",114.5 / 30,61.5 / 30,0,new b2Vec2(),0);
         lamp4 = Handler_WorldItems.AddObject("LAMP_1",144.5 / 30,61.5 / 30,0,new b2Vec2(),0);
         lift_small = Handler_WorldItems.AddObject("LIFT_SMALL_01",190.5 / 30,228 / 30,0,new b2Vec2(),0);
         lamp5 = Handler_WorldItems.AddObject("LAMP_1",450 / 30,99.5 / 30,0,new b2Vec2(),0);
         lamp6 = Handler_WorldItems.AddObject("LAMP_1",482 / 30,99.5 / 30,0,new b2Vec2(),0);
         lamp7 = Handler_WorldItems.AddObject("LAMP_1",515 / 30,99.5 / 30,0,new b2Vec2(),0);
         lamp8 = Handler_WorldItems.AddObject("LAMP_1",547.5 / 30,99.5 / 30,0,new b2Vec2(),0);
         crate_hanging_3 = Handler_WorldItems.AddObject("CRATE_HANGING",244 / 30,206 / 30,0,new b2Vec2(),0);
         lift_1 = Handler_WorldItems.AddObject("LIFT_01",334 / 30,300.5 / 30,0,new b2Vec2(),0);
         lift_2 = Handler_WorldItems.AddObject("LIFT_01",494 / 30,304.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE",415 / 30,289 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE,GASCAN",362 / 30,289 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE,BARREL",341 / 30,191.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL,BARREL_EXPLOSIVE,NONE,NONE",341 / 30,176 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE",539 / 30,278 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL",124 / 30,215 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE,NONE",184 / 30,217 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",293 / 30,193 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE",282 / 30,123 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,BARREL,NONE,BARREL",231.5 / 30,123.5 / 30,0,new b2Vec2(),0);
         pathGrid.AddNode(new PathNode("",361,292,"",null));
         pathGrid.AddNode(new PathNode("",389,292,"",null));
         pathGrid.AddNode(new PathNode("",418,292,"",null));
         pathGrid.AddNode(new PathNode("",491,296,"",lift_2));
         pathGrid.AddNode(new PathNode("",497,296,"",lift_2));
         pathGrid.AddNode(new PathNode("",520,296,"",null));
         pathGrid.AddNode(new PathNode("",563,296,"",null));
         pathGrid.AddNode(new PathNode("",541,296,"",null));
         pathGrid.AddNode(new PathNode("",622,296,"",null));
         pathGrid.AddNode(new PathNode("",563,170,"",null));
         pathGrid.AddNode(new PathNode("",621,170,"",null));
         pathGrid.AddNode(new PathNode("",532,170,"",null));
         pathGrid.AddNode(new PathNode("",502,170,"",null));
         pathGrid.AddNode(new PathNode("",477,170,"",null));
         pathGrid.AddNode(new PathNode("",452,170,"",null));
         pathGrid.AddNode(new PathNode("",424,170,"",null));
         pathGrid.AddNode(new PathNode("CRATE_2",382,183,"",crate_hanging_2));
         pathGrid.AddNode(new PathNode("CRATE_2",394,183,"",crate_hanging_2));
         pathGrid.AddNode(new PathNode("",347,196,"",null));
         pathGrid.AddNode(new PathNode("",320,196,"",null));
         pathGrid.AddNode(new PathNode("",297,196,"",null));
         pathGrid.AddNode(new PathNode("CRATE_3",250,195,"",crate_hanging_3));
         pathGrid.AddNode(new PathNode("CRATE_3",238,195,"",crate_hanging_3));
         pathGrid.AddNode(new PathNode("",338,292,"",lift_1));
         pathGrid.AddNode(new PathNode("",331,292,"",lift_1));
         pathGrid.AddNode(new PathNode("CRATE_1",320,119,"",crate_hanging_1));
         pathGrid.AddNode(new PathNode("CRATE_1",332,119,"",crate_hanging_1));
         pathGrid.AddNode(new PathNode("",283,126,"",null));
         pathGrid.AddNode(new PathNode("",186,220,"",lift_small));
         pathGrid.AddNode(new PathNode("",195,220,"",lift_small));
         pathGrid.AddNode(new PathNode("",165,218,"",null));
         pathGrid.AddNode(new PathNode("",137,218,"",null));
         pathGrid.AddNode(new PathNode("",107,218,"",null));
         pathGrid.AddNode(new PathNode("",92,229,"",null));
         pathGrid.AddNode(new PathNode("",82,239,"",null));
         pathGrid.AddNode(new PathNode("",46,246,"",null));
         pathGrid.AddNode(new PathNode("",67,259,"",null));
         pathGrid.AddNode(new PathNode("",99,282,"",null));
         pathGrid.AddNode(new PathNode("",83,271,"",null));
         pathGrid.AddNode(new PathNode("",123,282,"",null));
         pathGrid.AddNode(new PathNode("",146,282,"",null));
         pathGrid.AddNode(new PathNode("",39,246,"",null));
         pathGrid.AddNode(new PathNode("",-19,246,"",null));
         pathGrid.AddNode(new PathNode("",39,126,"",null));
         pathGrid.AddNode(new PathNode("",-25,126,"",null));
         pathGrid.AddNode(new PathNode("",66,126,"",null));
         pathGrid.AddNode(new PathNode("",94,126,"",null));
         pathGrid.AddNode(new PathNode("",119,126,"",null));
         pathGrid.AddNode(new PathNode("",145,126,"",null));
         pathGrid.AddNode(new PathNode("",168,126,"",null));
         pathGrid.AddNode(new PathNode("",232,126,"",null));
         pathGrid.AddNode(new PathNode("",257,126,"",null));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[3],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[2],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[5],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[4],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[8],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[10],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[6],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[9],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[12],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[12],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[15],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[14],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[14],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[17],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[15],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[17],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[16],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[18],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[18],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[19],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[18],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[19],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[20],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[20],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[21],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[18],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[0],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[23],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[24],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[0],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[23],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[26],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[26],pathGrid.Nodes[25],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[25],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[27],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[20],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[27],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[29],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[22],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[29],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[28],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[30],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[31],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[30],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[31],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[34],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[36],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[36],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[36],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[40],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[24],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[40],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[41],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[44],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[41],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[42],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[43],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[43],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[46],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[47],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[48],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[49],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[48],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[47],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[46],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[28],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[49],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[27],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[50],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[50],pathGrid.Nodes[51],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[51],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[50],pathGrid.Nodes[29],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[50],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         closness = 0.5 / 30;
         holder1 = Handler_WorldItems.AddObject("CRATE_HANGING_HOLDER",crate_hanging_1.GetPosition().x,crate_hanging_1.GetPosition().y - crate_hanging_1.GetUserData().height / 30 * 0.5,0,new b2Vec2(),0);
         holder2 = Handler_WorldItems.AddObject("CRATE_HANGING_HOLDER",crate_hanging_2.GetPosition().x,crate_hanging_2.GetPosition().y - crate_hanging_2.GetUserData().height / 30 * 0.5,0,new b2Vec2(),0);
         holder3 = Handler_WorldItems.AddObject("CRATE_HANGING_HOLDER",crate_hanging_3.GetPosition().x,crate_hanging_3.GetPosition().y - crate_hanging_3.GetUserData().height / 30 * 0.5,0,new b2Vec2(),0);
         Handler_WorldItems.AddLimitedJoint(crate_hanging_1,holder1,holder1.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(crate_hanging_2,holder2,holder2.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(crate_hanging_3,holder3,holder3.GetPosition(),0,0);
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder1,new b2Vec2(holder1.GetPosition().x,34 / 30),new b2Vec2(holder1.GetPosition().x + closness,holder1.GetPosition().y - holder1.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder1,new b2Vec2(holder1.GetPosition().x,34 / 30),new b2Vec2(holder1.GetPosition().x - closness,holder1.GetPosition().y - holder1.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder2,new b2Vec2(holder2.GetPosition().x,128 / 30),new b2Vec2(holder2.GetPosition().x + closness,holder2.GetPosition().y - holder2.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder2,new b2Vec2(holder2.GetPosition().x,128 / 30),new b2Vec2(holder2.GetPosition().x - closness,holder2.GetPosition().y - holder2.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder3,new b2Vec2(holder3.GetPosition().x,134 / 30),new b2Vec2(holder3.GetPosition().x + closness,holder3.GetPosition().y - holder3.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder3,new b2Vec2(holder3.GetPosition().x,134 / 30),new b2Vec2(holder3.GetPosition().x - closness,holder3.GetPosition().y - holder3.GetUserData().height / 30 * 0.5));
         crate_hanging_1.ApplyForce(new b2Vec2(Math.random() * 10 - 5,Math.random()),new b2Vec2(crate_hanging_1.GetPosition().x + Math.random() * 2 - 1,crate_hanging_1.GetPosition().y));
         crate_hanging_2.ApplyForce(new b2Vec2(Math.random() * 10 - 5,Math.random()),new b2Vec2(crate_hanging_2.GetPosition().x + Math.random() * 2 - 1,crate_hanging_2.GetPosition().y));
         crate_hanging_3.ApplyForce(new b2Vec2(Math.random() * 10 - 5,Math.random()),new b2Vec2(crate_hanging_3.GetPosition().x + Math.random() * 2 - 1,crate_hanging_3.GetPosition().y));
         ropeh1 = new Rope(Handler_WorldItems.Ground,holder1,new b2Vec2(holder1.GetPosition().x,34 / 30),new b2Vec2(holder1.GetPosition().x,holder1.GetPosition().y - holder1.GetUserData().height / 30 * 0.5));
         ropeh2 = new Rope(Handler_WorldItems.Ground,holder2,new b2Vec2(holder2.GetPosition().x,128 / 30),new b2Vec2(holder2.GetPosition().x,holder2.GetPosition().y - holder2.GetUserData().height / 30 * 0.5));
         ropeh3 = new Rope(Handler_WorldItems.Ground,holder3,new b2Vec2(holder3.GetPosition().x,134 / 30),new b2Vec2(holder3.GetPosition().x,holder3.GetPosition().y - holder3.GetUserData().height / 30 * 0.5));
         layer_mc = MovieClip(_dynamic_mc.getChildByName("OBJECTS"));
         layer_mc.addChild(ropeh1.MC);
         layer_mc.addChild(ropeh2.MC);
         layer_mc.addChild(ropeh3.MC);
         holder1.GetUserData().onDestruction = function(param1:b2Body):void
         {
            ropeh1.Remove();
            pathGrid.RemoveNodes("CRATE_1");
            pathGrid.UpdateSpecials();
            pathGrid.AnalyzeGrid();
         };
         holder2.GetUserData().onDestruction = function(param1:b2Body):void
         {
            ropeh2.Remove();
            pathGrid.RemoveNodes("CRATE_2");
            pathGrid.UpdateSpecials();
            pathGrid.AnalyzeGrid();
         };
         holder3.GetUserData().onDestruction = function(param1:b2Body):void
         {
            ropeh3.Remove();
            pathGrid.RemoveNodes("CRATE_3");
            pathGrid.UpdateSpecials();
            pathGrid.AnalyzeGrid();
         };
         CreateElevator(lift_small,95,1);
         CreateHorizontalElevator(lift_1,160,0.8);
         CreateHorizontalElevator(lift_2,49,2);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp1,lamp1.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp2,lamp2.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp3,lamp3.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp4,lamp4.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp5,lamp5.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp6,lamp6.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp7,lamp7.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp8,lamp8.GetPosition(),0,0);
         rope1 = Handler_WorldItems.AddHangingLamp(new Point(68,142),25);
         rope2 = Handler_WorldItems.AddHangingLamp(new Point(105,142),25);
         rope3 = Handler_WorldItems.AddHangingLamp(new Point(140,142),25);
         rope4 = Handler_WorldItems.AddHangingLamp(new Point(434,186.5),30);
         rope5 = Handler_WorldItems.AddHangingLamp(new Point(471,186.5),30);
         rope6 = Handler_WorldItems.AddHangingLamp(new Point(506,186.5),30);
         rope7 = Handler_WorldItems.AddHangingLamp(new Point(541,186.5),30);
         rope8 = Handler_WorldItems.AddHangingLamp(new Point(234,34),35);
         rope9 = Handler_WorldItems.AddHangingLamp(new Point(295,34),35);
         rope10 = Handler_WorldItems.AddHangingLamp(new Point(356,34),35);
         Handler_WorldItems.AddGlass(new Point(172 / 30,132 / 30),new Point(172 / 30,92 / 30));
         Handler_WorldItems.AddGlass(new Point(419 / 30,138 / 30),new Point(419 / 30,174 / 30));
         nextBubble = 2;
         MapUpdate = function(param1:Number):void
         {
            var _loc2_:int = 0;
            var _loc3_:Number = NaN;
            rope1.UpdateMC();
            rope2.UpdateMC();
            rope3.UpdateMC();
            rope4.UpdateMC();
            rope5.UpdateMC();
            rope6.UpdateMC();
            rope7.UpdateMC();
            rope8.UpdateMC();
            rope9.UpdateMC();
            rope10.UpdateMC();
            ropeh1.UpdateMC();
            ropeh2.UpdateMC();
            ropeh3.UpdateMC();
            nextBubble -= 1;
            if(nextBubble <= 0)
            {
               _loc3_ = Math.random() * 269;
               _loc3_ += 158;
               if(_loc3_ > 349)
               {
                  _loc3_ += 81;
               }
               _Handler_Effects.AddParticle(new particle_data("BUBBLE",_loc3_,312,new b2Vec2(0,0)));
               nextBubble = 2;
            }
            _loc2_ = 0;
            while(_loc2_ < _Handler_Players.Players.length)
            {
               if(!_Handler_Players.Players[_loc2_].Ignore)
               {
                  if(_Handler_Players.Players[_loc2_].MidPosY() > 325)
                  {
                     _Handler_Players.Players[_loc2_].IgnorePlayer();
                     _Handler_Sounds.PlaySoundAt("gib",_Handler_Players.Players[_loc2_].MidPosX(),_Handler_Players.Players[_loc2_].MidPosY());
                  }
               }
               _loc2_++;
            }
         };
         MapStart = function():void
         {
            mapGraphic.AddMC(GetLevelMC("fan_1"));
            mapGraphic.AddMC(GetLevelMC("fan_2"));
            mapGraphic.AddMC(GetLevelMC("fan_3"));
            mapGraphic.AddMC(GetLevelMC("fan_4"));
         };
      }
      
      public function LinkPlayers(param1:PlayersKeeper) : void
      {
         _Handler_Players = param1;
      }
      
      private function GenerateMapRooftops() : void
      {
         var stair:b2Body = null;
         var lift:b2Body = null;
         var lamp3:b2Body = null;
         var lamp2:b2Body = null;
         var lamp1:b2Body = null;
         var lamp4:b2Body = null;
         var lamp6:b2Body = null;
         var lamp5:b2Body = null;
         var rope1:Rope = null;
         var rope2:Rope = null;
         var rope3:Rope = null;
         mapArea = new Rectangle(-12,-110,583,510);
         playerSpawns = new Array(new Point(94,89),new Point(162,89),new Point(98,271),new Point(144,270),new Point(235,74),new Point(285,188),new Point(319,295.5),new Point(392,291),new Point(449.5,290),new Point(463,188),new Point(291,74),new Point(258,277));
         weaponSpawns = new Array(new WeaponSpawnData(315,77,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(259,189,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(392,297,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(274,279,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(380,189,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(159,274,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(126,90,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)));
         portals = new Array(new PortalData(new Rectangle(58,73,20,22),new Rectangle(47,255,20,24),new Point(-1,0),true,false),new PortalData(new Rectangle(47,255,20,24),new Rectangle(58,73,20,22),new Point(-1,0),true,false),new PortalData(new Rectangle(483,172,20,22),new Rectangle(483,279,20,23),new Point(1,0),true,false),new PortalData(new Rectangle(483,279,20,23),new Rectangle(483,172,20,22),new Point(1,0),true,false));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,103.5 / 30,157 / 30,0,167 / 30,124 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,39 / 30,74 / 30,0,38 / 30,42 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,68 / 30,63 / 30,0,20 / 30,20 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,43.5 / 30,237 / 30,0,47 / 30,36 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,33.5 / 30,267 / 30,0,27 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,103.5 / 30,319 / 30,0,167 / 30,82 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,265.5 / 30,323 / 30,0,47 / 30,78 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,429.5 / 30,332 / 30,0,223 / 30,60 / 30,new Array("NONE"));
         stair = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,304 / 30,311 / 30,0,new Array([-15 / 30,-27 / 30],[-10 / 30,-27 / 30],[14 / 30,-9 / 30],[14 / 30,51 / 30],[-15 / 30,51 / 30]),new Array("NONE"));
         stair.GetUserData().tiltValue = 2;
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,180.5 / 30,231 / 30,0,13 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,274.5 / 30,200.5 / 30,0,65 / 30,13 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,248.5 / 30,228 / 30,0,13 / 30,42 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,380 / 30,200.5 / 30,0,24 / 30,13 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,468 / 30,200.5 / 30,0,30 / 30,13 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,493 / 30,162 / 30,0,20 / 30,20 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,522 / 30,173 / 30,0,38 / 30,42 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,512 / 30,236.5 / 30,0,58 / 30,85 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,522 / 30,290.5 / 30,0,38 / 30,23 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,200.5 / 30,221 / 30,0,27 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,194 / 30,143.5 / 30,0,14 / 30,115 / 30,new Array("LADDER"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,265.5 / 30,84 / 30,0,119 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,337.5 / 30,197 / 30,0,13 / 30,6 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,422.5 / 30,197 / 30,0,13 / 30,6 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,155 / 30,380 / 30,0,64 / 30,40 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,269 / 30,381 / 30,0,54 / 30,38 / 30,new Array("NONE"));
         if(50 >= Math.random() * 100)
         {
            if(50 >= Math.random() * 100)
            {
               Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE",302 / 30,74 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,BARREL",224 / 30,278 / 30,0,new b2Vec2(),0);
            }
            else
            {
               Handler_WorldItems.AddObject("BARREL_EXPLOSIVE",269 / 30,187 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("CRATE,NONE,BARREL_EXPLOSIVE,CRATE,NONE",261 / 30,73 / 30,0,new b2Vec2(),0);
            }
         }
         else if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE",273 / 30,187 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,BARREL,CRATE",253 / 30,186 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,NONE,GASCAN",263 / 30,168 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,GASCAN",144 / 30,88 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("CRATE",176 / 30,88 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL",178 / 30,73 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("BARREL_EXPLOSIVE",138 / 30,88 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,NONE,BARREL_EXPLOSIVE,GASCAN",179 / 30,58 / 30,0,new b2Vec2(),0);
         }
         if(33 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,BARREL,CRATE",334 / 30,295 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL",352 / 30,295 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,GASCAN,NONE,CRATE",376 / 30,295 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",344 / 30,281 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL",413 / 30,295 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",431 / 30,295 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,NONE",423 / 30,281 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",283 / 30,277 / 30,0,new b2Vec2(),0);
         }
         else if(50 >= Math.random() * 100)
         {
            if(50 >= Math.random() * 100)
            {
               Handler_WorldItems.AddObject("COMP",374 / 30,284 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("COMP_SCREEN",362 / 30,284 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",416.5 / 30,285.5 / 30,0,new b2Vec2(),0);
            }
            else
            {
               Handler_WorldItems.AddObject("COMP",405.5 / 30,297 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("COMP_SCREEN",419 / 30,284 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",370.5 / 30,285.5 / 30,0,new b2Vec2(),0);
            }
            Handler_WorldItems.AddObject("DESK",367.5 / 30,296 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",342 / 30,294.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("DESK",422.5 / 30,296 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",460.5 / 30,294.5 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("COMFY_CHAIR",342 / 30,294 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("TABLE_SMALL",358 / 30,299 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",374 / 30,294 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",407 / 30,294 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("TABLE_SMALL",422 / 30,299 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",438 / 30,294 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("DESK",277 / 30,278 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE",273 / 30,267.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE",283 / 30,268 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE",358 / 30,292 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE",422 / 30,291 / 30,0,new b2Vec2(),0);
         }
         lift = Handler_WorldItems.AddObject("LIFT_SMALL_01",229 / 30,290 / 30,0,new b2Vec2(),0);
         lamp3 = Handler_WorldItems.AddObject("LAMP_1",155 / 30,221.5 / 30,0,new b2Vec2(),0);
         lamp2 = Handler_WorldItems.AddObject("LAMP_1",119.5 / 30,221.5 / 30,0,new b2Vec2(),0);
         lamp1 = Handler_WorldItems.AddObject("LAMP_1",83 / 30,221.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",531 / 30,145 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE,GASCAN",491 / 30,145 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE",511 / 30,145 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",30 / 30,46 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",49 / 30,46 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",40 / 30,32 / 30,1.5707963267948966,new b2Vec2(),0);
         Handler_WorldItems.AddObject("GASCAN,NONE",68 / 30,49 / 30,1.5707963267948966,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",113 / 30,88 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("TABLE",122 / 30,273 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CHAIR",101 / 30,274 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CHAIR_R",141 / 30,273 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE,NONE",82 / 30,271 / 30,0,new b2Vec2(),0);
         lamp4 = Handler_WorldItems.AddObject("LAMP_1",224 / 30,33 / 30,0,new b2Vec2(),0);
         lamp6 = Handler_WorldItems.AddObject("LAMP_1",307 / 30,33 / 30,0,new b2Vec2(),0);
         lamp5 = Handler_WorldItems.AddObject("LAMP_1",266 / 30,33 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("PAPER,NONE",118 / 30,263.5 / 30,0,new b2Vec2(),0);
         pathGrid.AddNode(new PathNode("",181,91,"",null));
         pathGrid.AddNode(new PathNode("",144,91,"",null));
         pathGrid.AddNode(new PathNode("",111,91,"",null));
         pathGrid.AddNode(new PathNode("",77,91,"",null));
         pathGrid.AddNode(new PathNode("",24,49,"",null));
         pathGrid.AddNode(new PathNode("",49,49,"",null));
         pathGrid.AddNode(new PathNode("",73,49,"",null));
         pathGrid.AddNode(new PathNode("",27,91,"",null));
         pathGrid.AddNode(new PathNode("",212,77,"",null));
         pathGrid.AddNode(new PathNode("",238,77,"",null));
         pathGrid.AddNode(new PathNode("",266,77,"",null));
         pathGrid.AddNode(new PathNode("",294,77,"",null));
         pathGrid.AddNode(new PathNode("",320,77,"",null));
         pathGrid.AddNode(new PathNode("",159,91,"",null));
         pathGrid.AddNode(new PathNode("",249,190,"",null));
         pathGrid.AddNode(new PathNode("",422.5,189.5,"",null));
         pathGrid.AddNode(new PathNode("",458,190,"",null));
         pathGrid.AddNode(new PathNode("",388,190,"",null));
         pathGrid.AddNode(new PathNode("",372,190,"",null));
         pathGrid.AddNode(new PathNode("",302,190,"",null));
         pathGrid.AddNode(new PathNode("",337.5,190,"",null));
         pathGrid.AddNode(new PathNode("",277,190,"",null));
         pathGrid.AddNode(new PathNode("",207,215,"",null));
         pathGrid.AddNode(new PathNode("",194,215,"",null));
         pathGrid.AddNode(new PathNode("",481,190,"",null));
         pathGrid.AddNode(new PathNode("",534,190,"",null));
         pathGrid.AddNode(new PathNode("",536,148,"",null));
         pathGrid.AddNode(new PathNode("",487,148,"",null));
         pathGrid.AddNode(new PathNode("",512,148,"",null));
         pathGrid.AddNode(new PathNode("",481,298,"",null));
         pathGrid.AddNode(new PathNode("",534,298,"",null));
         pathGrid.AddNode(new PathNode("",68,274,"",null));
         pathGrid.AddNode(new PathNode("",24,274,"",null));
         pathGrid.AddNode(new PathNode("",96,274,"",null));
         pathGrid.AddNode(new PathNode("",123,274,"",null));
         pathGrid.AddNode(new PathNode("",152,274,"",null));
         pathGrid.AddNode(new PathNode("",179,274,"",null));
         pathGrid.AddNode(new PathNode("",248.5,280,"",null));
         pathGrid.AddNode(new PathNode("",270,280,"",null));
         pathGrid.AddNode(new PathNode("",292,280,"",null));
         pathGrid.AddNode(new PathNode("",323,297,"",null));
         pathGrid.AddNode(new PathNode("",352,297,"",null));
         pathGrid.AddNode(new PathNode("",383,297,"",null));
         pathGrid.AddNode(new PathNode("",413.5,297,"",null));
         pathGrid.AddNode(new PathNode("",449,297,"",null));
         pathGrid.AddNode(new PathNode("",223,282,"",lift));
         pathGrid.AddNode(new PathNode("",235,282,"",lift));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[2],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[7],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[12],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[10],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[10],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[0],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[8],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[14],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[15],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[17],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[18],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[15],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[17],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[15],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[16],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[19],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[20],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[18],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[20],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[14],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[19],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[22],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[23],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[0],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[23],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[24],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[25],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[26],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[26],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[27],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[29],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[30],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[24],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[32],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[3],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[31],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[36],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[31],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[44],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[43],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[42],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[41],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[40],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[40],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[41],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[42],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[43],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[44],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[29],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[46],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[22],PathBind.DYNAMIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[37],PathBind.DYNAMIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[46],PathBind.DYNAMIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[36],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[45],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[14],PathBind.DYNAMIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[45],PathBind.DYNAMIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[46],PathBind.DYNAMIC,PathBind.ROAD));
         CreateElevator(lift,92,1);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp1,lamp1.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp2,lamp2.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp3,lamp3.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp4,lamp4.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp5,lamp5.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp6,lamp6.GetPosition(),0,0);
         Handler_WorldItems.AddGlass(new Point(306 / 30,196 / 30),new Point(332 / 30,196 / 30));
         Handler_WorldItems.AddGlass(new Point(343 / 30,196 / 30),new Point(369 / 30,196 / 30));
         Handler_WorldItems.AddGlass(new Point(391 / 30,196 / 30),new Point(417 / 30,196 / 30));
         Handler_WorldItems.AddGlass(new Point(428 / 30,196 / 30),new Point(454 / 30,196 / 30));
         Handler_WorldItems.AddGlass(new Point(245 / 30,285 / 30),new Point(245 / 30,247 / 30));
         Handler_WorldItems.AddGlass(new Point(184 / 30,241 / 30),new Point(184 / 30,280 / 30));
         rope1 = Handler_WorldItems.AddHangingLamp(new Point(280,206),25);
         rope2 = Handler_WorldItems.AddHangingLamp(new Point(380,206),25);
         rope3 = Handler_WorldItems.AddHangingLamp(new Point(468,206),25);
         MapUpdate = function(param1:Number):void
         {
            rope1.UpdateMC();
            rope2.UpdateMC();
            rope3.UpdateMC();
         };
         MapStart = function():void
         {
            mapGraphic.AddMC(GetLevelMC("background_clouds"));
            mapGraphic.AddMC(GetLevelMC("fan_1"));
            mapGraphic.AddMC(GetLevelMC("fan_2"));
            mapGraphic.AddMC(GetLevelMC("fan_3"));
         };
      }
      
      private function GetGroundWorld() : b2World
      {
         var _loc1_:b2AABB = null;
         var _loc2_:b2Vec2 = null;
         var _loc3_:Boolean = false;
         _loc1_ = new b2AABB();
         _loc1_.lowerBound.Set(-100,-100);
         _loc1_.upperBound.Set(100,100);
         _loc2_ = new b2Vec2(0,10);
         _loc3_ = true;
         m_world = new b2World(_loc1_,_loc2_,_loc3_);
         m_world.SetContactListener(m_contactListener);
         Handler_WorldItems.Setb2World = m_world;
         Handler_WorldItems.SetdbgDraw = MovieClip(_static_mc.getChildByName("WORLD_HITBOX"));
         return m_world;
      }
      
      public function ConstructContactListener(param1:ContactData) : void
      {
         m_contactListener = new b2ContactListener();
         m_contactListener.SetHandler(param1);
         Handler_WorldItems.LinkDeconstructer = param1.Handler_Deconstructer;
      }
      
      public function GetPlayerSpawnPositions(param1:Number = 0) : Array
      {
         return playerSpawns;
      }
      
      public function LinkWeapons(param1:Weapons) : void
      {
         _Handler_Weapons = param1;
      }
      
      public function GetMap(param1:Number) : b2World
      {
         var lvl:Number = param1;
         mapGraphic = new MapGraphic();
         pathGrid = new PathGrid();
         mapArea = new Rectangle(-3000,-3000,9000,9000);
         playerSpawns = new Array(new Point(0,0),new Point(10,0),new Point(20,0),new Point(30,0),new Point(40,0),new Point(50,0));
         portals = new Array();
         weaponSpawns = new Array(new WeaponSpawnData(420,188,new Array(1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(235,188,new Array(1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)));
         MapUpdate = function(param1:Number):void
         {
         };
         MapEnd = function():void
         {
         };
         MapStart = function():void
         {
         };
         _mapStartTimer = 2;
         m_world = GetGroundWorld();
         switch(lvl)
         {
            case 1:
               GenerateMapTutorial();
               break;
            case 2:
               GenerateMapStorage();
               break;
            case 3:
               GenerateMapRooftops();
               break;
            case 4:
               GenerateMapPoliceStation();
               break;
            case 5:
               GenerateMapHazardous();
         }
         _static_mc.addChild(pathGrid.DebugGraphic);
         pathGrid.UpdateSpecials();
         m_world.UpdateObjectLists();
         return m_world;
      }
      
      public function GetMapPortals(param1:Number = 0) : Array
      {
         return portals;
      }
      
      public function GetPathGrid(param1:Number = 0) : PathGrid
      {
         return pathGrid;
      }
      
      public function Update(param1:Number) : void
      {
         if(_mapStartTimer > 0)
         {
            _mapStartTimer -= 1;
            if(_mapStartTimer <= 0)
            {
               MapStart();
            }
         }
         MapUpdate(param1);
         mapGraphic.Update(param1);
      }
      
      private function CreateHorizontalElevator(param1:b2Body, param2:Number, param3:Number) : void
      {
         var _loc4_:b2Body = null;
         var _loc5_:b2RevoluteJoint = null;
         var _loc6_:b2Vec2 = null;
         var _loc7_:b2Vec2 = null;
         Handler_WorldItems.AddPrismaticJoint(Handler_WorldItems.Ground,param1,param1.GetPosition(),new b2Vec2(1,0));
         _loc4_ = Handler_WorldItems.AddCircle("PLATFORM_MOTOR",param1.GetPosition().x - param2 / 30 * 2,param1.GetPosition().y,0,new b2Vec2(),0);
         _loc4_.GetUserData().visible = false;
         _loc5_ = Handler_WorldItems.AddRevoluteMotor(Handler_WorldItems.Ground,_loc4_,_loc4_.GetPosition(),param3,9999);
         _loc6_ = param1.GetPosition();
         _loc7_ = new b2Vec2(_loc4_.GetPosition().x + param2 / 30 * 0.5,_loc4_.GetPosition().y);
         Handler_WorldItems.AddDistanceJoint(param1,_loc4_,_loc6_,_loc7_);
      }
      
      private function GenerateMapPoliceStation() : void
      {
         var stair:b2Body = null;
         var perm_cover1:b2Body = null;
         var propeller:b2Body = null;
         var lamp1:b2Body = null;
         var lamp2:b2Body = null;
         var lamp3:b2Body = null;
         var lamp4:b2Body = null;
         var rope1:Rope = null;
         var rope2:Rope = null;
         var rope3:Rope = null;
         var rope4:Rope = null;
         var rope5:Rope = null;
         var ropea:Rope = null;
         var ropeb:Rope = null;
         var ropec:Rope = null;
         var roped:Rope = null;
         mapArea = new Rectangle(105,-81,800,600);
         playerSpawns = new Array(new Point(184,369),new Point(272,370),new Point(368,370),new Point(443,370),new Point(531,356),new Point(571,357),new Point(690,358),new Point(750,376),new Point(821,375),new Point(828,250),new Point(675,251),new Point(738,249),new Point(588,250),new Point(600,159),new Point(672,160),new Point(782,158));
         weaponSpawns = new Array(new WeaponSpawnData(235,266,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(193,373,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(520,361,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(803,379,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(643,253,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(619,163,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)));
         portals = new Array(new PortalData(new Rectangle(848,234,20,24),new Rectangle(848,360,20,24),new Point(1,0),true,false),new PortalData(new Rectangle(848,360,20,24),new Rectangle(848,234,20,24),new Point(1,0),true,false));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,302.5 / 30,413 / 30,0,369 / 30,70 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,590 / 30,407 / 30,0,230 / 30,82 / 30,new Array("NONE"));
         stair = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,719 / 30,409 / 30,0,new Array([-14 / 30,-43 / 30],[-10 / 30,-43 / 30],[14 / 30,-25 / 30],[14 / 30,39 / 30],[-14 / 30,39 / 30]),new Array("NONE"));
         stair.GetUserData().tiltValue = 2;
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,818.5 / 30,416 / 30,0,171 / 30,64 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,886 / 30,372 / 30,0,36 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,876 / 30,309 / 30,0,56 / 30,102 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,876 / 30,117.5 / 30,0,56 / 30,233 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,886 / 30,246 / 30,0,36 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,822 / 30,163 / 30,0,52 / 30,34 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,777 / 30,174 / 30,0,38 / 30,12 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,637.5 / 30,174 / 30,0,171 / 30,12 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,716.5 / 30,201 / 30,0,13 / 30,42 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,558.5 / 30,201 / 30,0,13 / 30,42 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,733 / 30,193 / 30,0,20 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,749.5 / 30,216 / 30,0,45 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,749.5 / 30,238 / 30,0,45 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,629 / 30,276 / 30,0,154 / 30,36 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,777 / 30,282 / 30,0,142 / 30,48 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,558.5 / 30,312 / 30,0,13 / 30,36 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,712.5 / 30,321 / 30,0,13 / 30,30 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,125 / 30,341.5 / 30,0,14 / 30,73 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,248 / 30,273 / 30,0,38 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,299 / 30,273 / 30,0,38 / 30,4 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,273.5 / 30,301 / 30,0,13 / 30,118 / 30,new Array("LADDER"));
         Handler_WorldItems.CreateGroundCircle(Handler_WorldItems.Material.Metal,125 / 30,301 / 30,7 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,663 / 30,302.5 / 30,0,8 / 30,17 / 30,new Array("NONE"));
         perm_cover1 = Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,662.5 / 30,359.5 / 30,0,15 / 30,13 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,876 / 30,-36 / 30,0,56 / 30,74 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,238 / 30,317 / 30,0,58 / 30,4 / 30,new Array("CLOUD"));
         if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("COMFY_CHAIR",628 / 30,358 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("CHAIR,NONE",648 / 30,362 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE",612.5 / 30,356.5 / 30,0,new b2Vec2(),0);
         }
         if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("FILECAB",614 / 30,251.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER",603.5 / 30,254.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER",603.5 / 30,246.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER",595.5 / 30,254.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER",617 / 30,232.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER",614.5 / 30,240.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",627.5 / 30,251 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("FILECAB",627 / 30,236.5 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER",625.5 / 30,225.5 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("CRATE",610 / 30,251 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",625 / 30,251 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",611 / 30,236 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",626 / 30,236 / 30,0,new b2Vec2(),0);
         }
         if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",388 / 30,371 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",404 / 30,371 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",397 / 30,356 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("BARREL,BARREL_EXPLOSIVE",429 / 30,371 / 30,0,new b2Vec2(),0);
         }
         else
         {
            Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",422 / 30,371 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",403 / 30,371 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("BARREL,BARREL_EXPLOSIVE,NONE",390 / 30,371 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CRATE",456 / 30,371 / 30,0,new b2Vec2(),0);
         }
         Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",308 / 30,264 / 30,0,new b2Vec2(),0);
         propeller = Handler_WorldItems.AddObject("WINDMILL_PROPELLER",274 / 30,191 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("TABLE,CRATE,NONE",786 / 30,379 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CHAIR_R",677 / 30,361.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("COMFY_CHAIR,NONE",597 / 30,358 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("TABLE_SMALL",613 / 30,363.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("TABLE_SMALL",583 / 30,363.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE",219 / 30,308 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,BARREL",234 / 30,308 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",228 / 30,293 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",251 / 30,264 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",292 / 30,264 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",660 / 30,251 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,FILECAB",567 / 30,251 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("PAPER",578.5 / 30,254.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("PAPER,NONE",567 / 30,239.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE",690 / 30,251 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",707 / 30,251 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE,GASCAN",732 / 30,229 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,FILECAB,CRATE,NONE",766.5 / 30,207 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("TABLE,CRATE,NONE,NONE",804 / 30,253 / 30,0,new b2Vec2(),0);
         lamp1 = Handler_WorldItems.AddObject("LAMP_1",582 / 30,297.5 / 30,0,new b2Vec2(),0);
         lamp2 = Handler_WorldItems.AddObject("LAMP_1",612 / 30,297.5 / 30,0,new b2Vec2(),0);
         lamp3 = Handler_WorldItems.AddObject("LAMP_1",641 / 30,297.5 / 30,0,new b2Vec2(),0);
         lamp4 = Handler_WorldItems.AddObject("LAMP_1",686 / 30,297.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",808 / 30,139 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE,BARREL_EXPLOSIVE",832 / 30,139 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,NONE,BARREL_EXPLOSIVE",704 / 30,161 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",688 / 30,161 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE",565 / 30,161 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",581 / 30,161 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("GASCAN,CRATE,NONE",637 / 30,162.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",732 / 30,207 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL",499 / 30,359 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,BARREL",139 / 30,371.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL",154 / 30,371 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE",142 / 30,357 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",167 / 30,371 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",155 / 30,357 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE,BARREL_EXPLOSIVE",304 / 30,371 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",331 / 30,371 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",219 / 30,371 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",237 / 30,371 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,NONE,BARREL",317.5 / 30,371.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("GASCAN,NONE,NONE,NONE",256 / 30,311 / 30,0,new b2Vec2(),0);
         pathGrid.AddNode(new PathNode("",139,374,"",null));
         pathGrid.AddNode(new PathNode("",165,374,"",null));
         pathGrid.AddNode(new PathNode("",193,374,"",null));
         pathGrid.AddNode(new PathNode("",220,374,"",null));
         pathGrid.AddNode(new PathNode("",246,374,"",null));
         pathGrid.AddNode(new PathNode("",274,374,"",null));
         pathGrid.AddNode(new PathNode("",305,374,"",null));
         pathGrid.AddNode(new PathNode("",336,374,"",null));
         pathGrid.AddNode(new PathNode("",368,374,"",null));
         pathGrid.AddNode(new PathNode("",403,374,"",null));
         pathGrid.AddNode(new PathNode("",438,374,"",null));
         pathGrid.AddNode(new PathNode("",469,374,"",null));
         pathGrid.AddNode(new PathNode("",483,362,"",null));
         pathGrid.AddNode(new PathNode("",520,362,"",null));
         pathGrid.AddNode(new PathNode("",555,362,"",null));
         pathGrid.AddNode(new PathNode("",586,362,"",null));
         pathGrid.AddNode(new PathNode("",617,362,"",null));
         pathGrid.AddNode(new PathNode("",647,362,"",null));
         pathGrid.AddNode(new PathNode("",677,362,"",null));
         pathGrid.AddNode(new PathNode("",710,362,"",null));
         pathGrid.AddNode(new PathNode("",735,380,"",null));
         pathGrid.AddNode(new PathNode("",767,380,"",null));
         pathGrid.AddNode(new PathNode("",803,380,"",null));
         pathGrid.AddNode(new PathNode("",844,380,"",null));
         pathGrid.AddNode(new PathNode("",844,254,"",null));
         pathGrid.AddNode(new PathNode("",810,254,"",null));
         pathGrid.AddNode(new PathNode("",925,254,"",null));
         pathGrid.AddNode(new PathNode("",925,380,"",null));
         pathGrid.AddNode(new PathNode("",788,254,"",null));
         pathGrid.AddNode(new PathNode("",767,254,"",null));
         pathGrid.AddNode(new PathNode("",749,254,"",null));
         pathGrid.AddNode(new PathNode("",731,254,"",null));
         pathGrid.AddNode(new PathNode("",709,254,"",null));
         pathGrid.AddNode(new PathNode("",731,232,"",null));
         pathGrid.AddNode(new PathNode("",749,232,"",null));
         pathGrid.AddNode(new PathNode("",768,232,"",null));
         pathGrid.AddNode(new PathNode("",731,210,"",null));
         pathGrid.AddNode(new PathNode("",750,210,"",null));
         pathGrid.AddNode(new PathNode("",767,210,"",null));
         pathGrid.AddNode(new PathNode("",737,187,"",null));
         pathGrid.AddNode(new PathNode("",717,164,"",null));
         pathGrid.AddNode(new PathNode("",764,164,"",null));
         pathGrid.AddNode(new PathNode("",684,164,"",null));
         pathGrid.AddNode(new PathNode("",651,164,"",null));
         pathGrid.AddNode(new PathNode("",619,164,"",null));
         pathGrid.AddNode(new PathNode("",586,164,"",null));
         pathGrid.AddNode(new PathNode("",559,164,"",null));
         pathGrid.AddNode(new PathNode("",788,164,"",null));
         pathGrid.AddNode(new PathNode("",806,142,"",null));
         pathGrid.AddNode(new PathNode("",841,142,"",null));
         pathGrid.AddNode(new PathNode("",676,254,"",null));
         pathGrid.AddNode(new PathNode("",643,254,"",null));
         pathGrid.AddNode(new PathNode("",613,254,"",null));
         pathGrid.AddNode(new PathNode("",585,254,"",null));
         pathGrid.AddNode(new PathNode("",559,254,"",null));
         pathGrid.AddNode(new PathNode("",260,267,"",null));
         pathGrid.AddNode(new PathNode("",287,267,"",null));
         pathGrid.AddNode(new PathNode("",312,267,"",null));
         pathGrid.AddNode(new PathNode("",235,267,"",null));
         pathGrid.AddNode(new PathNode("",662,348,"",null));
         pathGrid.AddNode(new PathNode("",259,311,"",null));
         pathGrid.AddNode(new PathNode("",216,311,"",null));
         pathGrid.AddNode(new PathNode("",238,311,"",null));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[12],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[10],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[10],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[12],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[14],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[20],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[19],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[18],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[15],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[14],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[15],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[17],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[19],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[20],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[23],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[24],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[25],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[27],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[24],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[26],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[26],pathGrid.Nodes[23],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[31],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[30],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[29],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[25],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[29],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[30],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[31],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[35],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[33],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[34],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[35],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[33],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[34],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[33],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[34],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[35],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[30],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[29],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[31],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[38],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[37],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[36],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[37],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[36],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[37],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[38],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[33],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[34],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[35],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[36],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[25],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[39],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[39],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[36],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[37],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[41],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[40],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[44],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[43],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[43],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[40],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[42],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[42],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[44],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[46],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[10],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[41],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[40],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[48],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[47],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[49],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[48],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[41],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[47],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[54],pathGrid.Nodes[53],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[53],pathGrid.Nodes[52],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[52],pathGrid.Nodes[51],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[50],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[50],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[50],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[50],pathGrid.Nodes[51],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[52],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[52],pathGrid.Nodes[53],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[53],pathGrid.Nodes[54],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[54],pathGrid.Nodes[12],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[58],pathGrid.Nodes[55],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[55],pathGrid.Nodes[58],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[56],pathGrid.Nodes[57],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[57],pathGrid.Nodes[56],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[55],pathGrid.Nodes[5],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[56],pathGrid.Nodes[5],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[55],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[56],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[55],pathGrid.Nodes[56],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[56],pathGrid.Nodes[55],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[58],pathGrid.Nodes[1],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[57],pathGrid.Nodes[8],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[59],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[59],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[59],pathGrid.Nodes[17],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[59],pathGrid.Nodes[18],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[39],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[61],pathGrid.Nodes[1],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[61],pathGrid.Nodes[62],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[62],pathGrid.Nodes[60],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[60],pathGrid.Nodes[62],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[62],pathGrid.Nodes[61],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[60],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[60],pathGrid.Nodes[5],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[60],pathGrid.Nodes[6],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[41],PathBind.STATIC,PathBind.SPRINTJUMP));
         perm_cover1.GetUserData().allowCover = true;
         Handler_WorldItems.AddRevoluteJoint(Handler_WorldItems.Ground,propeller,propeller.GetPosition());
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp1,lamp1.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp2,lamp2.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp3,lamp3.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp4,lamp4.GetPosition(),0,0);
         rope1 = Handler_WorldItems.AddHangingLamp(new Point(588,180),20);
         rope2 = Handler_WorldItems.AddHangingLamp(new Point(635,180),20);
         rope3 = Handler_WorldItems.AddHangingLamp(new Point(686,180),20);
         rope4 = Handler_WorldItems.AddHangingLamp(new Point(795,180),20);
         rope5 = Handler_WorldItems.AddHangingLamp(new Point(823,180),20);
         ropea = Handler_WorldItems.AddHangingLamp(new Point(739,306),20);
         ropeb = Handler_WorldItems.AddHangingLamp(new Point(767,306),20);
         ropec = Handler_WorldItems.AddHangingLamp(new Point(796,306),20);
         roped = Handler_WorldItems.AddHangingLamp(new Point(825,306),20);
         Handler_WorldItems.AddGlass(new Point(553.5 / 30,221 / 30),new Point(553.5 / 30,258 / 30));
         Handler_WorldItems.AddGlass(new Point(661 / 30,310 / 30),new Point(661 / 30,341 / 30));
         MapStart = function():void
         {
            mapGraphic.AddMC(GetLevelMC("background_clouds"));
            mapGraphic.AddMC(GetLevelMC("fan_1"));
            mapGraphic.AddMC(GetLevelMC("fan_2"));
            mapGraphic.AddMC(GetLevelMC("fan_3"));
            mapGraphic.AddMC(GetLevelMC("fan_4"));
         };
         MapUpdate = function(param1:Number):void
         {
            rope1.UpdateMC();
            rope2.UpdateMC();
            rope3.UpdateMC();
            rope4.UpdateMC();
            rope5.UpdateMC();
            ropea.UpdateMC();
            ropeb.UpdateMC();
            ropec.UpdateMC();
            roped.UpdateMC();
         };
      }
      
      public function GetMinimumMapArea(param1:Number = 0) : Rectangle
      {
         return mapArea;
      }
      
      public function UpdateHandlers(param1:Effects, param2:Explosions, param3:Sounds, param4:BasicOverlays) : void
      {
         Handler_WorldItems.UpdateHandlers(param1,param2,param3,param4);
         _Handler_Sounds = param3;
         _Handler_Effects = param1;
      }
      
      private function GenerateMapStorage() : void
      {
         var stair02:b2Body = null;
         var stair01:b2Body = null;
         var stair03:b2Body = null;
         var lift:b2Body = null;
         var crate_hanging_1:b2Body = null;
         var crate_hanging_2:b2Body = null;
         var lamp2:b2Body = null;
         var lamp3:b2Body = null;
         var lamp1:b2Body = null;
         var lamp4:b2Body = null;
         var lamp5:b2Body = null;
         var lamp6:b2Body = null;
         var lamp7:b2Body = null;
         var lamp8:b2Body = null;
         var ropeLamp1:Rope = null;
         var ropeLamp2:Rope = null;
         var ropeLamp3:Rope = null;
         var closness:Number = NaN;
         var holder1:b2Body = null;
         var holder2:b2Body = null;
         var rope1:Rope = null;
         var rope2:Rope = null;
         var layer_mc:MovieClip = null;
         mapArea = new Rectangle(23,-26,477,365);
         playerSpawns = new Array(new Point(130,247),new Point(336,248),new Point(234,266),new Point(244,136),new Point(116,175),new Point(423,182),new Point(368,132),new Point(272,137),new Point(212,135),new Point(84,175),new Point(196,198),new Point(245,198),new Point(271,265),new Point(192,264),new Point(450,132),new Point(394,247),new Point(149,175),new Point(368,224),new Point(417,223),new Point(417,201),new Point(369,200),new Point(197,220),new Point(199,241),new Point(246,240),new Point(77,248),new Point(395,133));
         weaponSpawns = new Array(new WeaponSpawnData(197,161,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(125,106,new Array(0,1,1,1,1,0,0,0,1,0,1,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(366,136,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(120,250,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(385,184,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)),new WeaponSpawnData(246,224,new Array(1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0)));
         portals = new Array(new PortalData(new Rectangle(467,117,17,24),new Rectangle(467,165,17,24),new Point(1,0),true,false),new PortalData(new Rectangle(467,165,17,24),new Rectangle(467,117,17,24),new Point(1,0),true,false));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,176.5 / 30,26.5 / 30,0,351 / 30,51 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,431 / 30,41.5 / 30,0,184 / 30,81 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,345 / 30,94 / 30,0,12 / 30,24 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,495 / 30,99.5 / 30,0,56 / 30,35 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,411.5 / 30,147 / 30,0,145 / 30,12 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,503.5 / 30,153 / 30,0,39 / 30,72 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,495 / 30,259 / 30,0,56 / 30,140 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,475.5 / 30,159 / 30,0,17 / 30,12 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,27.5 / 30,190.5 / 30,0,53 / 30,277 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,104.5 / 30,120 / 30,0,73 / 30,18 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,90.5 / 30,292 / 30,0,73 / 30,74 / 30,new Array("NONE"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,230.5 / 30,301 / 30,0,147 / 30,56 / 30,new Array("NONE"));
         stair02 = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,143 / 30,294 / 30,0,new Array([-16 / 30,-39 / 30],[-10 / 30,-39 / 30],[14 / 30,-21 / 30],[14 / 30,35 / 30],[-16 / 30,35 / 30]),new Array("NONE"));
         stair02.GetUserData().tiltValue = 2;
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Ground,400.5 / 30,292 / 30,0,133 / 30,74 / 30,new Array("NONE"));
         stair01 = Handler_WorldItems.CreateGroundPolygon(Handler_WorldItems.Material.Ground,320 / 30,292 / 30,0,new Array([-16 / 30,-19 / 30],[8 / 30,-37 / 30],[14 / 30,-37 / 30],[14 / 30,37 / 30],[-16 / 30,37 / 30]),new Array("NONE"));
         stair01.GetUserData().tiltValue = -2;
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,246 / 30,145 / 30,0,102 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,197 / 30,167 / 30,0,50 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,105 / 30,184 / 30,0,102 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,221.5 / 30,208 / 30,0,93 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,221.5 / 30,230 / 30,0,93 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,221.5 / 30,252 / 30,0,93 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,392.5 / 30,212 / 30,0,93 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,392.5 / 30,234 / 30,0,93 / 30,2 / 30,new Array("CLOUD"));
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,423 / 30,190 / 30,0,88 / 30,2 / 30,new Array("CLOUD"));
         stair03 = Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,167 / 30,196 / 30,0.7853981633974483,34 / 30,3 / 30,new Array("CLOUD"));
         stair03.GetUserData().tiltValue = 2;
         Handler_WorldItems.CreateGroundBox(Handler_WorldItems.Material.Metal,60 / 30,139 / 30,0,12 / 30,83 / 30,new Array("LADDER"));
         if(50 >= Math.random() * 100)
         {
            Handler_WorldItems.AddObject("TABLE",420 / 30,136 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CHAIR",404 / 30,137 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("CHAIR_R",436 / 30,136 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("PAPER,NONE",416 / 30,126.5 / 30,0,new b2Vec2(),0);
         }
         else
         {
            if(50 >= Math.random() * 100)
            {
               Handler_WorldItems.AddObject("COMP_SCREEN",426 / 30,123 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("COMP",436 / 30,123 / 30,0,new b2Vec2(),0);
            }
            else
            {
               Handler_WorldItems.AddObject("PAPER",423.5 / 30,124.5 / 30,0,new b2Vec2(),0);
               Handler_WorldItems.AddObject("PAPER",433.5 / 30,124.5 / 30,0,new b2Vec2(),0);
            }
            Handler_WorldItems.AddObject("DESK_1",431 / 30,135 / 30,0,new b2Vec2(),0);
            Handler_WorldItems.AddObject("COMFY_CHAIR",410 / 30,133 / 30,0,new b2Vec2(),0);
         }
         lift = Handler_WorldItems.AddObject("LIFT_01",86.5 / 30,260 / 30,0,new b2Vec2(),0);
         crate_hanging_1 = Handler_WorldItems.AddObject("CRATE_HANGING",168 / 30,131 / 30,0,new b2Vec2(),0);
         crate_hanging_2 = Handler_WorldItems.AddObject("CRATE_HANGING",303 / 30,95 / 30,0,new b2Vec2(),0);
         lamp2 = Handler_WorldItems.AddObject("LAMP_1",367 / 30,156.5 / 30,0,new b2Vec2(),0);
         lamp3 = Handler_WorldItems.AddObject("LAMP_1",395 / 30,84.5 / 30,0,new b2Vec2(),0);
         lamp1 = Handler_WorldItems.AddObject("LAMP_1",423 / 30,156.5 / 30,0,new b2Vec2(),0);
         lamp4 = Handler_WorldItems.AddObject("LAMP_1",367 / 30,84.5 / 30,0,new b2Vec2(),0);
         lamp5 = Handler_WorldItems.AddObject("LAMP_1",423 / 30,84.5 / 30,0,new b2Vec2(),0);
         lamp6 = Handler_WorldItems.AddObject("LAMP_1",124 / 30,131.5 / 30,0,new b2Vec2(),0);
         lamp7 = Handler_WorldItems.AddObject("LAMP_1",85 / 30,131.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE,BARREL,NONE",281.5 / 30,136 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL,BARREL_EXPLOSIVE,NONE",230 / 30,137 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL,CRATE,NONE",351 / 30,203 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE",259 / 30,137 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,BARREL,CRATE,NONE",261 / 30,244 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE,BARREL_EXPLOSIVE",213 / 30,200 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL,CRATE",183 / 30,243 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",443.5 / 30,248 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",431 / 30,247 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL,BARREL_EXPLOSIVE,CRATE",96 / 30,247 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",109 / 30,103 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE",94 / 30,104 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,GASCAN",429 / 30,203 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,GASCAN,NONE,NONE",404 / 30,182 / 30,1.5707963267948966,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL,NONE,GASCAN,BARREL_EXPLOSIVE",260 / 30,200 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE,BARREL",132 / 30,174 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE,BARREL",101 / 30,174 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("GASCAN,NONE",215 / 30,162 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",221 / 30,221 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE",211 / 30,266 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,NONE,BARREL_EXPLOSIVE",355 / 30,247 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,BARREL,NONE,CRATE",375 / 30,247 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,GASCAN,NONE",392 / 30,226 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("BARREL_EXPLOSIVE,CRATE",390 / 30,203 / 30,0,new b2Vec2(),0);
         lamp8 = Handler_WorldItems.AddObject("LAMP_1",451 / 30,84.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("CRATE,BARREL_EXPLOSIVE,NONE",221 / 30,243 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("FILECAB",381.5 / 30,134.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("PAPER,NONE",382.5 / 30,123.5 / 30,0,new b2Vec2(),0);
         Handler_WorldItems.AddObject("PAPER,NONE",96.5 / 30,92.5 / 30,0,new b2Vec2(),0);
         pathGrid.AddNode(new PathNode("",161,268,"",null));
         pathGrid.AddNode(new PathNode("",135,250,"",null));
         pathGrid.AddNode(new PathNode("",180,247,"",null));
         pathGrid.AddNode(new PathNode("",180,225,"",null));
         pathGrid.AddNode(new PathNode("",222,247,"",null));
         pathGrid.AddNode(new PathNode("",222,225,"",null));
         pathGrid.AddNode(new PathNode("",221,203,"",null));
         pathGrid.AddNode(new PathNode("",201,225,"",null));
         pathGrid.AddNode(new PathNode("",201,247,"",null));
         pathGrid.AddNode(new PathNode("",201,269,"",null));
         pathGrid.AddNode(new PathNode("",180,269,"",null));
         pathGrid.AddNode(new PathNode("",222,269,"",null));
         pathGrid.AddNode(new PathNode("",243,269,"",null));
         pathGrid.AddNode(new PathNode("",263,269,"",null));
         pathGrid.AddNode(new PathNode("",262,247,"",null));
         pathGrid.AddNode(new PathNode("",262,225,"",null));
         pathGrid.AddNode(new PathNode("",243,247,"",null));
         pathGrid.AddNode(new PathNode("",243,225,"",null));
         pathGrid.AddNode(new PathNode("",242,203,"",null));
         pathGrid.AddNode(new PathNode("",262,203,"",null));
         pathGrid.AddNode(new PathNode("",201,203,"",null));
         pathGrid.AddNode(new PathNode("",184,203,"",null));
         pathGrid.AddNode(new PathNode("",154,179,"",null));
         pathGrid.AddNode(new PathNode("",181,162,"",null));
         pathGrid.AddNode(new PathNode("diveT",203,139,"",null));
         pathGrid.AddNode(new PathNode("",197,162,"",null));
         pathGrid.AddNode(new PathNode("",217,162,"",null));
         pathGrid.AddNode(new PathNode("",221,140,"",null));
         pathGrid.AddNode(new PathNode("",243,140,"",null));
         pathGrid.AddNode(new PathNode("",268,140,"",null));
         pathGrid.AddNode(new PathNode("",290,140,"",null));
         pathGrid.AddNode(new PathNode("",347,136,"",null));
         pathGrid.AddNode(new PathNode("",283,269,"",null));
         pathGrid.AddNode(new PathNode("",301,269,"",null));
         pathGrid.AddNode(new PathNode("",329,251,"",null));
         pathGrid.AddNode(new PathNode("",350,251,"",null));
         pathGrid.AddNode(new PathNode("",351,229,"",null));
         pathGrid.AddNode(new PathNode("",351,207,"",null));
         pathGrid.AddNode(new PathNode("",392,207,"",null));
         pathGrid.AddNode(new PathNode("",392,229,"",null));
         pathGrid.AddNode(new PathNode("",392,251,"",null));
         pathGrid.AddNode(new PathNode("",434,251,"",null));
         pathGrid.AddNode(new PathNode("",434,229,"",null));
         pathGrid.AddNode(new PathNode("",434,207,"",null));
         pathGrid.AddNode(new PathNode("",414,251,"",null));
         pathGrid.AddNode(new PathNode("",413,229,"",null));
         pathGrid.AddNode(new PathNode("",413,207,"",null));
         pathGrid.AddNode(new PathNode("",371,251,"",null));
         pathGrid.AddNode(new PathNode("",371,229,"",null));
         pathGrid.AddNode(new PathNode("",371,207,"",null));
         pathGrid.AddNode(new PathNode("",459,251,"",null));
         pathGrid.AddNode(new PathNode("",385,184,"",null));
         pathGrid.AddNode(new PathNode("",413,185,"",null));
         pathGrid.AddNode(new PathNode("",434,185,"",null));
         pathGrid.AddNode(new PathNode("",460,185,"",null));
         pathGrid.AddNode(new PathNode("",511,185,"",null));
         pathGrid.AddNode(new PathNode("",511,137,"",null));
         pathGrid.AddNode(new PathNode("",460,136,"",null));
         pathGrid.AddNode(new PathNode("",430,136,"",null));
         pathGrid.AddNode(new PathNode("",399,136,"",null));
         pathGrid.AddNode(new PathNode("",370,136,"",null));
         pathGrid.AddNode(new PathNode("",109,250,"",null));
         pathGrid.AddNode(new PathNode("",86,250,"",null));
         pathGrid.AddNode(new PathNode("",60,250,"",null));
         pathGrid.AddNode(new PathNode("",121,178,"",null));
         pathGrid.AddNode(new PathNode("",87,178,"",null));
         pathGrid.AddNode(new PathNode("",61,178,"",null));
         pathGrid.AddNode(new PathNode("",72.5,106,"",null));
         pathGrid.AddNode(new PathNode("",104,106,"",null));
         pathGrid.AddNode(new PathNode("diveS",135,106,"",null));
         pathGrid.AddNode(new PathNode("crate",158,120,"",crate_hanging_1));
         pathGrid.AddNode(new PathNode("crate",178,121,"",crate_hanging_1));
         pathGrid.AddNode(new PathNode("",86,252,"",lift));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[56],pathGrid.Nodes[54],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[55],pathGrid.Nodes[57],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[57],pathGrid.Nodes[56],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[54],pathGrid.Nodes[55],PathBind.STATIC,PathBind.PORTAL));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[57],pathGrid.Nodes[58],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[58],pathGrid.Nodes[59],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[59],pathGrid.Nodes[60],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[60],pathGrid.Nodes[31],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[60],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[60],pathGrid.Nodes[59],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[59],pathGrid.Nodes[58],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[58],pathGrid.Nodes[57],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[54],pathGrid.Nodes[53],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[53],pathGrid.Nodes[52],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[52],pathGrid.Nodes[51],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[52],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[52],pathGrid.Nodes[53],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[53],pathGrid.Nodes[54],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[49],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[46],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[43],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[46],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[38],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[49],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[48],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[42],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[45],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[39],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[48],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[36],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[50],pathGrid.Nodes[41],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[50],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[44],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[41],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[47],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[40],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[44],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[40],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[47],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[35],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[33],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[33],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[12],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[13],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[12],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[10],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[11],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[9],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[10],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[63],pathGrid.Nodes[62],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[62],pathGrid.Nodes[63],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[62],pathGrid.Nodes[61],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[61],pathGrid.Nodes[1],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[61],pathGrid.Nodes[62],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[61],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[27],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[29],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[30],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[29],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[29],pathGrid.Nodes[28],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[28],pathGrid.Nodes[27],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[24],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[26],pathGrid.Nodes[25],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[23],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[25],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[26],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[18],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[20],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[20],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[6],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[18],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[19],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[17],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[3],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[14],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[16],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[4],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[8],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[2],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[7],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[5],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[17],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[15],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[21],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[64],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[64],pathGrid.Nodes[65],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[65],pathGrid.Nodes[66],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[66],pathGrid.Nodes[65],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[65],pathGrid.Nodes[64],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[64],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[67],pathGrid.Nodes[68],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[68],pathGrid.Nodes[69],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[69],pathGrid.Nodes[68],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[68],pathGrid.Nodes[67],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[67],pathGrid.Nodes[66],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[66],pathGrid.Nodes[67],PathBind.STATIC,PathBind.LADDER));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[0],pathGrid.Nodes[2],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[32],pathGrid.Nodes[14],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[34],pathGrid.Nodes[36],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[50],pathGrid.Nodes[42],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[51],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[51],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[52],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[53],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[54],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[43],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[46],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[38],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[49],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[37],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[46],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[38],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[49],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[37],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[43],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[46],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[38],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[49],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[42],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[45],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[39],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[48],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[36],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[41],pathGrid.Nodes[45],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[39],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[48],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[36],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[35],pathGrid.Nodes[48],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[40],pathGrid.Nodes[45],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[47],pathGrid.Nodes[39],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[44],pathGrid.Nodes[42],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[33],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[33],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[33],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[26],pathGrid.Nodes[27],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[24],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[27],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[24],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[27],pathGrid.Nodes[26],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[25],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[23],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[22],pathGrid.Nodes[23],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[22],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[30],pathGrid.Nodes[31],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[30],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[1],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[53],pathGrid.Nodes[43],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[52],pathGrid.Nodes[46],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[38],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[37],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[51],pathGrid.Nodes[49],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[37],pathGrid.Nodes[36],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[49],pathGrid.Nodes[48],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[38],pathGrid.Nodes[39],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[46],pathGrid.Nodes[45],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[43],pathGrid.Nodes[42],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[41],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[42],pathGrid.Nodes[50],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[45],pathGrid.Nodes[44],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[39],pathGrid.Nodes[40],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[48],pathGrid.Nodes[47],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[35],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[36],pathGrid.Nodes[34],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[32],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[0],PathBind.STATIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[2],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[8],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[4],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[16],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[14],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[15],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[17],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[5],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[7],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[7],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[3],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[21],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[20],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[6],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[18],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[19],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[13],pathGrid.Nodes[16],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[4],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[8],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[2],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[10],pathGrid.Nodes[8],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[9],pathGrid.Nodes[4],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[11],pathGrid.Nodes[16],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[12],pathGrid.Nodes[14],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[17],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[5],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[3],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[7],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[5],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[17],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[15],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[18],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[6],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[20],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[21],PathBind.STATIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[20],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[6],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[18],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[19],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[1],pathGrid.Nodes[2],PathBind.STATIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[19],pathGrid.Nodes[15],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[15],pathGrid.Nodes[14],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[14],pathGrid.Nodes[13],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[21],pathGrid.Nodes[3],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[3],pathGrid.Nodes[2],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[2],pathGrid.Nodes[10],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[20],pathGrid.Nodes[7],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[7],pathGrid.Nodes[8],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[8],pathGrid.Nodes[9],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[6],pathGrid.Nodes[5],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[5],pathGrid.Nodes[4],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[4],pathGrid.Nodes[11],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[18],pathGrid.Nodes[17],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[17],pathGrid.Nodes[16],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[16],pathGrid.Nodes[12],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[26],pathGrid.Nodes[6],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[25],pathGrid.Nodes[20],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[23],pathGrid.Nodes[21],PathBind.STATIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[71],pathGrid.Nodes[24],PathBind.DYNAMIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[24],pathGrid.Nodes[71],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[70],pathGrid.Nodes[71],PathBind.DYNAMIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[71],pathGrid.Nodes[70],PathBind.DYNAMIC,PathBind.ROAD));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[70],pathGrid.Nodes[69],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[69],pathGrid.Nodes[70],PathBind.DYNAMIC,PathBind.SPRINTJUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[72],pathGrid.Nodes[62],PathBind.DYNAMIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[62],pathGrid.Nodes[72],PathBind.DYNAMIC,PathBind.JUMP));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[65],pathGrid.Nodes[72],PathBind.DYNAMIC,PathBind.CLOUDDOWN));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[31],pathGrid.Nodes[19],PathBind.STATIC,PathBind.DIVE));
         pathGrid.AddBind(new PathBind("",pathGrid.Nodes[72],pathGrid.Nodes[65],PathBind.DYNAMIC,PathBind.JUMP));
         ropeLamp1 = Handler_WorldItems.AddHangingLamp(new Point(139,52),20);
         ropeLamp2 = Handler_WorldItems.AddHangingLamp(new Point(267,52),20);
         ropeLamp3 = Handler_WorldItems.AddHangingLamp(new Point(203,52),20);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp1,lamp1.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp2,lamp2.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp3,lamp3.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp4,lamp4.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp5,lamp5.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp6,lamp6.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp7,lamp7.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(Handler_WorldItems.Ground,lamp8,lamp8.GetPosition(),0,0);
         closness = 0.5 / 30;
         holder1 = Handler_WorldItems.AddObject("CRATE_HANGING_HOLDER",crate_hanging_1.GetPosition().x,crate_hanging_1.GetPosition().y - crate_hanging_1.GetUserData().height / 30 * 0.5,0,new b2Vec2(),0);
         holder2 = Handler_WorldItems.AddObject("CRATE_HANGING_HOLDER",crate_hanging_2.GetPosition().x,crate_hanging_2.GetPosition().y - crate_hanging_2.GetUserData().height / 30 * 0.5,0,new b2Vec2(),0);
         Handler_WorldItems.AddLimitedJoint(crate_hanging_1,holder1,holder1.GetPosition(),0,0);
         Handler_WorldItems.AddLimitedJoint(crate_hanging_2,holder2,holder2.GetPosition(),0,0);
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder1,new b2Vec2(holder1.GetPosition().x,51 / 30),new b2Vec2(holder1.GetPosition().x + closness,holder1.GetPosition().y - holder1.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder1,new b2Vec2(holder1.GetPosition().x,51 / 30),new b2Vec2(holder1.GetPosition().x - closness,holder1.GetPosition().y - holder1.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder2,new b2Vec2(holder2.GetPosition().x,51 / 30),new b2Vec2(holder2.GetPosition().x + closness,holder2.GetPosition().y - holder2.GetUserData().height / 30 * 0.5));
         Handler_WorldItems.AddDistanceJoint(Handler_WorldItems.Ground,holder2,new b2Vec2(holder2.GetPosition().x,51 / 30),new b2Vec2(holder2.GetPosition().x - closness,holder2.GetPosition().y - holder2.GetUserData().height / 30 * 0.5));
         crate_hanging_1.ApplyForce(new b2Vec2(Math.random() * 10 - 5,Math.random()),new b2Vec2(crate_hanging_1.GetPosition().x + Math.random() * 2 - 1,crate_hanging_1.GetPosition().y));
         crate_hanging_2.ApplyForce(new b2Vec2(Math.random() * 10 - 5,Math.random()),new b2Vec2(crate_hanging_2.GetPosition().x + Math.random() * 2 - 1,crate_hanging_2.GetPosition().y));
         Handler_WorldItems.AddGlass(new Point(341 / 30,105 / 30),new Point(341 / 30,142 / 30));
         CreateElevator(lift,66,1);
         rope1 = new Rope(Handler_WorldItems.Ground,holder1,new b2Vec2(holder1.GetPosition().x,51 / 30),new b2Vec2(holder1.GetPosition().x,holder1.GetPosition().y - holder1.GetUserData().height / 30 * 0.5));
         rope2 = new Rope(Handler_WorldItems.Ground,holder2,new b2Vec2(holder2.GetPosition().x,51 / 30),new b2Vec2(holder2.GetPosition().x,holder2.GetPosition().y - holder2.GetUserData().height / 30 * 0.5));
         layer_mc = MovieClip(_dynamic_mc.getChildByName("OBJECTS"));
         layer_mc.addChild(rope1.MC);
         layer_mc.addChild(rope2.MC);
         MapUpdate = function(param1:Number):void
         {
            rope1.UpdateMC();
            rope2.UpdateMC();
            ropeLamp1.UpdateMC();
            ropeLamp2.UpdateMC();
            ropeLamp3.UpdateMC();
         };
         holder1.GetUserData().onDestruction = function(param1:b2Body):void
         {
            rope1.Remove();
            pathGrid.RemoveNodes("CRATE");
            pathGrid.AddBind(new PathBind("",pathGrid.GetNode("diveS"),pathGrid.GetNode("diveT"),PathBind.STATIC,PathBind.DIVE));
            pathGrid.UpdateSpecials();
            pathGrid.AnalyzeGrid();
         };
         holder2.GetUserData().onDestruction = function(param1:b2Body):void
         {
            rope2.Remove();
         };
         MapStart = function():void
         {
            mapGraphic.AddMC(GetLevelMC("fan_1"));
            mapGraphic.AddMC(GetLevelMC("fan_2"));
            mapGraphic.AddMC(GetLevelMC("fan_3"));
         };
      }
   }
}

