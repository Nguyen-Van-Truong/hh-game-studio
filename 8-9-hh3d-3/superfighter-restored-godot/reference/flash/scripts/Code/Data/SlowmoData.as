package Code.Data
{
   public class SlowmoData
   {
      private var _currentSlowmotion:Number;
      
      private var _timeStay:int;
      
      private var _timeFadeOut:int;
      
      private var _timeTotalDuration:int;
      
      private var _timeFadeIn:int;
      
      private var _elapsedTime:int;
      
      private var _slowmotion:Number;
      
      public function SlowmoData(param1:int, param2:int, param3:int, param4:Number)
      {
         super();
         _timeFadeIn = param1;
         _timeStay = param2;
         _timeFadeOut = param3;
         _timeTotalDuration = param1 + param2 + param3;
         _slowmotion = param4;
         _elapsedTime = 0;
      }
      
      public function ProgressTime(param1:int = 1) : void
      {
         _elapsedTime += param1;
         if(_elapsedTime < _timeFadeIn)
         {
            _currentSlowmotion = 1 - _elapsedTime / _timeFadeIn * (1 - _slowmotion);
         }
         else if(_elapsedTime <= _timeFadeIn + _timeStay)
         {
            _currentSlowmotion = _slowmotion;
         }
         else
         {
            _currentSlowmotion = _slowmotion + (_elapsedTime - (_timeFadeIn + _timeStay)) / _timeFadeOut * (1 - _slowmotion);
         }
      }
      
      public function get CurrentSlowmotion() : Number
      {
         return _currentSlowmotion;
      }
      
      public function get Completed() : Boolean
      {
         return _elapsedTime >= _timeTotalDuration;
      }
   }
}

