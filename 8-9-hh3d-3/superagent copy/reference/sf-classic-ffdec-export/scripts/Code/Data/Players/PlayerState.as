package Code.Data.Players
{
   import Code.Box2D.Dynamics.b2Body;
   import Code.Data.ProjectileData;
   import Code.Data.Weapons.*;
   
   public class PlayerState
   {
      public static var KNOCKDOWN_IMMUNITY_TIME:Number = 10;
      
      public var PlayerJumpPushPower:Number = -0.7;
      
      public var ImmunityDisabled:Boolean = false;
      
      public var PlayerGravity:Number = 0.6;
      
      private var _jumpKickPerformed:Boolean = false;
      
      public var ThrowTimer:Number = 0;
      
      private var _knockdownGrade:int = 0;
      
      private var _showFlashEffect:Boolean = false;
      
      public var CurrentChangePitchSpeed:Number = 0;
      
      public var FireRank1Minimum:Number = 15;
      
      public var JumpKickDamage:Number = 4;
      
      private var _grabbed_by_player:Boolean = false;
      
      private var _grabbed_player_nr:int = 0;
      
      public var FireRank2Damage:Number = 0.4;
      
      public var AimMode:int = 0;
      
      private var _currentPushbackPower:Number = 0;
      
      public var FireRankWorldExtraDamage:Number = 0.2;
      
      public var PlayerJumpPushEnabled:Boolean = false;
      
      private var _running:Boolean = false;
      
      private var _flashEffectTimer:int = 0;
      
      private var _decreaseKnockdownGradeTimer:Number = 0;
      
      private var _healthBarSpeed:Number = 4;
      
      private var _box2D_cover:b2Body;
      
      public var RocketRideTimer:Number = 0;
      
      private var _canDive:Boolean = true;
      
      public var FallTriggerSpeed:Number = 8.5;
      
      private var _portalDirectionX:int = 1;
      
      public var CritSmokeTimer:Number = 0;
      
      public var StaggerSpeed:Number = 1;
      
      public var Gone:Boolean = false;
      
      private var _punchComboNr:int = 1;
      
      private var _showHealthTimer:Number = -24;
      
      private var _knockdowned:Boolean = false;
      
      public var CurrentThrowableWeapon:WeaponThrowableData;
      
      public var PlayerJumpPushTime:Number = 4;
      
      public var PlayerFeetSize:Number = 4;
      
      private var _rolling:Boolean = false;
      
      public var RocketRideProjectile:ProjectileData = null;
      
      private var _kneeling:Boolean = false;
      
      private var _aimTurningAroundTimer:int = 0;
      
      private var _taking_cover:Boolean = false;
      
      public var JumpPushTimeLeft:Number = 0;
      
      public var FireRank1Damage:Number = 0.2;
      
      private var _drawDelay:int = 0;
      
      public var FireRank2Minimum:Number = 100;
      
      private var _stunTimer:Number = 0;
      
      private var _kickingCooldown:Number = 0;
      
      public var SlideSpeed:Number = 3;
      
      public var ImmunityTimer:Number = 0;
      
      public var PlayerJumpPushActivated:Boolean = false;
      
      public var PlayerWallJumpPower:Number = -5;
      
      private var _falling:Boolean = false;
      
      private var _punching:Boolean = false;
      
      private var _cover_object_id:int;
      
      public var CurrentAimPitch:Number = 0;
      
      public var KickDamage:Number = 4;
      
      public var CheckForCover:Boolean = false;
      
      private var _staggerTimer:Number = 0;
      
      private var _reSprintActivationDuration:int = 0;
      
      public var CharAnimWpnX:Number;
      
      public var CharAnimWpnY:Number;
      
      private var _aimTurningAround:Boolean = false;
      
      public var LockRocketSteering:Boolean = false;
      
      public var CurrentMeleeWeapon:WeaponMeleeData;
      
      public var FastTrigger:Boolean = false;
      
      public var DisableKneel:Boolean = false;
      
      public var RollSpeed:Number = 2;
      
      private var _aiming:Boolean = false;
      
      public var UsingMeleeWeapon:Boolean = false;
      
      private var _hp:Number = 100;
      
      private var game_speed:Number = 1;
      
      private var _doPunchCombo:Boolean = false;
      
      public var EmptyWeaponRecoilBack:int = 0;
      
      private var _grabbed_player_char_nr:int = 0;
      
      private var _runSpeed:Number = 1.7;
      
      private var _actionCooldown:Number = 0;
      
      private var _grabbed_player:Boolean = false;
      
      private var _movingDirectionInversed:int = 0;
      
      private var _stunAnimation:int = 1;
      
      public var StairBounceDamage:Number = 4;
      
      private var _backToIdleTimer:int = 0;
      
      private var _movingDirectionX:int = 1;
      
      private var _sprinting:Boolean = false;
      
      private var _wallJumping:Boolean = false;
      
      private var _hp_damage_timer:Number = 0;
      
      private var _char_nr:int = 0;
      
      private var kickHitMaterialSounds:Array;
      
      public var KickPower:Number = 1.6;
      
      public var LadderEffectRightSide:Boolean = false;
      
      private var _portalSpeedX:Number = 0;
      
      public var PlayerEdgeDistance:Number = 4;
      
      public var FireDelayTimer:Number;
      
      private var _climbing:Boolean = false;
      
      public var Team:int;
      
      private var _burnState:Number = 0;
      
      public var StopStaggerFunc:Function;
      
      public var DiveSpeed:Number = 3.5;
      
      public var FireRank2Attached:Boolean = false;
      
      private var _kicking:Boolean = false;
      
      public var CurrentRangeWeapon:WeaponData;
      
      public var SlowmotionDelay:Number = 0;
      
      private var kickHitMaterialEffects:Array;
      
      private var _kickingTimer:Number = 0;
      
      public var ClimbSpeed:Number = 1.5;
      
      private var _staggering:Boolean = false;
      
      private var _shortDiveTimer:Number = 0;
      
      private var _shortDiveAvailable:Boolean = false;
      
      public var LastFireFrame:int = 0;
      
      public var StuckToRocket:Boolean = false;
      
      public var Burned:Boolean = false;
      
      private var _diving:Boolean = false;
      
      private var _airVelocityY:Number = 0;
      
      public var PlayerJumpPushLevelOut:Boolean = false;
      
      public var CurrentLadder:b2Body = null;
      
      private var _airVelocityX:Number = 0;
      
      private var _actionAvailable:Boolean = true;
      
      private var _puchbackDecreaseDelay:Number = 0;
      
      public var NextLadderEffect:Number = 4;
      
      public var StairBounce:Boolean = false;
      
      public var Mass:Number = 0.7;
      
      private var _sprintEnergy:Number = 100;
      
      private var _deathKneel:Boolean = false;
      
      public var IgnoreMe:Boolean = false;
      
      public var FireDelayUpdated:Boolean = false;
      
      private var _punchHitPerformed:Boolean = false;
      
      private var _canRoll:Boolean = true;
      
      public var PunchGlideSpeed:Number = 2;
      
      public var Throwing:Boolean = false;
      
      private var _barHP:Number = 100;
      
      public var UpdateYAxisDistance:Number = 3;
      
      public var CurrentWeaponCooldown:Number = 0;
      
      public var PlayerJumpPower:Number = -5;
      
      public var CurrentFireFrame:Number = 0;
      
      public var FireDelayActivated:Boolean = false;
      
      private var _inFireDelay:Number = 0;
      
      private var _inWorldFire:Number = 0;
      
      public var AirbornTimer:Number = 0;
      
      public var FireRank1Attached:Boolean = false;
      
      public var QueueJumpKick:Boolean = false;
      
      public var CantRise:Boolean = false;
      
      private var _camera_ignore_me_timer:Number = 0;
      
      private var _jumping:Boolean = false;
      
      public var CurrentPowerupWeapon:WeaponPowerupData;
      
      public var DefaultMeleeWeapon:WeaponMeleeData;
      
      private var _sprintActivationDuration:int = 0;
      
      private var _stairVelocityX:Number = 0;
      
      private var _stairVelocityY:Number = 0;
      
      private var _last_dir_x:int = 1;
      
      public function PlayerState()
      {
         PlayerGravity = 0.6;
         UpdateYAxisDistance = 3;
         PlayerEdgeDistance = 4;
         PlayerFeetSize = 4;
         PlayerJumpPower = -5;
         PlayerJumpPushActivated = false;
         PlayerJumpPushPower = -0.7;
         PlayerJumpPushLevelOut = false;
         PlayerJumpPushEnabled = false;
         PlayerJumpPushTime = 4;
         JumpPushTimeLeft = 0;
         PlayerWallJumpPower = -5;
         FallTriggerSpeed = 8.5;
         StaggerSpeed = 1;
         RollSpeed = 2;
         DiveSpeed = 3.5;
         StuckToRocket = false;
         RocketRideProjectile = null;
         Mass = 0.7;
         KickPower = 1.6;
         CantRise = false;
         CheckForCover = false;
         FireRank1Attached = false;
         FireRank2Attached = false;
         StairBounce = false;
         UsingMeleeWeapon = false;
         CurrentAimPitch = 0;
         CurrentChangePitchSpeed = 0;
         ClimbSpeed = 1.5;
         SlideSpeed = 3;
         CurrentLadder = null;
         DisableKneel = false;
         CurrentWeaponCooldown = 0;
         NextLadderEffect = 4;
         LadderEffectRightSide = false;
         FireDelayActivated = false;
         FireDelayUpdated = false;
         SlowmotionDelay = 0;
         CurrentFireFrame = 0;
         LastFireFrame = 0;
         AimMode = 0;
         FastTrigger = false;
         Throwing = false;
         ThrowTimer = 0;
         Burned = false;
         CritSmokeTimer = 0;
         Gone = false;
         FireRankWorldExtraDamage = 0.2;
         FireRank1Damage = 0.2;
         FireRank2Damage = 0.4;
         FireRank1Minimum = 15;
         FireRank2Minimum = 100;
         StairBounceDamage = 4;
         KickDamage = 4;
         JumpKickDamage = 4;
         AirbornTimer = 0;
         QueueJumpKick = false;
         LockRocketSteering = false;
         RocketRideTimer = 0;
         EmptyWeaponRecoilBack = 0;
         IgnoreMe = false;
         ImmunityTimer = 0;
         ImmunityDisabled = false;
         game_speed = 1;
         kickHitMaterialSounds = new Array(["WOOD","BULLET_HITDEFAULT"]);
         kickHitMaterialEffects = new Array(["WOOD","HITDEFAULT_01"]);
         _hp_damage_timer = 0;
         _showFlashEffect = false;
         _flashEffectTimer = 0;
         _aimTurningAroundTimer = 0;
         _aimTurningAround = false;
         PunchGlideSpeed = 2;
         _runSpeed = 1.7;
         _aiming = false;
         _climbing = false;
         _camera_ignore_me_timer = 0;
         _diving = false;
         _jumpKickPerformed = false;
         _jumping = false;
         _wallJumping = false;
         _canRoll = true;
         _canDive = true;
         _inWorldFire = 0;
         _stunAnimation = 1;
         _stunTimer = 0;
         _puchbackDecreaseDelay = 0;
         _currentPushbackPower = 0;
         _drawDelay = 0;
         _backToIdleTimer = 0;
         _falling = false;
         _kneeling = false;
         _actionCooldown = 0;
         _actionAvailable = true;
         _rolling = false;
         _sprintEnergy = 100;
         _taking_cover = false;
         _staggerTimer = 0;
         _staggering = false;
         _deathKneel = false;
         _knockdowned = false;
         _knockdownGrade = 0;
         _decreaseKnockdownGradeTimer = 0;
         _kickingCooldown = 0;
         _kickingTimer = 0;
         _kicking = false;
         _doPunchCombo = false;
         _punchComboNr = 1;
         _punching = false;
         _punchHitPerformed = false;
         _sprinting = false;
         _running = false;
         _shortDiveTimer = 0;
         _shortDiveAvailable = false;
         _sprintActivationDuration = 0;
         _reSprintActivationDuration = 0;
         _airVelocityY = 0;
         _airVelocityX = 0;
         _stairVelocityY = 0;
         _stairVelocityX = 0;
         _movingDirectionInversed = 0;
         _last_dir_x = 1;
         _inFireDelay = 0;
         _burnState = 0;
         _hp = 100;
         _showHealthTimer = -24;
         _healthBarSpeed = 4;
         _barHP = 100;
         _movingDirectionX = 1;
         _portalSpeedX = 0;
         _portalDirectionX = 1;
         _grabbed_by_player = false;
         _grabbed_player = false;
         _grabbed_player_nr = 0;
         _grabbed_player_char_nr = 0;
         _char_nr = 0;
         super();
      }
      
      public function ResetChangePitchSpeed() : void
      {
         CurrentChangePitchSpeed = 0;
      }
      
      public function get DoPunchCombo() : Boolean
      {
         return _doPunchCombo;
      }
      
      public function get BackToIdleTimer() : int
      {
         return _backToIdleTimer;
      }
      
      public function get Punching() : Boolean
      {
         return _punching;
      }
      
      public function set DoPunchCombo(param1:Boolean) : void
      {
         _doPunchCombo = param1;
      }
      
      public function set BackToIdleTimer(param1:int) : void
      {
         _backToIdleTimer = param1;
      }
      
      public function set CameraIgnoreTimer(param1:Number) : void
      {
         _camera_ignore_me_timer = param1;
      }
      
      public function set Punching(param1:Boolean) : void
      {
         if(!param1)
         {
            PunchComboNr = 1;
         }
         _punching = param1;
      }
      
      public function get ShortDiveAvailable() : Boolean
      {
         return false;
      }
      
      public function get MeleeSwingEffect() : String
      {
         return GetMeleeWeapon().Properties.SwingComboEffects[_punchComboNr - 1];
      }
      
      public function get BarHP() : Number
      {
         return _barHP;
      }
      
      public function get KnockdownRiseSpeed() : Number
      {
         return 1;
      }
      
      public function get CanRoll() : Boolean
      {
         if(!_actionAvailable)
         {
            return false;
         }
         return _canRoll;
      }
      
      public function set Rolling(param1:Boolean) : void
      {
         _rolling = param1;
         if(_rolling)
         {
            _diving = false;
            _sprinting = false;
         }
         else
         {
            _kneeling = false;
            _actionCooldown = 12;
            _actionAvailable = false;
         }
      }
      
      public function get HitPunchComboFrame() : int
      {
         switch(_punchComboNr)
         {
            case 1:
               return 4;
            case 2:
               return 5;
            case 3:
               return 6;
            default:
               return 0;
         }
      }
      
      public function get OnGround() : Boolean
      {
         if(Boolean(_falling) || Boolean(_jumping) || Boolean(_climbing))
         {
            return false;
         }
         return true;
      }
      
      public function set ShortDiveAvailable(param1:Boolean) : void
      {
         _shortDiveAvailable = param1;
      }
      
      public function set GrabbedPlayerNr(param1:int) : void
      {
         _grabbed_player = true;
         _grabbed_player_nr = param1;
      }
      
      public function get Box2DCover() : b2Body
      {
         return _box2D_cover;
      }
      
      public function get BotInterrupt() : Boolean
      {
         if(Boolean(_falling) || Boolean(_knockdowned) || Boolean(_grabbed_by_player))
         {
            return true;
         }
         if(IsStunned || Boolean(_staggering))
         {
            return true;
         }
         return false;
      }
      
      public function set ShowFlashEffect(param1:Boolean) : void
      {
         _showFlashEffect = param1;
         if(param1)
         {
            _flashEffectTimer = 8;
         }
         else
         {
            _flashEffectTimer = 0;
         }
      }
      
      public function get RangeWeaponTotalDamage() : Number
      {
         if(CurrentRangeWeapon != null)
         {
            return CurrentRangeWeapon.TotalDamage;
         }
         return 0;
      }
      
      public function get MeleeAnimation() : String
      {
         return GetMeleeWeapon().Properties.Animation;
      }
      
      public function set CanRoll(param1:Boolean) : void
      {
         _canRoll = param1;
      }
      
      public function get RunSpeed() : Number
      {
         if(_sprinting)
         {
            return _runSpeed * 2;
         }
         return _runSpeed;
      }
      
      public function get Aiming() : Boolean
      {
         return _aiming;
      }
      
      public function get AddSmokeEffect() : Boolean
      {
         if(_burnState > 0)
         {
            if(!FireRank1Attached)
            {
               return true;
            }
         }
         if(CritSmokeTimer > 0)
         {
            return true;
         }
         return false;
      }
      
      public function get PortalSpeedX() : Number
      {
         if(StuckToRocket)
         {
            return RocketRideProjectile.VelocityX;
         }
         if(_staggering)
         {
            return -LastDirX * 10;
         }
         return _portalSpeedX;
      }
      
      public function get ControllAble() : Boolean
      {
         if(_hp <= 0 || Boolean(_falling) || Boolean(_knockdowned) || Boolean(_rolling) || Boolean(_diving))
         {
            return false;
         }
         if(Boolean(_grabbed_by_player) || Boolean(_kicking) || Punching || Throwing || Boolean(_staggering))
         {
            return false;
         }
         if(IsStunned || DeathKneel)
         {
            return false;
         }
         return true;
      }
      
      public function get HitPunchDamage() : Number
      {
         return GetMeleeWeapon().Properties.HitPunchFrameDamage[_punchComboNr - 1];
      }
      
      public function set Falling(param1:Boolean) : void
      {
         _falling = param1;
         if(_falling)
         {
            _camera_ignore_me_timer = 24 * 3;
            CancelAFS();
            _stunTimer = 0;
            Throwing = false;
            _diving = false;
            _jumping = false;
            JumpKickPerformed = false;
            _knockdowned = false;
            _staggering = false;
            Punching = false;
            _rolling = false;
            TakingCover = false;
            _kicking = false;
            _wallJumping = false;
            Aiming = false;
            _climbing = false;
            DeathKneel = false;
         }
         else
         {
            AirVelocityX = 0;
            AirVelocityY = 0;
         }
      }
      
      public function set PortalDirectionX(param1:int) : void
      {
         _portalDirectionX = param1;
      }
      
      public function get ClimbingDirection() : int
      {
         if(AirVelocityY < 0)
         {
            return -1;
         }
         if(AirVelocityY > 0)
         {
            return 1;
         }
         return 0;
      }
      
      public function get Jumping() : Boolean
      {
         return _jumping;
      }
      
      public function set JumpKickPerformed(param1:Boolean) : void
      {
         _jumpKickPerformed = param1;
      }
      
      public function DecreaseBurnState() : void
      {
         if(BurnState < 100 && !Burned && !InWorldFire)
         {
            BurnState = 0;
         }
         else
         {
            BurnState -= 50;
            if(BurnState < 50)
            {
               BurnState = 50;
            }
         }
      }
      
      public function Update(param1:Number) : void
      {
         game_speed = param1;
         if(_flashEffectTimer > 0)
         {
            _flashEffectTimer -= 1;
         }
         if(SlowmotionDelay > 0)
         {
            SlowmotionDelay -= 1;
         }
         if(ImmunityTimer > 0)
         {
            ImmunityTimer -= game_speed;
         }
         if(HP < 100 && _hp_damage_timer <= 0)
         {
            HP += param1 * 0.1;
         }
         else if(_hp_damage_timer > 0)
         {
            _hp_damage_timer -= game_speed;
         }
         if(CritSmokeTimer > 0)
         {
            CritSmokeTimer -= game_speed;
         }
         if(_inFireDelay > 0)
         {
            _inFireDelay -= game_speed;
         }
         if(AddSmokeEffect)
         {
            if(_inFireDelay <= 0)
            {
               _burnState -= game_speed;
            }
            if(_burnState < 0)
            {
               _burnState = 0;
            }
         }
         if(_kickingTimer > 0)
         {
            _kickingTimer -= game_speed;
         }
         if(_kickingCooldown > 0)
         {
            _kickingCooldown -= game_speed;
         }
         if(_drawDelay > 0)
         {
            _drawDelay -= 1;
         }
         if(_aimTurningAroundTimer > 0)
         {
            _aimTurningAroundTimer -= 1;
            if(_aimTurningAroundTimer <= 0)
            {
               if(AimTurningAround)
               {
                  AimTurningAround = false;
               }
            }
         }
         if(_backToIdleTimer > 0)
         {
            _backToIdleTimer -= 1;
         }
         if(_reSprintActivationDuration > 0)
         {
            _reSprintActivationDuration -= 1;
         }
         if(_sprintActivationDuration > 0)
         {
            _sprintActivationDuration -= 1;
            if(_sprintActivationDuration <= 0)
            {
               _sprinting = false;
            }
         }
         if(_shortDiveTimer > 0)
         {
            _shortDiveTimer -= 1;
            if(_shortDiveTimer <= 0)
            {
               _shortDiveAvailable = false;
            }
         }
         if(_actionCooldown > 0)
         {
            _actionCooldown -= game_speed;
            if(_actionCooldown <= 0)
            {
               _actionAvailable = true;
            }
         }
         if(_showHealthTimer > -24)
         {
            _showHealthTimer -= 1;
            if(_showHealthTimer >= 0)
            {
               _barHP += _healthBarSpeed;
            }
            if(_showHealthTimer <= -24)
            {
               _showHealthTimer = -24;
            }
         }
         if(OnGround && !Rolling)
         {
            if(Boolean(_sprinting) && Boolean(_running))
            {
               _sprintEnergy -= game_speed * 1.2;
               if(_sprintEnergy <= 0)
               {
                  _sprintEnergy = 0;
                  _sprinting = false;
               }
            }
            else if(_sprintEnergy < 100)
            {
               if(_running)
               {
                  _sprintEnergy += game_speed;
               }
               else
               {
                  _sprintEnergy += game_speed + game_speed;
               }
               if(_sprintEnergy > 100)
               {
                  _sprintEnergy = 100;
               }
            }
         }
         else if(Climbing)
         {
            _sprintEnergy += game_speed;
            if(_sprintEnergy > 100)
            {
               _sprintEnergy = 100;
            }
         }
         if(_puchbackDecreaseDelay > 0)
         {
            _puchbackDecreaseDelay -= game_speed;
         }
         else if(_currentPushbackPower > 0)
         {
            _currentPushbackPower -= 10 * game_speed;
         }
         if(_stunTimer > 0)
         {
            _stunTimer -= game_speed;
         }
         if(_camera_ignore_me_timer > 0)
         {
            if(OnGround)
            {
               _camera_ignore_me_timer -= 1;
            }
         }
         if(Jumping)
         {
            AirbornTimer += game_speed;
         }
         if(Staggering)
         {
            StaggerTimer -= game_speed;
            if(StaggerTimer <= 0)
            {
               StopStaggerFunc();
               Staggering = false;
               StaggerTimer = 0;
            }
         }
         if(Burned)
         {
            if(_burnState > 0)
            {
               if(OnGround)
               {
                  _burnState -= game_speed * 1.5;
                  if(_burnState <= 0)
                  {
                     _burnState = 0;
                  }
                  else if(_burnState >= 90)
                  {
                     _burnState = 90;
                  }
               }
            }
         }
         if(_inWorldFire > 0)
         {
            _inWorldFire -= game_speed;
         }
         if(!Knockdowned || HP <= 0)
         {
            if(_decreaseKnockdownGradeTimer > 0)
            {
               _decreaseKnockdownGradeTimer -= game_speed;
               if(_decreaseKnockdownGradeTimer <= 0)
               {
                  _knockdownGrade -= 1;
                  if(_knockdownGrade > 0)
                  {
                     _decreaseKnockdownGradeTimer = 12;
                  }
               }
            }
         }
      }
      
      public function set Knockdowned(param1:Boolean) : void
      {
         _knockdowned = param1;
         if(_knockdowned)
         {
            _stunTimer = 0;
            _staggering = false;
            DeathKneel = false;
         }
      }
      
      public function set TakingCover(param1:Boolean) : void
      {
         _taking_cover = param1;
         if(!_taking_cover)
         {
            if(Box2DCover != null)
            {
               Box2DCover.GetUserData().objectData.PlayerCoverLevel = Box2DCover.GetUserData().objectData.PlayerCoverLevel - 1;
               Box2DCover = null;
            }
         }
      }
      
      public function set Box2DCover(param1:b2Body) : void
      {
         _box2D_cover = param1;
         if(_box2D_cover != null)
         {
            _box2D_cover.GetUserData().objectData.PlayerCoverLevel = _box2D_cover.GetUserData().objectData.PlayerCoverLevel + 1;
         }
      }
      
      public function get KickingTimer() : Number
      {
         return _kickingTimer;
      }
      
      public function set DrawDelay(param1:int) : void
      {
         _drawDelay = param1;
      }
      
      public function IncreaseKnockdownGrade() : void
      {
         if(HP <= 0)
         {
            return;
         }
         if(_knockdownGrade < 3)
         {
            _knockdownGrade += 1;
            _decreaseKnockdownGradeTimer = 12;
         }
      }
      
      public function get MovingDirectionInversed() : int
      {
         return _movingDirectionInversed;
      }
      
      public function get HP() : Number
      {
         return _hp;
      }
      
      public function get AirVelocityX() : Number
      {
         return _airVelocityX;
      }
      
      public function get AirVelocityY() : Number
      {
         return _airVelocityY;
      }
      
      public function set StunTimer(param1:Number) : void
      {
         _stunTimer = param1;
         if(_stunTimer > 0)
         {
            CancelAFS();
            Punching = false;
            DoPunchCombo = false;
         }
         if(_stunAnimation < 2)
         {
            ++_stunAnimation;
         }
         else
         {
            _stunAnimation = 1;
         }
      }
      
      public function get InWorldFire() : Boolean
      {
         return _inWorldFire > 0;
      }
      
      public function get MeleeWeaponTotalDamage() : Number
      {
         return GetMeleeWeapon().TotalDamage;
      }
      
      public function get Climbing() : Boolean
      {
         return _climbing;
      }
      
      public function get GrabbedPlayerCharNr() : int
      {
         return _grabbed_player_char_nr;
      }
      
      public function get MeleeSwingSound() : String
      {
         return GetMeleeWeapon().Properties.SwingComboSounds[_punchComboNr - 1];
      }
      
      public function get Staggering() : Boolean
      {
         return _staggering;
      }
      
      public function get BloodVisible() : Boolean
      {
         return _hp <= 25 && !Burned;
      }
      
      public function set Aiming(param1:Boolean) : void
      {
         _aiming = param1;
         if(param1)
         {
            CurrentAimPitch = 0;
            ResetChangePitchSpeed();
            Kneeling = false;
         }
         else
         {
            _backToIdleTimer = 0;
         }
      }
      
      public function get HitPunchStunTime() : Number
      {
         switch(_punchComboNr)
         {
            case 1:
               return 3 + Math.random() * 5;
            case 2:
               return 4 + Math.random() * 5;
            case 3:
               return 5 + Math.random() * 5;
            default:
               return 0;
         }
      }
      
      public function set PortalSpeedX(param1:Number) : void
      {
         _portalSpeedX = param1;
      }
      
      public function get CoverObjectID() : int
      {
         if(!TakingCover)
         {
            return -1;
         }
         return _cover_object_id;
      }
      
      public function get LastDirX() : int
      {
         return _last_dir_x;
      }
      
      public function get ClimbingAround() : Boolean
      {
         if(AirVelocityX != 0 || AirVelocityY != 0)
         {
            return true;
         }
         return false;
      }
      
      public function GetMeleeMaterialHitEffect(param1:String) : String
      {
         var _loc2_:WeaponMeleeData = null;
         var _loc3_:int = 0;
         param1 = param1.toUpperCase();
         _loc2_ = GetMeleeWeapon();
         _loc3_ = 0;
         while(_loc3_ < _loc2_.Properties.HitMaterialEffects.length)
         {
            if(_loc2_.Properties.HitMaterialEffects[_loc3_][0] == param1)
            {
               return _loc2_.Properties.HitMaterialEffects[_loc3_][1];
            }
            _loc3_++;
         }
         return "";
      }
      
      public function get SprintEnergy() : Number
      {
         return _sprintEnergy;
      }
      
      public function get CameraIgnoreMe() : Boolean
      {
         if(_hp > 0)
         {
            return false;
         }
         if(_camera_ignore_me_timer > 0)
         {
            return false;
         }
         if(_staggering)
         {
            return false;
         }
         return true;
      }
      
      public function get ShowHealthBar() : Boolean
      {
         if(_showHealthTimer > -24)
         {
            return true;
         }
         return false;
      }
      
      public function get DeathKneel() : Boolean
      {
         return _deathKneel;
      }
      
      public function get PunchHitPerformed() : Boolean
      {
         return _punchHitPerformed;
      }
      
      public function get Running() : Boolean
      {
         return _running;
      }
      
      public function set Jumping(param1:Boolean) : void
      {
         _jumping = param1;
         if(!_jumping)
         {
            JumpKickPerformed = false;
            _airVelocityY = 0;
            _wallJumping = false;
         }
         else
         {
            AirbornTimer = 0;
            _rolling = false;
            TakingCover = false;
            DeathKneel = false;
            if(_knockdowned)
            {
               Falling = true;
            }
         }
         QueueJumpKick = false;
      }
      
      public function get CurrentPushbackPower() : Number
      {
         return _currentPushbackPower;
      }
      
      public function get CanDive() : Boolean
      {
         if(!_actionAvailable)
         {
            return false;
         }
         return _canDive;
      }
      
      public function get Diving() : Boolean
      {
         return _diving;
      }
      
      public function get GrabbedPlayer() : Boolean
      {
         return _grabbed_player;
      }
      
      public function set KickingTimer(param1:Number) : void
      {
         _kickingTimer = param1;
      }
      
      public function get IsStunned() : Boolean
      {
         return _stunTimer > 0;
      }
      
      public function get StairVelocityX() : Number
      {
         return _stairVelocityX;
      }
      
      public function get MeleeWeaponHitSound() : String
      {
         return GetMeleeWeapon().Properties.HitSound;
      }
      
      public function get WallJumpSpeed() : Number
      {
         return _runSpeed;
      }
      
      public function get AFSInProgress() : Boolean
      {
         return CurrentFireFrame > 0;
      }
      
      public function get CurrentAimAngleThrowable() : Number
      {
         if(LastDirX == 1)
         {
            return CurrentAimPitch - 25;
         }
         return 180 - CurrentAimPitch + 25;
      }
      
      public function get StairVelocityY() : Number
      {
         return _stairVelocityY;
      }
      
      public function set PunchComboNr(param1:int) : void
      {
         PunchHitPerformed = false;
         _punchComboNr = param1;
      }
      
      public function set MovingDirectionInversed(param1:int) : void
      {
         _movingDirectionInversed = param1;
      }
      
      public function set HP(param1:Number) : void
      {
         if(_hp <= 0)
         {
            return;
         }
         if(_hp > param1)
         {
            _hp_damage_timer = 24 * 3;
         }
         _barHP = _hp;
         _hp = param1;
         if(_hp <= 0)
         {
            _hp = 0;
         }
         if(_hp > 100)
         {
            _hp = 100;
         }
         _healthBarSpeed = (_hp - _barHP) / 6;
         _showHealthTimer = 6;
      }
      
      public function get KnockdownGrade() : int
      {
         return _knockdownGrade;
      }
      
      public function set AirVelocityY(param1:Number) : void
      {
         _airVelocityY = param1;
      }
      
      public function get Rolling() : Boolean
      {
         return _rolling;
      }
      
      public function set ForceHP(param1:Number) : void
      {
         _barHP = param1;
         _hp = param1;
      }
      
      public function set AirVelocityX(param1:Number) : void
      {
         _airVelocityX = param1;
      }
      
      public function get AimTurningAroundDelay() : Boolean
      {
         if(Boolean(_aimTurningAround) || _aimTurningAroundTimer > 0)
         {
            return true;
         }
         return false;
      }
      
      public function get GrabbedPlayerNr() : int
      {
         return _grabbed_player_nr;
      }
      
      public function get ShowFlashEffect() : Boolean
      {
         return _showFlashEffect;
      }
      
      public function UpdateCameraIgnoreTimer() : void
      {
         if(_camera_ignore_me_timer > 0)
         {
            _camera_ignore_me_timer -= 1;
         }
      }
      
      public function GetKickMaterialHitSound(param1:String) : String
      {
         var _loc2_:int = 0;
         param1 = param1.toUpperCase();
         _loc2_ = 0;
         while(_loc2_ < kickHitMaterialSounds.length)
         {
            if(kickHitMaterialSounds[_loc2_][0] == param1)
            {
               return kickHitMaterialSounds[_loc2_][1];
            }
            _loc2_++;
         }
         return "";
      }
      
      public function get FlashEffectTimer() : int
      {
         return _flashEffectTimer;
      }
      
      public function set InWorldFire(param1:Boolean) : void
      {
         if(param1)
         {
            _inWorldFire = 2.5;
         }
         else
         {
            _inWorldFire = 0;
         }
      }
      
      public function set Climbing(param1:Boolean) : void
      {
         _climbing = param1;
         if(!param1)
         {
            CurrentLadder = null;
            QueueJumpKick = false;
            JumpKickPerformed = false;
            AirbornTimer = 0;
         }
      }
      
      public function GetKickMaterialHitEffect(param1:String) : String
      {
         var _loc2_:int = 0;
         param1 = param1.toUpperCase();
         _loc2_ = 0;
         while(_loc2_ < kickHitMaterialEffects.length)
         {
            if(kickHitMaterialEffects[_loc2_][0] == param1)
            {
               return kickHitMaterialEffects[_loc2_][1];
            }
            _loc2_++;
         }
         return "";
      }
      
      public function get PortalDirectionX() : int
      {
         if(StuckToRocket)
         {
            return ConvertToDirection(RocketRideProjectile.VelocityX);
         }
         return _portalDirectionX;
      }
      
      public function get Falling() : Boolean
      {
         return _falling;
      }
      
      public function set Staggering(param1:Boolean) : void
      {
         _staggering = param1;
         if(!param1)
         {
            _staggerTimer = 0;
         }
         else
         {
            Punching = false;
            _knockdowned = false;
            _falling = false;
            _jumping = false;
         }
      }
      
      public function get IsImmune() : Boolean
      {
         return ImmunityTimer > 0 && !ImmunityDisabled;
      }
      
      public function set GrabbedPlayerCharNr(param1:int) : void
      {
         _grabbed_player_char_nr = param1;
      }
      
      public function get Knockdowned() : Boolean
      {
         return _knockdowned;
      }
      
      public function get TakingCover() : Boolean
      {
         return _taking_cover;
      }
      
      public function get DrawDelay() : int
      {
         return _drawDelay;
      }
      
      public function set LastDirX(param1:int) : void
      {
         _last_dir_x = param1;
      }
      
      public function get TotalAirVelocity() : Number
      {
         return Math.sqrt(_airVelocityX * _airVelocityX + _airVelocityY * _airVelocityY);
      }
      
      public function get JumpKickPerformed() : Boolean
      {
         return _jumpKickPerformed;
      }
      
      public function get StunTimer() : Number
      {
         return _stunTimer;
      }
      
      public function get MeleeWeaponRange() : Number
      {
         return GetMeleeWeapon().Properties.Range[_punchComboNr - 1];
      }
      
      public function set KickingCooldown(param1:Number) : void
      {
         _kickingCooldown = param1;
      }
      
      public function get RangeWeaponTotalAmmo() : Number
      {
         if(CurrentRangeWeapon != null)
         {
            if(CurrentRangeWeapon.Properties.WeaponType == "FLAMETHROWER")
            {
               return CurrentRangeWeapon.Ammo / 10;
            }
            return CurrentRangeWeapon.Ammo;
         }
         return 0;
      }
      
      public function set AimTurningAround(param1:Boolean) : void
      {
         _aimTurningAround = param1;
         if(!param1)
         {
            _aimTurningAroundTimer = 2;
         }
         else
         {
            BackToIdleTimer = 0;
         }
      }
      
      public function set CoverObjectID(param1:int) : void
      {
         _cover_object_id = param1;
      }
      
      public function set SprintEnergy(param1:Number) : void
      {
         _sprintEnergy = param1;
         if(_sprintEnergy < 0)
         {
            _sprintEnergy = 0;
         }
      }
      
      public function set Sprinting(param1:Boolean) : void
      {
         _sprinting = param1;
      }
      
      public function get MaxPlayerHeight() : Number
      {
         return 18;
      }
      
      public function get LowerAimPitch() : int
      {
         switch(AimMode)
         {
            case 0:
               return 90;
            case 1:
               return 90;
            default:
               return 45;
         }
      }
      
      public function get PunchComboNr() : int
      {
         return _punchComboNr;
      }
      
      public function get CurrentAimAngle() : Number
      {
         if(LastDirX == 1)
         {
            return CurrentAimPitch;
         }
         return 180 - CurrentAimPitch;
      }
      
      public function get RangeWeaponRange() : Number
      {
         if(CurrentRangeWeapon != null)
         {
            return CurrentRangeWeapon.Properties.ShootRange;
         }
         return 40;
      }
      
      public function set DeathKneel(param1:Boolean) : void
      {
         _deathKneel = param1;
         if(param1)
         {
            Staggering = false;
            Punching = false;
            CancelAFS();
         }
      }
      
      public function set PunchHitPerformed(param1:Boolean) : void
      {
         _punchHitPerformed = param1;
      }
      
      public function set Running(param1:Boolean) : void
      {
         if(!param1)
         {
            if(_sprinting)
            {
               _sprinting = false;
               _reSprintActivationDuration = 2;
            }
            else if(Boolean(_running) && !_jumping && !TakingCover)
            {
               _sprintActivationDuration = 3;
            }
         }
         else if(_reSprintActivationDuration > 0)
         {
            _reSprintActivationDuration = 0;
            _sprintActivationDuration = 0;
            _sprinting = true;
         }
         else if(_sprintActivationDuration > 0)
         {
            _shortDiveAvailable = true;
            _shortDiveTimer = 3;
            _sprintActivationDuration = 0;
            _sprinting = true;
         }
         _running = param1;
      }
      
      public function get KickingCooldown() : Number
      {
         return _kickingCooldown;
      }
      
      public function get AimTurningAround() : Boolean
      {
         return _aimTurningAround;
      }
      
      public function set CurrentPushbackPower(param1:Number) : void
      {
         _currentPushbackPower = param1;
         _puchbackDecreaseDelay = 3;
      }
      
      public function set WallJumping(param1:Boolean) : void
      {
         _wallJumping = param1;
      }
      
      public function get CanGrabWeapon() : Boolean
      {
         if(Boolean(_falling) || Boolean(_knockdowned) || Boolean(_grabbed_by_player) || Boolean(_climbing) || Throwing || Boolean(_kicking) || Punching)
         {
            return false;
         }
         if(IsStunned || Boolean(_staggering) || DeathKneel)
         {
            return false;
         }
         return true;
      }
      
      public function get Sprinting() : Boolean
      {
         return _sprinting;
      }
      
      public function set StaggerTimer(param1:Number) : void
      {
         _staggerTimer = param1;
      }
      
      public function set Kicking(param1:Boolean) : void
      {
         _kicking = param1;
         if(_kicking)
         {
            KickingTimer = 8;
            _kickingCooldown = 8;
            TakingCover = false;
         }
      }
      
      public function get CanBeKicked() : Boolean
      {
         if(IsImmune)
         {
            return false;
         }
         if(_knockdownGrade >= 2)
         {
            return false;
         }
         if(GrabbedByPlayer)
         {
            return false;
         }
         if(IgnoreMe)
         {
            return false;
         }
         return true;
      }
      
      public function GetMeleeMaterialHitSound(param1:String) : String
      {
         var _loc2_:WeaponMeleeData = null;
         var _loc3_:int = 0;
         param1 = param1.toUpperCase();
         _loc2_ = GetMeleeWeapon();
         _loc3_ = 0;
         while(_loc3_ < _loc2_.Properties.HitMaterialSounds.length)
         {
            if(_loc2_.Properties.HitMaterialSounds[_loc3_][0] == param1)
            {
               return _loc2_.Properties.HitMaterialSounds[_loc3_][1];
            }
            _loc3_++;
         }
         return "";
      }
      
      public function get PlayerHeight() : Number
      {
         if(_diving)
         {
            return 8;
         }
         if(_knockdowned)
         {
            return 10;
         }
         if(_falling)
         {
            return 12;
         }
         if(_rolling)
         {
            return 14;
         }
         if(Boolean(_kneeling) || TakingCover)
         {
            return 12;
         }
         return 18;
      }
      
      public function get CurrentAimAngleRad() : Number
      {
         return CurrentAimAngle * (Math.PI / 180);
      }
      
      public function set CanDive(param1:Boolean) : void
      {
         _canDive = param1;
      }
      
      public function set MovingDirectionX(param1:int) : void
      {
         _movingDirectionX = param1;
      }
      
      public function GetMeleeWeapon() : WeaponMeleeData
      {
         if(CurrentMeleeWeapon != null)
         {
            return CurrentMeleeWeapon;
         }
         return DefaultMeleeWeapon;
      }
      
      public function get UpperAimPitch() : int
      {
         switch(AimMode)
         {
            case 0:
               return 90;
            case 1:
               return 90;
            default:
               return 90;
         }
      }
      
      public function set GrabbedByPlayer(param1:Boolean) : void
      {
         _grabbed_by_player = param1;
      }
      
      public function set Diving(param1:Boolean) : void
      {
         _diving = param1;
      }
      
      public function get WallJumping() : Boolean
      {
         return _wallJumping;
      }
      
      public function set GrabbedPlayer(param1:Boolean) : void
      {
         _grabbed_player = param1;
      }
      
      public function get RangeWeaponIsBazooka() : Boolean
      {
         if(CurrentRangeWeapon != null)
         {
            if(CurrentRangeWeapon.Properties.WeaponType == "BAZOOKA")
            {
               return true;
            }
         }
         return false;
      }
      
      public function get RangeWeaponCanShootDown() : Boolean
      {
         if(CurrentRangeWeapon != null)
         {
            return CurrentRangeWeapon.CanShootDown;
         }
         return false;
      }
      
      public function set Kneeling(param1:Boolean) : void
      {
         _kneeling = param1;
         if(_kneeling)
         {
            _sprinting = false;
            if(TakingCover)
            {
               _kneeling = false;
            }
         }
      }
      
      public function set CharNr(param1:int) : void
      {
         _char_nr = param1;
      }
      
      public function get StaggerTimer() : Number
      {
         return _staggerTimer;
      }
      
      public function get MinPunchComboFrame() : int
      {
         switch(_punchComboNr)
         {
            case 1:
               return 6;
            case 2:
               return 7;
            case 3:
               return 8;
            default:
               return 0;
         }
      }
      
      public function get Kicking() : Boolean
      {
         return _kicking;
      }
      
      public function set BurnState(param1:Number) : void
      {
         if(!Burned)
         {
            _burnState = param1;
            _inFireDelay = 3.5;
            if(_burnState > 100)
            {
               _burnState = 100;
            }
            else if(_burnState < 0)
            {
               _burnState = 0;
            }
         }
      }
      
      private function ConvertToDirection(param1:Number) : int
      {
         if(param1 == 0)
         {
            return 0;
         }
         return param1 / Math.sqrt(param1 * param1);
      }
      
      public function get StunAnimation() : int
      {
         return _stunAnimation;
      }
      
      public function get GrabbedByPlayer() : Boolean
      {
         return _grabbed_by_player;
      }
      
      public function get MovingDirectionX() : int
      {
         return _movingDirectionX;
      }
      
      public function get RangeWeaponIsFlamethrower() : Boolean
      {
         if(CurrentRangeWeapon != null)
         {
            if(CurrentRangeWeapon.Properties.WeaponType == "FLAMETHROWER")
            {
               return true;
            }
         }
         return false;
      }
      
      public function get Kneeling() : Boolean
      {
         return _kneeling;
      }
      
      public function get CharNr() : int
      {
         return _char_nr;
      }
      
      public function set StairVelocityX(param1:Number) : void
      {
         _stairVelocityX = param1;
      }
      
      public function set StairVelocityY(param1:Number) : void
      {
         _stairVelocityY = param1;
      }
      
      public function get BurnState() : Number
      {
         if(Gone)
         {
            return 0;
         }
         return _burnState;
      }
      
      public function CancelAFS() : void
      {
         CurrentFireFrame = 0;
         LastFireFrame = 0;
         if(BackToIdleTimer < 6)
         {
            BackToIdleTimer = 6;
         }
      }
   }
}

