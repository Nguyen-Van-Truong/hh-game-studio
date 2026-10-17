package Code.Data
{
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.b2Body;
   import flash.display.*;
   
   public class Rope
   {
      internal var _local1:b2Vec2;
      
      internal var _local2:b2Vec2;
      
      internal var _removed:Boolean;
      
      internal var _body1:b2Body;
      
      internal var _body2:b2Body;
      
      internal var _mc:MovieClip;
      
      public function Rope(param1:b2Body, param2:b2Body, param3:b2Vec2, param4:b2Vec2)
      {
         super();
         BuildRope(param1,param2,param3,param4);
      }
      
      public function Remove() : void
      {
         if(!_removed)
         {
            _mc.parent.removeChild(_mc);
            _removed = true;
         }
      }
      
      public function get MC() : MovieClip
      {
         return _mc;
      }
      
      public function BuildRope(param1:b2Body, param2:b2Body, param3:b2Vec2, param4:b2Vec2) : *
      {
         var _loc5_:Number = NaN;
         var _loc6_:int = 0;
         var _loc7_:rope_segment_01 = null;
         _body1 = param1;
         _body2 = param2;
         _local1 = _body1.GetLocalPoint(param3);
         _local2 = _body2.GetLocalPoint(param4);
         _loc5_ = Math.sqrt(Math.pow(param3.x * 30 - param4.x * 30,2) + Math.pow(param3.y * 30 - param4.y * 30,2));
         _mc = new MovieClip();
         _loc6_ = 0;
         while(_loc6_ < _loc5_)
         {
            _loc7_ = new rope_segment_01();
            _loc7_.y = -_loc6_;
            _mc.addChild(_loc7_);
            _loc6_ += 3;
         }
         _removed = false;
         UpdateMC();
      }
      
      public function UpdateMC() : void
      {
         var _loc1_:b2Vec2 = null;
         var _loc2_:b2Vec2 = null;
         var _loc3_:Number = NaN;
         if(_removed)
         {
            return;
         }
         _loc1_ = _body1.GetWorldPoint(_local1);
         _loc2_ = _body2.GetWorldPoint(_local2);
         _mc.x = _loc1_.x * 30;
         _mc.y = _loc1_.y * 30;
         _loc3_ = Math.atan2(_loc1_.y - _loc2_.y,_loc1_.x - _loc2_.x);
         _mc.rotation = _loc3_ * (180 / Math.PI) - 90;
      }
   }
}

