package Code.Data
{
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public class MapLogic
   {
      public var OnUpdate:Function;
      
      private var refireInterval:int = 1000;
      
      private var started:Boolean = false;
      
      private var updateTimer:Number;
      
      public function MapLogic()
      {
         started = false;
         refireInterval = 1000;
         super();
         OnUpdate = function():void
         {
         };
      }
      
      public function Start() : void
      {
         if(started)
         {
            Stop();
         }
         updateTimer = setInterval(OnUpdate,refireInterval);
         started = true;
      }
      
      public function set RefireInterval(param1:int) : void
      {
         refireInterval = param1;
         if(started)
         {
            Start();
         }
      }
      
      public function Stop() : void
      {
         clearInterval(updateTimer);
         started = false;
      }
      
      public function get RefireInterval() : int
      {
         return refireInterval;
      }
   }
}

