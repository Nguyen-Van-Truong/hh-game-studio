package cpmstar
{
   import flash.events.Event;
   
   public class AdEvent extends Event
   {
      public static var INIT:String = "adevent_init";
      
      public static var NO_AD:String = "adevent_no_ad";
      
      public static var ERROR:String = "adevent_error";
      
      public static var SKIPPED:String = "adevent_skipped";
      
      public static var OVERLAY_STARTED:String = "adevent_overlay_started";
      
      public static var LEAVE_BEHIND:String = "adevent_leave_behind";
      
      public static var SKIP_ALLOWED:String = "adevent_skip_allowed";
      
      public static var OVERLAY_COMPLETE:String = "adevent_overlay_complete";
      
      public function AdEvent(param1:String, param2:Boolean = false, param3:Boolean = false)
      {
         super(param1,param2,param3);
      }
      
      override public function clone() : Event
      {
         return new AdEvent(type,bubbles,cancelable);
      }
      
      override public function toString() : String
      {
         return formatToString("AdEvent","type","bubbles","cancelable","eventPhase");
      }
   }
}

