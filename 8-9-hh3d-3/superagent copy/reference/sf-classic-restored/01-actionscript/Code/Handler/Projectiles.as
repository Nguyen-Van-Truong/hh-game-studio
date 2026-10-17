package Code.Handler
{
   import Code.Data.ProjectileData;
   import Code.Data.ProjectileProperties;
   
   public class Projectiles
   {
      private var p_sniper_bullet:ProjectileProperties;
      
      private var p_rifle_bullet:ProjectileProperties;
      
      private var p_shotgun_bullet:ProjectileProperties;
      
      private var d_magnum_bullet:ProjectileData;
      
      private var d_rifle_bullet:ProjectileData;
      
      private var d_shotgun_bullet:ProjectileData;
      
      private var p_magnum_bullet:ProjectileProperties;
      
      private var p_uzi_bullet:ProjectileProperties;
      
      private var d_pistol_bullet:ProjectileData;
      
      private var p_bazooka_rocket:ProjectileProperties;
      
      private var _Handler_Output:OutputTrace;
      
      private var d_sniper_bullet:ProjectileData;
      
      private var d_uzi_bullet:ProjectileData;
      
      private var p_pistol_bullet:ProjectileProperties;
      
      private var d_bazooka_rocket:ProjectileData;
      
      public function Projectiles(param1:OutputTrace)
      {
         p_pistol_bullet = new ProjectileProperties();
         p_shotgun_bullet = new ProjectileProperties();
         p_rifle_bullet = new ProjectileProperties();
         p_uzi_bullet = new ProjectileProperties();
         p_sniper_bullet = new ProjectileProperties();
         p_magnum_bullet = new ProjectileProperties();
         p_bazooka_rocket = new ProjectileProperties();
         super();
         _Handler_Output = param1;
         p_bazooka_rocket.Speed = 18;
         p_bazooka_rocket.Damage = 100;
         p_bazooka_rocket.CriticalChance = 0;
         p_bazooka_rocket.CriticalDamage = 0;
         p_bazooka_rocket.PushbackPower = 0;
         p_bazooka_rocket.TotalPenetrationDepth = 0;
         p_bazooka_rocket.SinglePenetrationDepth = 0;
         p_bazooka_rocket.BulletMC = "BAZOOKA_ROCKET";
         p_bazooka_rocket.BulletEffect = "";
         p_bazooka_rocket.BulletSlomoEffect = "";
         p_bazooka_rocket.Strength = 1;
         p_bazooka_rocket.ImpulseForce = 3;
         d_bazooka_rocket = new ProjectileData(p_bazooka_rocket);
         p_pistol_bullet.Speed = 30;
         p_pistol_bullet.Damage = 10;
         p_pistol_bullet.CriticalChance = 5;
         p_pistol_bullet.CriticalDamage = 15;
         p_pistol_bullet.PushbackPower = 15;
         p_pistol_bullet.TotalPenetrationDepth = 12;
         p_pistol_bullet.SinglePenetrationDepth = 5;
         p_pistol_bullet.BulletMC = "PISTOL_BULLET";
         p_pistol_bullet.BulletEffect = "BULLET_EFFECT_NORMAL";
         p_pistol_bullet.BulletSlomoEffect = "BULLET_EFFECT_SLOMO";
         p_pistol_bullet.Strength = 5;
         p_pistol_bullet.ImpulseForce = 0.6;
         d_pistol_bullet = new ProjectileData(p_pistol_bullet);
         p_shotgun_bullet.Speed = 30;
         p_shotgun_bullet.Damage = 6;
         p_shotgun_bullet.CriticalChance = 0;
         p_shotgun_bullet.CriticalDamage = 6;
         p_shotgun_bullet.PushbackPower = 33;
         p_shotgun_bullet.TotalPenetrationDepth = 12;
         p_shotgun_bullet.SinglePenetrationDepth = 5;
         p_shotgun_bullet.BulletMC = "SHOTGUN_BULLET";
         p_shotgun_bullet.BulletEffect = "BULLET_EFFECT_NORMAL";
         p_shotgun_bullet.BulletSlomoEffect = "BULLET_EFFECT_SLOMO";
         p_shotgun_bullet.Strength = 5;
         p_shotgun_bullet.ImpulseForce = 0.35;
         d_shotgun_bullet = new ProjectileData(p_shotgun_bullet);
         p_rifle_bullet.Speed = 35;
         p_rifle_bullet.Damage = 8;
         p_rifle_bullet.CriticalChance = 6;
         p_rifle_bullet.CriticalDamage = 10;
         p_rifle_bullet.PushbackPower = 20;
         p_rifle_bullet.TotalPenetrationDepth = 12;
         p_rifle_bullet.SinglePenetrationDepth = 5;
         p_rifle_bullet.BulletMC = "RIFLE_BULLET";
         p_rifle_bullet.BulletEffect = "BULLET_EFFECT_NORMAL";
         p_rifle_bullet.BulletSlomoEffect = "BULLET_EFFECT_SLOMO";
         p_rifle_bullet.Strength = 5;
         p_rifle_bullet.ImpulseForce = 0.45;
         d_rifle_bullet = new ProjectileData(p_rifle_bullet);
         p_uzi_bullet.Speed = 30;
         p_uzi_bullet.Damage = 7;
         p_uzi_bullet.CriticalChance = 4;
         p_uzi_bullet.CriticalDamage = 10;
         p_uzi_bullet.PushbackPower = 10;
         p_uzi_bullet.TotalPenetrationDepth = 12;
         p_uzi_bullet.SinglePenetrationDepth = 5;
         p_uzi_bullet.BulletMC = "UZI_BULLET";
         p_uzi_bullet.BulletEffect = "BULLET_EFFECT_NORMAL";
         p_uzi_bullet.BulletSlomoEffect = "BULLET_EFFECT_SLOMO";
         p_uzi_bullet.Strength = 5;
         p_uzi_bullet.ImpulseForce = 0.4;
         d_uzi_bullet = new ProjectileData(p_uzi_bullet);
         p_magnum_bullet.Speed = 40;
         p_magnum_bullet.Damage = 25;
         p_magnum_bullet.CriticalChance = 40;
         p_magnum_bullet.CriticalDamage = 35;
         p_magnum_bullet.PushbackPower = 50;
         p_magnum_bullet.TotalPenetrationDepth = 12;
         p_magnum_bullet.SinglePenetrationDepth = 5;
         p_magnum_bullet.BulletMC = "MAGNUM_BULLET";
         p_magnum_bullet.BulletEffect = "BULLET_EFFECT_NORMAL";
         p_magnum_bullet.BulletSlomoEffect = "BULLET_EFFECT_SLOMO";
         p_magnum_bullet.Strength = 15;
         p_magnum_bullet.ImpulseForce = 1.05;
         d_magnum_bullet = new ProjectileData(p_magnum_bullet);
         p_sniper_bullet.Speed = 40;
         p_sniper_bullet.Damage = 30;
         p_sniper_bullet.CriticalChance = 75;
         p_sniper_bullet.CriticalDamage = 60;
         p_sniper_bullet.PushbackPower = 50;
         p_sniper_bullet.TotalPenetrationDepth = 12;
         p_sniper_bullet.SinglePenetrationDepth = 5;
         p_sniper_bullet.BulletMC = "SNIPER_BULLET";
         p_sniper_bullet.BulletEffect = "BULLET_EFFECT_NORMAL";
         p_sniper_bullet.BulletSlomoEffect = "BULLET_EFFECT_SLOMO";
         p_sniper_bullet.Strength = 30;
         p_sniper_bullet.ImpulseForce = 1.25;
         d_sniper_bullet = new ProjectileData(p_sniper_bullet);
         _Handler_Output.Trace("Projectiles Created");
      }
      
      public function get Uzi_Bullet() : ProjectileData
      {
         return d_uzi_bullet.Copy();
      }
      
      public function get Bazooka_Rocket() : ProjectileData
      {
         return d_bazooka_rocket.Copy();
      }
      
      public function get Pistol_Bullet() : ProjectileData
      {
         return d_pistol_bullet.Copy();
      }
      
      public function get Sniper_Bullet() : ProjectileData
      {
         return d_sniper_bullet.Copy();
      }
      
      public function get Rifle_Bullet() : ProjectileData
      {
         return d_rifle_bullet.Copy();
      }
      
      public function get Shotgun_Bullet() : ProjectileData
      {
         return d_shotgun_bullet.Copy();
      }
      
      public function get Magnum_Bullet() : ProjectileData
      {
         return d_magnum_bullet.Copy();
      }
   }
}

