package Code.Particles
{
   import Code.Box2D.Common.Math.*;
   
   public class particle_data
   {
      public var Alpha:Number;
      
      public var PosX:Number;
      
      public var PosY:Number;
      
      public var ParticleVec:b2Vec2;
      
      public var Effect:String;
      
      public var ScaleY:Number;
      
      public var ScaleX:Number;
      
      public var DataArray:Array;
      
      public var Rotation:Number;
      
      public function particle_data(param1:String = "", param2:Number = 0, param3:Number = 0, param4:b2Vec2 = null, param5:Number = 0, param6:Number = 1, param7:Array = null)
      {
         super();
         Effect = param1.toUpperCase();
         PosX = param2;
         PosY = param3;
         if(param4 != null)
         {
            ParticleVec = param4;
         }
         else
         {
            ParticleVec = new b2Vec2(0,0);
         }
         Alpha = param6;
         Rotation = param5;
         DataArray = param7;
         ScaleX = 1;
         ScaleY = 1;
      }
   }
}

