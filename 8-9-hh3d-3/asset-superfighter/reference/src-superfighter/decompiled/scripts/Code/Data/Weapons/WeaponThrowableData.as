package Code.Data.Weapons
{
   public class WeaponThrowableData
   {
      private var t_amount:int;
      
      private var t_infinite_ammo:Boolean;
      
      private var t_properties:WeaponThrowableProperties;
      
      public function WeaponThrowableData(param1:int, param2:WeaponThrowableProperties, param3:Boolean = false)
      {
         super();
         t_amount = param1;
         t_properties = param2;
         t_infinite_ammo = param3;
      }
      
      public function get Properties() : WeaponThrowableProperties
      {
         return t_properties;
      }
      
      public function set InfiniteAmmo(param1:Boolean) : void
      {
         t_infinite_ammo = param1;
      }
      
      public function Copy() : WeaponThrowableData
      {
         return new WeaponThrowableData(t_amount,t_properties,t_infinite_ammo);
      }
      
      public function get TotalDamage() : Number
      {
         switch(Properties.WeaponType)
         {
            case "GRENADE":
               return 20;
            case "MOLOTOV":
               return 15;
            default:
               return 0;
         }
      }
      
      public function set Ammo(param1:int) : void
      {
         if(!t_infinite_ammo)
         {
            t_amount = param1;
         }
      }
      
      public function get Ammo() : int
      {
         if(t_infinite_ammo)
         {
            return 99;
         }
         return t_amount;
      }
   }
}

