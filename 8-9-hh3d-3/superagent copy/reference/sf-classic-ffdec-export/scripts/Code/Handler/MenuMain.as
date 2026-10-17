package Code.Handler
{
   import Code.Data.*;
   import Code.Data.Menu.*;
   import Code.Data.Players.*;
   import flash.display.*;
   import flash.events.*;
   import flash.net.*;
   
   public class MenuMain
   {
      private var _game_mc:MovieClip;
      
      private var _Handler_GameMain:GameMain;
      
      private var _delay_timer:Number;
      
      private var _curr_menu:submenu_base;
      
      private var _menu_history:Array;
      
      private var _menu_overlay:MovieClip;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _lastChoise:String = "";
      
      private var _Handler_Options:Options;
      
      private var _Handler_Output:OutputTrace;
      
      private var _Handler_Sounds:Sounds;
      
      private var _stage:*;
      
      public function MenuMain(param1:MenuMainData)
      {
         _lastChoise = "";
         super();
         _game_mc = param1.game_mc;
         _stage = param1.stage_temp;
         _Handler_Output = param1.Handler_Output;
         _Handler_GameMain = param1.Handler_GameMain;
         _Handler_Sounds = param1.Handler_Sounds;
         _Handler_Options = param1.Handler_Options;
         _menu_overlay = new main_menu_overlay();
         _menu_history = new Array();
         _menu_overlay.link_1.addEventListener(MouseEvent.CLICK,Link1);
         _menu_overlay.link_2.addEventListener(MouseEvent.CLICK,Link2);
         _menu_overlay.link_3.addEventListener(MouseEvent.CLICK,Link3);
         _menu_overlay.link_4.addEventListener(MouseEvent.CLICK,Link4);
      }
      
      private function StartTutorial() : void
      {
         _stage.removeChild(_menu_overlay);
         _Handler_Keyboard.Deconstruct();
         _Handler_GameMain.Stop();
         StartTutorialGame();
      }
      
      private function CheckPrevMenu() : void
      {
         if(_menu_history.length > 0)
         {
            if(_curr_menu.CanReturn)
            {
               _curr_menu.Hide();
               _curr_menu = _menu_history[_menu_history.length - 1];
               _curr_menu.Show();
               _menu_history.splice(_menu_history.length - 1,1);
               if(_lastChoise != "delete_progress" && _lastChoise != "not_delete_progress")
               {
                  if(_menu_history.length == 4 && _menu_history[3].NoBots == 0)
                  {
                     KeyPressed(MenuKey.KEY_BACKSPACE);
                  }
                  else if(_lastChoise != "reset")
                  {
                     _Handler_Sounds.PlayMightySound("CANCEL");
                  }
               }
               if(_menu_history.length == 1)
               {
                  _menu_history[0].Show();
               }
            }
         }
      }
      
      public function UserInpuOver() : void
      {
         _stage.removeChild(_menu_overlay);
         _Handler_Keyboard.Deconstruct();
         _Handler_GameMain.Stop();
         StartNewGame();
      }
      
      public function StartNewGame() : void
      {
         var _loc1_:PlayerSetupData = null;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         var _loc5_:NewGameData = null;
         _loc1_ = new PlayerSetupData();
         _loc1_.ot = _Handler_Output;
         _loc1_.keys = _Handler_Options.GetPlayerKeys();
         _loc1_.totalPlayers = _menu_history[0].Players + _menu_history[3].NoBots;
         _loc1_.ai = new Array(1,0,0,0,0,0,0,0);
         _loc1_.characters = new Array(_menu_history[2].PlayerPlateOne.Character,0,0,0,0,0,0,0);
         _loc1_.teams = new Array(_menu_history[2].PlayerPlateOne.Team,0,0,0,0,0,0,0);
         if(_menu_history[0].Players == 2)
         {
            _loc1_.ai[1] = 2;
            _loc1_.characters[1] = _menu_history[2].PlayerPlateTwo.Character;
            _loc1_.teams[1] = _menu_history[2].PlayerPlateTwo.Team;
         }
         _loc1_.aiDifficulty = new Array(0,0,0,0,0,0,0,0);
         _loc2_ = 0;
         _loc3_ = int(_menu_history[0].Players);
         while(_loc3_ < _loc1_.totalPlayers)
         {
            _loc1_.characters[_loc3_] = _menu_history[4].BotPlates[_loc2_].Character;
            _loc1_.teams[_loc3_] = _menu_history[4].BotPlates[_loc2_].Team;
            _loc1_.aiDifficulty[_loc3_] = _menu_history[4].BotPlates[_loc2_].Difficulty;
            _loc2_++;
            _loc3_++;
         }
         _loc4_ = 0;
         while(_loc4_ < _loc1_.characters.length)
         {
            if(_loc1_.characters[_loc4_] == 0)
            {
               _loc1_.characters[_loc4_] = GetRndChar();
            }
            _loc4_++;
         }
         _loc5_ = new NewGameData();
         _loc5_.lvl = _menu_history[_menu_history.length - 1].Level;
         _loc5_.pSetupData = _loc1_;
         _loc5_.gamePosX = 0;
         if(_loc1_.totalPlayers > 4)
         {
            _loc5_.gameScale = 1;
            _loc5_.gamePosY = 75;
         }
         else
         {
            _loc5_.gameScale = 1.05;
            _loc5_.gamePosY = 75 / 2;
         }
         _loc5_.challengeNr = -1;
         _loc5_.isMenuDemo = false;
         _loc5_.isTutorial = false;
         _loc5_.showTips = true;
         _loc5_.newScore = true;
         _loc5_.gameMode = _menu_history[_menu_history.length - 1].Mode;
         _Handler_GameMain.StartNewGame(_loc5_);
      }
      
      public function get MenuOverlay() : MovieClip
      {
         return _menu_overlay;
      }
      
      public function StartTutorialGame() : void
      {
         var _loc1_:PlayerSetupData = null;
         var _loc2_:NewGameData = null;
         _loc1_ = new PlayerSetupData();
         _loc1_.ot = _Handler_Output;
         _loc1_.keys = _Handler_Options.GetPlayerKeys();
         _loc1_.characters = new Array(1,2,3,3,3,3,3,3);
         _loc1_.totalPlayers = 1;
         _loc1_.teams = new Array(0,0,0,0,0,0,0,0);
         _loc1_.ai = new Array(1,2,0,0,0,0,0,0);
         _loc1_.aiDifficulty = new Array(3,3,3,3,3,3,3,3);
         _loc2_ = new NewGameData();
         _loc2_.lvl = 1;
         _loc2_.pSetupData = _loc1_;
         _loc2_.gameScale = 1;
         _loc2_.gamePosX = 0;
         _loc2_.gamePosY = 0;
         _loc2_.challengeNr = -1;
         _loc2_.isMenuDemo = false;
         _loc2_.isTutorial = true;
         _loc2_.showTips = false;
         _loc2_.newScore = true;
         _loc2_.gameMode = 1;
         _Handler_GameMain.StartNewGame(_loc2_);
      }
      
      private function Link1(param1:MouseEvent) : void
      {
         var _loc2_:URLRequest = null;
         _loc2_ = new URLRequest("http://johanhjarpe.newgrounds.com");
         navigateToURL(_loc2_,"_blank");
      }
      
      private function DeleteProgress() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         _loc1_.data.stageLevelsFinished = [false,false,false,false,false,false,false,false,false,false,false,false];
         _loc1_.flush();
      }
      
      private function Link3(param1:MouseEvent) : void
      {
         var _loc2_:URLRequest = null;
         _loc2_ = new URLRequest("http://hzlancer.newgrounds.com/");
         navigateToURL(_loc2_,"_blank");
      }
      
      private function Show(param1:Array) : void
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < param1.length)
         {
            MovieClip(param1[_loc2_]).visible = true;
            _loc2_++;
         }
      }
      
      private function Link2(param1:MouseEvent) : void
      {
         var _loc2_:URLRequest = null;
         _loc2_ = new URLRequest("http://gurt.newgrounds.com/");
         navigateToURL(_loc2_,"_blank");
      }
      
      private function GetRndChar() : int
      {
         return PlayerCharacter.GetRandomCharacter();
      }
      
      private function Link4(param1:MouseEvent) : void
      {
         var _loc2_:URLRequest = null;
         _loc2_ = new URLRequest("http://mythologicinteractive.com/");
         navigateToURL(_loc2_,"_blank");
      }
      
      private function KeyPressed(param1:int) : void
      {
         _curr_menu.KeyPressed(param1);
         switch(param1)
         {
            case MenuKey.KEY_ENTER:
               CheckNextMenu();
               break;
            case MenuKey.KEY_BACKSPACE:
               CheckPrevMenu();
         }
      }
      
      public function StartMenuGame() : void
      {
         var _loc1_:PlayerSetupData = null;
         var _loc2_:int = 0;
         var _loc3_:NewGameData = null;
         _loc1_ = new PlayerSetupData();
         _loc1_.ot = _Handler_Output;
         _loc1_.characters = new Array(GetRndChar(),GetRndChar(),GetRndChar(),GetRndChar(),GetRndChar(),GetRndChar(),GetRndChar(),GetRndChar());
         _loc2_ = Math.floor(Math.random() * 4.9999);
         switch(_loc2_)
         {
            case 0:
               _loc1_.totalPlayers = 3;
               _loc1_.teams = new Array(0,0,0,0,0,0,0,0);
               break;
            case 1:
               _loc1_.totalPlayers = 4;
               _loc1_.teams = new Array(1,1,2,2,0,0,0,0);
               break;
            case 2:
               _loc1_.totalPlayers = 5;
               _loc1_.teams = new Array(0,0,0,4,4,0,0,0);
               break;
            case 3:
               _loc1_.totalPlayers = 6;
               _loc1_.teams = new Array(1,1,2,2,3,3,4,4);
               break;
            default:
               _loc1_.characters = new Array(1,2,3,3,3,3,3,3);
               _loc1_.totalPlayers = 2;
               _loc1_.teams = new Array(0,0,0,0,0,0,0,0);
         }
         _loc1_.ai = new Array(0,0,0,0,0,0,0,0);
         _loc1_.aiDifficulty = new Array(3,3,3,3,3,3,3,3);
         _loc3_ = new NewGameData();
         _loc3_.lvl = 2 + Math.floor(Math.random() * 3.999);
         _loc3_.pSetupData = _loc1_;
         _loc3_.gameScale = 0.95;
         _loc3_.gamePosX = 80;
         _loc3_.gamePosY = 110;
         _loc3_.challengeNr = -1;
         _loc3_.isMenuDemo = true;
         _loc3_.isTutorial = false;
         _loc3_.showTips = false;
         _loc3_.newScore = true;
         _loc3_.gameMode = 1;
         _Handler_GameMain.StartNewGame(_loc3_);
      }
      
      private function Hide(param1:Array) : void
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < param1.length)
         {
            MovieClip(param1[_loc2_]).visible = false;
            _loc2_++;
         }
      }
      
      public function OpenMenu() : void
      {
         _Handler_Keyboard = new InputKeyboard(_stage);
         StartMenuGame();
         if(_menu_history.length > 0)
         {
            _curr_menu.Show();
         }
         else
         {
            _menu_history = new Array();
            Hide([_menu_overlay.vs_1p_setup,_menu_overlay.vs_2p_setup,_menu_overlay.map_selection,_menu_overlay.mode_selection,_menu_overlay.no_bots,_menu_overlay.bot_7_setup,_menu_overlay.bot_6_setup,_menu_overlay.set_up,_menu_overlay.set_up_main,_menu_overlay.challenge_selection,_menu_overlay.confirm_delete]);
            _curr_menu = new first_choise(_menu_overlay.first_choise,_Handler_Sounds);
         }
         _stage.addChild(_menu_overlay);
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("UP"),function():void
         {
            KeyPressed(MenuKey.KEY_UP);
         });
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("DOWN"),function():void
         {
            KeyPressed(MenuKey.KEY_DOWN);
         });
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("LEFT"),function():void
         {
            KeyPressed(MenuKey.KEY_LEFT);
         });
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("RIGHT"),function():void
         {
            KeyPressed(MenuKey.KEY_RIGHT);
         });
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("ENTER"),function():void
         {
            KeyPressed(MenuKey.KEY_ENTER);
         });
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("SPACE"),function():void
         {
            KeyPressed(MenuKey.KEY_ENTER);
         });
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("BACKSPACE"),function():void
         {
            KeyPressed(MenuKey.KEY_BACKSPACE);
         });
         _Handler_Keyboard.AddHandler(27,function():void
         {
            KeyPressed(MenuKey.KEY_BACKSPACE);
         });
      }
      
      public function StartChallengeGame() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Array = null;
         var _loc3_:int = 0;
         var _loc4_:PlayerSetupData = null;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         var _loc7_:int = 0;
         var _loc8_:NewGameData = null;
         _loc1_ = _menu_history[3].SelectedChallenge - 1;
         _loc2_ = Challenges.CHALLENGE[_menu_history[0].Players - 1][_loc1_];
         _loc3_ = _loc2_.length - 1;
         _loc4_ = new PlayerSetupData();
         _loc4_.ot = _Handler_Output;
         _loc4_.keys = _Handler_Options.GetPlayerKeys();
         _loc4_.totalPlayers = _menu_history[0].Players + _loc3_;
         _loc4_.ai = new Array(1,0,0,0,0,0,0,0);
         _loc4_.characters = new Array(_menu_history[2].PlayerPlateOne.Character,0,0,0,0,0,0,0);
         _loc4_.teams = new Array(_menu_history[2].PlayerPlateOne.Team,0,0,0,0,0,0,0);
         if(_menu_history[0].Players == 2)
         {
            _loc4_.ai[1] = 2;
            _loc4_.characters[1] = _menu_history[2].PlayerPlateTwo.Character;
            _loc4_.teams[1] = _menu_history[2].PlayerPlateTwo.Team;
         }
         _loc4_.aiDifficulty = new Array(0,0,0,0,0,0,0,0);
         _loc5_ = 1;
         _loc6_ = int(_menu_history[0].Players);
         while(_loc6_ < _loc4_.totalPlayers)
         {
            _loc4_.characters[_loc6_] = 0;
            _loc4_.teams[_loc6_] = 2;
            _loc4_.aiDifficulty[_loc6_] = _loc2_[_loc5_];
            _loc5_++;
            _loc6_++;
         }
         if(_loc1_ == 11)
         {
            _loc4_.characters[_menu_history[0].Players] = PlayerCharacter.FUNNYMAN;
         }
         _loc7_ = 0;
         while(_loc7_ < _loc4_.characters.length)
         {
            if(_loc4_.characters[_loc7_] == 0)
            {
               _loc4_.characters[_loc7_] = GetRndChar();
            }
            _loc7_++;
         }
         _loc8_ = new NewGameData();
         _loc8_.lvl = _loc2_[0];
         _loc8_.pSetupData = _loc4_;
         _loc8_.gamePosX = 0;
         if(_loc4_.totalPlayers > 4)
         {
            _loc8_.gameScale = 1;
            _loc8_.gamePosY = 75;
         }
         else
         {
            _loc8_.gameScale = 1.05;
            _loc8_.gamePosY = 75 / 2;
         }
         _loc8_.challengeNr = _loc1_;
         _loc8_.isMenuDemo = false;
         _loc8_.isTutorial = false;
         _loc8_.showTips = true;
         _loc8_.newScore = true;
         _loc8_.gameMode = 5;
         _Handler_GameMain.StartNewGame(_loc8_);
      }
      
      private function StartChallenge() : void
      {
         _stage.removeChild(_menu_overlay);
         _Handler_Keyboard.Deconstruct();
         _Handler_GameMain.Stop();
         StartChallengeGame();
      }
      
      private function OpenInstructions() : void
      {
         var targetURL:URLRequest = null;
         try
         {
            targetURL = new URLRequest("http://mythologicinteractive.com/?page_id=21#instructions");
            navigateToURL(targetURL,"_blank");
         }
         catch(e:Error)
         {
         }
      }
      
      private function CheckNextMenu() : void
      {
         var _loc1_:String = null;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         _loc1_ = _curr_menu.GetChoice();
         if(_loc1_ != "")
         {
            _lastChoise = _loc1_;
            _menu_history.push(_curr_menu);
            switch(_loc1_)
            {
               case "mode_selection":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new mode_selection(_menu_overlay.mode_selection,_Handler_Sounds);
                  _curr_menu.Show();
                  break;
               case "vs_mode":
                  _menu_history[0].Hide();
                  _menu_history[1].Hide();
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new vs_player_setup(MovieClip(_menu_overlay.getChildByName("vs_" + _menu_history[0].Players + "p_setup")),_Handler_Sounds,_menu_history[0].Players,0);
                  _curr_menu.Show();
                  break;
               case "stage_mode":
                  _menu_history[0].Hide();
                  _menu_history[1].Hide();
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new vs_player_setup(MovieClip(_menu_overlay.getChildByName("vs_" + _menu_history[0].Players + "p_setup")),_Handler_Sounds,_menu_history[0].Players,1);
                  _curr_menu.Show();
                  break;
               case "challenge_selection":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new challenge_selection(MovieClip(_menu_overlay.getChildByName("challenge_selection")),_Handler_Sounds,_Handler_Keyboard,_menu_history[0].Players);
                  _curr_menu.Show();
                  break;
               case "confirm_delete":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new confirm_delete(MovieClip(_menu_overlay.getChildByName("confirm_delete")),_Handler_Sounds);
                  _curr_menu.Show();
                  break;
               case "delete_progress":
                  _Handler_Sounds.PlayMightySound("CANCEL");
                  DeleteProgress();
                  KeyPressed(MenuKey.KEY_BACKSPACE);
                  KeyPressed(MenuKey.KEY_BACKSPACE);
                  _lastChoise = "";
                  break;
               case "not_delete_progress":
                  _Handler_Sounds.PlayMightySound("CANCEL");
                  KeyPressed(MenuKey.KEY_BACKSPACE);
                  KeyPressed(MenuKey.KEY_BACKSPACE);
                  _lastChoise = "";
                  break;
               case "no_bots":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _loc2_ = 0;
                  if(_menu_history[0].Players == 1)
                  {
                     _loc2_ = 1;
                  }
                  else if(_menu_history[2].PlayerPlateOne.Team == _menu_history[2].PlayerPlateTwo.Team && _menu_history[2].PlayerPlateOne.Team != 0)
                  {
                     _loc2_ = 1;
                  }
                  _loc3_ = 8 - _menu_history[0].Players;
                  _curr_menu = new no_bots(MovieClip(_menu_overlay.getChildByName("no_bots")),_Handler_Sounds,_loc2_,_loc3_);
                  _curr_menu.Show();
                  break;
               case "prepare_bots":
                  _loc4_ = 0;
                  if(_menu_history[0].Players == 1)
                  {
                     _loc4_ = int(_menu_history[2].PlayerPlateOne.Team);
                  }
                  else if(_menu_history[2].PlayerPlateOne.Team == _menu_history[2].PlayerPlateTwo.Team)
                  {
                     _loc4_ = int(_menu_history[2].PlayerPlateOne.Team);
                  }
                  if(_menu_history[0].Players == 1)
                  {
                     _curr_menu = new bot_setup(MovieClip(_menu_overlay.getChildByName("bot_7_setup")),_Handler_Sounds,_menu_history[3].NoBots,_loc4_);
                  }
                  else
                  {
                     _curr_menu = new bot_setup(MovieClip(_menu_overlay.getChildByName("bot_6_setup")),_Handler_Sounds,_menu_history[3].NoBots,_loc4_);
                  }
                  _curr_menu.Show();
                  if(_menu_history[3].NoBots == 0)
                  {
                     KeyPressed(MenuKey.KEY_ENTER);
                  }
                  else
                  {
                     _Handler_Sounds.PlayMightySound("ACCEPT");
                  }
                  break;
               case "map_selection":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new map_selection(MovieClip(_menu_overlay.getChildByName("map_selection")),_Handler_Sounds);
                  _curr_menu.Show();
                  break;
               case "reset":
                  while(_menu_history.length > 2)
                  {
                     KeyPressed(MenuKey.KEY_BACKSPACE);
                  }
                  _Handler_Sounds.PlayMightySound("CANCEL");
                  _lastChoise = "";
                  break;
               case "fight":
                  UserInpuOver();
                  _menu_history.splice(_menu_history.length - 1,1);
                  break;
               case "tutorial":
                  StartTutorial();
                  _menu_history.splice(_menu_history.length - 1,1);
                  OpenInstructions();
                  break;
               case "start_challenge":
                  StartChallenge();
                  _menu_history.splice(_menu_history.length - 1,1);
                  break;
               case "set_up":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new set_up(MovieClip(_menu_overlay.getChildByName("set_up")),_Handler_Sounds,_Handler_Keyboard,_Handler_Options);
                  _curr_menu.Show();
                  break;
               case "set_up_main":
                  _Handler_Sounds.PlayMightySound("ACCEPT");
                  _curr_menu = new set_up_main(MovieClip(_menu_overlay.getChildByName("set_up_main")),_Handler_Sounds,_Handler_Keyboard,_Handler_Options);
                  _curr_menu.Show();
            }
         }
      }
   }
}

