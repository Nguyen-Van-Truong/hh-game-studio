package Code.Data.Menu
{
   import Code.Data.Challenges;
   import Code.Handler.InputKeyboard;
   import Code.Handler.Sounds;
   import com.newgrounds.API;
   import flash.display.MovieClip;
   import flash.net.SharedObject;
   
   public class challenge_selection extends submenu_base
   {
      private var _skipChoiseOnce:Boolean = false;
      
      private var _Handler_Keyboard:InputKeyboard;
      
      private var _stageLevelsFinished:Array;
      
      private var _nextChallenge:int;
      
      public function challenge_selection(param1:MovieClip, param2:Sounds, param3:InputKeyboard, param4:int)
      {
         var _loc5_:int = 0;
         var _loc6_:int = 0;
         _skipChoiseOnce = false;
         super();
         _this = param1;
         _this.win_message.visible = false;
         _canReturn = true;
         _Handler_Sounds = param2;
         _Handler_Keyboard = param3;
         _loc5_ = 0;
         while(_loc5_ < 12)
         {
            _loc6_ = int(Challenges.CHALLENGE[param4 - 1][_loc5_][0]);
            MovieClip(_this.getChildByName("c_" + (_loc5_ + 1))).map_pic.gotoAndStop(_loc6_);
            _loc5_++;
         }
         LoadData();
         UpdateMarker();
      }
      
      override public function UpdateMarker() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 1;
         while(_loc1_ <= 12)
         {
            if(_stageLevelsFinished[_loc1_ - 1])
            {
               MovieClip(_this.getChildByName("c_" + _loc1_)).gotoAndStop(3);
            }
            else
            {
               MovieClip(_this.getChildByName("c_" + _loc1_)).gotoAndStop(1);
            }
            MovieClip(MovieClip(_this.getChildByName("c_" + _loc1_)).getChildByName("selection")).visible = false;
            _loc1_++;
         }
         if(_nextChallenge != 0)
         {
            MovieClip(_this.getChildByName("c_" + _nextChallenge)).gotoAndStop(2);
         }
         if(_nextChallenge == 0)
         {
            MovieClip(_this.getChildByName("funnyman_message")).gotoAndStop(2);
         }
         else
         {
            MovieClip(_this.getChildByName("funnyman_message")).gotoAndStop(1);
         }
         _this.delete_marker.visible = false;
         if(_marker_pos <= 12)
         {
            MovieClip(MovieClip(_this.getChildByName("c_" + _marker_pos)).getChildByName("selection")).visible = true;
         }
         else
         {
            _this.delete_marker.visible = true;
         }
      }
      
      public function SaveWinData() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         _loc1_.data.stageModeWinMessageShown = true;
         _loc1_.flush();
      }
      
      public function LoadData() : void
      {
         var _loc1_:SharedObject = null;
         var _loc2_:int = 0;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         if(_loc1_.data.stageLevelsFinished != undefined)
         {
            _stageLevelsFinished = _loc1_.data.stageLevelsFinished;
         }
         else
         {
            _stageLevelsFinished = [false,false,false,false,false,false,false,false,false,false,false,false];
            SaveData();
         }
         _nextChallenge = 0;
         _marker_pos = 1;
         _loc2_ = 0;
         while(_loc2_ < 12)
         {
            if(_stageLevelsFinished[_loc2_] == false)
            {
               _nextChallenge = _loc2_ + 1;
               _marker_pos = _loc2_ + 1;
               return;
            }
            _loc2_++;
         }
         if(_nextChallenge == 0)
         {
            if(_loc1_.data.stageModeWinMessageShown == undefined)
            {
               _this.win_message.visible = true;
               _canReturn = false;
               _skipChoiseOnce = true;
               SaveWinData();
            }
         }
      }
      
      public function SaveData() : void
      {
         var _loc1_:SharedObject = null;
         _loc1_ = SharedObject.getLocal("superfightersData_v1.0");
         _loc1_.data.stageLevelsFinished = _stageLevelsFinished;
         _loc1_.flush();
      }
      
      private function Change(param1:int) : void
      {
         if(_marker_pos == 13)
         {
            _marker_pos = 12;
         }
         _marker_pos += param1;
         if(_marker_pos < 1)
         {
            _marker_pos += 12;
         }
         if(_marker_pos > 12)
         {
            _marker_pos -= 12;
         }
      }
      
      override public function Show() : void
      {
         _this.visible = true;
         LoadData();
         UpdateMarker();
         if(_nextChallenge == 0)
         {
            API.unlockMedal("Superfighter");
         }
      }
      
      override public function KeyPressed(param1:int) : void
      {
         if(!_this.win_message.visible)
         {
            switch(param1)
            {
               case MenuKey.KEY_UP:
                  if(_marker_pos == 13)
                  {
                     _marker_pos = 12;
                  }
                  else
                  {
                     Change(-4);
                  }
                  break;
               case MenuKey.KEY_DOWN:
                  if(_marker_pos == 11 || _marker_pos == 12)
                  {
                     _marker_pos = 13;
                  }
                  else if(_marker_pos == 13)
                  {
                     _marker_pos = 4;
                  }
                  else
                  {
                     Change(4);
                  }
                  break;
               case MenuKey.KEY_LEFT:
                  Change(-1);
                  break;
               case MenuKey.KEY_RIGHT:
                  Change(1);
                  break;
               case MenuKey.KEY_ENTER:
               case MenuKey.KEY_BACKSPACE:
            }
            UpdateMarker();
         }
         else if(param1 == MenuKey.KEY_ENTER || param1 == MenuKey.KEY_BACKSPACE)
         {
            _this.win_message.visible = false;
            _canReturn = true;
         }
      }
      
      public function get SelectedChallenge() : int
      {
         return _marker_pos;
      }
      
      override public function GetChoice() : String
      {
         if(_skipChoiseOnce)
         {
            _skipChoiseOnce = false;
         }
         else
         {
            if(_marker_pos == 13)
            {
               return "confirm_delete";
            }
            if(_marker_pos <= _nextChallenge || _nextChallenge == 0)
            {
               return "start_challenge";
            }
         }
         return "";
      }
   }
}

