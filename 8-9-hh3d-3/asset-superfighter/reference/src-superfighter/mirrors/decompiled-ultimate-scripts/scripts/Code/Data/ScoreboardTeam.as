package Code.Data
{
   import Code.Data.Players.*;
   import flash.display.MovieClip;
   import flash.geom.ColorTransform;
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public class ScoreboardTeam
   {
      public var Loss:int;
      
      private var _team:int;
      
      private var _team_graphic:MovieClip;
      
      private var _players:Array;
      
      public var Wins:int;
      
      private var _build_timer:Number;
      
      public function ScoreboardTeam(param1:Player)
      {
         super();
         Wins = 0;
         Loss = 0;
         _team = param1.Team;
         _players = new Array();
         _players.push(param1);
      }
      
      public function AddPlayer(param1:Player) : void
      {
         _players.push(param1);
      }
      
      public function SetPics() : void
      {
         var _loc1_:int = 0;
         clearInterval(_build_timer);
         _loc1_ = 0;
         while(_loc1_ < TotalPlayers)
         {
            MovieClip(_team_graphic.pics.getChildByName("pic_" + (_loc1_ + 1))).gotoAndStop(_players[_loc1_].State.CharNr);
            _loc1_++;
         }
      }
      
      public function Build(param1:int) : void
      {
         var _loc2_:int = 0;
         var _loc3_:ColorTransform = null;
         _team_graphic = new score_team_plate();
         _team_graphic.gotoAndStop(param1);
         _team_graphic.pics.gotoAndStop(TotalPlayers);
         if(TotalPlayers <= 4 && param1 > 4)
         {
            _team_graphic.pics.x = 25 * (param1 - 4);
         }
         _loc2_ = int(_players[0].Team);
         if(_loc2_ < 0)
         {
            _loc2_ = 5;
         }
         _team_graphic.pics.team.gotoAndStop(_loc2_);
         _loc3_ = _team_graphic.pics.team.transform.colorTransform;
         if(_players[0].Team < 0)
         {
            _loc3_.redOffset = PlayerTeamColor.SOLO[0] - 255;
            _loc3_.greenOffset = PlayerTeamColor.SOLO[1] - 255;
            _loc3_.blueOffset = PlayerTeamColor.SOLO[2] - 255;
         }
         else
         {
            _loc3_.redOffset = PlayerTeamColor.TEAM[_players[0].Team - 1][0] - 255;
            _loc3_.greenOffset = PlayerTeamColor.TEAM[_players[0].Team - 1][1] - 255;
            _loc3_.blueOffset = PlayerTeamColor.TEAM[_players[0].Team - 1][2] - 255;
         }
         _team_graphic.pics.team.transform.colorTransform = _loc3_;
         _build_timer = setInterval(SetPics,100);
         Update();
      }
      
      public function get FirstPlayer() : Player
      {
         return _players[0];
      }
      
      public function get MC() : MovieClip
      {
         return _team_graphic;
      }
      
      public function Update() : void
      {
         SetNumTo(_team_graphic.score.wins,Wins);
         SetNumTo(_team_graphic.score.loss,Loss);
      }
      
      public function get TotalPlayers() : int
      {
         return _players.length;
      }
      
      public function get Team() : int
      {
         return _team;
      }
      
      private function SetNumTo(param1:MovieClip, param2:int) : void
      {
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         _loc3_ = param2 % 10;
         _loc4_ = int((param2 - _loc3_) / 10);
         if(_loc3_ == 0)
         {
            param1.dig_1.gotoAndStop(10);
         }
         else
         {
            param1.dig_1.gotoAndStop(_loc3_);
         }
         if(_loc4_ == 0)
         {
            param1.dig_10.gotoAndStop(10);
         }
         else
         {
            param1.dig_10.gotoAndStop(_loc4_);
         }
      }
   }
}

