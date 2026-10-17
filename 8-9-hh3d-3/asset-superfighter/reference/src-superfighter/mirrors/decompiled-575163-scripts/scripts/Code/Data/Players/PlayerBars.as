package Code.Data.Players
{
   import flash.display.MovieClip;
   import flash.display.Sprite;
   import flash.geom.ColorTransform;
   
   public class PlayerBars
   {
      public static var PLAYER_COM:int = 0;
      
      public static var PLAYER_1:int = 1;
      
      public static var PLAYER_2:int = 2;
      
      private var _gui_mc:MovieClip;
      
      private var _sprint_bar:MovieClip;
      
      private var _health_bar:MovieClip;
      
      private var _PlayerState:PlayerState;
      
      private var _player_sign:MovieClip;
      
      private var _health_energy_bar:MovieClip;
      
      private var _sprint_energy_bar:MovieClip;
      
      private var _player_sign_text:Boolean = false;
      
      private var _gui_bars_mc:MovieClip;
      
      private var _showBars:Boolean;
      
      public function PlayerBars(param1:PlayerState, param2:MovieClip)
      {
         var _loc3_:Sprite = null;
         var _loc4_:Sprite = null;
         var _loc5_:ColorTransform = null;
         _player_sign_text = false;
         super();
         _PlayerState = param1;
         _health_bar = new MovieClip();
         _loc3_ = new Sprite();
         _loc3_.graphics.lineStyle(0.25,0,0);
         _loc3_.graphics.beginFill(0,1);
         _loc3_.graphics.moveTo(-10,0);
         _loc3_.graphics.lineTo(-10,-2);
         _loc3_.graphics.lineTo(10,-2);
         _loc3_.graphics.lineTo(10,0);
         _loc3_.graphics.lineTo(-10,0);
         _loc3_.graphics.endFill();
         _health_energy_bar = new MovieClip();
         _health_energy_bar.graphics.lineStyle(1,GetColor(255,255,255),0);
         _health_energy_bar.graphics.beginFill(GetColor(255,255,255),1);
         _health_energy_bar.graphics.moveTo(0,0);
         _health_energy_bar.graphics.lineTo(0,-2);
         _health_energy_bar.graphics.lineTo(20,-2);
         _health_energy_bar.graphics.lineTo(20,0);
         _health_energy_bar.graphics.lineTo(0,0);
         _health_energy_bar.graphics.endFill();
         _health_energy_bar.x = -10;
         _health_bar.addChild(_loc3_);
         _health_bar.addChild(_health_energy_bar);
         _health_bar.alpha = 0.5;
         _sprint_bar = new MovieClip();
         _loc4_ = new Sprite();
         _loc4_.graphics.lineStyle(0.25,0,0);
         _loc4_.graphics.beginFill(0,1);
         _loc4_.graphics.moveTo(-10,0);
         _loc4_.graphics.lineTo(-10,-2);
         _loc4_.graphics.lineTo(10,-2);
         _loc4_.graphics.lineTo(10,0);
         _loc4_.graphics.lineTo(-10,0);
         _loc4_.graphics.endFill();
         _sprint_energy_bar = new MovieClip();
         _sprint_energy_bar.graphics.lineStyle(1,GetColor(255,255,255),0);
         _sprint_energy_bar.graphics.beginFill(GetColor(255,255,255),1);
         _sprint_energy_bar.graphics.moveTo(0,0);
         _sprint_energy_bar.graphics.lineTo(0,-2);
         _sprint_energy_bar.graphics.lineTo(20,-2);
         _sprint_energy_bar.graphics.lineTo(20,0);
         _sprint_energy_bar.graphics.lineTo(0,0);
         _sprint_energy_bar.graphics.endFill();
         _sprint_energy_bar.x = -10;
         _sprint_bar.addChild(_loc4_);
         _sprint_bar.addChild(_sprint_energy_bar);
         _sprint_bar.alpha = 0.5;
         param2.addChild(_sprint_bar);
         param2.addChild(_health_bar);
         _health_bar.visible = false;
         _player_sign = new player_sign();
         _loc5_ = _player_sign.transform.colorTransform;
         if(_PlayerState.Team < 0)
         {
            _loc5_.redOffset = PlayerTeamColor.SOLO[0] - 255;
            _loc5_.greenOffset = PlayerTeamColor.SOLO[1] - 255;
            _loc5_.blueOffset = PlayerTeamColor.SOLO[2] - 255;
         }
         else
         {
            _loc5_.redOffset = PlayerTeamColor.TEAM[_PlayerState.Team - 1][0] - 255;
            _loc5_.greenOffset = PlayerTeamColor.TEAM[_PlayerState.Team - 1][1] - 255;
            _loc5_.blueOffset = PlayerTeamColor.TEAM[_PlayerState.Team - 1][2] - 255;
         }
         _player_sign.transform.colorTransform = _loc5_;
         param2.addChild(_player_sign);
         _showBars = true;
      }
      
      public function Update(param1:Number, param2:Number, param3:Number) : void
      {
         var _loc4_:Number = NaN;
         var _loc5_:Number = NaN;
         if(_PlayerState.HP <= 0)
         {
            _sprint_bar.visible = false;
            _health_bar.visible = false;
            _player_sign.visible = false;
            _gui_bars_mc.visible = false;
            return;
         }
         DrawGUIBars();
         if(!_PlayerState.ShowHealthBar && _PlayerState.SprintEnergy >= 100 || _PlayerState.StuckToRocket)
         {
            _sprint_bar.visible = false;
            _health_bar.visible = false;
         }
         param2 += 30;
         if(_PlayerState.Diving)
         {
            param2 -= 14;
         }
         else
         {
            param2 -= 22;
         }
         _loc4_ = 0.5 + 0.5 / param3;
         _player_sign.x = param1;
         _player_sign.y = param2 - 30;
         if(_player_sign_text)
         {
            _player_sign.scaleX = _loc4_ * 1.3;
            _player_sign.scaleY = _loc4_ * 1.3;
         }
         else
         {
            _player_sign.scaleX = _loc4_;
            _player_sign.scaleY = _loc4_;
         }
         _player_sign.visible = true;
         if(!_showBars)
         {
            return;
         }
         if(_PlayerState.ShowHealthBar)
         {
            _health_bar.visible = true;
            _health_bar.scaleX = _loc4_;
            _health_bar.scaleY = _loc4_;
            _loc5_ = _PlayerState.BarHP / 100;
            _health_energy_bar.graphics.clear();
            _health_energy_bar.graphics.lineStyle(1,16777215,0);
            _health_energy_bar.graphics.beginFill(GetColor(255 - Math.round(255 * _loc5_),Math.round(255 * _loc5_),40));
            _health_energy_bar.graphics.moveTo(0,0);
            _health_energy_bar.graphics.lineTo(0,-2);
            _health_energy_bar.graphics.lineTo(20 * _loc5_,-2);
            _health_energy_bar.graphics.lineTo(20 * _loc5_,0);
            _health_energy_bar.graphics.lineTo(0,0);
            _health_energy_bar.graphics.endFill();
            _health_energy_bar.x = -10;
            _health_bar.x = param1;
            _health_bar.y = param2;
            param2 += 3;
         }
         else
         {
            _health_bar.visible = false;
         }
         if(_PlayerState.SprintEnergy >= 100)
         {
            _sprint_bar.visible = false;
            return;
         }
         _sprint_bar.visible = true;
         _sprint_bar.scaleX = _loc4_;
         _sprint_bar.scaleY = _loc4_;
         _loc5_ = _PlayerState.SprintEnergy / 100;
         _sprint_energy_bar.graphics.clear();
         _sprint_energy_bar.graphics.lineStyle(1,16777215,0);
         _sprint_energy_bar.graphics.beginFill(16777215);
         _sprint_energy_bar.graphics.moveTo(0,0);
         _sprint_energy_bar.graphics.lineTo(0,-2);
         _sprint_energy_bar.graphics.lineTo(20 * _loc5_,-2);
         _sprint_energy_bar.graphics.lineTo(20 * _loc5_,0);
         _sprint_energy_bar.graphics.lineTo(0,0);
         _sprint_energy_bar.graphics.endFill();
         _sprint_energy_bar.x = -10;
         _sprint_bar.x = param1;
         _sprint_bar.y = param2;
      }
      
      private function GetColor(param1:Number, param2:Number, param3:Number) : uint
      {
         var _loc4_:uint = 0;
         return uint(param1 << 16 | param2 << 8 | param3);
      }
      
      public function DrawGUIBars() : void
      {
         var _loc1_:Number = NaN;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         var _loc4_:Number = NaN;
         _loc1_ = _gui_mc.bars_end.x - _gui_mc.bars_start.x;
         _loc2_ = 4;
         _loc3_ = 6;
         _loc4_ = _PlayerState.BarHP / 100;
         _gui_bars_mc.graphics.clear();
         _gui_bars_mc.graphics.lineStyle(1,16777215,0);
         _gui_bars_mc.graphics.beginFill(GetColor(255 - Math.round(255 * _loc4_),Math.round(255 * _loc4_),40));
         _gui_bars_mc.graphics.moveTo(0,0);
         _gui_bars_mc.graphics.lineTo(0,_loc2_);
         _gui_bars_mc.graphics.lineTo(_loc1_ * _loc4_,_loc2_);
         _gui_bars_mc.graphics.lineTo(_loc1_ * _loc4_,0);
         _gui_bars_mc.graphics.lineTo(0,0);
         _gui_bars_mc.graphics.endFill();
         if(_loc4_ == 0)
         {
            return;
         }
         _loc4_ = _PlayerState.SprintEnergy / 100;
         _gui_bars_mc.graphics.lineStyle(1,16777215,0);
         _gui_bars_mc.graphics.beginFill(16777215);
         _gui_bars_mc.graphics.moveTo(0,_loc3_);
         _gui_bars_mc.graphics.lineTo(0,_loc3_ + _loc2_);
         _gui_bars_mc.graphics.lineTo(_loc1_ * _loc4_,_loc3_ + _loc2_);
         _gui_bars_mc.graphics.lineTo(_loc1_ * _loc4_,_loc3_);
         _gui_bars_mc.graphics.lineTo(0,_loc3_);
         _gui_bars_mc.graphics.endFill();
      }
      
      public function SetGUI(param1:MovieClip) : void
      {
         _gui_mc = param1;
         _gui_bars_mc = new MovieClip();
         _gui_bars_mc.x = _gui_mc.bars_start.x;
         _gui_bars_mc.y = _gui_mc.bars_start.y;
         _gui_mc.addChild(_gui_bars_mc);
      }
      
      public function Show() : void
      {
         _showBars = true;
      }
      
      public function SetSign(param1:int) : void
      {
         switch(param1)
         {
            case PLAYER_COM:
               _player_sign.gotoAndStop(3);
               _gui_mc.sign.gotoAndStop(3);
               _player_sign_text = false;
               break;
            case PLAYER_1:
               _player_sign.gotoAndStop(1);
               _gui_mc.sign.gotoAndStop(1);
               _player_sign_text = true;
               break;
            case PLAYER_2:
               _player_sign.gotoAndStop(2);
               _gui_mc.sign.gotoAndStop(2);
               _player_sign_text = true;
         }
         _gui_mc.sign.transform.colorTransform = _player_sign.transform.colorTransform;
      }
      
      public function Hide() : void
      {
         _showBars = false;
         _sprint_bar.visible = false;
         _health_bar.visible = false;
         _player_sign.visible = false;
         _gui_bars_mc.visible = false;
      }
   }
}

