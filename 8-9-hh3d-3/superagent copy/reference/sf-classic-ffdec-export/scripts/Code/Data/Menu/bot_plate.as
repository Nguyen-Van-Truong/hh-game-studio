package Code.Data.Menu
{
   import Code.Data.Players.*;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   import flash.geom.ColorTransform;
   
   public class bot_plate extends submenu_base
   {
      private var _allChoicesDone:Boolean = false;
      
      private var _curr_choice:int = -1;
      
      private var _must_not_team:int = 0;
      
      private var _difficulty:int = 2;
      
      private var _character:int = 0;
      
      private var _team:int = 0;
      
      public function bot_plate(param1:MovieClip, param2:Sounds)
      {
         _allChoicesDone = false;
         _curr_choice = -1;
         _character = 0;
         _team = 0;
         _difficulty = 2;
         _must_not_team = 0;
         super();
         _this = param1;
         _Handler_Sounds = param2;
         _this.empty_cover.visible = true;
         UpdateMarker();
         ShowCharacter();
         ShowTeam();
         ShowDifficulty();
      }
      
      override public function UpdateMarker() : void
      {
         HideMarker();
         if(_curr_choice == 0)
         {
            _this.marker_0.visible = true;
            _this.marker_1.visible = true;
            _this.highlight_0.visible = true;
         }
         else if(_curr_choice == 1)
         {
            _this.marker_2.visible = true;
            _this.marker_3.visible = true;
            _this.highlight_1.visible = true;
            UncolorTeam();
         }
         else if(_curr_choice == 2)
         {
            _this.marker_4.visible = true;
            _this.marker_5.visible = true;
            _this.highlight_2.visible = true;
         }
      }
      
      public function get Team() : int
      {
         return _team;
      }
      
      private function ChangeCharacter(param1:int) : void
      {
         _character += param1;
         if(_character < 0)
         {
            _character = PlayerCharacter.TOTAL_CHARACTERS;
         }
         if(_character > PlayerCharacter.TOTAL_CHARACTERS)
         {
            _character = 0;
         }
         if(!PlayerCharacter.CharacterAvailable(_character))
         {
            ChangeCharacter(param1);
         }
         ShowCharacter();
      }
      
      public function get Character() : int
      {
         return _character;
      }
      
      private function HideMarker() : void
      {
         _this.highlight_0.visible = false;
         _this.highlight_1.visible = false;
         _this.highlight_2.visible = false;
         _this.marker_0.visible = false;
         _this.marker_1.visible = false;
         _this.marker_2.visible = false;
         _this.marker_3.visible = false;
         _this.marker_4.visible = false;
         _this.marker_5.visible = false;
         ColorTeam();
      }
      
      private function ShowCharacter() : void
      {
         if(_character == 0)
         {
            _this.character_name.gotoAndStop("RANDOM");
            _this.character_pic.gotoAndStop("RANDOM");
         }
         else
         {
            _this.character_name.gotoAndStop(_character);
            _this.character_pic.gotoAndStop(_character);
         }
      }
      
      private function ChangeTeam(param1:int) : void
      {
         _team += param1;
         if(_team < 0)
         {
            _team = 4;
         }
         if(_team > 4)
         {
            _team = 0;
         }
         if(_team == _must_not_team && _must_not_team != 0)
         {
            ChangeTeam(param1);
            return;
         }
         ShowTeam();
      }
      
      private function UncolorTeam() : void
      {
         var _loc1_:ColorTransform = null;
         _loc1_ = _this.team.transform.colorTransform;
         _loc1_.redOffset = PlayerTeamColor.SOLO[0] - 255;
         _loc1_.greenOffset = PlayerTeamColor.SOLO[1] - 255;
         _loc1_.blueOffset = PlayerTeamColor.SOLO[2] - 255;
         _this.team.transform.colorTransform = _loc1_;
      }
      
      public function get CurrChoice() : int
      {
         return _curr_choice;
      }
      
      public function get Difficulty() : int
      {
         return _difficulty;
      }
      
      public function SetStartItems(param1:int, param2:int) : void
      {
         if(_this.empty_cover.visible == true)
         {
            if(param1 != _must_not_team)
            {
               _team = param1;
            }
            _difficulty = param2;
         }
      }
      
      override public function KeyPressed(param1:int) : void
      {
         switch(param1)
         {
            case MenuKey.KEY_LEFT:
               if(_curr_choice == 0)
               {
                  ChangeCharacter(-1);
               }
               else if(_curr_choice == 1)
               {
                  ChangeTeam(-1);
               }
               else if(_curr_choice == 2)
               {
                  ChangeDifficulty(-1);
               }
               break;
            case MenuKey.KEY_RIGHT:
               if(_curr_choice == 0)
               {
                  ChangeCharacter(1);
               }
               else if(_curr_choice == 1)
               {
                  ChangeTeam(1);
               }
               else if(_curr_choice == 2)
               {
                  ChangeDifficulty(1);
               }
               break;
            case MenuKey.KEY_DOWN:
               if(_curr_choice < 2)
               {
                  ++_curr_choice;
               }
               else
               {
                  _curr_choice = 0;
               }
               UpdateMarker();
               break;
            case MenuKey.KEY_ENTER:
               HideMarker();
               _canReturn = false;
               _allChoicesDone = true;
               break;
            case MenuKey.KEY_UP:
               if(_curr_choice > 0)
               {
                  --_curr_choice;
               }
               else
               {
                  _curr_choice = 2;
               }
               UpdateMarker();
               break;
            case MenuKey.KEY_BACKSPACE:
               HideMarker();
               _canReturn = true;
               _allChoicesDone = false;
         }
      }
      
      private function ShowDifficulty() : void
      {
         _this.difficulty.gotoAndStop(_difficulty);
      }
      
      public function set CurrChoice(param1:int) : void
      {
         _curr_choice = param1;
         _this.empty_cover.visible = false;
         UpdateMarker();
         ShowCharacter();
         ShowTeam();
         ShowDifficulty();
      }
      
      private function ShowTeam() : void
      {
         if(_team == 0)
         {
            _this.team.gotoAndStop("SOLO");
         }
         else
         {
            _this.team.gotoAndStop(_team);
         }
      }
      
      public function set MusntTeam(param1:int) : void
      {
         _must_not_team = param1;
         if(param1 != 0)
         {
            if(_team == param1)
            {
            }
         }
      }
      
      private function ChangeDifficulty(param1:int) : void
      {
         _difficulty += param1;
         if(_difficulty > 3)
         {
            _difficulty = 1;
         }
         if(_difficulty < 1)
         {
            _difficulty = 3;
         }
         ShowDifficulty();
      }
      
      override public function GetChoice() : String
      {
         if(_allChoicesDone)
         {
            return "done";
         }
         return "";
      }
      
      private function ColorTeam() : void
      {
         var _loc1_:ColorTransform = null;
         if(_team == 0)
         {
            UncolorTeam();
            return;
         }
         _loc1_ = _this.team.transform.colorTransform;
         _loc1_.redOffset = PlayerTeamColor.TEAM[_team - 1][0] - 255;
         _loc1_.greenOffset = PlayerTeamColor.TEAM[_team - 1][1] - 255;
         _loc1_.blueOffset = PlayerTeamColor.TEAM[_team - 1][2] - 255;
         _this.team.transform.colorTransform = _loc1_;
      }
   }
}

