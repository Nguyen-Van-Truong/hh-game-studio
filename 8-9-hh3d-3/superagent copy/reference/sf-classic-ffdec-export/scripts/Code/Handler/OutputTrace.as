package Code.Handler
{
   import flash.display.MovieClip;
   import flash.text.TextField;
   
   public class OutputTrace extends MovieClip
   {
      private var _trace_txt:TextField;
      
      private var _message_string:String;
      
      public function OutputTrace(param1:*)
      {
         _message_string = new String("");
         super();
         Clear();
         Trace("OutputTrace Created");
         Hide();
      }
      
      public function Trace(param1:String) : void
      {
      }
      
      public function Show() : void
      {
         Trace("Showing Output");
      }
      
      public function Clear() : void
      {
         var _loc1_:* = undefined;
         _message_string = "";
         _loc1_ = 0;
         while(_loc1_ < 39)
         {
            _message_string += "<br>";
            _loc1_++;
         }
      }
      
      public function Hide() : void
      {
         Trace("Hiding Output");
      }
      
      public function Selectable(param1:Boolean) : void
      {
         Trace("Output Selectable set to " + param1);
      }
   }
}

