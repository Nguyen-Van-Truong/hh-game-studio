package Code.Data
{
   import Code.Handler.GameMain;
   import Code.Handler.Options;
   import Code.Handler.OutputTrace;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   
   public class MenuMainData
   {
      public var Handler_GameMain:GameMain;
      
      public var game_mc:MovieClip;
      
      public var Handler_Options:Options;
      
      public var stage_temp:*;
      
      public var Handler_Output:OutputTrace;
      
      public var Handler_Sounds:Sounds;
      
      public function MenuMainData()
      {
         super();
      }
   }
}

