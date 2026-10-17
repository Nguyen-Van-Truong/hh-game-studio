package Code.Data.Menu
{
   import Code.Data.Players.*;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   import flash.geom.ColorTransform;
   
   public class player_plate extends submenu_base
   {
      private var _allChoicesDone:Boolean = false;
      
      private var _curr_choice:int = -1;
      
      private var _canSelectTeam:Boolean;
      
      private var _character:int = 0;
      
      private var _team:int = 0;
      
      public function player_plate(param1:MovieClip, param2:Sounds, param3:int, param4:Boolean)
      {
         _allChoicesDone = false;
         _curr_choice = -1;
         _character = 0;
         _team = 0;
         super();
         _this = param1;
         _Handler_Sounds = param2;
         UpdateMarker();
         _this.player_type.gotoAndStop(param3);
         _canSelectTeam = param4;
         if(_canSelectTeam)
         {
            _this.gotoAndStop(1);
         }
         else
         {
            _this.gotoAndStop(2);
            _team = 1;
         }
         ShowCharacter();
         ShowTeam();
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
      }
      
      public function get Team() : int
      {
         return _team;
      }
      
      public function get Character() : int
      {
         return _character;
      }
      
      private function HideMarker() : void
      {
         _this.highlight_0.visible = false;
         _this.highlight_1.visible = false;
         _this.marker_0.visible = false;
         _this.marker_1.visible = false;
         _this.marker_2.visible = false;
         _this.marker_3.visible = false;
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
               break;
            case MenuKey.KEY_DOWN:
               if(!_canSelectTeam)
               {
                  return;
               }
               if(_curr_choice < 1)
               {
                  ++_curr_choice;
               }
               else
               {
                  --_curr_choice;
               }
               UpdateMarker();
               break;
            case MenuKey.KEY_ENTER:
               HideMarker();
               _canReturn = false;
               _allChoicesDone = true;
               break;
            case MenuKey.KEY_UP:
               if(!_canSelectTeam)
               {
                  return;
               }
               if(_curr_choice > 0)
               {
                  --_curr_choice;
               }
               else
               {
                  ++_curr_choice;
               }
               UpdateMarker();
               break;
            case MenuKey.KEY_BACKSPACE:
               HideMarker();
               _canReturn = true;
               _allChoicesDone = false;
         }
      }
      
      public function set CurrChoice(param1:int) : void
      {
         _curr_choice = param1;
         UpdateMarker();
         ShowCharacter();
         ShowTeam();
      }
      
      override public function GetChoice() : String
      {
         if(_allChoicesDone)
         {
            return "done";
         }
         return "";
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
   }
}

