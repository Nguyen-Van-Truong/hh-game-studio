package Code.Handler
{
   import Code.Box2D.Collision.*;
   import Code.Box2D.Collision.Shapes.*;
   import Code.Box2D.Common.*;
   import Code.Box2D.Common.Math.*;
   import Code.Box2D.Dynamics.*;
   import Code.Box2D.Dynamics.Contacts.*;
   
   public class Deconstructer
   {
      private var m_world:b2World;
      
      private var _deconstructListener:Array;
      
      public function Deconstructer()
      {
         super();
         _deconstructListener = new Array();
      }
      
      public function AddBody(param1:b2Body) : void
      {
         if(param1.GetUserData().destroyed != true && param1.GetUserData().locked != true)
         {
            if(Boolean(param1.m_userData.objectData.DrawHitBox) || Boolean(param1.m_userData.objectData.DrawCloudBox))
            {
               param1.m_userData.objectData.CollisionMC.parent.removeChild(param1.m_userData.objectData.CollisionMC);
            }
            if(param1.m_userData.objectData.DrawShapeMC)
            {
               param1.m_userData.objectData.ShapeMC.parent.removeChild(param1.m_userData.objectData.ShapeMC);
            }
            param1.GetUserData().destroyed = true;
            m_world.RemoveObjectFromLists(param1);
            _deconstructListener.push(param1);
         }
      }
      
      public function set Setb2World(param1:b2World) : void
      {
         m_world = param1;
      }
      
      public function set DeconstructList(param1:Array) : void
      {
         _deconstructListener = param1;
      }
      
      public function Update() : void
      {
         var i:int = 0;
         if(_deconstructListener.length > 0)
         {
            i = 0;
            while(i < _deconstructListener.length)
            {
               try
               {
                  _deconstructListener[i].m_userData.parent.removeChild(_deconstructListener[i].m_userData);
                  _deconstructListener[i].m_userData.onDestruction(_deconstructListener[i]);
                  m_world.DestroyBody(_deconstructListener[i]);
               }
               catch(e:Error)
               {
               }
               i++;
            }
            _deconstructListener = new Array();
         }
      }
      
      public function get DeconstructList() : Array
      {
         return _deconstructListener;
      }
   }
}

