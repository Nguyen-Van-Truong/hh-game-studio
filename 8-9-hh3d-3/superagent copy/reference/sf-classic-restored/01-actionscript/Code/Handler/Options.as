package Code.Handler
{
   import flash.display.MovieClip;
   import flash.display.StageDisplayState;
   import flash.events.ContextMenuEvent;
   import flash.events.Event;
   import flash.net.SharedObject;
   import flash.net.URLRequest;
   import flash.net.navigateToURL;
   import flash.ui.ContextMenu;
   import flash.ui.ContextMenuItem;
   
   public class Options extends MovieClip
   {
      private var _Handler_Output:OutputTrace;
      
      private var _lastQualityLvl:String = "";
      
      private var _Handler_Camera:Cam;
      
      private var _effectLvl:int = 3;
      
      private var _playerDefaultKeys:Array;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _totalEffects:int;
      
      private var _stage:*;
      
      public function Options(param1:*, param2:OutputTrace)
      {
         _effectLvl = 3;
         _totalEffects = 10 + 3 * 70;
         _lastQualityLvl = "";
         super();
         _stage = param1;
         _Handler_Output = param2;
         _Handler_Keyboard = new InputKeyboard(_stage);
         _Handler_Keyboard.AddHandler(116,_Handler_Output.Show);
         _Handler_Keyboard.AddHandler(117,_Handler_Output.Hide);
         _Handler_Keyboard.AddHandler(123,ToggleFullscreen);
         _stage.quality = "HIGH";
         _stage.scaleMode = "noScale";
         _stage.addEventListener(Event.RESIZE,OnStageResize);
         _playerDefaultKeys = new Array([0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0]);
         SetDefaultP1Keys();
         SetDefaultP2Keys();
         LoadData();
         _Handler_Output.Trace("Options Created");
      }
      
      public function linkClick(param1:ContextMenuEvent) : void
      {
         var _loc2_:URLRequest = null;
         _loc2_ = new URLRequest("http://mythologicinteractive.com/");
         navigateToURL(_loc2_,"_blank");
      }
      
      public function set PlayerKeys(param1:Array) : void
      {
         _playerDefaultKeys = param1;
      }
      
      public function GetEffectLevel() : int
      {
         return _effectLvl;
      }
      
      public function ToggleEffectLevel(param1:int = -1) : void
      {
         _effectLvl += param1;
         if(_effectLvl < 1)
         {
            _effectLvl = 4;
         }
         if(_effectLvl > 4)
         {
            _effectLvl = 1;
         }
         _totalEffects = 10 + _effectLvl * 70;
         _Handler_Output.Trace("Effect Level: " + _effectLvl);
      }
      
      public function GetPlayerKeys() : Array
      {
         return _playerDefaultKeys;
      }
      
      public function LinkToCam(param1:Cam) : void
      {
         _Handler_Camera = param1;
      }
      
      public function SetDefaultP2Keys() : void
      {
         _playerDefaultKeys[1][0] = _Handler_Keyboard.GetKeyCode("W");
         _playerDefaultKeys[1][1] = _Handler_Keyboard.GetKeyCode("S");
         _playerDefaultKeys[1][2] = _Handler_Keyboard.GetKeyCode("A");
         _playerDefaultKeys[1][3] = _Handler_Keyboard.GetKeyCode("D");
         _playerDefaultKeys[1][4] = _Handler_Keyboard.GetKeyCode("1");
         _playerDefaultKeys[1][5] = _Handler_Keyboard.GetKeyCode("2");
         _playerDefaultKeys[1][6] = _Handler_Keyboard.GetKeyCode("3");
         _playerDefaultKeys[1][7] = _Handler_Keyboard.GetKeyCode("4");
         _playerDefaultKeys[1][8] = _Handler_Keyboard.GetKeyCode("W");
         _playerDefaultKeys[1][9] = _Handler_Keyboard.GetKeyCode("S");
         _playerDefaultKeys[1][10] = 0;
      }
      
      public function ToggleFullscreen() : void
      {
         if(_stage.displayState == StageDisplayState.FULL_SCREEN)
         {
            ExitFullscreen();
         }
         else
         {
            EnterFullscreen();
         }
      }
      
      public function GetStageQuality() : String
      {
         return _stage.quality;
      }
      
      public function GetTotalEffects() : int
      {
         return _totalEffects;
      }
      
      public function get PlayerKeys() : Array
      {
         return _playerDefaultKeys;
      }
      
      public function GetEffectQuality() : String
      {
         switch(_effectLvl)
         {
            case 1:
               return "LOW";
            case 2:
               return "MEDIUM";
            case 3:
               return "HIGH";
            case 4:
               return "BEST";
            default:
               return "LOW";
         }
      }
      
      public function ExitFullscreen() : void
      {
         _Handler_Output.Trace("Normal Mode");
         _stage.displayState = StageDisplayState.NORMAL;
      }
      
      public function ToggleGraphicQuality(param1:int = -1) : void
      {
         if(param1 < 0)
         {
            switch(_stage.quality)
            {
               case "HIGH":
                  _stage.quality = "MEDIUM";
                  break;
               case "MEDIUM":
                  _stage.quality = "LOW";
                  break;
               case "LOW":
                  _stage.quality = "HIGH";
            }
         }
         else
         {
            switch(_stage.quality)
            {
               case "HIGH":
                  _stage.quality = "LOW";
                  break;
               case "MEDIUM":
                  _stage.quality = "HIGH";
                  break;
               case "LOW":
                  _stage.quality = "MEDIUM";
            }
         }
      }
      
      public function CustomizedContextMenu() : ContextMenu
      {
         var _loc1_:ContextMenu = null;
         var _loc2_:ContextMenuItem = null;
         var _loc3_:ContextMenuItem = null;
         _loc1_ = new ContextMenu();
         _loc1_.hideBuiltInItems();
         _loc1_.builtInItems.quality = true;
         _loc2_ = new ContextMenuItem("Superfighters");
         _loc2_.enabled = false;
         _loc3_ = new ContextMenuItem("MythoLogic Interactive",true,true,true);
         _loc3_.addEventListener(ContextMenuEvent.MENU_ITEM_SELECT,linkClick);
         _loc1_.customItems.push(_loc3_);
         return _loc1_;
      }
      
      public function EnterFullscreen() : void
      {
         _stage.displayState = StageDisplayState.FULL_SCREEN;
         if(_stage.displayState != StageDisplayState.FULL_SCREEN)
         {
            _Handler_Output.Trace("<b>Error</b>: Can\'t Enter Fullscreen Mode. To allow full-screen, allowFullScreen must be true in the object/embed tags.");
         }
         else
         {
            _Handler_Output.Trace("Fullscreen Mode");
         }
      }
      
      private function LoadData() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         if(_loc1_.data.playerKeys != undefined)
         {
            _playerDefaultKeys = _loc1_.data.playerKeys;
         }
         if(_loc1_.data.graphicQuality != undefined)
         {
            _stage.quality = _loc1_.data.graphicQuality;
         }
         if(_loc1_.data.effectLevel != undefined)
         {
            _effectLvl = _loc1_.data.effectLevel;
         }
      }
      
      private function OnStageResize(param1:Event) : void
      {
         _Handler_Camera.SetScreenResulotion(_stage.stageWidth,_stage.stageHeight);
      }
      
      public function SetDefaultP1Keys() : void
      {
         _playerDefaultKeys[0][0] = _Handler_Keyboard.GetKeyCode("UP");
         _playerDefaultKeys[0][1] = _Handler_Keyboard.GetKeyCode("DOWN");
         _playerDefaultKeys[0][2] = _Handler_Keyboard.GetKeyCode("LEFT");
         _playerDefaultKeys[0][3] = _Handler_Keyboard.GetKeyCode("RIGHT");
         _playerDefaultKeys[0][4] = _Handler_Keyboard.GetKeyCode("N");
         _playerDefaultKeys[0][5] = _Handler_Keyboard.GetKeyCode("M");
         _playerDefaultKeys[0][6] = 188;
         _playerDefaultKeys[0][7] = 190;
         _playerDefaultKeys[0][8] = _Handler_Keyboard.GetKeyCode("UP");
         _playerDefaultKeys[0][9] = _Handler_Keyboard.GetKeyCode("DOWN");
         _playerDefaultKeys[0][10] = 0;
      }
      
      public function Update() : void
      {
         if(_stage.quality != _lastQualityLvl)
         {
            switch(_stage.quality)
            {
               case "HIGH":
                  _effectLvl = 3;
                  break;
               case "MEDIUM":
                  _effectLvl = 2;
                  break;
               case "LOW":
                  _effectLvl = 1;
                  break;
               case "BEST":
                  _effectLvl = 4;
                  break;
               default:
                  _effectLvl = 0;
            }
            _lastQualityLvl = _stage.quality;
         }
      }
      
      public function SaveData() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         _loc1_.data.playerKeys = _playerDefaultKeys;
         _loc1_.data.graphicQuality = _stage.quality;
         _loc1_.data.effectLevel = _effectLvl;
         _loc1_.flush();
      }
   }
}

