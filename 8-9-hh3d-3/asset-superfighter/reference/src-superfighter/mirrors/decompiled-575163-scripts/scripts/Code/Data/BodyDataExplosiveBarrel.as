package Code.Data
{
   import Code.Box2D.Dynamics.b2Body;
   import Code.Handler.Deconstructer;
   import flash.display.MovieClip;
   
   public class BodyDataExplosiveBarrel extends BodyData
   {
      public function BodyDataExplosiveBarrel(param1:MovieClip, param2:Deconstructer, param3:Number = 50, param4:Number = 1, param5:Number = 1, param6:Number = 1, param7:Number = 1, param8:Boolean = false)
      {
         super(param1,param2,param3,param4,param5,param6,param7,param8);
         UserValues = new Array(0,0);
      }
      
      override protected function Damage(param1:Number) : void
      {
         var dmg:Number = param1;
         if(!_indestructible)
         {
            HP -= dmg;
            if(HP <= 0 && UserValues[0] == 0)
            {
               _mc.gotoAndStop(2);
               UserValues[0] = 1;
               UpdateFunction = function(param1:b2Body, param2:Number):void
               {
                  UserValues[1] += param2;
                  if(UserValues[1] >= 1)
                  {
                     _Handler_Deconstructer.AddBody(_body);
                  }
               };
            }
         }
      }
      
      override public function ForceDestruction() : void
      {
         HP = 0;
         if(HP <= 0 && UserValues[0] == 0)
         {
            _mc.gotoAndStop(2);
            UserValues[0] = 1;
            UpdateFunction = function(param1:b2Body, param2:Number):void
            {
               UserValues[1] += param2;
               if(UserValues[1] >= 1)
               {
                  _Handler_Deconstructer.AddBody(_body);
               }
            };
         }
      }
   }
}

