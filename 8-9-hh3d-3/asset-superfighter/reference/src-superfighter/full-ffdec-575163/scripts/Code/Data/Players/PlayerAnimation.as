package Code.Data.Players
{
   import Code.Handler.OutputTrace;
   import flash.display.MovieClip;
   
   public class PlayerAnimation
   {
      private var _this_gui:MovieClip;
      
      private var _animation_done:Boolean = false;
      
      private var _disable_slowmotion_modifier:Boolean = false;
      
      private var _aim_animation:Boolean = false;
      
      private var _is_rocket_ride:Boolean = false;
      
      private var _collision_mc:MovieClip;
      
      private var _help_animation:Boolean = false;
      
      private var _animation_done_func:Function;
      
      private var _current_frame:Number = 1;
      
      private var _next_blink_timer:Number = 0;
      
      private var _current_animation:String = "";
      
      private var _rotate_speed:Number = 0;
      
      private var _grabbed_player_updated:Boolean = false;
      
      private var _loop_animation:Boolean = false;
      
      private var _PlayerState:PlayerState;
      
      public var UseGUI:Boolean = true;
      
      private var _delay_timer:Number = 0;
      
      private var _rotate_increase:Number = 0;
      
      private var _delay_frame:int = -1;
      
      private var _Handler_Output:OutputTrace;
      
      private var _blood_gui:MovieClip;
      
      private var _blood:MovieClip;
      
      private var _blink_duration_timer:Number = 0;
      
      private var _this:MovieClip;
      
      public function PlayerAnimation(param1:MovieClip, param2:MovieClip, param3:MovieClip, param4:PlayerState, param5:OutputTrace)
      {
         _current_frame = 1;
         _loop_animation = false;
         _animation_done = false;
         _help_animation = false;
         _aim_animation = false;
         _disable_slowmotion_modifier = false;
         _grabbed_player_updated = false;
         _current_animation = "";
         _is_rocket_ride = false;
         _rotate_speed = 0;
         _rotate_increase = 0;
         _delay_frame = -1;
         _delay_timer = 0;
         _next_blink_timer = 0;
         _blink_duration_timer = 0;
         UseGUI = true;
         super();
         _this = param1;
         _blood = param2;
         _collision_mc = param3;
         _PlayerState = param4;
         _Handler_Output = param5;
      }
      
      private function AnimationDone() : void
      {
         if(_PlayerState.Knockdowned)
         {
            _PlayerState.Knockdowned = false;
         }
         if(_PlayerState.Rolling)
         {
            _PlayerState.Rolling = false;
         }
         if(_PlayerState.Kicking)
         {
            _PlayerState.Kicking = false;
         }
         if(_PlayerState.Throwing)
         {
            _PlayerState.Throwing = false;
         }
         if(_PlayerState.Punching)
         {
            _PlayerState.Punching = false;
         }
         if(_PlayerState.AimTurningAround)
         {
            _PlayerState.AimTurningAround = false;
         }
         if(_PlayerState.DeathKneel)
         {
            _PlayerState.Falling = true;
            _PlayerState.AirVelocityX = _PlayerState.LastDirX * 1.7;
            _PlayerState.AirVelocityY = -1.5;
         }
      }
      
      public function get GrabRotation() : Number
      {
         return _this.ANIM.HELPMC.rotation;
      }
      
      private function FallingFoward() : Boolean
      {
         if(_PlayerState.LastDirX == 1 && _PlayerState.AirVelocityX >= 0 || _PlayerState.LastDirX == -1 && _PlayerState.AirVelocityX < 0)
         {
            return true;
         }
         return false;
      }
      
      private function UpdateAnimation() : void
      {
         _blood.visible = _PlayerState.BloodVisible;
         if(UseGUI)
         {
            _blood_gui.visible = _PlayerState.BloodVisible;
         }
         if(_PlayerState.IsImmune)
         {
            --_next_blink_timer;
            if(_next_blink_timer <= 0)
            {
               _this.alpha = 0.2;
               if(UseGUI)
               {
                  _this_gui.alpha = 0.2;
               }
               --_blink_duration_timer;
               if(_blink_duration_timer <= 0)
               {
                  _blink_duration_timer = 1;
                  _next_blink_timer = 3;
               }
            }
            else
            {
               _this.alpha = 1;
               if(UseGUI)
               {
                  _this_gui.alpha = 1;
               }
            }
         }
         else
         {
            _this.alpha = 1;
            if(UseGUI)
            {
               _this_gui.alpha = 1;
            }
            _next_blink_timer = 0;
            _blink_duration_timer = 1;
         }
         if(_PlayerState.IgnoreMe)
         {
            ShowAnimation("EMPTY");
         }
         else if(_PlayerState.StuckToRocket)
         {
            if(_PlayerState.RocketRideProjectile.DirectionX > 0)
            {
               ShowAnimation("ROCKET_RIDE_R");
            }
            else
            {
               ShowAnimation("ROCKET_RIDE_L");
            }
         }
         else if(_PlayerState.DeathKneel)
         {
            ShowAnimation("DEATH_KNEEL");
         }
         else if(_PlayerState.GrabbedByPlayer)
         {
            ShowAnimation("GRABBED");
         }
         else if(_PlayerState.Staggering)
         {
            ShowAnimation("STAGGER");
         }
         else if(_PlayerState.Climbing)
         {
            if(_PlayerState.ClimbingDirection == 1)
            {
               ShowAnimation("SLIDE");
            }
            else
            {
               ShowAnimation("CLIMB");
            }
         }
         else if(_PlayerState.Knockdowned)
         {
            ShowAnimation("KNOCKDOWN");
         }
         else if(_PlayerState.Falling)
         {
            if(FallingFoward())
            {
               ShowAnimation("FALL_F");
            }
            else
            {
               ShowAnimation("FALL_B");
            }
         }
         else if(_PlayerState.IsStunned)
         {
            ShowAnimation("STUN_0" + _PlayerState.StunAnimation);
         }
         else if(_PlayerState.Aiming)
         {
            if(_PlayerState.AimMode == 0)
            {
               if(_PlayerState.AimTurningAround)
               {
                  ShowAnimation("start_" + _PlayerState.CurrentRangeWeapon.Properties.AnimType);
               }
               else
               {
                  ShowAnimation("aim_" + _PlayerState.CurrentRangeWeapon.Properties.AnimType);
               }
            }
            else if(_PlayerState.AimMode == 1)
            {
               if(_PlayerState.AimTurningAround)
               {
                  ShowAnimation("aim_turn");
               }
               else
               {
                  ShowAnimation("aim_" + _PlayerState.CurrentThrowableWeapon.Properties.AnimType);
               }
            }
         }
         else if(_PlayerState.Throwing)
         {
            ShowAnimation("THROW");
         }
         else if(_PlayerState.Diving)
         {
            ShowAnimation("DIVE");
         }
         else if(_PlayerState.Jumping)
         {
            if(_PlayerState.JumpKickPerformed)
            {
               ShowAnimation("JUMPKICK");
            }
            else
            {
               ShowAnimation("JUMP");
            }
         }
         else if(_PlayerState.Rolling)
         {
            if(Boolean(_current_animation) && _animation_done)
            {
               ShowAnimation("ROLL",true);
            }
            else
            {
               ShowAnimation("ROLL");
            }
         }
         else if(_PlayerState.Kicking)
         {
            ShowAnimation("KICK");
         }
         else if(_PlayerState.Punching)
         {
            ShowAnimation(_PlayerState.MeleeAnimation + "_0" + _PlayerState.PunchComboNr);
         }
         else if(_PlayerState.Kneeling)
         {
            ShowAnimation("KNEEL");
         }
         else if(_PlayerState.TakingCover)
         {
            ShowAnimation("COVER");
         }
         else if(_PlayerState.MovingDirectionX == 0)
         {
            ShowAnimation("IDLE");
         }
         else if(_PlayerState.Sprinting)
         {
            ShowAnimation("SPRINT");
         }
         else
         {
            ShowAnimation("RUN");
         }
      }
      
      public function NewSkin(param1:MovieClip) : void
      {
         _this = param1;
         ShowAnimation(_current_animation,true);
      }
      
      public function ShowAnimation(param1:String, param2:Boolean = false) : void
      {
         if(_current_animation != param1.toUpperCase() || param2)
         {
            _current_animation = param1.toUpperCase();
            if(param2)
            {
               _this.gotoAndStop("IDLE");
               if(UseGUI)
               {
                  _this_gui.gotoAndStop("IDLE");
                  _blood_gui.gotoAndStop("IDLE");
               }
               _collision_mc.gotoAndStop("IDLE");
               _blood.gotoAndStop("IDLE");
            }
            _this.gotoAndStop(param1.toUpperCase());
            if(UseGUI)
            {
               _this_gui.gotoAndStop(param1.toUpperCase());
               _blood_gui.gotoAndStop(param1.toUpperCase());
            }
            _collision_mc.gotoAndStop(param1.toUpperCase());
            _blood.gotoAndStop(param1.toUpperCase());
            _current_frame = 0;
            _aim_animation = false;
            _animation_done = false;
            _loop_animation = false;
            _help_animation = false;
            _grabbed_player_updated = false;
            _disable_slowmotion_modifier = false;
            _is_rocket_ride = false;
            switch(param1.toUpperCase())
            {
               case "ROCKET_RIDE_L":
               case "ROCKET_RIDE_R":
                  _is_rocket_ride = true;
                  _loop_animation = true;
                  break;
               case "AIM_TURN":
                  _disable_slowmotion_modifier = true;
                  break;
               case "CLIMB":
               case "IDLE":
               case "STAGGER":
               case "SPRINT":
               case "GRABBED":
               case "RUN":
                  _loop_animation = true;
                  break;
               case "DIVE":
                  _help_animation = true;
                  _loop_animation = true;
                  _rotate_speed = 1.5;
                  _rotate_increase = 0;
                  break;
               case "FALL_B":
               case "FALL_F":
                  _help_animation = true;
                  _loop_animation = true;
                  if(param1.toUpperCase() == "FALL_B")
                  {
                     _rotate_speed = -10;
                     _rotate_increase = -2;
                  }
                  else
                  {
                     _rotate_speed = 10;
                     _rotate_increase = 2;
                  }
                  break;
               default:
                  if(param1.toUpperCase().substr(0,3) == "AIM")
                  {
                     _aim_animation = true;
                     _loop_animation = true;
                  }
                  if(param1.toUpperCase().substr(0,5) == "START")
                  {
                     _disable_slowmotion_modifier = true;
                  }
            }
         }
      }
      
      public function NextFrame(param1:Number) : int
      {
         return Math.floor(_current_frame + param1);
      }
      
      public function set GrabRotation(param1:Number) : void
      {
         _this.ANIM.DOLL.rotation = param1;
         _collision_mc.ANIM.DOLL.rotation = param1;
         _blood.ANIM.DOLL.rotation = param1;
      }
      
      public function get CurrentFrame() : int
      {
         return Math.floor(_current_frame);
      }
      
      public function SetGUISkin(param1:MovieClip, param2:MovieClip) : void
      {
         if(!UseGUI)
         {
            return;
         }
         _this_gui = param1;
         _blood_gui = param2;
         ShowAnimation(_current_animation,true);
      }
      
      public function ProgressAnimation(param1:Number) : void
      {
         var _loc2_:int = 0;
         var _loc3_:MovieClip = null;
         var _loc4_:MovieClip = null;
         var _loc5_:MovieClip = null;
         var _loc6_:MovieClip = null;
         var _loc7_:MovieClip = null;
         var _loc8_:int = 0;
         UpdateAnimation();
         if(!_animation_done)
         {
            if(_delay_frame == CurrentFrame)
            {
               if(_delay_timer > 0)
               {
                  _delay_timer -= param1;
                  if(_delay_timer <= 0)
                  {
                     _delay_frame = -1;
                  }
                  return;
               }
            }
            if(_current_frame == 0)
            {
               _current_frame = 1;
               return;
            }
            if(_is_rocket_ride)
            {
               _PlayerState.LastDirX = 1;
               _this.ANIM.rotation = _PlayerState.RocketRideProjectile.Angle;
               if(UseGUI)
               {
                  _this_gui.ANIM.rotation = _PlayerState.RocketRideProjectile.Angle;
                  _blood_gui.ANIM.rotation = _PlayerState.RocketRideProjectile.Angle;
               }
               _collision_mc.ANIM.rotation = _PlayerState.RocketRideProjectile.Angle;
               _blood.ANIM.rotation = _PlayerState.RocketRideProjectile.Angle;
               _current_frame += 1;
            }
            else if(_help_animation)
            {
               _current_frame += 1;
            }
            else
            {
               if(_aim_animation)
               {
                  _this.ANIM_WPN.rotation = _PlayerState.CurrentAimPitch;
                  if(UseGUI)
                  {
                     _this_gui.ANIM_WPN.rotation = _PlayerState.CurrentAimPitch;
                     _blood_gui.ANIM_WPN.rotation = _PlayerState.CurrentAimPitch;
                  }
                  _collision_mc.ANIM_WPN.rotation = _PlayerState.CurrentAimPitch;
                  _blood.ANIM_WPN.rotation = _PlayerState.CurrentAimPitch;
                  if(_PlayerState.AFSInProgress)
                  {
                     _loc2_ = int(_PlayerState.CurrentRangeWeapon.Properties.FireSequence[_PlayerState.LastFireFrame - 1].FrameNr);
                  }
                  else
                  {
                     _loc2_ = 1;
                  }
                  _this.ANIM_WPN.gotoAndStop(_loc2_);
                  if(UseGUI)
                  {
                     _this_gui.ANIM_WPN.gotoAndStop(_loc2_);
                     _blood_gui.ANIM_WPN.gotoAndStop(_loc2_);
                  }
                  _collision_mc.ANIM_WPN.gotoAndStop(_loc2_);
                  _blood.ANIM_WPN.gotoAndStop(_loc2_);
                  return;
               }
               if(_current_animation == "CLIMB" && !_PlayerState.ClimbingAround)
               {
                  _loc2_ = Math.floor(_current_frame);
                  _this.ANIM.gotoAndStop(_loc2_);
                  if(UseGUI)
                  {
                     _this_gui.ANIM.gotoAndStop(_loc2_);
                     _blood_gui.ANIM.gotoAndStop(_loc2_);
                  }
                  _collision_mc.ANIM.gotoAndStop(_loc2_);
                  _blood.ANIM.gotoAndStop(_loc2_);
                  return;
               }
               if(_current_frame >= 4 && _current_animation == "KNOCKDOWN" && (_PlayerState.CantRise || _PlayerState.HP <= 0))
               {
                  _current_frame = 4;
               }
               else if(!_disable_slowmotion_modifier)
               {
                  if(_current_animation == "KNOCKDOWN")
                  {
                     if(_current_frame < 9)
                     {
                        _current_frame += param1 * _PlayerState.KnockdownRiseSpeed;
                        if(_current_frame >= 9)
                        {
                           _PlayerState.ImmunityTimer = PlayerState.KNOCKDOWN_IMMUNITY_TIME;
                        }
                     }
                     else
                     {
                        _current_frame += param1 * _PlayerState.KnockdownRiseSpeed;
                     }
                  }
                  else
                  {
                     _current_frame += param1;
                  }
               }
               else
               {
                  _current_frame += 1;
               }
            }
            if(_help_animation)
            {
               _loc3_ = _this.ANIM.HELPMC;
               _loc4_ = _collision_mc.ANIM.HELPMC;
               _loc5_ = _blood.ANIM.HELPMC;
               if(UseGUI)
               {
                  _loc7_ = _blood_gui.ANIM.HELPMC;
                  _loc6_ = _this_gui.ANIM.HELPMC;
               }
               _loc3_.rotation += _rotate_speed * param1;
               _loc4_.rotation = _loc3_.rotation;
               _loc5_.rotation = _loc3_.rotation;
               if(UseGUI)
               {
                  _loc6_.rotation = _loc3_.rotation;
                  _loc7_.rotation = _loc3_.rotation;
               }
               if(Math.sqrt(_rotate_speed * _rotate_speed) < 36)
               {
                  _rotate_speed += _rotate_increase * param1;
               }
               if(_current_animation == "DIVE")
               {
                  if(_PlayerState.GrabbedPlayer)
                  {
                     if(!_grabbed_player_updated)
                     {
                        _grabbed_player_updated = true;
                     }
                  }
               }
            }
            else
            {
               _loc3_ = _this.ANIM;
               _loc4_ = _collision_mc.ANIM;
               _loc5_ = _blood.ANIM;
               if(UseGUI)
               {
                  _loc6_ = _this_gui.ANIM;
                  _loc7_ = _blood_gui.ANIM;
               }
            }
            _loc8_ = Math.floor(_current_frame);
            if(_loc8_ > _loc3_.totalFrames)
            {
               AnimationDone();
               if(_loop_animation)
               {
                  _current_frame = 1;
                  _loc8_ = 1;
               }
               else
               {
                  _animation_done = true;
               }
            }
            if(!_grabbed_player_updated)
            {
               _loc3_.gotoAndStop(_loc8_);
               _loc4_.gotoAndStop(_loc8_);
               _loc5_.gotoAndStop(_loc8_);
               if(UseGUI)
               {
                  _loc6_.gotoAndStop(_loc8_);
                  _loc7_.gotoAndStop(_loc8_);
               }
            }
            if(_collision_mc.currentFrame == _this.currentFrame)
            {
               if(_loc4_.currentFrame == _loc3_.currentFrame)
               {
                  if(_loc5_.currentFrame != _loc3_.currentFrame)
                  {
                  }
               }
            }
         }
         else
         {
            AnimationDone();
         }
      }
      
      public function get Progress() : Number
      {
         return CurrentFrame / LastFrame;
      }
      
      public function get LastFrame() : int
      {
         return _this.ANIM.totalFrames;
      }
      
      public function DelayAnimation(param1:int, param2:Number) : void
      {
         _delay_frame = param1;
         _delay_timer = param2;
      }
   }
}

