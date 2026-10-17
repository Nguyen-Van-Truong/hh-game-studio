package Code.Handler
{
   import Code.Box2D.Common.Math.*;
   
   public class CommandList
   {
      private var _Handler_Box2DMouse:Box2DMouse;
      
      private var _menu:Array;
      
      private var _Handler_Fires:Fires;
      
      private var _Handler_Maps:Maps;
      
      private var _curr_menu:int = 0;
      
      private var _Handler_Effects:Effects;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _Handler_Weapons:Weapons;
      
      private var _Handler_Explosions:Explosions;
      
      private var _Handler_Output:OutputTrace;
      
      private var _Restart:Function;
      
      private var _Handler_Players:PlayersKeeper;
      
      private var _Handler_Sounds:Sounds;
      
      public function CommandList(param1:OutputTrace)
      {
         _curr_menu = 0;
         _menu = new Array([["",function():*
         {
         }]],[["Prev",function():*
         {
            _curr_menu = 3;
            PrintMenu();
         }],["Next",function():*
         {
            _curr_menu = 2;
            PrintMenu();
         }],["Pistol",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_pistol",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Pistol;
         }],["Rifle",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_rifle",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Rifle;
         }],["Shotgun",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_shotgun",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Shotgun;
         }],["Sniper",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_sniper",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Sniper;
         }],["Bazooka",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_bazooka",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Bazooka;
         }],["Flamethrower",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_flamethrower",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Flamethrower;
         }]],[["Prev",function():*
         {
            _curr_menu = 1;
            PrintMenu();
         }],["Next",function():*
         {
            _curr_menu = 3;
            PrintMenu();
         }],["Grenades",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_grenades",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Grenades;
         }],["Molotovs",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_molotovs",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Molotovs;
         }],["Axe",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_axe",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Axe;
         }],["Machete",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_machete",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Machete;
         }],["Sword",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_sword",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Sword;
         }],["Slowmotion (5)",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_slowmo_05",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Slowmo05;
         }],["Slowmotion (10)",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_slowmo_10",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Slowmo10;
         }]],[["Prev",function():*
         {
            _curr_menu = 2;
            PrintMenu();
         }],["Next",function():*
         {
            _curr_menu = 1;
            PrintMenu();
         }],["Pills",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_pills",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Pills;
         }],["Medkit",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_medkit",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Medkit;
         }],["Magnum",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_magnum",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Magnum;
         }],["Uzi",function():*
         {
            var _loc1_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_uzi",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
            _loc1_.GetUserData().weaponData = _Handler_Weapons.Uzi;
         }]],[["Prev",function():*
         {
            _curr_menu = 5;
            PrintMenu();
         }],["Next",function():*
         {
            _curr_menu = 5;
            PrintMenu();
         }],["Barrel",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("barrel",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Barrel Explosive",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("barrel_explosive",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Barrel Wreck",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("barrel_wreck",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Crate",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("crate",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Table",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("table",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Comfy Chair",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("comfy_chair",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Trashcan",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("Trashcan",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }]],[["Prev",function():*
         {
            _curr_menu = 4;
            PrintMenu();
         }],["Next",function():*
         {
            _curr_menu = 4;
            PrintMenu();
         }],["Gascan",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("gascan",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Filecab",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("filecab",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Pool Table",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("pool_table",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Beachball",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("beachball",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Rolling Pipe",function():*
         {
            _Handler_Maps.Handler_WorldItems.AddObject("rolling_pipe",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys(),0,new b2Vec2(),0);
         }],["Statue Globe",function():*
         {
            var _loc1_:* = undefined;
            var _loc2_:* = undefined;
            _loc1_ = _Handler_Maps.Handler_WorldItems.AddObject("statue_globe",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys() - 30 / 30,0,new b2Vec2(),0);
            _loc1_.PutToSleep();
            _loc2_ = _Handler_Maps.Handler_WorldItems.AddObject("statue",_Handler_Box2DMouse.GetMouseXWorldPhys(),_Handler_Box2DMouse.GetMouseYWorldPhys() - 9 / 30,0,new b2Vec2(),0);
            _loc2_.PutToSleep();
         }]],[["Holder",function():*
         {
         }],["Holder",function():*
         {
         }]],[["Holder",function():*
         {
         }],["Holder",function():*
         {
         }]],[["Holder",function():*
         {
         }],["Holder",function():*
         {
         }]],[["Holder",function():*
         {
         }],["Holder",function():*
         {
         }]]);
         super();
         _Handler_Output = param1;
      }
      
      public function PrintMenu() : void
      {
         var _loc1_:int = 0;
         _Handler_Output.Clear();
         _loc1_ = _menu[_curr_menu].length - 1;
         while(_loc1_ >= 0)
         {
            if(_menu[_curr_menu][_loc1_][0] != "")
            {
               _Handler_Output.Trace(_loc1_ + 1 + " - " + _menu[_curr_menu][_loc1_][0]);
            }
            _loc1_--;
         }
      }
      
      private function CallMethod() : void
      {
         var _loc1_:int = 0;
         if(_Handler_Keyboard.KeyIsDown(16))
         {
            _loc1_ = 0;
            while(_loc1_ < _menu[_curr_menu].length)
            {
               if(_Handler_Keyboard.KeyIsDown(49 + _loc1_))
               {
                  _menu[_curr_menu][_loc1_][1]();
               }
               _loc1_++;
            }
         }
      }
      
      public function LinkFunctions(param1:Function) : void
      {
         _Restart = param1;
      }
      
      private function ShowList() : void
      {
         _curr_menu = 0;
         _Handler_Output.Show();
         PrintMenu();
      }
      
      private function HideList() : void
      {
         _Handler_Output.Hide();
      }
      
      public function LinkHandlers(param1:Maps, param2:Box2DMouse, param3:InputKeyboard, param4:Effects, param5:Sounds, param6:Explosions, param7:Fires, param8:Weapons, param9:PlayersKeeper) : void
      {
         var _loc10_:int = 0;
         _Handler_Maps = param1;
         _Handler_Box2DMouse = param2;
         _Handler_Keyboard = param3;
         _Handler_Effects = param4;
         _Handler_Sounds = param5;
         _Handler_Explosions = param6;
         _Handler_Fires = param7;
         _Handler_Weapons = param8;
         _Handler_Players = param9;
         _Handler_Keyboard.AddHandler(16,ShowList,HideList);
         _loc10_ = 49;
         while(_loc10_ < 58)
         {
            _Handler_Keyboard.AddHandler(_loc10_,CallMethod);
            _loc10_++;
         }
      }
   }
}

