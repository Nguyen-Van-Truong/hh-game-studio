package Code.Handler
{
   import Code.Box2D.Common.Math.b2Vec2;
   import Code.Box2D.Dynamics.b2Body;
   import Code.Box2D.Dynamics.b2World;
   import Code.Data.ExplosionData;
   import Code.Data.SlowmoData;
   import Code.Particles.particle_data;
   import flash.display.MovieClip;
   import flash.display.Sprite;
   import flash.geom.Point;
   
   public class Explosions
   {
      private var _sp:Array;
      
      private var explosionPowerObjects:Number = 5;
      
      private var _static_mc:MovieClip;
      
      private var _Handler_Fires:Fires;
      
      private var _Handler_Effects:Effects;
      
      private var _object_mc:MovieClip;
      
      private var _Handler_Camera:Cam;
      
      private var _Handler_Shake:Shake;
      
      private var explosionPowerPlayers:Number = 5;
      
      private var _dynamic_mc:MovieClip;
      
      private var _Handler_Sounds:Sounds;
      
      private var explosionPosX:Number;
      
      private var explosionPosY:Number;
      
      private var explosionBuffer:Array;
      
      private var _Handler_Players:PlayersKeeper;
      
      private var _static_objects_hitbox_mc:MovieClip;
      
      private var explosionDamagePlayers:Number = 20;
      
      private var m_world:b2World;
      
      private var _static_world_hitbox_mc:MovieClip;
      
      private var _Handler_Slowmo:Slowmo;
      
      private var _explosion_mc:MovieClip;
      
      private var explosionDamage:Number = 25;
      
      private var _m:Number;
      
      private var _n:int = 36;
      
      private var _p:int;
      
      private var _r:Number = 0;
      
      private var _static_world_cloud_hitbox_mc:MovieClip;
      
      private var _Handler_Output:OutputTrace;
      
      private var _static_objects_cloud_hitbox_mc:MovieClip;
      
      private var _powerForEachPin:Number;
      
      public function Explosions()
      {
         _explosion_mc = new MovieClip();
         _n = 36;
         _r = 0;
         explosionPowerObjects = 5;
         explosionPowerPlayers = 5;
         explosionDamage = 25;
         explosionDamagePlayers = 20;
         explosionBuffer = new Array();
         super();
      }
      
      public function LinkToFire(param1:Fires) : void
      {
         _Handler_Fires = param1;
      }
      
      public function Update(param1:Number) : void
      {
         var _loc2_:int = 0;
         var _loc3_:b2Body = null;
         if(explosionBuffer.length > 0)
         {
            _loc2_ = 0;
            while(_loc2_ < explosionBuffer.length)
            {
               explosionBuffer[_loc2_][0] = explosionBuffer[_loc2_][0] - 1;
               if(explosionBuffer[_loc2_][0] <= 0)
               {
                  _loc3_ = explosionBuffer[_loc2_][1];
                  _loc3_.m_userData.objectData.Damage_Explosion(explosionBuffer[_loc2_][2]);
                  explosionBuffer.splice(_loc2_,1);
               }
               _loc2_++;
            }
         }
      }
      
      public function TriggerExplosionAt_Box2DScale(param1:String, param2:Number, param3:Number) : void
      {
         param2 = Math.round(param2 * 30);
         param3 = Math.round(param3 * 30);
         TriggerExplosionAt(param1,param2,param3);
      }
      
      public function BuildClass(param1:ExplosionData) : void
      {
         var _loc2_:* = undefined;
         _Handler_Output = param1.Handler_Output;
         _Handler_Camera = param1.Handler_Camera;
         _Handler_Shake = param1.Handler_Shake;
         _Handler_Players = param1.Handler_Players;
         _Handler_Effects = param1.Handler_Effects;
         _Handler_Sounds = param1.Handler_Sounds;
         _Handler_Slowmo = param1.Handler_Slowmo;
         _static_mc = param1.static_mc;
         _dynamic_mc = param1.dynamic_mc;
         m_world = param1.m_world;
         _static_world_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_HITBOX"));
         _static_objects_hitbox_mc = MovieClip(_static_world_hitbox_mc.getChildByName("OBJECTS_HITBOX"));
         _static_world_cloud_hitbox_mc = MovieClip(_static_mc.getChildByName("WORLD_CLOUD_HITBOX"));
         _static_objects_cloud_hitbox_mc = MovieClip(_static_world_cloud_hitbox_mc.getChildByName("OBJECTS_CLOUD_HITBOX"));
         _static_mc.addChild(_explosion_mc);
         _sp = new Array();
         _loc2_ = 0;
         while(_loc2_ < _n)
         {
            _sp.push(new Array(Math.cos(GradToRad(_loc2_ * (360 / _n))),Math.sin(GradToRad(_loc2_ * (360 / _n))),2,3,0,0));
            _loc2_++;
         }
         _Handler_Output.Trace("Explosion Handler Created");
      }
      
      private function GradToRad(param1:Number) : Number
      {
         return Math.PI / 180 * param1;
      }
      
      public function TriggerExplosionAt(param1:String, param2:Number, param3:Number) : Boolean
      {
         var _loc4_:int = 0;
         var _loc5_:b2Body = null;
         var _loc6_:Number = NaN;
         var _loc7_:int = 0;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         var _loc12_:Number = NaN;
         var _loc13_:int = 0;
         var _loc14_:int = 0;
         var _loc15_:b2Body = null;
         var _loc16_:Boolean = false;
         var _loc17_:Number = NaN;
         var _loc18_:Number = NaN;
         var _loc19_:* = undefined;
         var _loc20_:int = 0;
         var _loc21_:* = undefined;
         _Handler_Output.Trace("Explosion Triggered At (" + param2 + ", " + param3 + ")");
         if(_static_world_hitbox_mc.hitTestPoint(param2,param3,true))
         {
            if(!_static_objects_hitbox_mc.hitTestPoint(param2,param3,true))
            {
               _loc16_ = true;
               _loc17_ = param2 - 5;
               while(_loc17_ <= param2 + 5)
               {
                  _loc18_ = param3 - 5;
                  while(_loc18_ <= param3 + 5)
                  {
                     if(!(_static_world_hitbox_mc.hitTestPoint(_loc17_,_loc18_,true) && !_static_objects_hitbox_mc.hitTestPoint(_loc17_,_loc18_,true)))
                     {
                        param2 = _loc17_;
                        param3 = _loc18_;
                        _loc16_ = false;
                        _loc17_ = param2 + 10;
                        _loc18_ = param3 + 10;
                        _Handler_Output.Trace("Explosion Triggered At Updated Position (" + param2 + ", " + param3 + ")");
                     }
                     _loc18_ += 5;
                  }
                  _loc17_ += 5;
               }
               if(_loc16_)
               {
                  _Handler_Output.Trace("Explosion triggered inside a static object. Aborting explosion");
                  return false;
               }
            }
         }
         explosionPosX = param2;
         explosionPosY = param3;
         if(_Handler_Camera.IsInside(new Point(param2,param3)))
         {
            _Handler_Shake.Add(5,4);
         }
         _r = 33;
         _m = 0;
         _p = _n;
         _loc4_ = 3;
         _loc7_ = 0;
         while(_loc7_ < _n)
         {
            _sp[_loc7_][2] = param2;
            _sp[_loc7_][3] = param3;
            _sp[_loc7_][4] = 0;
            _loc19_ = 0;
            while(_loc19_ <= _r)
            {
               _sp[_loc7_][2] += _sp[_loc7_][0] * _loc4_;
               _sp[_loc7_][3] += _sp[_loc7_][1] * _loc4_;
               if(_static_world_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true) || _static_world_cloud_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true))
               {
                  if(!_static_objects_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true) && !_static_objects_cloud_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true))
                  {
                     _sp[_loc7_][2] += _sp[_loc7_][0] * _loc4_;
                     _sp[_loc7_][3] += _sp[_loc7_][1] * _loc4_;
                     _sp[_loc7_][4] = 1;
                     _sp[_loc7_][5] = _loc19_;
                     _m += _r - _loc19_;
                     --_p;
                     break;
                  }
                  _loc5_ = m_world.GetDynamicBodyAt(_sp[_loc7_][2],_sp[_loc7_][3],true);
                  if(_loc5_ == null)
                  {
                     _Handler_Output.Trace("Error 2: Object \'" + _loc5_ + "\' doesn\'t exist");
                  }
                  else if(_loc5_.m_userData.objectData.CanBlockExplosions)
                  {
                     _sp[_loc7_][2] += _sp[_loc7_][0] * _loc4_;
                     _sp[_loc7_][3] += _sp[_loc7_][1] * _loc4_;
                     _sp[_loc7_][4] = 1;
                     _sp[_loc7_][5] = _loc19_;
                     _m += _r - _loc19_;
                     --_p;
                     if(_loc5_.m_userData.objectData.AffectedByExplosions)
                     {
                        _loc6_ = 1 - _loc19_ / _r;
                        if((_loc6_ = _loc6_ * 4) > 1)
                        {
                           _loc6_ = 1;
                        }
                        _loc6_ *= 0.01 * _loc5_.GetMass();
                        _loc5_.ApplyImpulse(new b2Vec2((_sp[_loc7_][2] - param2) * _loc6_,(_sp[_loc7_][3] - param3 - 10) * _loc6_),new b2Vec2(_sp[_loc7_][2] / 30,_sp[_loc7_][3] / 30));
                        _loc5_.GetUserData().objectData.Damage_Explosion(explosionDamage * 0.1);
                     }
                     break;
                  }
               }
               _loc19_ += _loc4_;
            }
            if(_sp[_loc7_][4] == 0)
            {
               _sp[_loc7_][5] = _r;
            }
            _loc7_++;
         }
         if(_m > 0)
         {
            _powerForEachPin = _m / _p * 0.25;
            if(_powerForEachPin > _r * 0.5)
            {
               _powerForEachPin = _r * 0.5;
            }
            _loc7_ = 0;
            while(_loc7_ < _n)
            {
               if(_sp[_loc7_][4] == 0)
               {
                  _loc21_ = 1;
                  while(_loc21_ <= _powerForEachPin)
                  {
                     _sp[_loc7_][2] += _sp[_loc7_][0] * _loc4_;
                     _sp[_loc7_][3] += _sp[_loc7_][1] * _loc4_;
                     if(_static_world_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true) || _static_world_cloud_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true))
                     {
                        if(!_static_objects_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true) && !_static_objects_cloud_hitbox_mc.hitTestPoint(_sp[_loc7_][2],_sp[_loc7_][3],true))
                        {
                           _sp[_loc7_][2] += _sp[_loc7_][0] * _loc4_;
                           _sp[_loc7_][3] += _sp[_loc7_][1] * _loc4_;
                           _sp[_loc7_][4] = 1;
                           _sp[_loc7_][5] += _loc21_;
                           break;
                        }
                        _loc5_ = m_world.GetDynamicBodyAt(_sp[_loc7_][2],_sp[_loc7_][3],true);
                        if(_loc5_ == null)
                        {
                           _Handler_Output.Trace("Error 3: Object \'" + _loc5_ + "\' doesn\'t exist");
                        }
                        else if(_loc5_.m_userData.objectData.CanBlockExplosions)
                        {
                           _sp[_loc7_][4] = 1;
                           _sp[_loc7_][5] += _loc21_;
                           break;
                        }
                     }
                     _loc21_ += _loc4_;
                  }
                  if(_sp[_loc7_][4] == 0)
                  {
                     _sp[_loc7_][5] += _powerForEachPin;
                  }
               }
               _loc7_++;
            }
            _r += _powerForEachPin;
            _explosion_mc.graphics.clear();
            _explosion_mc.graphics.lineStyle(1,16711680,1,false,"none");
            _explosion_mc.graphics.beginFill(16711680,0);
            _explosion_mc.graphics.moveTo(_sp[0][2],_sp[0][3]);
            _loc20_ = 1;
            while(_loc20_ < _n)
            {
               _explosion_mc.graphics.lineTo(_sp[_loc20_][2],_sp[_loc20_][3]);
               _loc20_++;
            }
            _explosion_mc.graphics.lineTo(_sp[0][2],_sp[0][3]);
            _explosion_mc.graphics.endFill();
         }
         else
         {
            _explosion_mc.graphics.clear();
            _explosion_mc.graphics.lineStyle(1,16711680,1,false,"none");
            _explosion_mc.graphics.beginFill(16711680,0);
            _explosion_mc.graphics.drawCircle(param2,param3,_r + 1);
            _explosion_mc.graphics.endFill();
         }
         _loc13_ = 0;
         _loc14_ = 0;
         while(_loc14_ < _Handler_Players.Players.length)
         {
            if(!_Handler_Players.Players[_loc14_].State.Gone)
            {
               if(_explosion_mc.hitTestPoint(_Handler_Players.Players[_loc14_].ExplosionX(),_Handler_Players.Players[_loc14_].ExplosionY(),true))
               {
                  _loc10_ = _Handler_Players.Players[_loc14_].ExplosionX() - explosionPosX;
                  _loc11_ = _Handler_Players.Players[_loc14_].ExplosionY() - explosionPosY;
                  _loc12_ = Math.sqrt(_loc10_ * _loc10_ + _loc11_ * _loc11_);
                  if(_loc12_ <= _r / 2)
                  {
                     _loc9_ = 1;
                  }
                  else
                  {
                     _loc9_ = 1 - (_loc12_ - _r / 2) / (_r / 2);
                     if(_loc9_ < 0)
                     {
                        _loc9_ = 0;
                     }
                  }
                  if(_loc9_ > 0)
                  {
                     _loc8_ = Math.atan2(_loc11_,_loc10_);
                     _Handler_Players.Players[_loc14_].ExplosionHit(_loc8_,explosionPowerPlayers * _loc9_,explosionDamagePlayers * _loc9_);
                     if(!_Handler_Players.Players[_loc14_].Ignore && _Handler_Players.Players[_loc14_].State.HP > 0)
                     {
                        _loc13_ += 1;
                     }
                  }
               }
            }
            _loc14_++;
         }
         if(_loc13_ >= 2)
         {
            _Handler_Slowmo.AddSlowmotion(new SlowmoData(0,24 * 1,24 * 0.5,0.25));
         }
         if(_loc13_ >= 1)
         {
            _Handler_Shake.Add(2,2);
         }
         _loc15_ = m_world.m_bodyList;
         while(_loc15_)
         {
            if(_loc15_.m_userData is Sprite)
            {
               if(_explosion_mc.hitTestPoint(_loc15_.m_userData.x,_loc15_.m_userData.y,true))
               {
                  if(_loc15_.m_userData.objectData.AffectedByExplosions)
                  {
                     _loc10_ = _loc15_.m_userData.x - explosionPosX;
                     _loc11_ = _loc15_.m_userData.y - 4 - explosionPosY;
                     _loc12_ = Math.sqrt(_loc10_ * _loc10_ + _loc11_ * _loc11_);
                     if(_loc12_ <= _r / 2)
                     {
                        _loc9_ = 1;
                     }
                     else
                     {
                        _loc9_ = 1 - (_loc12_ * 2 - _r) / _r;
                        if(_loc9_ < 0)
                        {
                           _loc9_ = 0;
                        }
                     }
                     if(_loc9_ > 0)
                     {
                        _Handler_Fires.AddSmokeToObject(_loc15_,2);
                        _loc8_ = Math.atan2(_loc11_,_loc10_);
                        explosionBuffer.push([1,_loc15_,explosionDamage]);
                        _loc15_.ApplyImpulse(new b2Vec2(Math.cos(_loc8_) * _loc15_.GetMass() * explosionPowerObjects * _loc9_,Math.sin(_loc8_) * _loc15_.GetMass() * explosionPowerObjects * _loc9_),_loc15_.GetWorldPoint(new b2Vec2(-Math.cos(_loc8_) * 0.2,-Math.sin(_loc8_) * 0.1)));
                     }
                  }
               }
            }
            _loc15_ = _loc15_.m_next;
         }
         _Handler_Effects.AddParticle(new particle_data("explosion_centrum",param2,param3));
         return true;
      }
   }
}

