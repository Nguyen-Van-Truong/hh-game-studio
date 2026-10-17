package Code.Data
{
   public class PathWebNode
   {
      public var Distance:Number;
      
      public var SourceNode:PathNode;
      
      public function PathWebNode()
      {
         super();
      }
      
      public function Clear() : void
      {
         SourceNode = null;
         Distance = 9999;
      }
   }
}

