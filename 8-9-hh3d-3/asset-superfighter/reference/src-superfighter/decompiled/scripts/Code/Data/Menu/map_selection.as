package Code.Data.Menu
{
   import Code.Handler.*;
   import flash.display.MovieClip;
   
   public class map_selection extends submenu_base
   {
      public var Mode:int = 1;
      
      public var Level:int = 2;
      
      public function map_selection(param1:MovieClip, param2:Sounds)
      {
         Level = 2;
         Mode = 1;
         super();
         _this = param1;
         _canReturn = true;
         _Handler_Sounds = param2;
         _canReturn = true;
         UpdateMarker();
      }
      
      override public function UpdateMarker() : void
      {
         _this.highlight_0.visible = false;
         _this.highlight_1.visible = false;
         _this.marker_0.visible = false;
         _this.marker_1.visible = false;
         _this.marker_2.visible = false;
         _this.marker_3.visible = false;
         _this.marker_4.visible = false;
         _this.marker_5.visible = false;
         if(_marker_pos == 0)
         {
            _this.marker_0.visible = true;
         }
         else if(_marker_pos == 1)
         {
            _this.highlight_0.visible = true;
            _this.marker_1.visible = true;
            _this.marker_2.visible = true;
         }
         else if(_marker_pos == 2)
         {
            _this.highlight_1.visible = true;
            _this.marker_3.visible = true;
            _this.marker_4.visible = true;
         }
         else if(_marker_pos == 3)
         {
            _this.marker_5.visible = true;
         }
         _this.map.gotoAndStop(Level);
         _this.map_pic.gotoAndStop(Level);
         _this.game_mode.gotoAndStop(Mode);
      }
      
      private function ChangeMode(param1:int) : void
      {
         Mode += param1;
         if(Mode < 1)
         {
            Mode = 7;
         }
         if(Mode > 7)
         {
            Mode = 1;
         }
      }
      
      private function ChangeLevel(param1:int) : void
      {
         Level += param1;
         if(Level > Maps.TOTAL_MAPS)
         {
            Level = 2;
         }
         if(Level < 2)
         {
            Level = Maps.TOTAL_MAPS;
         }
      }
      
      override public function KeyPressed(param1:int) : void
      {
         switch(param1)
         {
            case MenuKey.KEY_UP:
               --_marker_pos;
               if(_marker_pos < 0)
               {
                  _marker_pos = 3;
               }
               break;
            case MenuKey.KEY_DOWN:
               ++_marker_pos;
               if(_marker_pos > 3)
               {
                  _marker_pos = 0;
               }
               break;
            case MenuKey.KEY_LEFT:
               if(_marker_pos == 1)
               {
                  ChangeLevel(-1);
               }
               if(_marker_pos == 2)
               {
                  ChangeMode(-1);
               }
               break;
            case MenuKey.KEY_RIGHT:
               if(_marker_pos == 1)
               {
                  ChangeLevel(1);
               }
               if(_marker_pos == 2)
               {
                  ChangeMode(1);
               }
         }
         UpdateMarker();
      }
      
      override public function GetChoice() : String
      {
         if(_marker_pos == 0)
         {
            return "fight";
         }
         if(_marker_pos == 3)
         {
            return "reset";
         }
         return "";
      }
   }
}

