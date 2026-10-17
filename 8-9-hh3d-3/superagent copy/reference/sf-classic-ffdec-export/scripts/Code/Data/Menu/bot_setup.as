package Code.Data.Menu
{
   import Code.Handler.Sounds;
   import flash.display.*;
   
   public class bot_setup extends submenu_base
   {
      private var _all_plates_set:Boolean = false;
      
      private var _must_not_team:int;
      
      private var _max_plates:int;
      
      private var _curr_plate:int = 0;
      
      private var _bots:int;
      
      private var _plates:Array;
      
      public function bot_setup(param1:MovieClip, param2:Sounds, param3:int, param4:int)
      {
         var i:int = 0;
         var botPlate:MovieClip = null;
         var j:int = 0;
         var mc:MovieClip = param1;
         var snd:Sounds = param2;
         var nrOfBots:int = param3;
         var musntTeam:int = param4;
         _curr_plate = 0;
         _all_plates_set = false;
         super();
         _this = mc;
         _Handler_Sounds = snd;
         _bots = nrOfBots;
         _must_not_team = musntTeam;
         _canReturn = true;
         _plates = new Array();
         try
         {
            _this.cp_7.visible = true;
            _max_plates = 7;
         }
         catch(e:Error)
         {
            _max_plates = 6;
         }
         i = 1;
         while(i <= _max_plates)
         {
            botPlate = MovieClip(_this.getChildByName("cp_" + i));
            botPlate.visible = true;
            _plates.push(new bot_plate(botPlate,_Handler_Sounds));
            i++;
         }
         if(_bots < _max_plates)
         {
            j = _bots + 1;
            while(j <= _max_plates)
            {
               MovieClip(_this.getChildByName("cp_" + j)).visible = false;
               j++;
            }
         }
         _plates[0].CurrChoice = 0;
         if(_bots == 1)
         {
            _plates[0].MusntTeam = _must_not_team;
         }
      }
      
      private function CheckNextPlate() : void
      {
         var _loc1_:String = null;
         _canReturn = false;
         _loc1_ = _plates[_curr_plate].GetChoice();
         if(_loc1_ == "done")
         {
            if(_curr_plate < _bots - 1)
            {
               ++_curr_plate;
               _plates[_curr_plate].MusntTeam = GetMustNotTeam();
               _plates[_curr_plate].SetStartItems(_plates[_curr_plate - 1].Team,_plates[_curr_plate - 1].Difficulty);
               _plates[_curr_plate].CurrChoice = 0;
               _Handler_Sounds.PlayMightySound("ACCEPT");
            }
            else
            {
               _all_plates_set = true;
            }
         }
      }
      
      override public function Show() : void
      {
         _this.visible = true;
         _plates[_curr_plate].CurrChoice = 0;
      }
      
      override public function KeyPressed(param1:int) : void
      {
         _plates[_curr_plate].KeyPressed(param1);
         switch(param1)
         {
            case MenuKey.KEY_ENTER:
               CheckNextPlate();
               break;
            case MenuKey.KEY_BACKSPACE:
               CheckPrevPlate();
         }
      }
      
      public function get BotPlates() : Array
      {
         return _plates;
      }
      
      private function CheckPrevPlate() : void
      {
         _all_plates_set = false;
         if(Boolean(_plates[_curr_plate].CanReturn))
         {
            if(_curr_plate > 0)
            {
               --_curr_plate;
               _plates[_curr_plate].MusntTeam = GetMustNotTeam();
               _plates[_curr_plate].CurrChoice = 0;
               _Handler_Sounds.PlayMightySound("CANCEL");
            }
            else
            {
               _canReturn = true;
            }
         }
      }
      
      private function GetMustNotTeam() : int
      {
         var _loc1_:int = 0;
         if(_must_not_team != 0)
         {
            _loc1_ = 0;
            while(_loc1_ < _bots)
            {
               if(_loc1_ != _curr_plate)
               {
                  if(_plates[_loc1_].Team != _must_not_team)
                  {
                     return 0;
                  }
               }
               _loc1_++;
            }
            return _must_not_team;
         }
         return 0;
      }
      
      override public function GetChoice() : String
      {
         if(_all_plates_set)
         {
            return "map_selection";
         }
         return "";
      }
   }
}

