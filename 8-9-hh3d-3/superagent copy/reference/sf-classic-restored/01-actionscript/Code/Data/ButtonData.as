package Code.Data
{
   public class ButtonData
   {
      public var OnActivation:Function;
      
      public var Enabled:Boolean = true;
      
      public var OnActivationSound:String = "";
      
      public function ButtonData()
      {
         OnActivationSound = "";
         Enabled = true;
         super();
         OnActivation = function():void
         {
         };
      }
      
      public function Activate() : void
      {
         OnActivation();
      }
   }
}

