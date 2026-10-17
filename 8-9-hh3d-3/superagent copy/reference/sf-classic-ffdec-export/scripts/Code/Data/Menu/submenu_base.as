package Code.Data.Menu
{
   import Code.Handler.Sounds;
   import flash.display.*;
   
   public class submenu_base
   {
      protected var _canReturn:Boolean = false;
      
      protected var _marker_pos:int = 0;
      
      protected var _Handler_Sounds:Sounds;
      
      protected var _this:MovieClip;
      
      protected var _total_markers:int = 0;
      
      public function submenu_base()
      {
         _total_markers = 0;
         _marker_pos = 0;
         _canReturn = false;
         super();
      }
      
      public function get CanReturn() : Boolean
      {
         return _canReturn;
      }
      
      public function KeyPressed(param1:int) : void
      {
      }
      
      public function Show() : void
      {
         _this.visible = true;
      }
      
      public function Hide() : void
      {
         _this.visible = false;
      }
      
      public function UpdateMarker() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < _total_markers)
         {
            MovieClip(_this.getChildByName("marker_" + _loc1_)).visible = false;
            _loc1_++;
         }
         MovieClip(_this.getChildByName("marker_" + _marker_pos)).visible = true;
      }
      
      public function GetChoice() : String
      {
         return "";
      }
   }
}

