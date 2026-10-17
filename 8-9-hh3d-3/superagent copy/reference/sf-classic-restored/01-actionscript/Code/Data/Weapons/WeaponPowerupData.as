package Code.Data.Weapons
{
   public class WeaponPowerupData
   {
      private var t_time:int;
      
      private var t_properties:WeaponPowerupProperties;
      
      public function WeaponPowerupData(param1:int, param2:WeaponPowerupProperties)
      {
         super();
         t_time = param1;
         t_properties = param2;
      }
      
      public function get TotalDamage() : Number
      {
         return 10;
      }
      
      public function get Ammo() : int
      {
         return t_time;
      }
      
      public function get Properties() : WeaponPowerupProperties
      {
         return t_properties;
      }
      
      public function Copy() : WeaponPowerupData
      {
         return new WeaponPowerupData(t_time,t_properties);
      }
      
      public function set Ammo(param1:int) : void
      {
         t_time = param1;
      }
   }
}

