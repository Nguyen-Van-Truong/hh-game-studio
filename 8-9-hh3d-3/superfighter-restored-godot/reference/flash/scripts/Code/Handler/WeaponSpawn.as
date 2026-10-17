package Code.Handler
{
   import Code.Box2D.Common.Math.b2Vec2;
   import Code.Box2D.Dynamics.b2Body;
   import Code.Data.WeaponSpawnData;
   
   public class WeaponSpawn
   {
      private var _Handler_Weapons:Weapons;
      
      private var _spawnTimer:Number;
      
      private var _Handler_Maps:Maps;
      
      private var _spawnInterval:Number = 72;
      
      private var _WeaponSpawns:Array;
      
      private var _weaponSpawnChance:Array;
      
      private var _Handler_Output:OutputTrace;
      
      public function WeaponSpawn(param1:OutputTrace, param2:Maps, param3:Weapons)
      {
         _spawnInterval = 72;
         super();
         _Handler_Output = param1;
         _Handler_Maps = param2;
         _Handler_Weapons = param3;
         _WeaponSpawns = _Handler_Maps.GetWeaponSpawns();
         _spawnTimer = _spawnInterval;
         _weaponSpawnChance = new Array();
         _weaponSpawnChance.push(11);
         _weaponSpawnChance.push(9);
         _weaponSpawnChance.push(7);
         _weaponSpawnChance.push(2);
         _weaponSpawnChance.push(2);
         _weaponSpawnChance.push(4);
         _weaponSpawnChance.push(6);
         _weaponSpawnChance.push(5);
         _weaponSpawnChance.push(2);
         _weaponSpawnChance.push(3);
         _weaponSpawnChance.push(3);
         _weaponSpawnChance.push(4);
         _weaponSpawnChance.push(3);
         _weaponSpawnChance.push(2);
         _weaponSpawnChance.push(2);
         _weaponSpawnChance.push(2);
         _weaponSpawnChance.push(6);
         _Handler_Output.Trace("Weapon Spawn Created");
      }
      
      public function Update(param1:Number) : void
      {
         var w:int = 0;
         var tmpArr:Array = null;
         var i:int = 0;
         var rndIndex:int = 0;
         var wpnData:WeaponSpawnData = null;
         var wpnIndexes:Array = null;
         var j:int = 0;
         var wpnToSpawn:Array = null;
         var spawnValue:int = 0;
         var k:int = 0;
         var rndWeapon:int = 0;
         var wpn:b2Body = null;
         var l:int = 0;
         var game_speed:Number = param1;
         w = 0;
         while(w < _WeaponSpawns.length)
         {
            _WeaponSpawns[w].Update(game_speed);
            w++;
         }
         _spawnTimer -= game_speed;
         if(_spawnTimer <= 0)
         {
            _spawnTimer = _spawnInterval;
            tmpArr = new Array();
            i = 0;
            while(i < _WeaponSpawns.length)
            {
               if(_WeaponSpawns[i].LinkedWeapon == null && !_WeaponSpawns[i].SkipThisOnce)
               {
                  tmpArr.push(_WeaponSpawns[i]);
               }
               i++;
            }
            if(tmpArr.length <= 0)
            {
               return;
            }
            rndIndex = Math.floor(Math.random() * tmpArr.length);
            wpnData = tmpArr[rndIndex];
            wpnIndexes = new Array();
            j = 0;
            while(j < wpnData.WeaponArray.length)
            {
               if(wpnData.WeaponArray[j] == 1)
               {
                  wpnIndexes.push(j);
               }
               j++;
            }
            if(wpnIndexes.length <= 0)
            {
               return;
            }
            wpnToSpawn = new Array();
            spawnValue = 0;
            k = 0;
            while(k < wpnIndexes.length)
            {
               spawnValue = int(_weaponSpawnChance[wpnIndexes[k]]);
               l = 0;
               while(l < spawnValue)
               {
                  wpnToSpawn.push(wpnIndexes[k]);
                  l++;
               }
               k++;
            }
            rndWeapon = Math.floor(Math.random() * wpnToSpawn.length);
            switch(wpnToSpawn[rndWeapon])
            {
               case 0:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_pistol",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Pistol;
                  break;
               case 1:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_rifle",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Rifle;
                  break;
               case 2:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_shotgun",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Shotgun;
                  break;
               case 3:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_sniper",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Sniper;
                  break;
               case 4:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_bazooka",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Bazooka;
                  break;
               case 5:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_molotovs",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Molotovs;
                  break;
               case 6:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_grenades",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Grenades;
                  break;
               case 7:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_flamethrower",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Flamethrower;
                  break;
               case 8:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_sword",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Sword;
                  break;
               case 9:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_machete",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Machete;
                  break;
               case 10:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_axe",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Axe;
                  break;
               case 11:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_slowmo_05",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Slowmo05;
                  break;
               case 12:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_slowmo_10",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Slowmo10;
                  break;
               case 13:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_pills",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Pills;
                  break;
               case 14:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_medkit",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Medkit;
                  break;
               case 15:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_magnum",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Magnum;
                  break;
               case 16:
                  wpn = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_uzi",wpnData.PositionX / 30,wpnData.PositionY / 30,0,new b2Vec2(),0);
                  wpn.GetUserData().weaponData = _Handler_Weapons.Uzi;
            }
            if(wpn != null)
            {
               wpn.GetUserData().objectData.UpdateFunction = function(param1:b2Body, param2:Number):void
               {
               };
               wpn.PutToSleep();
               wpnData.LinkedWeapon = wpn;
            }
         }
      }
   }
}

