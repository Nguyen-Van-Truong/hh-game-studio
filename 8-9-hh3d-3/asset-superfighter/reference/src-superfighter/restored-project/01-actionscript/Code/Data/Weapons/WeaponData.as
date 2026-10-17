package Code.Data.Weapons
{
   public class WeaponData
   {
      private var w_infinite_ammo:Boolean;
      
      private var w_ammo:int;
      
      private var w_properties:WeaponProperties;
      
      public function WeaponData(param1:int, param2:WeaponProperties, param3:Boolean = false)
      {
         super();
         w_ammo = param1;
         w_properties = param2;
         w_infinite_ammo = param3;
      }
      
      public function set InfiniteAmmo(param1:Boolean) : void
      {
         w_infinite_ammo = param1;
      }
      
      public function get Properties() : WeaponProperties
      {
         return w_properties;
      }
      
      public function get Ammo() : int
      {
         if(w_infinite_ammo)
         {
            return 99;
         }
         return w_ammo;
      }
      
      public function get TotalKnockdown() : Number
      {
         if(Properties.WeaponType == "FLAMETHROWER")
         {
            return 0;
         }
         return Ammo * Properties.Projectile.Properties.PushbackPower + Properties.Projectile.Properties.CriticalChance;
      }
      
      public function Copy() : WeaponData
      {
         return new WeaponData(w_ammo,w_properties,w_infinite_ammo);
      }
      
      public function get CanShootDown() : Boolean
      {
         switch(Properties.WeaponType)
         {
            case "FLAMETHROWER":
               return false;
            default:
               return true;
         }
      }
      
      public function get TotalDamage() : Number
      {
         if(Properties.WeaponType == "FLAMETHROWER")
         {
            return Ammo * 1;
         }
         return Ammo * Properties.Projectile.AverageDamage;
      }
      
      public function set Ammo(param1:int) : void
      {
         if(!w_infinite_ammo)
         {
            w_ammo = param1;
         }
      }
   }
}

