package Code.Data
{
   import Code.Box2D.Common.Math.b2Vec2;
   import Code.Box2D.Dynamics.b2Body;
   
   public class PathNode
   {
      private var _parentBody:b2Body;
      
      private var _inFire:Boolean;
      
      private var _locked:Boolean;
      
      private var _activatorID:String;
      
      private var _isHazard:Boolean;
      
      private var _id:String;
      
      private var _listIndex:int = -1;
      
      private var _binds:Array;
      
      private var _parentBodyLocation:b2Vec2;
      
      private var _posX:Number;
      
      private var _posY:Number;
      
      private var _isEndNode:Boolean;
      
      public function PathNode(param1:String, param2:Number, param3:Number, param4:String, param5:b2Body)
      {
         var _loc6_:b2Vec2 = null;
         _listIndex = -1;
         super();
         _id = param1.toUpperCase();
         _posX = param2;
         _posY = param3;
         _activatorID = param4;
         _parentBody = param5;
         _inFire = false;
         _isHazard = false;
         _locked = false;
         _isEndNode = true;
         _binds = new Array();
         if(_parentBody != null)
         {
            _loc6_ = new b2Vec2(param2 / 30,param3 / 30);
            _parentBodyLocation = _parentBody.GetLocalPoint(_loc6_);
         }
      }
      
      public function RemoveBind(param1:PathBind) : void
      {
         var _loc2_:int = 0;
         _loc2_ = int(_binds.length - 1);
         while(_loc2_ >= 0)
         {
            if(_binds[_loc2_] == param1)
            {
               _binds.splice(_loc2_,1);
            }
            _loc2_--;
         }
      }
      
      public function UpdateIsEndNode() : void
      {
         var _loc1_:int = 0;
         _isEndNode = false;
         _loc1_ = int(_binds.length - 1);
         while(_loc1_ >= 0)
         {
            if(_binds[_loc1_].MovementType != PathBind.PORTAL)
            {
               _isEndNode = true;
               return;
            }
            _loc1_--;
         }
      }
      
      public function get ParentBody() : b2Body
      {
         return _parentBody;
      }
      
      public function get SpeedX() : Number
      {
         if(_parentBody != null)
         {
            return _parentBody.GetLinearVelocity().x;
         }
         return 0;
      }
      
      public function get SpeedY() : Number
      {
         if(_parentBody != null)
         {
            return _parentBody.GetLinearVelocity().y;
         }
         return 0;
      }
      
      public function set ParentBody(param1:b2Body) : void
      {
         _parentBody = param1;
      }
      
      public function get ID() : String
      {
         return _id;
      }
      
      public function set ActivatorID(param1:String) : void
      {
         _activatorID = param1;
      }
      
      public function get InFire() : Boolean
      {
         return _inFire;
      }
      
      public function get PosX() : Number
      {
         return _posX;
      }
      
      public function get PosY() : Number
      {
         return _posY;
      }
      
      public function GetDistanceTo(param1:Number, param2:Number) : Number
      {
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         _loc3_ = _posX - param1;
         _loc4_ = _posY - param2;
         return Math.sqrt(_loc3_ * _loc3_ + _loc4_ * _loc4_);
      }
      
      public function get Speed() : b2Vec2
      {
         if(_parentBody != null)
         {
            return _parentBody.GetLinearVelocity();
         }
         return new b2Vec2(0,0);
      }
      
      public function set IsEndNode(param1:Boolean) : void
      {
         _isEndNode = param1;
      }
      
      public function set InFire(param1:Boolean) : void
      {
         _inFire = param1;
      }
      
      public function get Locked() : Boolean
      {
         return _locked;
      }
      
      public function get Binds() : Array
      {
         return _binds;
      }
      
      public function get ListIndex() : int
      {
         return _listIndex;
      }
      
      public function get ActivatorID() : String
      {
         return _activatorID;
      }
      
      public function get IsEndNode() : Boolean
      {
         return _isEndNode;
      }
      
      public function set Locked(param1:Boolean) : void
      {
         _locked = param1;
      }
      
      public function get Avoid() : Boolean
      {
         return _isHazard || _inFire;
      }
      
      public function CalculateParentLocation() : void
      {
         _posX = _parentBody.GetWorldPoint(_parentBodyLocation).x * 30;
         _posY = _parentBody.GetWorldPoint(_parentBodyLocation).y * 30;
      }
      
      public function set Binds(param1:Array) : void
      {
         _binds = param1;
      }
      
      public function GetBindTo(param1:PathNode) : PathBind
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < _binds.length)
         {
            if(_binds[_loc2_].TargetNode == param1)
            {
               return _binds[_loc2_];
            }
            _loc2_++;
         }
         return null;
      }
      
      public function set ListIndex(param1:int) : void
      {
         _listIndex = param1;
      }
      
      public function set IsHazard(param1:Boolean) : void
      {
         _isHazard = param1;
      }
      
      public function get IsHazard() : Boolean
      {
         return _isHazard;
      }
   }
}

