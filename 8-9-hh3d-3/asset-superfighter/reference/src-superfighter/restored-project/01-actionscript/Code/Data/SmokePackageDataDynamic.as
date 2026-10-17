package Code.Data
{
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Handler.Effects;
   import Code.Particles.particle_data;
   
   public class SmokePackageDataDynamic
   {
      private var _smokePoint:b2Vec2;
      
      private var _body:b2Body;
      
      private var _smoke_tick:Number;
      
      private var _Handler_Effects:Effects;
      
      private var _speed:Number;
      
      private var _smoke_pack_done:Boolean = false;
      
      private var xDiff:Number;
      
      private var yDiff:Number;
      
      private var _still_timer:Number = 0;
      
      private var _smoke_timer:Number;
      
      private var _init_smoke_grade:int = 0;
      
      private var _lastSmokePoint:b2Vec2;
      
      public function SmokePackageDataDynamic(param1:Effects)
      {
         _smoke_pack_done = false;
         _init_smoke_grade = 0;
         _still_timer = 0;
         super();
         _Handler_Effects = param1;
         _smoke_timer = 72 + Math.random() * 5;
         _smokePoint = new b2Vec2();
         _lastSmokePoint = new b2Vec2();
      }
      
      public function SetSmokeElementAt(param1:b2Body) : void
      {
         _body = param1;
         _init_smoke_grade = param1.GetUserData().objectData.ObjectSmokeGrade;
         UpdatePosition();
         _smoke_tick = Math.random() * 2;
      }
      
      private function AddEffect() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         _lastSmokePoint.x = _smokePoint.x;
         _lastSmokePoint.y = _smokePoint.y;
         _loc1_ = Math.random() * _body.m_userData.objectData.ShapeMC.width - _body.m_userData.objectData.ShapeMC.width / 2;
         _loc2_ = Math.random() * _body.m_userData.objectData.ShapeMC.height - _body.m_userData.objectData.ShapeMC.height / 2;
         _Handler_Effects.AddParticle(new particle_data("SMOKE_TRACE_EFFECT",_smokePoint.x + _loc1_ * 0.7,_smokePoint.y + _loc2_ * 0.7,_body.GetLinearVelocity(),0,1,[_init_smoke_grade]));
      }
      
      public function get SmokePackageCompleted() : Boolean
      {
         return _smoke_pack_done;
      }
      
      public function Update(param1:Number) : void
      {
         if(_init_smoke_grade != _body.GetUserData().objectData.ObjectSmokeGrade || _body.GetUserData().objectData.ObjectOnFire || _body.GetUserData().destroyed == true)
         {
            _smoke_pack_done = true;
            return;
         }
         UpdatePosition();
         _smoke_tick -= param1;
         if(_smoke_tick <= 0)
         {
            AddEffect();
            _smoke_tick = 3;
         }
         else
         {
            xDiff = _lastSmokePoint.x - _smokePoint.x;
            yDiff = _lastSmokePoint.y - _smokePoint.y;
            _speed = Math.sqrt(xDiff * xDiff + yDiff * yDiff);
            if(_speed > 5)
            {
               AddEffect();
               _smoke_tick = 3;
            }
            else if(_speed < 0.5)
            {
               _still_timer += param1;
               if(_still_timer > 3)
               {
                  _smoke_timer = 0;
               }
            }
            else
            {
               _still_timer = 0;
            }
         }
         _smoke_timer -= param1;
         if(_smoke_timer <= 0)
         {
            _body.GetUserData().objectData.ObjectSmokeGrade = 0;
            _smoke_pack_done = true;
         }
      }
      
      private function UpdatePosition() : void
      {
         _smokePoint.x = _body.GetPosition().x * 30;
         _smokePoint.y = _body.GetPosition().y * 30;
      }
   }
}

