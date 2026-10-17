package Code.Data.Weapons
{
   public class WeaponMeleeData
   {
      private var t_charges:int;
      
      private var t_properties:WeaponMeleeProperties;
      
      public function WeaponMeleeData(param1:int, param2:WeaponMeleeProperties)
      {
         super();
         t_charges = param1;
         t_properties = param2;
      }
      
      public function get TotalDamage() : Number
      {
         return Properties.HitPunchFrameDamage[0] + Properties.HitPunchFrameDamage[1] + Properties.HitPunchFrameDamage[2];
      }
      
      public function get Ammo() : int
      {
         return t_charges;
      }
      
      public function get Properties() : WeaponMeleeProperties
      {
         return t_properties;
      }
      
      public function Copy() : WeaponMeleeData
      {
         return new WeaponMeleeData(t_charges,t_properties);
      }
      
      public function set Ammo(param1:int) : void
      {
         t_charges = param1;
      }
   }
}

