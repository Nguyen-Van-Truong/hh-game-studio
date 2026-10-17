package Code.Data
{
   public class PathBind
   {
      public static const STATIC:int = 0;
      
      public static const DYNAMIC:int = 1;
      
      public static const ROAD:int = 3;
      
      public static const JUMP:int = 4;
      
      public static const SPRINTJUMP:int = 5;
      
      public static const CLOUDDOWN:int = 6;
      
      public static const DIVE:int = 7;
      
      public static const LADDER:int = 8;
      
      public static const PORTAL:int = 9;
      
      public static const ROLL:int = 10;
      
      private var _id:String;
      
      private var _targetNode:PathNode;
      
      private var _distance:Number;
      
      private var _sourceNode:PathNode;
      
      private var _movementType:int;
      
      private var _blocked:Boolean;
      
      private var _bindType:int;
      
      public function PathBind(param1:String, param2:PathNode, param3:PathNode, param4:int, param5:int)
      {
         super();
         _id = param1;
         _sourceNode = param2;
         _targetNode = param3;
         _bindType = param4;
         _movementType = param5;
         _blocked = false;
         CalcDistance();
      }
      
      private function CalcDistance() : void
      {
         if(_movementType == PORTAL)
         {
            _distance = 0;
            return;
         }
         _distance = Math.sqrt(Math.pow(SourceNode.PosY - TargetNode.PosY,2) + Math.pow(SourceNode.PosX - TargetNode.PosX,2));
         if(_movementType == LADDER)
         {
            _distance *= 1.5;
         }
      }
      
      public function get Blocked() : Boolean
      {
         return _blocked;
      }
      
      public function get TargetNode() : PathNode
      {
         return _targetNode;
      }
      
      public function get Distance() : Number
      {
         if(_bindType == DYNAMIC)
         {
            CalcDistance();
         }
         return _distance;
      }
      
      public function set Blocked(param1:Boolean) : void
      {
         _blocked = param1;
      }
      
      public function set MovementType(param1:int) : void
      {
         _movementType = param1;
      }
      
      public function get ID() : String
      {
         return _id;
      }
      
      public function get SourceNode() : PathNode
      {
         return _sourceNode;
      }
      
      public function set TargetNode(param1:PathNode) : void
      {
         _targetNode = param1;
         CalcDistance();
      }
      
      public function set SourceNode(param1:PathNode) : void
      {
         _sourceNode = param1;
         CalcDistance();
      }
      
      public function get MovementType() : int
      {
         return _movementType;
      }
      
      public function set BindType(param1:int) : void
      {
         _bindType = param1;
         if(_bindType == STATIC)
         {
            CalcDistance();
         }
      }
      
      public function TargetNodeCloseEnough() : Boolean
      {
         var _loc1_:Boolean = false;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         if(_bindType == STATIC)
         {
            return true;
         }
         _loc1_ = true;
         _loc2_ = Math.abs(SourceNode.PosX - (TargetNode.PosX + TargetNode.SpeedX * 2));
         _loc3_ = Math.abs(SourceNode.PosY - TargetNode.PosY);
         if(TargetNode.SpeedY < 0 && TargetNode.PosY + 4 < SourceNode.PosY)
         {
            _loc1_ = false;
         }
         if(SourceNode.SpeedX > 0.1 && TargetNode.PosX < SourceNode.PosX || SourceNode.SpeedX < -0.1 && TargetNode.PosX > SourceNode.PosX)
         {
            _loc1_ = false;
         }
         switch(_movementType)
         {
            case ROAD:
               if(!_loc1_)
               {
                  return false;
               }
               if(_loc2_ < 20 && _loc3_ < 20)
               {
                  return true;
               }
               break;
            case JUMP:
               if(!_loc1_)
               {
                  return false;
               }
               if(_loc2_ < 20 && _loc3_ <= 22)
               {
                  return true;
               }
               break;
            case SPRINTJUMP:
               if(!_loc1_)
               {
                  return false;
               }
               if(_loc2_ < 60 && _loc3_ <= 22)
               {
                  return true;
               }
               break;
            case CLOUDDOWN:
               if(_loc2_ < 20 && _loc3_ < 30)
               {
                  return true;
               }
               break;
            case DIVE:
               if(_loc2_ < 100 && _loc3_ < 100)
               {
                  return true;
               }
               break;
            case LADDER:
               if(_loc2_ < 20 && _loc3_ < 20)
               {
                  return true;
               }
               break;
            case PORTAL:
               if(_loc2_ < 20 && _loc3_ < 20)
               {
                  return true;
               }
               break;
            case ROLL:
               if(_loc2_ < 20 && _loc3_ < 20)
               {
                  return true;
               }
               break;
         }
         return false;
      }
      
      public function get BindType() : int
      {
         return _bindType;
      }
   }
}

