package Code.Data
{
   import Code.Data.Players.*;
   
   public class Challenges
   {
      public static var CHALLENGE_1P:Array = [[3,BotState.EASY],[2,BotState.MEDIUM],[4,BotState.EASY,BotState.EASY],[5,BotState.MEDIUM,BotState.EASY],[3,BotState.MEDIUM,BotState.EASY],[2,BotState.HARD],[4,BotState.MEDIUM,BotState.MEDIUM],[5,BotState.EASY,BotState.EASY,BotState.EASY],[3,BotState.MEDIUM,BotState.EASY,BotState.EASY],[2,BotState.HARD,BotState.EASY],[4,BotState.HARD,BotState.MEDIUM,BotState.EASY],[5,BotState.HARD,BotState.MEDIUM,BotState.MEDIUM,BotState.EASY]];
      
      public static var CHALLENGE:Array = [CHALLENGE_1P,CHALLENGE_1P];
      
      public function Challenges()
      {
         super();
      }
   }
}

