package Code.Data
{
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Data.Players.Player;
   import Code.Handler.Effects;
   import Code.Particles.*;
   import flash.display.*;
   
   public class FireNodeData
   {
      private var _b2BodyBurning:b2Body = null;
      
      private var _Handler_Effects:Effects;
      
      private var _ownerResetTimer:Number;
      
      private var _passCloud:Number = 0;
      
      private var _onlyBurnWakeTimer:Number = 0;
      
      private var _lastEffectX:Number;
      
      private var _lastEffectY:Number;
      
      private var _owner:int = -1;
      
      private var _velX:Number;
      
      private var _velY:Number;
      
      private var _b2BodyLocalPosition:b2Vec2;
      
      private var _slowingDown:Boolean = true;
      
      private var _lifeSpan:Number = 10;
      
      private var _air_mc:MovieClip;
      
      private var _currentFrame:Number;
      
      private var _playerBurnLevel:int = 0;
      
      private var _fire_area_mc:MovieClip;
      
      private var _playerBurnTarget:Player = null;
      
      private var _posX:Number;
      
      private var _playerNr:int = -1;
      
      private var _inAir:Boolean = true;
      
      private var _posY:Number;
      
      private var _b2Body:b2Body = null;
      
      private var _air_mc_removed:Boolean = false;
      
      private var _burn_timer:Number;
      
      private var _fire_node_done:Boolean = false;
      
      private var _effect_timer:Number = 0;
      
      private var _fireType:int = 0;
      
      public function FireNodeData(param1:Effects, param2:MovieClip, param3:Number, param4:Number, param5:Number, param6:Number, param7:Number, param8:int = -1, param9:int = 0)
      {
         _fire_node_done = false;
         _inAir = true;
         _air_mc_removed = false;
         _effect_timer = 0;
         _b2Body = null;
         _b2BodyBurning = null;
         _playerBurnTarget = null;
         _playerNr = -1;
         _playerBurnLevel = 0;
         _lifeSpan = 10;
         _slowingDown = true;
         _owner = -1;
         _fireType = 0;
         _onlyBurnWakeTimer = 0;
         _passCloud = 0;
         super();
         _Handler_Effects = param1;
         _burn_timer = param3;
         _posX = param4;
         _posY = param5;
         _velX = param6;
         _velY = param7;
         _lastEffectX = _posX;
         _lastEffectY = _posY;
         _owner = param8;
         _ownerResetTimer = 24;
         _fireType = param9;
         _currentFrame = 0;
         _effect_timer = Math.random() * 3;
         _fire_area_mc = new MovieClip();
         _fire_area_mc.graphics.lineStyle(1,16776960,1,false,"none");
         _fire_area_mc.graphics.beginFill(16776960,0.4);
         _fire_area_mc.graphics.drawCircle(0,0,5);
         _fire_area_mc.graphics.endFill();
         param2.addChild(_fire_area_mc);
         _fire_area_mc.x = _posX;
         _fire_area_mc.y = _posY;
         _passCloud = 0;
         switch(_fireType)
         {
            case 0:
               _air_mc = new fire_effect_air();
               break;
            case 1:
               _air_mc = new fire_effect_flamethrower_air();
               _passCloud = 8;
               break;
            default:
               _air_mc = new fire_effect_air();
         }
         _Handler_Effects.EffectMCFront.addChild(_air_mc);
         _air_mc_removed = false;
      }
      
      public function get VelY() : Number
      {
         return _velY;
      }
      
      public function get SlowingDown() : Boolean
      {
         return _slowingDown;
      }
      
      public function get PassCloud() : Boolean
      {
         return _passCloud > 0;
      }
      
      public function get PlayerNR() : int
      {
         return _playerNr;
      }
      
      public function set PosY(param1:Number) : void
      {
         _posY = param1;
      }
      
      public function get FireArea() : MovieClip
      {
         if(_lifeSpan > 6)
         {
            return _fire_area_mc;
         }
         return new MovieClip();
      }
      
      public function FollowBody(param1:b2Body, param2:b2Vec2) : void
      {
         var _loc3_:b2Vec2 = null;
         _b2Body = param1;
         _b2BodyLocalPosition = param2;
         _b2BodyBurning = null;
         _playerBurnTarget = null;
         _playerNr = -1;
         _loc3_ = _b2Body.GetWorldPoint(_b2BodyLocalPosition);
         _posX = _loc3_.x * 30;
         _posY = _loc3_.y * 30;
         _lastEffectX = _posX;
         _lastEffectY = _posY;
         _inAir = false;
         if(!_air_mc_removed)
         {
            _air_mc.parent.removeChild(_air_mc);
            _air_mc_removed = true;
         }
      }
      
      public function get BurnTimer() : Number
      {
         return _burn_timer;
      }
      
      public function set VelX(param1:Number) : void
      {
         _velX = param1;
      }
      
      private function AddEffectGround(param1:Boolean = false) : void
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         _lastEffectX = _posX;
         _lastEffectY = _posY;
         if(_fireType == 1 && _currentFrame <= _air_mc.totalFrames - 2)
         {
            _Handler_Effects.AddParticle(new particle_data("FIRE_FLAMETHROWER",_posX + Math.random() * 6 - 3,_posY + Math.random(),new b2Vec2(_velX,_velY)));
         }
         else
         {
            _Handler_Effects.AddParticle(new particle_data("fire",_posX + Math.random() * 6 - 3,_posY + Math.random()));
         }
         if(param1)
         {
            if(Math.random() < 0.4)
            {
               _loc2_ = _posX + Math.random() * 6 - 3;
               _loc3_ = _posY + Math.random();
               _Handler_Effects.AddParticle(new particle_data("fireground",_loc2_,_loc3_));
               if(Math.random() <= 0.5)
               {
                  _Handler_Effects.AddParticle(new particle_data("smoke_fire",_loc2_,_loc3_));
               }
            }
         }
      }
      
      public function get Owner() : int
      {
         return _owner;
      }
      
      public function get VelX() : Number
      {
         return _velX;
      }
      
      public function get CanBeMerged() : Boolean
      {
         if(_inAir)
         {
            return false;
         }
         if(_playerBurnTarget != null)
         {
            return false;
         }
         return true;
      }
      
      public function set InAir(param1:Boolean) : void
      {
         _inAir = param1;
      }
      
      public function get PosX() : Number
      {
         return _posX;
      }
      
      public function set BurnTimer(param1:Number) : void
      {
         _burn_timer = param1;
      }
      
      public function BurnPlayer(param1:Player, param2:int, param3:int) : void
      {
         _b2Body = null;
         _b2BodyBurning = null;
         _playerBurnTarget = param1;
         _playerNr = param2;
         _playerBurnLevel = param3;
         _inAir = false;
         if(!_air_mc_removed)
         {
            _air_mc.parent.removeChild(_air_mc);
            _air_mc_removed = true;
         }
         if(_playerBurnLevel == 1)
         {
            _fire_area_mc.graphics.clear();
            _fire_area_mc.graphics.lineStyle(1,16776960,1,false,"none");
            _fire_area_mc.graphics.beginFill(16776960,0.4);
            _fire_area_mc.graphics.moveTo(-4,8);
            _fire_area_mc.graphics.lineTo(-4,-8);
            _fire_area_mc.graphics.lineTo(4,-8);
            _fire_area_mc.graphics.lineTo(4,8);
            _fire_area_mc.graphics.lineTo(4,8);
            _fire_area_mc.graphics.endFill();
         }
         else if(_playerBurnLevel == 2)
         {
            _fire_area_mc.graphics.clear();
            _fire_area_mc.addChild(new fire_big());
         }
         _posX = _playerBurnTarget.MidPosX();
         _posY = _playerBurnTarget.MidPosY();
         _lastEffectX = _posX;
         _lastEffectY = _posY;
         UpdateMC();
      }
      
      public function BurnBody(param1:b2Body) : void
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:b2Vec2 = null;
         _b2BodyBurning = param1;
         _b2Body = null;
         _playerBurnTarget = null;
         _playerNr = -1;
         _loc2_ = Number(param1.m_userData.objectData.ShapeMC.width);
         _loc3_ = Number(param1.m_userData.objectData.ShapeMC.height);
         _loc4_ = Math.sqrt(_loc2_ * _loc2_ + _loc3_ * _loc3_) / 2;
         if(_loc4_ < 5)
         {
            _loc4_ = 5;
         }
         _fire_area_mc.graphics.clear();
         _fire_area_mc.graphics.lineStyle(1,16776960,1,false,"none");
         _fire_area_mc.graphics.beginFill(16776960,0.4);
         _fire_area_mc.graphics.drawCircle(0,0,_loc4_);
         _fire_area_mc.graphics.endFill();
         _loc5_ = _b2BodyBurning.GetWorldPoint(new b2Vec2(0,0));
         _posX = _loc5_.x * 30;
         _posY = _loc5_.y * 30;
         _lastEffectX = _posX;
         _lastEffectY = _posY;
         UpdateMC();
         _lifeSpan = 0;
         _inAir = false;
         if(!_air_mc_removed)
         {
            _air_mc.parent.removeChild(_air_mc);
            _air_mc_removed = true;
         }
      }
      
      public function get PosY() : Number
      {
         return _posY;
      }
      
      public function UpdateMC() : void
      {
         _fire_area_mc.x = _posX;
         _fire_area_mc.y = _posY;
      }
      
      public function get FireNodeCompleted() : Boolean
      {
         return _fire_node_done;
      }
      
      public function set SlowingDown(param1:Boolean) : void
      {
         _slowingDown = param1;
      }
      
      public function get InAir() : Boolean
      {
         return _inAir;
      }
      
      public function set PosX(param1:Number) : void
      {
         _posX = param1;
      }
      
      public function get TotalVel() : Number
      {
         return Math.sqrt(_velY * _velY + _velX * _velX);
      }
      
      public function End() : void
      {
         if(!_air_mc_removed)
         {
            _air_mc.parent.removeChild(_air_mc);
            _air_mc_removed = true;
         }
         _fire_area_mc.parent.removeChild(_fire_area_mc);
         _fire_node_done = true;
      }
      
      public function Update(param1:Number) : void
      {
         var _loc2_:b2Vec2 = null;
         if(_passCloud > 0)
         {
            _passCloud -= param1;
         }
         if(_playerBurnTarget != null)
         {
            if(_playerBurnTarget.State.IgnoreMe)
            {
               _burn_timer = 0;
            }
            if(_playerBurnLevel == 1 && _playerBurnTarget.State.BurnState < _playerBurnTarget.State.FireRank1Minimum)
            {
               _playerBurnTarget.State.FireRank1Attached = false;
               _burn_timer = 0;
            }
            if(_playerBurnLevel == 2 && _playerBurnTarget.State.BurnState < _playerBurnTarget.State.FireRank2Minimum)
            {
               _playerBurnTarget.State.FireRank2Attached = false;
               _burn_timer = 0;
            }
            if(_playerBurnTarget.State.BurnState > 0)
            {
               _playerBurnTarget.FireContact();
               _posX = _playerBurnTarget.MidPosX();
               _posY = _playerBurnTarget.MidPosY();
               UpdateMC();
               _effect_timer -= param1;
               if(_effect_timer <= 0)
               {
                  AddEffectPlayer();
                  _effect_timer = 3;
               }
               else if(EffectDistancePass(4))
               {
                  AddEffectPlayer();
                  _effect_timer = 3;
               }
            }
         }
         else if(_b2BodyBurning != null)
         {
            _loc2_ = _b2BodyBurning.GetWorldPoint(new b2Vec2(0,0));
            _posX = _loc2_.x * 30;
            _posY = _loc2_.y * 30;
            UpdateMC();
            _lifeSpan += param1;
            _effect_timer -= param1;
            if(_effect_timer <= 0)
            {
               AddEffectDynamic();
               _effect_timer = 2 + Math.random();
            }
            else if(EffectDistancePass(4))
            {
               AddEffectDynamic(4);
               _effect_timer = 3 + Math.random() * 2;
            }
            if(_b2BodyBurning.m_userData.destroyed == true)
            {
               _burn_timer = 0;
            }
            else
            {
               _b2BodyBurning.m_userData.objectData.Damage_Fire(param1);
               if(Boolean(_b2BodyBurning.m_userData.objectData.OnlyBurnWhileWake))
               {
                  if(_b2BodyBurning.IsSleeping())
                  {
                     _burn_timer = 0;
                     _b2BodyBurning.m_userData.objectData.ObjectOnFire = false;
                  }
                  else if(_onlyBurnWakeTimer < 10)
                  {
                     if(Math.abs(_b2BodyBurning.GetLinearVelocity().LengthSquared()) < 0.1)
                     {
                        _onlyBurnWakeTimer += param1;
                        if(_onlyBurnWakeTimer >= 10)
                        {
                           _burn_timer = 0;
                           _b2BodyBurning.m_userData.objectData.ObjectOnFire = false;
                        }
                     }
                  }
                  else
                  {
                     _onlyBurnWakeTimer = 0;
                  }
               }
               else if(_lifeSpan > _b2BodyBurning.m_userData.objectData.FireLifeSpan && _b2BodyBurning.m_userData.objectData.FireLifeSpan > 0)
               {
                  _burn_timer = 0;
                  _b2BodyBurning.m_userData.objectData.ObjectOnFire = false;
               }
            }
         }
         else
         {
            _burn_timer -= param1;
            if(_b2Body != null)
            {
               _loc2_ = _b2Body.GetWorldPoint(_b2BodyLocalPosition);
               _posX = _loc2_.x * 30;
               _posY = _loc2_.y * 30;
               UpdateMC();
               _effect_timer -= param1;
               if(_effect_timer <= 0)
               {
                  AddEffectGround(!_inAir);
                  _effect_timer = 3 + Math.random() * 2;
               }
               else if(EffectDistancePass(5))
               {
                  AddEffectGround();
                  _effect_timer = 3 + Math.random() * 2;
               }
            }
            else
            {
               _effect_timer -= param1;
               if(_effect_timer <= 0)
               {
                  AddEffectGround(!_inAir);
                  _effect_timer = 3 + Math.random() * 2;
               }
               else if(_inAir)
               {
                  if(EffectDistancePass(4))
                  {
                     AddEffectGround();
                  }
               }
            }
         }
         if(!_air_mc_removed)
         {
            if(!_inAir)
            {
               _air_mc.parent.removeChild(_air_mc);
               _air_mc_removed = true;
               _fireType = 0;
               _ownerResetTimer = 0;
               _owner = -1;
            }
            else
            {
               _air_mc.x = _posX;
               _air_mc.y = _posY;
               if(_fireType == 1)
               {
                  _currentFrame += param1;
                  _air_mc.gotoAndStop(Math.ceil(_currentFrame));
               }
            }
         }
         else if(_ownerResetTimer > 0)
         {
            _ownerResetTimer -= param1;
            if(_ownerResetTimer <= 0)
            {
               _ownerResetTimer = 0;
               _owner = -1;
            }
         }
         if(_burn_timer <= 0)
         {
            End();
         }
      }
      
      private function EffectDistancePass(param1:Number) : Boolean
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         _loc2_ = _lastEffectX - _posX;
         _loc3_ = _lastEffectY - _posY;
         if(Math.sqrt(_loc2_ * _loc2_ + _loc3_ * _loc3_) > param1)
         {
            return true;
         }
         return false;
      }
      
      public function set VelY(param1:Number) : void
      {
         _velY = param1;
      }
      
      public function get IsFlamethrower() : Boolean
      {
         return _fireType == 1;
      }
      
      private function AddEffectPlayer() : void
      {
         _lastEffectX = _posX;
         _lastEffectY = _posY;
         _Handler_Effects.AddParticle(new particle_data("fire",_playerBurnTarget.MidPosX() + Math.random() * 8 - 4,_playerBurnTarget.MidPosY() + Math.random() * 12 - 6));
      }
      
      private function AddEffectDynamic(param1:int = 0) : void
      {
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:int = 0;
         if(param1 == 0)
         {
            _loc2_ = Math.random() * _b2BodyBurning.m_userData.objectData.ShapeMC.width - _b2BodyBurning.m_userData.objectData.ShapeMC.width / 2;
            _loc3_ = Math.random() * _b2BodyBurning.m_userData.objectData.ShapeMC.height - _b2BodyBurning.m_userData.objectData.ShapeMC.height / 2;
            _Handler_Effects.AddParticle(new particle_data("fire",_posX + _loc2_ * 0.9,_posY + _loc3_ * 0.9));
         }
         else if(!_b2BodyBurning.m_userData.objectData.ThroughPortal)
         {
            _loc4_ = _posX - _lastEffectX;
            _loc5_ = _posY - _lastEffectY;
            _loc6_ = Math.sqrt(_loc4_ * _loc4_ + _loc5_ * _loc5_);
            _loc7_ = _loc4_ / _loc6_;
            _loc8_ = _loc5_ / _loc6_;
            _loc9_ = param1;
            while(_loc9_ <= _loc6_)
            {
               _loc2_ = Math.random() * _b2BodyBurning.m_userData.objectData.ShapeMC.width - _b2BodyBurning.m_userData.objectData.ShapeMC.width / 2;
               _loc3_ = Math.random() * _b2BodyBurning.m_userData.objectData.ShapeMC.height - _b2BodyBurning.m_userData.objectData.ShapeMC.height / 2;
               _Handler_Effects.AddParticle(new particle_data("fire",_posX + _loc7_ * _loc9_ + _loc2_ * 0.9,_posY + _loc8_ * _loc9_ + _loc3_ * 0.9));
               _loc9_ += param1;
            }
         }
         else
         {
            _b2BodyBurning.m_userData.objectData.ThroughPortal = false;
         }
         _lastEffectX = _posX;
         _lastEffectY = _posY;
      }
   }
}

