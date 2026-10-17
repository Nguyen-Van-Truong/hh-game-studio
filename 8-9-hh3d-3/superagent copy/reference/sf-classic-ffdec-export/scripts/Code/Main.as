package Code
{
   import Code.Data.*;
   import Code.Handler.*;
   import flash.display.*;
   
   public class Main extends MovieClip
   {
      private var _Handler_Output:OutputTrace;
      
      private var _Handler_Options:Options;
      
      private var _Handler_Sounds:Sounds;
      
      private var _this:*;
      
      private var _Handler_MenuMain:MenuMain;
      
      private var _Handler_GameMain:GameMain;
      
      private var _game_mc:MovieClip;
      
      private var _stage:*;
      
      public function Main(param1:*, param2:*)
      {
         var _loc3_:GameMainData = null;
         var _loc4_:MenuMainData = null;
         super();
         _stage = param1;
         _this = param2;
         _game_mc = new MovieClip();
         _stage.addChild(_game_mc);
         _Handler_Output = new OutputTrace(_stage);
         _Handler_Sounds = new Sounds(_Handler_Output);
         _Handler_Options = new Options(_stage,_Handler_Output);
         _this.contextMenu = _Handler_Options.CustomizedContextMenu();
         _loc3_ = new GameMainData();
         _loc3_.game_mc = _game_mc;
         _loc3_.stage_temp = _stage;
         _loc3_.Handler_Output = _Handler_Output;
         _loc3_.Handler_Options = _Handler_Options;
         _loc3_.Handler_Sounds = _Handler_Sounds;
         _Handler_GameMain = new GameMain(_loc3_);
         _loc4_ = new MenuMainData();
         _loc4_.game_mc = _game_mc;
         _loc4_.stage_temp = _stage;
         _loc4_.Handler_Output = _Handler_Output;
         _loc4_.Handler_GameMain = _Handler_GameMain;
         _loc4_.Handler_Sounds = _Handler_Sounds;
         _loc4_.Handler_Options = _Handler_Options;
         _Handler_MenuMain = new MenuMain(_loc4_);
         _Handler_GameMain.Handler_MenuMain = _Handler_MenuMain;
         _Handler_MenuMain.OpenMenu();
         _Handler_Output.Trace("Game Started Successfully");
         _Handler_Output.Trace("");
      }
   }
}

