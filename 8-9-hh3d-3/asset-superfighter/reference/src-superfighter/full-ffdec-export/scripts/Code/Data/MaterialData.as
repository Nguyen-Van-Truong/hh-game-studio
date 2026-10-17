package Code.Data
{
   public class MaterialData
   {
      private var _bullet_hit_sound:String = "";
      
      private var _material_type:String = "";
      
      private var _impact_conditions:Array;
      
      private var _bullet_hit_effect:String = "";
      
      private var _friction:Number = 0;
      
      private var _density:Number = 0;
      
      private var _impact_effect:String = "";
      
      private var _bounce_impact_sound:String = "";
      
      private var _restitution:Number = 0;
      
      public function MaterialData(param1:String, param2:Number, param3:Number, param4:Number, param5:String, param6:Array, param7:String, param8:String, param9:String)
      {
         _material_type = "";
         _density = 0;
         _friction = 0;
         _restitution = 0;
         _impact_effect = "";
         _bullet_hit_effect = "";
         _bullet_hit_sound = "";
         _bounce_impact_sound = "";
         super();
         _material_type = param1.toUpperCase();
         _density = param2;
         _friction = param3;
         _restitution = param4;
         _impact_effect = param5.toUpperCase();
         _impact_conditions = param6;
         _bullet_hit_effect = param7.toUpperCase();
         _bullet_hit_sound = param8.toUpperCase();
         _bounce_impact_sound = param9.toUpperCase();
      }
      
      public function get BulletHitEffect() : String
      {
         return _bullet_hit_effect;
      }
      
      public function set BulletHitEffect(param1:String) : void
      {
         _bullet_hit_effect = param1;
      }
      
      public function get Density() : Number
      {
         return _density;
      }
      
      public function set BounceImpactSound(param1:String) : void
      {
         _bounce_impact_sound = param1;
      }
      
      public function set Density(param1:Number) : void
      {
         _density = param1;
      }
      
      public function get Restitution() : Number
      {
         return _restitution;
      }
      
      public function set Restitution(param1:Number) : void
      {
         _restitution = param1;
      }
      
      public function ImpactEffectConditionFullfilled(param1:String) : Boolean
      {
         var _loc2_:int = 0;
         if(_impact_conditions[0] == "ANYTHING")
         {
            return true;
         }
         _loc2_ = 0;
         while(_loc2_ < _impact_conditions.length)
         {
            if(_impact_conditions[_loc2_] == param1)
            {
               return true;
            }
            _loc2_++;
         }
         return false;
      }
      
      public function get ImpactEffect() : String
      {
         return _impact_effect;
      }
      
      public function get Type() : String
      {
         return _material_type;
      }
      
      public function get Friction() : Number
      {
         return _friction;
      }
      
      public function get BounceImpactSound() : String
      {
         return _bounce_impact_sound;
      }
      
      public function Copy() : MaterialData
      {
         return new MaterialData(_material_type,_density,_friction,_restitution,_impact_effect,_impact_conditions,_bullet_hit_effect,_bullet_hit_sound,_bounce_impact_sound);
      }
      
      public function set Type(param1:String) : void
      {
         _material_type = param1;
      }
      
      public function set ImpactEffect(param1:String) : void
      {
         _impact_effect = param1;
      }
      
      public function set Friction(param1:Number) : void
      {
         _friction = param1;
      }
      
      public function set BulletHitSound(param1:String) : void
      {
         _bullet_hit_sound = param1;
      }
      
      public function get BulletHitSound() : String
      {
         return _bullet_hit_sound;
      }
   }
}

