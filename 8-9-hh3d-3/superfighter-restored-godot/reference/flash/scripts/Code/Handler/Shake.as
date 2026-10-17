package Code.Handler
{
   import flash.display.MovieClip;
   
   public class Shake
   {
      private var _speedX:Number = 0;
      
      private var _speedY:Number = 0;
      
      private var _tarX:Number = 0;
      
      private var _lastRnd:Number = 0;
      
      private var _Handler_Output:OutputTrace;
      
      private var _shakeMangitude:Number = 0;
      
      private var _tarY:Number = 0;
      
      private var _shake_mc:MovieClip;
      
      private var _shakeTimer:Number = 0;
      
      public function Shake(param1:OutputTrace, param2:MovieClip)
      {
         _shakeTimer = 0;
         _shakeMangitude = 0;
         _lastRnd = 0;
         _tarX = 0;
         _tarY = 0;
         _speedX = 0;
         _speedY = 0;
         super();
         _Handler_Output = param1;
         _shake_mc = param2;
      }
      
      public function Add(param1:Number, param2:Number) : void
      {
         _shakeTimer += param1;
         _shakeMangitude += param2;
         if(_shakeMangitude > 30)
         {
            _shakeMangitude = 30;
         }
         if(_shakeTimer > 20)
         {
            _shakeTimer = 20;
         }
      }
      
      public function Update(param1:Number) : void
      {
         if(_shakeTimer > 0)
         {
            if(_lastRnd != Math.floor(_shakeTimer))
            {
               _tarX = Math.random() * _shakeMangitude - _shakeMangitude / 2;
               _tarY = Math.random() * _shakeMangitude - _shakeMangitude / 2;
               _speedX = _tarX - _shake_mc.x;
               _speedY = _tarY - _shake_mc.y;
               _lastRnd = Math.floor(_shakeTimer);
            }
            _shake_mc.x += _speedX * param1;
            _shake_mc.y += _speedY * param1;
            _shakeTimer -= param1;
            if(_shakeTimer <= 0)
            {
               _shakeTimer = 0;
               _shake_mc.x = 0;
               _shake_mc.y = 0;
               _lastRnd = 0;
               _shakeTimer = 0;
               _shakeMangitude = 0;
            }
         }
      }
   }
}

