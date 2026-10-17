package Code.Data
{
   import Code.Box2D.Dynamics.b2Body;
   import Code.Handler.Deconstructer;
   import flash.display.MovieClip;
   
   public class BodyData
   {
      public static var DAMAGE_IMPACT:int = 0;
      
      public static var DAMAGE_FIRE:int = 1;
      
      public static var DAMAGE_BULLET:int = 2;
      
      public static var DAMAGE_EXPLOSION:int = 3;
      
      private var _can_crush:Boolean = false;
      
      private var _isBulletHazard:Boolean = false;
      
      private var _playerCoverLevel:int = 0;
      
      protected var _Handler_Deconstructer:Deconstructer;
      
      protected var _mc:MovieClip;
      
      protected var _resistance_fire:Number;
      
      private var _canBlockFire:Boolean = false;
      
      private var _shape_mc:MovieClip;
      
      private var _isBurningHazard:Boolean = false;
      
      private var _bulletTransparent:Boolean = false;
      
      private var _isExplosionHazard:Boolean = false;
      
      private var _canBurn:Boolean = false;
      
      protected var _body:b2Body;
      
      private var _kickWeightCalculation:Boolean = false;
      
      private var _drawCloudBox:Boolean = false;
      
      private var _onlyBurnWhileWake:Boolean = false;
      
      private var _fireLifeSpan:Number = 0;
      
      protected var _indestructible:Boolean;
      
      private var _objectSmokeGrade:int = 0;
      
      private var _objectOnFire:Boolean = false;
      
      private var _canKnockDownPlayer:Boolean = true;
      
      protected var _hp_max:Number;
      
      private var _canSmoke:Boolean = false;
      
      private var _kickPower:Number = 0;
      
      private var _ignoreCoverID:int = -1;
      
      private var _aimTransparent:Boolean = false;
      
      private var _isThrowableFragile:Boolean = false;
      
      public var UserValues:Array = null;
      
      private var _can_gibb:Boolean = false;
      
      private var _isActiveHazard:Boolean = false;
      
      private var _laserVisibleOnObject:Boolean = false;
      
      public var ObjectTimer:Number = 0;
      
      private var _affectedByExplosions:Boolean = false;
      
      private var _canBlockExplosions:Boolean = false;
      
      private var _player_fragile:Boolean = false;
      
      private var _drawHitBox:Boolean = false;
      
      private var _isHazard:Boolean = false;
      
      protected var _resistance_bullet:Number;
      
      private var _lastDamage:int;
      
      private var _inPortal:Boolean = false;
      
      private var _crush_damage:Number = 0;
      
      private var _drawShapeMC:Boolean = true;
      
      private var _isImpactHazard:Boolean = false;
      
      protected var _resistance_explosion:Number;
      
      private var _is_glass:Boolean = false;
      
      protected var _resistance_impact:Number;
      
      private var _throughPortal:Boolean = false;
      
      private var _botPreferJump:Boolean = false;
      
      private var _isThrowableObject:Boolean = false;
      
      private var _strength:int = 10;
      
      private var _collision_mc:MovieClip;
      
      protected var _hp:Number;
      
      private var _player_bounce:Boolean = false;
      
      private var _partOfStaticWorld:Boolean = false;
      
      private var _isElevator:Boolean = false;
      
      private var _canCarryFire:Boolean = false;
      
      private var _laserTransparent:Boolean = false;
      
      public var UpdateFunction:Function;
      
      private var _kickable:Boolean = false;
      
      public function BodyData(param1:MovieClip, param2:Deconstructer, param3:Number = 50, param4:Number = 1, param5:Number = 1, param6:Number = 1, param7:Number = 1, param8:Boolean = false)
      {
         var mc:MovieClip = param1;
         var dec:Deconstructer = param2;
         var h:Number = param3;
         var ri:Number = param4;
         var rf:Number = param5;
         var rb:Number = param6;
         var re:Number = param7;
         var ind:Boolean = param8;
         _drawHitBox = false;
         _drawCloudBox = false;
         _drawShapeMC = true;
         _player_bounce = false;
         _player_fragile = false;
         _is_glass = false;
         _kickable = false;
         _kickPower = 0;
         _kickWeightCalculation = false;
         _can_gibb = false;
         _can_crush = false;
         _crush_damage = 0;
         _canBlockExplosions = false;
         _affectedByExplosions = false;
         _canBlockFire = false;
         _canBurn = false;
         _canCarryFire = false;
         _canSmoke = false;
         _objectOnFire = false;
         _objectSmokeGrade = 0;
         _canKnockDownPlayer = true;
         _playerCoverLevel = 0;
         _bulletTransparent = false;
         _aimTransparent = false;
         _laserTransparent = false;
         _laserVisibleOnObject = false;
         _onlyBurnWhileWake = false;
         _fireLifeSpan = 0;
         _strength = 10;
         _inPortal = false;
         _throughPortal = false;
         _isHazard = false;
         _isBurningHazard = false;
         _isBulletHazard = false;
         _isImpactHazard = false;
         _isExplosionHazard = false;
         _isActiveHazard = false;
         _isThrowableFragile = false;
         _isThrowableObject = false;
         _botPreferJump = false;
         _partOfStaticWorld = false;
         _ignoreCoverID = -1;
         UserValues = null;
         ObjectTimer = 0;
         _isElevator = false;
         super();
         _mc = mc;
         _mc.stop();
         _Handler_Deconstructer = dec;
         _hp = h;
         _hp_max = hp;
         _resistance_impact = ri;
         _resistance_fire = rf;
         _resistance_bullet = rb;
         _resistance_explosion = re;
         _indestructible = ind;
         _drawHitBox = false;
         _lastDamage = 0;
         UserValues = new Array();
         UpdateFunction = function(param1:b2Body, param2:Number):void
         {
         };
      }
      
      public function get CanBeHazard() : Boolean
      {
         return _isActiveHazard || _isBurningHazard || _isBulletHazard || _isImpactHazard || _isExplosionHazard;
      }
      
      public function set HP(param1:Number) : void
      {
         _hp = param1;
      }
      
      public function get InPortal() : Boolean
      {
         return _inPortal;
      }
      
      public function Damage_Impact(param1:Number) : void
      {
         _lastDamage = DAMAGE_IMPACT;
         Damage(param1 * _resistance_impact);
      }
      
      public function SetResistance(param1:Number = 1, param2:Number = 1, param3:Number = 1, param4:Number = 1) : void
      {
         _resistance_impact = param1;
         _resistance_fire = param2;
         _resistance_bullet = param3;
         _resistance_explosion = param4;
      }
      
      public function get IsBulletHazard() : Boolean
      {
         return _isBulletHazard;
      }
      
      public function get CanCarryFire() : Boolean
      {
         return _canCarryFire;
      }
      
      public function set InPortal(param1:Boolean) : void
      {
         _inPortal = param1;
      }
      
      public function get CollisionMC() : MovieClip
      {
         return _collision_mc;
      }
      
      public function get PartOfStaticWorld() : Boolean
      {
         return _partOfStaticWorld;
      }
      
      public function get ResistanceFire() : Number
      {
         return _resistance_fire;
      }
      
      public function set PartOfStaticWorld(param1:Boolean) : void
      {
         _partOfStaticWorld = param1;
      }
      
      public function set IsBulletHazard(param1:Boolean) : void
      {
         _isBulletHazard = param1;
      }
      
      public function get PlayerFragile() : Boolean
      {
         return _player_fragile;
      }
      
      public function get KickPower() : Number
      {
         return _kickPower;
      }
      
      public function set IsActiveHazard(param1:Boolean) : void
      {
         _isActiveHazard = param1;
      }
      
      public function Damage_Explosion(param1:Number) : void
      {
         _lastDamage = DAMAGE_EXPLOSION;
         Damage(param1 * _resistance_explosion);
      }
      
      public function get CanKnockDownPlayer() : Boolean
      {
         return _canKnockDownPlayer;
      }
      
      public function set CanCarryFire(param1:Boolean) : void
      {
         _canCarryFire = param1;
      }
      
      public function set CollisionMC(param1:MovieClip) : void
      {
         _collision_mc = param1;
      }
      
      public function get IsElevator() : Boolean
      {
         return _isElevator;
      }
      
      public function get IsGlass() : Boolean
      {
         return _is_glass;
      }
      
      public function get Strength() : int
      {
         return _strength;
      }
      
      public function get LaserVisibleOnObject() : Boolean
      {
         return _laserVisibleOnObject;
      }
      
      public function get ObjectSmokeGrade() : int
      {
         return _objectSmokeGrade;
      }
      
      public function get AffectedByExplosions() : Boolean
      {
         return _affectedByExplosions;
      }
      
      public function set PlayerFragile(param1:Boolean) : void
      {
         _player_fragile = param1;
      }
      
      public function get CanGibb() : Boolean
      {
         return _can_gibb;
      }
      
      public function get IsBurningHazard() : Boolean
      {
         return _isBurningHazard;
      }
      
      public function set KickPower(param1:Number) : void
      {
         _kickPower = param1;
      }
      
      public function get IsThrowableFragile() : Boolean
      {
         return _isThrowableFragile;
      }
      
      public function set CanKnockDownPlayer(param1:Boolean) : void
      {
         _canKnockDownPlayer = param1;
      }
      
      public function get CanBlockFire() : Boolean
      {
         return _canBlockFire;
      }
      
      public function get CanBlockExplosions() : Boolean
      {
         return _canBlockExplosions;
      }
      
      public function set IsElevator(param1:Boolean) : void
      {
         _isElevator = param1;
      }
      
      public function get Indestructible() : Boolean
      {
         return _indestructible;
      }
      
      public function set IsGlass(param1:Boolean) : void
      {
         _is_glass = param1;
      }
      
      public function get Kickable() : Boolean
      {
         return _kickable;
      }
      
      public function set IsImpactHazard(param1:Boolean) : void
      {
         _isImpactHazard = param1;
      }
      
      public function get IgnoreCoverID() : Number
      {
         return _ignoreCoverID;
      }
      
      public function set Strength(param1:int) : void
      {
         _strength = param1;
      }
      
      public function set BotPreferJump(param1:Boolean) : void
      {
         _botPreferJump = param1;
      }
      
      public function set ObjectSmokeGrade(param1:int) : void
      {
         _objectSmokeGrade = param1;
      }
      
      public function get BulletTransparent() : Boolean
      {
         return _bulletTransparent;
      }
      
      public function set LaserVisibleOnObject(param1:Boolean) : void
      {
         _laserVisibleOnObject = param1;
      }
      
      public function set AffectedByExplosions(param1:Boolean) : void
      {
         _affectedByExplosions = param1;
      }
      
      public function set KickWeightCalculation(param1:Boolean) : void
      {
         _kickWeightCalculation = param1;
      }
      
      public function get ShapeMC() : MovieClip
      {
         return _shape_mc;
      }
      
      public function get DrawCloudBox() : Boolean
      {
         return _drawCloudBox;
      }
      
      public function get IsExplosionHazard() : Boolean
      {
         return _isExplosionHazard;
      }
      
      public function get FireLifeSpan() : Number
      {
         return _fireLifeSpan;
      }
      
      public function set CanGibb(param1:Boolean) : void
      {
         _can_gibb = param1;
      }
      
      public function ForceDestruction() : void
      {
         _Handler_Deconstructer.AddBody(_body);
         _hp = 0;
      }
      
      public function set ThroughPortal(param1:Boolean) : void
      {
         _throughPortal = param1;
      }
      
      public function get AimTransparent() : Boolean
      {
         return _aimTransparent;
      }
      
      public function get PlayerBounce() : Boolean
      {
         return _player_bounce;
      }
      
      public function get DrawShapeMC() : Boolean
      {
         return _drawShapeMC;
      }
      
      public function get ObjectOnFire() : Boolean
      {
         return _objectOnFire;
      }
      
      public function set IsBurningHazard(param1:Boolean) : void
      {
         _isBurningHazard = param1;
      }
      
      public function get OnlyBurnWhileWake() : Boolean
      {
         return _onlyBurnWhileWake;
      }
      
      public function set IsThrowableFragile(param1:Boolean) : void
      {
         _isThrowableFragile = param1;
      }
      
      public function Damage_Fire(param1:Number) : void
      {
         _lastDamage = DAMAGE_FIRE;
         Damage(param1 * _resistance_fire);
      }
      
      public function get hp() : Number
      {
         return _hp;
      }
      
      public function get HP() : Number
      {
         return _hp;
      }
      
      public function get IsActiveHazard() : Boolean
      {
         return _isActiveHazard;
      }
      
      public function set CanBlockFire(param1:Boolean) : void
      {
         _canBlockFire = param1;
      }
      
      public function set MC(param1:MovieClip) : void
      {
         _mc = param1;
      }
      
      public function set CanBurn(param1:Boolean) : void
      {
         _canBurn = param1;
      }
      
      public function set CanSmoke(param1:Boolean) : void
      {
         _canSmoke = param1;
      }
      
      public function set Indestructible(param1:Boolean) : void
      {
         _indestructible = param1;
      }
      
      public function set LaserTransparent(param1:Boolean) : void
      {
         _laserTransparent = param1;
      }
      
      public function get IsImpactHazard() : Boolean
      {
         return _isImpactHazard;
      }
      
      public function set CanBlockExplosions(param1:Boolean) : void
      {
         _canBlockExplosions = param1;
      }
      
      public function get BotPreferJump() : Boolean
      {
         return _botPreferJump;
      }
      
      public function get KickWeightCalculation() : Boolean
      {
         return _kickWeightCalculation;
      }
      
      public function get ThroughPortal() : Boolean
      {
         return _throughPortal;
      }
      
      public function set DrawHitBox(param1:Boolean) : void
      {
         _drawHitBox = param1;
      }
      
      public function set IgnoreCoverID(param1:Number) : void
      {
         _ignoreCoverID = param1;
      }
      
      public function set Body(param1:b2Body) : void
      {
         _body = param1;
      }
      
      public function set Kickable(param1:Boolean) : void
      {
         _kickable = param1;
      }
      
      protected function Damage(param1:Number) : void
      {
         if(!_indestructible)
         {
            _hp -= param1;
            if(_hp <= 0)
            {
               _Handler_Deconstructer.AddBody(_body);
            }
         }
      }
      
      public function get MC() : MovieClip
      {
         return _mc;
      }
      
      public function get CanBurn() : Boolean
      {
         return _canBurn;
      }
      
      public function get CanSmoke() : Boolean
      {
         return _canSmoke;
      }
      
      public function set BulletTransparent(param1:Boolean) : void
      {
         _bulletTransparent = param1;
      }
      
      public function set DrawCloudBox(param1:Boolean) : void
      {
         _drawCloudBox = param1;
      }
      
      public function get LaserTransparent() : Boolean
      {
         return _laserTransparent;
      }
      
      public function set FireLifeSpan(param1:Number) : void
      {
         _fireLifeSpan = param1;
      }
      
      public function set IsExplosionHazard(param1:Boolean) : void
      {
         _isExplosionHazard = param1;
      }
      
      public function set ShapeMC(param1:MovieClip) : void
      {
         _shape_mc = param1;
      }
      
      public function get DrawHitBox() : Boolean
      {
         return _drawHitBox;
      }
      
      public function get LastDamage() : int
      {
         return _lastDamage;
      }
      
      public function get Body() : b2Body
      {
         return _body;
      }
      
      public function set PlayerBounce(param1:Boolean) : void
      {
         _player_bounce = param1;
      }
      
      public function set CrushDamage(param1:Number) : void
      {
         _crush_damage = param1;
      }
      
      public function Damage_Bullet(param1:Number) : void
      {
         _lastDamage = DAMAGE_BULLET;
         Damage(param1 * _resistance_bullet);
      }
      
      public function set AimTransparent(param1:Boolean) : void
      {
         _aimTransparent = param1;
      }
      
      public function set PlayerCoverLevel(param1:int) : void
      {
         _playerCoverLevel = param1;
      }
      
      public function set IsThrowableObject(param1:Boolean) : void
      {
         _isThrowableObject = param1;
      }
      
      public function set DrawShapeMC(param1:Boolean) : void
      {
         _drawShapeMC = param1;
      }
      
      public function get PlayerCoverLevel() : int
      {
         return _playerCoverLevel;
      }
      
      public function set ObjectOnFire(param1:Boolean) : void
      {
         _objectOnFire = param1;
         if(_objectOnFire)
         {
            _objectSmokeGrade = 0;
         }
      }
      
      public function get CrushDamage() : Number
      {
         return _crush_damage;
      }
      
      public function set OnlyBurnWhileWake(param1:Boolean) : void
      {
         _onlyBurnWhileWake = param1;
      }
      
      public function get IsThrowableObject() : Boolean
      {
         return _isThrowableObject;
      }
      
      public function get IsHazard() : Boolean
      {
         if(_isActiveHazard)
         {
            return true;
         }
         if(_isBurningHazard && _objectOnFire)
         {
            return true;
         }
         if(_isImpactHazard && !_body.IsSleeping())
         {
            return true;
         }
         return false;
      }
   }
}

