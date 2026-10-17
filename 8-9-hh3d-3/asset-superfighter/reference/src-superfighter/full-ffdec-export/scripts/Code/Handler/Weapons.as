package Code.Handler
{
   import Code.Data.Weapons.*;
   
   public class Weapons
   {
      private var w_rifle:WeaponData;
      
      private var p_magnum:WeaponProperties;
      
      private var p_bazooka:WeaponProperties;
      
      private var wt_grenades:WeaponThrowableData;
      
      private var w_bazooka:WeaponData;
      
      private var wm_machete:WeaponMeleeData;
      
      private var p_uzi:WeaponProperties;
      
      private var w_slowmo_05:WeaponPowerupData;
      
      private var w_magnum:WeaponData;
      
      private var w_uzi:WeaponData;
      
      private var p_sniper:WeaponProperties;
      
      private var w_pills:WeaponPowerupData;
      
      private var w_health_p:WeaponPowerupProperties;
      
      private var wm_axe:WeaponMeleeData;
      
      private var p_pistol:WeaponProperties;
      
      private var w_slowmo_10:WeaponPowerupData;
      
      private var w_sniper:WeaponData;
      
      private var p_rifle:WeaponProperties;
      
      private var pm_sword:WeaponMeleeProperties;
      
      private var w_shotgun:WeaponData;
      
      private var wt_molotovs:WeaponThrowableData;
      
      private var pt_grenades:WeaponThrowableProperties;
      
      private var pm_machete:WeaponMeleeProperties;
      
      private var p_shotgun:WeaponProperties;
      
      private var w_flamethrower:WeaponData;
      
      private var pm_fists:WeaponMeleeProperties;
      
      private var w_pistol:WeaponData;
      
      private var w_slowmo_p_05:WeaponPowerupProperties;
      
      private var w_medkit:WeaponPowerupData;
      
      private var pm_axe:WeaponMeleeProperties;
      
      private var wm_sword:WeaponMeleeData;
      
      private var w_slowmo_p_10:WeaponPowerupProperties;
      
      private var wm_fists:WeaponMeleeData;
      
      private var w_projectiles:Projectiles;
      
      private var p_flamethrower:WeaponProperties;
      
      private var _Handler_Output:OutputTrace;
      
      private var pt_molotovs:WeaponThrowableProperties;
      
      public function Weapons(param1:OutputTrace)
      {
         p_pistol = new WeaponProperties();
         p_rifle = new WeaponProperties();
         p_uzi = new WeaponProperties();
         p_shotgun = new WeaponProperties();
         p_sniper = new WeaponProperties();
         p_magnum = new WeaponProperties();
         p_bazooka = new WeaponProperties();
         p_flamethrower = new WeaponProperties();
         pt_grenades = new WeaponThrowableProperties();
         pt_molotovs = new WeaponThrowableProperties();
         pm_machete = new WeaponMeleeProperties();
         pm_sword = new WeaponMeleeProperties();
         pm_fists = new WeaponMeleeProperties();
         pm_axe = new WeaponMeleeProperties();
         w_slowmo_p_05 = new WeaponPowerupProperties();
         w_slowmo_p_10 = new WeaponPowerupProperties();
         w_health_p = new WeaponPowerupProperties();
         super();
         _Handler_Output = param1;
         w_projectiles = new Projectiles(_Handler_Output);
         pm_axe.WeaponType = "AXE";
         pm_axe.PickupSound = "MELEE_GRAB";
         pm_axe.PickupRadius = 10;
         pm_axe.HitPunchFrameDamage = new Array(11,12,13);
         pm_axe.Animation = "AXE";
         pm_axe.HitSound = "KATANA_HIT";
         pm_axe.Range = new Array(18,18,20);
         pm_axe.HitMaterialSounds = new Array(["WOOD","BULLET_HITDEFAULT"],["METAL","BULLET_HITMETAL"]);
         pm_axe.HitMaterialEffects = new Array(["WOOD","HITDEFAULT_01"]);
         pm_axe.SwingComboSounds = new Array("MELEE_SWING","MELEE_SWING","MELEE_SWING");
         pm_axe.SwingComboEffects = new Array("TRACE_AXE_01","TRACE_AXE_02","TRACE_AXE_03");
         wm_axe = new WeaponMeleeData(3,pm_axe);
         pm_sword.WeaponType = "SWORD";
         pm_sword.PickupSound = "MELEE_GRAB";
         pm_sword.PickupRadius = 10;
         pm_sword.HitPunchFrameDamage = new Array(13,14,15);
         pm_sword.Animation = "SWORD";
         pm_sword.HitSound = "KATANA_HIT";
         pm_sword.Range = new Array(18,18,23);
         pm_sword.HitMaterialSounds = new Array(["WOOD","BULLET_HITDEFAULT"],["METAL","BULLET_HITMETAL"]);
         pm_sword.HitMaterialEffects = new Array(["WOOD","HITDEFAULT_01"]);
         pm_sword.SwingComboSounds = new Array("MELEE_SWING","MELEE_SWING","MELEE_SWING");
         pm_sword.SwingComboEffects = new Array("TRACE_SWORD_01","TRACE_SWORD_02","TRACE_SWORD_03");
         wm_sword = new WeaponMeleeData(3,pm_sword);
         pm_machete.WeaponType = "MACHETE";
         pm_machete.PickupSound = "MELEE_GRAB";
         pm_machete.PickupRadius = 10;
         pm_machete.HitPunchFrameDamage = new Array(8,9,10);
         pm_machete.Animation = "MACHETE";
         pm_machete.HitSound = "KATANA_HIT";
         pm_machete.Range = new Array(13,13,19);
         pm_machete.HitMaterialSounds = new Array(["WOOD","BULLET_HITDEFAULT"],["METAL","BULLET_HITMETAL"]);
         pm_machete.HitMaterialEffects = new Array(["WOOD","HITDEFAULT_01"]);
         pm_machete.SwingComboSounds = new Array("MELEE_SWING","MELEE_SWING","MELEE_SWING");
         pm_machete.SwingComboEffects = new Array("TRACE_MACHETE_01","TRACE_MACHETE_02","TRACE_MACHETE_03");
         wm_machete = new WeaponMeleeData(3,pm_machete);
         pm_fists.WeaponType = "FISTS";
         pm_fists.PickupSound = "";
         pm_fists.PickupRadius = 0;
         pm_fists.HitPunchFrameDamage = new Array(6,7,8);
         pm_fists.Animation = "PUNCH";
         pm_fists.HitSound = "MELEE_HIT";
         pm_fists.Range = new Array(10,11,13);
         pm_fists.HitMaterialSounds = new Array(["WOOD","BULLET_HITDEFAULT"]);
         pm_fists.HitMaterialEffects = new Array(["WOOD","HITDEFAULT_01"]);
         pm_fists.SwingComboSounds = new Array("MELEE_SWING","MELEE_SWING","MELEE_SWING");
         pm_fists.SwingComboEffects = new Array("","","");
         wm_fists = new WeaponMeleeData(3,pm_fists);
         pt_grenades.WeaponType = "GRENADE";
         pt_grenades.AnimType = "GRENADE";
         pt_grenades.ThrowType = "GRENADE";
         pt_grenades.ThrowTimer = 24 * 3;
         pt_grenades.AimSound = "GRENADE_SAFE";
         pt_grenades.PickupSound = "GRENADE_SAFE";
         pt_grenades.PickupRadius = 10;
         wt_grenades = new WeaponThrowableData(3,pt_grenades);
         pt_molotovs.WeaponType = "MOLOTOV";
         pt_molotovs.AnimType = "MOLOTOV";
         pt_molotovs.ThrowType = "MOLOTOV";
         pt_molotovs.ThrowTimer = 0;
         pt_molotovs.AimSound = "SND_PLACEHOLDER";
         pt_molotovs.PickupSound = "GRENADE_SAFE";
         pt_molotovs.PickupRadius = 10;
         wt_molotovs = new WeaponThrowableData(3,pt_molotovs);
         p_pistol.WeaponType = "PISTOL";
         p_pistol.AnimType = "PISTOL";
         p_pistol.WeaponCooldown = 6;
         p_pistol.AccuracyDeflection = 1;
         p_pistol.AimSound = "PISTOL_AIM";
         p_pistol.EmptySound = "NOAMMO_LIGHT";
         p_pistol.PickupSound = "PISTOL_AIM";
         p_pistol.BulletType = "PISTOL_BULLET";
         p_pistol.PickupRadius = 10;
         p_pistol.LaserSight = false;
         p_pistol.MuzzleFlashEffect = "MUZZLE_FLASH_PISTOL";
         p_pistol.ShellEffect = "EMPTY_SHELL_SMALL";
         p_pistol.Projectile = w_projectiles.Pistol_Bullet;
         p_pistol.ShootRange = 900;
         p_pistol.FireSequence.push(new WeaponSequencePart(1,true,true,"PISTOL_FIRE",2));
         p_pistol.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_pistol = new WeaponData(12,p_pistol);
         p_rifle.WeaponType = "RIFLE";
         p_rifle.AnimType = "RIFLE";
         p_rifle.WeaponCooldown = 6;
         p_rifle.AccuracyDeflection = 3;
         p_rifle.AimSound = "RIFLE_AIM";
         p_rifle.EmptySound = "NOAMMO_HEAVY";
         p_rifle.PickupSound = "RIFLE_AIM";
         p_rifle.BulletType = "RIFLE_BULLET";
         p_rifle.PickupRadius = 16;
         p_rifle.LaserSight = false;
         p_rifle.MuzzleFlashEffect = "MUZZLE_FLASH_RIFLE";
         p_rifle.ShellEffect = "EMPTY_SHELL_SMALL";
         p_rifle.Projectile = w_projectiles.Rifle_Bullet;
         p_rifle.ShootRange = 900;
         p_rifle.FireSequence.push(new WeaponSequencePart(1,true,true,"RIFLE_FIRE",2));
         p_rifle.FireSequence.push(new WeaponSequencePart());
         p_rifle.FireSequence.push(new WeaponSequencePart(1,true,true,"RIFLE_FIRE",2));
         p_rifle.FireSequence.push(new WeaponSequencePart());
         p_rifle.FireSequence.push(new WeaponSequencePart(1,true,true,"RIFLE_FIRE",2));
         p_rifle.FireSequence.push(new WeaponSequencePart());
         p_rifle.FireSequence.push(new WeaponSequencePart(1,true,true,"RIFLE_FIRE",2));
         p_rifle.FireSequence.push(new WeaponSequencePart());
         p_rifle.FireSequence.push(new WeaponSequencePart(1,true,true,"RIFLE_FIRE",2));
         p_rifle.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_rifle = new WeaponData(5 * 5,p_rifle);
         p_uzi.WeaponType = "UZI";
         p_uzi.AnimType = "UZI";
         p_uzi.WeaponCooldown = 6;
         p_uzi.AccuracyDeflection = 6;
         p_uzi.AimSound = "UZI_AIM";
         p_uzi.EmptySound = "NOAMMO_LIGHT";
         p_uzi.PickupSound = "UZI_AIM";
         p_uzi.BulletType = "UZI_BULLET";
         p_uzi.PickupRadius = 16;
         p_uzi.LaserSight = false;
         p_uzi.MuzzleFlashEffect = "MUZZLE_FLASH_PISTOL";
         p_uzi.ShellEffect = "EMPTY_SHELL_SMALL";
         p_uzi.Projectile = w_projectiles.Uzi_Bullet;
         p_uzi.ShootRange = 900;
         p_uzi.FireSequence.push(new WeaponSequencePart(1,true,true,"UZI_FIRE",2));
         p_uzi.FireSequence.push(new WeaponSequencePart());
         p_uzi.FireSequence.push(new WeaponSequencePart(1,true,true,"UZI_FIRE",2));
         p_uzi.FireSequence.push(new WeaponSequencePart());
         p_uzi.FireSequence.push(new WeaponSequencePart(1,true,true,"UZI_FIRE",2));
         p_uzi.FireSequence.push(new WeaponSequencePart());
         p_uzi.FireSequence.push(new WeaponSequencePart(1,true,true,"UZI_FIRE",2));
         p_uzi.FireSequence.push(new WeaponSequencePart());
         p_uzi.FireSequence.push(new WeaponSequencePart(1,true,true,"UZI_FIRE",2));
         p_uzi.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_uzi = new WeaponData(5 * 5,p_uzi);
         p_shotgun.WeaponType = "SHOTGUN";
         p_shotgun.AnimType = "SHOTGUN";
         p_shotgun.WeaponCooldown = 3;
         p_shotgun.AccuracyDeflection = 4.2;
         p_shotgun.AimSound = "SHOTGUN_AIM";
         p_shotgun.EmptySound = "NOAMMO_HEAVY";
         p_shotgun.PickupSound = "SHOTGUN_AIM";
         p_shotgun.BulletType = "SHOTGUN_BULLET";
         p_shotgun.PickupRadius = 14;
         p_shotgun.LaserSight = false;
         p_shotgun.MuzzleFlashEffect = "MUZZLE_FLASH_SHOTGUN";
         p_shotgun.ShellEffect = "EMPTY_SHELL_SHOTGUN";
         p_shotgun.Projectile = w_projectiles.Shotgun_Bullet;
         p_shotgun.ShootRange = 900;
         p_shotgun.FireSequence.push(new WeaponSequencePart(4,true,false,"SHOTGUN_FIRE",2));
         p_shotgun.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",2));
         p_shotgun.FireSequence.push(new WeaponSequencePart());
         p_shotgun.FireSequence.push(new WeaponSequencePart());
         p_shotgun.FireSequence.push(new WeaponSequencePart());
         p_shotgun.FireSequence.push(new WeaponSequencePart(0,false,true,"SHOTGUN_PUMP_P1",3));
         p_shotgun.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",3));
         p_shotgun.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",3));
         p_shotgun.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",3));
         p_shotgun.FireSequence.push(new WeaponSequencePart());
         p_shotgun.FireSequence.push(new WeaponSequencePart(0,false,false,"SHOTGUN_PUMP_P2",1,true));
         w_shotgun = new WeaponData(8 * 4,p_shotgun);
         p_magnum.WeaponType = "MAGNUM";
         p_magnum.AnimType = "MAGNUM";
         p_magnum.WeaponCooldown = 8;
         p_magnum.AccuracyDeflection = 0.5;
         p_magnum.AimSound = "MAGNUM_AIM";
         p_magnum.EmptySound = "NOAMMO_HEAVY";
         p_magnum.PickupSound = "MAGNUM_AIM";
         p_magnum.BulletType = "MAGNUM_BULLET";
         p_magnum.PickupRadius = 10;
         p_magnum.LaserSight = false;
         p_magnum.LaserDeflection = 0.5;
         p_magnum.MuzzleFlashEffect = "MUZZLE_FLASH_SHOTGUN";
         p_magnum.ShellEffect = "EMPTY_SHELL_SMALL";
         p_magnum.Projectile = w_projectiles.Magnum_Bullet;
         p_magnum.ShootRange = 900;
         p_magnum.FireSequence.push(new WeaponSequencePart(1,true,false,"MAGNUM_FIRE",2));
         p_magnum.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_magnum = new WeaponData(6,p_magnum);
         p_sniper.WeaponType = "SNIPER";
         p_sniper.AnimType = "SNIPER";
         p_sniper.WeaponCooldown = 18;
         p_sniper.AccuracyDeflection = 0;
         p_sniper.AimSound = "SNIPER_AIM";
         p_sniper.EmptySound = "NOAMMO_HEAVY";
         p_sniper.PickupSound = "SNIPER_AIM";
         p_sniper.BulletType = "SNIPER_BULLET";
         p_sniper.PickupRadius = 16;
         p_sniper.LaserSight = true;
         p_sniper.LaserDeflection = 0.5;
         p_sniper.MuzzleFlashEffect = "MUZZLE_FLASH_SNIPER";
         p_sniper.ShellEffect = "EMPTY_SHELL_BIG";
         p_sniper.Projectile = w_projectiles.Sniper_Bullet;
         p_sniper.ShootRange = 900;
         p_sniper.FireSequence.push(new WeaponSequencePart(1,true,true,"SNIPER_FIRE",2));
         p_sniper.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",2));
         p_sniper.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_sniper = new WeaponData(5,p_sniper);
         p_bazooka.WeaponType = "BAZOOKA";
         p_bazooka.AnimType = "BAZOOKA";
         p_bazooka.WeaponCooldown = 10;
         p_bazooka.AccuracyDeflection = 2;
         p_bazooka.AimSound = "BAZOOKA_AIM";
         p_bazooka.EmptySound = "NOAMMO_HEAVY";
         p_bazooka.PickupSound = "BAZOOKA_AIM";
         p_bazooka.BulletType = "BAZOOKA_ROCKET";
         p_bazooka.PickupRadius = 16;
         p_bazooka.LaserSight = false;
         p_bazooka.MuzzleFlashEffect = "MUZZLE_FLASH_BAZOOKA";
         p_bazooka.ShellEffect = "";
         p_bazooka.Projectile = w_projectiles.Bazooka_Rocket;
         p_bazooka.ShootRange = 400;
         p_bazooka.FireSequence.push(new WeaponSequencePart(1,true,false,"BAZOOKA_FIRE",2));
         p_bazooka.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",2));
         p_bazooka.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_bazooka = new WeaponData(3,p_bazooka);
         p_flamethrower.WeaponType = "FLAMETHROWER";
         p_flamethrower.AnimType = "FLAMETHROWER";
         p_flamethrower.WeaponCooldown = 10;
         p_flamethrower.AccuracyDeflection = 6;
         p_flamethrower.AimSound = "FLAMETHROWER_AIM";
         p_flamethrower.EmptySound = "NOAMMO_LIGHT";
         p_flamethrower.PickupSound = "FLAMETHROWER_AIM";
         p_flamethrower.BulletType = "FLAME";
         p_flamethrower.PickupRadius = 16;
         p_flamethrower.LaserSight = false;
         p_flamethrower.MuzzleFlashEffect = "";
         p_flamethrower.ShellEffect = "";
         p_flamethrower.Projectile = null;
         p_flamethrower.ShootRange = 140;
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"FLAMETHROWER_FIRE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(1,false,false,"NONE",1));
         p_flamethrower.FireSequence.push(new WeaponSequencePart(0,false,false,"NONE",1,true));
         w_flamethrower = new WeaponData(60,p_flamethrower);
         w_slowmo_p_05.WeaponType = "SLOMO05";
         w_slowmo_p_05.PickupSound = "SND_PLACEHOLDER";
         w_slowmo_p_05.PickupRadius = 12;
         w_slowmo_p_10.WeaponType = "SLOMO10";
         w_slowmo_p_10.PickupSound = "SND_PLACEHOLDER";
         w_slowmo_p_10.PickupRadius = 12;
         w_slowmo_05 = new WeaponPowerupData(5,w_slowmo_p_05);
         w_slowmo_10 = new WeaponPowerupData(10,w_slowmo_p_10);
         w_health_p.PickupSound = "GET_HEALTH";
         w_health_p.PickupRadius = 12;
         w_pills = new WeaponPowerupData(25,w_health_p);
         w_medkit = new WeaponPowerupData(50,w_health_p);
         _Handler_Output.Trace("Weapons Created");
      }
      
      public function get Shotgun() : WeaponData
      {
         return w_shotgun.Copy();
      }
      
      public function get Grenades() : WeaponThrowableData
      {
         return wt_grenades.Copy();
      }
      
      public function get Fists() : WeaponMeleeData
      {
         return wm_fists.Copy();
      }
      
      public function get Sniper() : WeaponData
      {
         return w_sniper.Copy();
      }
      
      public function get Flamethrower() : WeaponData
      {
         return w_flamethrower.Copy();
      }
      
      public function get Axe() : WeaponMeleeData
      {
         return wm_axe.Copy();
      }
      
      public function get Molotovs() : WeaponThrowableData
      {
         return wt_molotovs.Copy();
      }
      
      public function get Bazooka() : WeaponData
      {
         return w_bazooka.Copy();
      }
      
      public function get Pistol() : WeaponData
      {
         return w_pistol.Copy();
      }
      
      public function get Rifle() : WeaponData
      {
         return w_rifle.Copy();
      }
      
      public function get Slowmo05() : WeaponPowerupData
      {
         return w_slowmo_05.Copy();
      }
      
      public function get Uzi() : WeaponData
      {
         return w_uzi.Copy();
      }
      
      public function get Sword() : WeaponMeleeData
      {
         return wm_sword.Copy();
      }
      
      public function get Medkit() : WeaponPowerupData
      {
         return w_medkit.Copy();
      }
      
      public function get Machete() : WeaponMeleeData
      {
         return wm_machete.Copy();
      }
      
      public function get Pills() : WeaponPowerupData
      {
         return w_pills.Copy();
      }
      
      public function get Slowmo10() : WeaponPowerupData
      {
         return w_slowmo_10.Copy();
      }
      
      public function get Magnum() : WeaponData
      {
         return w_magnum.Copy();
      }
   }
}

