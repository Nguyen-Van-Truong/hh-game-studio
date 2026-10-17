package Code.Data
{
   import Code.Box2D.Dynamics.b2World;
   import Code.Handler.Cam;
   import Code.Handler.Effects;
   import Code.Handler.OutputTrace;
   import Code.Handler.PlayersKeeper;
   import Code.Handler.Shake;
   import Code.Handler.Slowmo;
   import Code.Handler.Sounds;
   import flash.display.MovieClip;
   
   public class ExplosionData
   {
      public var m_world:b2World;
      
      public var dynamic_mc:MovieClip;
      
      public var Handler_Effects:Effects;
      
      public var static_mc:MovieClip;
      
      public var Handler_Shake:Shake;
      
      public var Handler_Camera:Cam;
      
      public var Handler_Output:OutputTrace;
      
      public var Handler_Slowmo:Slowmo;
      
      public var Handler_Sounds:Sounds;
      
      public var Handler_Players:PlayersKeeper;
      
      public function ExplosionData()
      {
         super();
      }
   }
}

