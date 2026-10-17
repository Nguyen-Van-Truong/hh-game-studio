package Code.Data
{
   import flash.display.*;
   
   public class MapGraphic
   {
      private var clips:Array;
      
      public function MapGraphic()
      {
         super();
         clips = new Array();
      }
      
      public function Update(param1:Number) : void
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < clips.length)
         {
            clips[_loc2_][1] += param1;
            if(clips[_loc2_][1] >= MovieClip(clips[_loc2_][0]).totalFrames + 1)
            {
               clips[_loc2_][1] -= MovieClip(clips[_loc2_][0]).totalFrames;
            }
            MovieClip(clips[_loc2_][0]).gotoAndStop(Math.floor(clips[_loc2_][1]));
            _loc2_++;
         }
      }
      
      public function AddMC(param1:MovieClip) : void
      {
         clips.push([param1,1]);
      }
   }
}

