package Code.Data
{
   import Code.Handler.Deconstructer;
   import Code.Handler.Effects;
   import Code.Handler.OutputTrace;
   import Code.Handler.Sounds;
   
   public class ContactData
   {
      public var Handler_Effects:Effects;
      
      public var Handler_Deconstructer:Deconstructer;
      
      public var Handler_Output:OutputTrace;
      
      public var Handler_Sounds:Sounds;
      
      public var game_speed:Number = 1;
      
      public function ContactData()
      {
         game_speed = 1;
         super();
      }
   }
}

