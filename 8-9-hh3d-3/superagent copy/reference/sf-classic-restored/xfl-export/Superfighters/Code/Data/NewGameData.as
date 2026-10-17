package Code.Data
{
   import Code.Data.Players.PlayerSetupData;
   
   public class NewGameData
   {
      public var isSurvival:Boolean;
      
      public var newScore:Boolean;
      
      public var showTips:Boolean;
      
      public var gamePosX:Number;
      
      public var gamePosY:Number;
      
      public var challengeNr:int;
      
      public var lvl:Number;
      
      public var isTutorial:Boolean;
      
      public var isMenuDemo:Boolean;
      
      public var pSetupData:PlayerSetupData;
      
      public var gameScale:Number;
      
      public var gameMode:int;
      
      public function NewGameData()
      {
         super();
      }
   }
}

