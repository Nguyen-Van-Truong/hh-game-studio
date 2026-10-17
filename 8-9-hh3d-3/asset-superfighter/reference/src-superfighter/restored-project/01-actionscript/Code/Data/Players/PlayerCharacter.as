package Code.Data.Players
{
   import fl.motion.Color;
   import flash.display.MovieClip;
   import flash.geom.ColorTransform;
   import flash.net.SharedObject;
   
   public class PlayerCharacter
   {
      public static const RANDOM:int = 0;
      
      public static const JOHNNY:int = 1;
      
      public static const BORIS:int = 2;
      
      public static const AGENT:int = 3;
      
      public static const BILLY:int = 4;
      
      public static const SCOTT:int = 5;
      
      public static const FUNNYMAN:int = 6;
      
      public static const MAC:int = 7;
      
      public static const JEFF:int = 8;
      
      public static const TOTAL_CHARACTERS:int = 8;
      
      public static const BRIGHTNESS:Number = 0.05;
      
      public function PlayerCharacter()
      {
         super();
      }
      
      public static function CharacterAvailable(param1:int) : Boolean
      {
         var _loc2_:SharedObject = null;
         var _loc3_:Array = null;
         var _loc4_:int = 0;
         if(param1 == FUNNYMAN)
         {
            _loc2_ = SharedObject.getLocal("superfightersData_v1.0");
            if(_loc2_.data.stageLevelsFinished != undefined)
            {
               _loc3_ = _loc2_.data.stageLevelsFinished;
               _loc4_ = 0;
               while(_loc4_ < _loc3_.length)
               {
                  if(!_loc3_[_loc4_])
                  {
                     return false;
                  }
                  _loc4_++;
               }
               return true;
            }
            return false;
         }
         return true;
      }
      
      public static function GetRandomCharacter() : int
      {
         var _loc1_:int = 0;
         _loc1_ = Math.floor(1 + Math.random() * (PlayerCharacter.TOTAL_CHARACTERS - 0.001));
         while(_loc1_ == FUNNYMAN)
         {
            _loc1_ = Math.floor(1 + Math.random() * (PlayerCharacter.TOTAL_CHARACTERS - 0.001));
         }
         return _loc1_;
      }
      
      public static function Get(param1:int) : MovieClip
      {
         var _loc2_:MovieClip = null;
         var _loc3_:Color = null;
         var _loc4_:ColorTransform = null;
         switch(param1)
         {
            case JOHNNY:
               _loc2_ = new player_johnny();
               break;
            case BORIS:
               _loc2_ = new player_boris();
               break;
            case AGENT:
               _loc2_ = new player_agent();
               break;
            case BILLY:
               _loc2_ = new player_billy();
               break;
            case SCOTT:
               _loc2_ = new player_scott();
               break;
            case FUNNYMAN:
               _loc2_ = new player_funnyman();
               break;
            case MAC:
               _loc2_ = new player_mac();
               break;
            case JEFF:
               _loc2_ = new player_jeff();
               break;
            default:
               _loc2_ = new player_boris();
               (_loc4_ = _loc2_.transform.colorTransform).color = 0;
               _loc4_.alphaMultiplier = 0.5;
               _loc2_.transform.colorTransform = _loc4_;
         }
         _loc3_ = new Color();
         _loc3_.brightness = BRIGHTNESS;
         _loc2_.transform.colorTransform = _loc3_;
         return _loc2_;
      }
   }
}

