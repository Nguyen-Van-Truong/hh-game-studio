package Code.Handler
{
   import Code.Box2D.Dynamics.b2World;
   import Code.Data.Players.Player;
   import Code.Data.Players.PlayerAreaData;
   import Code.Data.Players.PlayerBars;
   import Code.Data.Players.PlayerSetupData;
   import Code.Data.Players.PlayersKeeperData;
   import flash.display.MovieClip;
   import flash.geom.Point;
   import flash.geom.Rectangle;
   
   public class PlayersKeeper
   {
      private var _roundOverTimer:Number = 36;
      
      private var _roundOver:Boolean = false;
      
      private var gui_holder_mc:MovieClip;
      
      private var _Handler_Fires:Fires;
      
      private var _Handler_Maps:Maps;
      
      private var _Handler_Effects:Effects;
      
      private var _characters:Array;
      
      private var _Handler_Shake:Shake;
      
      private var _cameraUpdateTimer:Number = 12;
      
      private var _Handler_Camera:Cam;
      
      private var _cameraBounds:Array;
      
      private var _playerSetupData:PlayerSetupData;
      
      private var _RecalculateCamArea:Function;
      
      private var _MapArea:Rectangle;
      
      private var _lastCoveredPosition:Point;
      
      private var _Handler_ProjectilesUpdater:ProjectilesUpdater;
      
      private var _Handler_Sounds:Sounds;
      
      private var m_world:b2World;
      
      private var _game_mc:MovieClip;
      
      private var plrData:PlayersKeeperData;
      
      private var _playerSpawnPositions:Array;
      
      private var _players_left:Array;
      
      private var _Handler_Slowmo:Slowmo;
      
      private var _solo_nr_winner:int = -1;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _team_winner:int = -1;
      
      private var _pathGrid:PathGrid;
      
      private var _players:Array;
      
      private var _Handler_Output:OutputTrace;
      
      private var _playersInitialized:Boolean = false;
      
      private var _stage:*;
      
      public function PlayersKeeper(param1:PlayersKeeperData)
      {
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         _cameraUpdateTimer = 12;
         _roundOverTimer = 24 * 1.5;
         _players = new Array();
         _lastCoveredPosition = new Point(0,0);
         _roundOver = false;
         _team_winner = -1;
         _solo_nr_winner = -1;
         _playersInitialized = false;
         super();
         plrData = param1;
         _stage = plrData.stg;
         m_world = plrData.m_world;
         _game_mc = plrData.game_mc;
         _playerSetupData = plrData.pSetupData;
         _pathGrid = plrData.pathGrid;
         _pathGrid.LinkPlayers(_players);
         gui_holder_mc = MovieClip(_game_mc.getChildByName("GUI_HOLDER"));
         gui_holder_mc.player_1.visible = false;
         gui_holder_mc.player_2.visible = false;
         gui_holder_mc.com_no_players.visible = false;
         gui_holder_mc.com_0.visible = false;
         gui_holder_mc.com_1.visible = false;
         gui_holder_mc.com_2.visible = false;
         gui_holder_mc.com_3.visible = false;
         gui_holder_mc.com_4.visible = false;
         gui_holder_mc.com_5.visible = false;
         gui_holder_mc.com_6.visible = false;
         _Handler_Output = plrData.Handler_Output;
         _Handler_Keyboard = plrData.Handler_Keyboard;
         _Handler_Shake = plrData.Handler_Shake;
         _Handler_Effects = plrData.Handler_Effects;
         _Handler_ProjectilesUpdater = plrData.Handler_Projectiles;
         _Handler_Maps = plrData.Handler_Maps;
         _Handler_Sounds = plrData.Handler_Sounds;
         _Handler_Slowmo = plrData.Handler_Slowmo;
         _playerSpawnPositions = new Array();
         _loc2_ = 0;
         while(_loc2_ < _playerSetupData.playerSpawnPositions.length)
         {
            _playerSpawnPositions.push(_playerSetupData.playerSpawnPositions[_loc2_]);
            _loc2_++;
         }
         _loc3_ = -1;
         _loc4_ = 0;
         while(_loc4_ < _playerSetupData.totalPlayers)
         {
            ConstructPlayer(_loc4_,_playerSetupData.characters[_loc4_],_playerSetupData.teams[_loc4_]);
            if(_playerSetupData.ai[_loc4_] != 0)
            {
               _players[_loc4_].SetControls(_Handler_Keyboard,_playerSetupData.keys[_loc4_]);
               _players[_loc4_].SetGUI(MovieClip(gui_holder_mc.getChildByName("player_" + _playerSetupData.ai[_loc4_])));
               _players[_loc4_].SetSign(_playerSetupData.ai[_loc4_]);
               _loc3_++;
            }
            else
            {
               _players[_loc4_].SetAI(_playerSetupData.aiDifficulty[_loc4_]);
               if(_loc3_ == -1)
               {
                  _players[_loc4_].SetGUI(MovieClip(gui_holder_mc.getChildByName("com_no_players")));
               }
               else
               {
                  _players[_loc4_].SetGUI(MovieClip(gui_holder_mc.getChildByName("com_" + _loc3_)));
               }
               _players[_loc4_].SetSign(PlayerBars.PLAYER_COM);
               _loc3_++;
            }
            _players[_loc4_].GiveStartItems(plrData.rangedStartWeapon.Copy(),plrData.throwableStartWeapon.Copy());
            _players[_loc4_].GiveDefaultMelee(plrData.defaultMeleeWeapon.Copy());
            _players[_loc4_].UpdateGUI();
            _loc4_++;
         }
         _players_left = new Array(false,false,false,false,false);
      }
      
      public function AddBot(param1:int, param2:int, param3:int) : Player
      {
         var _loc4_:Array = null;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         var _loc7_:MovieClip = null;
         _loc4_ = _Handler_Maps.GetPlayerSpawnPositions();
         _playerSetupData.playerSpawnPositions = new Array();
         _playerSpawnPositions = new Array();
         _loc5_ = 0;
         while(_loc5_ < _loc4_.length)
         {
            _playerSetupData.playerSpawnPositions.push(_loc4_[_loc5_]);
            _playerSpawnPositions.push(_loc4_[_loc5_]);
            _loc5_++;
         }
         _loc6_ = int(_players.length);
         ConstructPlayer(_loc6_,param1,param2);
         _players[_loc6_].NoGUI();
         _players[_loc6_].SetAI(param3);
         _loc7_ = MovieClip(gui_holder_mc.getChildByName("com_0"));
         _players[_loc6_].SetGUI(_loc7_);
         _loc7_.visible = false;
         _players[_loc6_].SetSign(PlayerBars.PLAYER_COM);
         _players[_loc6_].GiveStartItems(plrData.rangedStartWeapon.Copy(),plrData.throwableStartWeapon.Copy());
         _players[_loc6_].GiveDefaultMelee(plrData.defaultMeleeWeapon.Copy());
         _players[_loc6_].Initialize(new PlayerAreaData(_MapArea));
         _players[_loc6_].LinkToFire(_Handler_Fires);
         _players[_loc6_].Activate();
         RecalculateCamArea();
         return _players[_loc6_];
      }
      
      public function GetCamArea() : Rectangle
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         var _loc6_:Number = NaN;
         var _loc7_:* = undefined;
         var _loc8_:Rectangle = null;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         var _loc12_:* = undefined;
         var _loc13_:Number = NaN;
         var _loc14_:Number = NaN;
         _loc5_ = 15;
         _loc6_ = 30;
         if(_players.length > 0)
         {
            _loc12_ = 0;
            while(_loc12_ < _players.length)
            {
               if(!_players[_loc12_].CameraIgnore)
               {
                  _lastCoveredPosition.x = _players[_loc12_].PosX();
                  _lastCoveredPosition.y = _players[_loc12_].PosY();
               }
               _loc12_++;
            }
         }
         _loc3_ = _lastCoveredPosition.x - _loc5_;
         _loc4_ = _lastCoveredPosition.x + _loc5_;
         _loc1_ = _lastCoveredPosition.y - _loc6_;
         _loc2_ = _lastCoveredPosition.y;
         _loc7_ = 0;
         while(_loc7_ < _players.length)
         {
            if(!_players[_loc7_].CameraIgnore)
            {
               if(_players[_loc7_].PosX() + _loc5_ > _loc4_)
               {
                  _loc4_ = _players[_loc7_].PosX() + _loc5_;
               }
               if(_players[_loc7_].PosX() - _loc5_ < _loc3_)
               {
                  _loc3_ = _players[_loc7_].PosX() - _loc5_;
               }
               if(_players[_loc7_].PosY() > _loc2_)
               {
                  _loc2_ = Number(_players[_loc7_].PosY());
               }
               if(_players[_loc7_].PosY() - _loc6_ < _loc1_)
               {
                  _loc1_ = _players[_loc7_].PosY() - _loc6_;
               }
            }
            _loc7_++;
         }
         _loc8_ = new Rectangle(_loc3_,_loc1_,_loc4_ - _loc3_,_loc2_ - _loc1_);
         _loc9_ = _loc8_.width / 4;
         _loc10_ = _loc8_.height / 3;
         _loc11_ = 0;
         if(_loc9_ < _loc10_)
         {
            _loc11_ = _loc10_ - _loc9_;
            _loc13_ = _loc11_ * 4;
            _loc8_.x -= _loc13_ / 2;
            _loc8_.width += _loc13_;
         }
         else if(_loc9_ > _loc10_)
         {
            _loc11_ = _loc9_ - _loc10_;
            _loc14_ = _loc11_ * 3;
            _loc8_.y -= _loc14_ / 2;
            _loc8_.height += _loc14_;
         }
         return _loc8_;
      }
      
      public function LinkToFire(param1:Fires) : void
      {
         var _loc2_:int = 0;
         _Handler_Fires = param1;
         _loc2_ = 0;
         while(_loc2_ < _players.length)
         {
            _players[_loc2_].LinkToFire(_Handler_Fires);
            _loc2_++;
         }
      }
      
      public function ActivatePlayers() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < _playerSetupData.totalPlayers)
         {
            _players[_loc1_].Activate();
            _loc1_++;
         }
      }
      
      public function Stop() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < _players.length)
         {
            _players[_loc1_].Stop();
            _loc1_++;
         }
      }
      
      private function GetRandomSpawnPosition() : Point
      {
         var _loc1_:Number = NaN;
         var _loc2_:Point = null;
         var _loc3_:int = 0;
         if(_playerSpawnPositions.length <= 0)
         {
            _loc3_ = 0;
            while(_loc3_ < _playerSetupData.playerSpawnPositions.length)
            {
               _playerSpawnPositions.push(_playerSetupData.playerSpawnPositions[_loc3_]);
               _loc3_++;
            }
         }
         _loc1_ = Math.floor(Math.random() * (_playerSpawnPositions.length * 0.99));
         _loc2_ = _playerSpawnPositions[_loc1_];
         _playerSpawnPositions.splice(_loc1_,1);
         return _loc2_;
      }
      
      public function SetStartImmunity() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < _players.length)
         {
            _players[_loc1_].State.ImmunityTimer = 48;
            _loc1_++;
         }
      }
      
      public function get Players() : Array
      {
         return _players;
      }
      
      public function RecalculateCamArea(param1:int = 8, param2:Boolean = false) : void
      {
         _Handler_Camera.RecalculateCamArea(param1,param2);
      }
      
      public function GetTeamWinner() : int
      {
         return _team_winner;
      }
      
      public function LinkToCam(param1:Cam) : void
      {
         _Handler_Camera = param1;
      }
      
      public function SetCamArea(param1:Rectangle, param2:Rectangle, param3:Rectangle, param4:Rectangle) : void
      {
         _cameraBounds = new Array();
         _cameraBounds.push(param1);
         _cameraBounds.push(param2);
         _cameraBounds.push(param3);
         _cameraBounds.push(param4);
      }
      
      public function get RoundOver() : Boolean
      {
         return _roundOver && _roundOverTimer <= 0;
      }
      
      public function SetMapArea(param1:Rectangle) : void
      {
         _MapArea = param1;
      }
      
      public function Update(param1:Number) : void
      {
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         var _loc7_:int = 0;
         var _loc8_:int = 0;
         if(!_playersInitialized)
         {
            _loc7_ = 0;
            while(_loc7_ < _playerSetupData.totalPlayers)
            {
               _players[_loc7_].Initialize(new PlayerAreaData(_MapArea));
               _loc7_++;
            }
            _Handler_Camera.Initialize();
            _playersInitialized = true;
         }
         _loc2_ = 0;
         while(_loc2_ < _players_left.length)
         {
            _players_left[_loc2_] = false;
            _loc2_++;
         }
         _loc3_ = 0;
         _loc4_ = -1;
         _loc5_ = -1;
         _loc6_ = 0;
         while(_loc6_ < _players.length)
         {
            _players[_loc6_].Update(param1);
            if(_players[_loc6_].State.HP > 0)
            {
               if(_players[_loc6_].Team < 0)
               {
                  _players_left[0] = true;
                  _loc3_++;
                  _loc5_ = 0;
                  _loc4_ = _loc6_;
               }
               else
               {
                  _loc5_ = int(_players[_loc6_].Team);
                  _players_left[_players[_loc6_].Team] = true;
               }
            }
            _loc6_++;
         }
         if(!_roundOver)
         {
            if(_loc3_ <= 1)
            {
               _loc8_ = 0;
               _loc2_ = 0;
               while(_loc2_ < _players_left.length)
               {
                  if(_players_left[_loc2_] == true)
                  {
                     _loc8_++;
                  }
                  _loc2_++;
               }
               if(_loc8_ <= 1)
               {
                  _roundOver = true;
               }
            }
         }
         else if(_roundOverTimer > 0)
         {
            _roundOverTimer -= param1;
            if(_roundOverTimer <= 0)
            {
               _team_winner = _loc5_;
               _solo_nr_winner = _loc4_;
            }
         }
         --_cameraUpdateTimer;
         if(_cameraUpdateTimer <= 0)
         {
            RecalculateCamArea();
            _cameraUpdateTimer = 6;
         }
      }
      
      public function GetSoloWinner() : int
      {
         return _players[_solo_nr_winner].Team;
      }
      
      private function ConstructPlayer(param1:int, param2:int, param3:int) : void
      {
         var _loc4_:Player = null;
         _loc4_ = new Player(param2,_game_mc,m_world,_Handler_Maps,_Handler_Sounds,_Handler_Slowmo,_Handler_Shake,_Handler_Effects,_Handler_ProjectilesUpdater,_Handler_Output,GetRandomSpawnPosition(),param3,param1,RecalculateCamArea,_players,_pathGrid);
         _players.push(_loc4_);
      }
      
      public function GetPlayerNrWinner() : int
      {
         return _solo_nr_winner;
      }
   }
}

