package Code.Handler
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Box2D.Dynamics.Contacts.*;
   import Code.Box2D.Dynamics.Joints.*;
   import Code.Data.*;
   import Code.Data.Players.*;
   import Code.Data.Weapons.*;
   import Code.Particles.*;
   import flash.display.MovieClip;
   import flash.events.Event;
   import flash.events.FocusEvent;
   import flash.filters.*;
   import flash.geom.Point;
   import flash.net.SharedObject;
   import flash.ui.Keyboard;
   
   public class GameMain
   {
      public static var DEBUG_MODE:Boolean = false;
      
      private var _roundOver:Boolean;
      
      private var _ContactData:ContactData;
      
      private var _Handler_Portals:Portals;
      
      private var _tips:MovieClip;
      
      private var _Handler_Camera:Cam;
      
      internal var fullcolour:ColorMatrixFilter;
      
      private var _game_window:MovieClip;
      
      private var _victory_text:MovieClip;
      
      private var _last_bgNoiseFrame:int = 1;
      
      private var _Handler_Options:Options;
      
      private var _round_initialized:int;
      
      private var _box2D_speed:Number = 100;
      
      private var _Handler_Deconstructer:Deconstructer;
      
      private var _Handler_Mouse:InputMouse;
      
      private var _dynamic_mc:MovieClip;
      
      private var _Handler_Projectiles:Projectiles;
      
      private var _Handler_Sounds:Sounds;
      
      private var _Handler_Box2DMouse:Box2DMouse;
      
      private var _Handler_Players:PlayersKeeper;
      
      private var _static_objects_hitbox_mc:MovieClip;
      
      private var _countdown_mc:MovieClip;
      
      private var _player_speed:Number = 1;
      
      private var _shake_container:MovieClip;
      
      private var _Handler_WeaponSpawn:WeaponSpawn;
      
      private var _dynamic_gui_mc:MovieClip;
      
      private var _Handler_Slowmo:Slowmo;
      
      public var m_iterations:int = 20;
      
      private var _Handler_Weapons:Weapons;
      
      private var _static_players_hitbox_mc:MovieClip;
      
      private var _gameModeWinnerShown:Boolean;
      
      private var _object_shape_container_mc:MovieClip;
      
      private var _static_world_cloud_hitbox_mc:MovieClip;
      
      private var _static_objects_cloud_hitbox_mc:MovieClip;
      
      private var _static_ladder_hitbox_mc:MovieClip;
      
      private var _Handler_Fires:Fires;
      
      private var _Handler_Maps:Maps;
      
      private var _camera_speed:Number = 1;
      
      private var _Handler_Effects:Effects;
      
      private var _static_mc:MovieClip;
      
      private var _Handler_Shake:Shake;
      
      private var _score:Scoreboard;
      
      private var _Handler_Commands:CommandList;
      
      private var _tipsOver:Boolean;
      
      private var _bgNoise:MovieClip;
      
      public var m_world:b2World;
      
      private var _countdownOver:Boolean;
      
      private var _Handler_MenuMain:MenuMain;
      
      private var _countdown:int = 0;
      
      private var _Handler_ProjectilesUpdater:ProjectilesUpdater;
      
      private var _static_world_hitbox_mc:MovieClip;
      
      private var _game_mc:MovieClip;
      
      internal var greyscale:ColorMatrixFilter;
      
      internal var colour:Array;
      
      internal var nocolour:Array;
      
      private var _press_space_indication:MovieClip;
      
      private var _bodyIndex:int;
      
      public var m_timeStep:Number = 0.03333333333333333;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _prevGameData:NewGameData;
      
      private var _scoreSurvival:ScoreboardSurvival;
      
      private var _Handler_Explosions:Explosions;
      
      private var _Handler_Output:OutputTrace;
      
      private var _Handler_BasicOverlays:BasicOverlays;
      
      private var _stage:*;
      
      public function GameMain(param1:GameMainData)
      {
         _box2D_speed = 100;
         _camera_speed = 1;
         _player_speed = 1;
         _countdown = 0;
         _last_bgNoiseFrame = 1;
         nocolour = [0.213,0.715,0.072,0,0,0.213,0.715,0.072,0,0,0.213,0.715,0.072,0,0,0,0,0,1,0];
         colour = [1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,1,0];
         greyscale = new ColorMatrixFilter(nocolour);
         fullcolour = new ColorMatrixFilter(colour);
         m_iterations = 20;
         m_timeStep = 1 / 30;
         super();
         _game_mc = param1.game_mc;
         _stage = param1.stage_temp;
         _Handler_Output = param1.Handler_Output;
         _Handler_Options = param1.Handler_Options;
         _Handler_Sounds = param1.Handler_Sounds;
         _Handler_Sounds.ChangeVolume(1);
         _Handler_Weapons = new Weapons(_Handler_Output);
         _Handler_Projectiles = new Projectiles(_Handler_Output);
         _Handler_Maps = new Maps(_Handler_Output);
         _Handler_Mouse = new InputMouse(_stage);
         _Handler_Commands = new CommandList(_Handler_Output,DEBUG_MODE);
         _tips = new tips();
         _tips.gotoAndStop(1);
         _press_space_indication = new press_space();
         _victory_text = new round_winner();
         _Handler_Output.Trace("Main Game Initialized");
      }
      
      private function ShowVictoryText() : void
      {
         _victory_text.visible = true;
      }
      
      private function ShowStatic() : void
      {
         _dynamic_mc.alpha = 0.2;
         _object_shape_container_mc.visible = true;
         _static_mc.visible = true;
      }
      
      public function StartNewGame(param1:NewGameData) : void
      {
         var _static_players_area_mc:MovieClip = null;
         var slomo_rectangle:MovieClip = null;
         var gui_holder_mc:MovieClip = null;
         var level_mc:levels = null;
         var mc_effects_behind:MovieClip = null;
         var mc_objects:MovieClip = null;
         var mc_scrap:MovieClip = null;
         var mc_players:MovieClip = null;
         var mc_weapons:MovieClip = null;
         var mc_effects:MovieClip = null;
         var mc_effects2:MovieClip = null;
         var mc_projectiles:MovieClip = null;
         var mc_lazers:MovieClip = null;
         var level_front_mc:levels_front = null;
         var pData:PlayersKeeperData = null;
         var eData:ExplosionData = null;
         var puData:ProjectilesUpdaterData = null;
         var p:int = 0;
         var p2:int = 0;
         var gameData:NewGameData = param1;
         _prevGameData = gameData;
         _Handler_Keyboard = new InputKeyboard(_stage);
         _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("P"),_Handler_Options.ToggleEffectLevel);
         _static_mc = new MovieClip();
         _static_mc.name = "STATIC";
         _static_world_hitbox_mc = new MovieClip();
         _static_world_hitbox_mc.name = "WORLD_HITBOX";
         _static_world_cloud_hitbox_mc = new MovieClip();
         _static_world_cloud_hitbox_mc.name = "WORLD_CLOUD_HITBOX";
         _static_objects_cloud_hitbox_mc = new MovieClip();
         _static_objects_cloud_hitbox_mc.name = "OBJECTS_CLOUD_HITBOX";
         _static_ladder_hitbox_mc = new MovieClip();
         _static_ladder_hitbox_mc.name = "LADDER_HITBOX";
         _static_objects_hitbox_mc = new MovieClip();
         _static_objects_hitbox_mc.name = "OBJECTS_HITBOX";
         _static_players_hitbox_mc = new MovieClip();
         _static_players_hitbox_mc.name = "PLAYERS_HITBOX";
         _static_players_area_mc = new MovieClip();
         _static_players_area_mc.name = "PLAYERS_AREA";
         _static_mc.addChild(_static_ladder_hitbox_mc);
         _static_mc.addChild(_static_players_hitbox_mc);
         _static_mc.addChild(_static_players_area_mc);
         _static_world_hitbox_mc.addChild(_static_objects_hitbox_mc);
         _static_mc.addChild(_static_world_hitbox_mc);
         _static_world_cloud_hitbox_mc.addChild(_static_objects_cloud_hitbox_mc);
         _static_mc.addChild(_static_world_cloud_hitbox_mc);
         _dynamic_mc = new MovieClip();
         _dynamic_mc.name = "DYNAMIC";
         _object_shape_container_mc = new MovieClip();
         _object_shape_container_mc.name = "ALLOBJECTS";
         HideStatic();
         _game_mc.addChild(_static_mc);
         _game_mc.addChild(_object_shape_container_mc);
         _shake_container = new MovieClip();
         _shake_container.name = "DYNAMICHOLDER";
         _shake_container.addChild(_dynamic_mc);
         _game_window = new MovieClip();
         _game_window.name = "GAME_WINDOW";
         _game_window.addChild(_shake_container);
         _game_mc.addChild(_game_window);
         slomo_rectangle = new MovieClip();
         _game_mc.addChild(slomo_rectangle);
         gui_holder_mc = new gui_holder();
         gui_holder_mc.name = "GUI_HOLDER";
         _game_mc.addChild(gui_holder_mc);
         if(gameData.pSetupData.totalPlayers > 4)
         {
            gui_holder_mc.gotoAndStop(2);
         }
         else
         {
            gui_holder_mc.gotoAndStop(1);
         }
         _game_mc.addChild(_press_space_indication);
         _game_mc.addChild(_victory_text);
         HideSpaceIndication();
         HideVictoryText();
         level_mc = new levels();
         level_mc.name = "LEVEL";
         level_mc.gotoAndStop(gameData.lvl);
         _dynamic_mc.addChild(level_mc);
         mc_effects_behind = new MovieClip();
         mc_effects_behind.name = "EFFECTSBEHIND";
         _dynamic_mc.addChild(mc_effects_behind);
         mc_objects = new MovieClip();
         mc_objects.name = "OBJECTS";
         _dynamic_mc.addChild(mc_objects);
         mc_scrap = new MovieClip();
         mc_scrap.name = "SCRAP";
         _dynamic_mc.addChild(mc_scrap);
         mc_players = new MovieClip();
         mc_players.name = "PLAYERS";
         _dynamic_mc.addChild(mc_players);
         mc_weapons = new MovieClip();
         mc_weapons.name = "WEAPONS";
         _dynamic_mc.addChild(mc_weapons);
         mc_effects = new MovieClip();
         mc_effects.name = "EFFECTS";
         _dynamic_mc.addChild(mc_effects);
         mc_effects2 = new MovieClip();
         mc_effects2.name = "EFFECTS2";
         _dynamic_mc.addChild(mc_effects2);
         mc_projectiles = new MovieClip();
         mc_projectiles.name = "PROJECTILES";
         _dynamic_mc.addChild(mc_projectiles);
         mc_lazers = new MovieClip();
         mc_lazers.name = "LAZERS";
         _dynamic_mc.addChild(mc_lazers);
         level_front_mc = new levels_front();
         level_front_mc.name = "LEVEL_FRONT";
         level_front_mc.gotoAndStop(gameData.lvl);
         _dynamic_mc.addChild(level_front_mc);
         _dynamic_gui_mc = new MovieClip();
         _dynamic_gui_mc.name = "GUI";
         _game_window.addChild(_dynamic_gui_mc);
         _Handler_BasicOverlays = new BasicOverlays(mc_lazers);
         _Handler_Explosions = new Explosions();
         _Handler_Deconstructer = new Deconstructer();
         _Handler_Effects = new Effects(_Handler_Output,MovieClip(_dynamic_mc.getChildByName("EFFECTSBEHIND")),MovieClip(_dynamic_mc.getChildByName("EFFECTS")),_Handler_Options,_Handler_Maps);
         _Handler_Slowmo = new Slowmo(_Handler_Output,_Handler_Effects,_Handler_Sounds,slomo_rectangle,_stage);
         _Handler_Shake = new Shake(_Handler_Output,_shake_container);
         _Handler_Maps.UpdateMCs(_static_mc,_dynamic_mc,_object_shape_container_mc);
         _Handler_Maps.UpdateHandlers(_Handler_Effects,_Handler_Explosions,_Handler_Sounds,_Handler_BasicOverlays);
         _ContactData = new ContactData();
         _ContactData.Handler_Output = _Handler_Output;
         _ContactData.Handler_Effects = _Handler_Effects;
         _ContactData.Handler_Sounds = _Handler_Sounds;
         _ContactData.Handler_Deconstructer = _Handler_Deconstructer;
         _Handler_Maps.ConstructContactListener(_ContactData);
         m_world = _Handler_Maps.GetMap(gameData.lvl);
         _Handler_WeaponSpawn = new WeaponSpawn(_Handler_Output,_Handler_Maps,_Handler_Weapons);
         _Handler_ProjectilesUpdater = new ProjectilesUpdater();
         _Handler_Deconstructer.Setb2World = m_world;
         _Handler_Box2DMouse = new Box2DMouse(_Handler_Mouse,m_world,_dynamic_mc);
         pData = new PlayersKeeperData();
         pData.stg = _stage;
         pData.game_mc = _game_mc;
         pData.Handler_Projectiles = _Handler_ProjectilesUpdater;
         pData.Handler_Output = _Handler_Output;
         pData.Handler_Keyboard = _Handler_Keyboard;
         pData.Handler_Effects = _Handler_Effects;
         pData.Handler_Maps = _Handler_Maps;
         pData.Handler_Shake = _Handler_Shake;
         pData.Handler_Sounds = _Handler_Sounds;
         pData.Handler_Slowmo = _Handler_Slowmo;
         pData.pathGrid = _Handler_Maps.GetPathGrid(gameData.lvl);
         pData.rangedStartWeapon = _Handler_Weapons.Pistol;
         pData.throwableStartWeapon = _Handler_Weapons.Grenades;
         pData.meleeStartWeapon = null;
         pData.defaultMeleeWeapon = _Handler_Weapons.Fists;
         pData.m_world = m_world;
         pData.pSetupData = gameData.pSetupData;
         pData.pSetupData.playerSpawnPositions = _Handler_Maps.GetPlayerSpawnPositions(gameData.lvl);
         _Handler_Players = new PlayersKeeper(pData);
         _Handler_Maps.LinkPlayers(_Handler_Players);
         _Handler_Maps.LinkWeapons(_Handler_Weapons);
         _Handler_Camera = new Cam(_stage,_dynamic_mc,gui_holder_mc,_Handler_MenuMain.MenuOverlay,_Handler_Output,_Handler_Players);
         _Handler_Camera.SetMapArea(_Handler_Maps.GetMinimumMapArea(gameData.lvl));
         _Handler_Options.LinkToCam(_Handler_Camera);
         _Handler_Players.LinkToCam(_Handler_Camera);
         _Handler_Portals = new Portals(m_world,_Handler_Players,_Handler_Output);
         _Handler_Portals.SetMapPortals(_Handler_Maps.GetMapPortals(gameData.lvl));
         eData = new ExplosionData();
         eData.Handler_Output = _Handler_Output;
         eData.Handler_Camera = _Handler_Camera;
         eData.Handler_Shake = _Handler_Shake;
         eData.Handler_Players = _Handler_Players;
         eData.Handler_Effects = _Handler_Effects;
         eData.Handler_Sounds = _Handler_Sounds;
         eData.Handler_Slowmo = _Handler_Slowmo;
         eData.static_mc = _static_mc;
         eData.dynamic_mc = _dynamic_mc;
         eData.m_world = m_world;
         _Handler_Explosions.BuildClass(eData);
         _Handler_Fires = new Fires(eData,_object_shape_container_mc);
         _Handler_Explosions.LinkToFire(_Handler_Fires);
         _Handler_Players.LinkToFire(_Handler_Fires);
         _Handler_Maps.Handler_WorldItems.LinkToFire(_Handler_Fires);
         puData = new ProjectilesUpdaterData();
         puData.Handler_Output = _Handler_Output;
         puData.Handler_Projectiles = _Handler_Projectiles;
         puData.Handler_Camera = _Handler_Camera;
         puData.Handler_Players = _Handler_Players;
         puData.Handler_Effects = _Handler_Effects;
         puData.Handler_Sounds = _Handler_Sounds;
         puData.Handler_Explosions = _Handler_Explosions;
         puData.static_mc = _static_mc;
         puData.dynamic_mc = _dynamic_mc;
         puData.object_shape_container_mc = _object_shape_container_mc;
         puData.m_world = m_world;
         _Handler_ProjectilesUpdater.BuildClass(puData);
         _stage.addEventListener(Event.ENTER_FRAME,Update,false,0,true);
         m_world.DrawDebugData();
         m_world.FallAsleepBody = function(param1:b2Body):void
         {
            _Handler_Portals.CheckBodyInsidePortal(param1);
         };
         _Handler_Commands.LinkHandlers(_Handler_Maps,_Handler_Box2DMouse,_Handler_Keyboard,_Handler_Effects,_Handler_Sounds,_Handler_Explosions,_Handler_Fires,_Handler_Weapons,_Handler_Players);
         _Handler_Commands.LinkFunctions(Restart);
         _Handler_Maps.GetPathGrid().UpdateHandlers(_Handler_Fires,m_world);
         _countdownOver = true;
         _bgNoise = null;
         if(gameData.isSurvival)
         {
            _countdown_mc = new get_ready_fight();
            _countdown_mc.x = 400;
            _countdown_mc.y = 300;
            _countdown_mc.scaleX = 4;
            _countdown_mc.scaleY = 4;
            _game_window.addChild(_countdown_mc);
            _countdown = _countdown_mc.totalFrames - 1;
            _Handler_Sounds.InMenu = false;
            _game_window.visible = false;
            _round_initialized = 2;
            _countdownOver = false;
            _Handler_Keyboard.AddHandler(27,BackToMainMenu);
            _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("SPACE"),SpacePressed);
            _scoreSurvival = new ScoreboardSurvival(_game_mc);
            p = 0;
            while(p < _Handler_Players.Players.length)
            {
               _scoreSurvival.AddPlayerToScore(_Handler_Players.Players[p]);
               p++;
            }
            _scoreSurvival.Build();
            gui_holder_mc.addChild(_scoreSurvival.MC);
            _scoreSurvival.Hide();
         }
         else if(gameData.isTutorial)
         {
            _countdown = 0;
            _Handler_Sounds.InMenu = false;
            _game_window.visible = false;
            _round_initialized = 2;
            _Handler_Keyboard.AddHandler(27,BackToMainMenu);
            _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("SPACE"),SpacePressed);
            _Handler_Players.ActivatePlayers();
            _Handler_Camera.ShowAll = true;
         }
         else if(!gameData.isMenuDemo)
         {
            _countdown_mc = new get_ready_fight();
            _countdown_mc.x = 400;
            _countdown_mc.y = 300;
            _countdown_mc.scaleX = 4;
            _countdown_mc.scaleY = 4;
            _game_window.addChild(_countdown_mc);
            _countdown = _countdown_mc.totalFrames - 1;
            _Handler_Sounds.InMenu = false;
            _game_window.visible = false;
            _round_initialized = 2;
            _countdownOver = false;
            _Handler_Keyboard.AddHandler(27,BackToMainMenu);
            _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("SPACE"),SpacePressed);
            if(_prevGameData.newScore)
            {
               _prevGameData.newScore = false;
               _score = new Scoreboard(_game_mc,_prevGameData.gameMode);
               p2 = 0;
               while(p2 < _Handler_Players.Players.length)
               {
                  _score.AddPlayerToScore(_Handler_Players.Players[p2]);
                  p2++;
               }
               _score.Build();
            }
            gui_holder_mc.addChild(_score.MC);
            _score.Hide();
         }
         else
         {
            _countdown = 0;
            _game_window.visible = false;
            _round_initialized = 2;
            _Handler_Sounds.InMenu = true;
            _Handler_Players.ActivatePlayers();
            _bgNoise = new bg_noise();
            _bgNoise.EFFECT_MC.gotoAndPlay(_last_bgNoiseFrame);
            _game_window.addChild(_bgNoise);
            gui_holder_mc.visible = false;
            _game_window.removeChild(_dynamic_gui_mc);
            _game_window.addChild(_dynamic_gui_mc);
         }
         if(gameData.showTips)
         {
            _tipsOver = false;
            _game_mc.addChild(_tips);
            _tips.gotoAndStop(1 + Math.floor(Math.random() * (_tips.totalFrames - 0.001)));
            _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("LEFT"),function():*
            {
               ChangeTips(-1);
            });
            _Handler_Keyboard.AddHandler(_Handler_Keyboard.GetKeyCode("RIGHT"),function():*
            {
               ChangeTips(1);
            });
            _countdown_mc.gotoAndStop(1);
            _countdown_mc.visible = false;
            ShowSpaceIndication();
         }
         else
         {
            _tipsOver = true;
         }
         _roundOver = false;
         _gameModeWinnerShown = false;
         _game_window.scaleX = gameData.gameScale;
         _game_window.scaleY = gameData.gameScale;
         _game_window.x = gameData.gamePosX;
         _game_window.y = gameData.gamePosY;
         _Handler_Output.Trace("New Game Created");
      }
      
      private function ChangeTips(param1:int) : void
      {
         var _loc2_:int = 0;
         if(!_tipsOver)
         {
            _loc2_ = _tips.currentFrame + param1;
            if(_loc2_ <= 0)
            {
               _loc2_ = _tips.totalFrames;
            }
            if(_loc2_ > _tips.totalFrames)
            {
               _loc2_ = 1;
            }
            _tips.gotoAndStop(_loc2_);
         }
      }
      
      public function Stop() : void
      {
         _Handler_Output.Trace("");
         _Handler_Output.Trace("Stopping Game...");
         _stage.removeEventListener(Event.ENTER_FRAME,Update);
         _Handler_Keyboard.Deconstruct();
         _Handler_Effects.Stop();
         _Handler_Maps.Stop();
         _Handler_Slowmo.Stop();
         _Handler_Fires.Stop();
         _Handler_Players.Stop();
         ClearMC(_game_mc);
         _Handler_Output.Trace("Game Stopped");
      }
      
      private function ShowSpaceIndication() : void
      {
         _press_space_indication.visible = true;
         _press_space_indication.gotoAndPlay(1);
      }
      
      private function HideSpaceIndication() : void
      {
         _press_space_indication.visible = false;
      }
      
      private function SetBlackWhite(param1:MovieClip) : void
      {
         param1.filters = [greyscale];
      }
      
      private function SpacePressed() : void
      {
         var _loc1_:ScoreboardTeam = null;
         var _loc2_:SharedObject = null;
         if(!_tipsOver)
         {
            _game_mc.removeChild(_tips);
            _tipsOver = true;
            _countdown_mc.visible = true;
            _countdown_mc.gotoAndPlay(1);
            HideSpaceIndication();
            return;
         }
         if(_roundOver)
         {
            if(_prevGameData.isSurvival)
            {
               if(!_gameModeWinnerShown)
               {
                  _Handler_Keyboard.RemoveHandler(Keyboard.TAB);
                  TabPressed();
                  _gameModeWinnerShown = true;
                  _Handler_Sounds.PlaySound("GROOVY",0,0);
               }
               else
               {
                  BackToMainMenu();
               }
            }
            else if(_prevGameData.isTutorial)
            {
               BackToMainMenu();
            }
            else if(_score.GameFinished)
            {
               if(!_gameModeWinnerShown)
               {
                  _Handler_Keyboard.RemoveHandler(Keyboard.TAB);
                  TabPressed();
                  _loc1_ = _score.GetTeamWinner();
                  if(_loc1_ == null)
                  {
                     _victory_text.gotoAndStop("DRAW");
                  }
                  else if(_loc1_.Team > 0)
                  {
                     _victory_text.gotoAndStop(_loc1_.Team);
                  }
                  else if(_loc1_.FirstPlayer.PlayerNr == 0)
                  {
                     _victory_text.gotoAndStop("PLAYER_1");
                  }
                  else if(_loc1_.FirstPlayer.PlayerNr == 1 && !_loc1_.FirstPlayer.Bot)
                  {
                     _victory_text.gotoAndStop("PLAYER_2");
                  }
                  else
                  {
                     _victory_text.gotoAndStop("COM");
                  }
                  ShowVictoryText();
                  _gameModeWinnerShown = true;
                  _Handler_Sounds.PlaySound("GROOVY",0,0);
                  if(_prevGameData.challengeNr != -1)
                  {
                     if(_loc1_.Team == 1)
                     {
                        _loc2_ = SharedObject.getLocal("superfightersData_v1.0");
                        if(_loc2_.data.stageLevelsFinished != undefined)
                        {
                           _loc2_.data.stageLevelsFinished[_prevGameData.challengeNr] = true;
                           _loc2_.flush();
                        }
                     }
                  }
               }
               else
               {
                  BackToMainMenu();
               }
            }
            else
            {
               HideVictoryText();
               Restart();
            }
         }
      }
      
      private function HideStatic() : void
      {
         _dynamic_mc.alpha = 1;
         _object_shape_container_mc.visible = false;
         _static_mc.visible = false;
      }
      
      private function ClearMC(param1:MovieClip) : void
      {
         var _loc2_:int = 0;
         _loc2_ = param1.numChildren;
         while(_loc2_--)
         {
            param1.removeChildAt(_loc2_);
         }
      }
      
      private function HideVictoryText() : void
      {
         _victory_text.visible = false;
      }
      
      public function set Handler_MenuMain(param1:MenuMain) : void
      {
         _Handler_MenuMain = param1;
      }
      
      private function BackToMainMenu() : void
      {
         _stage.removeEventListener(Event.ENTER_FRAME,Update);
         Stop();
         _Handler_MenuMain.OpenMenu();
      }
      
      private function Unfocus(param1:FocusEvent) : void
      {
         _stage.focus = null;
      }
      
      private function TabReleased() : void
      {
         _Handler_Slowmo.GamePaused = false;
         if(_prevGameData.isSurvival)
         {
            _scoreSurvival.Hide();
         }
         else
         {
            _score.Hide();
         }
      }
      
      private function Update(param1:Event) : void
      {
         var _loc2_:b2Body = null;
         var _loc3_:int = 0;
         if(_round_initialized <= 0)
         {
            if(_countdown > 0 && _tipsOver)
            {
               --_countdown;
               if(_countdown <= 0)
               {
                  _countdown_mc.stop();
                  _game_window.removeChild(_countdown_mc);
               }
               else if(_countdown == 15)
               {
                  _countdownOver = true;
                  _Handler_Players.ActivatePlayers();
                  if(!_prevGameData.isMenuDemo)
                  {
                     _Handler_Players.SetStartImmunity();
                     _Handler_Keyboard.AddHandler(Keyboard.TAB,TabPressed,TabReleased);
                  }
               }
            }
         }
         if(DEBUG_MODE)
         {
            _Handler_Box2DMouse.UpdateMouseWorld(new Point(_dynamic_mc.x * _prevGameData.gameScale + _prevGameData.gamePosX,_dynamic_mc.y * _prevGameData.gameScale + _prevGameData.gamePosY),_dynamic_mc.scaleX * _prevGameData.gameScale,m_timeStep);
            _Handler_Box2DMouse.MouseDrag();
         }
         _Handler_Slowmo.Update();
         m_timeStep = 1 / (30 / _Handler_Slowmo.Slowmotion);
         _ContactData.game_speed = _Handler_Slowmo.Slowmotion;
         _Handler_Maps.Handler_WorldItems.Lock();
         m_world.Step(m_timeStep,m_iterations);
         _Handler_Maps.Handler_WorldItems.Unlock();
         _bodyIndex = 0;
         while(_bodyIndex < m_world.AllDynamicObjectList.length)
         {
            _loc2_ = m_world.AllDynamicObjectList[_bodyIndex];
            _loc2_.m_userData.x = _loc2_.GetPosition().x * 30;
            _loc2_.m_userData.y = _loc2_.GetPosition().y * 30;
            _loc2_.m_userData.rotation = _loc2_.GetAngle() * (180 / Math.PI);
            if(_loc2_.m_userData.objectData.DrawShapeMC)
            {
               _loc2_.m_userData.objectData.ShapeMC.x = _loc2_.GetPosition().x * 30;
               _loc2_.m_userData.objectData.ShapeMC.y = _loc2_.GetPosition().y * 30;
               _loc2_.m_userData.objectData.ShapeMC.rotation = _loc2_.GetAngle() * (180 / Math.PI);
            }
            if(!_loc2_.m_userData.objectData.InPortal)
            {
               if(Boolean(_loc2_.m_userData.objectData.DrawHitBox) || Boolean(_loc2_.m_userData.objectData.DrawCloudBox))
               {
                  _loc2_.m_userData.objectData.CollisionMC.x = _loc2_.m_userData.objectData.ShapeMC.x;
                  _loc2_.m_userData.objectData.CollisionMC.y = _loc2_.m_userData.objectData.ShapeMC.y;
                  _loc2_.m_userData.objectData.CollisionMC.rotation = _loc2_.m_userData.objectData.ShapeMC.rotation;
               }
            }
            if(_loc2_.IsFrozen())
            {
               _Handler_Output.Trace("Object " + _loc2_.GetUserData().IDNumber + " out of bounds. Removing object");
               m_world.RemoveObjectFromLists(_loc2_);
               _loc2_.m_userData.destroyed = true;
               _loc2_.m_userData.objectData.HP = 0;
               if(Boolean(_loc2_.m_userData.objectData.DrawHitBox) || Boolean(_loc2_.m_userData.objectData.DrawCloudBox))
               {
                  _loc2_.m_userData.objectData.CollisionMC.parent.removeChild(_loc2_.m_userData.objectData.CollisionMC);
               }
               if(_loc2_.m_userData.objectData.DrawShapeMC)
               {
                  _loc2_.m_userData.objectData.ShapeMC.parent.removeChild(_loc2_.m_userData.objectData.ShapeMC);
               }
               _loc2_.m_userData.parent.removeChild(_loc2_.m_userData);
               m_world.DestroyBody(_loc2_);
            }
            else
            {
               _loc2_.m_userData.objectData.UpdateFunction(_loc2_,_Handler_Slowmo.Slowmotion);
            }
            _bodyIndex += 1;
         }
         _Handler_Maps.UpdatePathGrid();
         _Handler_Shake.Update(_Handler_Slowmo.Slowmotion);
         if(_countdownOver)
         {
            _Handler_WeaponSpawn.Update(_Handler_Slowmo.Slowmotion);
         }
         _Handler_Players.Update(_Handler_Slowmo.Slowmotion);
         _Handler_ProjectilesUpdater.Update(_Handler_Slowmo.Slowmotion);
         _Handler_Fires.Update(_Handler_Slowmo.Slowmotion);
         _Handler_Explosions.Update(_Handler_Slowmo.Slowmotion);
         _Handler_Deconstructer.Update();
         _Handler_Portals.Update();
         _Handler_Camera.Update(_camera_speed);
         _Handler_Maps.Update(_Handler_Slowmo.Slowmotion);
         _Handler_BasicOverlays.Update();
         _Handler_Sounds.Update(_Handler_Slowmo.Slowmotion);
         _dynamic_gui_mc.x = _dynamic_mc.x;
         _dynamic_gui_mc.y = _dynamic_mc.y;
         _dynamic_gui_mc.scaleX = _dynamic_mc.scaleX;
         _dynamic_gui_mc.scaleY = _dynamic_mc.scaleY;
         _dynamic_gui_mc.x += _shake_container.x * (1 / _dynamic_mc.scaleX);
         _dynamic_gui_mc.y += _shake_container.y * (1 / _dynamic_mc.scaleY);
         if(_bgNoise != null)
         {
            _bgNoise.scaleX = 1 / _game_window.scaleX;
            _bgNoise.scaleY = 1 / _game_window.scaleY;
            _bgNoise.x = -_game_window.x * _bgNoise.scaleX;
            _bgNoise.y = -_game_window.y * _bgNoise.scaleY;
            _bgNoise.x -= 400 * (_Handler_MenuMain.MenuOverlay.scaleX - 1) * _bgNoise.scaleX;
            _bgNoise.y -= 300 * (_Handler_MenuMain.MenuOverlay.scaleY - 1) * _bgNoise.scaleY;
            _bgNoise.scaleX *= _Handler_MenuMain.MenuOverlay.scaleX;
            _bgNoise.scaleY *= _Handler_MenuMain.MenuOverlay.scaleY;
            _last_bgNoiseFrame = _bgNoise.EFFECT_MC.currentFrame;
         }
         if(DEBUG_MODE)
         {
            if(_Handler_Keyboard.KeyIsDown(16))
            {
               _Handler_Commands.PrintMenu();
            }
         }
         if(_Handler_Players.RoundOver && !_roundOver)
         {
            if(_prevGameData.isTutorial || _prevGameData.isSurvival)
            {
               if(_Handler_Maps.MapOver)
               {
                  _roundOver = true;
                  if(_prevGameData.isSurvival)
                  {
                     ShowSpaceIndication();
                  }
               }
               return;
            }
            _roundOver = true;
            if(_prevGameData.isMenuDemo)
            {
               Stop();
               _Handler_MenuMain.StartMenuGame();
            }
            else
            {
               _score.RoundsFinished += 1;
               _loc3_ = _Handler_Players.GetTeamWinner();
               switch(_loc3_)
               {
                  case -1:
                     _victory_text.gotoAndStop("DRAW");
                     break;
                  case 0:
                     _score.ScoreTeam(_Handler_Players.GetSoloWinner());
                     switch(_Handler_Players.GetPlayerNrWinner())
                     {
                        case 0:
                           _victory_text.gotoAndStop("PLAYER_1");
                           break;
                        case 1:
                           if(_Handler_Players.Players[_Handler_Players.GetPlayerNrWinner()].Bot)
                           {
                              _victory_text.gotoAndStop("COM");
                           }
                           else
                           {
                              _victory_text.gotoAndStop("PLAYER_2");
                           }
                           break;
                        default:
                           _victory_text.gotoAndStop("COM");
                     }
                     break;
                  default:
                     _score.ScoreTeam(_Handler_Players.GetTeamWinner());
                     _victory_text.gotoAndStop(_Handler_Players.GetTeamWinner());
               }
               ShowVictoryText();
               ShowSpaceIndication();
            }
         }
         if(_round_initialized > 0)
         {
            --_round_initialized;
            if(_round_initialized <= 0)
            {
               _game_window.visible = true;
            }
         }
      }
      
      private function TabPressed() : void
      {
         _Handler_Slowmo.GamePaused = true;
         if(_prevGameData.isSurvival)
         {
            _scoreSurvival.Update(_Handler_Maps.SurvivalTime);
            _scoreSurvival.Show();
         }
         else
         {
            _score.Update();
            _score.Show();
         }
      }
      
      private function Restart(param1:Boolean = false) : void
      {
         Stop();
         _Handler_Output.Trace("");
         _Handler_Output.Trace("Restarting Game...");
         if(param1)
         {
            _prevGameData.lvl += 1;
            if(_prevGameData.lvl > 5)
            {
               _prevGameData.lvl = 1;
            }
         }
         _prevGameData.showTips = false;
         StartNewGame(_prevGameData);
      }
   }
}

