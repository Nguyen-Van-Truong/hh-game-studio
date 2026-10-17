package Code.Handler
{
   import Code.Data.*;
   import Code.Data.Players.*;
   import flash.display.*;
   
   public class Scoreboard
   {
      private var _gameMode:int;
      
      public var RoundsFinished:int;
      
      private var _score_info:MovieClip;
      
      private var _mostPlayers:int;
      
      private var _teams:Array;
      
      private var _score_graphic:MovieClip;
      
      public function Scoreboard(param1:MovieClip, param2:int)
      {
         super();
         _score_graphic = new MovieClip();
         param1.addChild(_score_graphic);
         _teams = new Array();
         RoundsFinished = 0;
         _gameMode = param2;
      }
      
      private function FirstToReach(param1:int) : Boolean
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < _teams.length)
         {
            if(_teams[_loc2_].Wins >= param1)
            {
               return true;
            }
            _loc2_++;
         }
         return false;
      }
      
      public function Build() : void
      {
         var _loc1_:int = 0;
         var _loc2_:int = 0;
         _score_graphic = new MovieClip();
         _mostPlayers = 0;
         _loc1_ = 0;
         while(_loc1_ < _teams.length)
         {
            if(_teams[_loc1_].TotalPlayers > _mostPlayers)
            {
               _mostPlayers = _teams[_loc1_].TotalPlayers;
            }
            _loc1_++;
         }
         _loc2_ = 0;
         while(_loc2_ < _teams.length)
         {
            _teams[_loc2_].Build(_mostPlayers);
            _score_graphic.addChild(_teams[_loc2_].MC);
            _loc2_++;
         }
         _score_info = new score_info();
         _score_graphic.addChild(_score_info);
         _score_info.game_mode.gotoAndStop(_gameMode);
         _score_info.rounds.text = "0";
      }
      
      public function GetTeamWinner() : ScoreboardTeam
      {
         var _loc1_:int = 0;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         _loc1_ = 0;
         _loc3_ = 1;
         while(_loc3_ < _teams.length)
         {
            if(_teams[_loc3_].Wins > _teams[_loc1_].Wins)
            {
               _loc1_ = _loc3_;
            }
            _loc3_++;
         }
         if(_loc1_ != 0)
         {
            _loc2_ = 0;
         }
         else
         {
            _loc2_ = 1;
         }
         _loc3_ = 1;
         while(_loc3_ < _teams.length)
         {
            if(_teams[_loc3_].Wins > _teams[_loc2_].Wins && _loc3_ != _loc1_)
            {
               _loc2_ = _loc3_;
            }
            _loc3_++;
         }
         if(_teams[_loc1_].Wins == _teams[_loc2_].Wins)
         {
            return null;
         }
         return _teams[_loc1_];
      }
      
      public function get MC() : MovieClip
      {
         return _score_graphic;
      }
      
      public function Show() : void
      {
         _score_graphic.visible = true;
      }
      
      public function Hide() : void
      {
         _score_graphic.visible = false;
      }
      
      public function get GameFinished() : Boolean
      {
         var _loc1_:int = 0;
         switch(_gameMode)
         {
            case 1:
               return false;
            case 2:
               return FirstToReach(3);
            case 3:
               return FirstToReach(5);
            case 4:
               return FirstToReach(10);
            case 5:
               return BestOfReach(3);
            case 6:
               return BestOfReach(5);
            case 7:
               return BestOfReach(10);
            default:
               return false;
         }
      }
      
      public function Update() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Array = null;
         var _loc3_:Number = NaN;
         var _loc4_:int = 0;
         _loc2_ = _teams.sortOn(["Wins","Loss"],Array.NUMERIC | Array.DESCENDING | Array.RETURNINDEXEDARRAY);
         _score_info.rounds.text = RoundsFinished.toString();
         _loc3_ = 45;
         _loc1_ = 0;
         while(_loc1_ < _loc2_.length)
         {
            _loc4_ = int(_loc2_[_loc1_]);
            if(_teams.length <= 4)
            {
               _teams[_loc4_].MC.x = 400 - GetScoreWidth() / 2;
               _teams[_loc4_].MC.y = 300 - 75 * _teams.length / 2 + 75 * _loc1_ + _loc3_;
            }
            else if(_loc1_ < 4)
            {
               _teams[_loc4_].MC.x = 400 - GetScoreWidth();
               _teams[_loc4_].MC.y = 300 - 75 * 4 / 2 + 75 * _loc1_ + _loc3_;
            }
            else
            {
               _teams[_loc4_].MC.x = 400;
               _teams[_loc4_].MC.y = 300 - 75 * 4 / 2 + 75 * (_loc1_ - 4) + _loc3_;
            }
            _loc1_++;
         }
         _score_info.x = _teams[_loc2_[0]].MC.x;
         _score_info.y = _teams[_loc2_[0]].MC.y - 20;
         _loc1_ = 0;
         while(_loc1_ < _teams.length)
         {
            _teams[_loc1_].Update();
            _loc1_++;
         }
      }
      
      private function GetScoreWidth() : Number
      {
         switch(_mostPlayers)
         {
            case 1:
            case 2:
            case 3:
            case 4:
               return 320;
            case 5:
               return 370;
            case 6:
               return 420;
            case 7:
               return 470;
            default:
               return 470;
         }
      }
      
      public function ScoreTeam(param1:int) : void
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < _teams.length)
         {
            if(_teams[_loc2_].Team == param1)
            {
               _teams[_loc2_].Wins += 1;
            }
            else
            {
               _teams[_loc2_].Loss += 1;
            }
            _loc2_++;
         }
      }
      
      public function AddPlayerToScore(param1:Player) : void
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < _teams.length)
         {
            if(_teams[_loc2_].Team == param1.Team)
            {
               _teams[_loc2_].AddPlayer(param1);
               return;
            }
            _loc2_++;
         }
         _teams.push(new ScoreboardTeam(param1));
      }
      
      private function BestOfReach(param1:int) : Boolean
      {
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         if(RoundsFinished >= param1)
         {
            return true;
         }
         _loc2_ = 0;
         _loc4_ = 1;
         while(_loc4_ < _teams.length)
         {
            if(_teams[_loc4_].Wins > _teams[_loc2_].Wins)
            {
               _loc2_ = _loc4_;
            }
            _loc4_++;
         }
         if(_loc2_ != 0)
         {
            _loc3_ = 0;
         }
         else
         {
            _loc3_ = 1;
         }
         _loc4_ = 1;
         while(_loc4_ < _teams.length)
         {
            if(_teams[_loc4_].Wins > _teams[_loc3_].Wins && _loc4_ != _loc2_)
            {
               _loc3_ = _loc4_;
            }
            _loc4_++;
         }
         _loc5_ = _teams[_loc2_].Wins - _teams[_loc3_].Wins;
         _loc6_ = param1 - RoundsFinished;
         if(_loc5_ > _loc6_)
         {
            return true;
         }
         return false;
      }
   }
}

