package Code.Handler
{
   import flash.display.MovieClip;
   import flash.text.TextField;
   
   public class OutputTrace extends MovieClip
   {
      private var _trace_txt:TextField;
      
      private var _debug:Boolean;
      
      private var _message_string:String;
      
      public function OutputTrace(param1:*, param2:Boolean)
      {
         _message_string = new String("");
         super();
         _debug = param2;
         if(_debug)
         {
            _trace_txt = new TextField();
            _trace_txt.width = 600;
            _trace_txt.height = 600;
            _trace_txt.selectable = false;
            _trace_txt.multiline = true;
            _trace_txt.textColor = 14540219;
            param1.addChild(_trace_txt);
         }
         Clear();
         Trace("OutputTrace Created");
         Hide();
      }
      
      public function Trace(param1:String) : void
      {
         if(_debug)
         {
            _message_string = _message_string.substr(0,_message_string.lastIndexOf("<br>"));
            _message_string = param1 + "<br>" + _message_string;
            _trace_txt.htmlText = _message_string;
         }
      }
      
      public function Show() : void
      {
         Trace("Showing Output");
         if(_debug)
         {
            _trace_txt.visible = true;
         }
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
         if(_debug)
         {
            _trace_txt.visible = false;
         }
      }
      
      public function Selectable(param1:Boolean) : void
      {
         Trace("Output Selectable set to " + param1);
         if(_debug)
         {
            _trace_txt.selectable = param1;
         }
      }
   }
}

