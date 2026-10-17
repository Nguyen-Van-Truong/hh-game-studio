package Code.Data.Weapons
{
   import Code.Data.ProjectileData;
   
   public class WeaponProperties
   {
      public var BulletType:String;
      
      public var Projectile:ProjectileData;
      
      public var AnimType:String;
      
      public var ShellEffect:String;
      
      public var PickupSound:String;
      
      public var PickupRadius:Number;
      
      public var WeaponType:String;
      
      public var WeaponCooldown:int;
      
      public var MuzzleFlashEffect:String;
      
      public var EmptySound:String;
      
      public var AimSound:String;
      
      public var LaserDeflection:Number;
      
      public var AccuracyDeflection:Number;
      
      public var FireSequence:Array;
      
      public var LaserSight:Boolean;
      
      public var ShootRange:Number;
      
      public function WeaponProperties()
      {
         FireSequence = new Array();
         super();
      }
   }
}

