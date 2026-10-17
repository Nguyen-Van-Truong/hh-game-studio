package Code.Handler
{
   import Code.Particles.*;
   import flash.display.MovieClip;
   
   public class Effects extends MovieClip
   {
      private static var EFFECT_LAYER_BACK:int = 0;
      
      private static var EFFECT_LAYER_FRONT:int = 1;
      
      private static var EFFECT_PRIMARY:int = 0;
      
      private static var EFFECT_SECONDARY:int = 1;
      
      private var _Handler_Output:OutputTrace;
      
      private var _effect_behind_mc:MovieClip;
      
      private var _Handler_Options:Options;
      
      private var _effect_mc_primary:MovieClip;
      
      private var _game_speed:Number = 1;
      
      private var _Handler_Maps:Maps;
      
      private var _effect_mc:MovieClip;
      
      private var _effect_mc_secondary:MovieClip;
      
      private var _effect_behind_mc_primary:MovieClip;
      
      private var _effect_behind_mc_secondary:MovieClip;
      
      public function Effects(param1:OutputTrace, param2:MovieClip, param3:MovieClip, param4:Options, param5:Maps)
      {
         _game_speed = 1;
         super();
         _Handler_Output = param1;
         _effect_behind_mc = param2;
         _effect_mc = param3;
         _Handler_Options = param4;
         _Handler_Maps = param5;
         _effect_mc_primary = new MovieClip();
         _effect_mc_secondary = new MovieClip();
         _effect_behind_mc_primary = new MovieClip();
         _effect_behind_mc_secondary = new MovieClip();
         _effect_mc.addChild(_effect_mc_primary);
         _effect_mc.addChild(_effect_mc_secondary);
         _effect_behind_mc.addChild(_effect_behind_mc_primary);
         _effect_behind_mc.addChild(_effect_behind_mc_secondary);
      }
      
      private function CanAddSecondaryEffect() : Boolean
      {
         if(TotalEffects >= _Handler_Options.GetTotalEffects())
         {
            return RemoveRandomSecondaryEffect();
         }
         return true;
      }
      
      public function Stop() : void
      {
         StopParticlesIn(_effect_mc_primary);
         StopParticlesIn(_effect_mc_secondary);
         StopParticlesIn(_effect_behind_mc_primary);
         StopParticlesIn(_effect_behind_mc_secondary);
      }
      
      public function AddParticle_Box2DScale(param1:particle_data) : void
      {
         param1.PosX = Math.round(param1.PosX * 30);
         param1.PosY = Math.round(param1.PosY * 30);
         AddParticle(param1);
      }
      
      public function AddParticle(param1:particle_data) : void
      {
         var _loc2_:MovieClip = null;
         var _loc3_:* = undefined;
         var _loc4_:* = undefined;
         var _loc5_:MovieClip = null;
         var _loc6_:MovieClip = null;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:int = 0;
         var _loc10_:MovieClip = null;
         var _loc11_:Number = NaN;
         var _loc12_:Number = NaN;
         var _loc13_:MovieClip = null;
         var _loc14_:Number = NaN;
         if(param1.Effect != "")
         {
            _loc3_ = EFFECT_PRIMARY;
            _loc4_ = EFFECT_LAYER_FRONT;
            switch(param1.Effect)
            {
               case "PROJECTILE_LIGHT_TRACE":
                  _loc2_ = new simple_effect(new bullet_effect_normal());
                  break;
               case "GIB":
                  _loc2_ = new simple_effect(new gib_effect());
                  break;
               case "TRACE_AXE_01":
                  _loc2_ = new simple_effect(new trace_axe_01());
                  break;
               case "TRACE_AXE_02":
                  _loc2_ = new simple_effect(new trace_axe_02());
                  break;
               case "TRACE_AXE_03":
                  _loc2_ = new simple_effect(new trace_axe_03());
                  break;
               case "TRACE_MACHETE_01":
                  _loc2_ = new simple_effect(new trace_machete_01());
                  break;
               case "TRACE_MACHETE_02":
                  _loc2_ = new simple_effect(new trace_machete_02());
                  break;
               case "TRACE_MACHETE_03":
                  _loc2_ = new simple_effect(new trace_machete_03());
                  break;
               case "TRACE_SWORD_01":
                  _loc2_ = new simple_effect(new trace_sword_01());
                  break;
               case "TRACE_SWORD_02":
                  _loc2_ = new simple_effect(new trace_sword_02());
                  break;
               case "TRACE_SWORD_03":
                  _loc2_ = new simple_effect(new trace_sword_03());
                  break;
               case "TRACE_BAZOOKA_ROCKET":
                  _loc2_ = new fire_effect_bazooka_rocket(param1);
                  break;
               case "BULLET_TRACE_SLOMO":
                  _loc2_ = new simple_effect(new bullet_trace_slomo());
                  break;
               case "BUBBLE":
                  if(_Handler_Options.GetEffectLevel() >= 3 || _Handler_Options.GetEffectLevel() == 2 && Math.random() < 0.5)
                  {
                     _loc2_ = new simple_effect(new bubble());
                     _loc3_ = EFFECT_SECONDARY;
                     break;
                  }
                  return;
                  break;
               case "DUST":
               case "WOOD":
                  _loc2_ = new particle_impact_wood(param1);
                  _loc3_ = EFFECT_SECONDARY;
                  break;
               case "METAL":
                  _loc2_ = new particle_impact_metal(param1);
                  _loc3_ = EFFECT_SECONDARY;
                  break;
               case "SMOKE_TRACE_EFFECT":
                  _loc2_ = new smoke_trace_effect(param1);
                  _loc3_ = EFFECT_SECONDARY;
                  break;
               case "SMOKE_FIRE":
                  if(_Handler_Options.GetEffectLevel() >= 3)
                  {
                     _loc2_ = new smoke_fire(param1);
                     _loc3_ = EFFECT_SECONDARY;
                     _loc4_ = EFFECT_LAYER_BACK;
                     break;
                  }
                  return;
                  break;
               case "EXPLOSION_CIRCLE":
                  _loc5_ = new explosion_circle();
                  _loc5_.gotoAndPlay(2);
                  _loc2_ = new simple_effect(_loc5_);
                  break;
               case "FILECAB_HIT":
                  param1.Effect = "PAPER_HIT";
                  AddParticle(param1);
                  param1.Effect = "BULLET_HITMETAL";
                  AddParticle(param1);
                  return;
               case "EXPLOSION_CENTRUM":
                  _loc6_ = new explosion_circle();
                  _loc6_.gotoAndPlay(3);
                  _loc2_ = new simple_effect(_loc6_);
                  _loc9_ = 0;
                  while(_loc9_ < 360)
                  {
                     _loc11_ = 12 + Math.random() * 7;
                     _loc12_ = (_loc9_ + Math.random() * 40 - 20) * (Math.PI / 180);
                     _loc13_ = new explosion_circle();
                     (_loc10_ = new simple_effect(_loc13_)).CurrentFrame = Math.round(0.51 + Math.random() * 2.98);
                     _loc10_.x = param1.PosX + Math.cos(_loc12_) * _loc11_;
                     _loc10_.y = param1.PosY + Math.sin(_loc12_) * _loc11_;
                     _loc10_.rotation = param1.Rotation;
                     _loc10_.alpha = param1.Alpha;
                     _loc10_.scaleX = param1.ScaleX * _loc10_.scaleX;
                     _loc10_.scaleY = param1.ScaleY * _loc10_.scaleY;
                     _effect_mc_primary.addChild(_loc10_);
                     _loc10_.game_speed = _game_speed;
                     _loc9_ += 60;
                  }
                  break;
               case "BULLET_HITMETAL":
                  param1.Alpha = 0.8;
                  switch(Math.floor(Math.random() * 4.99))
                  {
                     case 0:
                        _loc2_ = new simple_effect(new hit_metal_1_1());
                        break;
                     case 1:
                        _loc2_ = new simple_effect(new hit_metal_1_2());
                        break;
                     case 2:
                        _loc2_ = new simple_effect(new hit_metal_2_1());
                        break;
                     case 3:
                        _loc2_ = new simple_effect(new hit_metal_2_2());
                        break;
                     case 4:
                        _loc2_ = new simple_effect(new hit_metal_3_1());
                  }
                  break;
               case "HITDEFAULT_01":
                  _loc2_ = new bullet_hitdefault(param1);
                  _loc3_ = EFFECT_SECONDARY;
                  break;
               case "PLAYER_BURNED":
                  param1.Effect = "HITDEFAULT_01";
                  _loc7_ = param1.PosX;
                  _loc8_ = param1.PosY;
                  AddParticle(param1);
                  _loc14_ = 0;
                  while(_loc14_ < Math.PI * 2)
                  {
                     param1.PosX = _loc7_ + Math.cos(_loc14_) * 6;
                     param1.PosY = _loc8_ + Math.sin(_loc14_) * 6;
                     AddParticle(param1);
                     _loc14_ += Math.PI / 4;
                  }
                  return;
               case "ELECTRIC_SPARK":
                  param1.Alpha = 0.8;
                  switch(Math.floor(Math.random() * 2.99))
                  {
                     case 0:
                        _loc2_ = new simple_effect(new electric_1());
                        break;
                     case 1:
                        _loc2_ = new simple_effect(new electric_2());
                        break;
                     case 2:
                        _loc2_ = new simple_effect(new electric_3());
                  }
                  break;
               case "PLAYER_BURNED_HITDEFAULT":
               case "BULLET_HITDEFAULT":
                  param1.Effect = "HITDEFAULT_01";
                  AddParticle(param1);
                  AddParticle(param1);
                  if(_Handler_Options.GetEffectLevel() >= 2)
                  {
                     AddParticle(param1);
                  }
                  return;
               case "PARTICLE_BLOOD":
                  if(param1.DataArray == null)
                  {
                     param1.DataArray = new Array();
                     if(Math.random() < 0.5)
                     {
                        param1.DataArray.push(0);
                     }
                     else
                     {
                        param1.DataArray.push(1);
                     }
                  }
                  _loc2_ = new particle_blood(param1);
                  _loc3_ = EFFECT_SECONDARY;
                  break;
               case "BLOOD":
                  switch(Math.round(Math.random() * 2))
                  {
                     case 0:
                        _loc2_ = new simple_effect(new blood_1());
                        break;
                     case 1:
                        _loc2_ = new simple_effect(new blood_2());
                        break;
                     case 2:
                        _loc2_ = new simple_effect(new blood_3());
                  }
                  break;
               case "BLOOD_GIB_TRACE":
                  if(_Handler_Options.GetEffectLevel() >= 2)
                  {
                     _loc2_ = new blood_gib_trace(param1);
                     _loc3_ = EFFECT_SECONDARY;
                     break;
                  }
                  return;
                  break;
               case "FIRE":
                  _loc2_ = new fire_effect(param1);
                  break;
               case "BODYFALL":
                  _loc2_ = new particle_bodyfall(param1);
                  break;
               case "FIRE_FLAMETHROWER":
                  _loc2_ = new fire_effect_flamethrower(param1);
                  break;
               case "FIREGROUND":
                  if(_Handler_Options.GetEffectLevel() >= 2)
                  {
                     _loc2_ = new fire_effect_ground(param1);
                     _loc3_ = EFFECT_SECONDARY;
                     break;
                  }
                  return;
                  break;
               case "DIVE_IMPACT":
               case "KICK_IMPACT":
               case "FIST_IMPACT":
               case "BULLET_IMPACT":
               case "BULLET_WHITE_SQUARE":
                  _loc2_ = new simple_effect(new bullet_impact());
                  break;
               case "MUZZLE_WEAPON_SMOKE":
                  if(_Handler_Options.GetEffectLevel() >= 2)
                  {
                     _loc2_ = new muzzle_weapon_smoke(param1);
                     _loc3_ = EFFECT_SECONDARY;
                     _loc4_ = EFFECT_LAYER_BACK;
                     break;
                  }
                  return;
                  break;
               case "MUZZLE_FLASH_PISTOL":
                  param1.Effect = "MUZZLE_WEAPON_SMOKE";
                  AddParticle(param1);
                  AddParticle(param1);
                  _loc2_ = new simple_effect(new muzzle_flash_pistol());
                  break;
               case "MUZZLE_FLASH_SNIPER":
                  param1.Effect = "MUZZLE_WEAPON_SMOKE";
                  AddParticle(param1);
                  AddParticle(param1);
                  AddParticle(param1);
                  _loc2_ = new simple_effect(new muzzle_flash_sniper());
                  break;
               case "MUZZLE_FLASH_RIFLE":
                  param1.Effect = "MUZZLE_WEAPON_SMOKE";
                  AddParticle(param1);
                  _loc2_ = new simple_effect(new muzzle_flash_rifle());
                  break;
               case "MUZZLE_FLASH_BAZOOKA":
                  _loc2_ = new simple_effect(new muzzle_flash_bazooka());
                  break;
               case "MUZZLE_FLASH_SHOTGUN":
                  param1.Effect = "MUZZLE_WEAPON_SMOKE";
                  AddParticle(param1);
                  AddParticle(param1);
                  AddParticle(param1);
                  AddParticle(param1);
                  _loc2_ = new simple_effect(new muzzle_flash_shotgun());
                  break;
               case "SPARK":
                  if(_Handler_Options.GetEffectLevel() >= 3)
                  {
                     _Handler_Maps.Handler_WorldItems.AddBox("spark",param1.PosX / 30,param1.PosY / 30,0,param1.ParticleVec,0);
                  }
                  return;
               case "EMPTY_SHELL_SMALL":
                  if(_Handler_Options.GetEffectLevel() >= 3)
                  {
                     _Handler_Maps.Handler_WorldItems.AddBox("EMPTY_SHELL_SMALL",param1.PosX / 30,param1.PosY / 30,param1.Rotation,param1.ParticleVec,Math.random() * 10 - 5);
                  }
                  return;
               case "EMPTY_SHELL_SHOTGUN":
                  if(_Handler_Options.GetEffectLevel() >= 3)
                  {
                     _Handler_Maps.Handler_WorldItems.AddBox("EMPTY_SHELL_SHOTGUN",param1.PosX / 30,param1.PosY / 30,param1.Rotation,param1.ParticleVec,Math.random() * 10 - 5);
                  }
                  return;
               case "EMPTY_SHELL_BIG":
                  if(_Handler_Options.GetEffectLevel() >= 3)
                  {
                     _Handler_Maps.Handler_WorldItems.AddBox("EMPTY_SHELL_BIG",param1.PosX / 30,param1.PosY / 30,param1.Rotation,param1.ParticleVec,Math.random() * 10 - 5);
                  }
                  return;
               case "PAPER_HIT":
                  _loc2_ = new simple_effect(new hit_paper());
                  if(Math.random() < 0.5)
                  {
                     param1.ScaleX = 1;
                  }
                  else
                  {
                     param1.ScaleX = -1;
                  }
                  break;
               case "PICKUP_AXE":
               case "PICKUP_BAZOOKA":
               case "PICKUP_FLAMETHROWER":
               case "PICKUP_SHOTGUN":
               case "PICKUP_PISTOL":
               case "PICKUP_MAGNUM":
               case "PICKUP_RIFLE":
               case "PICKUP_SNIPER":
               case "PICKUP_MACHETE":
               case "PICKUP_SWORD":
               case "PICKUP_GRENADE":
               case "PICKUP_MOLOTOV":
               case "PICKUP_UZI":
               case "PICKUP_SLOMO05":
               case "PICKUP_SLOMO10":
                  param1.ScaleX = 0.75;
                  param1.ScaleY = 0.75;
                  _loc2_ = new pickup_sign(param1);
                  break;
               default:
                  _loc2_ = new error_mc();
                  return;
            }
            if(_loc3_ == EFFECT_SECONDARY)
            {
               if(!CanAddSecondaryEffect())
               {
                  _loc2_.EndParticle();
                  return;
               }
            }
            _loc2_.x = param1.PosX;
            _loc2_.y = param1.PosY;
            _loc2_.rotation = param1.Rotation;
            _loc2_.alpha = param1.Alpha;
            _loc2_.scaleX = param1.ScaleX * _loc2_.scaleX;
            _loc2_.scaleY = param1.ScaleY * _loc2_.scaleY;
            if(_loc4_ == EFFECT_LAYER_FRONT)
            {
               if(_loc3_ == EFFECT_PRIMARY)
               {
                  _effect_mc_primary.addChild(_loc2_);
               }
               else
               {
                  _effect_mc_secondary.addChild(_loc2_);
               }
            }
            else if(_loc3_ == EFFECT_PRIMARY)
            {
               _effect_behind_mc_primary.addChild(_loc2_);
            }
            else
            {
               _effect_behind_mc_secondary.addChild(_loc2_);
            }
            _loc2_.game_speed = _game_speed;
         }
      }
      
      private function StopParticlesIn(param1:MovieClip) : void
      {
         var _loc2_:int = 0;
         _loc2_ = param1.numChildren;
         while(_loc2_ > 0)
         {
            _loc2_--;
            MovieClip(param1.getChildAt(_loc2_)).EndParticle();
         }
      }
      
      public function get TotalEffects() : int
      {
         return _effect_mc_primary.numChildren + _effect_mc_secondary.numChildren + _effect_behind_mc_primary.numChildren + _effect_behind_mc_secondary.numChildren;
      }
      
      public function AddEffectAt(param1:String, param2:Number, param3:Number) : void
      {
         AddParticle(new particle_data(param1,param2,param3));
      }
      
      public function AddEffectAt_Box2DScale(param1:String, param2:Number, param3:Number) : void
      {
         AddEffectAt(param1,param2 * 30,param3 * 30);
      }
      
      public function get EffectMCFront() : MovieClip
      {
         return _effect_mc;
      }
      
      public function get EffectMCBack() : MovieClip
      {
         return _effect_behind_mc;
      }
      
      private function RemoveRandomEffectFrom(param1:MovieClip) : Boolean
      {
         var _loc2_:* = undefined;
         if(param1.numChildren <= 0)
         {
            return false;
         }
         _loc2_ = Math.floor(Math.random() * (param1.numChildren - 0.0001));
         if(_loc2_ < 0)
         {
            _loc2_ = 0;
         }
         MovieClip(param1.getChildAt(_loc2_)).EndParticle();
         return true;
      }
      
      public function RemoveRandomSecondaryEffect() : Boolean
      {
         if(_effect_mc_secondary.numChildren <= 0)
         {
            return RemoveRandomEffectFrom(_effect_behind_mc_secondary);
         }
         if(_effect_behind_mc_secondary.numChildren <= 0)
         {
            return RemoveRandomEffectFrom(_effect_mc_secondary);
         }
         if(Math.random() < 0.5)
         {
            return RemoveRandomEffectFrom(_effect_behind_mc_secondary);
         }
         return RemoveRandomEffectFrom(_effect_mc_secondary);
      }
      
      public function SetSlowmotion(param1:Number) : void
      {
         _game_speed = param1;
         SetSlowmotionIn(_effect_mc_primary);
         SetSlowmotionIn(_effect_mc_secondary);
         SetSlowmotionIn(_effect_behind_mc_primary);
         SetSlowmotionIn(_effect_behind_mc_secondary);
      }
      
      private function SetSlowmotionIn(param1:MovieClip) : void
      {
         var _loc2_:int = 0;
         _loc2_ = param1.numChildren;
         while(_loc2_ > 0)
         {
            _loc2_--;
            MovieClip(param1.getChildAt(_loc2_)).game_speed = _game_speed;
         }
      }
   }
}

