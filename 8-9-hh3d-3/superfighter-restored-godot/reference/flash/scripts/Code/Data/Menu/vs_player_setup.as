package Code.Data.Menu
{
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   
   public class vs_player_setup extends submenu_base
   {
      private var _all_plates_set:Boolean = false;
      
      private var _mode:int;
      
      private var _curr_plate:int = 0;
      
      private var _players:int;
      
      private var _plates:Array;
      
      public function vs_player_setup(param1:MovieClip, param2:Sounds, param3:int, param4:int)
      {
         var _loc5_:Boolean = false;
         var _loc6_:int = 0;
         _curr_plate = 0;
         _all_plates_set = false;
         super();
         _this = param1;
         _Handler_Sounds = param2;
         _players = param3;
         _plates = new Array();
         _mode = param4;
         _loc5_ = true;
         if(_mode == 1 || _mode == 2)
         {
            _loc5_ = false;
         }
         _loc6_ = 1;
         while(_loc6_ <= _players)
         {
            _plates.push(new player_plate(MovieClip(_this.getChildByName("p" + _loc6_ + "_plate")),_Handler_Sounds,_loc6_,_loc5_));
            _loc6_++;
         }
         _plates[0].CurrChoice = 0;
      }
      
      public function get PlayerPlateOne() : player_plate
      {
         return _plates[0];
      }
      
      public function get PlayerPlateTwo() : player_plate
      {
         return _plates[1];
      }
      
      private function CheckNextPlate() : void
      {
         var _loc1_:String = null;
         _canReturn = false;
         _loc1_ = _plates[_curr_plate].GetChoice();
         if(_loc1_ == "done")
         {
            if(_curr_plate < _players - 1)
            {
               ++_curr_plate;
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
      
      private function CheckPrevPlate() : void
      {
         _all_plates_set = false;
         if(_plates[_curr_plate].CanReturn)
         {
            if(_curr_plate > 0)
            {
               --_curr_plate;
               _plates[_curr_plate].CurrChoice = 0;
               _Handler_Sounds.PlayMightySound("CANCEL");
            }
            else
            {
               _canReturn = true;
            }
         }
      }
      
      override public function GetChoice() : String
      {
         if(_all_plates_set && _mode == 0)
         {
            return "no_bots";
         }
         if(_all_plates_set && _mode == 1)
         {
            return "challenge_selection";
         }
         if(_all_plates_set && _mode == 2)
         {
            return "start_survival";
         }
         return "";
      }
   }
}

