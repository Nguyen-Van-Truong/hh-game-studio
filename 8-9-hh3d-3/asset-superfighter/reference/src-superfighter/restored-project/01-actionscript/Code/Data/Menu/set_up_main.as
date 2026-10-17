package Code.Data.Menu
{
   import Code.Handler.InputKeyboard;
   import Code.Handler.Options;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   import flash.events.KeyboardEvent;
   
   public class set_up_main extends submenu_base
   {
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _Handler_Options:Options;
      
      public function set_up_main(param1:MovieClip, param2:Sounds, param3:InputKeyboard, param4:Options)
      {
         super();
         _this = param1;
         _canReturn = true;
         _Handler_Sounds = param2;
         _Handler_Options = param4;
         _Handler_Keyboard = param3;
         _Handler_Keyboard.KeyDownFunctionRepeatable = keyDownHandler;
         UpdateMarker();
      }
      
      override public function UpdateMarker() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < 7)
         {
            MovieClip(_this.getChildByName("marker_" + _loc1_)).visible = false;
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < 3)
         {
            MovieClip(_this.getChildByName("highlight_" + _loc1_)).visible = false;
            _loc1_++;
         }
         switch(_marker_pos)
         {
            case 0:
               _this.marker_0.visible = true;
               _this.marker_1.visible = true;
               _this.highlight_0.visible = true;
               break;
            case 1:
               _this.marker_2.visible = true;
               _this.marker_3.visible = true;
               _this.highlight_1.visible = true;
               break;
            case 2:
               _this.marker_4.visible = true;
               _this.marker_5.visible = true;
               _this.highlight_2.visible = true;
               break;
            case 3:
               _this.marker_6.visible = true;
         }
         UpdateText();
      }
      
      private function UpdateText() : void
      {
         _this.graphic_text.text = _Handler_Options.GetStageQuality();
         _this.effect_text.text = _Handler_Options.GetEffectQuality();
         _this.volume_text.text = Math.round(_Handler_Sounds.SoundEffectVolume * 100) + " %";
      }
      
      override public function Show() : void
      {
         _this.visible = true;
         UpdateMarker();
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
               if(_marker_pos == 0)
               {
                  _Handler_Options.ToggleGraphicQuality(-1);
               }
               if(_marker_pos == 1)
               {
                  _Handler_Options.ToggleEffectLevel(-1);
               }
               if(_marker_pos == 2)
               {
                  _Handler_Sounds.ChangeEffectVolume(0);
               }
               break;
            case MenuKey.KEY_RIGHT:
               if(_marker_pos == 0)
               {
                  _Handler_Options.ToggleGraphicQuality(1);
               }
               if(_marker_pos == 1)
               {
                  _Handler_Options.ToggleEffectLevel(1);
               }
               if(_marker_pos == 2)
               {
                  _Handler_Sounds.ChangeEffectVolume(0);
               }
               break;
            case MenuKey.KEY_BACKSPACE:
               _Handler_Keyboard.KeyDownFunctionRepeatable = null;
               _Handler_Options.SaveData();
         }
         UpdateMarker();
      }
      
      private function keyDownHandler(param1:KeyboardEvent) : void
      {
         if(_marker_pos == 2)
         {
            if(param1.keyCode == 37)
            {
               _Handler_Sounds.ChangeEffectVolume(-0.01);
            }
            if(param1.keyCode == 39)
            {
               _Handler_Sounds.ChangeEffectVolume(0.01);
            }
            _this.volume_text.text = Math.round(_Handler_Sounds.SoundEffectVolume * 100) + " %";
         }
      }
      
      override public function GetChoice() : String
      {
         switch(_marker_pos)
         {
            case 3:
               return "set_up";
            default:
               return "";
         }
      }
   }
}

