package Code.Data
{
   import Code.Data.Players.Player;
   import flash.display.*;
   
   public class ProjectileData
   {
      private var _bullet_slomo_trace:Number = 5;
      
      private var penetratingCloud:Boolean = false;
      
      private var mc:MovieClip;
      
      private var p_angle_rad:Number;
      
      private var isRocket:Boolean = false;
      
      private var p_owner:Player;
      
      private var penetrating:Boolean = false;
      
      private var p_strength:int;
      
      private var normal_effect_mc:MovieClip;
      
      private var p_current_penetration:Number;
      
      private var playerStuck:Player = null;
      
      private var p_total_penetration:Number;
      
      private var players_avoided:Array;
      
      private var p_angle:Number;
      
      private var effect_length:Number = 0;
      
      private var explode:Boolean = false;
      
      private var p_properties:ProjectileProperties;
      
      private var p_directionY:Number;
      
      private var p_directionX:Number;
      
      private var p_posX:Number;
      
      private var p_posY:Number;
      
      private var bullet_mc:MovieClip;
      
      public function ProjectileData(param1:ProjectileProperties)
      {
         effect_length = 0;
         isRocket = false;
         playerStuck = null;
         explode = false;
         penetrating = false;
         penetratingCloud = false;
         _bullet_slomo_trace = 5;
         super();
         p_posX = 0;
         p_posY = 0;
         p_angle = 0;
         p_angle_rad = 0;
         p_directionX = 1;
         p_directionY = 0;
         p_owner = null;
         p_properties = param1;
         p_strength = p_properties.Strength;
         p_total_penetration = p_properties.TotalPenetrationDepth;
         p_current_penetration = p_properties.SinglePenetrationDepth;
         switch(p_properties.BulletMC.toUpperCase())
         {
            case "PISTOL_BULLET":
               bullet_mc = new bullet_pistol();
               break;
            case "RIFLE_BULLET":
               bullet_mc = new bullet_rifle();
               break;
            case "UZI_BULLET":
               bullet_mc = new bullet_uzi();
               break;
            case "SHOTGUN_BULLET":
               bullet_mc = new bullet_shotgun();
               break;
            case "SNIPER_BULLET":
               bullet_mc = new bullet_sniper();
               break;
            case "MAGNUM_BULLET":
               bullet_mc = new bullet_magnum();
               break;
            case "BAZOOKA_ROCKET":
               isRocket = true;
               bullet_mc = new bazooka_rocket();
               break;
            default:
               bullet_mc = new bullet();
         }
         mc = new MovieClip();
         mc.addChild(bullet_mc);
         players_avoided = new Array();
         if(p_properties.BulletEffect == "BULLET_EFFECT_NORMAL")
         {
            normal_effect_mc = new bullet_effect_normal();
         }
         else
         {
            normal_effect_mc = new MovieClip();
         }
         normal_effect_mc.scaleX = effect_length;
         mc.addChild(normal_effect_mc);
      }
      
      public function ClearPenetrationCurrentLeft() : void
      {
         p_current_penetration = p_properties.SinglePenetrationDepth;
         if(p_current_penetration > p_total_penetration)
         {
            p_current_penetration = p_total_penetration;
         }
      }
      
      public function get Penetrating() : Boolean
      {
         return penetrating;
      }
      
      public function UpdateVisuals(param1:Number) : void
      {
         if(BulletGameSpeed >= 0.8)
         {
            bullet_mc.visible = false;
            normal_effect_mc.visible = true;
         }
         else
         {
            bullet_mc.visible = true;
            normal_effect_mc.visible = false;
         }
         if(effect_length < 30)
         {
            effect_length += param1;
            if(effect_length > 30)
            {
               effect_length = 30;
            }
            normal_effect_mc.alpha = 0.9 - effect_length / 100;
            normal_effect_mc.scaleX = effect_length / 10;
         }
      }
      
      public function get BulletGameSpeed() : Number
      {
         return p_owner.BulletGameSpeed;
      }
      
      public function set Penetrating(param1:Boolean) : void
      {
         penetrating = param1;
      }
      
      public function PlayerAvoided(param1:int) : Boolean
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < players_avoided.length)
         {
            if(players_avoided[_loc2_] == param1)
            {
               return true;
            }
            _loc2_++;
         }
         return false;
      }
      
      public function get StrengthLeft() : int
      {
         return p_strength;
      }
      
      public function get PenetrationTotalLeft() : Number
      {
         return p_total_penetration;
      }
      
      public function get PlayerStuck() : Player
      {
         return playerStuck;
      }
      
      public function Copy() : ProjectileData
      {
         return new ProjectileData(p_properties);
      }
      
      public function Show() : void
      {
         mc.visible = true;
      }
      
      public function set StrengthLeft(param1:int) : void
      {
         p_strength = param1;
      }
      
      public function AddBulletTrace(param1:Number) : Boolean
      {
         if(isRocket)
         {
            if(_bullet_slomo_trace <= 0)
            {
               _bullet_slomo_trace = 2;
               return true;
            }
            _bullet_slomo_trace -= param1;
         }
         else if(BulletGameSpeed < 0.8)
         {
            if(_bullet_slomo_trace <= 0)
            {
               _bullet_slomo_trace = 12;
               return true;
            }
            _bullet_slomo_trace -= param1;
         }
         return false;
      }
      
      public function set Owner(param1:Player) : void
      {
         p_owner = param1;
      }
      
      public function get Owner() : Player
      {
         return p_owner;
      }
      
      public function set PenetrationTotalLeft(param1:Number) : void
      {
         p_total_penetration = param1;
      }
      
      public function get MC() : MovieClip
      {
         return mc;
      }
      
      public function AddPlayerAvoided(param1:int) : void
      {
         players_avoided.push(param1);
      }
      
      public function get PenetratingCloud() : Boolean
      {
         return penetratingCloud;
      }
      
      public function set DirectionX(param1:Number) : void
      {
         p_directionX = param1;
         p_angle_rad = Math.atan2(DirectionY,DirectionX);
         Angle = p_angle_rad * (180 / Math.PI);
      }
      
      public function get DoExplode() : Boolean
      {
         return explode;
      }
      
      public function set DirectionY(param1:Number) : void
      {
         p_directionY = param1;
         p_angle_rad = Math.atan2(DirectionY,DirectionX);
         Angle = p_angle_rad * (180 / Math.PI);
      }
      
      public function set PlayerStuck(param1:Player) : void
      {
         playerStuck = param1;
      }
      
      public function get PosX() : Number
      {
         return p_posX;
      }
      
      public function get AverageDamage() : Number
      {
         return Properties.Damage + Properties.CriticalChance / 100 * Properties.CriticalDamage;
      }
      
      public function set MC(param1:MovieClip) : void
      {
         mc = param1;
      }
      
      public function set PosX(param1:Number) : void
      {
         p_posX = param1;
         mc.x = p_posX;
      }
      
      public function ResetPlayersAvoided() : void
      {
         players_avoided = new Array();
      }
      
      public function get Properties() : ProjectileProperties
      {
         return p_properties;
      }
      
      public function get AngleRad() : Number
      {
         return p_angle_rad;
      }
      
      public function Explode() : void
      {
         explode = true;
      }
      
      public function get DirectionY() : Number
      {
         return p_directionY;
      }
      
      public function get PosY() : Number
      {
         return p_posY;
      }
      
      public function set PenetratingCloud(param1:Boolean) : void
      {
         penetratingCloud = param1;
      }
      
      public function set PenetrationCurrentLeft(param1:Number) : void
      {
         p_current_penetration = param1;
      }
      
      public function get VelocityX() : Number
      {
         return p_directionX * p_properties.Speed;
      }
      
      public function Hide() : void
      {
         mc.visible = false;
      }
      
      public function get PenetrationCurrentLeft() : Number
      {
         return p_current_penetration;
      }
      
      public function set PosY(param1:Number) : void
      {
         p_posY = param1;
         mc.y = p_posY;
      }
      
      public function get Angle() : Number
      {
         return p_angle;
      }
      
      public function get DirectionX() : Number
      {
         return p_directionX;
      }
      
      public function get VelocityY() : Number
      {
         return p_directionY * p_properties.Speed;
      }
      
      public function set Angle(param1:Number) : void
      {
         p_angle = param1;
         p_angle_rad = p_angle * (Math.PI / 180);
         p_directionX = Math.cos(p_angle_rad);
         p_directionY = Math.sin(p_angle_rad);
         mc.rotation = p_angle;
      }
   }
}

