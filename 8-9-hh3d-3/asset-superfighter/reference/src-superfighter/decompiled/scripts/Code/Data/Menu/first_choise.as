package Code.Data.Menu
{
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   import flash.net.*;
   
   public class first_choise extends submenu_base
   {
      private var _players:int = 1;
      
      public function first_choise(param1:MovieClip, param2:Sounds)
      {
         _players = 1;
         super();
         _this = param1;
         _total_markers = 4;
         _Handler_Sounds = param2;
         _canReturn = true;
         LoadData();
         UpdateMarker();
      }
      
      private function LoadData() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         if(_loc1_.data.startedBefore == undefined)
         {
            _marker_pos = 2;
            _this.tutorial_promt.visible = true;
            SaveData();
         }
         else
         {
            _this.tutorial_promt.visible = false;
         }
      }
      
      public function get Players() : int
      {
         return _players;
      }
      
      override public function KeyPressed(param1:int) : void
      {
         switch(param1)
         {
            case MenuKey.KEY_UP:
               --_marker_pos;
               if(_marker_pos < 0)
               {
                  _marker_pos = _total_markers - 1;
               }
               break;
            case MenuKey.KEY_DOWN:
               ++_marker_pos;
               if(_marker_pos >= _total_markers)
               {
                  _marker_pos = 0;
               }
         }
         UpdateMarker();
      }
      
      private function SaveData() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         _loc1_.data.startedBefore = true;
         _loc1_.flush();
      }
      
      override public function GetChoice() : String
      {
         switch(_marker_pos)
         {
            case 0:
               _players = 1;
               return "mode_selection";
            case 1:
               _players = 2;
               return "mode_selection";
            case 2:
               _players = 1;
               return "tutorial";
            case 3:
               return "set_up_main";
            default:
               return "";
         }
      }
   }
}

