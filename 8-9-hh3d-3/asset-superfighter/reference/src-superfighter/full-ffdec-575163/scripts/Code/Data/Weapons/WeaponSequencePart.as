package Code.Data.Weapons
{
   public class WeaponSequencePart
   {
      public var FrameSound:String;
      
      public var End:Boolean;
      
      public var FrameNr:int;
      
      public var Bullets:int;
      
      public var UseMuzzleEffect:Boolean;
      
      public var UseShellEffect:Boolean;
      
      public function WeaponSequencePart(param1:int = 0, param2:Boolean = false, param3:Boolean = false, param4:String = "NONE", param5:int = 1, param6:Boolean = false)
      {
         super();
         Bullets = param1;
         UseMuzzleEffect = param2;
         UseShellEffect = param3;
         FrameSound = param4;
         FrameNr = param5;
         End = param6;
      }
   }
}

