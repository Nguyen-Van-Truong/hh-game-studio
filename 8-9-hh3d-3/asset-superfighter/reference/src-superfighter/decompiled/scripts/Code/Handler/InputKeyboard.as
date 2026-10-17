package Code.Handler
{
   import flash.events.*;
   
   public class InputKeyboard
   {
      private var _keyBuffer:Array;
      
      public var KeyDownFunction:Function;
      
      public var KeyDownFunctionRepeatable:Function;
      
      private var _functionBuffer:Array;
      
      private var _modifierBuffer:Array;
      
      public var KeyUpFunction:Function;
      
      private var _stage:*;
      
      public function InputKeyboard(param1:*)
      {
         _keyBuffer = new Array();
         _modifierBuffer = new Array();
         _functionBuffer = new Array();
         super();
         _stage = param1;
         _stage.addEventListener(KeyboardEvent.KEY_DOWN,keyDownHandler);
         _stage.addEventListener(KeyboardEvent.KEY_UP,keyUpHandler);
      }
      
      public function GetCharFromCode(param1:int) : String
      {
         var _loc2_:String = null;
         switch(param1)
         {
            case 32:
               return "SPACE";
            case 38:
               return "UP";
            case 40:
               return "DOWN";
            case 37:
               return "LEFT";
            case 39:
               return "RIGHT";
            case 16:
               return "SHIFT";
            case 17:
               return "CTRL";
            case 20:
               return "CAPS";
            case 13:
               return "ENTER";
            case 8:
               return "BACKSPACE";
            case 27:
               return "ESCAPE";
            case 188:
               return ",";
            case 190:
               return ".";
            default:
               _loc2_ = String.fromCharCode(param1);
               if(param1 >= 127)
               {
                  _loc2_ = "C" + param1;
               }
               return _loc2_;
         }
      }
      
      private function RemoveKeyFromBuffer(param1:int) : void
      {
         var _loc2_:* = undefined;
         _loc2_ = 0;
         while(_loc2_ < _keyBuffer.length)
         {
            if(_keyBuffer[_loc2_] == param1)
            {
               _keyBuffer.splice(_loc2_,1);
            }
            _loc2_++;
         }
      }
      
      public function RemoveHandler(param1:int, param2:int = -1) : void
      {
         var _loc3_:* = undefined;
         _loc3_ = 0;
         while(_loc3_ < _functionBuffer.length)
         {
            if(param1 == _functionBuffer[_loc3_][0] && _functionBuffer[_loc3_][3] == param2)
            {
               _functionBuffer.splice(_loc3_,1);
            }
            _loc3_++;
         }
         UpdateModifierBuffer();
      }
      
      public function AddHandler(param1:int, param2:Function, param3:Function = undefined) : void
      {
         if(param2 == null)
         {
            param2 = Blank;
         }
         if(param3 == null)
         {
            param3 = Blank;
         }
         _functionBuffer.push([param1,param2,param3,-1]);
      }
      
      public function KeyIsDown(param1:int) : Boolean
      {
         var _loc2_:* = undefined;
         _loc2_ = 0;
         while(_loc2_ < _keyBuffer.length)
         {
            if(_keyBuffer[_loc2_] == param1)
            {
               return true;
            }
            _loc2_++;
         }
         return false;
      }
      
      private function keyUpHandler(param1:KeyboardEvent) : void
      {
         RemoveKeyFromBuffer(param1.keyCode);
         CheckKeyFunction(param1.keyCode,2);
         if(KeyUpFunction != null)
         {
            KeyUpFunction(param1);
         }
      }
      
      public function TraceKeys() : void
      {
         var _loc1_:String = null;
         var _loc2_:* = undefined;
         _loc1_ = "Keys Down: ";
         _loc2_ = 0;
         while(_loc2_ < _keyBuffer.length)
         {
            _loc1_ += _keyBuffer[_loc2_] + ", ";
            _loc2_++;
         }
      }
      
      public function GetKeyCode(param1:String) : int
      {
         switch(param1.toUpperCase())
         {
            case "SPACEBAR":
            case "SPACE":
               return 32;
            case "UP":
               return 38;
            case "DOWN":
               return 40;
            case "LEFT":
               return 37;
            case "RIGHT":
               return 39;
            case "SHIFT":
               return 16;
            case "CTRL":
               return 17;
            case "CAPS":
            case "CAPSLOCK":
               return 20;
            case "ENTER":
               return 13;
            case "BACKSPACE":
               return 8;
            case "ESCAPE":
               return 27;
            default:
               return param1.charCodeAt(0);
         }
      }
      
      public function RemoveModifier(param1:int, param2:int) : void
      {
         var _loc3_:* = undefined;
         _loc3_ = 0;
         while(_loc3_ < _functionBuffer.length)
         {
            if(param1 == _functionBuffer[_loc3_][0] && _functionBuffer[_loc3_][3] == param2)
            {
               _functionBuffer[_loc3_][3] = -1;
               UpdateModifierBuffer();
            }
            _loc3_++;
         }
      }
      
      private function CheckKeyFunction(param1:int, param2:int) : void
      {
         var _loc3_:* = undefined;
         _loc3_ = 0;
         while(_loc3_ < _functionBuffer.length)
         {
            if(param1 == _functionBuffer[_loc3_][0])
            {
               if(_functionBuffer[_loc3_][3] == GetModifierPressed() || KeyIsDown(_functionBuffer[_loc3_][3]) || param2 != 1)
               {
                  _functionBuffer[_loc3_][param2]();
               }
            }
            _loc3_++;
         }
      }
      
      private function UpdateModifierBuffer() : void
      {
         var _loc1_:* = undefined;
         _modifierBuffer = new Array();
         _loc1_ = 0;
         while(_loc1_ < _functionBuffer.length)
         {
            if(_functionBuffer[_loc1_][3] != -1)
            {
               AddModifierToBuffer(_functionBuffer[_loc1_][3]);
            }
            _loc1_++;
         }
      }
      
      public function Deconstruct() : void
      {
         _stage.removeEventListener(KeyboardEvent.KEY_DOWN,keyDownHandler);
         _stage.removeEventListener(KeyboardEvent.KEY_UP,keyUpHandler);
      }
      
      private function keyDownHandler(param1:KeyboardEvent) : void
      {
         if(KeyDownFunctionRepeatable != null)
         {
            KeyDownFunctionRepeatable(param1);
         }
         if(KeyIsDown(param1.keyCode) == false)
         {
            _keyBuffer.push(param1.keyCode);
            CheckKeyFunction(param1.keyCode,1);
            if(KeyDownFunction != null)
            {
               KeyDownFunction(param1);
            }
         }
      }
      
      private function Blank() : void
      {
      }
      
      private function GetModifierPressed() : int
      {
         var _loc1_:* = undefined;
         var _loc2_:* = undefined;
         _loc1_ = 0;
         while(_loc1_ < _modifierBuffer.length)
         {
            _loc2_ = 0;
            while(_loc2_ < _keyBuffer.length)
            {
               if(_modifierBuffer[_loc1_] == _keyBuffer[_loc2_])
               {
                  return _modifierBuffer[_loc1_];
               }
               _loc2_++;
            }
            _loc1_++;
         }
         return -1;
      }
      
      public function AddModifier(param1:int = -1) : void
      {
         _functionBuffer[_functionBuffer.length - 1][3] = param1;
         UpdateModifierBuffer();
      }
      
      private function AddModifierToBuffer(param1:int) : void
      {
         var _loc2_:Boolean = false;
         var _loc3_:* = undefined;
         _loc2_ = true;
         _loc3_ = 0;
         while(_loc3_ < _modifierBuffer.length)
         {
            if(_modifierBuffer[_loc3_] == param1)
            {
               _loc2_ = false;
            }
            _loc3_++;
         }
         if(_loc2_)
         {
            _modifierBuffer.push(param1);
         }
      }
   }
}

