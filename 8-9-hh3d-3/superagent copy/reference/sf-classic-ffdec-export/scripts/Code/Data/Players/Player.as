package Code.Data.Players
{
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.b2Body;
   import Code.Box2D.Dynamics.b2World;
   import Code.Data.*;
   import Code.Data.Weapons.*;
   import Code.Handler.Effects;
   import Code.Handler.Fires;
   import Code.Handler.InputKeyboard;
   import Code.Handler.Maps;
   import Code.Handler.OutputTrace;
   import Code.Handler.PathGrid;
   import Code.Handler.ProjectilesUpdater;
   import Code.Handler.Shake;
   import Code.Handler.Slowmo;
   import Code.Handler.Sounds;
   import Code.Particles.*;
   import fl.motion.*;
   import flash.display.*;
   import flash.geom.*;
   import flash.utils.*;
   
   [Embed(source="/_assets/assets.swf", symbol="symbol120")]
   public class Player extends MovieClip
   {
      public static const KEY_UP:int = 0;
      
      public static const KEY_DOWN:int = 1;
      
      public static const KEY_LEFT:int = 2;
      
      public static const KEY_RIGHT:int = 3;
      
      public static const KEY_MELEE:int = 4;
      
      public static const KEY_FIRE:int = 5;
      
      public static const KEY_THROW:int = 6;
      
      public static const KEY_POWERUP:int = 7;
      
      public static const KEY_JUMP:int = 8;
      
      public static const KEY_KNEEL:int = 9;
      
      public static const KEY_SPRINT:int = 10;
      
      public static const AIM_SQUARE_DISTANCE:Number = 8;
      
      public static const HAZARDOUS_DISTANCE:Number = 25;
      
      public static const HAZARDOUS_DISTANCE_AVOID:Number = 45;
      
      public static const TEAM_SOLO:int = 0;
      
      public static const TEAM_1:int = 1;
      
      public static const TEAM_2:int = 2;
      
      public static const TEAM_3:int = 3;
      
      public static const TEAM_4:int = 4;
      
      private var _last_slowmotion:SlowmoData = null;
      
      private var AFSUpdated:Boolean = false;
      
      private var _staggerFragileObject:b2Body = null;
      
      private var _char:MovieClip;
      
      private var _this_x:Number;
      
      private var _this_y:Number;
      
      private var _gui_mc:MovieClip;
      
      private var _static_objects_hitbox_mc:MovieClip;
      
      private var _button_in_melee_range:Boolean = false;
      
      private var _static_players_area_mc:MovieClip;
      
      private var _PlayerState:PlayerState;
      
      private var _activated:Boolean = false;
      
      private var _Handler_Slowmo:Slowmo;
      
      private var _flameAwayCounter:Number = 0;
      
      private var _slowmotion_timer:int = 0;
      
      private var b:b2Body;
      
      private var _players:Array;
      
      private var _static_objects_cloud_hitbox_mc:MovieClip;
      
      private var _BotState:BotState;
      
      private var _static_ladder_hitbox_mc:MovieClip;
      
      private var _Handler_Maps:Maps;
      
      private var _performJumpDownLevel:Boolean = false;
      
      private var _flameAwayActivated:Boolean = false;
      
      private var _Handler_ProjectilesUpdater:*;
      
      private var _static_world_hitbox_mc:MovieClip;
      
      private var _standingOnObject:b2Body = null;
      
      private var _indicationWeapon:b2Body = null;
      
      internal var _edgePositionL:Number;
      
      private var _bot:Boolean = false;
      
      internal var _edgePositionR:Number;
      
      private var _flameAwayTimer:Number;
      
      private var _lazer_mc:MovieClip;
      
      private var m_world:b2World;
      
      private var _player_area_mc:MovieClip;
      
      private var _Handler_Fires:Fires;
      
      private var _lastBounceY:Number;
      
      private var _startAimASAP:Boolean = false;
      
      private var _old_this_x:Number;
      
      private var _old_this_y:Number;
      
      private var _playerNr:int;
      
      private var _Handler_Output:OutputTrace;
      
      private var _char_gui:MovieClip;
      
      private var _player_mc:MovieClip;
      
      private var _Handler_Sounds:Sounds;
      
      private var _downTimer:Number;
      
      private var _cancelAimingASAP:Boolean = false;
      
      private var _slowmotion_modifier:Number = 1;
      
      private var _keyPressed:Array;
      
      internal var _headColl:Boolean;
      
      internal var _sideColl:Boolean;
      
      private var _pathGrid:PathGrid;
      
      private var _static_world_cloud_hitbox_mc:MovieClip;
      
      private var _Handler_Effects:Effects;
      
      private var _bullet_game_speed:Number = 1;
      
      private var _MapArea:PlayerAreaData;
      
      private var _keys:Array;
      
      private var _smokeDelay:Number = 0;
      
      private var _PlayerBars:PlayerBars;
      
      private var RecalculateCamArea:Function;
      
      private var _botTimer:Number;
      
      private var _dynamic_mc:MovieClip;
      
      private var _team:Number;
      
      private var _PlayerAnimation:PlayerAnimation;
      
      private var _button_to_activate:b2Body = null;
      
      private var _game_speed:Number = 1;
      
      private var _blood_mc:MovieClip;
      
      private var _static_players_hitbox_mc:MovieClip;
      
      private var _deathScreamDone:Boolean = false;
      
      private var _lazer_rnd:Number = 0;
      
      private var _Handler_Shake:Shake;
      
      private var _static_mc:MovieClip;
      
      private var _collision_mc:MovieClip;
      
      private var objectImpactList:Array;
      
      private var _game_mc:MovieClip;
      
      private var _jumpDownPosYDisable:Number = 0;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      internal var _edgePosition:Number;
      
      private var _aim_mc:MovieClip;
      
      private var _enableJumpDownLevel:Boolean = false;
      
      private var _blood_gui:MovieClip;
      
      public function Player(param1:int, param2:MovieClip, param3:b2World, param4:Maps, param5:Sounds, param6:Slowmo, param7:Shake, param8:Effects, param9:ProjectilesUpdater, param10:OutputTrace, param11:Point, param12:Number, param13:int, param14:Function, param15:Array, param16:PathGrid)
      {
         var _loc17_:MovieClip = null;
         var _loc18_:* = undefined;
         var _loc19_:MovieClip = null;
         _bot = false;
         _game_speed = 1;
         _last_slowmotion = null;
         _slowmotion_timer = 0;
         _slowmotion_modifier = 1;
         _bullet_game_speed = 1;
         _lazer_rnd = 0;
         _startAimASAP = false;
         _cancelAimingASAP = false;
         _smokeDelay = 0;
         _deathScreamDone = false;
         _activated = false;
         _indicationWeapon = null;
         _performJumpDownLevel = false;
         _jumpDownPosYDisable = 0;
         _enableJumpDownLevel = false;
         _standingOnObject = null;
         _flameAwayCounter = 0;
         _flameAwayActivated = false;
         AFSUpdated = false;
         _button_in_melee_range = false;
         _button_to_activate = null;
         _staggerFragileObject = null;
         super();
         _game_mc = param2;
         m_world = param3;
         _Handler_Output = param10;
         _Handler_Effects = param8;
         _Handler_ProjectilesUpdater = param9;
         _Handler_Maps = param4;
         _Handler_Sounds = param5;
         _Handler_Slowmo = param6;
         _Handler_Shake = param7;
         _pathGrid = param16;
         PlayerNr = param13;
         RecalculateCamArea = param14;
         _static_mc = MovieClip(_game_mc.getChildByName("STATIC"));
         _loc17_ = MovieClip(_game_mc.getChildByName("GAME_WINDOW"));
         _dynamic_mc = MovieClip(MovieClip(_loc17_.getChildByName("DYNAMICHOLDER")).getChildByName("DYNAMIC"));
         _static_ladder_hitbox_mc = MovieClip(_static_mc.getChildByName("LADDER_HITBOX"));
         _static_world_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_HITBOX"));
         _static_world_cloud_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_CLOUD_HITBOX"));
         _static_objects_cloud_hitbox_mc = MovieClip(_static_world_cloud_hitbox_mc.getChildByName("OBJECTS_CLOUD_HITBOX"));
         _static_objects_hitbox_mc = MovieClip(_static_world_hitbox_mc.getChildByName("OBJECTS_HITBOX"));
         _static_players_hitbox_mc = MovieClip(_static_mc.getChildByName("PLAYERS_HITBOX"));
         _static_players_area_mc = MovieClip(_static_mc.getChildByName("PLAYERS_AREA"));
         _lazer_mc = new MovieClip();
         _lazer_mc.visible = false;
         _aim_mc = new player_aim();
         _aim_mc.visible = false;
         MovieClip(_dynamic_mc.getChildByName("LAZERS")).addChild(_lazer_mc);
         MovieClip(_dynamic_mc.getChildByName("LAZERS")).addChild(_aim_mc);
         _collision_mc = new player_hitarea();
         _player_area_mc = new MovieClip();
         _player_area_mc.graphics.lineStyle(1,16711680,0.5);
         _player_area_mc.graphics.beginFill(16711680,0.5);
         _player_area_mc.graphics.moveTo(-6,2);
         _player_area_mc.graphics.lineTo(-6,-18);
         _player_area_mc.graphics.lineTo(6,-18);
         _player_area_mc.graphics.lineTo(6,2);
         _player_area_mc.graphics.lineTo(-6,2);
         _player_area_mc.graphics.endFill();
         _static_players_hitbox_mc.addChild(_collision_mc);
         _static_players_area_mc.addChild(_player_area_mc);
         _char = PlayerCharacter.Get(param1);
         _char.x = 0;
         _char.y = 0;
         this.addChild(_char);
         _blood_mc = new player_blood();
         _blood_mc.visible = false;
         this.addChild(_blood_mc);
         _player_mc = MovieClip(_dynamic_mc.getChildByName("PLAYERS"));
         _player_mc.addChild(this);
         this.x = param11.x;
         this.y = param11.y;
         _team = param12;
         if(_team == 0)
         {
            _team = -PlayerNr - 1;
         }
         _keyPressed = new Array(20);
         _loc18_ = 0;
         while(_loc18_ < _keyPressed.length)
         {
            _keyPressed[_loc18_] = false;
            _loc18_++;
         }
         _PlayerState = new PlayerState();
         _PlayerState.Team = _team;
         _PlayerState.CharNr = param1;
         _PlayerState.StopStaggerFunc = StopStaggerFunc;
         _PlayerAnimation = new PlayerAnimation(_char,_blood_mc,_collision_mc,_PlayerState,_Handler_Output);
         _loc19_ = MovieClip(_dynamic_mc.parent.parent.getChildByName("GUI"));
         _PlayerBars = new PlayerBars(_PlayerState,_loc19_);
         _players = param15;
         _Handler_Output.Trace("Player Constructed at: " + param11);
      }
      
      public function ExplosionX() : Number
      {
         return MidPosX();
      }
      
      public function ExplosionY() : Number
      {
         return MidPosY();
      }
      
      private function KillPlayer() : void
      {
      }
      
      private function ThrowUp() : void
      {
         if(Boolean(_PlayerState.StuckToRocket) || Boolean(_PlayerState.Staggering))
         {
            return;
         }
         _startAimASAP = false;
         if(!_PlayerState.Throwing && Boolean(_PlayerState.Aiming) && !_PlayerState.AimTurningAroundDelay)
         {
            if(_PlayerState.AimMode == 1)
            {
               _PlayerState.Throwing = true;
               _PlayerState.Aiming = false;
               ReleaseThrowable();
            }
         }
      }
      
      public function LinkToFire(param1:Fires) : void
      {
         _Handler_Fires = param1;
      }
      
      private function MainUpdate() : void
      {
         var _loc1_:int = 0;
         var _loc2_:int = 0;
         var _loc3_:Number = NaN;
         if(_PlayerState.HP > 0 && Boolean(_PlayerState.ShowFlashEffect))
         {
            if(_PlayerState.FlashEffectTimer > 0)
            {
               UpdateFlashEffect();
            }
            else
            {
               StopFlashEffect();
            }
         }
         else if(_PlayerState.ShowFlashEffect)
         {
            StopFlashEffect();
         }
         if(_PlayerState.GrabbedByPlayer)
         {
            return;
         }
         if(_PlayerState.StuckToRocket)
         {
            AddSmokeTrace(1);
            _PlayerState.RocketRideTimer += _game_speed;
            if(_PlayerState.RocketRideTimer > 150)
            {
               _PlayerState.RocketRideProjectile.Explode();
               return;
            }
            if(Boolean(_keyPressed[3]))
            {
               _PlayerState.RocketRideProjectile.Angle += 20 * _game_speed;
            }
            if(Boolean(_keyPressed[2]))
            {
               _PlayerState.RocketRideProjectile.Angle -= 20 * _game_speed;
            }
            return;
         }
         _old_this_x = _this_x;
         _old_this_y = _this_y;
         _PlayerState.MovingDirectionX = 0;
         UpdateInversedDirection();
         if(_PlayerState.TakingCover)
         {
            if(!CanTakeCover(_PlayerState.LastDirX))
            {
               _PlayerState.TakingCover = false;
            }
         }
         if(_PlayerState.ControllAble)
         {
            if(_PlayerState.Aiming)
            {
               if(!_PlayerState.AimTurningAroundDelay)
               {
                  if(Boolean(_keyPressed[1]))
                  {
                     AimDown();
                  }
                  else if(Boolean(_keyPressed[0]))
                  {
                     AimUp();
                  }
                  else
                  {
                     AimIdle();
                  }
                  AimLazer();
                  if(PressingLeft())
                  {
                     AimLeft();
                  }
                  else if(PressingRight())
                  {
                     AimRight();
                  }
               }
               else if(Boolean(_keyPressed[1]))
               {
                  AimDown();
               }
               else if(Boolean(_keyPressed[0]))
               {
                  AimUp();
               }
               else
               {
                  AimIdle();
               }
            }
            else
            {
               if(!_PlayerState.Sprinting)
               {
                  if(KeyPressed(KEY_SPRINT))
                  {
                     if(_PlayerState.SprintEnergy > 10)
                     {
                        _PlayerState.Sprinting = true;
                     }
                  }
               }
               if(_PlayerState.PlayerJumpPushActivated)
               {
                  if(Boolean(_PlayerState.Jumping) && Boolean(_PlayerState.PlayerJumpPushEnabled))
                  {
                     if(Boolean(_keyPressed[KEY_JUMP]))
                     {
                        _PlayerState.JumpPushTimeLeft -= _game_speed;
                        if(_PlayerState.JumpPushTimeLeft <= 0)
                        {
                           _PlayerState.PlayerJumpPushEnabled = false;
                        }
                        else if(_PlayerState.PlayerJumpPushLevelOut)
                        {
                           _loc3_ = _PlayerState.JumpPushTimeLeft / _PlayerState.PlayerJumpPushTime;
                           _PlayerState.AirVelocityY += _PlayerState.PlayerJumpPushPower * _loc3_ * _game_speed;
                        }
                        else
                        {
                           _PlayerState.AirVelocityY += _PlayerState.PlayerJumpPushPower * _game_speed;
                        }
                     }
                     else
                     {
                        _PlayerState.PlayerJumpPushEnabled = false;
                     }
                  }
               }
               if(Boolean(_keyPressed[KEY_UP]))
               {
                  if(_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY(),true))
                  {
                     _PlayerState.Climbing = true;
                  }
               }
               else if(Boolean(_keyPressed[KEY_DOWN]))
               {
                  if(!_PlayerState.OnGround)
                  {
                     if(_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY(),true))
                     {
                        _PlayerState.Climbing = true;
                     }
                  }
               }
               if(Boolean(_keyPressed[KEY_KNEEL]) && !_PlayerState.TakingCover)
               {
                  if(_PlayerState.OnGround)
                  {
                     if(!_keyPressed[2] && !_keyPressed[3])
                     {
                        if(!_PlayerState.DisableKneel)
                        {
                           _PlayerState.Kneeling = true;
                        }
                     }
                     else
                     {
                        if(!CheckForceKneeling())
                        {
                           _PlayerState.Kneeling = false;
                        }
                        if(_PlayerState.Sprinting)
                        {
                           if(Boolean(_PlayerState.CanDive) || Boolean(_PlayerState.ShortDiveAvailable))
                           {
                              Dive();
                           }
                        }
                        else if(_PlayerState.ShortDiveAvailable)
                        {
                           Dive();
                        }
                        else if(_PlayerState.CanRoll)
                        {
                           Roll();
                        }
                     }
                  }
               }
               else if(!CheckForceKneeling())
               {
                  _PlayerState.Kneeling = false;
               }
               if(!_PlayerState.Climbing)
               {
                  if(PressingLeft(true))
                  {
                     MoveDirection(-1);
                  }
                  else if(PressingRight(true))
                  {
                     MoveDirection(1);
                  }
                  else if(_PlayerState.WallJumping)
                  {
                     MovePlayer(1,_PlayerState.WallJumpSpeed);
                  }
               }
            }
            UpdateWeaponGrab();
            if(_PlayerState.QueueJumpKick)
            {
               if(_PlayerState.Jumping)
               {
                  if(!_PlayerState.JumpKickPerformed && _PlayerState.AirbornTimer >= 2.5 && !_PlayerState.Climbing)
                  {
                     _Handler_Sounds.PlaySoundAt("KICK_SWING",PosX(),PosY());
                     Kick(false,true);
                     _PlayerState.JumpKickPerformed = true;
                  }
               }
            }
         }
         else
         {
            _lazer_mc.visible = false;
            _aim_mc.visible = false;
            if(_PlayerState.Staggering)
            {
               if(CanStagger())
               {
                  if(_staggerFragileObject != null)
                  {
                     _staggerFragileObject.ApplyImpulse(new b2Vec2(-_PlayerState.LastDirX * 0.5,0),new b2Vec2(0,0));
                     _staggerFragileObject.GetUserData().objectData.ForceDestruction();
                     _staggerFragileObject = null;
                  }
                  MovePlayer(_PlayerState.LastDirX,_PlayerState.LastDirX * _PlayerState.StaggerSpeed);
               }
               else
               {
                  if(_PlayerState.HP <= 0)
                  {
                     Fall(false);
                  }
                  _PlayerState.Staggering = false;
               }
            }
            else if(_PlayerState.Rolling)
            {
               MovePlayer(_PlayerState.LastDirX,_PlayerState.LastDirX * _PlayerState.RollSpeed);
               UpdateWeaponGrab();
            }
            else if(!_PlayerState.IsStunned)
            {
               if(_PlayerState.Punching)
               {
                  if(!_PlayerState.PunchHitPerformed)
                  {
                     if(_PlayerAnimation.NextFrame(_game_speed) < _PlayerState.HitPunchComboFrame)
                     {
                        if(PressingLeft())
                        {
                           TurnLeft();
                        }
                        else if(PressingRight())
                        {
                           TurnRight();
                        }
                     }
                     else if(_PlayerAnimation.NextFrame(_game_speed) == _PlayerState.HitPunchComboFrame)
                     {
                        MeleeStrike();
                     }
                  }
                  else if(_PlayerState.PunchComboNr == 3)
                  {
                     MovePlayer(_PlayerState.LastDirX,_PlayerState.PunchGlideSpeed * _PlayerState.LastDirX * (1 - _PlayerAnimation.Progress));
                  }
               }
            }
         }
         if(!_PlayerState.ControllAble || Boolean(_PlayerState.Aiming) || !_keyPressed[2] && !_keyPressed[3] || Boolean(_keyPressed[2]) && Boolean(_keyPressed[3]))
         {
            _PlayerState.Running = false;
         }
         UpdateObjectImpacts();
         UpdateStairBounce();
         if(!_PlayerState.OnGround)
         {
            UpdateAirMovement();
         }
         else
         {
            UpdateGroundMovement();
         }
         if(Stuck())
         {
            _this_x = _old_this_x;
            _this_y = _old_this_y;
         }
         this.x = _this_x;
         this.y = _this_y;
         _collision_mc.x = _this_x;
         _collision_mc.y = _this_y;
         _player_area_mc.x = _this_x;
         _player_area_mc.y = _this_y;
         _PlayerState.PortalSpeedX = Math.abs(_this_x - _old_this_x) / _game_speed;
         _loc1_ = int(ConvertToDirection(_this_x - _old_this_x));
         if(_loc1_ != 0)
         {
            _PlayerState.PortalDirectionX = _loc1_;
         }
         ProgressAFS();
         AFSUpdated = false;
         _loc2_ = 0;
         while(_loc2_ < m_world.MolotovList.length)
         {
            b = m_world.MolotovList[_loc2_];
            if(b.GetUserData().objectData.UserValues[0] != PlayerNr)
            {
               if(CollisionMC.hitTestObject(b.GetUserData().objectData.ShapeMC))
               {
                  if(CollisionMC.hitTestPoint(b.GetPosition().x * 30,b.GetPosition().y * 30,true))
                  {
                     b.GetUserData().objectData.ForceDestruction();
                  }
               }
            }
            _loc2_++;
         }
         if(_PlayerState.EmptyWeaponRecoilBack > 0)
         {
            _PlayerState.EmptyWeaponRecoilBack -= 1;
            if(_PlayerState.EmptyWeaponRecoilBack <= 0)
            {
               if(_char.ANIM_WPN != null)
               {
                  _char.ANIM_WPN.x = _PlayerState.CharAnimWpnX;
                  _char.ANIM_WPN.y = _PlayerState.CharAnimWpnY;
               }
            }
         }
         if(_PlayerState.AddSmokeEffect)
         {
            AddSmokeTrace(2);
         }
      }
      
      private function FireWeapon() : void
      {
         if(_PlayerState.CurrentWeaponCooldown > 0 || _PlayerState.DrawDelay > 0)
         {
            return;
         }
         if(_PlayerState.CurrentRangeWeapon.Ammo > 0)
         {
            _PlayerState.CurrentWeaponCooldown = _PlayerState.CurrentRangeWeapon.Properties.WeaponCooldown;
            _PlayerState.CurrentFireFrame = 1;
            ProgressAFS(true);
         }
         else
         {
            WeaponEmptyRecoil();
         }
      }
      
      private function CheckDeathBounce() : void
      {
         var _loc1_:Boolean = false;
         var _loc2_:Boolean = false;
         var _loc3_:Boolean = false;
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         var _loc6_:Boolean = false;
         _loc1_ = true;
         _loc2_ = true;
         _loc3_ = true;
         if(_lastBounceY + 5 > _this_y)
         {
            _loc3_ = false;
            _loc1_ = false;
            _loc2_ = false;
         }
         else
         {
            _loc1_ = Boolean(DetectEdge(1));
            _loc2_ = Boolean(DetectEdge(-1));
         }
         if(!_loc1_ && !_loc2_)
         {
            _loc6_ = true;
            _loc5_ = 0;
            while(_loc5_ < 6)
            {
               if(HitTestWorldOnly(_this_x,_this_y + _loc5_))
               {
                  _loc6_ = false;
               }
               _loc5_ += 2;
            }
            if(_loc6_)
            {
               _loc5_ = 0;
               while(_loc5_ < 4)
               {
                  if(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x,_this_y + _loc5_,true))
                  {
                     _jumpDownPosYDisable = _this_y + 10;
                     _performJumpDownLevel = true;
                     Fall(false);
                     this.scaleX *= -1;
                     _collision_mc.scaleX = this.scaleX;
                     _PlayerState.LastDirX *= -1;
                     _PlayerState.AirVelocityX = Math.random() * 3 - 1.5;
                     _PlayerState.AirVelocityY = -1.5;
                     return;
                  }
                  _loc5_ += 2;
               }
            }
            return;
         }
         if(!_loc3_)
         {
            return;
         }
         if(_loc1_ && _loc2_)
         {
            if(Math.random() < 0.5)
            {
               _loc1_ = false;
            }
            else
            {
               _loc2_ = false;
            }
         }
         _loc4_ = 0;
         if(_loc1_)
         {
            _loc4_ = 1;
         }
         else if(_loc2_)
         {
            _loc4_ = -1;
         }
         Fall(false);
         this.scaleX *= -1;
         _collision_mc.scaleX = this.scaleX;
         _PlayerState.LastDirX *= -1;
         _PlayerState.AirVelocityX = _loc4_ * 1.5;
         _PlayerState.AirVelocityY = -1.5;
      }
      
      private function FireDown() : void
      {
         if(_game_speed == 0)
         {
            return;
         }
         if(_PlayerState.StuckToRocket)
         {
            return;
         }
         if(_PlayerState.Staggering)
         {
            return;
         }
         if(Boolean(_PlayerState.ControllAble) && !_PlayerState.Jumping)
         {
            if(!_PlayerState.Throwing && !_PlayerState.Aiming)
            {
               if(!_PlayerState.FireDelayActivated)
               {
                  _PlayerState.FireDelayActivated = true;
                  _PlayerState.FireDelayUpdated = false;
                  _PlayerState.FireDelayTimer = setInterval(FireDelay,100);
               }
               else if(_PlayerState.CurrentThrowableWeapon.Ammo > 0)
               {
                  CancelFireDelay();
                  _PlayerState.Aiming = true;
                  _PlayerState.AimMode = 1;
                  _PlayerState.ThrowTimer = _PlayerState.CurrentThrowableWeapon.Properties.ThrowTimer;
                  _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentThrowableWeapon.Properties.AimSound,PosX(),PosY());
               }
               else
               {
                  CancelFireDelay();
               }
            }
         }
         else
         {
            _startAimASAP = true;
         }
      }
      
      private function CollisionHead(param1:Number = 0) : Boolean
      {
         var _loc2_:int = 0;
         if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y - _PlayerState.PlayerHeight + param1,true)) && (Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x - _PlayerState.PlayerEdgeDistance,_this_y - _PlayerState.PlayerHeight + param1,true)) || Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x + _PlayerState.PlayerEdgeDistance,_this_y - _PlayerState.PlayerHeight + param1,true))))
         {
            return true;
         }
         _loc2_ = 4;
         while(_loc2_ <= _PlayerState.PlayerHeight - 2)
         {
            if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x - _PlayerState.PlayerEdgeDistance,_this_y - _loc2_ + param1,true)) && Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y - _loc2_,true)) && Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x + _PlayerState.PlayerEdgeDistance,_this_y - _loc2_ + param1,true)))
            {
               return true;
            }
            _loc2_ += 2;
         }
         return false;
      }
      
      private function BotGoForReset(param1:Boolean = false) : void
      {
         _BotState.ResetTimer += 1;
         if(_BotState.ResetTimer >= 4 || param1)
         {
            _BotState.NextResultNode = null;
            _BotState.TargetPlayer = null;
            _BotState.TargetWeapon = null;
            _BotState.ResetTimer = 0;
            _BotState.RunAwayFromHazards = false;
         }
      }
      
      private function StopFlashEffect() : void
      {
         var _loc1_:Color = null;
         if(_PlayerState.ShowFlashEffect)
         {
            _loc1_ = new Color();
            _loc1_.brightness = 0;
            this.transform.colorTransform = _loc1_;
         }
         _PlayerState.ShowFlashEffect = false;
      }
      
      public function Stop() : void
      {
         CancelFireDelay();
         clearInterval(_flameAwayTimer);
         clearInterval(_downTimer);
         if(_bot)
         {
            clearInterval(_BotState._targetInSightTimer);
            clearInterval(_BotState._targetChooseTimer);
            clearInterval(_BotState._randomizTimer);
            clearInterval(_botTimer);
         }
      }
      
      private function CloudCollisionUp(param1:Number, param2:Number, param3:Boolean) : Boolean
      {
         var _loc4_:b2Body = null;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         if(_static_world_cloud_hitbox_mc.hitTestPoint(param1,param2,param3))
         {
            _loc4_ = m_world.GetRotatedCloudAt(param1,param2);
            if(_loc4_ != null)
            {
               if(_loc4_.GetAngle() != 0)
               {
                  _loc5_ = Number(_PlayerState.AirVelocityX);
                  _loc6_ = Number(_PlayerState.AirVelocityY);
                  if(!_PlayerState.Falling && !_PlayerState.Knockdowned)
                  {
                     _loc5_ = _PlayerState.MovingDirectionX * _PlayerState.RunSpeed;
                  }
                  _loc7_ = Math.cos(-_loc4_.GetAngle());
                  _loc8_ = Math.sin(-_loc4_.GetAngle());
                  _loc9_ = _loc5_ * _loc7_ + _loc6_ * -_loc8_;
                  _loc10_ = _loc5_ * _loc8_ + _loc6_ * _loc7_;
                  _loc11_ = Math.atan2(_loc10_,_loc9_);
                  if(_loc11_ > 0)
                  {
                     return true;
                  }
               }
            }
         }
         return false;
      }
      
      private function ClearLazerPoints() : void
      {
         var _loc1_:int = 0;
         _loc1_ = int(_lazer_mc.numChildren);
         while(Boolean(_loc1_--))
         {
            _lazer_mc.removeChildAt(_loc1_);
         }
      }
      
      private function BotObstacleAt(param1:int) : Boolean
      {
         var _loc2_:b2Body = null;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         _loc3_ = 0;
         while(_loc3_ <= 4)
         {
            _loc4_ = -12;
            while(_loc4_ <= 6)
            {
               _loc2_ = GetDynamicBodyAt(_this_x + param1 * _PlayerState.PlayerEdgeDistance + param1 * _loc3_,MidPosY() + _loc4_,false);
               if(_loc2_ != null)
               {
                  _BotState.PreferJumpOverObstacle = _loc2_.GetUserData().objectData.BotPreferJump;
                  return true;
               }
               _loc4_ += 6;
            }
            _loc3_ += 4;
         }
         return false;
      }
      
      private function BotCheckStandingOnObject() : Boolean
      {
         if(Boolean(BotStandingOnObjectAtX(0)) || Boolean(BotStandingOnObjectAtX(_PlayerState.LastDirX * 6)))
         {
            if(_PlayerState.KickingCooldown <= 0)
            {
               SetBotKey(KEY_MELEE,!_keyPressed[KEY_MELEE]);
            }
            else
            {
               SetBotKey(KEY_MELEE,false);
            }
            return true;
         }
         if(BotStandingOnObjectAtX(-_PlayerState.LastDirX * 6))
         {
            if(_PlayerState.LastDirX == 1)
            {
               SetBotKey(KEY_LEFT,false);
               SetBotKey(KEY_RIGHT,true);
            }
            else
            {
               SetBotKey(KEY_LEFT,true);
               SetBotKey(KEY_RIGHT,false);
            }
            return true;
         }
         return false;
      }
      
      private function BotWalkAroundJumpObstalce() : void
      {
         var _loc1_:int = 0;
         var _loc2_:int = 0;
         _loc1_ = 1;
         _loc2_ = int(_PlayerState.PlayerEdgeDistance);
         while(_loc2_ <= _PlayerState.PlayerEdgeDistance * 5)
         {
            if(BotCanJump(_loc2_))
            {
               _loc1_ = 1;
               _loc2_ = 100;
            }
            else if(BotCanJump(-_loc2_))
            {
               _loc1_ = -1;
               _loc2_ = 100;
            }
            _loc2_ += _PlayerState.PlayerEdgeDistance;
         }
         if(_loc1_ == 1)
         {
            SetBotKey(KEY_RIGHT,true);
            SetBotKey(KEY_LEFT,false);
         }
         else
         {
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_LEFT,true);
         }
         if(BotObstacleAt(_loc1_))
         {
            if(Boolean(_BotState.PreferJumpOverObstacle) && !_PlayerState.Jumping)
            {
               SetBotKey(KEY_UP,true);
               SetBotKey(KEY_UP,false);
            }
            else
            {
               SetBotKey(KEY_MELEE,!_keyPressed[KEY_MELEE]);
            }
         }
      }
      
      private function RangedDown() : void
      {
         if(Boolean(_cancelAimingASAP) || _game_speed == 0 || Boolean(_PlayerState.StuckToRocket) || Boolean(_PlayerState.Staggering))
         {
            return;
         }
         if(Boolean(_PlayerState.ControllAble) && !_PlayerState.Jumping)
         {
            if(!_PlayerState.Throwing && !_PlayerState.Aiming)
            {
               if(_PlayerState.CurrentRangeWeapon != null)
               {
                  _PlayerState.FastTrigger = true;
                  _PlayerState.Aiming = true;
                  _cancelAimingASAP = false;
                  _PlayerState.AimMode = 0;
                  _PlayerState.AimTurningAround = true;
                  _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentRangeWeapon.Properties.AimSound,PosX(),PosY());
                  _PlayerState.DrawDelay = 1;
               }
            }
         }
         else
         {
            _startAimASAP = true;
         }
      }
      
      private function UpdateSimpleGroundMovement(param1:Boolean) : void
      {
         var _loc2_:int = 0;
         if(CollisionFeetMid(0,1))
         {
            if(CollisionFeetMid(-1,1))
            {
               _loc2_ = 0;
               while(Boolean(CollisionFeetMid(-1,1)) && !WorldCollisionHead() && _loc2_ < 100)
               {
                  _this_y -= 0.1;
                  _loc2_ += 1;
               }
               if(_loc2_ > 0)
               {
                  _this_y += 0.1;
               }
            }
            if(param1)
            {
               UpdateDynamicMovement();
            }
         }
         else if(CanLandInMid())
         {
            if(_PlayerState.OnGround)
            {
               while(!CollisionFeetMid())
               {
                  _this_y += 0.1;
               }
               if(param1)
               {
                  UpdateDynamicMovement();
               }
            }
         }
         else if(CollisionFeetSides())
         {
            if(param1)
            {
               UpdateDynamicMovement();
            }
            if(!CollisionFeetSides())
            {
               if(_PlayerState.Staggering)
               {
                  Fall(false);
               }
               else
               {
                  _PlayerState.Jumping = true;
               }
            }
         }
         else
         {
            CheckAimDrop();
            if(_PlayerState.Staggering)
            {
               Fall(false);
            }
            else
            {
               if(_standingOnObject != null)
               {
                  if(Boolean(_standingOnObject.GetUserData().objectData.IsElevator))
                  {
                     UpdateDynamicMovement();
                     return;
                  }
               }
               _PlayerState.Jumping = true;
            }
         }
      }
      
      public function get RemoveFromList() : Boolean
      {
         return Boolean(_PlayerState.CameraIgnoreMe) && Boolean(_PlayerState.Gone);
      }
      
      private function BotAutoPickupItem(param1:b2Body) : Boolean
      {
         if(param1.GetUserData().isRanged == true && _PlayerState.CurrentRangeWeapon == null)
         {
            return true;
         }
         if(param1.GetUserData().isThrowable == true && _PlayerState.CurrentThrowableWeapon == null)
         {
            return true;
         }
         if(param1.GetUserData().isMelee == true && _PlayerState.CurrentMeleeWeapon == null)
         {
            return true;
         }
         if(param1.GetUserData().isPowerup == true && _PlayerState.CurrentPowerupWeapon == null)
         {
            return true;
         }
         if(param1.GetUserData().isHealth == true && _PlayerState.HP < 100)
         {
            return true;
         }
         return false;
      }
      
      public function get CollisionMC() : MovieClip
      {
         return _collision_mc;
      }
      
      private function Jump() : void
      {
         if(!_PlayerState.Aiming)
         {
            if(_PlayerState.Climbing)
            {
               LadderJump();
            }
            else if(!_PlayerState.Jumping)
            {
               BeginJump();
            }
         }
      }
      
      private function UpdateWeaponGrab() : void
      {
         var _loc1_:b2Body = null;
         _loc1_ = GetClosestReachableWeapon();
         if(_loc1_ != null)
         {
            if(_loc1_.GetUserData().isRanged == true && _PlayerState.CurrentRangeWeapon == null)
            {
               _PlayerState.CurrentRangeWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _loc1_.GetUserData().objectData.ForceDestruction();
               _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentRangeWeapon.Properties.PickupSound,PosX(),PosY());
               UpdateGUI();
               return;
            }
            if(_loc1_.GetUserData().isThrowable == true && _PlayerState.CurrentThrowableWeapon.Ammo <= 0)
            {
               _PlayerState.CurrentThrowableWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentThrowableWeapon.Properties.PickupSound,PosX(),PosY());
               _loc1_.GetUserData().objectData.ForceDestruction();
               UpdateGUI();
               return;
            }
            if(_loc1_.GetUserData().isMelee == true && _PlayerState.CurrentMeleeWeapon == null)
            {
               _PlayerState.CurrentMeleeWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _Handler_Sounds.PlaySoundAt(_PlayerState.GetMeleeWeapon().Properties.PickupSound,PosX(),PosY());
               _loc1_.GetUserData().objectData.ForceDestruction();
               UpdateGUI();
               return;
            }
            if(_loc1_.GetUserData().isPowerup == true && _PlayerState.CurrentPowerupWeapon == null)
            {
               _PlayerState.CurrentPowerupWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentPowerupWeapon.Properties.PickupSound,PosX(),PosY());
               _loc1_.GetUserData().objectData.ForceDestruction();
               UpdateGUI();
               return;
            }
            if(_loc1_.GetUserData().isHealth == true && _PlayerState.HP < 100)
            {
               _PlayerState.HP += _loc1_.GetUserData().weaponData.Ammo;
               _Handler_Sounds.PlaySoundAt(_loc1_.GetUserData().weaponData.Properties.PickupSound,PosX(),PosY());
               _loc1_.GetUserData().objectData.ForceDestruction();
               StartFlashEffect();
               return;
            }
            if(_indicationWeapon != _loc1_)
            {
               if(_indicationWeapon != null)
               {
                  _indicationWeapon.GetUserData().objectData.MC.indicator.gotoAndStop(1);
               }
               _indicationWeapon = _loc1_;
               _indicationWeapon.GetUserData().objectData.MC.indicator.gotoAndStop(2);
            }
         }
         else if(_indicationWeapon != null)
         {
            _indicationWeapon.GetUserData().objectData.MC.indicator.gotoAndStop(1);
            _indicationWeapon = null;
         }
      }
      
      private function CheckObjectHeadImpactSpeeds() : void
      {
         var _loc1_:int = 0;
         _loc1_ = -_PlayerState.PlayerEdgeDistance;
         while(_loc1_ <= _PlayerState.PlayerEdgeDistance)
         {
            b = GetDynamicBodyAt(_this_x + _loc1_,_this_y - _PlayerState.PlayerHeight,false);
            if(b != null)
            {
               if(Boolean(b.GetUserData().objectData.CanKnockDownPlayer))
               {
                  if(b.GetLinearVelocity().y + 1 > _PlayerState.AirVelocityY)
                  {
                     _PlayerState.AirVelocityY = b.GetLinearVelocity().y + 1;
                     break;
                  }
               }
            }
            _loc1_ += _PlayerState.PlayerEdgeDistance;
         }
      }
      
      public function EnemiesInMeleeRange() : Array
      {
         var _loc1_:Array = null;
         var _loc2_:* = undefined;
         _loc1_ = new Array();
         _loc2_ = 0;
         while(_loc2_ < _players.length)
         {
            if(_loc2_ != PlayerNr)
            {
               if(Team != _players[_loc2_].Team)
               {
                  if(Boolean(_players[_loc2_].CanBePunched))
                  {
                     if(CheckCollisionTowardsPlayer(_this_x,_players[_loc2_].PosX(),_PlayerState.LastDirX))
                     {
                        if(InMeleeRange(_players[_loc2_]))
                        {
                           _loc1_.push(_loc2_);
                        }
                     }
                  }
               }
            }
            _loc2_++;
         }
         return _loc1_;
      }
      
      public function SetCoordinates(param1:Number, param2:Number, param3:Boolean = false) : void
      {
         _this_x = param1;
         _this_y = param2;
         _PlayerState.PortalDirectionX = 0;
         if(param3)
         {
            _PlayerState.AirVelocityX *= -1;
            _PlayerState.MovingDirectionInversed = _PlayerState.MovingDirectionX;
            _PlayerState.MovingDirectionX *= -1;
            _PlayerState.LastDirX *= -1;
            if(!_PlayerState.StuckToRocket)
            {
               this.scaleX *= -1;
               _collision_mc.scaleX = this.scaleX;
               if(_PlayerState.GrabbedPlayer)
               {
                  _players[_PlayerState.GrabbedPlayerNr].SetCoordinates(_this_x,_this_y,param3);
               }
            }
            else
            {
               _PlayerAnimation.ShowAnimation("ROCKET_RIDE",true);
               _PlayerState.RocketRideProjectile.DirectionX *= -1;
            }
         }
         _collision_mc.x = _this_x;
         _collision_mc.y = _this_y;
         _player_area_mc.x = _this_x;
         _player_area_mc.y = _this_y;
         this.x = _this_x;
         this.y = _this_y;
         if(_PlayerState.StuckToRocket)
         {
            _PlayerState.RocketRideProjectile.PosX = _this_x;
            _PlayerState.RocketRideProjectile.PosY = _this_y;
         }
      }
      
      private function BotStateCancelAim() : void
      {
         var _loc1_:int = 0;
         if(_PlayerState.Aiming)
         {
            SetBotKey(KEY_UP,false);
            SetBotKey(KEY_DOWN,false);
            SetBotKey(KEY_LEFT,false);
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_MELEE,!_keyPressed[KEY_MELEE]);
         }
         else
         {
            SetBotKey(KEY_MELEE,false);
            SetBotKey(KEY_FIRE,false);
            _BotState.CancelAimSoon = false;
            if(_BotState.RunAwayFromHazards)
            {
               _BotState.Phase = BotState.FOLLOW_PATH;
            }
            else if(BotTargetInMelee())
            {
               _BotState.Phase = BotState.MELEE;
            }
            else
            {
               _BotState.Phase = BotState.IDLE;
            }
         }
      }
      
      public function ExplosionHit(param1:Number, param2:Number, param3:Number) : void
      {
         var _loc4_:int = 0;
         if(_PlayerState.IsImmune)
         {
            return;
         }
         _PlayerState.CritSmokeTimer = 48;
         _PlayerState.AirVelocityX += Math.cos(param1) * param2;
         _PlayerState.AirVelocityY += Math.sin(param1) * param2;
         if(_PlayerState.AirVelocityY > -2)
         {
            if(!_PlayerState.Falling)
            {
               _PlayerState.AirVelocityY = -2;
            }
         }
         DropGrabbedPlayer();
         if(_PlayerState.HP > 0)
         {
            _PlayerState.HP -= param3;
            if(_PlayerState.HP <= 0)
            {
               Disarm();
               if(ActivateSlowmotion(PlayerNr))
               {
                  _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
               }
            }
         }
         else if(param3 >= 20)
         {
            GibPlayer();
            return;
         }
         if(param3 <= 10)
         {
            if(_PlayerState.HP > 0)
            {
               StartStagger(ConvertToDirection(-_PlayerState.AirVelocityX));
            }
            else
            {
               _loc4_ = int(EdgeStaggerDistance());
               if(_loc4_ > 6)
               {
                  StartStagger(ConvertToDirection(-_PlayerState.AirVelocityX));
                  _PlayerState.StaggerTimer = _loc4_ - 4;
               }
               else
               {
                  CheckAimDrop();
                  if(!_PlayerState.CantRise)
                  {
                     _PlayerState.Falling = true;
                  }
                  _PlayerAnimation.ShowAnimation("knockdown",true);
               }
            }
         }
         else
         {
            CheckAimDrop();
            if(!_PlayerState.CantRise)
            {
               _PlayerState.Falling = true;
            }
            _PlayerAnimation.ShowAnimation("knockdown",true);
         }
      }
      
      private function BeginJump() : void
      {
         if(Boolean(CheckForceKneeling()) || !_PlayerState.ControllAble || Boolean(CollisionHead(-2)))
         {
            return;
         }
         if(PressingLeft(true))
         {
            this.scaleX = -1;
         }
         if(PressingRight(true))
         {
            this.scaleX = 1;
         }
         _PlayerState.LastDirX = this.scaleX;
         _collision_mc.scaleX = this.scaleX;
         if(_PlayerState.SprintEnergy <= 0)
         {
            _PlayerState.Sprinting = false;
         }
         _Handler_Sounds.PlaySoundAt("JUMP",PosX(),PosY());
         _PlayerAnimation.ShowAnimation("jump",true);
         UpdateDynamicMovement(true);
         _PlayerState.AirVelocityY += _PlayerState.PlayerJumpPower;
         _PlayerState.Jumping = true;
         _PlayerState.JumpPushTimeLeft = _PlayerState.PlayerJumpPushTime;
         _PlayerState.PlayerJumpPushEnabled = true;
         if(_PlayerState.Sprinting)
         {
            DrainEnergy("SPRINT_JUMP");
         }
         else
         {
            DrainEnergy("JUMP");
         }
      }
      
      private function GetStaticCoverAt(param1:Number, param2:Number) : b2Body
      {
         if(_static_world_hitbox_mc.hitTestPoint(param1,param2,true))
         {
            return m_world.GetStaticCoverAt(param1,param2);
         }
         return null;
      }
      
      private function BotCanJump(param1:Number = 0) : Boolean
      {
         var _loc2_:b2Body = null;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         _loc3_ = -_PlayerState.PlayerEdgeDistance;
         while(_loc3_ <= _PlayerState.PlayerEdgeDistance)
         {
            _loc4_ = 0;
            while(_loc4_ <= 20)
            {
               _loc2_ = GetDynamicBodyAt(_this_x + _loc3_ + param1,_this_y - 16 - _loc4_,false);
               if(_loc2_ != null)
               {
                  return false;
               }
               _loc4_ += 4;
            }
            _loc3_ += _PlayerState.PlayerEdgeDistance * 2;
         }
         return true;
      }
      
      private function PressingRight(param1:Boolean = false) : Boolean
      {
         if(_PlayerState.MovingDirectionInversed != 0)
         {
            if(_PlayerState.MovingDirectionInversed == 1)
            {
               return false;
            }
            if(Boolean(_keyPressed[2]))
            {
               return true;
            }
         }
         else if(Boolean(_keyPressed[3]) && (!_keyPressed[2] || !param1))
         {
            return true;
         }
         return false;
      }
      
      private function AddSmokeTrace(param1:Number = 0) : void
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         _smokeDelay -= _game_speed;
         if(_smokeDelay <= 0 || param1 == 0)
         {
            _loc2_ = Math.random() * 10 - 5;
            _loc3_ = Math.random() * 14 - 8;
            _Handler_Effects.AddParticle(new particle_data("SMOKE_TRACE_EFFECT",MidPosX() + _loc2_ * 0.7,MidPosY() + _loc3_ * 0.7,new b2Vec2(),0,1,[1]));
            _smokeDelay = param1;
         }
      }
      
      private function BotStateMelee() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Boolean = false;
         var _loc3_:Number = NaN;
         if(_BotState.TargetPlayer == null)
         {
            BotGoForReset(true);
            _BotState.Phase = BotState.IDLE;
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_LEFT,false);
            SetBotKey(KEY_MELEE,false);
            return;
         }
         _loc1_ = _BotState.TargetPlayer.MidPosX() - MidPosX();
         BotCheckObstacle(_loc1_ / Math.abs(_loc1_),true);
         _loc2_ = Boolean(BotTargetInMelee());
         if(_PlayerState.Climbing)
         {
            SetBotKey(KEY_UP,false);
            SetBotKey(KEY_DOWN,true);
         }
         else
         {
            SetBotKey(KEY_DOWN,false);
            if(Math.abs(_loc1_) >= 40 || Math.abs(_loc1_) < _PlayerState.MeleeWeaponRange && !_loc2_)
            {
               if(Boolean(_BotState.TargetInSight) && _PlayerState.CurrentRangeWeapon != null)
               {
                  _BotState.Phase = BotState.AIM;
               }
               else
               {
                  _BotState.Phase = BotState.FOLLOW_PATH;
               }
               SetBotKey(KEY_RIGHT,false);
               SetBotKey(KEY_LEFT,false);
               SetBotKey(KEY_MELEE,false);
               return;
            }
         }
         if(_PlayerState.CurrentRangeWeapon != null)
         {
            if(Math.abs(_loc1_) >= 8)
            {
               if(_BotState.TargetPlayer.State.Knockdowned)
               {
                  if(Math.random() < _PlayerState.CurrentRangeWeapon.TotalKnockdown / 100 + _BotState.MeleeToAimMinimumChance)
                  {
                     if(_PlayerState.RangeWeaponCanShootDown)
                     {
                        _BotState.ActionShotFired = false;
                     }
                     else
                     {
                        _BotState.ActionShotFired = true;
                     }
                     _BotState.Phase = BotState.AIM;
                  }
               }
            }
         }
         SetBotKey(KEY_RIGHT,false);
         SetBotKey(KEY_LEFT,false);
         if(BotFacingEdgeMelee())
         {
            if(_PlayerState.LastDirX < 0 && _loc1_ > 0)
            {
               SetBotKey(KEY_RIGHT,true);
               SetBotKey(KEY_LEFT,false);
            }
            else if(_PlayerState.LastDirX > 0 && _loc1_ < 0)
            {
               SetBotKey(KEY_RIGHT,false);
               SetBotKey(KEY_LEFT,true);
            }
         }
         else if(_PlayerState.OnGround)
         {
            if(_loc1_ > 6 || _PlayerState.LastDirX < 0 && _loc1_ > 0)
            {
               SetBotKey(KEY_RIGHT,true);
               SetBotKey(KEY_LEFT,false);
            }
            else if(_loc1_ < -6 || _PlayerState.LastDirX > 0 && _loc1_ < 0)
            {
               SetBotKey(KEY_RIGHT,false);
               SetBotKey(KEY_LEFT,true);
            }
         }
         else if(_loc1_ > 0.5)
         {
            SetBotKey(KEY_RIGHT,true);
            SetBotKey(KEY_LEFT,false);
         }
         else if(_loc1_ < -0.5)
         {
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_LEFT,true);
         }
         if(_loc1_ != 0)
         {
            if(_PlayerState.CanRoll)
            {
               if(_BotState.TargetPlayer.State.Aiming)
               {
                  SetBotKey(KEY_DOWN,true);
               }
               else if(_PlayerState.Sprinting)
               {
                  if(Math.random() <= 0.08)
                  {
                     if(!BotFacingEdge())
                     {
                        SetBotKey(KEY_DOWN,true);
                     }
                  }
               }
            }
         }
         if(_loc2_)
         {
            if(!_keyPressed[KEY_MELEE] && Boolean(_PlayerState.OnGround) && Math.random() < 0.1 && _BotState.Difficulty > BotState.EASY)
            {
               SetBotKey(KEY_UP,true);
               SetBotKey(KEY_UP,false);
            }
            else
            {
               if(_BotState.Difficulty == BotState.EASY)
               {
                  if(Math.random() < 0.65 || Boolean(_PlayerState.Jumping))
                  {
                     return;
                  }
               }
               if(_BotState.Difficulty == BotState.MEDIUM)
               {
                  if(Math.random() < 0.55)
                  {
                     return;
                  }
               }
               SetBotKey(KEY_MELEE,!_keyPressed[KEY_MELEE]);
            }
         }
         else if(Math.abs(_loc1_) < 4)
         {
            if(Boolean(_PlayerState.OnGround) && Boolean(_BotState.TargetPlayer.State.OnGround))
            {
               _loc3_ = MidPosY() - _BotState.TargetPlayer.MidPosY();
               if(Math.abs(_loc3_) > 10)
               {
                  _BotState.Phase = BotState.FOLLOW_PATH;
               }
            }
         }
      }
      
      private function KneelPressed() : void
      {
         if(!_PlayerState.Jumping)
         {
            if(_enableJumpDownLevel)
            {
               _enableJumpDownLevel = false;
               clearInterval(_downTimer);
               AbortAiming();
               _jumpDownPosYDisable = _this_y + 10;
               _performJumpDownLevel = true;
               _PlayerState.AirVelocityX = 0;
               _PlayerState.AirVelocityY = 0;
               _PlayerState.Jumping = true;
            }
            else
            {
               if(!_PlayerState.ControllAble || Boolean(_PlayerState.Aiming))
               {
                  return;
               }
               clearInterval(_downTimer);
               _downTimer = setInterval(DisableJumpDownLevel,250);
               _enableJumpDownLevel = true;
            }
         }
      }
      
      public function get State() : PlayerState
      {
         return _PlayerState;
      }
      
      public function get BulletGameSpeed() : Number
      {
         return _bullet_game_speed;
      }
      
      private function BotCheckCover() : void
      {
         if(_PlayerState.TakingCover)
         {
            SetBotKey(KEY_UP,true);
            SetBotKey(KEY_UP,false);
            return;
         }
      }
      
      private function ThrowDown() : void
      {
         if(_game_speed == 0 || Boolean(_PlayerState.StuckToRocket) || Boolean(_PlayerState.Staggering))
         {
            return;
         }
         if(Boolean(_PlayerState.ControllAble) && !_PlayerState.Jumping)
         {
            if(!_PlayerState.Throwing && !_PlayerState.Aiming)
            {
               if(_PlayerState.CurrentThrowableWeapon.Ammo > 0)
               {
                  _PlayerState.Aiming = true;
                  _PlayerState.AimMode = 1;
                  _PlayerState.ThrowTimer = _PlayerState.CurrentThrowableWeapon.Properties.ThrowTimer;
                  _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentThrowableWeapon.Properties.AimSound,PosX(),PosY());
               }
            }
         }
         else
         {
            _startAimASAP = true;
         }
      }
      
      private function Roll() : void
      {
         _Handler_Sounds.PlaySoundAt("ROLL",PosX(),PosY());
         DrainEnergy("ROLL");
         _PlayerState.DecreaseBurnState();
         _PlayerState.Rolling = true;
      }
      
      private function FlameAway() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         if(_PlayerState.Staggering)
         {
            clearInterval(_flameAwayTimer);
            _flameAwayActivated = false;
            _flameAwayCounter = 0;
            return;
         }
         _flameAwayCounter -= _game_speed;
         if(_char.ANIM_WPN == null)
         {
            return;
         }
         if(_flameAwayCounter <= 0)
         {
            _loc1_ = _char.ANIM_WPN.x * _PlayerState.LastDirX + PosX();
            _loc2_ = _char.ANIM_WPN.y + PosY();
            _loc1_ += Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.x;
            _loc2_ += Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.x;
            _loc2_ += Math.sin((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.y * _PlayerState.LastDirX;
            _loc1_ += Math.cos((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.y * _PlayerState.LastDirX;
            _loc3_ = Math.random() * _PlayerState.CurrentRangeWeapon.Properties.AccuracyDeflection * 2 - _PlayerState.CurrentRangeWeapon.Properties.AccuracyDeflection;
            _Handler_Fires.AddFlame(_loc1_,_loc2_,_PlayerState.CurrentAimAngle + _loc3_,PlayerNr);
            _flameAwayCounter = 2;
         }
      }
      
      private function CheckDivePlayerImpact() : void
      {
         var _loc1_:* = undefined;
         if(!_PlayerState.GrabbedPlayer)
         {
            _loc1_ = 0;
            while(_loc1_ < _players.length)
            {
               if(_loc1_ != PlayerNr && !_players[_loc1_].State.IsImmune)
               {
                  if(this.hitTestObject(_players[_loc1_].MC))
                  {
                     if(CheckCollisionTowardsPlayer(PosX(),_players[_loc1_].PosX(),_PlayerState.LastDirX))
                     {
                        if(Math.sqrt((_this_x - _players[_loc1_].MidPosX()) * (_this_x - _players[_loc1_].MidPosX())) <= 8)
                        {
                           if(Math.sqrt((MidPosY() - _players[_loc1_].MidPosY()) * (MidPosY() - _players[_loc1_].MidPosY())) <= 10)
                           {
                              if(Boolean(_players[_loc1_].State.Diving))
                              {
                                 _Handler_Sounds.PlaySoundAt("DIVE_CATCH",PosX(),PosY());
                                 _Handler_Effects.AddEffectAt("DIVE_IMPACT",MidPosX() + _PlayerState.LastDirX * 12,MidPosY() - 4);
                                 _players[_loc1_].DiveCollision();
                                 DiveCollision();
                              }
                              else if(Boolean(_players[_loc1_].CanBeCatched) && !_PlayerState.GrabbedPlayer)
                              {
                                 _Handler_Sounds.PlaySoundAt("DIVE_CATCH",PosX(),PosY());
                                 _Handler_Effects.AddEffectAt("DIVE_IMPACT",MidPosX() + _PlayerState.LastDirX * 12,MidPosY() - 4);
                                 if(this.parent.getChildIndex(this) < _players[_loc1_].parent.getChildIndex(_players[_loc1_]))
                                 {
                                    this.parent.swapChildren(this,_players[_loc1_]);
                                 }
                                 _PlayerState.GrabbedPlayerNr = _loc1_;
                                 _PlayerState.GrabbedPlayerCharNr = _players[_PlayerState.GrabbedPlayerNr].State.CharNr;
                                 _players[_PlayerState.GrabbedPlayerNr].GrabbedByOtherPlayer(true,_PlayerState.LastDirX);
                              }
                           }
                        }
                     }
                  }
               }
               _loc1_++;
            }
         }
      }
      
      public function GrabbedByOtherPlayer(param1:Boolean, param2:int = 0) : void
      {
         if(param2 != 0)
         {
            _PlayerState.LastDirX = -param2;
            this.scaleX = _PlayerState.LastDirX;
            _collision_mc.scaleX = this.scaleX;
         }
         _PlayerState.GrabbedByPlayer = param1;
         if(!param1)
         {
            _PlayerState.AirVelocityY = 0;
            _PlayerState.AirVelocityX = 0;
            _PlayerState.Knockdowned = true;
            _PlayerState.Jumping = true;
            if(_PlayerState.IgnoreMe)
            {
               this.visible = false;
            }
         }
         else
         {
            CheckAimDrop();
            CancelAFS();
            _PlayerAnimation.ShowAnimation("GRABBED");
         }
      }
      
      private function UpdateGroundMovement() : void
      {
         if(CollisionFeetBothSides())
         {
            if(CollisionFeetMid())
            {
               _this_y -= 0.1;
            }
         }
         UpdateSides();
         if(!_PlayerState.Knockdowned && !_PlayerState.Falling)
         {
            if(CheckForceKnockdown())
            {
               Fall();
               _PlayerState.Falling = false;
               _PlayerState.Knockdowned = true;
               _PlayerState.CantRise = true;
               _PlayerAnimation.ShowAnimation("knockdown",true);
               if(CheckGibPlayer())
               {
                  return;
               }
            }
            else if(CheckForceKneeling())
            {
               _PlayerState.Kneeling = true;
            }
         }
         else if(_PlayerState.CantRise)
         {
            if(!CheckForceKnockdown())
            {
               _PlayerState.CantRise = false;
            }
            else if(CheckGibPlayer())
            {
               return;
            }
         }
         else if(CheckForceKnockdown())
         {
            if(CheckForceKnockdown())
            {
               _PlayerState.CantRise = true;
               if(CheckGibPlayer())
               {
                  return;
               }
            }
         }
         UpdateSimpleGroundMovement(true);
      }
      
      public function PosX() : Number
      {
         return this.x;
      }
      
      public function get PortalSpeedX() : Number
      {
         return _PlayerState.PortalSpeedX;
      }
      
      private function CanKickPlayer(param1:Player, param2:Boolean = false) : Boolean
      {
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         if(param1.State.CanBeKicked)
         {
            if(CheckCollisionTowardsPlayer(_this_x,param1.PosX(),_PlayerState.LastDirX))
            {
               _loc3_ = PosX() - param1.PosX();
               if(Math.abs(_loc3_) <= 16)
               {
                  _loc4_ = PosY() - param1.PosY();
                  _loc5_ = -4;
                  _loc6_ = -16;
                  if(param1.State.Knockdowned)
                  {
                     _loc6_ = -8;
                     if(param2)
                     {
                        _loc5_ = 8;
                     }
                     else
                     {
                        _loc5_ = 2;
                     }
                  }
                  else if(param2)
                  {
                     _loc5_ = 16;
                  }
                  if(_loc4_ <= _loc5_ && _loc4_ >= _loc6_)
                  {
                     return true;
                  }
               }
            }
         }
         return false;
      }
      
      public function PosY() : Number
      {
         return this.y;
      }
      
      private function UpdateInversedDirection() : void
      {
         if(_PlayerState.MovingDirectionInversed != 0)
         {
            if(!_keyPressed[3] && _PlayerState.MovingDirectionInversed == 1)
            {
               _PlayerState.MovingDirectionInversed = 0;
            }
            if(!_keyPressed[2] && _PlayerState.MovingDirectionInversed == -1)
            {
               _PlayerState.MovingDirectionInversed = 0;
            }
         }
      }
      
      private function SimpleMove(param1:Number, param2:Number) : void
      {
         var _loc3_:int = 0;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:int = 0;
         _this_x += param1;
         _this_y += param2;
      }
      
      public function get PlayerNr() : int
      {
         return _playerNr;
      }
      
      private function BotTargetThreat_Weapon(param1:Player) : Number
      {
         return param1.State.RangeWeaponTotalDamage / 100;
      }
      
      public function RocketWillHit() : Boolean
      {
         if(_PlayerState.IsImmune)
         {
            return false;
         }
         if(Boolean(_PlayerState.Rolling) || Boolean(_PlayerState.Diving))
         {
            if(Math.random() < 0.5)
            {
               return false;
            }
         }
         return true;
      }
      
      private function CheckCollisionWithBody(param1:Array) : void
      {
         var _loc2_:b2Body = null;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Boolean = false;
         var _loc7_:b2Vec2 = null;
         var _loc8_:b2Vec2 = null;
         var _loc9_:b2Vec2 = null;
         var _loc10_:b2Vec2 = null;
         var _loc11_:b2Vec2 = null;
         var _loc12_:Number = NaN;
         var _loc13_:Number = NaN;
         var _loc14_:Boolean = false;
         var _loc15_:Boolean = false;
         var _loc16_:Number = NaN;
         var _loc17_:Number = NaN;
         var _loc18_:Number = NaN;
         var _loc19_:b2Vec2 = null;
         var _loc20_:int = 0;
         var _loc21_:Number = NaN;
         var _loc22_:Number = NaN;
         var _loc23_:Number = NaN;
         var _loc24_:b2Vec2 = null;
         var _loc25_:Number = NaN;
         _loc2_ = param1[0];
         if(_loc2_.GetLinearVelocity().Length() < 2)
         {
            return;
         }
         _loc3_ = _loc2_.GetLinearVelocity().Length();
         _loc4_ = Number(param1[1]);
         _loc5_ = Number(param1[2]);
         _loc6_ = false;
         _loc7_ = new b2Vec2(_loc4_ / 30,_loc5_ / 30);
         _loc8_ = _loc2_.GetLinearVelocityFromWorldPoint(_loc7_);
         _loc9_ = new b2Vec2(_PlayerState.AirVelocityX,_PlayerState.AirVelocityY);
         _loc10_ = new b2Vec2(_loc8_.x,_loc8_.y);
         _loc11_ = new b2Vec2(_loc9_.x,_loc9_.y);
         _loc12_ = _loc2_.GetMass();
         _loc13_ = Number(_PlayerState.Mass);
         if(_loc5_ < _this_y - 1)
         {
            _loc14_ = Boolean(CheckCollisionTowardsPlayer(_loc4_,MidPosX(),ConvertToDirection(_loc8_.x)));
            _loc15_ = Boolean(CheckCollisionTowardsPlayer(_loc5_,MidPosY(),ConvertToDirection(_loc8_.y)));
            if(_loc14_ && _loc15_)
            {
               _loc10_.y = (_loc8_.y * (_loc12_ - _loc13_) + 2 * _loc13_ * _loc9_.y) / (_loc12_ + _loc13_);
               _loc11_.y = (_loc9_.y * (_loc13_ - _loc12_) + 2 * _loc12_ * _loc8_.y) / (_loc12_ + _loc13_);
               if(Boolean(_PlayerState.OnGround) && !_PlayerState.Knockdowned)
               {
                  if(_loc2_.GetUserData().objectData.CrushDamage > 0)
                  {
                     if((_loc14_ || _loc8_.x == 0) && _loc15_)
                     {
                        _PlayerState.HP -= _loc2_.GetUserData().objectData.CrushDamage;
                        _loc10_.y = -2;
                        _loc6_ = true;
                        if(_PlayerState.HP <= 0)
                        {
                           Fall(false);
                        }
                     }
                  }
                  else
                  {
                     _loc6_ = true;
                  }
                  if(_loc10_.x > -1 && _loc10_.x < 1)
                  {
                     _loc10_.x = ConvertToDirection(_loc10_.x);
                     if(_loc10_.x == 0)
                     {
                        _loc10_.x = ConvertToDirection(_loc4_ - MidPosX());
                     }
                  }
               }
               else if(!_loc2_.GetUserData().objectData.CanGibb)
               {
                  _loc6_ = true;
               }
            }
         }
         else if(_loc14_ || _loc15_)
         {
            if(Boolean(_PlayerState.OnGround) && !_PlayerState.Knockdowned)
            {
               if(_loc2_.GetUserData().objectData.CrushDamage > 0)
               {
                  if((_loc14_ || _loc8_.x == 0) && _loc15_)
                  {
                     _loc11_.y = (_loc9_.y * (_loc13_ - _loc12_) + 2 * _loc12_ * _loc8_.y) / (_loc12_ + _loc13_);
                     _PlayerState.HP -= _loc2_.GetUserData().objectData.CrushDamage;
                     _loc10_.y = -2;
                     _loc6_ = true;
                     if(_PlayerState.HP <= 0)
                     {
                        Fall(false);
                     }
                  }
               }
            }
         }
         if(_loc6_)
         {
            if(!_loc2_.GetUserData().objectData.CanGibb)
            {
               _loc20_ = 0;
               _loc21_ = _loc2_.m_linearVelocity.x / _loc2_.m_linearVelocity.Length() / 30;
               _loc22_ = _loc2_.m_linearVelocity.y / _loc2_.m_linearVelocity.Length() / 30;
               while(_loc20_ < 0 && Boolean(_loc2_.m_userData.objectData.CollisionMC.hitTestPoint(_loc4_,_loc5_,true)))
               {
                  _loc2_.SetXForm(new b2Vec2(_loc2_.GetPosition().x - _loc21_,_loc2_.GetPosition().y - _loc22_),_loc2_.GetAngle());
                  _loc2_.m_userData.objectData.ShapeMC.x = _loc2_.GetPosition().x * 30;
                  _loc2_.m_userData.objectData.ShapeMC.y = _loc2_.GetPosition().y * 30;
                  _loc2_.m_userData.objectData.ShapeMC.rotation = _loc2_.GetAngle() * (180 / Math.PI);
                  _loc2_.m_userData.objectData.CollisionMC.x = _loc2_.m_userData.objectData.ShapeMC.x;
                  _loc2_.m_userData.objectData.CollisionMC.y = _loc2_.m_userData.objectData.ShapeMC.y;
                  _loc2_.m_userData.objectData.CollisionMC.rotation = _loc2_.m_userData.objectData.ShapeMC.rotation;
                  _loc20_ += 1;
               }
            }
            UpdateSides();
            _loc2_.SetLinearVelocity(_loc10_);
            _loc16_ = _loc4_ - MidPosX();
            _loc17_ = _loc5_ - MidPosY();
            _loc18_ = Math.atan2(_loc17_,_loc16_);
            _loc19_ = new b2Vec2(Math.cos(_loc18_) * 2,Math.sin(_loc18_) * 4);
            if(Boolean(_loc2_.GetUserData().objectData.CanGibb))
            {
               _loc19_ = new b2Vec2(Math.cos(_loc18_) * 0.5,Math.sin(_loc18_) * 1);
            }
            _loc2_.ApplyImpulse(_loc19_,_loc7_);
            _Handler_Sounds.PlaySoundAt("MELEE_HIT",_this_x,_this_y);
            _PlayerState.AirVelocityX = _loc11_.x;
            _PlayerState.AirVelocityY = _loc11_.y;
            if(_PlayerState.AirVelocityY > -2)
            {
               _PlayerState.AirVelocityY = -2;
            }
            if(_loc4_ < MidPosX())
            {
               if(_loc2_.GetLinearVelocity().x > _PlayerState.AirVelocityX)
               {
                  _PlayerState.AirVelocityX = _loc2_.GetLinearVelocity().x + 1;
               }
            }
            else if(_loc2_.GetLinearVelocity().x < _PlayerState.AirVelocityX)
            {
               _PlayerState.AirVelocityX = _loc2_.GetLinearVelocity().x - 1;
            }
            _this_y -= 0.5;
            Fall();
            _loc2_.GetUserData().objectData.Damage_Impact(5);
            if(_loc2_.GetLinearVelocity().Length() > _loc3_)
            {
               _loc23_ = _loc3_ / _loc2_.GetLinearVelocity().Length();
               _loc24_ = _loc2_.GetLinearVelocity();
               _loc24_.x *= _loc23_ * 0.8;
               _loc24_.y *= _loc23_ * 0.8;
               _loc2_.SetLinearVelocity(_loc24_);
            }
            if(_PlayerState.TotalAirVelocity > _loc3_)
            {
               _loc25_ = _loc3_ / _PlayerState.TotalAirVelocity;
               _PlayerState.AirVelocityX *= _loc25_;
               _PlayerState.AirVelocityY *= _loc25_;
            }
         }
      }
      
      private function FireDelay() : void
      {
         CancelFireDelay();
         if(KeyPressed(5))
         {
            if(_PlayerState.CurrentRangeWeapon != null)
            {
               if(Boolean(_PlayerState.ControllAble) && !_PlayerState.Jumping)
               {
                  _PlayerState.Aiming = true;
                  _cancelAimingASAP = false;
                  _PlayerState.AimMode = 0;
                  _PlayerState.AimTurningAround = true;
                  _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentRangeWeapon.Properties.AimSound,PosX(),PosY());
                  _PlayerState.DrawDelay = 1;
               }
            }
         }
      }
      
      private function KeyPressed(param1:int) : Boolean
      {
         if(_bot)
         {
            return _keyPressed[param1];
         }
         return _Handler_Keyboard.KeyIsDown(_keys[param1]);
      }
      
      private function UpPressed() : void
      {
         if(_PlayerState.ControllAble)
         {
            if(_PlayerState.Aiming)
            {
               if(!_PlayerState.AimTurningAroundDelay)
               {
                  AimUp(0.5);
               }
            }
         }
      }
      
      public function Update(param1:Number) : void
      {
         if(_slowmotion_timer > 0)
         {
            _slowmotion_timer -= 1;
            _game_speed = param1 * _slowmotion_modifier;
            _bullet_game_speed = param1 * _slowmotion_modifier * 0.75;
            if(_game_speed > 1)
            {
               _game_speed = 1;
            }
            if(_bullet_game_speed > 1)
            {
               _bullet_game_speed = 1;
            }
         }
         else
         {
            _game_speed = param1;
            _bullet_game_speed = param1;
            if(param1 < 1)
            {
               _bullet_game_speed *= 0.5;
            }
         }
         if(_PlayerState.HP <= 0 && !_deathScreamDone)
         {
            if(Math.random() < 0.02)
            {
               _Handler_Sounds.PlaySoundAt("WILHELM",PosX(),PosY());
            }
            _deathScreamDone = true;
         }
         if(_PlayerState.IgnoreMe)
         {
            _PlayerState.UpdateCameraIgnoreTimer();
            return;
         }
         if(RemoveFromList)
         {
            return;
         }
         if(!_bot)
         {
            UpdateEventPC();
         }
         if(_game_speed != 0)
         {
            if(!_PlayerState.Gone)
            {
               MainUpdate();
               _PlayerState.Update(_game_speed);
               _char_gui.scaleX = this.scaleX;
               _blood_gui.scaleX = this.scaleX;
            }
         }
         _PlayerAnimation.ProgressAnimation(_game_speed);
         _PlayerBars.Update(this.x,this.y,_dynamic_mc.scaleX);
      }
      
      public function FireContact(param1:Boolean = false, param2:Number = 1) : void
      {
         var _loc3_:MovieClip = null;
         if(_PlayerState.IsImmune)
         {
            return;
         }
         if(_PlayerState.StuckToRocket)
         {
            return;
         }
         _PlayerState.BurnState += _game_speed * param2;
         if(param1 && _PlayerState.BurnState < 100)
         {
            _PlayerState.InWorldFire = true;
         }
         if(_PlayerState.BurnState < _PlayerState.FireRank1Minimum)
         {
            return;
         }
         if(_PlayerState.HP <= 0)
         {
            if(!_PlayerState.Burned)
            {
               DropGrabbedPlayer();
               StopFlashEffect();
               this.removeChild(_char);
               _char = new player_burnt();
               this.addChild(_char);
               _PlayerAnimation.NewSkin(_char);
               _loc3_ = MovieClip(_char_gui.parent);
               _loc3_.removeChild(_char_gui);
               _char_gui = new player_burnt();
               _loc3_.addChild(_char_gui);
               _PlayerAnimation.SetGUISkin(_char_gui,_blood_gui);
               _Handler_Effects.AddEffectAt("PLAYER_BURNED",MidPosX(),MidPosY());
               _PlayerState.BurnState = 100;
               _PlayerState.Burned = true;
               if(!_PlayerState.Knockdowned && !_PlayerState.DeathKneel && !_PlayerState.Staggering)
               {
                  if((Boolean(DetectEdge(_PlayerState.LastDirX)) || Math.random() < 0.5) && Boolean(_PlayerState.OnGround))
                  {
                     if(_PlayerState.Sprinting)
                     {
                        Fall(false);
                     }
                     else
                     {
                        _PlayerState.DeathKneel = true;
                        _PlayerState.CameraIgnoreTimer = 3 * 24;
                     }
                  }
                  else
                  {
                     Fall(false);
                  }
                  _Handler_Shake.Add(2,2);
               }
            }
            return;
         }
         if(param1)
         {
            _PlayerState.HP -= _PlayerState.FireRankWorldExtraDamage * _game_speed * param2;
         }
         if(_PlayerState.BurnState >= _PlayerState.FireRank2Minimum)
         {
            _PlayerState.HP -= _PlayerState.FireRank2Damage * _game_speed * param2;
         }
         else
         {
            _PlayerState.HP -= _PlayerState.FireRank1Damage * _game_speed * param2;
         }
         if(_PlayerState.HP <= 0)
         {
            _PlayerState.AirVelocityY -= 1;
            Disarm();
            Fall(true);
            if(ActivateSlowmotion(PlayerNr))
            {
               _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
            }
         }
      }
      
      private function CheckCollisionHeight(param1:Number, param2:Number) : Boolean
      {
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         var _loc5_:b2Body = null;
         var _loc6_:b2Vec2 = null;
         var _loc7_:int = 0;
         _headColl = false;
         _sideColl = false;
         _loc3_ = param2;
         while(_loc3_ >= param1)
         {
            if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y - _loc3_,true)) && (Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x - _PlayerState.PlayerEdgeDistance,_this_y - _loc3_,true)) || Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x + _PlayerState.PlayerEdgeDistance,_this_y - _loc3_,true))))
            {
               _headColl = true;
               break;
            }
            _loc3_ -= 2;
         }
         if(!_headColl)
         {
            _loc4_ = -_PlayerState.PlayerEdgeDistance;
            while(_loc4_ <= _PlayerState.PlayerEdgeDistance)
            {
               _loc5_ = GetDynamicBodyAt(_this_x + _loc4_,_this_y - param2,false);
               if(_loc5_ != null)
               {
                  if(Boolean(_loc5_.GetUserData().objectData.CanGibb))
                  {
                     _loc6_ = _loc5_.GetLinearVelocity();
                     if(Math.abs(_loc6_.x) > 0.01)
                     {
                        if(CheckCollisionTowardsPlayer(_this_x + _loc4_,_this_x,ConvertToDirection(_loc6_.x)))
                        {
                           _headColl = true;
                           _sideColl = true;
                           break;
                        }
                     }
                  }
               }
               _loc4_ += _PlayerState.PlayerEdgeDistance * 2;
            }
         }
         if(!_sideColl)
         {
            _edgePositionL = _this_x - _PlayerState.PlayerEdgeDistance;
            _edgePositionR = _this_x + _PlayerState.PlayerEdgeDistance;
            _loc7_ = param2;
            while(_loc7_ >= param1)
            {
               if(Boolean(_static_world_hitbox_mc.hitTestPoint(_edgePositionL,_this_y - _loc7_,true)) || Boolean(_static_world_hitbox_mc.hitTestPoint(_edgePositionR,_this_y - _loc7_,true)))
               {
                  _sideColl = true;
                  break;
               }
               _loc7_ -= 2;
            }
         }
         if(Boolean(_headColl) && Boolean(_sideColl))
         {
            return true;
         }
         return false;
      }
      
      private function UpdateEventPC() : void
      {
         var _loc1_:* = undefined;
         if(!_activated)
         {
            return;
         }
         _loc1_ = 0;
         while(_loc1_ < _keys.length)
         {
            if(_Handler_Keyboard.KeyIsDown(_keys[_loc1_]))
            {
               _keyPressed[_loc1_] = true;
            }
            else
            {
               _keyPressed[_loc1_] = false;
            }
            _loc1_++;
         }
      }
      
      private function UpdateFlashEffect() : void
      {
         var _loc1_:Color = null;
         _loc1_ = new Color();
         _loc1_.brightness = _PlayerState.FlashEffectTimer / 8 * 1;
         this.transform.colorTransform = _loc1_;
      }
      
      private function UpdateGUIRanged() : void
      {
         if(_PlayerState.CurrentRangeWeapon == null)
         {
            _gui_mc.ranged.gotoAndStop("EMPTY");
            _gui_mc.ranged_num.visible = false;
         }
         else
         {
            _gui_mc.ranged.gotoAndStop(_PlayerState.CurrentRangeWeapon.Properties.WeaponType);
            _gui_mc.ranged_num.visible = true;
            if(_PlayerState.CurrentRangeWeapon.Properties.WeaponType == "SHOTGUN")
            {
               SetNumTo(_gui_mc.ranged_num,_PlayerState.CurrentRangeWeapon.Ammo / 4);
            }
            else
            {
               SetNumTo(_gui_mc.ranged_num,_PlayerState.CurrentRangeWeapon.Ammo);
            }
         }
      }
      
      private function CheckHeadToObjectImpacts(param1:Number) : void
      {
         var _loc2_:int = 0;
         var _loc3_:b2Vec2 = null;
         _loc2_ = -_PlayerState.PlayerEdgeDistance;
         while(_loc2_ <= _PlayerState.PlayerEdgeDistance)
         {
            b = GetDynamicBodyAt(_this_x + _loc2_,_this_y - _PlayerState.PlayerHeight - 2,false);
            if(b != null)
            {
               _loc3_ = new b2Vec2((_this_x + _loc2_) / 30,(_this_y - _PlayerState.PlayerHeight - 2) / 30);
               b.ApplyImpulse(new b2Vec2(0,-param1),_loc3_);
            }
            _loc2_ += _PlayerState.PlayerEdgeDistance;
         }
      }
      
      private function DownPressed() : void
      {
         if(_PlayerState.ControllAble)
         {
            if(_PlayerState.Aiming)
            {
               if(!_PlayerState.AimTurningAroundDelay)
               {
                  AimDown(0.5);
               }
            }
         }
      }
      
      private function GetClosestReachableWeapon() : b2Body
      {
         var _loc1_:b2Body = null;
         var _loc2_:Number = NaN;
         var _loc3_:int = 0;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         _loc1_ = null;
         _loc3_ = 0;
         while(_loc3_ < m_world.WeaponList.length)
         {
            b = m_world.WeaponList[_loc3_];
            if(b.GetUserData().weaponData.Ammo > 0)
            {
               _loc4_ = MidPosX() - b.GetPosition().x * 30;
               if(Math.sqrt(_loc4_ * _loc4_) <= b.GetUserData().weaponData.Properties.PickupRadius)
               {
                  _loc5_ = MidPosY() + 4 - b.GetPosition().y * 30;
                  if(Math.sqrt(_loc5_ * _loc5_) <= 10)
                  {
                     if(_loc1_ != null)
                     {
                        if(Math.sqrt(_loc4_ * _loc4_ + _loc5_ * _loc5_) < _loc2_)
                        {
                           _loc1_ = b;
                           _loc2_ = Math.sqrt(_loc4_ * _loc4_ + _loc5_ * _loc5_);
                        }
                     }
                     else
                     {
                        _loc1_ = b;
                        _loc2_ = Math.sqrt(_loc4_ * _loc4_ + _loc5_ * _loc5_);
                     }
                  }
               }
            }
            _loc3_++;
         }
         return _loc1_;
      }
      
      public function StartStagger(param1:int = 0) : void
      {
         if(_PlayerState.Aiming)
         {
            if(_PlayerState.AimMode == 1)
            {
               DropThrowable();
            }
         }
         _PlayerState.CurrentFireFrame = 0;
         _PlayerState.LastFireFrame = 0;
         if(param1 != 0)
         {
            _PlayerState.LastDirX = param1;
         }
         this.scaleX = _PlayerState.LastDirX;
         _collision_mc.scaleX = this.scaleX;
         if(Boolean(_PlayerState.OnGround) && Boolean(CanStagger()))
         {
            _PlayerState.Staggering = true;
            if(_PlayerState.StaggerTimer < 6)
            {
               _PlayerState.StaggerTimer = 6 + Math.random() * 8;
            }
         }
         else
         {
            Fall(false);
         }
      }
      
      private function ActivateSprint() : void
      {
         if(_PlayerState.SprintEnergy > 0)
         {
            _Handler_Output.Trace("Sprint On");
            _PlayerState.Sprinting = true;
         }
      }
      
      private function Punch(param1:Boolean = false) : void
      {
         _PlayerState.Punching = true;
         _PlayerAnimation.ShowAnimation(_PlayerState.MeleeAnimation + "_0" + _PlayerState.PunchComboNr,true);
      }
      
      public function Activate() : void
      {
         _activated = true;
         if(_bot)
         {
            _botTimer = setInterval(function():*
            {
               clearInterval(_botTimer);
               _BotState._targetChooseTimer = setInterval(BotChooseTarget_Tick,200);
               _botTimer = setInterval(function():*
               {
                  clearInterval(_botTimer);
                  _botTimer = setInterval(UpdateEventNPC,1000 / 24);
                  _BotState._targetInSightTimer = setInterval(BotInSightCheck_Tick,300);
                  _BotState._randomizTimer = setInterval(BotRandomize,4000);
               },25);
            },10 + PlayerNr * 3 % 20);
         }
         else
         {
            _Handler_Keyboard.AddHandler(_keys[KEY_POWERUP],UsePowerup);
            _Handler_Keyboard.AddHandler(_keys[KEY_THROW],ThrowDown,ThrowUp);
            _Handler_Keyboard.AddHandler(_keys[KEY_FIRE],RangedDown,RangedUp);
            _Handler_Keyboard.AddHandler(_keys[KEY_MELEE],Melee);
            _Handler_Keyboard.AddHandler(_keys[KEY_JUMP],Jump);
            _Handler_Keyboard.AddHandler(_keys[KEY_KNEEL],KneelPressed,KneelReleased);
            _Handler_Keyboard.AddHandler(_keys[KEY_SPRINT],ActivateSprint,DeactivateSprint);
            _Handler_Keyboard.AddHandler(_keys[KEY_UP],UpPressed);
            _Handler_Keyboard.AddHandler(_keys[KEY_DOWN],DownPressed);
         }
      }
      
      public function SetControls(param1:InputKeyboard, param2:Array) : void
      {
         _Handler_Keyboard = param1;
         _keys = param2;
         _Handler_Output.Trace("Controls set to: " + _keys);
      }
      
      private function ReleaseThrowable() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:b2Body = null;
         _loc1_ = (MidPosX() - _PlayerState.LastDirX * 4.5) / 30;
         _loc2_ = (MidPosY() - 7.5) / 30;
         _loc3_ = _PlayerState.CurrentAimAngle * (Math.PI / 180);
         _loc4_ = Math.cos(_loc3_) * 5.5;
         _loc5_ = Math.sin(_loc3_) * 5.5 - 2;
         _loc6_ = _Handler_Maps.Handler_WorldItems.AddPolygon(_PlayerState.CurrentThrowableWeapon.Properties.ThrowType + "_thrown",_loc1_,_loc2_,0,new b2Vec2(_loc4_,_loc5_),_PlayerState.LastDirX * 10,new Array(_PlayerState.ThrowTimer,PlayerNr));
         _loc6_.SetBullet(true);
         _loc6_.GetUserData().objectData.IgnoreCoverID = _PlayerState.CoverObjectID;
         _PlayerState.ThrowTimer = 0;
         _PlayerState.CurrentThrowableWeapon.Ammo -= 1;
         UpdateGUI();
      }
      
      public function SetSign(param1:int) : void
      {
         _PlayerBars.SetSign(param1);
      }
      
      public function get CanBeCatched() : Boolean
      {
         if(_PlayerState.IsImmune)
         {
            return false;
         }
         if(_PlayerState.StuckToRocket)
         {
            return false;
         }
         if(_PlayerState.Knockdowned)
         {
            if(_PlayerAnimation.CurrentFrame < 10)
            {
               return false;
            }
         }
         if(_PlayerState.GrabbedPlayer)
         {
            return false;
         }
         if(_PlayerState.Gone)
         {
            return false;
         }
         return !_PlayerState.GrabbedByPlayer;
      }
      
      public function UpdatePositionToProjectile() : void
      {
         _this_x = _PlayerState.RocketRideProjectile.PosX;
         _this_y = _PlayerState.RocketRideProjectile.PosY;
         this.x = _this_x;
         this.y = _this_y;
         _collision_mc.x = _this_x;
         _collision_mc.y = _this_y;
         _player_area_mc.x = _this_x;
         _player_area_mc.y = _this_y;
      }
      
      private function BackToOldPosition() : void
      {
         _this_x = _old_this_x;
         _this_y = _old_this_y;
      }
      
      private function HitTestWorldOnly(param1:Number, param2:Number) : Boolean
      {
         if(_static_world_hitbox_mc.hitTestPoint(param1,param2,true))
         {
            if(!_static_objects_hitbox_mc.hitTestPoint(param1,param2,true))
            {
               return true;
            }
         }
         return false;
      }
      
      private function Walljump() : void
      {
         var _loc1_:* = undefined;
         var _loc2_:int = 0;
         var _loc3_:b2Vec2 = null;
         _edgePosition = _this_x + _PlayerState.PlayerEdgeDistance * _PlayerState.LastDirX;
         _loc1_ = 0;
         while(_loc1_ < m_world.DynamicHitBoxObjectList.length)
         {
            b = m_world.DynamicHitBoxObjectList[_loc1_];
            _loc2_ = 0;
            while(_loc2_ <= 8)
            {
               if(Boolean(b.GetUserData().objectData.CollisionMC.hitTestPoint(_edgePosition,_this_y - _loc2_,true)))
               {
                  _loc3_ = new b2Vec2((_this_x + _PlayerState.PlayerEdgeDistance * _PlayerState.LastDirX) / 30,_this_y / 30);
                  b.ApplyImpulse(new b2Vec2(_PlayerState.LastDirX,0),_loc3_);
                  break;
               }
               _loc2_ += 2;
            }
            _loc1_++;
         }
         this.scaleX *= -1;
         _collision_mc.scaleX = this.scaleX;
         _PlayerState.LastDirX *= -1;
         _PlayerState.MovingDirectionX = _PlayerState.LastDirX;
         _PlayerState.Sprinting = false;
         _PlayerState.WallJumping = true;
         _PlayerState.AirVelocityY = _PlayerState.PlayerWallJumpPower;
         _PlayerAnimation.ShowAnimation("jump",true);
         _Handler_Effects.AddParticle(new particle_data("DUST",_this_x - _PlayerState.LastDirX * 5,_this_y,new b2Vec2(_PlayerState.LastDirX,1)));
      }
      
      private function BotTargetThreat_Weakness(param1:Player) : Number
      {
         return (100 - param1.State.HP) / 100;
      }
      
      public function PunchReady() : Boolean
      {
         if(_PlayerState.Punching)
         {
            if(!_PlayerState.PunchHitPerformed)
            {
               if(_PlayerAnimation.NextFrame(_game_speed) == _PlayerState.HitPunchComboFrame)
               {
                  return true;
               }
            }
         }
         return false;
      }
      
      private function BotInSightCheck_Tick() : void
      {
         if(_BotState.TargetPlayer != null)
         {
            _BotState.TargetInSight = BotPositionInSight(_BotState.TargetPlayer.MidPosX() + Math.random() * 6 - 3,_BotState.TargetPlayer.MidPosY() + Math.random() * 4 - 2,_BotState.TargetPlayer.PlayerNr);
         }
      }
      
      public function set PlayerNr(param1:int) : void
      {
         _playerNr = param1;
      }
      
      private function UpdateObjectImpacts() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Boolean = false;
         var _loc3_:MovieClip = null;
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         var _loc6_:b2Vec2 = null;
         var _loc7_:b2Vec2 = null;
         var _loc8_:int = 0;
         if(_PlayerState.Knockdowned)
         {
            if(_PlayerState.HP > 0)
            {
               if(_PlayerState.OnGround)
               {
                  b = GetDynamicBodyAt(MidPosX(),MidPosY() - 4,false);
                  if(b == null)
                  {
                     b = GetDynamicBodyAt(MidPosX(),MidPosY() - 8,false);
                  }
                  if(b == null)
                  {
                     b = GetDynamicBodyAt(MidPosX(),MidPosY() - 12,false);
                  }
                  if(b != null)
                  {
                     if(b.GetLinearVelocity().Length() < 0.5)
                     {
                        if(b.GetUserData().objectData.CanGibb && b.IsSleeping() || !b.GetUserData().objectData.CanGibb)
                        {
                           _loc6_ = new b2Vec2(_PlayerState.LastDirX * b.GetMass(),-b.GetMass());
                           _loc7_ = new b2Vec2(MidPosX(),MidPosY() - 8);
                           _loc7_.x /= 30;
                           _loc7_.y /= 30;
                           b.ApplyImpulse(_loc6_,_loc7_);
                           b.GetUserData().objectData.Damage_Impact(1);
                        }
                     }
                  }
               }
            }
            return;
         }
         objectImpactList = new Array();
         _loc1_ = 0;
         while(_loc1_ < m_world.DynamicHitBoxObjectList.length)
         {
            b = m_world.DynamicHitBoxObjectList[_loc1_];
            if(_standingOnObject != b)
            {
               if(Boolean(b.GetUserData().objectData.CanKnockDownPlayer))
               {
                  if(Boolean(b.GetUserData().objectData.CollisionMC.hitTestObject(CollisionMC)))
                  {
                     objectImpactList.push([b,0,0]);
                  }
               }
            }
            _loc1_++;
         }
         if(objectImpactList.length <= 0)
         {
            return;
         }
         _loc4_ = 0;
         while(_loc4_ < objectImpactList.length)
         {
            _loc2_ = false;
            _loc3_ = objectImpactList[_loc4_][0].GetUserData().objectData.CollisionMC;
            _loc8_ = 0;
            while(_loc8_ <= _PlayerState.PlayerHeight)
            {
               if(_loc3_.hitTestPoint(_this_x - 5,_this_y - _loc8_,true))
               {
                  _loc2_ = true;
                  objectImpactList[_loc4_][1] = _this_x - 4;
                  objectImpactList[_loc4_][2] = _this_y - _loc8_;
                  break;
               }
               if(_loc3_.hitTestPoint(_this_x + 5,_this_y - _loc8_,true))
               {
                  _loc2_ = true;
                  objectImpactList[_loc4_][1] = _this_x + 4;
                  objectImpactList[_loc4_][2] = _this_y - _loc8_;
                  break;
               }
               _loc8_ += 2;
            }
            if(!_loc2_)
            {
               if(_loc3_.hitTestPoint(_this_x,_this_y,true))
               {
                  objectImpactList[_loc4_][1] = _this_x;
                  objectImpactList[_loc4_][2] = _this_y;
               }
               else if(_loc3_.hitTestPoint(_this_x,_this_y - _PlayerState.PlayerHeight,true))
               {
                  objectImpactList[_loc4_][1] = _this_x;
                  objectImpactList[_loc4_][2] = _this_y - _PlayerState.PlayerHeight;
               }
               else
               {
                  objectImpactList.splice(_loc4_,1);
               }
            }
            _loc4_++;
         }
         if(objectImpactList.length <= 0)
         {
            return;
         }
         _loc5_ = 0;
         while(_loc5_ < objectImpactList.length)
         {
            CheckCollisionWithBody(objectImpactList[_loc5_]);
            _loc5_++;
         }
      }
      
      public function CanBeKnockedByFlyingPlayer() : Boolean
      {
         if(_PlayerState.IsImmune)
         {
            return false;
         }
         if(_PlayerState.Falling)
         {
            return false;
         }
         if(_PlayerState.Knockdowned)
         {
            if(_PlayerAnimation.CurrentFrame >= 10)
            {
               return true;
            }
            return false;
         }
         return true;
      }
      
      private function BotCheckObstacle(param1:int, param2:Boolean = false) : void
      {
         if(BotObstacleAt(param1))
         {
            if(!_PlayerState.Jumping)
            {
               SetBotKey(KEY_UP,true);
               SetBotKey(KEY_UP,false);
            }
            else if(!_PlayerState.JumpKickPerformed && (Math.abs(_PlayerState.AirVelocityY) < 2 || param2))
            {
               SetBotKey(KEY_MELEE,!_keyPressed[KEY_MELEE]);
            }
         }
      }
      
      private function WorldCollisionSide(param1:Number, param2:Number = -1) : Boolean
      {
         var _loc3_:int = 0;
         if(param2 < 0)
         {
            param2 = Number(_PlayerState.PlayerEdgeDistance);
         }
         _edgePosition = _this_x + param2 * ConvertToDirection(param1);
         _loc3_ = 4;
         while(_loc3_ <= _PlayerState.PlayerHeight - 2)
         {
            if(HitTestWorldOnly(_edgePosition,_this_y - _loc3_))
            {
               return true;
            }
            _loc3_ += 2;
         }
         return false;
      }
      
      public function LadderKnockdown(param1:int) : *
      {
         if(param1 == 0)
         {
            if(Math.random() * 10 < 5)
            {
               param1 = 1;
            }
            else
            {
               param1 = -1;
            }
         }
         _PlayerState.AirVelocityX = param1;
         _PlayerState.AirVelocityY = -1;
         Fall();
      }
      
      public function SetDirection(param1:int) : void
      {
         this.scaleX = param1;
         _collision_mc.scaleX = this.scaleX;
         _PlayerState.LastDirX = param1;
      }
      
      private function Melee() : void
      {
         if(_game_speed == 0)
         {
            return;
         }
         if(_PlayerState.AFSInProgress)
         {
            _cancelAimingASAP = true;
            return;
         }
         if(_PlayerState.Aiming)
         {
            AbortAiming();
            return;
         }
         if(_PlayerState.CanGrabWeapon)
         {
            if(KeyPressed(KEY_KNEEL))
            {
               if(GrabWeapon())
               {
                  UpdateGUI();
                  return;
               }
            }
         }
         if(Boolean(_PlayerState.ControllAble) && !_PlayerState.Jumping)
         {
            _button_in_melee_range = false;
            if(EnemiesInMeleeRange().length > 0)
            {
               Punch(true);
            }
            else if(ButtonInMeleeRange())
            {
               Punch();
            }
            else if(!Kick())
            {
               Punch();
            }
         }
         else if(_PlayerState.ControllAble)
         {
            _PlayerState.QueueJumpKick = true;
         }
         else if(_PlayerState.Punching)
         {
            if(_PlayerAnimation.CurrentFrame >= _PlayerState.MinPunchComboFrame)
            {
               if(_PlayerState.PunchComboNr < 3)
               {
                  _PlayerState.PunchComboNr += 1;
               }
               if(EnemiesInMeleeRange().length > 0)
               {
                  _button_in_melee_range = false;
               }
            }
         }
      }
      
      private function BotDodgeRocket() : Boolean
      {
         if(_BotState.Difficulty == BotState.EASY)
         {
            return false;
         }
         if(_BotState.Difficulty == BotState.MEDIUM)
         {
            if(Math.random() < 0.5)
            {
               return false;
            }
         }
         if(!_PlayerState.OnGround)
         {
            return false;
         }
         if(_PlayerState.Aiming)
         {
            if(Boolean(_Handler_ProjectilesUpdater.RocketImpactFrameTime(this,0.1,16)))
            {
               return true;
            }
         }
         else if(Boolean(_Handler_ProjectilesUpdater.RocketImpactFrameTime(this,0.1,16)))
         {
            return true;
         }
         return false;
      }
      
      private function KeyTurnPlayer() : void
      {
         if(PressingLeft())
         {
            if(_PlayerState.LastDirX != -1)
            {
               _PlayerState.LastDirX = -1;
               this.scaleX = _PlayerState.LastDirX;
               _collision_mc.scaleX = this.scaleX;
            }
         }
         else if(PressingRight())
         {
            if(_PlayerState.LastDirX != 1)
            {
               _PlayerState.LastDirX = 1;
               this.scaleX = _PlayerState.LastDirX;
               _collision_mc.scaleX = this.scaleX;
            }
         }
      }
      
      private function PlayerLands() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Boolean = false;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         var _loc5_:Boolean = false;
         var _loc6_:Boolean = false;
         var _loc7_:int = 0;
         _PlayerState.Climbing = false;
         _performJumpDownLevel = false;
         if(_PlayerState.Falling)
         {
            _loc1_ = Math.abs(_PlayerState.AirVelocityY);
            _loc1_ -= 3;
            _loc1_ *= 1.5;
            if(_loc1_ < 3)
            {
               _loc1_ = 0;
            }
            _loc2_ = false;
            _loc3_ = 0;
            while(_loc3_ <= 2)
            {
               if(HitTestWorldOnly(_this_x,_this_y + _loc3_))
               {
                  _loc2_ = true;
                  break;
               }
               _loc3_++;
            }
            _loc4_ = 0;
            while(_loc4_ <= 6)
            {
               b = m_world.GetStairBodyAt(_this_x,_this_y + _loc4_);
               if(b != null)
               {
                  if(CanBounceAtDirection(ConvertToDirection(b.GetUserData().tiltValue)))
                  {
                     _PlayerState.StairBounce = true;
                     _PlayerState.LastDirX *= -1;
                     _PlayerState.StairVelocityY *= -0.7;
                     if(_PlayerState.StairVelocityY < -4)
                     {
                        _PlayerState.StairVelocityY = -4;
                     }
                     else if(_PlayerState.StairVelocityY > -1)
                     {
                        _PlayerState.StairVelocityY = -1;
                     }
                     _PlayerState.StairVelocityX = b.GetUserData().tiltValue;
                     _Handler_Sounds.PlaySoundAt("BODYFALL",_this_x,_this_y);
                     BodyDust();
                     _PlayerState.IncreaseKnockdownGrade();
                     _lastBounceY = _this_y;
                     return;
                  }
               }
               _loc4_++;
            }
            if(!_loc2_)
            {
               _loc5_ = false;
               _loc6_ = false;
               _loc7_ = -4;
               while(_loc7_ <= _PlayerState.PlayerEdgeDistance)
               {
                  b = GetDynamicBodyAt(_this_x + _loc7_,_this_y + 2,false);
                  if(b != null)
                  {
                     if(Boolean(b.GetUserData().objectData.PlayerFragile))
                     {
                        b.GetUserData().objectData.ForceDestruction();
                        _PlayerState.AirVelocityY *= 0.6;
                        _PlayerState.LastDirX *= -1;
                        _loc5_ = true;
                     }
                  }
                  _loc7_ += 2;
               }
            }
            if(!_loc6_ && !_loc5_)
            {
               _loc6_ = Boolean(SidewayBounce());
            }
            if(_loc1_ != 0)
            {
               _PlayerState.HP -= _loc1_;
            }
            if(_loc6_)
            {
               _PlayerState.DecreaseBurnState();
               _lastBounceY = _this_y;
               return;
            }
            if(_loc5_)
            {
               _lastBounceY = _this_y;
               return;
            }
            _Handler_Sounds.PlaySoundAt("BODYFALL",_this_x,_this_y);
            BodyDust();
            _PlayerState.IncreaseKnockdownGrade();
            _PlayerState.Falling = false;
            _PlayerState.Knockdowned = true;
            this.scaleX = _PlayerState.LastDirX;
            _collision_mc.scaleX = this.scaleX;
            _PlayerState.DecreaseBurnState();
            if(_PlayerState.HP <= 0)
            {
               CheckDeathBounce();
               _lastBounceY = _this_y;
            }
         }
         else if(_PlayerState.Diving)
         {
            b = m_world.GetGlassAt(_this_x,_this_y);
            if(b == null)
            {
               b = m_world.GetGlassAt(_this_x,_this_y + 2);
            }
            if(b != null)
            {
               b.GetUserData().objectData.ForceDestruction();
               return;
            }
            DropGrabbedPlayer();
            _PlayerState.Jumping = false;
            Roll();
            return;
         }
         if(_PlayerState.Jumping)
         {
            _PlayerState.Jumping = false;
            if(Boolean(_keyPressed[KEY_JUMP]))
            {
               Jump();
            }
         }
         else
         {
            UpdateDynamicMovement();
         }
      }
      
      public function BotPositionInSight(param1:Number, param2:Number, param3:Number, param4:b2Body = null) : Boolean
      {
         var _loc5_:Point = null;
         var _loc6_:Point = null;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:b2Body = null;
         var _loc11_:b2Body = null;
         var _loc12_:int = 0;
         var _loc13_:Number = NaN;
         var _loc14_:Number = NaN;
         var _loc15_:int = 0;
         var _loc16_:Point = null;
         var _loc17_:b2Body = null;
         var _loc18_:int = 0;
         var _loc19_:int = 0;
         var _loc20_:Boolean = false;
         _loc5_ = new Point(PosX() - _PlayerState.LastDirX * 4,PosY() - 14);
         _loc6_ = new Point(param1,param2);
         _loc7_ = _loc5_.x - _loc6_.x;
         _loc8_ = _loc5_.y - _loc6_.y;
         _loc9_ = Math.sqrt(_loc7_ * _loc7_ + _loc8_ * _loc8_);
         if(_loc9_ > _PlayerState.RangeWeaponRange)
         {
            return false;
         }
         _loc10_ = null;
         _loc11_ = null;
         _loc12_ = _loc9_ / 4;
         _loc13_ = -_loc7_ / _loc12_;
         _loc14_ = -_loc8_ / _loc12_;
         _loc15_ = 1;
         while(_loc15_ <= _loc12_)
         {
            _loc5_.x += _loc13_;
            _loc5_.y += _loc14_;
            _loc6_.x -= _loc13_;
            _loc6_.y -= _loc14_;
            _loc17_ = null;
            _loc18_ = -1;
            while(_loc18_ <= 1)
            {
               if(_loc18_ == 1)
               {
                  _loc16_ = _loc5_;
                  _loc17_ = _loc10_;
               }
               else
               {
                  _loc16_ = _loc6_;
                  _loc17_ = _loc11_;
               }
               if(_loc17_ != null)
               {
                  if(!_loc17_.GetUserData().objectData.ShapeMC.hitTestPoint(_loc16_.x,_loc16_.y,true))
                  {
                     _loc17_ = null;
                  }
               }
               if(_loc17_ == null)
               {
                  if(_static_objects_hitbox_mc.hitTestPoint(_loc16_.x,_loc16_.y,true))
                  {
                     _loc17_ = m_world.GetBulletSolidAt(_loc16_.x,_loc16_.y);
                     if(_loc17_ == param4)
                     {
                        _loc17_ = null;
                     }
                  }
                  else
                  {
                     if(_static_world_hitbox_mc.hitTestPoint(_loc16_.x,_loc16_.y,true))
                     {
                        return false;
                     }
                     if(_loc14_ > 0 && !_PlayerState.RangeWeaponCanShootDown)
                     {
                        if(_static_world_cloud_hitbox_mc.hitTestPoint(_loc16_.x,_loc16_.y,true))
                        {
                           return false;
                        }
                     }
                  }
               }
               if(_loc17_ != null)
               {
                  if(!_PlayerState.RangeWeaponIsFlamethrower)
                  {
                     if(!_BotState.IgnoreObjectChecking || !_PlayerState.RangeWeaponIsBazooka)
                     {
                        if(Boolean(_loc17_.GetUserData().objectData.Indestructible))
                        {
                           return false;
                        }
                     }
                     if(_PlayerState.CurrentRangeWeapon != null)
                     {
                        _loc20_ = false;
                        if(Boolean(_loc17_.GetUserData().objectData.IsBulletHazard))
                        {
                           if(Math.sqrt(Math.pow(_loc17_.GetPosition().x * 30 - MidPosX(),2) + Math.pow(_loc17_.GetPosition().y * 30 - MidPosY(),2)) <= HAZARDOUS_DISTANCE_AVOID)
                           {
                              return false;
                           }
                           _loc20_ = true;
                        }
                        if(!_loc20_ && !_BotState.IgnoreObjectChecking)
                        {
                           if(_PlayerState.CurrentRangeWeapon.Properties.Projectile.StrengthLeft < _loc17_.GetUserData().objectData.Strength)
                           {
                              return false;
                           }
                        }
                     }
                  }
               }
               if(_loc18_ == 1)
               {
                  _loc10_ = _loc17_;
               }
               else
               {
                  _loc11_ = _loc17_;
               }
               _loc19_ = 0;
               while(_loc19_ < _players.length)
               {
                  if(_players[_loc19_].State.HP <= 0)
                  {
                     if(_loc15_ + 2 <= _loc12_)
                     {
                        if(Boolean(_players[_loc19_].CollisionMC.hitTestPoint(_loc16_.x,_loc16_.y,true)))
                        {
                           return false;
                        }
                     }
                  }
                  else if(_players[_loc19_].PlayerNr != PlayerNr)
                  {
                     if(_players[_loc19_].PlayerNr != param3)
                     {
                        if(_players[_loc19_].Team == Team)
                        {
                           if(Boolean(_players[_loc19_].AreaMC.hitTestPoint(_loc16_.x,_loc16_.y,true)))
                           {
                              return false;
                           }
                        }
                     }
                  }
                  _loc19_++;
               }
               _loc18_ += 2;
            }
            _loc15_ += 2;
         }
         return true;
      }
      
      public function Revive(param1:Number, param2:Number) : void
      {
         _PlayerBars.Show();
         this.visible = true;
         _PlayerState.ForceHP = 100;
         _collision_mc.visible = true;
         _collision_mc.x = param1;
         _collision_mc.y = param2;
         _player_area_mc.x = param1;
         _player_area_mc.y = param2;
         _this_x = param1;
         _this_y = param2;
         _PlayerState.IgnoreMe = false;
         _char_gui.visible = true;
         _blood_gui.visible = true;
         _gui_mc.gib_pic.alpha = 0;
         _PlayerState.Gone = false;
         _PlayerState.AirVelocityX = 0;
         _PlayerState.AirVelocityY = 0;
         _PlayerState.Falling = false;
         _PlayerState.Knockdowned = false;
         _PlayerState.Jumping = true;
      }
      
      public function get CameraIgnore() : Boolean
      {
         return _PlayerState.CameraIgnoreMe;
      }
      
      private function SetNumTo(param1:MovieClip, param2:int) : void
      {
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         _loc3_ = param2 % 10;
         _loc4_ = int((param2 - _loc3_) / 10);
         if(_loc3_ == 0)
         {
            param1.dig_1.gotoAndStop(10);
         }
         else
         {
            param1.dig_1.gotoAndStop(_loc3_);
         }
         if(_loc4_ == 0)
         {
            param1.dig_10.gotoAndStop(10);
         }
         else
         {
            param1.dig_10.gotoAndStop(_loc4_);
         }
      }
      
      private function Stuck() : Boolean
      {
         if(HitTestWorldOnly(_this_x,_this_y - 2))
         {
            if(HitTestWorldOnly(_this_x,_this_y + 2))
            {
               return true;
            }
         }
         return false;
      }
      
      public function GiveDefaultMelee(param1:WeaponMeleeData) : void
      {
         _PlayerState.DefaultMeleeWeapon = param1;
      }
      
      private function StandingOnCloud() : Boolean
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ <= 4)
         {
            if(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x,_this_y + _loc1_,true))
            {
               return true;
            }
            _loc1_ += 1;
         }
         return false;
      }
      
      private function PunchPlayer(param1:int) : void
      {
         var _loc2_:Boolean = false;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         _loc2_ = false;
         if(_players[param1].State.HP <= 0)
         {
            _loc2_ = true;
         }
         _players[param1].SetDirection(-_PlayerState.LastDirX);
         _players[param1].Disarm();
         if(Boolean(_players[param1].State.Jumping))
         {
            _players[param1].State.AirVelocityX += _PlayerState.LastDirX * 2;
            _players[param1].Fall();
         }
         else
         {
            _players[param1].State.StunTimer = _PlayerState.HitPunchStunTime;
         }
         if(_players[param1].State.HP > 0)
         {
            _players[param1].State.HP -= _PlayerState.HitPunchDamage;
            if(_players[param1].State.HP <= 0)
            {
               if(ActivateSlowmotion(param1))
               {
                  _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
               }
            }
         }
         if(_PlayerState.CurrentMeleeWeapon != null)
         {
            if(!_players[param1].State.Burned)
            {
               _loc3_ = 0;
               while(_loc3_ < 3)
               {
                  _Handler_Effects.AddParticle(new particle_data("PARTICLE_BLOOD",_players[param1].PosX() - _PlayerState.LastDirX * 2,_players[param1].PosY() - 12 - Math.random() * 2,new b2Vec2(_PlayerState.LastDirX,0),0,1,[Math.floor(Math.random() * 1.99)]));
                  _loc3_++;
               }
               _Handler_Effects.AddEffectAt("BLOOD",_players[param1].PosX() - _PlayerState.LastDirX * 2,_players[param1].PosY() - 12);
            }
            else
            {
               _Handler_Effects.AddEffectAt("PLAYER_BURNED_HITDEFAULT",_players[param1].PosX() - _PlayerState.LastDirX * 2,_players[param1].PosY() - 12);
            }
         }
         else
         {
            _Handler_Effects.AddEffectAt("FIST_IMPACT",_players[param1].PosX() - _PlayerState.LastDirX * 2,_players[param1].PosY() - 12);
            if(_PlayerState.PunchComboNr >= 2)
            {
               if(!_players[param1].State.Burned)
               {
                  _loc4_ = 0;
                  while(_loc4_ < _PlayerState.PunchComboNr)
                  {
                     _Handler_Effects.AddParticle(new particle_data("PARTICLE_BLOOD",_players[param1].PosX() - _PlayerState.LastDirX * 2,_players[param1].PosY() - 12 - Math.random() * 2,new b2Vec2(_PlayerState.LastDirX,0),0,1,[Math.floor(Math.random() * 1.99)]));
                     _loc4_++;
                  }
               }
               else
               {
                  _Handler_Effects.AddEffectAt("PLAYER_BURNED_HITDEFAULT",_players[param1].PosX() - _PlayerState.LastDirX * 2,_players[param1].PosY() - 12);
               }
            }
         }
         if(_players[param1].State.HP <= 0 && !_loc2_ && (Boolean(_players[param1].State.Running) || Boolean(_players[param1].State.Sprinting)))
         {
            _players[param1].State.AirVelocityX = _players[param1].State.LastDirX * 3;
            _players[param1].State.AirVelocityY = -2.5;
            _players[param1].Fall();
         }
         else if(_PlayerState.PunchComboNr == 3 || _players[param1].State.HP <= 0)
         {
            _players[param1].State.AirVelocityX = _PlayerState.LastDirX * 3;
            _players[param1].State.AirVelocityY = -2.5;
            _players[param1].Fall();
         }
         if(_players[param1].State.HP <= 0 && !_players[param1].State.Knockdowned && !_PlayerState.Falling)
         {
            _players[param1].State.AirVelocityX = _PlayerState.LastDirX * 2;
            _players[param1].State.AirVelocityY = -2.5;
            _players[param1].Fall();
         }
      }
      
      private function DisableJumpDownLevel() : void
      {
         _enableJumpDownLevel = false;
         clearInterval(_downTimer);
      }
      
      private function PressingLeft(param1:Boolean = false) : Boolean
      {
         if(_PlayerState.MovingDirectionInversed != 0)
         {
            if(_PlayerState.MovingDirectionInversed == -1)
            {
               return false;
            }
            if(Boolean(_keyPressed[3]))
            {
               return true;
            }
         }
         else if(Boolean(_keyPressed[2]) && (!_keyPressed[3] || !param1))
         {
            return true;
         }
         return false;
      }
      
      public function get MC() : MovieClip
      {
         return this;
      }
      
      public function SetGUI(param1:MovieClip) : void
      {
         var _loc2_:MovieClip = null;
         _gui_mc = param1;
         _gui_mc.visible = true;
         _loc2_ = new MovieClip();
         _char_gui = PlayerCharacter.Get(_PlayerState.CharNr);
         _blood_gui = new player_blood();
         _loc2_.addChild(_char_gui);
         _loc2_.scaleX = 1;
         _loc2_.scaleY = 1;
         _gui_mc.addChild(_loc2_);
         _gui_mc.addChild(_blood_gui);
         _loc2_.x = _gui_mc.player_mc.x;
         _loc2_.y = _gui_mc.player_mc.y;
         _blood_gui.x = _gui_mc.player_mc.x;
         _blood_gui.y = _gui_mc.player_mc.y;
         _PlayerAnimation.SetGUISkin(_char_gui,_blood_gui);
         _PlayerAnimation.ShowAnimation("aim_pistol");
         _PlayerBars.SetGUI(_gui_mc);
      }
      
      private function CanTakeCover(param1:int) : Boolean
      {
         var _loc2_:Number = NaN;
         var _loc3_:int = 0;
         _loc2_ = param1 * _PlayerState.PlayerEdgeDistance + param1 * 4;
         if(_static_world_hitbox_mc.hitTestPoint(_this_x + _loc2_,MidPosY(),true))
         {
            if(!_PlayerState.TakingCover)
            {
               b = m_world.GetStairBodyAt(_this_x + _loc2_,MidPosY());
               if(b != null)
               {
                  return false;
               }
            }
            _loc3_ = 0;
            while(_loc3_ <= 12)
            {
               if(!_static_world_hitbox_mc.hitTestPoint(_this_x + _loc2_,_this_y - 22 + _loc3_,true))
               {
                  return true;
               }
               _loc3_ += 4;
            }
         }
         return false;
      }
      
      public function get Bot() : Boolean
      {
         return _bot;
      }
      
      private function SwapDepths(param1:int) : void
      {
         if(this.parent.getChildIndex(this) < _players[param1].parent.getChildIndex(_players[param1]))
         {
            this.parent.swapChildren(this,_players[param1]);
         }
      }
      
      private function AbleToWalljump() : Boolean
      {
         var _loc1_:int = 0;
         if(!_PlayerState.WallJumping)
         {
            if(Math.sqrt(_PlayerState.AirVelocityY * _PlayerState.AirVelocityY) <= 3)
            {
               _edgePosition = _this_x + (_PlayerState.PlayerEdgeDistance + 1) * _PlayerState.LastDirX;
               _loc1_ = 0;
               while(_loc1_ <= 8)
               {
                  if(_static_world_hitbox_mc.hitTestPoint(_edgePosition,_this_y - _loc1_,true))
                  {
                     return true;
                  }
                  _loc1_ += 2;
               }
            }
         }
         return false;
      }
      
      private function BotStateAim() : void
      {
         var _loc1_:Number = NaN;
         if(Boolean(_PlayerState.Jumping) || _PlayerState.CurrentRangeWeapon == null)
         {
            _BotState.Phase = BotState.CANCEL_AIM;
            return;
         }
         if(_PlayerState.CurrentRangeWeapon.Ammo <= 0)
         {
            _BotState.Phase = BotState.CANCEL_AIM;
            return;
         }
         if(_BotState.TargetHazardousObject == null)
         {
            if(_BotState.ActionShotFired)
            {
               if(!_BotState.TargetInSight)
               {
                  _BotState.Phase = BotState.CANCEL_AIM;
                  return;
               }
               if(Boolean(BotTargetInMelee()) && !_BotState.TargetPlayer.State.Knockdowned)
               {
                  _BotState.Phase = BotState.CANCEL_AIM;
                  return;
               }
            }
            else if(_BotState.TargetPlayer == null)
            {
               _BotState.Phase = BotState.CANCEL_AIM;
               return;
            }
         }
         SetBotKey(2,false);
         SetBotKey(3,false);
         if(_BotState.TargetHazardousObject != null)
         {
            _loc1_ = _BotState.TargetHazardousObject.GetPosition().x * 30 - MidPosX();
         }
         else
         {
            _loc1_ = _BotState.TargetPlayer.MidPosX() - MidPosX();
         }
         if(Math.abs(_loc1_) > 5)
         {
            if(_PlayerState.LastDirX * _loc1_ <= 0)
            {
               if(_PlayerState.LastDirX > 0)
               {
                  SetBotKey(2,true);
               }
               else
               {
                  SetBotKey(3,true);
               }
               return;
            }
         }
         if(!_PlayerState.Aiming)
         {
            SetBotKey(KEY_FIRE,!_keyPressed[KEY_FIRE]);
         }
         BotAimY();
         if(_BotState.TargetInAim)
         {
            if(_PlayerState.CurrentWeaponCooldown <= 0 && !_PlayerState.AimTurningAround)
            {
               if(_BotState.TargetHazardousObject == null)
               {
                  if(Boolean(_BotState.TargetPlayer.State.IsImmune) && _BotState.Difficulty == BotState.HARD)
                  {
                     return;
                  }
                  if(Boolean(_BotState.TargetPlayer.State.StuckToRocket) && _PlayerState.CurrentRangeWeapon.Properties.WeaponType == "BAZOOKA")
                  {
                     return;
                  }
               }
               if(_BotState.Difficulty == BotState.EASY)
               {
                  if(Math.random() < 0.85)
                  {
                     return;
                  }
               }
               if(_BotState.Difficulty == BotState.MEDIUM)
               {
                  if(Math.random() < 0.7)
                  {
                     return;
                  }
               }
               _BotState.SetDelay();
               _BotState.Phase = BotState.SHOOT;
               SetBotKey(5,false);
               _BotState.RandomFirePosition = true;
               _BotState.ActionShotFired = true;
            }
         }
      }
      
      private function BotFacingEdge(param1:int = 1) : Boolean
      {
         return DetectEdge(_PlayerState.LastDirX * param1,45,true);
      }
      
      private function BotTargetThreat_Aim(param1:Player) : Number
      {
         if(param1.State.Aiming)
         {
            return param1.PlayerInSightPercentage(this);
         }
         return 0;
      }
      
      private function CanDive() : Boolean
      {
         if(CollisionHead())
         {
            return false;
         }
         return true;
      }
      
      private function BotChooseTarget(param1:Boolean = true) : void
      {
         var _loc2_:int = 0;
         var _loc3_:Number = NaN;
         var _loc4_:Player = null;
         var _loc5_:int = 0;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Boolean = false;
         var _loc10_:Number = NaN;
         var _loc11_:b2Body = null;
         var _loc12_:Number = NaN;
         var _loc13_:Number = NaN;
         var _loc14_:b2Body = null;
         var _loc15_:int = 0;
         var _loc16_:PathNode = null;
         var _loc17_:Number = NaN;
         var _loc18_:PathNode = null;
         var _loc19_:Number = NaN;
         var _loc20_:Number = NaN;
         var _loc21_:PathNode = null;
         var _loc22_:PathNode = null;
         var _loc23_:Array = null;
         _loc2_ = -1;
         _loc3_ = 99999;
         _loc4_ = _BotState.TargetPlayer;
         _BotState.DoFireCheck = true;
         _loc9_ = false;
         if(param1)
         {
            _BotState.UpdateUnavailableStuff();
         }
         _loc5_ = 0;
         while(_loc5_ < _players.length)
         {
            if(PlayerNr != _loc5_)
            {
               if(_players[_loc5_].State.HP > 0 && _players[_loc5_].Team != _team)
               {
                  _loc9_ = true;
                  if(!_BotState.IsPlayerUnavailable(_players[_loc5_]))
                  {
                     _loc6_ = _players[_loc5_].MidPosX() - MidPosX();
                     _loc7_ = _players[_loc5_].MidPosY() - MidPosY();
                     _loc8_ = Math.sqrt(_loc6_ * _loc6_ + _loc7_ * _loc7_);
                     _loc8_ *= 1 - 0.33 * BotTargetThreat_Aim(_players[_loc5_]);
                     _loc8_ *= 1 - 0.25 * BotTargetThreat_Weapon(_players[_loc5_]);
                     _loc8_ *= 1 - 0.4 * BotTargetThreat_Weakness(_players[_loc5_]);
                     _loc10_ = _loc8_ * 0.33;
                     if(_loc8_ < 50 && Math.abs(_loc7_) < 20)
                     {
                        _loc8_ = _loc10_;
                     }
                     else if(_loc10_ < _loc3_)
                     {
                        if(_PlayerState.RangeWeaponRange < _loc10_)
                        {
                           if(BotPositionInSight(_players[_loc5_].MidPosX() + Math.random() * 6 - 3,_players[_loc5_].MidPosY() + Math.random() * 4 - 2,_players[_loc5_].PlayerNr))
                           {
                              _loc8_ = _loc10_;
                           }
                        }
                     }
                     if(_loc8_ < _loc3_)
                     {
                        _loc2_ = _loc5_;
                        _loc3_ = _loc8_;
                     }
                  }
               }
            }
            _loc5_++;
         }
         _BotState.OpponentExist = _loc9_;
         if(!_BotState.OpponentExist)
         {
            BotCalculatePathGrid(_pathGrid.GetNodeAt(MidPosX(),MidPosY()));
            return;
         }
         if(_BotState.Difficulty > BotState.EASY && Boolean(_PlayerState.OnGround) && _loc2_ != -1 && _PlayerState.CurrentRangeWeapon != null && !BotState.FOLLOW_ONLY)
         {
            _loc5_ = 0;
            while(_loc5_ < m_world.HazardsList.length)
            {
               _loc11_ = m_world.HazardsList[_loc5_];
               if(Boolean(_loc11_.GetUserData().objectData.IsBulletHazard))
               {
                  _loc12_ = _loc11_.GetPosition().x * 30;
                  _loc13_ = _loc11_.GetPosition().y * 30;
                  _loc6_ = _loc12_ - _players[_loc2_].MidPosX();
                  _loc7_ = _loc13_ - _players[_loc2_].MidPosY();
                  _loc8_ = Math.sqrt(_loc6_ * _loc6_ + _loc7_ * _loc7_);
                  if(_loc8_ <= HAZARDOUS_DISTANCE)
                  {
                     _loc6_ = _loc12_ - MidPosX();
                     _loc7_ = _loc13_ - MidPosY();
                     _loc8_ = Math.sqrt(_loc6_ * _loc6_ + _loc7_ * _loc7_);
                     if(_loc8_ > HAZARDOUS_DISTANCE_AVOID)
                     {
                        if(BotPositionInSight(_loc12_,_loc13_,9999,_loc11_))
                        {
                           _BotState.TargetHazardousObject = _loc11_;
                           _BotState.TargetPlayer = _players[_loc2_];
                           _BotState.Phase = BotState.AIM;
                           return;
                        }
                     }
                  }
               }
               _loc5_++;
            }
         }
         _BotState.TargetHazardousObject = null;
         if(!BotState.FOLLOW_ONLY)
         {
            if(_PlayerState.CurrentRangeWeapon == null || !_BotState.TargetInSight)
            {
               _loc14_ = _BotState.TargetWeapon;
               _loc15_ = -1;
               _loc5_ = 0;
               while(_loc5_ < m_world.WeaponList.length)
               {
                  b = m_world.WeaponList[_loc5_];
                  _loc16_ = _pathGrid.GetNodeAt(b.GetPosition().x * 30,b.GetPosition().y * 30);
                  if(_loc16_ != null)
                  {
                     if(!_loc16_.Avoid)
                     {
                        if(b.GetUserData().weaponData.Ammo > 0)
                        {
                           if(!_BotState.IsWeaponUnavailable(b))
                           {
                              _loc6_ = MidPosX() - b.GetPosition().x * 30;
                              _loc7_ = MidPosY() + 4 - b.GetPosition().y * 30;
                              _loc8_ = Math.sqrt(_loc6_ * _loc6_ + _loc7_ * _loc7_);
                              if(b.GetUserData().isRanged == true && b.GetUserData().weaponData.TotalDamage > _PlayerState.RangeWeaponTotalDamage * 1.2)
                              {
                                 _loc8_ -= 0.25 * (b.GetUserData().weaponData.TotalDamage - _PlayerState.RangeWeaponTotalDamage);
                              }
                              else if(b.GetUserData().isMelee == true && b.GetUserData().weaponData.TotalDamage > _PlayerState.MeleeWeaponTotalDamage)
                              {
                                 _loc8_ -= 0.25 * (b.GetUserData().weaponData.TotalDamage - _PlayerState.MeleeWeaponTotalDamage);
                              }
                              else if(b.GetUserData().isHealth == true && _PlayerState.HP < 100 && _BotState.Difficulty > BotState.EASY)
                              {
                                 _loc17_ = 100 - _PlayerState.HP;
                                 if(_loc17_ > b.GetUserData().weaponData.Ammo)
                                 {
                                    _loc17_ = Number(b.GetUserData().weaponData.Ammo);
                                 }
                                 _loc8_ -= 0.5 * _loc17_;
                                 if(_PlayerState.HP <= 25)
                                 {
                                    _loc8_ *= 0.7;
                                 }
                              }
                              else
                              {
                                 _loc8_ = 9999;
                              }
                              if(b == _loc14_)
                              {
                                 _loc8_ *= 0.8;
                              }
                              if(_loc8_ < _loc3_)
                              {
                                 _loc15_ = _loc5_;
                                 _loc3_ = _loc8_;
                                 _loc2_ = -1;
                              }
                           }
                        }
                     }
                  }
                  _loc5_++;
               }
               if(_loc15_ >= 0)
               {
                  _BotState.TargetWeapon = m_world.WeaponList[_loc15_];
                  _BotState.PathGridCounter -= 1;
                  if(_loc14_ != _BotState.TargetWeapon && _BotState.Phase == BotState.GRAB_WEAPON)
                  {
                     _BotState.Phase = BotState.IDLE;
                  }
                  if(_loc14_ != _BotState.TargetWeapon || _BotState.PathGridCounter <= 0)
                  {
                     _BotState.PathGridCounter = 2;
                     _loc18_ = _pathGrid.GetNodeAt(_BotState.TargetWeapon.GetPosition().x * 30,_BotState.TargetWeapon.GetPosition().y * 30);
                     BotCalculatePathGrid(_loc18_);
                     if(_BotState.Path.length <= 0)
                     {
                        if(_pathGrid.GetNodeAt(MidPosX(),MidPosY()) != _loc18_)
                        {
                           _BotState.UnavailableWeapons.push([_BotState.TargetWeapon,0]);
                           _BotState.TargetWeapon = null;
                        }
                     }
                  }
               }
               else
               {
                  _BotState.TargetWeapon = null;
               }
            }
         }
         if(_loc2_ >= 0)
         {
            _BotState.TargetPlayer = _players[_loc2_];
            _BotState.PathGridCounter -= 1;
            if(_loc4_ != _BotState.TargetPlayer || _BotState.PathGridCounter <= 0)
            {
               _BotState.PathGridCounter = 2;
               _loc19_ = Number(_BotState.TargetPlayer.MidPosX());
               _loc20_ = Number(_BotState.TargetPlayer.MidPosY());
               _loc21_ = _pathGrid.GetNodeAt(_loc19_,_loc20_);
               BotCalculatePathGrid(_loc21_);
               if(_BotState.Path.length <= 0)
               {
                  _loc22_ = _pathGrid.GetNodeAt(MidPosX(),MidPosY());
                  if(_loc22_ != null)
                  {
                     if(_loc22_.GetBindTo(_loc21_) != null || _loc22_ == _loc21_)
                     {
                        return;
                     }
                     if(BotPositionShootableFrom(_loc19_,_loc20_,_loc22_.PosX,_loc22_.PosY - 2))
                     {
                        _BotState.IgnoreObjectCheckingTimer = BotState.UNAVAILABLE_PLAYER_TIMER;
                        return;
                     }
                     _loc23_ = _pathGrid.GetConnectedNodes();
                     _loc5_ = 2;
                     while(_loc5_ < _loc23_.length)
                     {
                        if(BotPositionShootableFrom(_loc19_,_loc20_,_loc23_[_loc5_].PosX,_loc23_[_loc5_].PosY - 2))
                        {
                           _BotState.IgnoreObjectCheckingTimer = BotState.UNAVAILABLE_PLAYER_TIMER;
                           BotCalculatePathGrid(_loc23_[_loc5_]);
                           return;
                        }
                        _loc5_ += 2;
                     }
                     _BotState.UnavailablePlayers.push([_BotState.TargetPlayer,0]);
                     _BotState.TargetPlayer = null;
                     BotChooseTarget(false);
                  }
               }
            }
         }
         else
         {
            _BotState.TargetPlayer = null;
         }
         if(_loc2_ == -1 && _loc15_ == -1)
         {
            BotCalculatePathGrid(_pathGrid.GetNodeAt(MidPosX(),MidPosY()));
         }
      }
      
      private function ThrowTimerEnded() : void
      {
         if(Boolean(_PlayerState.Aiming) && _PlayerState.AimMode == 1)
         {
            DropThrowable();
         }
      }
      
      private function CanStagger() : Boolean
      {
         if(_PlayerState.HP <= 0 && Boolean(_PlayerState.Knockdowned))
         {
            return false;
         }
         return !StaggerCollision(-_PlayerState.LastDirX);
      }
      
      private function WorldCollisionHead() : Boolean
      {
         var _loc1_:int = 0;
         if(Boolean(HitTestWorldOnly(_this_x,_this_y - _PlayerState.PlayerHeight)) && (Boolean(HitTestWorldOnly(_this_x - _PlayerState.PlayerEdgeDistance,_this_y - _PlayerState.PlayerHeight)) || Boolean(HitTestWorldOnly(_this_x + _PlayerState.PlayerEdgeDistance,_this_y - _PlayerState.PlayerHeight))))
         {
            return true;
         }
         _loc1_ = 4;
         while(_loc1_ <= _PlayerState.PlayerHeight - 2)
         {
            if(Boolean(HitTestWorldOnly(_this_x - _PlayerState.PlayerEdgeDistance,_this_y - _loc1_)) && Boolean(HitTestWorldOnly(_this_x,_this_y - _loc1_)) && Boolean(HitTestWorldOnly(_this_x + _PlayerState.PlayerEdgeDistance,_this_y - _loc1_)))
            {
               return true;
            }
            _loc1_ += 2;
         }
         return false;
      }
      
      private function UpdateDynamicMovement(param1:Boolean = false) : void
      {
         var _loc2_:Array = null;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         var _loc5_:b2Vec2 = null;
         var _loc6_:b2Vec2 = null;
         var _loc7_:Number = NaN;
         if(_PlayerState.KickingTimer > 0)
         {
            return;
         }
         if(_PlayerState.OnGround)
         {
            _loc2_ = new Array();
            _loc3_ = 0;
            while(_loc3_ < m_world.DynamicHitBoxObjectList.length)
            {
               b = m_world.DynamicHitBoxObjectList[_loc3_];
               if(Boolean(b.GetUserData().objectData.ShapeMC.hitTestObject(_player_area_mc)))
               {
                  _loc2_.push(b);
               }
               _loc3_++;
            }
            _loc4_ = 0;
            while(_loc4_ <= _PlayerState.PlayerEdgeDistance + 2)
            {
               _loc3_ = 0;
               while(_loc3_ < _loc2_.length)
               {
                  b = _loc2_[_loc3_];
                  if(Boolean(b.GetUserData().objectData.ShapeMC.hitTestPoint(_this_x + _loc4_,_this_y + 2,true)) || Boolean(b.GetUserData().objectData.ShapeMC.hitTestPoint(_this_x - _loc4_,_this_y + 2,true)))
                  {
                     _loc5_ = new b2Vec2(_this_x / 30,_this_y / 30);
                     if(Boolean(b.GetUserData().objectData.IsElevator))
                     {
                        _loc6_ = b.GetLinearVelocity();
                     }
                     else
                     {
                        _loc6_ = b.GetLinearVelocityFromWorldPoint(_loc5_);
                     }
                     if(param1)
                     {
                        if(b.GetUserData().isConveyorBelt == true)
                        {
                           _PlayerState.AirVelocityX = b.GetLinearVelocity().x + b.GetUserData().conveyorBeltSpeedX;
                           _PlayerState.AirVelocityY = b.GetLinearVelocity().y + b.GetUserData().conveyorBeltSpeedY;
                        }
                        else
                        {
                           _PlayerState.AirVelocityX = b.GetLinearVelocity().x;
                           _PlayerState.AirVelocityY = b.GetLinearVelocity().y;
                        }
                     }
                     else
                     {
                        _PlayerState.AirVelocityX = _loc6_.x;
                        _PlayerState.AirVelocityY = _loc6_.y;
                        if(Boolean(b.GetUserData().objectData.ShapeMC.hitTestPoint(_this_x,_this_y + 2,true)))
                        {
                           SimpleMove(_loc6_.x * _game_speed,_loc6_.y * _game_speed * 0.66);
                        }
                        else
                        {
                           SimpleMove(_loc6_.x * _game_speed,_loc6_.y * _game_speed * 1.01);
                        }
                        if(_game_speed >= 0.01)
                        {
                           _loc7_ = b.GetMass() / 10;
                           b.ApplyImpulse(new b2Vec2(0,_loc7_ * _game_speed),_loc5_);
                        }
                     }
                     _standingOnObject = b;
                     return;
                  }
                  _loc3_++;
               }
               _loc4_ += 2;
            }
            _PlayerState.AirVelocityX = 0;
            _PlayerState.AirVelocityY = 0;
         }
         _standingOnObject = null;
      }
      
      private function CanLandInMid() : Boolean
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ <= _PlayerState.PlayerEdgeDistance)
         {
            if(!_performJumpDownLevel)
            {
               if(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x,_this_y + _loc1_,true))
               {
                  return true;
               }
            }
            if(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y + _loc1_,true))
            {
               return true;
            }
            _loc1_ += 2;
         }
         return false;
      }
      
      private function UpdateEventNPC() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Number = NaN;
         var _loc3_:int = 0;
         var _loc4_:* = undefined;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         var _loc12_:Boolean = false;
         var _loc13_:Boolean = false;
         if(_PlayerState.HP <= 0)
         {
            clearInterval(_botTimer);
            clearInterval(_BotState._targetChooseTimer);
            clearInterval(_BotState._targetInSightTimer);
            clearInterval(_BotState._randomizTimer);
            return;
         }
         if(_PlayerState.StuckToRocket)
         {
            clearInterval(_BotState._targetChooseTimer);
            clearInterval(_BotState._targetInSightTimer);
            clearInterval(_BotState._randomizTimer);
            SetBotKey(KEY_UP,false);
            SetBotKey(KEY_DOWN,false);
            if(_BotState.Difficulty < BotState.HARD)
            {
               SetBotKey(KEY_RIGHT,false);
               SetBotKey(KEY_LEFT,false);
               return;
            }
            _loc2_ = 99999;
            _loc3_ = -1;
            _loc1_ = 0;
            while(_loc1_ < _players.length)
            {
               if(_players[_loc1_].State.HP > 0 && _players[_loc1_].Team != Team && _loc1_ != PlayerNr)
               {
                  _loc4_ = Math.sqrt(Math.pow(_players[_loc1_].MidPosX() - MidPosX(),2) + Math.pow(_players[_loc1_].MidPosY() - MidPosY(),2));
                  if(_loc4_ < _loc2_)
                  {
                     _loc2_ = _loc4_;
                     _loc3_ = _loc1_;
                  }
               }
               _loc1_++;
            }
            if(_loc3_ == -1)
            {
               SetBotKey(KEY_LEFT,false);
               SetBotKey(KEY_RIGHT,false);
               return;
            }
            _BotState.TargetPlayer = _players[_loc3_];
            if(!_BotState.FirstRocketTurnDone && (_PlayerState.RocketRideProjectile.DirectionX > 0 && _BotState.TargetPlayer.MidPosX() < MidPosX() || _PlayerState.RocketRideProjectile.DirectionX < 0 && _BotState.TargetPlayer.MidPosX() > MidPosX()))
            {
               if(_PlayerState.RocketRideProjectile.DirectionX < 0)
               {
                  SetBotKey(KEY_LEFT,false);
                  SetBotKey(KEY_RIGHT,true);
               }
               else
               {
                  SetBotKey(KEY_RIGHT,false);
                  SetBotKey(KEY_LEFT,true);
               }
               return;
            }
            _BotState.FirstRocketTurnDone = true;
            _loc5_ = Math.atan2(_BotState.TargetPlayer.MidPosY() - MidPosY(),_BotState.TargetPlayer.MidPosX() - MidPosX());
            _loc6_ = Math.atan2(_PlayerState.RocketRideProjectile.DirectionY,_PlayerState.RocketRideProjectile.DirectionX);
            _loc7_ = _loc5_ * (180 / Math.PI);
            _loc8_ = _loc6_ * (180 / Math.PI);
            _loc9_ = 10;
            _loc10_ = _loc8_;
            _loc11_ = _loc8_;
            _loc1_ = 0;
            while(_loc1_ < 180)
            {
               _loc10_ -= 4;
               _loc11_ += 4;
               if(_loc10_ < -180)
               {
                  _loc10_ += 360;
               }
               if(_loc11_ > 180)
               {
                  _loc11_ -= 360;
               }
               _loc12_ = Math.abs(_loc10_ - _loc7_) < _loc9_;
               _loc13_ = Math.abs(_loc11_ - _loc7_) < _loc9_;
               if(_loc12_ && _loc13_)
               {
                  SetBotKey(KEY_LEFT,false);
                  SetBotKey(KEY_RIGHT,false);
               }
               else if(_loc12_)
               {
                  SetBotKey(KEY_RIGHT,false);
                  SetBotKey(KEY_LEFT,true);
               }
               else if(_loc13_)
               {
                  SetBotKey(KEY_LEFT,false);
                  SetBotKey(KEY_RIGHT,true);
               }
               _loc1_ += 4;
            }
            return;
         }
         if(_BotState.TargetPlayer != null)
         {
            if(_BotState.TargetPlayer.State.HP <= 0)
            {
               _BotState.TargetPlayer = null;
            }
         }
         if(_PlayerState.BotInterrupt)
         {
            _loc1_ = 0;
            while(_loc1_ <= 9)
            {
               SetBotKey(_loc1_,false);
               _loc1_++;
            }
            _BotState.Phase = BotState.INTERRUPTED;
            return;
         }
         if(_BotState.Phase == BotState.INTERRUPTED)
         {
            BotGoForReset(true);
            BotChooseTarget();
            _BotState.Phase = BotState.IDLE;
         }
         if(_BotState.PhaseDelay > 0)
         {
            _BotState.PhaseDelay -= 1;
            return;
         }
         if(BotDodgeRocket())
         {
            if(_PlayerState.Aiming)
            {
               _BotState.Phase = BotState.CANCEL_AIM;
            }
            else if(Math.random() < 0.7 || !_PlayerState.CanRoll || Boolean(BotFacingEdge()))
            {
               SetBotKey(KEY_UP,true);
               SetBotKey(KEY_UP,false);
            }
            else
            {
               if(Boolean(_keyPressed[KEY_LEFT]) && Boolean(_keyPressed[KEY_RIGHT]))
               {
                  if(_PlayerState.LastDirX == 1)
                  {
                     SetBotKey(KEY_LEFT,false);
                  }
                  else
                  {
                     SetBotKey(KEY_RIGHT,false);
                  }
               }
               else if(!_keyPressed[KEY_LEFT] && !_keyPressed[KEY_RIGHT])
               {
                  if(_PlayerState.LastDirX == 1)
                  {
                     SetBotKey(KEY_RIGHT,true);
                  }
                  else
                  {
                     SetBotKey(KEY_LEFT,true);
                  }
               }
               SetBotKey(KEY_DOWN,true);
            }
         }
         if(Boolean(BotDodgeBullet()) || Boolean(_BotState.DodgeBullet))
         {
            if(!_PlayerState.Aiming)
            {
               BotCheckCover();
               if(_PlayerState.CanRoll)
               {
                  if(Boolean(_keyPressed[KEY_LEFT]) && Boolean(_keyPressed[KEY_RIGHT]))
                  {
                     if(_PlayerState.LastDirX == 1)
                     {
                        SetBotKey(KEY_LEFT,false);
                     }
                     else
                     {
                        SetBotKey(KEY_RIGHT,false);
                     }
                  }
                  else if(!_keyPressed[KEY_LEFT] && !_keyPressed[KEY_RIGHT])
                  {
                     if(_PlayerState.LastDirX == 1)
                     {
                        SetBotKey(KEY_RIGHT,true);
                     }
                     else
                     {
                        SetBotKey(KEY_LEFT,true);
                     }
                  }
                  if(BotFacingEdge())
                  {
                     if(BotFacingEdge(-1))
                     {
                        SetBotKey(KEY_UP,false);
                        SetBotKey(KEY_UP,true);
                        SetBotKey(KEY_UP,false);
                        _BotState.Phase = BotState.FOLLOW_PATH;
                        _BotState.DodgeBullet = false;
                        return;
                     }
                     if(Boolean(_keyPressed[KEY_LEFT]))
                     {
                        SetBotKey(KEY_LEFT,false);
                        SetBotKey(KEY_RIGHT,true);
                     }
                     else
                     {
                        SetBotKey(KEY_RIGHT,false);
                        SetBotKey(KEY_LEFT,true);
                     }
                  }
                  DisableJumpDownLevel();
                  SetBotKey(KEY_DOWN,true);
               }
               else
               {
                  if(_BotState.NextResultNode != null)
                  {
                     if(_BotState.NextResultNode.PrevBind != null)
                     {
                        switch(_BotState.NextResultNode.PrevBind.MovementType)
                        {
                           case PathBind.SPRINTJUMP:
                           case PathBind.JUMP:
                           case PathBind.DIVE:
                           case PathBind.CLOUDDOWN:
                              _BotState.DodgeBullet = false;
                              return;
                        }
                     }
                  }
                  SetBotKey(KEY_UP,true);
                  SetBotKey(KEY_UP,false);
               }
               _BotState.DodgeBullet = false;
               return;
            }
            _BotState.DodgeBullet = true;
            _BotState.Phase = BotState.CANCEL_AIM;
         }
         if(_PlayerState.BurnState >= 60 || !_PlayerState.InWorldFire && _PlayerState.BurnState > 20 && !_BotState.RunAwayFromHazards || !_PlayerState.InWorldFire && Boolean(_PlayerState.FireRank1Attached) && _PlayerState.HP < 10 && !_BotState.RunAwayFromHazards)
         {
            if(_PlayerState.Aiming)
            {
               if(_PlayerState.HP < 10)
               {
                  SetBotKey(KEY_MELEE,!_keyPressed[KEY_MELEE]);
                  _BotState.Phase = BotState.FOLLOW_PATH;
                  return;
               }
               _BotState.CancelAimSoon = true;
            }
            else if(_PlayerState.CanRoll)
            {
               BotCheckCover();
               if(_PlayerState.Sprinting)
               {
                  SetBotKey(KEY_LEFT,false);
                  SetBotKey(KEY_RIGHT,false);
                  return;
               }
               SetBotKey(KEY_MELEE,false);
               SetBotKey(KEY_UP,false);
               if(_PlayerState.OnGround)
               {
                  if(!_PlayerState.Rolling)
                  {
                     if(_PlayerState.LastDirX == 1)
                     {
                        SetBotKey(KEY_LEFT,false);
                        SetBotKey(KEY_RIGHT,true);
                     }
                     else
                     {
                        SetBotKey(KEY_RIGHT,false);
                        SetBotKey(KEY_LEFT,true);
                     }
                     DisableJumpDownLevel();
                     SetBotKey(KEY_DOWN,true);
                     return;
                  }
                  SetBotKey(KEY_DOWN,false);
               }
               if(_BotState.Phase == BotState.MELEE && _PlayerState.BurnState >= 45)
               {
                  return;
               }
            }
         }
         if(!_PlayerState.Sprinting && _PlayerState.SprintEnergy > 40)
         {
            if(_PlayerState.OnGround)
            {
               if(_BotState.RunOften)
               {
                  if(_PlayerState.Running)
                  {
                     SetBotKey(KEY_LEFT,false);
                     SetBotKey(KEY_RIGHT,false);
                     return;
                  }
               }
            }
         }
         if(_BotState.Phase == BotState.IDLE)
         {
            SetBotKey(KEY_DOWN,false);
            if(_PlayerState.ControllAble)
            {
               if(_BotState.TargetPlayer != null || _BotState.TargetWeapon != null || Boolean(_BotState.RunAwayFromHazards))
               {
                  _BotState.Phase = BotState.FOLLOW_PATH;
               }
               else if(Boolean(_BotState.TargetInSight) && _PlayerState.CurrentRangeWeapon != null && !BotState.FOLLOW_ONLY)
               {
                  _BotState.Phase = BotState.AIM;
               }
            }
         }
         if(_BotState.Phase == BotState.MELEE)
         {
            BotStateMelee();
         }
         else if(_BotState.Phase == BotState.GRAB_WEAPON)
         {
            BotStateGrabWeapon();
         }
         else if(_BotState.Phase == BotState.FOLLOW_PATH)
         {
            BotStateFollowPath();
         }
         else if(_BotState.Phase == BotState.CANCEL_AIM)
         {
            BotStateCancelAim();
         }
         else if(_BotState.Phase == BotState.AIM)
         {
            BotStateAim();
         }
         else if(_BotState.Phase == BotState.SHOOT)
         {
            BotStateShoot();
         }
      }
      
      public function get Ignore() : Boolean
      {
         return _PlayerState.IgnoreMe;
      }
      
      private function SetBotKey(param1:int, param2:Boolean) : void
      {
         switch(param2)
         {
            case true:
               switch(param1)
               {
                  case 0:
                     if(!_keyPressed[0])
                     {
                        _keyPressed[0] = true;
                        _keyPressed[8] = true;
                        UpPressed();
                        Jump();
                     }
                     break;
                  case 1:
                     if(!_keyPressed[1])
                     {
                        _keyPressed[1] = true;
                        _keyPressed[9] = true;
                        DownPressed();
                        KneelPressed();
                     }
                     break;
                  case 2:
                     _keyPressed[2] = true;
                     break;
                  case 3:
                     _keyPressed[3] = true;
                     break;
                  case 4:
                     if(!_keyPressed[4])
                     {
                        _keyPressed[4] = true;
                        Melee();
                     }
                     break;
                  case 5:
                     if(!_keyPressed[5])
                     {
                        _keyPressed[5] = true;
                        RangedDown();
                     }
                     break;
                  case 6:
                     if(!_keyPressed[6])
                     {
                        _keyPressed[6] = true;
                        ThrowDown();
                     }
                     break;
                  case 7:
                     if(!_keyPressed[7])
                     {
                        _keyPressed[7] = true;
                        UsePowerup();
                     }
               }
               break;
            case false:
               switch(param1)
               {
                  case 0:
                     _keyPressed[0] = false;
                     _keyPressed[8] = false;
                     break;
                  case 1:
                     if(Boolean(_keyPressed[1]))
                     {
                        _keyPressed[1] = false;
                        _keyPressed[9] = false;
                        KneelReleased();
                     }
                     break;
                  case 2:
                     _keyPressed[2] = false;
                     break;
                  case 3:
                     _keyPressed[3] = false;
                     break;
                  case 4:
                     _keyPressed[4] = false;
                     break;
                  case 5:
                     if(Boolean(_keyPressed[5]))
                     {
                        _keyPressed[5] = false;
                        RangedUp();
                     }
                     break;
                  case 6:
                     if(Boolean(_keyPressed[6]))
                     {
                        _keyPressed[6] = false;
                        ThrowUp();
                     }
                     break;
                  case 7:
                     _keyPressed[7] = false;
               }
         }
      }
      
      private function BotAimY() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         if(_BotState.TargetPlayer == null)
         {
            return;
         }
         if(_BotState.TargetHazardousObject != null)
         {
            _loc3_ = PosX() - _PlayerState.LastDirX * 4 - _BotState.TargetHazardousObject.GetPosition().x * 30;
            _loc4_ = PosY() - 14 - _BotState.TargetHazardousObject.GetPosition().y * 30;
         }
         else
         {
            _loc3_ = PosX() - _PlayerState.LastDirX * 4 - _BotState.TargetPlayer.MidPosX();
            _loc7_ = -1;
            if(Math.abs(_loc3_) < 100)
            {
               if(!_BotState.TargetPlayer.State.Kneeling && !_BotState.TargetPlayer.State.TakingCover && !_BotState.TargetPlayer.State.Knockdowned)
               {
                  _loc7_ -= 2;
               }
            }
            _loc4_ = PosY() - 14 - (_BotState.TargetPlayer.MidPosY() + _loc7_);
         }
         _loc5_ = Math.sqrt(Math.pow(_loc3_,2) + Math.pow(_loc4_,2));
         if(_BotState.RandomFirePosition)
         {
            if(_BotState.Difficulty == BotState.EASY)
            {
               _loc9_ = 14 * (Math.PI / 180);
               _loc8_ = _loc5_ * Math.tan(_loc9_);
               if(_loc8_ > 20)
               {
                  _loc8_ = 20;
               }
            }
            else if(_BotState.Difficulty == BotState.MEDIUM)
            {
               _loc9_ = 9 * (Math.PI / 180);
               _loc8_ = _loc5_ * Math.tan(_loc9_);
               if(_loc8_ > 12)
               {
                  _loc8_ = 12;
               }
            }
            else if(_BotState.Difficulty == BotState.HARD)
            {
               _loc8_ = 2;
            }
            _loc10_ = Math.random() * Math.PI * 2;
            _BotState.RandomFireX = Math.cos(_loc10_) * _loc8_;
            _BotState.RandomFireY = Math.sin(_loc10_) * _loc8_;
            _BotState.RandomFirePosition = false;
         }
         _loc3_ += _BotState.RandomFireX;
         _loc4_ += _BotState.RandomFireY;
         if(_PlayerState.LastDirX == -1)
         {
            _loc1_ = _PlayerState.CurrentAimAngle - 180;
            _loc2_ = Math.atan2(_loc4_,_loc3_) * (180 / Math.PI);
         }
         else
         {
            _loc1_ = Math.atan2(-_loc4_,-_loc3_) * (180 / Math.PI) + 180;
            _loc2_ = _PlayerState.CurrentAimAngle + 180;
         }
         _loc6_ = Math.atan(5 / _loc5_) * (180 / Math.PI);
         if(_loc4_ != 0)
         {
            _loc11_ = Math.abs(_loc3_) / Math.abs(_loc4_);
            if(_loc11_ < 1)
            {
               _loc6_ *= _loc11_;
            }
         }
         if(_loc6_ < 1.5)
         {
            _loc6_ = 1.5;
         }
         _BotState.TargetInAim = false;
         if(_loc1_ + _loc6_ < _loc2_)
         {
            SetBotKey(1,false);
            SetBotKey(0,true);
         }
         else if(_loc1_ - _loc6_ > _loc2_)
         {
            SetBotKey(0,false);
            SetBotKey(1,true);
         }
         else
         {
            SetBotKey(1,false);
            SetBotKey(0,false);
            _BotState.TargetInAim = true;
         }
      }
      
      private function CollisionFeetSides(param1:Number = 0, param2:Number = 0) : Boolean
      {
         var _loc3_:int = 0;
         if(param2 == 0)
         {
            param2 = Number(_PlayerState.PlayerEdgeDistance);
         }
         _loc3_ = 2;
         while(_loc3_ <= param2)
         {
            if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x - _loc3_,_this_y + param1,true)) || Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x + _loc3_,_this_y + param1,true)))
            {
               return true;
            }
            if(!_performJumpDownLevel)
            {
               if(Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x - _loc3_,_this_y + param1,true)) || Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x + _loc3_,_this_y + param1,true)))
               {
                  return true;
               }
            }
            _loc3_ += 2;
         }
         return false;
      }
      
      private function BotTargetInMelee() : Boolean
      {
         if(_BotState.TargetPlayer == null)
         {
            return false;
         }
         if(_PlayerState.Jumping)
         {
            return CanKickPlayer(_BotState.TargetPlayer,_PlayerState.Jumping);
         }
         if(CanKickPlayer(_BotState.TargetPlayer,false))
         {
            return true;
         }
         return InMeleeRange(_BotState.TargetPlayer);
      }
      
      private function Dive() : void
      {
         if(!CanDive())
         {
            return;
         }
         KeyTurnPlayer();
         if(!_PlayerState.ShortDiveAvailable)
         {
            _PlayerState.DiveSpeed = 3.5;
         }
         else
         {
            _PlayerState.DiveSpeed = 1;
         }
         _Handler_Sounds.PlaySoundAt("JUMP",PosX(),PosY());
         _PlayerState.Diving = true;
         _PlayerState.Jumping = true;
         _PlayerState.AirVelocityX += _PlayerState.LastDirX * _PlayerState.DiveSpeed;
         _PlayerState.AirVelocityY -= 3;
         _this_y -= 6;
         _this_x += _PlayerState.MovingDirectionX;
         DrainEnergy("SPRINT_DIVE");
      }
      
      private function StaggerCollision(param1:int) : Boolean
      {
         var _loc2_:int = 0;
         _loc2_ = 2;
         while(_loc2_ <= 6)
         {
            if(_static_world_hitbox_mc.hitTestPoint(_this_x + (_loc2_ - 1) * param1,_this_y - 3 - _loc2_,true))
            {
               _staggerFragileObject = m_world.GetGlassAt(_this_x + (_loc2_ - 1) * param1,_this_y - 3 - _loc2_);
               if(_staggerFragileObject == null)
               {
                  return true;
               }
               return false;
            }
            _loc2_ += 2;
         }
         return false;
      }
      
      private function MeleeStrike() : void
      {
         var _loc1_:particle_data = null;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Boolean = false;
         var _loc5_:Number = NaN;
         var _loc6_:Array = null;
         var _loc7_:Array = null;
         var _loc8_:int = 0;
         var _loc9_:int = 0;
         var _loc10_:Boolean = false;
         var _loc11_:Array = null;
         var _loc12_:int = 0;
         var _loc13_:Number = NaN;
         _Handler_Sounds.PlaySoundAt(_PlayerState.MeleeSwingSound,MidPosX(),MidPosY());
         _loc1_ = new particle_data(_PlayerState.MeleeSwingEffect,_this_x,_this_y);
         _loc1_.ScaleX = _PlayerState.LastDirX;
         _Handler_Effects.AddParticle(_loc1_);
         _loc3_ = MidPosY() - 4;
         _loc4_ = false;
         _loc5_ = 4;
         while(_loc5_ <= _PlayerState.MeleeWeaponRange)
         {
            _loc2_ = MidPosX() + _PlayerState.LastDirX * _loc5_;
            if(HitTestWorldOnly(_loc2_,_loc3_))
            {
               _loc4_ = true;
               _loc2_ = MidPosX() + _PlayerState.LastDirX * (_loc5_ + 2);
               _loc5_ = _PlayerState.MeleeWeaponRange + 1;
            }
            _loc5_++;
         }
         if(_loc4_)
         {
            _Handler_Effects.AddParticle(new particle_data("DUST",_loc2_,_loc3_,new b2Vec2(Math.random() * 4 - 2,-Math.random() * 4)));
            _Handler_Effects.AddEffectAt("FIST_IMPACT",_loc2_,_loc3_);
         }
         Kick(true);
         _PlayerState.PunchHitPerformed = true;
         if(_PlayerState.CurrentMeleeWeapon != null)
         {
            DeflectBullets();
         }
         _loc6_ = new Array();
         _loc7_ = EnemiesInMeleeRange();
         _loc8_ = 0;
         while(_loc8_ < _loc7_.length)
         {
            SwapDepths(_loc7_[_loc8_]);
            _loc10_ = false;
            if(_loc7_[_loc8_] > PlayerNr)
            {
               if(Boolean(_players[_loc7_[_loc8_]].PunchReady()))
               {
                  _loc11_ = _players[_loc7_[_loc8_]].EnemiesInMeleeRange();
                  _loc12_ = 0;
                  while(_loc12_ < _loc11_.length)
                  {
                     if(_loc11_[_loc12_] == PlayerNr)
                     {
                        _loc10_ = true;
                        _loc6_.push(_loc7_[_loc8_]);
                     }
                     _loc12_++;
                  }
               }
            }
            if(!_loc10_)
            {
               PunchPlayer(_loc7_[_loc8_]);
            }
            _loc8_++;
         }
         _loc9_ = 0;
         while(_loc9_ < _loc6_.length)
         {
            _loc13_ = Math.random();
            if(_loc13_ < 0.5)
            {
               PunchPlayer(_loc6_[_loc9_]);
            }
            else
            {
               _PlayerState.StunTimer = 2;
               _PlayerState.StunTimer = 2;
            }
            _loc9_++;
         }
         if(_loc7_.length > 0)
         {
            _Handler_Sounds.PlaySoundAt(_PlayerState.MeleeWeaponHitSound,_this_x,_this_y);
            _PlayerAnimation.DelayAnimation(_PlayerState.HitPunchComboFrame,1);
         }
         else if(_button_in_melee_range)
         {
            _Handler_Output.Trace("Pressing Button");
            _Handler_Sounds.PlaySoundAt(_button_to_activate.GetUserData().buttonData.OnActivationSound,MidPosX(),MidPosY());
            _button_to_activate.GetUserData().buttonData.Activate();
         }
      }
      
      private function BotChooseTarget_Tick() : void
      {
         BotChooseTarget();
      }
      
      private function MovePlayer(param1:int, param2:Number) : void
      {
         var _loc3_:int = 0;
         var _loc4_:Number = NaN;
         var _loc5_:int = 0;
         if(!_PlayerState.Staggering)
         {
            if(!_PlayerState.WallJumping && Boolean(_PlayerState.Jumping))
            {
               _PlayerState.MovingDirectionX = param1;
            }
            else if(!_PlayerState.WallJumping)
            {
               this.scaleX = param1;
               _collision_mc.scaleX = this.scaleX;
               _PlayerState.LastDirX = this.scaleX;
               _PlayerState.MovingDirectionX = _PlayerState.LastDirX;
            }
            else
            {
               _PlayerState.LastDirX = this.scaleX;
               _PlayerState.MovingDirectionX = _PlayerState.LastDirX;
            }
         }
         else
         {
            _PlayerState.MovingDirectionX = -_PlayerState.LastDirX;
         }
         if(Boolean(_PlayerState.Kneeling) && !_PlayerState.Rolling)
         {
            if(_PlayerState.CanRoll)
            {
               Roll();
            }
            return;
         }
         _loc3_ = Math.abs(param2 * 10);
         _loc4_ = _PlayerState.MovingDirectionX * 0.1;
         _loc5_ = 1;
         while(_loc5_ <= _loc3_)
         {
            if(WalkCollision(_PlayerState.MovingDirectionX,_PlayerState.Jumping))
            {
               return;
            }
            _this_x += _loc4_ * _game_speed;
            if(_PlayerState.OnGround)
            {
               UpdateSimpleGroundMovement(false);
            }
            _loc5_++;
         }
      }
      
      private function CollisionFeetMid(param1:Number = 0, param2:Number = 0, param3:Boolean = false) : Boolean
      {
         if(Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x,_this_y + param1,true)) && !_performJumpDownLevel)
         {
            return true;
         }
         if(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y + param1,true))
         {
            return true;
         }
         if(param2 != 0)
         {
            if(Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x + param2,_this_y + param1,true)) && !_performJumpDownLevel)
            {
               return true;
            }
            if(_static_world_hitbox_mc.hitTestPoint(_this_x + param2,_this_y + param1,true))
            {
               return true;
            }
            if(Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x - param2,_this_y + param1,true)) && !_performJumpDownLevel)
            {
               return true;
            }
            if(_static_world_hitbox_mc.hitTestPoint(_this_x - param2,_this_y + param1,true))
            {
               return true;
            }
         }
         return false;
      }
      
      private function TurnLeft() : void
      {
         if(_PlayerState.LastDirX == 1)
         {
            this.scaleX = -1;
            _collision_mc.scaleX = this.scaleX;
            _PlayerState.LastDirX = -1;
         }
      }
      
      private function BotStateFollowPath() : void
      {
         var _loc1_:Boolean = false;
         var _loc2_:PathResultNode = null;
         var _loc3_:int = 0;
         var _loc4_:Boolean = false;
         var _loc5_:PathNode = null;
         var _loc6_:* = undefined;
         var _loc7_:Number = NaN;
         var _loc8_:PathNode = null;
         if(_PlayerState.BurnState <= 0)
         {
            SetBotKey(KEY_LEFT,false);
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_UP,false);
            SetBotKey(KEY_DOWN,false);
         }
         if(_PlayerState.Aiming)
         {
            _BotState.Phase = BotState.AIM;
            return;
         }
         if(_BotState.TargetPlayer == null && _BotState.TargetWeapon == null && !_BotState.RunAwayFromHazards)
         {
            _BotState.Phase = BotState.IDLE;
            BotGoForReset();
            return;
         }
         if(_BotState.Path.length <= 0)
         {
            _BotState.RunAwayFromHazards = false;
            _BotState.NextResultNode = null;
            _loc1_ = false;
            if(!BotState.FOLLOW_ONLY)
            {
               if(_BotState.TargetWeapon != null)
               {
                  BotCalculatePathGrid(_pathGrid.GetNodeAt(_BotState.TargetWeapon.GetPosition().x * 30,_BotState.TargetWeapon.GetPosition().y * 30));
                  if(_BotState.Path.length <= 1)
                  {
                     _BotState.Phase = BotState.GRAB_WEAPON;
                     SetBotKey(KEY_UP,false);
                  }
                  else
                  {
                     _loc1_ = true;
                  }
                  return;
               }
               if(_BotState.TargetPlayer != null)
               {
                  BotCalculatePathGrid(_pathGrid.GetNodeAt(_BotState.TargetPlayer.MidPosX(),_BotState.TargetPlayer.MidPosY()));
                  if(_BotState.Path.length <= 1)
                  {
                     _BotState.Phase = BotState.MELEE;
                  }
                  else
                  {
                     _loc1_ = true;
                  }
                  return;
               }
            }
            if(!_loc1_)
            {
               BotGoForReset(true);
               return;
            }
         }
         if(_BotState.Path.length > 0)
         {
            BotCheckPathProgress();
            if(_BotState.Path.length <= 0)
            {
               return;
            }
            _BotState.NextResultNode = _BotState.Path[_BotState.Path.length - 1];
            if(!_PlayerState.Climbing && !_BotState.RunAwayFromHazards && !BotState.FOLLOW_ONLY)
            {
               if(BotTargetInMelee())
               {
                  if(!BotFacingEdgeMelee())
                  {
                     _BotState.Phase = BotState.MELEE;
                  }
                  else if(_PlayerState.Jumping)
                  {
                     SetBotKey(KEY_MELEE,true);
                     SetBotKey(KEY_MELEE,false);
                  }
               }
               else if(Boolean(_PlayerState.OnGround) && Boolean(_BotState.TargetInSight) && _PlayerState.CurrentRangeWeapon != null)
               {
                  if(Math.sqrt(Math.pow(_BotState.TargetPlayer.MidPosX() - MidPosX(),2) + Math.pow(_BotState.TargetPlayer.MidPosY() - MidPosY(),2)) >= _BotState.FollowToAimMinimumDistance)
                  {
                     _BotState.Phase = BotState.AIM;
                     return;
                  }
               }
            }
            _loc2_ = _BotState.NextResultNode;
            if(Boolean(_BotState.DoFireCheck) && !_BotState.RunAwayFromHazards)
            {
               if(_PlayerState.BurnState <= 0)
               {
                  if(_Handler_Fires.PlayerPosInFire(_loc2_.Node.PosX,_loc2_.Node.PosY + 4))
                  {
                     return;
                  }
               }
               _BotState.DoFireCheck = false;
            }
            if(_PlayerState.MovingDirectionInversed != 0)
            {
               _BotState.Path.splice(_BotState.Path.length - 1,1);
               _PlayerState.MovingDirectionInversed = 0;
               return;
            }
            _loc3_ = 0;
            if(PosX() > _loc2_.Node.PosX + BotState.DISTANCE_WALK_TOLERANCE)
            {
               _loc3_ = -1;
            }
            else if(PosX() < _loc2_.Node.PosX - BotState.DISTANCE_WALK_TOLERANCE)
            {
               _loc3_ = 1;
            }
            BotCheckCover();
            _loc4_ = true;
            if(_loc2_.PrevBind != null)
            {
               if(!_loc2_.PrevBind.TargetNodeCloseEnough() && Boolean(_PlayerState.OnGround))
               {
                  _loc3_ = 0;
                  if(PosX() > _loc2_.PrevBind.SourceNode.PosX + BotState.DISTANCE_WALK_TOLERANCE)
                  {
                     _loc3_ = -1;
                  }
                  else if(PosX() < _loc2_.PrevBind.SourceNode.PosX - BotState.DISTANCE_WALK_TOLERANCE)
                  {
                     _loc3_ = 1;
                  }
                  if(_loc3_ == 0)
                  {
                     SetBotKey(KEY_LEFT,false);
                     SetBotKey(KEY_RIGHT,false);
                  }
                  else if(_loc3_ == 1)
                  {
                     SetBotKey(KEY_LEFT,false);
                     SetBotKey(KEY_RIGHT,true);
                  }
                  else
                  {
                     SetBotKey(KEY_LEFT,true);
                     SetBotKey(KEY_RIGHT,false);
                  }
                  SetBotKey(KEY_UP,false);
                  SetBotKey(KEY_DOWN,false);
                  return;
               }
               switch(_loc2_.PrevBind.MovementType)
               {
                  case PathBind.ROAD:
                     break;
                  case PathBind.JUMP:
                     if(_loc2_.Node.PosY < MidPosY())
                     {
                        BotGoForReset();
                     }
                     if(!_PlayerState.Jumping)
                     {
                        SetBotKey(KEY_UP,true);
                        SetBotKey(KEY_UP,false);
                     }
                     else
                     {
                        SetBotKey(KEY_UP,false);
                     }
                     BotWalkAroundJumpObstalce();
                     break;
                  case PathBind.CLOUDDOWN:
                     _loc4_ = false;
                     if(!_keyPressed[KEY_DOWN])
                     {
                        if(!_PlayerState.Jumping)
                        {
                           if(BotCheckStandingOnObject())
                           {
                              return;
                           }
                           SetBotKey(KEY_DOWN,true);
                           SetBotKey(KEY_DOWN,false);
                           SetBotKey(KEY_DOWN,true);
                           SetBotKey(KEY_DOWN,false);
                           return;
                        }
                        SetBotKey(KEY_DOWN,false);
                     }
                     break;
                  case PathBind.DIVE:
                     if(!_PlayerState.Running)
                     {
                        if(_loc3_ == -1)
                        {
                           SetBotKey(KEY_LEFT,false);
                           SetBotKey(KEY_RIGHT,true);
                        }
                        else
                        {
                           SetBotKey(KEY_LEFT,true);
                           SetBotKey(KEY_RIGHT,false);
                        }
                     }
                     else if(!_PlayerState.Sprinting)
                     {
                        _BotState.ActivateSprintCounter -= 1;
                        if(_BotState.ActivateSprintCounter <= 0)
                        {
                           _BotState.ActivateSprintCounter = 2;
                           SetBotKey(KEY_RIGHT,false);
                           SetBotKey(KEY_LEFT,false);
                           return;
                        }
                     }
                     else if(!_PlayerState.Diving && !_PlayerState.ShortDiveAvailable)
                     {
                        SetBotKey(KEY_DOWN,true);
                     }
                     else if(_PlayerState.Diving)
                     {
                        SetBotKey(KEY_DOWN,false);
                     }
                     break;
                  case PathBind.SPRINTJUMP:
                     if(!_PlayerState.Sprinting)
                     {
                        _BotState.ActivateSprintCounter -= 1;
                        if(_BotState.ActivateSprintCounter <= 0)
                        {
                           _BotState.ActivateSprintCounter = 2;
                           SetBotKey(KEY_RIGHT,false);
                           SetBotKey(KEY_LEFT,false);
                           return;
                        }
                     }
                     else if(!_PlayerState.Jumping)
                     {
                        SetBotKey(KEY_UP,true);
                        SetBotKey(KEY_UP,false);
                     }
                     else if(BotObstacleAt(_loc3_))
                     {
                        SetBotKey(KEY_MELEE,true);
                        SetBotKey(KEY_MELEE,false);
                     }
                     break;
                  case PathBind.ROLL:
                     SetBotKey(KEY_DOWN,true);
                     break;
                  case PathBind.LADDER:
                     if(_loc2_.Node.PosY < _loc2_.PrevBind.SourceNode.PosY && !_loc2_.PrevBind.Blocked)
                     {
                        if(Boolean(_PlayerState.Climbing) && !_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY() - 1,true))
                        {
                           SetBotKey(KEY_UP,false);
                           SetBotKey(KEY_UP,true);
                        }
                        if(_BotState.TargetPlayer != null)
                        {
                           if(_BotState.TargetPlayer.MidPosY() < MidPosY())
                           {
                              _loc6_ = false;
                              _loc7_ = Math.abs(MidPosX() - _BotState.TargetPlayer.MidPosX());
                              if(_loc7_ < 35)
                              {
                                 if(!_PlayerState.Climbing)
                                 {
                                    BotGoForReset(true);
                                    SetBotKey(KEY_UP,false);
                                    SetBotKey(KEY_DOWN,false);
                                    return;
                                 }
                                 SetBotKey(KEY_UP,false);
                                 SetBotKey(KEY_DOWN,true);
                              }
                           }
                        }
                        SetBotKey(KEY_UP,true);
                        _loc5_ = _loc2_.PrevBind.SourceNode;
                        if(_loc2_.Node.PosY - MidPosY() >= BotState.DISTANCE_LADDER_TOLERANCE_Y)
                        {
                           _loc5_ = _loc2_.Node;
                        }
                        if(PosX() > _loc5_.PosX + BotState.DISTANCE_LADDER_TOLERANCE_X)
                        {
                           SetBotKey(KEY_LEFT,true);
                           SetBotKey(KEY_RIGHT,false);
                        }
                        else if(PosX() < _loc5_.PosX - BotState.DISTANCE_LADDER_TOLERANCE_X)
                        {
                           SetBotKey(KEY_LEFT,false);
                           SetBotKey(KEY_RIGHT,true);
                        }
                        else
                        {
                           SetBotKey(KEY_LEFT,false);
                           SetBotKey(KEY_RIGHT,false);
                        }
                        return;
                     }
                     _loc8_ = _loc2_.Node;
                     SetBotKey(KEY_DOWN,true);
                     if(PosX() > _loc8_.PosX + BotState.DISTANCE_LADDER_TOLERANCE_X)
                     {
                        SetBotKey(KEY_LEFT,true);
                        SetBotKey(KEY_RIGHT,false);
                     }
                     else if(PosX() < _loc8_.PosX - BotState.DISTANCE_LADDER_TOLERANCE_X)
                     {
                        SetBotKey(KEY_LEFT,false);
                        SetBotKey(KEY_RIGHT,true);
                     }
                     else
                     {
                        SetBotKey(KEY_LEFT,false);
                        SetBotKey(KEY_RIGHT,false);
                     }
                     if(Boolean(_PlayerState.OnGround) && Boolean(_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY() - 1,true)))
                     {
                        BotGoForReset();
                     }
                     return;
               }
            }
            else
            {
               BotGoForReset();
            }
            if(_PlayerState.AirVelocityY >= 0 && !_PlayerState.OnGround && Boolean(_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY() - 1,true)))
            {
               SetBotKey(KEY_DOWN,true);
               SetBotKey(KEY_UP,false);
               return;
            }
            if(_loc4_)
            {
               if(Boolean(BotCloudAbove()) && Boolean(_PlayerState.OnGround) && Math.random() < 0.5)
               {
                  if(BotObstacleAt(_loc3_))
                  {
                     if(Boolean(_BotState.PreferJumpOverObstacle) && !_PlayerState.Jumping)
                     {
                        SetBotKey(KEY_UP,true);
                        SetBotKey(KEY_UP,false);
                     }
                     else
                     {
                        SetBotKey(KEY_MELEE,true);
                        SetBotKey(KEY_MELEE,false);
                     }
                  }
               }
               else
               {
                  BotCheckObstacle(_loc3_);
               }
            }
            if(_PlayerState.Climbing)
            {
               SetBotKey(KEY_DOWN,true);
               SetBotKey(KEY_UP,false);
               return;
            }
            if(_loc3_ == -1)
            {
               SetBotKey(KEY_LEFT,true);
               SetBotKey(KEY_RIGHT,false);
            }
            else if(_loc3_ == 1)
            {
               SetBotKey(KEY_LEFT,false);
               SetBotKey(KEY_RIGHT,true);
            }
            else if(MidPosY() - _loc2_.Node.PosY >= 22)
            {
               _BotState.NextResultNode = null;
               BotChooseTarget();
            }
            else if(Boolean(_PlayerState.OnGround) || Boolean(_PlayerState.Climbing))
            {
               if(MidPosY() - _loc2_.Node.PosY >= 0)
               {
                  if(!_PlayerState.Jumping)
                  {
                     SetBotKey(KEY_UP,false);
                     SetBotKey(KEY_UP,true);
                  }
               }
               else
               {
                  BotCheckStandingOnObject();
               }
               BotGoForReset();
            }
         }
      }
      
      private function BotStateGrabWeapon() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Boolean = false;
         if(_BotState.TargetWeapon == null)
         {
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_LEFT,false);
            SetBotKey(KEY_DOWN,false);
            SetBotKey(KEY_MELEE,false);
            BotGoForReset(true);
            _BotState.Phase = BotState.IDLE;
            return;
         }
         _loc1_ = _BotState.TargetWeapon.GetPosition().x * 30 - MidPosX();
         _loc2_ = _BotState.TargetWeapon.GetPosition().y * 30 - MidPosY();
         _loc3_ = Math.sqrt(_loc1_ * _loc1_ + _loc2_ * _loc2_);
         _loc4_ = 2;
         if(_PlayerState.OnGround)
         {
            _loc4_ = _BotState.TargetWeapon.GetUserData().weaponData.Properties.PickupRadius * 0.5;
         }
         SetBotKey(KEY_UP,false);
         _loc5_ = false;
         if(_loc1_ > _loc4_)
         {
            SetBotKey(KEY_RIGHT,true);
            SetBotKey(KEY_LEFT,false);
            BotCheckObstacle(_loc1_ / Math.abs(_loc1_));
         }
         else if(_loc1_ < -_loc4_)
         {
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_LEFT,true);
            BotCheckObstacle(_loc1_ / Math.abs(_loc1_));
         }
         else
         {
            _loc5_ = true;
            SetBotKey(KEY_RIGHT,false);
            SetBotKey(KEY_LEFT,false);
            if(_PlayerState.OnGround)
            {
               if(BotCheckStandingOnObject())
               {
                  return;
               }
            }
         }
         if(_PlayerState.Climbing)
         {
            SetBotKey(KEY_UP,false);
            SetBotKey(KEY_DOWN,true);
            return;
         }
         if(_PlayerState.OnGround)
         {
            if(_loc3_ <= _BotState.TargetWeapon.GetUserData().weaponData.Properties.PickupRadius * 0.7)
            {
               SetBotKey(KEY_RIGHT,false);
               SetBotKey(KEY_LEFT,false);
               if(!_PlayerState.Kneeling)
               {
                  DisableJumpDownLevel();
                  SetBotKey(KEY_DOWN,true);
                  return;
               }
               SetBotKey(KEY_MELEE,true);
               BotGoForReset();
            }
            else if(_loc5_)
            {
               SetBotKey(KEY_RIGHT,false);
               SetBotKey(KEY_LEFT,false);
               SetBotKey(KEY_DOWN,false);
               SetBotKey(KEY_MELEE,false);
               BotGoForReset(true);
               _BotState.Phase = BotState.IDLE;
               return;
            }
         }
      }
      
      private function BotFacingEdgeMelee(param1:int = 1) : Boolean
      {
         return DetectEdge(_PlayerState.LastDirX * param1,18,true);
      }
      
      public function get PortalDirectionX() : int
      {
         return _PlayerState.PortalDirectionX;
      }
      
      private function Kick(param1:Boolean = false, param2:Boolean = false) : Boolean
      {
         var _loc3_:Boolean = false;
         var _loc4_:Number = NaN;
         var _loc5_:b2Body = null;
         var _loc6_:int = 0;
         var _loc7_:Boolean = false;
         var _loc8_:* = undefined;
         var _loc9_:b2Vec2 = null;
         var _loc10_:b2Vec2 = null;
         var _loc11_:Number = NaN;
         var _loc12_:Number = NaN;
         var _loc13_:int = 0;
         if(!param1 && !param2)
         {
            if(_PlayerState.KickingCooldown > 0)
            {
               return false;
            }
         }
         _loc3_ = false;
         _loc6_ = 0;
         while(_loc6_ < m_world.DynamicObjectList.length)
         {
            _loc5_ = m_world.DynamicObjectList[_loc6_];
            if(Boolean(_loc5_.m_userData.objectData.Kickable))
            {
               if(KickHit(_loc5_,param1,param2))
               {
                  if(_loc5_.m_userData.objectData.KickPower == 0)
                  {
                     if(Boolean(_loc5_.m_userData.objectData.KickWeightCalculation))
                     {
                        _loc4_ = _PlayerState.KickPower * _loc5_.GetMass();
                     }
                     else
                     {
                        _loc4_ = Number(_PlayerState.KickPower);
                     }
                  }
                  else if(Boolean(_loc5_.m_userData.objectData.KickWeightCalculation))
                  {
                     _loc4_ = _loc5_.m_userData.objectData.KickPower * _loc5_.GetMass();
                  }
                  else
                  {
                     _loc4_ = Number(_loc5_.m_userData.objectData.KickPower);
                  }
                  _loc9_ = _loc9_ = new b2Vec2(_PlayerState.LastDirX * _loc4_,-_loc4_);
                  _loc10_ = _loc5_.GetPosition();
                  _loc5_.ApplyImpulse(_loc9_,_loc10_);
                  _loc10_ = new b2Vec2((_this_x + _PlayerState.LastDirX * 4) / 30,(_this_y - 4) / 30);
                  if(_loc5_.GetMass() < 1)
                  {
                     _loc9_ = new b2Vec2(0,-0.4 * _loc5_.GetMass());
                  }
                  else
                  {
                     _loc9_ = new b2Vec2(0,-0.4);
                  }
                  _loc5_.ApplyImpulse(_loc9_,_loc10_);
                  _loc11_ = _loc5_.GetPosition().x * 30;
                  if(Math.abs(_this_x - _loc11_) > _PlayerState.MeleeWeaponRange)
                  {
                     _loc11_ = MidPosX() + _PlayerState.LastDirX * _PlayerState.MeleeWeaponRange;
                  }
                  if(param1)
                  {
                     _loc5_.GetUserData().objectData.Damage_Impact(_PlayerState.HitPunchDamage);
                     _Handler_Sounds.PlaySoundAt(_PlayerState.GetMeleeMaterialHitSound(_loc5_.GetUserData().material.Type),MidPosX(),MidPosY());
                     _loc12_ = 4;
                     while(_loc12_ <= _PlayerState.MeleeWeaponRange)
                     {
                        if(Boolean(_loc5_.m_userData.objectData.ShapeMC.hitTestPoint(MidPosX() + _PlayerState.LastDirX * _loc12_,_this_y - 12,true)))
                        {
                           _loc11_ = MidPosX() + _PlayerState.LastDirX * _loc12_;
                           _loc12_ = _PlayerState.MeleeWeaponRange + 1;
                        }
                        _loc12_++;
                     }
                     _Handler_Effects.AddEffectAt("FIST_IMPACT",_loc11_,_this_y - 12);
                     _Handler_Effects.AddEffectAt(_PlayerState.GetMeleeMaterialHitEffect(_loc5_.GetUserData().material.Type),_loc11_,_this_y - 12);
                  }
                  else
                  {
                     if(param2)
                     {
                        _loc5_.GetUserData().objectData.Damage_Impact(_PlayerState.JumpKickDamage);
                     }
                     else
                     {
                        _loc5_.GetUserData().objectData.Damage_Impact(_PlayerState.KickDamage);
                     }
                     _Handler_Sounds.PlaySoundAt(_PlayerState.GetKickMaterialHitSound(_loc5_.GetUserData().material.Type),MidPosX(),MidPosY());
                     _loc12_ = 4;
                     while(_loc12_ <= _PlayerState.MeleeWeaponRange)
                     {
                        if(Boolean(_loc5_.m_userData.objectData.ShapeMC.hitTestPoint(MidPosX() + _PlayerState.LastDirX * _loc12_,_this_y - 6,true)))
                        {
                           _loc11_ = MidPosX() + _PlayerState.LastDirX * _loc12_;
                           _loc12_ = _PlayerState.MeleeWeaponRange + 1;
                        }
                        _loc12_++;
                     }
                     _Handler_Effects.AddEffectAt(_PlayerState.GetKickMaterialHitEffect(_loc5_.GetUserData().material.Type),_loc11_,_this_y - 6);
                     _Handler_Effects.AddEffectAt("KICK_IMPACT",_loc11_,_this_y - 6);
                     _loc3_ = true;
                  }
               }
            }
            _loc6_++;
         }
         if(_loc3_)
         {
            if(param1)
            {
               _loc13_ = 1;
               while(_loc13_ <= 2)
               {
                  _Handler_Effects.AddParticle(new particle_data("DUST",_this_x + _PlayerState.LastDirX * (6 + Math.random() * 2),_this_y - 10 - Math.random() * 2,new b2Vec2(_PlayerState.LastDirX * Math.random() * 4,-Math.random() * 4)));
                  _loc13_++;
               }
            }
            else
            {
               _loc13_ = 1;
               while(_loc13_ <= 2)
               {
                  _Handler_Effects.AddParticle(new particle_data("DUST",_this_x + _PlayerState.LastDirX * (6 + Math.random() * 2),_this_y - 3 - Math.random() * 2,new b2Vec2(_PlayerState.LastDirX * Math.random() * 4,-Math.random() * 4)));
                  _loc13_++;
               }
            }
         }
         if(param1)
         {
            return false;
         }
         _loc7_ = false;
         _loc8_ = 0;
         while(_loc8_ < _players.length)
         {
            if(_loc8_ != PlayerNr)
            {
               if(Team != _players[_loc8_].Team)
               {
                  if(CanKickPlayer(_players[_loc8_],param2))
                  {
                     _loc7_ = true;
                     SwapDepths(_loc8_);
                     if(_players[_loc8_].State.HP > 0)
                     {
                        if(param2)
                        {
                           _players[_loc8_].State.HP -= _PlayerState.JumpKickDamage;
                        }
                        else
                        {
                           _players[_loc8_].State.HP -= _PlayerState.KickDamage;
                        }
                        if(_players[_loc8_].State.HP <= 0)
                        {
                           if(ActivateSlowmotion(_loc8_))
                           {
                              _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
                           }
                           _players[_loc8_].BeingKicked(_PlayerState.LastDirX);
                        }
                        else
                        {
                           _players[_loc8_].BeingKicked(_PlayerState.LastDirX,param2);
                        }
                     }
                     else
                     {
                        _players[_loc8_].BeingKicked(_PlayerState.LastDirX);
                     }
                  }
               }
            }
            _loc8_++;
         }
         if(_loc7_)
         {
            _Handler_Sounds.PlaySoundAt("kick",_this_x,_this_y);
            _Handler_Effects.AddEffectAt("KICK_IMPACT",_this_x + _PlayerState.LastDirX * 6,_this_y - 2);
         }
         if(_loc3_ || _loc7_)
         {
            _PlayerAnimation.ShowAnimation("kick",true);
            _PlayerState.Kicking = true;
            if(!param1 && !param2)
            {
               _Handler_Sounds.PlaySoundAt("KICK_SWING",PosX(),PosY());
            }
            return true;
         }
         return false;
      }
      
      public function StuckToProjectile(param1:ProjectileData) : void
      {
         if(!_PlayerState.StuckToRocket)
         {
            DropGrabbedPlayer();
            Disarm();
            CancelAFS();
            _PlayerState.StuckToRocket = true;
            _PlayerState.BurnState = 0;
         }
         _PlayerState.LastDirX = 1;
         this.scaleX = 1;
         _collision_mc.scaleX = 1;
         _PlayerState.RocketRideTimer = 0;
         _PlayerState.RocketRideProjectile = param1;
         _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,12,6,0.01));
      }
      
      public function ActivateSlowmotion(param1:Number) : Boolean
      {
         var _loc2_:int = 0;
         var _loc3_:Array = null;
         var _loc4_:int = 0;
         var _loc5_:Boolean = false;
         var _loc6_:int = 0;
         _loc2_ = 0;
         _loc3_ = new Array();
         _loc4_ = 0;
         while(_loc4_ < _players.length)
         {
            if(_players[_loc4_].State.HP > 0)
            {
               if(_players[_loc4_].Team != _players[param1].Team)
               {
                  _loc5_ = false;
                  _loc6_ = 0;
                  while(_loc6_ < _loc3_.length)
                  {
                     if(_loc3_[_loc6_] == _players[_loc4_].Team)
                     {
                        _loc5_ = true;
                        _loc6_ = int(_loc3_.length);
                     }
                     _loc6_++;
                  }
                  if(!_loc5_)
                  {
                     _loc2_++;
                     _loc3_.push(_players[_loc4_].Team);
                     if(_loc2_ >= 2)
                     {
                        return false;
                     }
                  }
               }
               else if(_playerNr != _loc4_)
               {
                  return false;
               }
            }
            _loc4_++;
         }
         return true;
      }
      
      private function DrainEnergy(param1:String) : void
      {
         switch(param1)
         {
            case "SPRINT_JUMP":
               _PlayerState.SprintEnergy -= 12;
               break;
            case "JUMP":
               _PlayerState.SprintEnergy -= 5;
               break;
            case "SPRINT_DIVE":
               _PlayerState.SprintEnergy -= 12;
               break;
            case "ROLL":
               _PlayerState.SprintEnergy -= 5;
         }
      }
      
      public function get Team() : int
      {
         return _team;
      }
      
      private function BotStandingOnObjectAtX(param1:Number) : Boolean
      {
         var _loc2_:Number = NaN;
         _loc2_ = 0;
         while(_loc2_ <= 2)
         {
            if(_static_objects_hitbox_mc.hitTestPoint(_this_x + param1,_this_y + _loc2_,true))
            {
               return true;
            }
            _loc2_ += 2;
         }
         return false;
      }
      
      public function GiveStartItems(param1:WeaponData = null, param2:WeaponThrowableData = null, param3:WeaponMeleeData = null, param4:WeaponPowerupData = null) : void
      {
         _PlayerState.CurrentRangeWeapon = param1;
         _PlayerState.CurrentThrowableWeapon = param2;
         _PlayerState.CurrentMeleeWeapon = param3;
         _PlayerState.CurrentPowerupWeapon = param4;
      }
      
      private function UpdateStairBounce() : void
      {
         if(_PlayerState.StairBounce)
         {
            _PlayerState.AirVelocityX = _PlayerState.StairVelocityX;
            _PlayerState.AirVelocityY = _PlayerState.StairVelocityY;
            _Handler_Sounds.PlaySoundAt("STAIRBOUNCE",_this_x,_this_y);
            _PlayerState.Knockdowned = false;
            _PlayerState.Jumping = true;
            _PlayerState.Falling = true;
            _PlayerState.StairBounce = false;
            _PlayerState.DecreaseBurnState();
            if(_PlayerState.HP > 0)
            {
               _PlayerState.HP -= _PlayerState.StairBounceDamage;
               if(_PlayerState.HP <= 0)
               {
                  if(ActivateSlowmotion(PlayerNr))
                  {
                     _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
                  }
               }
            }
         }
      }
      
      private function UpdateSides(param1:Boolean = true) : void
      {
         var _loc2_:Boolean = false;
         var _loc3_:Boolean = false;
         var _loc4_:int = 0;
         var _loc5_:b2Vec2 = null;
         var _loc6_:int = 0;
         if(CanLandInMid())
         {
            _loc4_ = -_PlayerState.PlayerEdgeDistance - 1;
            while(_loc4_ <= _PlayerState.PlayerEdgeDistance + 1)
            {
               b = GetDynamicBodyAt(_this_x + _loc4_,_this_y - _PlayerState.PlayerHeight,false);
               if(b != null)
               {
                  if(Boolean(b.GetUserData().objectData.CanGibb))
                  {
                     _loc5_ = b.GetLinearVelocity();
                     if(Math.abs(_loc5_.x) > 0.1)
                     {
                        if(CheckCollisionTowardsPlayer(b.GetPosition().x * 30,_this_x,ConvertToDirection(_loc5_.x)))
                        {
                           return;
                        }
                     }
                  }
               }
               _loc4_ += _PlayerState.PlayerEdgeDistance + 1;
            }
         }
         _loc2_ = Boolean(CollisionSide(1));
         _loc3_ = Boolean(CollisionSide(-1));
         if(_loc2_ || _loc3_)
         {
            _loc6_ = 1;
            while(_loc6_ <= _PlayerState.PlayerEdgeDistance * 10)
            {
               _loc2_ = Boolean(CollisionSide(1,_loc6_ / 10));
               _loc3_ = Boolean(CollisionSide(-1,_loc6_ / 10));
               if(!(_loc3_ && _loc2_))
               {
                  if(_loc2_)
                  {
                     if(!WorldCollisionSide(-1,_PlayerState.PlayerEdgeDistance))
                     {
                        _this_x -= 0.1;
                        if(param1)
                        {
                           _PlayerState.AirVelocityX -= 0.02;
                        }
                     }
                     else
                     {
                        _this_x += 0.1;
                        if(param1)
                        {
                           _PlayerState.AirVelocityX += 0.02;
                        }
                     }
                  }
                  else if(_loc3_)
                  {
                     if(!WorldCollisionSide(1,_PlayerState.PlayerEdgeDistance))
                     {
                        _this_x += 0.1;
                        if(param1)
                        {
                           _PlayerState.AirVelocityX += 0.02;
                        }
                     }
                     else
                     {
                        _this_x -= 0.1;
                        if(param1)
                        {
                           _PlayerState.AirVelocityX -= 0.02;
                        }
                     }
                  }
               }
               _loc6_++;
            }
            _PlayerState.AirVelocityX *= 0.9;
         }
      }
      
      private function MoveDirection(param1:int) : void
      {
         if(_PlayerState.TakingCover)
         {
            if(_PlayerState.LastDirX == param1)
            {
               _PlayerState.Running = false;
               return;
            }
            _PlayerState.TakingCover = false;
         }
         if(!_PlayerState.Running && Boolean(_PlayerState.OnGround))
         {
            if(CanTakeCover(param1))
            {
               _PlayerState.TakingCover = true;
               b = GetDynamicBodyAt(_this_x + param1 * _PlayerState.PlayerEdgeDistance + param1 * 4,MidPosY(),false);
               if(b != null)
               {
                  _PlayerState.Box2DCover = b;
                  _PlayerState.CoverObjectID = b.GetUserData().IDNumber;
               }
               else
               {
                  b = GetStaticCoverAt(_this_x + param1 * _PlayerState.PlayerEdgeDistance + param1 * 4,MidPosY());
                  if(b != null)
                  {
                     _PlayerState.Box2DCover = null;
                     _PlayerState.CoverObjectID = b.GetUserData().IDNumber;
                  }
               }
            }
         }
         _PlayerState.Running = true;
         if(_PlayerState.WallJumping)
         {
            MovePlayer(param1,_PlayerState.WallJumpSpeed * param1 + _PlayerState.LastDirX);
         }
         else
         {
            MovePlayer(param1,_PlayerState.RunSpeed * param1);
         }
      }
      
      private function StopStaggerFunc() : void
      {
         if(_PlayerState.HP <= 0)
         {
            Fall(false);
            return;
         }
         b = m_world.GetStairBodyAt(_this_x,_this_y + 2);
         if(b == null)
         {
            b = m_world.GetStairBodyAt(_this_x,_this_y + 4);
         }
         if(b != null)
         {
            if(CanBounceAtDirection(ConvertToDirection(b.GetUserData().tiltValue)))
            {
               Fall(false);
               _PlayerState.StairBounce = true;
               if(_PlayerState.StairVelocityY < -4)
               {
                  _PlayerState.StairVelocityY = -4;
               }
               else if(_PlayerState.StairVelocityY > -1)
               {
                  _PlayerState.StairVelocityY = -1;
               }
               _PlayerState.StairVelocityX = b.GetUserData().tiltValue;
            }
         }
      }
      
      private function AimIdle() : void
      {
         _PlayerState.ResetChangePitchSpeed();
      }
      
      private function PlayerOutsideLevel() : Boolean
      {
         if(_this_x < _MapArea.Left || _this_x > _MapArea.Right || _this_y > _MapArea.Bottom)
         {
            return true;
         }
         return false;
      }
      
      private function AimUp(param1:Number = 0) : void
      {
         if(_PlayerState.CurrentAimPitch > -_PlayerState.UpperAimPitch)
         {
            if(param1 != 0)
            {
               _PlayerState.CurrentChangePitchSpeed = -param1;
            }
            if(_PlayerState.CurrentChangePitchSpeed > 0)
            {
               _PlayerState.CurrentChangePitchSpeed = 0;
            }
            _PlayerState.CurrentAimPitch += _PlayerState.CurrentChangePitchSpeed * _game_speed;
            _PlayerState.CurrentChangePitchSpeed -= 2;
            if(_PlayerState.CurrentAimPitch < -_PlayerState.UpperAimPitch)
            {
               _PlayerState.CurrentAimPitch = -_PlayerState.UpperAimPitch;
            }
         }
      }
      
      public function GibPlayer() : void
      {
         if(ActivateSlowmotion(PlayerNr))
         {
            _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
         }
         Disarm();
         CancelAFS();
         _Handler_Maps.Handler_WorldItems.AddBox("char_gib_01",(_this_x + Math.random() * 8 - 4) / 30,(_this_y - 1) / 30,Math.random() * Math.PI,new b2Vec2(Math.random() * 6 - 3,-Math.random() * 4 + 3),Math.random() * Math.PI - Math.PI / 2);
         _Handler_Maps.Handler_WorldItems.AddBox("char_gib_02",(_this_x + Math.random() * 8 - 4) / 30,(_this_y - 2) / 30,Math.random() * Math.PI,new b2Vec2(Math.random() * 6 - 3,-Math.random() * 4 + 3),Math.random() * Math.PI - Math.PI / 2);
         _Handler_Maps.Handler_WorldItems.AddBox("char_gib_03",(_this_x + Math.random() * 8 - 4) / 30,(_this_y - 5) / 30,Math.random() * Math.PI,new b2Vec2(Math.random() * 6 - 3,-Math.random() * 4 + 3),Math.random() * Math.PI - Math.PI / 2);
         _Handler_Maps.Handler_WorldItems.AddBox("char_gib_04",(_this_x + Math.random() * 8 - 4) / 30,(_this_y - 7) / 30,Math.random() * Math.PI,new b2Vec2(Math.random() * 6 - 3,-Math.random() * 4 + 3),Math.random() * Math.PI - Math.PI / 2);
         _Handler_Maps.Handler_WorldItems.AddBox("char_gib_05",(_this_x + Math.random() * 8 - 4) / 30,(_this_y - 8) / 30,Math.random() * Math.PI,new b2Vec2(Math.random() * 6 - 3,-Math.random() * 4 + 3),Math.random() * Math.PI - Math.PI / 2);
         _Handler_Effects.AddEffectAt("gib",_this_x,_this_y);
         _Handler_Sounds.PlaySoundAt("gib",_this_x,_this_y);
         IgnorePlayer();
         _PlayerState.CameraIgnoreTimer = 24 * 2;
         _PlayerState.Gone = true;
         _char_gui.visible = false;
         _blood_gui.visible = false;
         _gui_mc.gib_pic.alpha = 1;
         _PlayerState.BurnState = 0;
         _Handler_Output.Trace("Gib player");
      }
      
      private function CheckGibPlayer() : Boolean
      {
         var _loc1_:int = 0;
         if(Boolean(_PlayerState.OnGround) && Boolean(_PlayerState.Knockdowned))
         {
            b = GetDynamicBodyAt(_this_x,_this_y - 6,false);
            if(b != null)
            {
               if(Boolean(b.GetUserData().objectData.CanGibb))
               {
                  _loc1_ = 4;
                  while(_loc1_ >= 1)
                  {
                     if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y + _loc1_,true)) || Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x,_this_y + _loc1_,true)))
                     {
                        if(!b.GetUserData().objectData.CollisionMC.hitTestPoint(_this_x,_this_y + _loc1_,true))
                        {
                           GibPlayer();
                           return true;
                        }
                     }
                     _loc1_--;
                  }
               }
            }
         }
         return false;
      }
      
      public function get CanBePunched() : Boolean
      {
         if(_PlayerState.IsImmune)
         {
            return false;
         }
         if(_PlayerState.Gone)
         {
            return false;
         }
         if(_PlayerState.KnockdownGrade >= 3 && Boolean(_PlayerState.Falling))
         {
            return false;
         }
         if(Boolean(_PlayerState.Knockdowned) && Boolean(_PlayerState.OnGround))
         {
            if(_PlayerAnimation.CurrentFrame < 10)
            {
               return false;
            }
         }
         return !_PlayerState.GrabbedByPlayer;
      }
      
      private function UpdatePlayerFallingOnPlayer() : void
      {
         var _loc1_:* = undefined;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         if(_PlayerState.TotalAirVelocity >= 6 && Boolean(_PlayerState.Falling))
         {
            _loc1_ = 0;
            while(_loc1_ < _players.length)
            {
               if(_loc1_ != PlayerNr)
               {
                  if(Boolean(_players[_loc1_].CanBeKnockedByFlyingPlayer()))
                  {
                     if(this.hitTestObject(_players[_loc1_].MC))
                     {
                        _loc2_ = _players[_loc1_].MidPosX() - MidPosX();
                        _loc3_ = _players[_loc1_].MidPosY() - MidPosY();
                        if(Math.sqrt(_loc2_ * _loc2_ + _loc3_ * _loc3_) <= 12)
                        {
                           _loc4_ = Number(_players[_loc1_].State.AirVelocityY);
                           _players[_loc1_].State.AirVelocityY = _PlayerState.AirVelocityY * 0.9;
                           _PlayerState.AirVelocityY = _loc4_ * 0.9;
                           _loc4_ = Number(_players[_loc1_].State.AirVelocityX);
                           _players[_loc1_].State.AirVelocityX = _PlayerState.AirVelocityX * 0.9;
                           _PlayerState.AirVelocityX = _loc4_ * 0.9;
                           _players[_loc1_].Fall(false);
                        }
                     }
                  }
               }
               _loc1_++;
            }
         }
      }
      
      private function SidewayBounce() : Boolean
      {
         var _loc1_:Number = NaN;
         if(Math.abs(_PlayerState.AirVelocityX) >= 4 && Math.abs(_PlayerState.AirVelocityX) > Math.abs(_PlayerState.AirVelocityY))
         {
            _Handler_Sounds.PlaySoundAt("BODYFALL",_this_x,_this_y);
            BodyDust();
            _loc1_ = Number(_PlayerState.TotalAirVelocity);
            _PlayerState.AirVelocityY = -_loc1_ * 0.3;
            _PlayerState.AirVelocityX = _loc1_ * 0.5 * ConvertToDirection(_PlayerState.AirVelocityX);
            _PlayerState.LastDirX *= -1;
            if(_PlayerState.AirVelocityY > -2)
            {
               _PlayerState.AirVelocityY = -2;
            }
            return true;
         }
         return false;
      }
      
      public function MidPosY() : Number
      {
         if(_PlayerState.Diving)
         {
            return _this_y;
         }
         if(_PlayerState.Knockdowned)
         {
            return _this_y - 3;
         }
         if(Boolean(_PlayerState.Kneeling) || Boolean(_PlayerState.Falling))
         {
            return _this_y - 6;
         }
         return _this_y - 8;
      }
      
      private function CheckCollisionTowardsPlayer(param1:Number, param2:Number, param3:int) : Boolean
      {
         if(param3 == 1 && param1 < param2 + 4)
         {
            return true;
         }
         if(param3 == -1 && param1 > param2 - 4)
         {
            return true;
         }
         return false;
      }
      
      private function AimLeft() : void
      {
         if(_PlayerState.LastDirX == 1)
         {
            _PlayerState.FastTrigger = false;
            _lazer_mc.visible = false;
            _aim_mc.visible = false;
            CancelAFS();
            _PlayerState.AimTurningAround = true;
            this.scaleX = -1;
            _collision_mc.scaleX = this.scaleX;
            _PlayerState.LastDirX = -1;
            _PlayerState.CurrentAimPitch = 0;
            _PlayerState.CurrentChangePitchSpeed = 0;
         }
      }
      
      private function BeingKicked(param1:int, param2:Boolean = false) : void
      {
         var _loc3_:int = 0;
         DropGrabbedPlayer();
         _loc3_ = int(_PlayerState.LastDirX);
         _PlayerState.LastDirX = -param1;
         CheckAimDrop(true);
         if(!_PlayerState.Burned)
         {
            _Handler_Effects.AddParticle(new particle_data("PARTICLE_BLOOD",PosX(),PosY() - 13,new b2Vec2(param1,-0.5),0,1,[Math.floor(Math.random() * 1.99)]));
         }
         else
         {
            _Handler_Effects.AddEffectAt("PLAYER_BURNED_HITDEFAULT",PosX(),PosY() - 13);
         }
         if(Math.random() < 0.5 || !param2)
         {
            _PlayerState.LastDirX = _loc3_;
            Fall();
         }
         else
         {
            this.scaleX = _PlayerState.LastDirX;
            StartStagger();
         }
         _PlayerState.AirVelocityX = param1 * 4;
         _PlayerState.AirVelocityY = -2;
      }
      
      public function BulletWillHit() : Boolean
      {
         if(_PlayerState.IsImmune)
         {
            return false;
         }
         if(Boolean(_PlayerState.Rolling) || Boolean(_PlayerState.Diving))
         {
            if(Math.random() < 0.9)
            {
               return false;
            }
         }
         return true;
      }
      
      private function AimLazer() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Point = null;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Array = null;
         var _loc8_:int = 0;
         if(_char.ANIM_WPN == null)
         {
            return;
         }
         if(!_bot)
         {
            _loc1_ = _char.ANIM_WPN.x * _PlayerState.LastDirX + PosX();
            _loc2_ = _char.ANIM_WPN.y + PosY();
            _loc1_ += Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.AIM_POSITION.x;
            _loc2_ += Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.AIM_POSITION.x;
            _loc2_ += Math.sin((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.AIM_POSITION.y * _PlayerState.LastDirX;
            _loc1_ += Math.cos((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.AIM_POSITION.y * _PlayerState.LastDirX;
            _loc3_ = _Handler_ProjectilesUpdater.CalculateAimSquare(new Point(_loc1_,_loc2_),_PlayerState.CurrentAimAngle,_PlayerState.CoverObjectID,AIM_SQUARE_DISTANCE,CollisionMC);
            _aim_mc.x = _loc3_.x;
            _aim_mc.y = _loc3_.y;
            _aim_mc.visible = true;
         }
         if(_PlayerState.AimMode == 0)
         {
            if(_PlayerState.CurrentRangeWeapon.Properties.LaserSight)
            {
               ClearLazerPoints();
               _loc4_ = _char.ANIM_WPN.x * _PlayerState.LastDirX + PosX();
               _loc5_ = _char.ANIM_WPN.y + PosY();
               _loc4_ += Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.LAZER_CENTER.x;
               _loc5_ += Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.LAZER_CENTER.x;
               _loc5_ += Math.sin((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.LAZER_CENTER.y * _PlayerState.LastDirX;
               _loc4_ += Math.cos((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.LAZER_CENTER.y * _PlayerState.LastDirX;
               _lazer_rnd = Math.random() * Math.PI * 2;
               _loc6_ = Math.sin(_lazer_rnd) * _PlayerState.CurrentRangeWeapon.Properties.LaserDeflection;
               _loc7_ = _Handler_ProjectilesUpdater.CalculateLazer(new Point(_loc4_,_loc5_),_PlayerState.CurrentAimAngle + _loc6_,_PlayerState.CoverObjectID,CollisionMC);
               _loc8_ = 0;
               while(_loc8_ < _loc7_.length)
               {
                  AddLazerPoint(_loc7_[_loc8_]);
                  _loc8_++;
               }
               _lazer_mc.visible = true;
            }
         }
      }
      
      public function MidPosX() : Number
      {
         return _this_x;
      }
      
      private function DropThrowable() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         if(_PlayerState.Throwing)
         {
            _PlayerState.Aiming = false;
            _PlayerState.Throwing = false;
            return;
         }
         _loc1_ = (MidPosX() - _PlayerState.LastDirX * 6) / 30;
         _loc2_ = (MidPosY() - 6) / 30;
         _Handler_Maps.Handler_WorldItems.AddPolygon(_PlayerState.CurrentThrowableWeapon.Properties.ThrowType + "_thrown",_loc1_,_loc2_,0,new b2Vec2(),_PlayerState.LastDirX * 10,[_PlayerState.ThrowTimer]);
         _PlayerState.Aiming = false;
         _PlayerState.Throwing = false;
         _PlayerState.ThrowTimer = 0;
         _PlayerState.CurrentThrowableWeapon.Ammo -= 1;
      }
      
      private function UsePowerup() : void
      {
         if(_PlayerState.HP <= 0)
         {
            return;
         }
         if(_PlayerState.CurrentPowerupWeapon != null)
         {
            _PlayerState.SlowmotionDelay = 24;
            _Handler_Output.Trace("Activating Slowmotion (" + _PlayerState.CurrentPowerupWeapon.Ammo + ")");
            _slowmotion_timer = 24 * _PlayerState.CurrentPowerupWeapon.Ammo + 24 * 2;
            _slowmotion_modifier = 1.2;
            _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * _PlayerState.CurrentPowerupWeapon.Ammo,24 * 1,0.2),true,PlayerNr);
            _PlayerState.CurrentPowerupWeapon = null;
            UpdateGUI();
         }
         else if(_PlayerState.SlowmotionDelay <= 0)
         {
            _Handler_Slowmo.RemoveSlowmotion(PlayerNr);
         }
      }
      
      private function CollisionFeetBothSides() : Boolean
      {
         var _loc1_:int = 0;
         _loc1_ = 2;
         while(_loc1_ <= _PlayerState.PlayerEdgeDistance)
         {
            if(Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x - _loc1_,_this_y,true)) && Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x + _loc1_,_this_y,true)) && !_performJumpDownLevel)
            {
               return true;
            }
            if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x - _loc1_,_this_y,true)) && Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x + _loc1_,_this_y,true)))
            {
               return true;
            }
            _loc1_ += 2;
         }
         return false;
      }
      
      private function CollisionFeetMidUp(param1:Number = 0, param2:Number = 0) : Boolean
      {
         if(Boolean(CloudCollisionUp(_this_x,_this_y + param1,true)) && !_performJumpDownLevel)
         {
            return true;
         }
         if(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y + param1,true))
         {
            return true;
         }
         if(param2 != 0)
         {
            if(Boolean(CloudCollisionUp(_this_x + param2,_this_y + param1,true)) && !_performJumpDownLevel)
            {
               return true;
            }
            if(_static_world_hitbox_mc.hitTestPoint(_this_x + param2,_this_y + param1,true))
            {
               return true;
            }
            if(Boolean(CloudCollisionUp(_this_x - param2,_this_y + param1,true)) && !_performJumpDownLevel)
            {
               return true;
            }
            if(_static_world_hitbox_mc.hitTestPoint(_this_x - param2,_this_y + param1,true))
            {
               return true;
            }
         }
         return false;
      }
      
      private function GetDynamicBodyAt(param1:Number, param2:Number, param3:Boolean) : b2Body
      {
         if(_static_objects_hitbox_mc.hitTestPoint(param1,param2,true))
         {
            return m_world.GetDynamicBodyAt(param1,param2,param3);
         }
         return null;
      }
      
      private function AddLazerPoint(param1:Point) : void
      {
         var _loc2_:MovieClip = null;
         var _loc3_:Number = NaN;
         _loc2_ = new lazersight();
         _loc2_.x = param1.x;
         _loc2_.y = param1.y;
         _loc2_.alpha = 0.7;
         _loc3_ = 0.7 + 0.7 / _dynamic_mc.scaleX;
         _loc2_.scaleX = _loc3_;
         _loc2_.scaleY = _loc3_;
         _lazer_mc.addChild(_loc2_);
      }
      
      private function WeaponEmptyRecoil() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         if(_PlayerState.EmptyWeaponRecoilBack <= 0)
         {
            _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentRangeWeapon.Properties.EmptySound,PosX(),PosY());
            _PlayerState.CharAnimWpnX = _char.ANIM_WPN.x;
            _PlayerState.CharAnimWpnY = _char.ANIM_WPN.y;
            _loc1_ = Number(_PlayerState.CharAnimWpnX);
            _loc2_ = Number(_PlayerState.CharAnimWpnY);
            _loc1_ -= Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * 0.5 * _PlayerState.LastDirX;
            _loc2_ -= Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * 0.5;
            _char.ANIM_WPN.x = _loc1_;
            _char.ANIM_WPN.y = _loc2_;
            _PlayerState.EmptyWeaponRecoilBack = 2;
         }
      }
      
      private function CanBounceAtDirection(param1:Number) : Boolean
      {
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         _loc2_ = 2;
         while(_loc2_ <= 12)
         {
            _edgePosition = _this_x + param1 * _loc2_;
            _loc3_ = 2;
            while(_loc3_ <= 20)
            {
               if(_static_world_hitbox_mc.hitTestPoint(_edgePosition,_this_y - _loc3_,true))
               {
                  return false;
               }
               _loc3_ += 4;
            }
            _loc2_ += 2;
         }
         return true;
      }
      
      private function BotStateShoot() : void
      {
         if(_PlayerState.AFSInProgress)
         {
            if(_char.ANIM_WPN == null)
            {
               _BotState.Phase = BotState.CANCEL_AIM;
            }
            else
            {
               SetBotKey(5,true);
               BotAimY();
            }
         }
         else if(_PlayerState.CurrentRangeWeapon != null)
         {
            if(_PlayerState.CurrentRangeWeapon.Ammo <= 0)
            {
               _BotState.Phase = BotState.CANCEL_AIM;
            }
            else if(_BotState.CancelAimSoon)
            {
               _BotState.Phase = BotState.CANCEL_AIM;
            }
            else
            {
               SetBotKey(KEY_UP,false);
               SetBotKey(KEY_DOWN,false);
               _BotState.Phase = BotState.AIM;
            }
         }
         else
         {
            _BotState.Phase = BotState.CANCEL_AIM;
         }
      }
      
      public function get AreaMC() : MovieClip
      {
         return _player_area_mc;
      }
      
      private function DetectEdge(param1:int, param2:int = 14, param3:Boolean = false) : Boolean
      {
         var _loc4_:int = 0;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Boolean = false;
         _loc4_ = 0;
         _loc5_ = Number(_this_y);
         _loc7_ = 4;
         while(_loc7_ <= param2)
         {
            _loc4_ = _this_x + param1 * _loc7_;
            _loc8_ = 4;
            while(_loc8_ < 12)
            {
               _loc6_ = _loc5_ - _loc8_;
               if(Boolean(_static_world_hitbox_mc.hitTestPoint(_loc4_,_loc6_,true)) || Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_loc4_,_loc6_,true)))
               {
                  if(m_world.GetPartWorldAt(_loc4_,_loc6_) == null)
                  {
                     return false;
                  }
               }
               _loc8_ += 2;
            }
            _loc10_ = true;
            _loc9_ = -2;
            while(_loc9_ <= 10)
            {
               _loc6_ = _loc5_ + _loc9_;
               if(Boolean(_static_world_hitbox_mc.hitTestPoint(_loc4_,_loc6_,true)) || Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_loc4_,_loc6_,true)))
               {
                  _loc10_ = false;
                  _loc9_ = 12;
               }
               _loc9_ += 1;
            }
            if(_loc10_)
            {
               _Handler_Output.Trace("Edge Found: " + _loc7_);
               if(param3)
               {
                  _loc9_ = 12;
                  while(_loc9_ <= 40)
                  {
                     _loc6_ = _loc5_ + _loc9_;
                     if(Boolean(_static_world_hitbox_mc.hitTestPoint(_loc4_,_loc6_,true)) || Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_loc4_,_loc6_,true)))
                     {
                        return false;
                     }
                     _loc9_ += 4;
                  }
               }
               return true;
            }
            _loc7_ += 2;
         }
         return false;
      }
      
      private function EdgeStaggerDistance() : int
      {
         var _loc1_:int = 0;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Boolean = false;
         var _loc7_:Number = NaN;
         var _loc8_:Boolean = false;
         _loc1_ = 0;
         _loc2_ = Number(_this_y);
         _loc4_ = 0;
         while(_loc4_ <= 36)
         {
            _loc1_ = _this_x - _PlayerState.LastDirX * _PlayerState.StaggerSpeed * _loc4_;
            _loc5_ = 4;
            while(_loc5_ < 12)
            {
               _loc3_ = _loc2_ - _loc5_;
               if(_static_world_hitbox_mc.hitTestPoint(_loc1_,_loc3_,true))
               {
                  if(m_world.GetGlassAt(_loc1_,_loc3_) == null)
                  {
                     return 0;
                  }
               }
               _loc5_ += 2;
            }
            _loc6_ = true;
            _loc7_ = -2;
            while(_loc7_ <= 10)
            {
               _loc3_ = _loc2_ + _loc7_;
               _loc8_ = Boolean(_static_world_cloud_hitbox_mc.hitTestPoint(_loc1_,_loc3_,true));
               if(Boolean(_static_world_hitbox_mc.hitTestPoint(_loc1_,_loc3_,true)) || _loc8_)
               {
                  if(Boolean(HitTestWorldOnly(_loc1_,_loc3_)) || m_world.GetGlassAt(_loc1_,_loc3_) == null || _loc8_)
                  {
                     _loc2_ = _loc3_;
                     _loc6_ = false;
                     _loc7_ = 12;
                  }
               }
               _loc7_ += 1;
            }
            if(_loc6_)
            {
               _Handler_Output.Trace("Edge Found: " + _loc4_);
               return _loc4_;
            }
            _loc4_ += 2;
         }
         return 0;
      }
      
      private function DropGrabbedPlayer() : void
      {
         if(_PlayerState.GrabbedPlayer)
         {
            UpdateGrabbedPlayer(true);
            _players[_PlayerState.GrabbedPlayerNr].GrabbedByOtherPlayer(false,_PlayerState.LastDirX);
            _PlayerState.GrabbedPlayer = false;
         }
      }
      
      public function Disarm() : void
      {
         CheckAimDrop(true);
      }
      
      public function PlayerInSightPercentage(param1:Player) : Number
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         _loc4_ = PosX() - _PlayerState.LastDirX * 4 - param1.MidPosX();
         _loc5_ = PosY() - 14 - param1.MidPosY();
         if(_PlayerState.LastDirX == -1)
         {
            _loc2_ = _PlayerState.CurrentAimAngle - 180;
            _loc3_ = Math.atan2(_loc5_,_loc4_) * (180 / Math.PI);
         }
         else
         {
            _loc2_ = Math.atan2(-_loc5_,-_loc4_) * (180 / Math.PI) + 180;
            _loc3_ = _PlayerState.CurrentAimAngle + 180;
         }
         if(_loc2_ < _loc3_)
         {
            _loc6_ = Math.round(_loc3_ - _loc2_) / 90;
         }
         else
         {
            _loc6_ = Math.round(_loc2_ - _loc3_) / 90;
         }
         if(_loc6_ > 1)
         {
            _loc6_ = 1;
         }
         return 1 - _loc6_;
      }
      
      public function BotPositionShootableFrom(param1:Number, param2:Number, param3:Number, param4:Number) : Boolean
      {
         var _loc5_:Point = null;
         var _loc6_:Point = null;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:b2Body = null;
         var _loc11_:b2Body = null;
         var _loc12_:int = 0;
         var _loc13_:Number = NaN;
         var _loc14_:Number = NaN;
         var _loc15_:int = 0;
         var _loc16_:Point = null;
         var _loc17_:b2Body = null;
         var _loc18_:int = 0;
         _loc5_ = new Point(param3,param4);
         _loc6_ = new Point(param1,param2);
         _loc7_ = _loc5_.x - _loc6_.x;
         _loc8_ = _loc5_.y - _loc6_.y;
         _loc9_ = Math.sqrt(_loc7_ * _loc7_ + _loc8_ * _loc8_);
         if(_loc9_ > _PlayerState.RangeWeaponRange)
         {
            return false;
         }
         _loc10_ = null;
         _loc11_ = null;
         _loc12_ = _loc9_ / 4;
         _loc13_ = -_loc7_ / _loc12_;
         _loc14_ = -_loc8_ / _loc12_;
         _loc15_ = 1;
         while(_loc15_ <= _loc12_)
         {
            _loc5_.x += _loc13_;
            _loc5_.y += _loc14_;
            _loc6_.x -= _loc13_;
            _loc6_.y -= _loc14_;
            _loc17_ = null;
            _loc18_ = -1;
            while(_loc18_ <= 1)
            {
               if(_loc18_ == 1)
               {
                  _loc16_ = _loc5_;
                  _loc17_ = _loc10_;
               }
               else
               {
                  _loc16_ = _loc6_;
                  _loc17_ = _loc11_;
               }
               if(_loc17_ != null)
               {
                  if(!_loc17_.GetUserData().objectData.ShapeMC.hitTestPoint(_loc16_.x,_loc16_.y,true))
                  {
                     _loc17_ = null;
                  }
               }
               if(_loc17_ == null)
               {
                  if(_static_objects_hitbox_mc.hitTestPoint(_loc16_.x,_loc16_.y,true))
                  {
                     _loc17_ = m_world.GetBulletSolidAt(_loc16_.x,_loc16_.y);
                  }
                  else
                  {
                     if(_static_world_hitbox_mc.hitTestPoint(_loc16_.x,_loc16_.y,true))
                     {
                        return false;
                     }
                     if(_loc14_ > 0 && !_PlayerState.RangeWeaponCanShootDown)
                     {
                        if(_static_world_cloud_hitbox_mc.hitTestPoint(_loc16_.x,_loc16_.y,true))
                        {
                           return false;
                        }
                     }
                  }
               }
               if(_loc17_ != null)
               {
                  if(!_PlayerState.RangeWeaponIsFlamethrower && !_PlayerState.RangeWeaponIsBazooka)
                  {
                     if(Boolean(_loc17_.GetUserData().objectData.Indestructible))
                     {
                        return false;
                     }
                  }
               }
               if(_loc18_ == 1)
               {
                  _loc10_ = _loc17_;
               }
               else
               {
                  _loc11_ = _loc17_;
               }
               _loc18_ += 2;
            }
            _loc15_ += 2;
         }
         return true;
      }
      
      public function BulletDamage(param1:ProjectileData) : void
      {
         var _loc2_:Boolean = false;
         var _loc3_:Boolean = false;
         var _loc4_:int = 0;
         if(_PlayerState.IsImmune)
         {
            return;
         }
         if(_PlayerState.DeathKneel)
         {
            return;
         }
         _loc2_ = false;
         if(_PlayerState.HP <= 0)
         {
            _loc2_ = true;
         }
         _loc3_ = false;
         if(Math.random() * 100 <= param1.Properties.CriticalChance)
         {
            _loc3_ = true;
         }
         if(_PlayerState.StuckToRocket)
         {
            if(_loc3_)
            {
               _PlayerState.RocketRideProjectile.Explode();
               if(ActivateSlowmotion(PlayerNr))
               {
                  _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
               }
            }
            return;
         }
         _PlayerState.CurrentPushbackPower += param1.Properties.PushbackPower;
         if(_loc3_)
         {
            _PlayerState.HP -= param1.Properties.CriticalDamage;
         }
         else
         {
            _PlayerState.HP -= param1.Properties.Damage;
         }
         if(_PlayerState.GrabbedByPlayer)
         {
            return;
         }
         if(_loc3_ || !_loc2_ && _PlayerState.HP <= 0 || _PlayerState.CurrentPushbackPower >= 100)
         {
            _PlayerState.CritSmokeTimer = 36;
            _Handler_Effects.AddEffectAt("HITDEFAULT_01",param1.PosX,param1.PosY);
            if(_PlayerState.OnGround)
            {
               _this_y -= 1;
            }
            if(_PlayerState.HP > 0 || _loc2_)
            {
               _PlayerState.AirVelocityX += param1.DirectionX * 2;
               _PlayerState.AirVelocityY = -2;
            }
            else if(Boolean(_PlayerState.OnGround) && Math.random() < 0.5)
            {
               _PlayerState.AirVelocityX = _PlayerState.LastDirX * _PlayerState.RunSpeed;
               _PlayerState.AirVelocityY = -2;
            }
            else
            {
               _PlayerState.AirVelocityX += param1.DirectionX * 2;
               _PlayerState.AirVelocityY = -2;
            }
            _PlayerState.LastDirX = -ConvertToDirection(param1.DirectionX);
            if(_PlayerState.LastDirX == 0)
            {
               _PlayerState.LastDirX = 1;
            }
            _PlayerState.CurrentPushbackPower = 0;
            this.scaleX = _PlayerState.LastDirX;
            _collision_mc.scaleX = this.scaleX;
            if(_PlayerState.HP <= 0)
            {
               Disarm();
               if(!_loc2_ && Boolean(_PlayerState.OnGround) && !_PlayerState.Knockdowned || Boolean(_PlayerState.Staggering))
               {
                  _loc4_ = int(EdgeStaggerDistance());
                  if(_loc4_ > 6)
                  {
                     StartStagger();
                     _PlayerState.StaggerTimer = _loc4_ - 4;
                  }
                  else if(DetectEdge(_PlayerState.LastDirX))
                  {
                     _PlayerState.DeathKneel = true;
                     _PlayerState.CameraIgnoreTimer = 3 * 24;
                  }
                  else
                  {
                     if(Math.random() < 0.5)
                     {
                        Fall(false);
                     }
                     else if(Math.random() < 0.5)
                     {
                        StartStagger();
                     }
                     else
                     {
                        _PlayerState.DeathKneel = true;
                        _PlayerState.CameraIgnoreTimer = 3 * 24;
                     }
                     _Handler_Shake.Add(2,2);
                  }
               }
               else
               {
                  Fall(false);
                  _Handler_Shake.Add(2,2);
               }
            }
            else if(Math.random() < 0.25 || Boolean(_PlayerState.Knockdowned))
            {
               Fall(false);
               _Handler_Shake.Add(2,2);
            }
            else
            {
               StartStagger();
            }
         }
         if(!_loc2_ && _PlayerState.HP <= 0)
         {
            if(ActivateSlowmotion(PlayerNr))
            {
               _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 2,24 * 1,0.2));
            }
            if(Boolean(_PlayerState.OnGround) && !_PlayerState.Staggering && !_PlayerState.DeathKneel)
            {
               Fall(false);
            }
         }
      }
      
      public function SetGrabRotation(param1:Number) : void
      {
         _PlayerAnimation.GrabRotation = param1;
      }
      
      private function InMeleeRange(param1:Player) : Boolean
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         _loc2_ = _this_x - param1.PosX();
         if(Math.abs(_loc2_) <= _PlayerState.MeleeWeaponRange + 4)
         {
            _loc3_ = MidPosY() - param1.MidPosY();
            if(_loc3_ >= -7 && _loc3_ <= 12.5)
            {
               return true;
            }
         }
         return false;
      }
      
      private function WalkCollision(param1:int, param2:Boolean) : Boolean
      {
         var _loc3_:int = 0;
         _loc3_ = 2;
         while(_loc3_ <= 4)
         {
            if(_static_world_hitbox_mc.hitTestPoint(_this_x + (_loc3_ - 1) * param1,_this_y - 2 - _loc3_,true))
            {
               return true;
            }
            _loc3_ += 2;
         }
         return false;
      }
      
      private function KickHit(param1:b2Body, param2:Boolean, param3:Boolean = false) : Boolean
      {
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         if(param2)
         {
            if(_standingOnObject == param1)
            {
               return false;
            }
         }
         _loc6_ = int(_PlayerState.LastDirX);
         if(param2)
         {
            _loc4_ = 0;
            while(_loc4_ <= _PlayerState.MeleeWeaponRange)
            {
               _loc5_ = -16;
               while(_loc5_ <= 0)
               {
                  if(Boolean(param1.m_userData.objectData.ShapeMC.hitTestPoint(_this_x + _loc4_ * _loc6_,_this_y + _loc5_,true)))
                  {
                     return true;
                  }
                  _loc5_ += 2;
               }
               _loc4_ += 2;
            }
         }
         else if(param3)
         {
            _loc4_ = 0;
            while(_loc4_ <= 16)
            {
               _loc5_ = -16;
               while(_loc5_ <= 0)
               {
                  if(Boolean(param1.m_userData.objectData.ShapeMC.hitTestPoint(_this_x + _loc4_ * _loc6_,_this_y + _loc5_,true)))
                  {
                     return true;
                  }
                  _loc5_ += 2;
               }
               _loc4_ += 2;
            }
         }
         else
         {
            _loc4_ = 0;
            while(_loc4_ <= 8)
            {
               _loc5_ = -8;
               while(_loc5_ <= 4)
               {
                  if(Boolean(param1.m_userData.objectData.ShapeMC.hitTestPoint(_this_x + _loc4_ * _loc6_,_this_y + _loc5_,true)))
                  {
                     return true;
                  }
                  _loc5_ += 2;
               }
               _loc4_ += 2;
            }
         }
         return false;
      }
      
      private function AimDown(param1:Number = 0) : void
      {
         if(_PlayerState.CurrentAimPitch < _PlayerState.LowerAimPitch)
         {
            if(param1 != 0)
            {
               _PlayerState.CurrentChangePitchSpeed = param1;
            }
            if(_PlayerState.CurrentChangePitchSpeed < 0)
            {
               _PlayerState.CurrentChangePitchSpeed = 0;
            }
            _PlayerState.CurrentAimPitch += _PlayerState.CurrentChangePitchSpeed * _game_speed;
            _PlayerState.CurrentChangePitchSpeed += 2;
            if(_PlayerState.CurrentAimPitch > _PlayerState.LowerAimPitch)
            {
               _PlayerState.CurrentAimPitch = _PlayerState.LowerAimPitch;
            }
         }
      }
      
      private function ProgressAFS(param1:Boolean = false) : void
      {
         var pd:particle_data = null;
         var realFrame:int = 0;
         var posX:Number = NaN;
         var posY:Number = NaN;
         var shellPosX:Number = NaN;
         var shellPosY:Number = NaN;
         var muzzlePosX:Number = NaN;
         var muzzlePosY:Number = NaN;
         var speedVec:b2Vec2 = null;
         var randomDeflection:Number = NaN;
         var i:int = 0;
         var firstUpdate:Boolean = param1;
         try
         {
            if(_PlayerState.Staggering)
            {
               return;
            }
            if(_startAimASAP)
            {
               if(Boolean(_PlayerState.ControllAble) && Boolean(_PlayerState.OnGround))
               {
                  if(KeyPressed(5))
                  {
                     RangedDown();
                  }
                  else if(KeyPressed(6))
                  {
                     ThrowDown();
                  }
               }
            }
            if(_PlayerState.Aiming)
            {
               if(_PlayerState.AimMode == 1)
               {
                  if(_PlayerState.CurrentThrowableWeapon.Properties.ThrowType == "MOLOTOV")
                  {
                     if(Math.random() < 0.35)
                     {
                        pd = new particle_data("FIRE",MidPosX() - _PlayerState.LastDirX * 8,MidPosY() - 4.5);
                        pd.ScaleX = 0.5;
                        pd.ScaleY = 0.5;
                        _Handler_Effects.AddParticle(pd);
                     }
                  }
                  if(_PlayerState.ThrowTimer > 0)
                  {
                     _PlayerState.ThrowTimer -= _game_speed;
                     if(_PlayerState.ThrowTimer <= 0)
                     {
                        _PlayerState.ThrowTimer = 0;
                        ThrowTimerEnded();
                     }
                  }
               }
            }
            if(AFSUpdated)
            {
               return;
            }
            AFSUpdated = true;
            if(_PlayerState.CurrentFireFrame > 0)
            {
               if(!firstUpdate)
               {
                  _PlayerState.CurrentFireFrame += _game_speed;
               }
               if(_char.ANIM_WPN == null)
               {
                  return;
               }
               realFrame = Math.floor(_PlayerState.CurrentFireFrame);
               if(_PlayerState.LastFireFrame != realFrame)
               {
                  _PlayerState.LastFireFrame = realFrame;
                  if(Boolean(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].End))
                  {
                     _PlayerState.CurrentFireFrame = 0;
                     _PlayerState.LastFireFrame = 0;
                     if(_flameAwayActivated)
                     {
                        clearInterval(_flameAwayTimer);
                        _flameAwayActivated = false;
                     }
                  }
                  else if(_PlayerState.BackToIdleTimer < 6)
                  {
                     _PlayerState.BackToIdleTimer = 6;
                  }
                  _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].FrameSound,PosX(),PosY());
                  posX = _char.ANIM_WPN.x * _PlayerState.LastDirX + PosX();
                  posY = _char.ANIM_WPN.y + PosY();
                  if(Boolean(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].UseShellEffect))
                  {
                     shellPosX = posX;
                     shellPosY = posY;
                     shellPosX += Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.SHELL_CENTER.x;
                     shellPosY += Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.SHELL_CENTER.x;
                     shellPosY += Math.sin((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.SHELL_CENTER.y * _PlayerState.LastDirX;
                     shellPosX += Math.cos((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.SHELL_CENTER.y * _PlayerState.LastDirX;
                     _Handler_Effects.AddParticle(new particle_data(_PlayerState.CurrentRangeWeapon.Properties.ShellEffect,shellPosX,shellPosY,new b2Vec2(-_PlayerState.LastDirX * Math.random() * 1 - _PlayerState.LastDirX,-Math.random() * 1 - 1),_PlayerState.CurrentAimAngleRad));
                  }
                  if(Boolean(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].UseMuzzleEffect))
                  {
                     muzzlePosX = posX;
                     muzzlePosY = posY;
                     muzzlePosX += Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.MUZZLE_CENTER.x;
                     muzzlePosY += Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.MUZZLE_CENTER.x;
                     muzzlePosY += Math.sin((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.MUZZLE_CENTER.y * _PlayerState.LastDirX;
                     muzzlePosX += Math.cos((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.MUZZLE_CENTER.y * _PlayerState.LastDirX;
                     speedVec = new b2Vec2();
                     _Handler_Effects.AddParticle(new particle_data(_PlayerState.CurrentRangeWeapon.Properties.MuzzleFlashEffect,muzzlePosX,muzzlePosY,speedVec,_PlayerState.CurrentAimAngle));
                  }
                  if(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].Bullets > 0)
                  {
                     posX += Math.cos(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.x;
                     posY += Math.sin(_PlayerState.CurrentAimAngle * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.x;
                     posY += Math.sin((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.y * _PlayerState.LastDirX;
                     posX += Math.cos((_PlayerState.CurrentAimAngle + 90) * (Math.PI / 180)) * _char.ANIM_WPN.FIRE_CENTER.y * _PlayerState.LastDirX;
                     i = 0;
                     while(i < _PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].Bullets)
                     {
                        if(_PlayerState.CurrentRangeWeapon.Ammo > 0)
                        {
                           randomDeflection = Math.random() * _PlayerState.CurrentRangeWeapon.Properties.AccuracyDeflection * 2 - _PlayerState.CurrentRangeWeapon.Properties.AccuracyDeflection;
                           switch(_PlayerState.CurrentRangeWeapon.Properties.BulletType)
                           {
                              case "FLAME":
                                 if(!_flameAwayActivated)
                                 {
                                    FlameAway();
                                    _flameAwayTimer = setInterval(FlameAway,10);
                                    _flameAwayActivated = true;
                                 }
                                 break;
                              case "BAZOOKA_ROCKET":
                                 _Handler_ProjectilesUpdater.NewRocket("BAZOOKA_ROCKET",posX,posY,_PlayerState.CurrentAimAngle + randomDeflection,this);
                                 break;
                              default:
                                 _Handler_ProjectilesUpdater.NewProjectile(_PlayerState.CurrentRangeWeapon.Properties.BulletType,posX,posY,_PlayerState.CurrentAimAngle + randomDeflection,this);
                           }
                           _PlayerState.CurrentRangeWeapon.Ammo -= 1;
                        }
                        else
                        {
                           WeaponEmptyRecoil();
                           _PlayerState.CurrentFireFrame = _PlayerState.CurrentRangeWeapon.Properties.FireSequence.length - 1;
                           _PlayerState.LastFireFrame = _PlayerState.CurrentFireFrame;
                           i = int(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[realFrame - 1].Bullets);
                        }
                        UpdateGUIRanged();
                        i++;
                     }
                  }
               }
            }
            if(!_PlayerState.AFSInProgress)
            {
               if(_PlayerState.CurrentWeaponCooldown > 0)
               {
                  _PlayerState.CurrentWeaponCooldown -= 1 - (1 - _game_speed) / 2;
               }
               if(_PlayerState.Aiming)
               {
                  if(!KeyPressed(5) && !KeyPressed(6) || Boolean(_cancelAimingASAP))
                  {
                     if(_PlayerState.FastTrigger)
                     {
                        if(!_PlayerState.AimTurningAroundDelay)
                        {
                           _PlayerState.FastTrigger = false;
                           AFSUpdated = false;
                           FireWeapon();
                        }
                     }
                     else if(_PlayerState.BackToIdleTimer <= 0 || Boolean(_cancelAimingASAP))
                     {
                        _cancelAimingASAP = false;
                        AbortAiming();
                     }
                  }
               }
            }
         }
         catch(e:Error)
         {
         }
      }
      
      private function BotCloudAbove() : Boolean
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < 20)
         {
            if(_static_world_cloud_hitbox_mc.hitTestPoint(_this_x,_this_y - _loc1_,true))
            {
               return true;
            }
            _loc1_ += 2;
         }
         return false;
      }
      
      private function UpdateAirMovement() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:int = 0;
         var _loc7_:Number = NaN;
         var _loc8_:Boolean = false;
         var _loc9_:int = 0;
         var _loc10_:b2Vec2 = null;
         var _loc11_:b2Vec2 = null;
         var _loc12_:Boolean = false;
         var _loc13_:b2Vec2 = null;
         var _loc14_:b2Vec2 = null;
         var _loc15_:Number = NaN;
         if(_PlayerState.AirVelocityY == 0)
         {
            _PlayerState.AirVelocityY = 0.1;
         }
         if(_this_y > _jumpDownPosYDisable)
         {
            _performJumpDownLevel = false;
         }
         if(_PlayerState.Climbing)
         {
            if(Boolean(_keyPressed[1]) && !_keyPressed[0])
            {
               _PlayerState.AirVelocityY = _PlayerState.SlideSpeed;
               _PlayerState.AirVelocityX = 0;
               if(_PlayerState.CurrentLadder == null)
               {
                  _PlayerState.CurrentLadder = m_world.GetLadderBodyAt(MidPosX(),MidPosY());
               }
               if(_PlayerState.CurrentLadder != null)
               {
                  _PlayerState.DisableKneel = true;
                  _this_x = _PlayerState.CurrentLadder.GetPosition().x * 30;
               }
               LadderSliding();
            }
            else
            {
               if(Boolean(_keyPressed[0]))
               {
                  _PlayerState.AirVelocityY = -_PlayerState.ClimbSpeed;
               }
               else
               {
                  _PlayerState.AirVelocityY = 0;
               }
               if(PressingLeft())
               {
                  _PlayerState.AirVelocityX = -_PlayerState.ClimbSpeed;
                  this.scaleX = -1;
                  _collision_mc.scaleX = this.scaleX;
                  _PlayerState.LastDirX = -1;
               }
               else if(PressingRight())
               {
                  _PlayerState.AirVelocityX = _PlayerState.ClimbSpeed;
                  this.scaleX = 1;
                  _collision_mc.scaleX = this.scaleX;
                  _PlayerState.LastDirX = 1;
               }
               else
               {
                  _PlayerState.AirVelocityX = 0;
               }
            }
         }
         else if(!_PlayerState.Knockdowned && _PlayerState.HP <= 0)
         {
            Fall(false);
         }
         _loc1_ = Math.ceil(_PlayerState.TotalAirVelocity);
         if(_loc1_ <= 1)
         {
            _loc1_ = 1;
         }
         _loc2_ = _PlayerState.AirVelocityY * _game_speed;
         _loc3_ = _PlayerState.AirVelocityX * _game_speed;
         if(_PlayerState.ControllAble)
         {
            if(PressingLeft())
            {
               TurnLeft();
            }
            else if(PressingRight())
            {
               TurnRight();
            }
         }
         _loc4_ = Number(_this_x);
         _loc5_ = Number(_this_y);
         _loc6_ = 1;
         while(_loc6_ <= _loc1_)
         {
            _loc4_ = Number(_this_x);
            _loc5_ = Number(_this_y);
            _this_x += _loc3_ / _loc1_;
            _this_y += _loc2_ / _loc1_;
            if(PlayerOutsideLevel())
            {
               IgnorePlayer();
               return;
            }
            if(_PlayerState.Climbing)
            {
               if(!_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY(),true))
               {
                  if(_loc2_ < 0)
                  {
                     _this_y = _loc5_;
                     if(!_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY(),true))
                     {
                        _PlayerState.Climbing = false;
                        _PlayerState.AirVelocityX = 0;
                     }
                     else
                     {
                        _PlayerState.AirVelocityY = 0;
                     }
                  }
                  else
                  {
                     _PlayerState.Climbing = false;
                     _PlayerState.AirVelocityX = 0;
                  }
               }
               else if(_loc2_ > 0)
               {
                  _PlayerState.NextLadderEffect -= _loc2_;
                  if(_PlayerState.NextLadderEffect <= 0)
                  {
                     if(_PlayerState.LadderEffectRightSide)
                     {
                        _loc7_ = 1;
                     }
                     else
                     {
                        _loc7_ = -1;
                     }
                     if(Math.random() * 10 < 5)
                     {
                        _Handler_Effects.AddParticle(new particle_data("METAL",PosX() + 6 * _loc7_,PosY() - 16,new b2Vec2(Math.random() * _loc7_ * 0.5,-Math.random() * 0.5)));
                     }
                     else
                     {
                        _Handler_Effects.AddParticle(new particle_data("METAL",PosX() + 6 * _loc7_,PosY(),new b2Vec2(Math.random() * _loc7_ * 0.5,Math.random() * 0.5)));
                     }
                     _PlayerState.LadderEffectRightSide = !_PlayerState.LadderEffectRightSide;
                     _PlayerState.NextLadderEffect = 14 + Math.random() * 4;
                  }
               }
            }
            if(_PlayerState.Falling)
            {
               if(CollisionSide(_loc3_))
               {
                  _loc8_ = false;
                  _loc9_ = int(ConvertToDirection(_PlayerState.AirVelocityX));
                  b = GetDynamicBodyAt(MidPosX() + (_PlayerState.PlayerEdgeDistance + 2) * _loc9_,MidPosY(),false);
                  if(b != null)
                  {
                     _loc10_ = new b2Vec2(_PlayerState.LastDirX,0);
                     _loc11_ = new b2Vec2(MidPosX() + (_PlayerState.PlayerEdgeDistance + 2) * _loc9_,MidPosY());
                     _loc11_.x /= 30;
                     _loc11_.y /= 30;
                     b.ApplyImpulse(_loc10_,_loc11_);
                     if(Boolean(b.GetUserData().objectData.PlayerFragile))
                     {
                        _loc8_ = true;
                        b.GetUserData().objectData.ForceDestruction();
                        _PlayerState.AirVelocityX *= 0.6;
                        return;
                     }
                     b.GetUserData().objectData.Damage_Impact(2);
                  }
                  _Handler_Sounds.PlaySoundAt("MELEE_HIT",_this_x,_this_y);
                  _this_x = _loc4_;
                  if(CanLandInMid())
                  {
                     _PlayerState.AirVelocityX = 0;
                  }
                  else if(!CollisionHead())
                  {
                     _PlayerState.AirVelocityX = -_PlayerState.AirVelocityX * 0.5;
                     _PlayerState.AirVelocityY = -Math.abs(_PlayerState.AirVelocityY) * 0.7;
                     if(Math.abs(_PlayerState.AirVelocityX) > 2)
                     {
                        _PlayerState.AirVelocityX = -_loc9_ * 2;
                     }
                     if(_PlayerState.AirVelocityY < -2.5)
                     {
                        _PlayerState.AirVelocityY = -2.5;
                     }
                     return;
                  }
               }
            }
            else
            {
               _loc12_ = false;
               if(CollisionSide(_loc3_))
               {
                  if(_PlayerState.Diving)
                  {
                     b = GetDynamicBodyAt(MidPosX() + 6 * _PlayerState.LastDirX,MidPosY(),false);
                     if(b != null)
                     {
                        _loc13_ = new b2Vec2(_PlayerState.LastDirX,0);
                        _loc14_ = new b2Vec2(MidPosX() + 6 * _PlayerState.LastDirX,MidPosY());
                        _loc14_.x /= 30;
                        _loc14_.y /= 30;
                        b.ApplyImpulse(_loc13_,_loc14_);
                        b.GetUserData().objectData.Damage_Impact(2);
                        if(b.GetUserData().objectData.HP > 0)
                        {
                           _loc12_ = true;
                           _PlayerState.Diving = false;
                           _PlayerState.Sprinting = false;
                           _PlayerState.AirVelocityY = 0;
                           _PlayerState.AirVelocityX = 0;
                           _loc3_ = 0;
                        }
                     }
                     else
                     {
                        _loc12_ = true;
                        _PlayerState.Diving = false;
                        _PlayerState.Sprinting = false;
                        _PlayerState.AirVelocityY = 0;
                        _PlayerState.AirVelocityX = 0;
                        _loc3_ = 0;
                     }
                  }
                  else
                  {
                     _PlayerState.AirVelocityX = 0;
                     _loc3_ = 0;
                  }
               }
               UpdateSides(false);
               if(_loc12_)
               {
                  DropGrabbedPlayer();
               }
            }
            if(_PlayerState.Diving)
            {
               CheckDivePlayerImpact();
            }
            if(_loc2_ > 0)
            {
               if(!_PlayerState.Climbing)
               {
                  if(!_PlayerState.Falling && !_PlayerState.Diving)
                  {
                     if(_PlayerState.AirVelocityY >= _PlayerState.FallTriggerSpeed)
                     {
                        if(_PlayerState.MovingDirectionInversed != 0)
                        {
                           if(Boolean(_keyPressed[2]) && !CollisionSide(1,_PlayerState.PlayerEdgeDistance + 1))
                           {
                              _PlayerState.AirVelocityX += _PlayerState.RunSpeed * 0.8;
                           }
                           if(Boolean(_keyPressed[3]) && !CollisionSide(-1,_PlayerState.PlayerEdgeDistance + 1))
                           {
                              _PlayerState.AirVelocityX -= _PlayerState.RunSpeed * 0.8;
                           }
                        }
                        else
                        {
                           if(Boolean(_keyPressed[2]) && !CollisionSide(-1,_PlayerState.PlayerEdgeDistance + 1))
                           {
                              _PlayerState.AirVelocityX -= _PlayerState.RunSpeed * 0.8;
                           }
                           if(Boolean(_keyPressed[3]) && !CollisionSide(1,_PlayerState.PlayerEdgeDistance + 1))
                           {
                              _PlayerState.AirVelocityX += _PlayerState.RunSpeed * 0.8;
                           }
                        }
                        _PlayerState.Falling = true;
                     }
                  }
               }
               if(CollisionHead())
               {
                  CheckObjectHeadImpactSpeeds();
               }
               if(CollisionFeetSides())
               {
                  if(CanLandInMid())
                  {
                     if(CollisionFeetMid())
                     {
                        PlayerLands();
                        return;
                     }
                  }
                  else if(!CollisionFeetSides(-2))
                  {
                     if(CollisionFeetSides(1,_PlayerState.PlayerEdgeDistance - 1))
                     {
                        PlayerLands();
                        return;
                     }
                  }
                  else
                  {
                     if(CollisionFeetBothSides())
                     {
                        PlayerLands();
                        return;
                     }
                     UpdateSides();
                  }
               }
            }
            else if(_loc2_ < 0)
            {
               if(Boolean(CollisionHead()) || Boolean(WorldCollisionHead()))
               {
                  _loc15_ = Number(_PlayerState.AirVelocityY);
                  _this_y = _loc5_;
                  _PlayerState.AirVelocityY = 0;
                  CheckObjectHeadImpactSpeeds();
                  CheckHeadToObjectImpacts(Math.abs(_loc15_) * 0.1);
                  return;
               }
               if(_PlayerState.AirVelocityY != _PlayerState.PlayerJumpPower)
               {
                  if(CollisionFeetSides())
                  {
                     if(CanLandInMid())
                     {
                        if(CollisionFeetMidUp(-2,0))
                        {
                           PlayerLands();
                           return;
                        }
                     }
                  }
               }
            }
            UpdateGrabbedPlayer();
            UpdatePlayerFallingOnPlayer();
            if(!_PlayerState.Climbing)
            {
               _PlayerState.AirVelocityY += _PlayerState.PlayerGravity * _game_speed / _loc1_;
               _loc3_ = _PlayerState.AirVelocityX * _game_speed;
               _loc2_ = _PlayerState.AirVelocityY * _game_speed;
            }
            _loc6_++;
         }
      }
      
      private function CancelFireDelay() : void
      {
         clearInterval(_PlayerState.FireDelayTimer);
         _PlayerState.FireDelayActivated = false;
         _PlayerState.FireDelayUpdated = false;
         _startAimASAP = false;
      }
      
      public function IgnorePlayer() : void
      {
         if(_PlayerState.GrabbedPlayer)
         {
            _players[_PlayerState.GrabbedPlayerNr].SetCoordinates(_this_x,_this_y);
            _players[_PlayerState.GrabbedPlayerNr].GrabbedByOtherPlayer(false,_PlayerState.LastDirX);
            _PlayerState.GrabbedPlayer = false;
         }
         _PlayerBars.Hide();
         _PlayerState.TakingCover = false;
         _PlayerState.CoverObjectID = -1;
         _PlayerState.HP = 0;
         _char_gui.visible = false;
         _blood_gui.visible = false;
         _gui_mc.gib_pic.alpha = 1;
         _PlayerState.CameraIgnoreTimer = 24 * 2;
         this.visible = false;
         _collision_mc.visible = false;
         _collision_mc.x = 9999;
         _collision_mc.y = 9999;
         _player_area_mc.x = 9999;
         _player_area_mc.y = 9999;
         _PlayerState.IgnoreMe = true;
      }
      
      private function TurnRight() : void
      {
         if(_PlayerState.LastDirX == -1)
         {
            this.scaleX = 1;
            _collision_mc.scaleX = this.scaleX;
            _PlayerState.LastDirX = 1;
         }
      }
      
      public function DiveCollision() : void
      {
         DropGrabbedPlayer();
         _PlayerState.AirVelocityX = _PlayerState.LastDirX * 3.5;
         _PlayerState.LastDirX *= -1;
         _PlayerState.Falling = true;
      }
      
      private function CollisionSide(param1:Number, param2:Number = -1) : Boolean
      {
         var _loc3_:int = 0;
         if(param1 == 0)
         {
            return false;
         }
         if(param2 <= 0)
         {
            param2 = Number(_PlayerState.PlayerEdgeDistance);
         }
         _edgePosition = _this_x + param2 * ConvertToDirection(param1);
         _loc3_ = 6;
         while(_loc3_ <= _PlayerState.PlayerHeight - 2)
         {
            if(_static_world_hitbox_mc.hitTestPoint(_edgePosition,_this_y - _loc3_,true))
            {
               return true;
            }
            _loc3_ += 2;
         }
         return false;
      }
      
      private function UpdateGrabbedPlayer(param1:Boolean = false) : void
      {
         var center:Boolean = param1;
         if(_PlayerState.GrabbedPlayer)
         {
            if(center)
            {
               _players[_PlayerState.GrabbedPlayerNr].SetCoordinates(_this_x,_this_y);
            }
            else
            {
               _players[_PlayerState.GrabbedPlayerNr].SetCoordinates(_this_x + _PlayerState.LastDirX * 6,_this_y - 2);
            }
            try
            {
               _players[_PlayerState.GrabbedPlayerNr].SetGrabRotation(-_PlayerAnimation.GrabRotation);
            }
            catch(e:Error)
            {
            }
         }
      }
      
      private function LadderJump() : void
      {
         if(!_static_ladder_hitbox_mc.hitTestPoint(MidPosX(),MidPosY() - 1,true))
         {
            _PlayerState.Climbing = false;
            _this_y -= 1;
            BeginJump();
         }
      }
      
      private function FireUp() : void
      {
         if(_PlayerState.StuckToRocket)
         {
            return;
         }
         if(_PlayerState.Staggering)
         {
            return;
         }
         _startAimASAP = false;
         if(Boolean(_PlayerState.FireDelayActivated) && !_PlayerState.FireDelayUpdated)
         {
            clearInterval(_PlayerState.FireDelayTimer);
            _PlayerState.FireDelayUpdated = true;
            _PlayerState.FireDelayTimer = setInterval(CancelFireDelay,100);
            return;
         }
         if(!_PlayerState.Throwing && Boolean(_PlayerState.Aiming) && !_PlayerState.AimTurningAroundDelay)
         {
            if(_PlayerState.AimMode == 0)
            {
               _PlayerState.BackToIdleTimer = 6;
               FireWeapon();
            }
            else if(_PlayerState.AimMode == 1)
            {
               _PlayerState.Throwing = true;
               _PlayerState.Aiming = false;
               ReleaseThrowable();
            }
         }
      }
      
      private function LadderSliding() : void
      {
         var _loc1_:* = undefined;
         _loc1_ = 0;
         while(_loc1_ < _players.length)
         {
            if(_loc1_ != PlayerNr)
            {
               if(Boolean(_players[_loc1_].State.Climbing))
               {
                  if(_players[_loc1_].PosY() > PosY())
                  {
                     if(this.hitTestObject(_players[_loc1_].MC))
                     {
                        _players[_loc1_].LadderKnockdown(ConvertToDirection(_players[_loc1_].PosX() - PosX()));
                     }
                  }
               }
            }
            _loc1_++;
         }
      }
      
      private function BodyDust() : void
      {
         var _loc1_:int = 0;
         _loc1_ = -2;
         while(_loc1_ < 3)
         {
            _Handler_Effects.AddEffectAt("BODYFALL",_this_x + _loc1_ * 3,_this_y);
            _loc1_++;
         }
      }
      
      public function UpdateGUI() : void
      {
         _gui_mc.melee.gotoAndStop(_PlayerState.GetMeleeWeapon().Properties.WeaponType);
         if(_PlayerState.CurrentThrowableWeapon.Ammo <= 0)
         {
            _gui_mc.throwable.gotoAndStop("EMPTY");
            _gui_mc.throwable_num.visible = false;
         }
         else
         {
            _gui_mc.throwable.gotoAndStop(_PlayerState.CurrentThrowableWeapon.Properties.WeaponType);
            _gui_mc.throwable_num.visible = true;
            SetNumTo(_gui_mc.throwable_num,_PlayerState.CurrentThrowableWeapon.Ammo);
         }
         UpdateGUIRanged();
         if(_PlayerState.CurrentPowerupWeapon == null)
         {
            _gui_mc.powerup.gotoAndStop("EMPTY");
         }
         else
         {
            _gui_mc.powerup.gotoAndStop(_PlayerState.CurrentPowerupWeapon.Properties.WeaponType);
         }
      }
      
      public function Fall(param1:Boolean = true) : void
      {
         if(!_PlayerState.Falling)
         {
            _lastBounceY = _this_y;
            DropGrabbedPlayer();
            CheckAimDrop();
            if(_PlayerState.Knockdowned)
            {
               if(_PlayerState.AirVelocityY > -0.1)
               {
                  _PlayerState.AirVelocityY = -0.1;
               }
            }
            if(param1)
            {
               if(PressingRight())
               {
                  _PlayerState.AirVelocityX += _PlayerState.RunSpeed - 1;
               }
               if(PressingLeft())
               {
                  _PlayerState.AirVelocityX -= _PlayerState.RunSpeed - 1;
               }
            }
            else if(_PlayerState.Staggering)
            {
               _PlayerState.AirVelocityX = -_PlayerState.LastDirX * _PlayerState.StaggerSpeed;
               _PlayerState.AirVelocityY = -2;
            }
            _PlayerState.Falling = true;
         }
      }
      
      private function ButtonInMeleeRange() : Boolean
      {
         var _loc1_:int = 0;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         _loc1_ = 0;
         while(_loc1_ < m_world.ButtonList.length)
         {
            b = m_world.ButtonList[_loc1_];
            if(Boolean(b.GetUserData().buttonData.Enabled))
            {
               if(CheckCollisionTowardsPlayer(MidPosX(),b.GetPosition().x * 30,_PlayerState.LastDirX))
               {
                  _loc2_ = MidPosX() - b.GetPosition().x * 30;
                  _loc2_ = Math.abs(_loc2_);
                  if(_loc2_ <= 14 && _loc2_ > 4)
                  {
                     _loc3_ = MidPosY() - b.GetPosition().y * 30;
                     if(Math.abs(_loc3_) <= 10)
                     {
                        _button_in_melee_range = true;
                        _button_to_activate = m_world.ButtonList[_loc1_];
                        return true;
                     }
                  }
               }
            }
            _loc1_++;
         }
         return false;
      }
      
      private function BotDodgeBullet() : Boolean
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         if(_BotState.Difficulty == BotState.EASY)
         {
            return false;
         }
         if(_BotState.DodgeBullet)
         {
            return true;
         }
         if(_BotState.Difficulty == BotState.MEDIUM)
         {
            if(Math.random() < 0.7)
            {
               return false;
            }
         }
         if(!_PlayerState.OnGround || Boolean(_PlayerState.Punching))
         {
            return false;
         }
         if(!_PlayerState.CanRoll && Boolean(_PlayerState.Aiming))
         {
            return false;
         }
         if(!_PlayerState.CanRoll && !_PlayerState.Aiming && Math.random() < 0.7)
         {
            return false;
         }
         if(_PlayerState.Aiming)
         {
            if(_BotState.IgnoreDodgeBulletWhileAiming)
            {
               return false;
            }
            if(Boolean(_Handler_ProjectilesUpdater.BulletImpactFrameTime(this,3.1,8)))
            {
               return true;
            }
         }
         else
         {
            if(Boolean(_Handler_ProjectilesUpdater.BulletImpactFrameTime(this,0,8)))
            {
               return true;
            }
            if(_BotState.TargetPlayer != null)
            {
               if(_BotState.TargetPlayer.State.Aiming)
               {
                  _loc1_ = _BotState.TargetPlayer.MidPosX() - MidPosX();
                  _loc2_ = _BotState.TargetPlayer.MidPosY() - MidPosY();
                  _loc3_ = Math.sqrt(_loc1_ * _loc1_ + _loc2_ * _loc2_);
                  if(_loc3_ <= 25)
                  {
                     return true;
                  }
               }
            }
         }
         return false;
      }
      
      private function DeflectBullets() : void
      {
         _Handler_ProjectilesUpdater.DeflectBullets(this);
      }
      
      private function BotCalculatePathGrid(param1:PathNode) : void
      {
         var _loc2_:PathNode = null;
         var _loc3_:PathBind = null;
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         _loc2_ = null;
         _loc3_ = null;
         if(_BotState.NextResultNode != null)
         {
            if(!_PlayerState.OnGround)
            {
               _loc2_ = _BotState.NextResultNode.Node;
            }
            if(_BotState.NextResultNode.PrevBind != null)
            {
               _loc3_ = _BotState.NextResultNode.PrevBind;
               if(Boolean(_PlayerState.Climbing) && _loc3_.MovementType == PathBind.LADDER)
               {
                  return;
               }
               if(Boolean(_PlayerState.Jumping) && _loc3_.MovementType == PathBind.SPRINTJUMP)
               {
                  return;
               }
               if(Boolean(_PlayerState.Diving) && _loc3_.MovementType == PathBind.DIVE)
               {
                  return;
               }
            }
         }
         if(_loc2_ == null)
         {
            _loc2_ = _pathGrid.GetNodeAt(MidPosX(),MidPosY());
         }
         _BotState.Path = _pathGrid.GetPath(_loc2_,param1);
         if(_loc2_ != null)
         {
            if(_loc2_.Avoid)
            {
               _BotState.RunAwayFromHazards = true;
               if(_PlayerState.Aiming)
               {
                  _BotState.Phase = BotState.CANCEL_AIM;
               }
               else
               {
                  _BotState.Phase = BotState.FOLLOW_PATH;
               }
            }
         }
         if(_BotState.Path.length > 0)
         {
            _BotState.Path[_BotState.Path.length - 1].PrevBind = _loc3_;
         }
         if(_BotState.NextResultNode != null)
         {
            _loc4_ = 0;
            _loc5_ = _BotState.Path.length - 2;
            while(_loc5_ > _loc4_)
            {
               if(_BotState.Path[_loc5_].Node == _BotState.NextResultNode.Node)
               {
                  _BotState.Path.splice(_loc5_ + 1,_BotState.Path.length - (_loc5_ + 1));
               }
               _loc5_--;
            }
         }
      }
      
      private function AbortAiming(param1:Boolean = false) : void
      {
         var _loc2_:b2Vec2 = null;
         var _loc3_:b2Body = null;
         _PlayerState.Aiming = false;
         _startAimASAP = false;
         _lazer_mc.visible = false;
         _aim_mc.visible = false;
         CancelAFS();
         if(_PlayerState.CurrentRangeWeapon != null)
         {
            if(_PlayerState.CurrentRangeWeapon.Ammo <= 0 || param1)
            {
               if(param1)
               {
                  _loc2_ = new b2Vec2(_PlayerState.LastDirX * -2,-(2 + Math.random() * 2));
               }
               else
               {
                  _loc2_ = new b2Vec2(_PlayerState.LastDirX * 2,-1);
               }
               _loc3_ = _Handler_Maps.Handler_WorldItems.AddPolygon("wpn_" + _PlayerState.CurrentRangeWeapon.Properties.WeaponType,(MidPosX() + _PlayerState.LastDirX * 5) / 30,(MidPosY() - 3) / 30,0,_loc2_,Math.random() * 30 - 15,null,_PlayerState.LastDirX != 1);
               _loc3_.GetUserData().weaponData = _PlayerState.CurrentRangeWeapon;
               _loc3_.GetUserData().weaponData.Ammo = 0;
               _loc3_.GetUserData().objectData.MC.indicator.visible = false;
               _PlayerState.CurrentRangeWeapon = null;
               UpdateGUIRanged();
            }
         }
      }
      
      private function GrabWeapon() : Boolean
      {
         var _loc1_:b2Body = null;
         _loc1_ = GetClosestReachableWeapon();
         if(_loc1_ != null)
         {
            if(_loc1_.GetUserData().isRanged == true)
            {
               _PlayerState.CurrentRangeWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _loc1_.GetUserData().objectData.ForceDestruction();
               _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentRangeWeapon.Properties.PickupSound,PosX(),PosY());
               return true;
            }
            if(_loc1_.GetUserData().isThrowable == true)
            {
               _PlayerState.CurrentThrowableWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _loc1_.GetUserData().objectData.ForceDestruction();
               _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentThrowableWeapon.Properties.PickupSound,PosX(),PosY());
               return true;
            }
            if(_loc1_.GetUserData().isMelee == true)
            {
               _PlayerState.CurrentMeleeWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _loc1_.GetUserData().objectData.ForceDestruction();
               _Handler_Sounds.PlaySoundAt(_PlayerState.GetMeleeWeapon().Properties.PickupSound,PosX(),PosY());
               return true;
            }
            if(_loc1_.GetUserData().isPowerup == true)
            {
               _PlayerState.CurrentPowerupWeapon = _loc1_.GetUserData().weaponData;
               _Handler_Effects.AddParticle(new particle_data("PICKUP_" + _loc1_.GetUserData().weaponData.Properties.WeaponType,MidPosX(),MidPosY() - 10));
               _loc1_.GetUserData().objectData.ForceDestruction();
               _Handler_Sounds.PlaySoundAt(_PlayerState.CurrentPowerupWeapon.Properties.PickupSound,PosX(),PosY());
               return true;
            }
            if(_loc1_.GetUserData().isHealth == true)
            {
               _PlayerState.HP += _loc1_.GetUserData().weaponData.Ammo;
               _Handler_Sounds.PlaySoundAt(_loc1_.GetUserData().weaponData.Properties.PickupSound,PosX(),PosY());
               _loc1_.GetUserData().objectData.ForceDestruction();
               StartFlashEffect();
               return true;
            }
         }
         return false;
      }
      
      public function Initialize(param1:PlayerAreaData) : void
      {
         var _loc2_:Number = NaN;
         var _loc3_:* = undefined;
         _MapArea = param1;
         _loc2_ = 1;
         if(_static_world_hitbox_mc.hitTestPoint(this.x,this.y,true))
         {
            _loc2_ = -1;
         }
         _loc3_ = 0;
         while(_loc3_ < 100)
         {
            if(!_static_world_hitbox_mc.hitTestPoint(this.x,this.y,true) && !_static_world_cloud_hitbox_mc.hitTestPoint(this.x,this.y,true))
            {
               this.y += _loc2_;
            }
            _loc3_++;
         }
         _this_x = this.x;
         _this_y = this.y;
         _PlayerAnimation.ShowAnimation("idle");
      }
      
      private function ConvertToDirection(param1:Number) : int
      {
         if(param1 == 0)
         {
            return 0;
         }
         return param1 / Math.sqrt(param1 * param1);
      }
      
      private function BotCheckPathProgress() : void
      {
         var _loc1_:PathResultNode = null;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         _loc1_ = _BotState.Path[_BotState.Path.length - 1];
         _loc2_ = MidPosX() - _loc1_.Node.PosX;
         _loc3_ = MidPosY() - _loc1_.Node.PosY;
         if(Math.abs(_loc2_) <= BotState.DISTANCE_NODE_TOLERANCE_X)
         {
            if(_loc3_ >= BotState.DISTANCE_NODE_TOLERANCE_Y_MAX && _loc3_ <= BotState.DISTANCE_NODE_TOLERANCE_Y_MIN)
            {
               if(_loc1_.NextBind != null)
               {
                  if(!_PlayerState.OnGround)
                  {
                     if(_loc1_.NextBind.MovementType == PathBind.DIVE)
                     {
                        return;
                     }
                     if(_loc1_.NextBind.MovementType == PathBind.SPRINTJUMP || _loc1_.NextBind.MovementType == PathBind.JUMP)
                     {
                        if(_PlayerState.AirVelocityY > _PlayerState.PlayerJumpPower + 2)
                        {
                           return;
                        }
                     }
                  }
               }
               _BotState.Path.splice(_BotState.Path.length - 1,1);
               _BotState.DoFireCheck = true;
               return;
            }
            if(_loc3_ < 0)
            {
               if(_loc1_.NextBind != null)
               {
                  if(_loc1_.NextBind.MovementType == PathBind.ROAD)
                  {
                     _loc4_ = Math.abs(_loc3_);
                     while(_loc4_ >= 2)
                     {
                        if(_static_objects_hitbox_mc.hitTestPoint(_this_x,MidPosY() + _loc4_,true))
                        {
                           _BotState.Path.splice(_BotState.Path.length - 1,1);
                           _BotState.DoFireCheck = true;
                           return;
                        }
                        _loc4_ -= 2;
                     }
                  }
               }
            }
         }
      }
      
      private function GetGibBodyNearPlayer() : b2Body
      {
         var _loc1_:b2Body = null;
         var _loc2_:int = 0;
         _loc2_ = -4;
         while(_loc2_ <= 4)
         {
            _loc1_ = GetDynamicBodyAt(_this_x + _loc2_,_this_y - 4,false);
            if(_loc1_ != null)
            {
               if(Boolean(_loc1_.GetUserData().objectData.CanGibb))
               {
                  if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x,_this_y + 2,true)) && !_loc1_.GetUserData().objectData.CollisionMC.hitTestPoint(_this_x,_this_y + 2,true))
                  {
                     return _loc1_;
                  }
                  if(Boolean(_static_world_hitbox_mc.hitTestPoint(_this_x + _loc2_,_this_y + 2,true)) && !_loc1_.GetUserData().objectData.CollisionMC.hitTestPoint(_this_x + _loc2_,_this_y + 2,true))
                  {
                     return _loc1_;
                  }
               }
            }
            _loc2_ += 4;
         }
         return null;
      }
      
      private function CheckForceKneeling() : Boolean
      {
         return CheckCollisionHeight(12,_PlayerState.MaxPlayerHeight);
      }
      
      private function KneelReleased() : void
      {
         _PlayerState.DisableKneel = false;
      }
      
      private function BotRandomize() : void
      {
         switch(Math.floor(Math.random() * 3.999))
         {
            case 0:
               _BotState.FollowToAimMinimumDistance = 10;
               break;
            case 1:
               _BotState.FollowToAimMinimumDistance = 30;
               break;
            case 2:
               _BotState.FollowToAimMinimumDistance = 60;
               break;
            case 3:
               _BotState.FollowToAimMinimumDistance = 100;
         }
         switch(_BotState.Difficulty)
         {
            case BotState.EASY:
               _BotState.RunOften = false;
               break;
            case BotState.MEDIUM:
               _BotState.RunOften = Math.random() < 0.4;
               break;
            case BotState.HARD:
               _BotState.RunOften = true;
         }
         if(_BotState.Difficulty == BotState.EASY)
         {
            _BotState.FollowToAimMinimumDistance += 40;
         }
         if(_BotState.Difficulty == BotState.MEDIUM && Math.random() < 0.5)
         {
            _BotState.FollowToAimMinimumDistance += 20;
         }
         _BotState.MeleeToAimMinimumChance = 0.2 + Math.random() * 0.7;
         if(Math.random() < 0.4)
         {
            _BotState.IgnoreDodgeBulletWhileAiming = true;
         }
         else
         {
            _BotState.IgnoreDodgeBulletWhileAiming = false;
         }
      }
      
      private function CheckAimDrop(param1:Boolean = false) : void
      {
         if(_PlayerState.Aiming)
         {
            if(_PlayerState.AimMode == 1)
            {
               DropThrowable();
            }
            if(_PlayerState.AimMode == 0)
            {
               AbortAiming(param1);
            }
         }
      }
      
      private function GetBodyAbovePlayer() : b2Body
      {
         var _loc1_:b2Body = null;
         _loc1_ = GetDynamicBodyAt(_this_x,_this_y - _PlayerState.PlayerHeight,false);
         if(_loc1_ != null)
         {
            return _loc1_;
         }
         _loc1_ = GetDynamicBodyAt(_this_x - 4,_this_y - _PlayerState.PlayerHeight,false);
         if(_loc1_ != null)
         {
            return _loc1_;
         }
         _loc1_ = GetDynamicBodyAt(_this_x + 4,_this_y - _PlayerState.PlayerHeight,false);
         if(_loc1_ != null)
         {
            return _loc1_;
         }
         return null;
      }
      
      private function DeactivateSprint() : void
      {
         _Handler_Output.Trace("Sprint Off");
         _PlayerState.Sprinting = false;
      }
      
      private function CheckForceKnockdown() : Boolean
      {
         return CheckCollisionHeight(6,12);
      }
      
      private function GetStaticBodyAt(param1:Number, param2:Number) : b2Body
      {
         if(HitTestWorldOnly(param1,param2))
         {
            return m_world.GetStaticBodyAt(param1,param2);
         }
         return null;
      }
      
      private function RangedUp() : void
      {
         if(Boolean(_PlayerState.StuckToRocket) || Boolean(_PlayerState.Staggering))
         {
            return;
         }
         _startAimASAP = false;
         if(!_PlayerState.Throwing && Boolean(_PlayerState.Aiming) && !_PlayerState.AimTurningAroundDelay)
         {
            if(_PlayerState.AimMode == 0)
            {
               _PlayerState.BackToIdleTimer = 6;
               FireWeapon();
            }
         }
      }
      
      private function HitTestWorld(param1:Number, param2:Number) : Boolean
      {
         if(_static_world_hitbox_mc.hitTestPoint(param1,param2,true))
         {
            return true;
         }
         if(_static_world_cloud_hitbox_mc.hitTestPoint(param1,param2,true))
         {
            return true;
         }
         return false;
      }
      
      private function CancelAFS() : void
      {
         _PlayerState.CancelAFS();
         _cancelAimingASAP = false;
         if(_flameAwayActivated)
         {
            clearInterval(_flameAwayTimer);
            _flameAwayActivated = false;
         }
      }
      
      public function SetAI(param1:Number) : void
      {
         _bot = true;
         _BotState = new BotState();
         _BotState.Difficulty = param1;
         if(_BotState.Difficulty == BotState.EASY)
         {
            _PlayerState.ImmunityDisabled = true;
         }
         _Handler_Output.Trace("Bot difficulty set to: " + _BotState.Difficulty);
      }
      
      private function AimRight() : void
      {
         if(_PlayerState.LastDirX == -1)
         {
            _PlayerState.FastTrigger = false;
            _lazer_mc.visible = false;
            _aim_mc.visible = false;
            CancelAFS();
            _PlayerState.AimTurningAround = true;
            this.scaleX = 1;
            _collision_mc.scaleX = this.scaleX;
            _PlayerState.LastDirX = 1;
            _PlayerState.CurrentAimPitch = 0;
            _PlayerState.CurrentChangePitchSpeed = 0;
         }
      }
      
      private function StartFlashEffect() : void
      {
         var _loc1_:Color = null;
         _loc1_ = new Color();
         _loc1_.brightness = 1;
         this.transform.colorTransform = _loc1_;
         _PlayerState.ShowFlashEffect = true;
      }
   }
}

