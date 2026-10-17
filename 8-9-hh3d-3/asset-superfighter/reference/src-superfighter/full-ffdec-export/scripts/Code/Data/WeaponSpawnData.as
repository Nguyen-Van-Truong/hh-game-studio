package Code.Data
{
   import Code.Box2D.Dynamics.b2Body;
   
   public class WeaponSpawnData
   {
      private var blinkTimer:Number;
      
      private var positionY:Number;
      
      private var linkedWeapon:b2Body;
      
      private var positionX:Number;
      
      private var startBlink:int;
      
      private var weaponArray:Array;
      
      private var weaponDespawnTimer:Number;
      
      private var wpnHidden:Boolean;
      
      public function WeaponSpawnData(param1:Number, param2:Number, param3:Array)
      {
         super();
         positionX = param1;
         positionY = param2;
         weaponArray = param3;
         weaponDespawnTimer = 0;
         blinkTimer = 0;
         wpnHidden = false;
         startBlink = 8 * 24;
         linkedWeapon = null;
      }
      
      public function Update(param1:Number) : void
      {
         if(linkedWeapon != null)
         {
            if(weaponDespawnTimer > 0)
            {
               weaponDespawnTimer -= param1;
               if(weaponDespawnTimer <= 0)
               {
                  linkedWeapon.GetUserData().objectData.ForceDestruction();
                  linkedWeapon = null;
               }
               else if(weaponDespawnTimer <= startBlink)
               {
                  blinkTimer -= 1;
                  if(blinkTimer <= 0)
                  {
                     if(wpnHidden)
                     {
                        linkedWeapon.GetUserData().objectData.MC.gotoAndStop(1);
                     }
                     else
                     {
                        linkedWeapon.GetUserData().objectData.MC.gotoAndStop(2);
                     }
                     wpnHidden = !wpnHidden;
                     blinkTimer = 8;
                  }
               }
            }
         }
      }
      
      public function get PositionX() : Number
      {
         return positionX;
      }
      
      public function get PositionY() : Number
      {
         return positionY;
      }
      
      public function set LinkedWeapon(param1:b2Body) : void
      {
         linkedWeapon = param1;
         weaponDespawnTimer = 20 * 24;
      }
      
      public function get LinkedWeapon() : b2Body
      {
         return linkedWeapon;
      }
      
      public function get WeaponArray() : Array
      {
         return weaponArray;
      }
   }
}

