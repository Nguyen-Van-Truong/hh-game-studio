package Code.Handler
{
   import Code.Data.Players.*;
   import Code.Data.SurvivalTimePackage;
   import flash.display.MovieClip;
   import flash.net.SharedObject;
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public class ScoreboardSurvival
   {
      private var _personal_best:SurvivalTimePackage;
      
      private var _score_info:MovieClip;
      
      private var _build_timer:Number;
      
      private var _players:Array;
      
      public function ScoreboardSurvival(param1:MovieClip)
      {
         super();
         _players = new Array();
         _score_info = new survival_score();
         _score_info.gotoAndStop(1);
         param1.addChild(_score_info);
      }
      
      public function Hide() : void
      {
         _score_info.visible = false;
      }
      
      private function SetTimer(param1:MovieClip, param2:SurvivalTimePackage) : void
      {
         var _loc3_:* = null;
         var _loc4_:* = null;
         var _loc5_:* = null;
         _loc3_ = param2.totalMins + "";
         _loc4_ = param2.totalSecs + "";
         _loc5_ = param2.totalParts + "";
         if(param2.totalMins < 10)
         {
            _loc3_ = "0" + _loc3_;
         }
         if(param2.totalSecs < 10)
         {
            _loc4_ = "0" + _loc4_;
         }
         if(param2.totalParts < 10)
         {
            _loc5_ = "0" + _loc5_;
         }
         param1.time_txt.text = _loc3_ + ":" + _loc4_ + ":" + _loc5_;
         if(param2.wave < 10)
         {
            param1.wave_txt.text = "0" + param2.wave;
         }
         else
         {
            param1.wave_txt.text = "" + param2.wave;
         }
      }
      
      public function get MC() : MovieClip
      {
         return _score_info;
      }
      
      private function SetPics() : void
      {
         var _loc1_:int = 0;
         clearInterval(_build_timer);
         _loc1_ = 0;
         while(_loc1_ < _players.length)
         {
            MovieClip(_score_info.pics.getChildByName("pic_" + (_loc1_ + 1))).gotoAndStop(_players[_loc1_].State.CharNr);
            _loc1_++;
         }
      }
      
      public function Build() : void
      {
         _score_info.players_txt.text = "" + _players.length;
         _score_info.pics.gotoAndStop(_players.length);
         _personal_best = LoadBest();
         SetTimer(_score_info.personal_best,_personal_best);
         _build_timer = setInterval(SetPics,100);
      }
      
      public function SaveBest(param1:SurvivalTimePackage) : void
      {
         var _loc2_:SharedObject = null;
         _loc2_ = SharedObject.getLocal("superfightersData_v1.0");
         if(_players.length == 1)
         {
            _loc2_.data.survivalBestMins = param1.totalMins;
            _loc2_.data.survivalBestSecs = param1.totalSecs;
            _loc2_.data.survivalBestParts = param1.totalParts;
            _loc2_.data.survivalBestWave = param1.wave;
         }
         else
         {
            _loc2_.data.survival2BestMins = param1.totalMins;
            _loc2_.data.survival2BestSecs = param1.totalSecs;
            _loc2_.data.survival2BestParts = param1.totalParts;
            _loc2_.data.survival2BestWave = param1.wave;
         }
         _loc2_.flush();
      }
      
      public function LoadBest() : SurvivalTimePackage
      {
         var _loc1_:SurvivalTimePackage = null;
         var _loc2_:SharedObject = null;
         _loc1_ = new SurvivalTimePackage();
         _loc2_ = SharedObject.getLocal("superfightersData_v1.0");
         if(_players.length == 1 && _loc2_.data.survivalBestMins != undefined && _loc2_.data.survivalBestSecs != undefined && _loc2_.data.survivalBestParts != undefined && _loc2_.data.survivalBestWave != undefined)
         {
            _loc1_.totalMins = _loc2_.data.survivalBestMins;
            _loc1_.totalSecs = _loc2_.data.survivalBestSecs;
            _loc1_.totalParts = _loc2_.data.survivalBestParts;
            _loc1_.wave = _loc2_.data.survivalBestWave;
         }
         else if(_players.length == 2 && _loc2_.data.survival2BestMins != undefined && _loc2_.data.survival2BestSecs != undefined && _loc2_.data.survival2BestParts != undefined && _loc2_.data.survival2BestWave != undefined)
         {
            _loc1_.totalMins = _loc2_.data.survival2BestMins;
            _loc1_.totalSecs = _loc2_.data.survival2BestSecs;
            _loc1_.totalParts = _loc2_.data.survival2BestParts;
            _loc1_.wave = _loc2_.data.survival2BestWave;
         }
         else
         {
            _loc1_.totalMins = 0;
            _loc1_.totalSecs = 0;
            _loc1_.totalParts = 0;
            _loc1_.wave = 0;
         }
         return _loc1_;
      }
      
      public function BeatPersonal(param1:SurvivalTimePackage) : Boolean
      {
         if(_personal_best.totalMins > param1.totalMins)
         {
            return false;
         }
         if(_personal_best.totalMins < param1.totalMins)
         {
            return true;
         }
         if(_personal_best.totalSecs > param1.totalSecs)
         {
            return false;
         }
         if(_personal_best.totalSecs < param1.totalSecs)
         {
            return true;
         }
         if(_personal_best.totalParts > param1.totalParts)
         {
            return false;
         }
         if(_personal_best.totalParts < param1.totalParts)
         {
            return true;
         }
         return true;
      }
      
      public function Update(param1:SurvivalTimePackage) : void
      {
         SetTimer(_score_info.current,param1);
         if(BeatPersonal(param1))
         {
            SaveBest(param1);
            _score_info.gotoAndStop(2);
         }
      }
      
      public function AddPlayerToScore(param1:Player) : void
      {
         _players.push(param1);
      }
      
      public function Show() : void
      {
         _score_info.visible = true;
      }
   }
}

