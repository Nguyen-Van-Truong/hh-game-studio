package Code.Data
{
   import Code.Data.Players.PlayerSetupData;
   
   public class NewGameData
   {
      public var newScore:Boolean;
      
      public var showTips:Boolean;
      
      public var gamePosX:Number;
      
      public var gamePosY:Number;
      
      public var challengeNr:int;
      
      public var lvl:Number;
      
      public var isTutorial:Boolean;
      
      public var isMenuDemo:Boolean;
      
      public var gameMode:int;
      
      public var pSetupData:PlayerSetupData;
      
      public var gameScale:Number;
      
      public function NewGameData()
      {
         super();
      }
   }
}

