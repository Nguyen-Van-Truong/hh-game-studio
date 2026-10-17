package Code.Data
{
   public class PathResultNode
   {
      private var _pathNode:PathNode;
      
      private var _nextBind:PathBind;
      
      private var _prevBind:PathBind;
      
      public function PathResultNode(param1:PathNode)
      {
         super();
         _prevBind = null;
         _pathNode = param1;
         _nextBind = null;
      }
      
      public function set PrevBind(param1:PathBind) : void
      {
         _prevBind = param1;
      }
      
      public function get Node() : PathNode
      {
         return _pathNode;
      }
      
      public function get PrevBind() : PathBind
      {
         return _prevBind;
      }
      
      public function get NextBind() : PathBind
      {
         return _nextBind;
      }
      
      public function set NextBind(param1:PathBind) : void
      {
         _nextBind = param1;
      }
   }
}

