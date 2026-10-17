package Code.Data.Menu
{
   import Code.Data.Players.Player;
   import Code.Handler.InputKeyboard;
   import Code.Handler.Options;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   import flash.events.Event;
   import flash.events.KeyboardEvent;
   import flash.text.TextField;
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public class set_up extends submenu_base
   {
      private static var SIMPLE:int = 0;
      
      private static var ADVANCED:int = 1;
      
      private static var TOTAL_SELECTIONS:Array = [10,13];
      
      private var _delay_key:Boolean = true;
      
      private var _Handler_Options:Options;
      
      private var _lockKeys:Boolean = false;
      
      private var _curr_player:int = 0;
      
      private var _key_edit_timer:Number;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _config:int;
      
      private var _update_delay:Boolean;
      
      private var _update_marker_timer:Number;
      
      private var _wait_for_key:Boolean = false;
      
      public function set_up(param1:MovieClip, param2:Sounds, param3:InputKeyboard, param4:Options)
      {
         _curr_player = 0;
         _config = SIMPLE;
         _wait_for_key = false;
         _delay_key = true;
         _lockKeys = false;
         super();
         _this = param1;
         _marker_pos = 0;
         _canReturn = true;
         _Handler_Sounds = param2;
         _Handler_Keyboard = param3;
         _Handler_Options = param4;
         UpdateMarker();
         _Handler_Keyboard.KeyDownFunction = keyDownHandler;
      }
      
      override public function UpdateMarker() : void
      {
         try
         {
            UpdateMarkerTick(null);
         }
         catch(e:Error)
         {
            _update_delay = false;
            _this.removeEventListener(Event.ENTER_FRAME,UpdateMarkerTick);
            _this.addEventListener(Event.ENTER_FRAME,UpdateMarkerTick,false,0,true);
         }
      }
      
      override public function GetChoice() : String
      {
         return "";
      }
      
      private function EngageWaiting() : void
      {
         _delay_key = true;
         _wait_for_key = true;
         _canReturn = false;
         GetCurrentTextField().text = "PRESS";
         MovieClip(_this.getChildByName("highlight_" + (_marker_pos + 2))).visible = true;
         _key_edit_timer = setInterval(function():*
         {
            clearInterval(_key_edit_timer);
            _delay_key = false;
         },100);
      }
      
      override public function Show() : void
      {
         _this.gotoAndStop(_config);
         _this.visible = true;
         UpdateMarker();
      }
      
      public function PrintKeys() : void
      {
         if(_config == SIMPLE)
         {
            PrintKeyFor(_this.key_up,Player.KEY_JUMP,Player.KEY_UP);
            PrintKeyFor(_this.key_down,Player.KEY_KNEEL,Player.KEY_DOWN);
            PrintKeyFor(_this.key_left,Player.KEY_LEFT,Player.KEY_LEFT);
            PrintKeyFor(_this.key_right,Player.KEY_RIGHT,Player.KEY_RIGHT);
            PrintKeyFor(_this.key_melee,Player.KEY_MELEE,Player.KEY_MELEE);
            PrintKeyFor(_this.key_fire,Player.KEY_FIRE,Player.KEY_FIRE);
            PrintKeyFor(_this.key_throw,Player.KEY_THROW,Player.KEY_THROW);
            PrintKeyFor(_this.key_powerup,Player.KEY_POWERUP,Player.KEY_POWERUP);
         }
         else
         {
            PrintKeyFor(_this.key_up,Player.KEY_UP,Player.KEY_UP);
            PrintKeyFor(_this.key_jump,Player.KEY_JUMP,Player.KEY_JUMP);
            PrintKeyFor(_this.key_down,Player.KEY_DOWN,Player.KEY_DOWN);
            PrintKeyFor(_this.key_kneel,Player.KEY_KNEEL,Player.KEY_KNEEL);
            PrintKeyFor(_this.key_left,Player.KEY_LEFT,Player.KEY_LEFT);
            PrintKeyFor(_this.key_right,Player.KEY_RIGHT,Player.KEY_RIGHT);
            PrintKeyFor(_this.key_melee,Player.KEY_MELEE,Player.KEY_MELEE);
            PrintKeyFor(_this.key_fire,Player.KEY_FIRE,Player.KEY_FIRE);
            PrintKeyFor(_this.key_throw,Player.KEY_THROW,Player.KEY_THROW);
            PrintKeyFor(_this.key_powerup,Player.KEY_POWERUP,Player.KEY_POWERUP);
            PrintKeyFor(_this.key_sprint,Player.KEY_SPRINT,Player.KEY_SPRINT);
         }
      }
      
      private function GetCurrentTextField() : TextField
      {
         if(_config == SIMPLE)
         {
            switch(_marker_pos)
            {
               case 2:
                  return _this.key_up;
               case 3:
                  return _this.key_down;
               case 4:
                  return _this.key_left;
               case 5:
                  return _this.key_right;
               case 6:
                  return _this.key_melee;
               case 7:
                  return _this.key_fire;
               case 8:
                  return _this.key_throw;
               case 9:
                  return _this.key_powerup;
            }
         }
         else
         {
            switch(_marker_pos)
            {
               case 2:
                  return _this.key_up;
               case 3:
                  return _this.key_jump;
               case 4:
                  return _this.key_down;
               case 5:
                  return _this.key_kneel;
               case 6:
                  return _this.key_left;
               case 7:
                  return _this.key_right;
               case 8:
                  return _this.key_melee;
               case 9:
                  return _this.key_fire;
               case 10:
                  return _this.key_throw;
               case 11:
                  return _this.key_powerup;
               case 12:
                  return _this.key_sprint;
            }
         }
         return null;
      }
      
      private function EditKeyBind() : void
      {
         if(!_wait_for_key)
         {
            EngageWaiting();
         }
      }
      
      private function SetDefaultKeys() : void
      {
         if(_curr_player == 0)
         {
            _Handler_Options.SetDefaultP1Keys();
         }
         else
         {
            _Handler_Options.SetDefaultP2Keys();
         }
         _Handler_Sounds.PlayMightySound("ACCEPT");
         PrintKeys();
      }
      
      private function GetCurrentKeyIndex() : Array
      {
         if(_config == SIMPLE)
         {
            switch(_marker_pos)
            {
               case 2:
                  return [Player.KEY_UP,Player.KEY_JUMP];
               case 3:
                  return [Player.KEY_DOWN,Player.KEY_KNEEL];
               case 4:
                  return [Player.KEY_LEFT];
               case 5:
                  return [Player.KEY_RIGHT];
               case 6:
                  return [Player.KEY_MELEE];
               case 7:
                  return [Player.KEY_FIRE];
               case 8:
                  return [Player.KEY_THROW];
               case 9:
                  return [Player.KEY_POWERUP];
            }
         }
         else
         {
            switch(_marker_pos)
            {
               case 2:
                  return [Player.KEY_UP];
               case 3:
                  return [Player.KEY_JUMP];
               case 4:
                  return [Player.KEY_DOWN];
               case 5:
                  return [Player.KEY_KNEEL];
               case 6:
                  return [Player.KEY_LEFT];
               case 7:
                  return [Player.KEY_RIGHT];
               case 8:
                  return [Player.KEY_MELEE];
               case 9:
                  return [Player.KEY_FIRE];
               case 10:
                  return [Player.KEY_THROW];
               case 11:
                  return [Player.KEY_POWERUP];
               case 12:
                  return [Player.KEY_SPRINT];
            }
         }
         return [0];
      }
      
      private function UpdateMarkerTick(param1:Event) : void
      {
         var _loc2_:int = 0;
         if(!_update_delay)
         {
            _update_delay = true;
            return;
         }
         _this.removeEventListener(Event.ENTER_FRAME,UpdateMarkerTick);
         _loc2_ = 0;
         while(_loc2_ < 16)
         {
            MovieClip(_this.getChildByName("marker_" + _loc2_)).visible = false;
            _loc2_++;
         }
         _this.highlight_0.visible = false;
         _this.highlight_1.visible = false;
         _loc2_ = 4;
         while(_loc2_ < 16)
         {
            MovieClip(_this.getChildByName("highlight_" + _loc2_)).visible = false;
            _loc2_++;
         }
         switch(_marker_pos)
         {
            case 0:
               _this.highlight_0.visible = true;
               _this.marker_0.visible = true;
               _this.marker_1.visible = true;
               break;
            case 1:
               _this.highlight_1.visible = true;
               _this.marker_2.visible = true;
               _this.marker_3.visible = true;
               break;
            default:
               MovieClip(_this.getChildByName("marker_" + (_marker_pos + 2))).visible = true;
         }
         PrintKeys();
      }
      
      private function PrintKeyFor(param1:TextField, param2:int, param3:int) : void
      {
         if(_Handler_Options.PlayerKeys[_curr_player][param2] == _Handler_Options.PlayerKeys[_curr_player][param3])
         {
            if(_Handler_Options.PlayerKeys[_curr_player][param2] == 0)
            {
               param1.text = "[ NONE ]";
            }
            else
            {
               param1.text = _Handler_Keyboard.GetCharFromCode(_Handler_Options.PlayerKeys[_curr_player][param2]);
            }
         }
         else
         {
            param1.text = _Handler_Keyboard.GetCharFromCode(_Handler_Options.PlayerKeys[_curr_player][param2]) + " / " + _Handler_Keyboard.GetCharFromCode(_Handler_Options.PlayerKeys[_curr_player][param3]);
         }
      }
      
      private function ToggleConfig() : void
      {
         if(_config == SIMPLE)
         {
            _config = ADVANCED;
         }
         else
         {
            _config = SIMPLE;
         }
         _this.gotoAndStop(_config + 1);
      }
      
      override public function KeyPressed(param1:int) : void
      {
         if(_wait_for_key)
         {
            return;
         }
         switch(param1)
         {
            case MenuKey.KEY_UP:
               --_marker_pos;
               if(_marker_pos < 0)
               {
                  _marker_pos = TOTAL_SELECTIONS[_config];
               }
               break;
            case MenuKey.KEY_DOWN:
               ++_marker_pos;
               if(_marker_pos > TOTAL_SELECTIONS[_config])
               {
                  _marker_pos = 0;
               }
               break;
            case MenuKey.KEY_LEFT:
               if(_marker_pos == 0)
               {
                  TogglePlayer();
               }
               if(_marker_pos == 1)
               {
                  ToggleConfig();
               }
               break;
            case MenuKey.KEY_RIGHT:
               if(_marker_pos == 0)
               {
                  TogglePlayer();
               }
               if(_marker_pos == 1)
               {
                  ToggleConfig();
               }
               break;
            case MenuKey.KEY_ENTER:
               if(_marker_pos > 1 && _marker_pos < TOTAL_SELECTIONS[_config])
               {
                  EditKeyBind();
                  return;
               }
               if(_marker_pos == TOTAL_SELECTIONS[_config])
               {
                  SetDefaultKeys();
               }
               break;
            case MenuKey.KEY_BACKSPACE:
               if(!_wait_for_key)
               {
                  _Handler_Keyboard.KeyDownFunction = null;
               }
         }
         UpdateMarker();
      }
      
      private function ReleaseWaiting() : void
      {
         _wait_for_key = false;
         _canReturn = true;
         _lockKeys = false;
         clearInterval(_key_edit_timer);
      }
      
      private function keyDownHandler(param1:KeyboardEvent) : void
      {
         var _loc2_:Array = null;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         if(!_lockKeys && _wait_for_key && !_delay_key)
         {
            _lockKeys = true;
            _loc2_ = GetCurrentKeyIndex();
            _loc3_ = int(param1.keyCode);
            if(_loc3_ == 27)
            {
               _loc3_ = 0;
            }
            _loc4_ = 0;
            while(_loc4_ < _loc2_.length)
            {
               _Handler_Options.PlayerKeys[_curr_player][_loc2_[_loc4_]] = _loc3_;
               _loc4_++;
            }
            _key_edit_timer = setInterval(ReleaseWaiting,60);
            _Handler_Sounds.PlayMightySound("ACCEPT");
            UpdateMarker();
         }
      }
      
      private function TogglePlayer() : void
      {
         if(_curr_player == 0)
         {
            _curr_player = 1;
         }
         else
         {
            _curr_player = 0;
         }
         _this.player_nr.text = (_curr_player + 1).toString();
      }
   }
}

