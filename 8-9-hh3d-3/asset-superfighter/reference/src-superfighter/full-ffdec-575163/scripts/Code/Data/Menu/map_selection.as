package Code.Data.Menu
{
   import Code.Handler.Maps;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   
   public class map_selection extends submenu_base
   {
      private var _mode:int;
      
      public var Mode:int = 1;
      
      public var Level:int;
      
      public function map_selection(param1:MovieClip, param2:Sounds, param3:int)
      {
         Level = Maps.RANDOM_MAP;
         Mode = 1;
         super();
         _mode = param3;
         _this = param1;
         _canReturn = true;
         _Handler_Sounds = param2;
         _canReturn = true;
         if(_mode == 0)
         {
            _this.gotoAndStop(1);
         }
         else if(_mode == 2)
         {
            _this.gotoAndStop(2);
            Level = 10;
         }
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
         if(_mode == 0)
         {
            _this.game_mode.gotoAndStop(Mode);
         }
         else if(_mode == 2)
         {
            _this.game_mode.gotoAndStop(10);
         }
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
         if(_mode == 0)
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
         else if(_mode == 2)
         {
            Level += param1;
            if(Level - 9 > Maps.TOTAL_SURVIVAL_MAPS)
            {
               Level = 10;
            }
            if(Level - 9 < 1)
            {
               Level = 9 + Maps.TOTAL_SURVIVAL_MAPS;
            }
         }
      }
      
      override public function KeyPressed(param1:int) : void
      {
         switch(param1)
         {
            case MenuKey.KEY_UP:
               --_marker_pos;
               if(_mode == 2 && _marker_pos == 2)
               {
                  --_marker_pos;
               }
               if(_marker_pos < 0)
               {
                  _marker_pos = 3;
               }
               break;
            case MenuKey.KEY_DOWN:
               ++_marker_pos;
               if(_mode == 2 && _marker_pos == 2)
               {
                  ++_marker_pos;
               }
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
            if(_mode == 0)
            {
               return "fight";
            }
            if(_mode == 2)
            {
               return "start_survival";
            }
         }
         else if(_marker_pos == 3)
         {
            return "reset";
         }
         return "";
      }
   }
}

