package Code.Data.Players
{
   import Code.Box2D.Dynamics.b2Body;
   import Code.Data.PathResultNode;
   
   public class BotState
   {
      public static const EASY:int = 1;
      
      public static const MEDIUM:int = 2;
      
      public static const HARD:int = 3;
      
      public static const FOLLOW_ONLY:Boolean = false;
      
      public static const IDLE:int = 0;
      
      public static const AIM:int = 1;
      
      public static const SHOOT:int = 2;
      
      public static const CANCEL_AIM:int = 3;
      
      public static const FOLLOW_PATH:int = 4;
      
      public static const GRAB_WEAPON:int = 5;
      
      public static const MELEE:int = 6;
      
      public static const INTERRUPTED:int = -1;
      
      public static const DISTANCE_LADDER_TOLERANCE_X:Number = 2;
      
      public static const DISTANCE_LADDER_TOLERANCE_Y:Number = 5;
      
      public static const DISTANCE_WALK_TOLERANCE:Number = 4;
      
      public static const DISTANCE_NODE_TOLERANCE_X:Number = 6;
      
      public static const DISTANCE_NODE_TOLERANCE_Y_MIN:Number = 8;
      
      public static const DISTANCE_NODE_TOLERANCE_Y_MAX:Number = -22;
      
      public static const UNAVAILABLE_PLAYER_TIMER:int = 6;
      
      public var RandomFirePosition:Boolean = true;
      
      public var GrabWeaponTimer:int = 0;
      
      private var _nextResNode:PathResultNode = null;
      
      public var TargetInSight:Boolean = false;
      
      public var DodgeBullet:Boolean = false;
      
      public var _targetChooseTimer:Number;
      
      public var DoFireCheck:Boolean = false;
      
      public var PreferJumpOverObstacle:Boolean = false;
      
      public var CancelAimSoon:Boolean = false;
      
      public var IgnoreDodgeBulletWhileAiming:Boolean = false;
      
      public var UnavailableWeapons:Array;
      
      public var ActivateSprintCounter:int = 0;
      
      public var TargetHazardousObject:b2Body = null;
      
      public var MeleeToAimMinimumChance:Number = 0.2;
      
      public var IgnoreObjectCheckingTimer:int = 0;
      
      public var RunOften:Boolean = true;
      
      public var TargetInAim:Boolean = false;
      
      public var RandomFireX:Number;
      
      public var RandomFireY:Number;
      
      public var FirstRocketTurnDone:Boolean = false;
      
      public var Path:Array;
      
      public var PathGridCounter:int = 0;
      
      public var ResetTimer:int = 0;
      
      public var ActionShotFired:Boolean = true;
      
      public var Difficulty:int;
      
      private var _phaseDelay:int = 0;
      
      public var UnavailablePlayers:Array;
      
      private var _targetWeapon:b2Body = null;
      
      public var RunAwayFromHazards:Boolean = false;
      
      public var FollowToAimMinimumDistance:Number = 50;
      
      public var _randomizTimer:Number;
      
      public var OpponentExist:Boolean = true;
      
      private var _phase:int = 0;
      
      public var _targetInSightTimer:Number;
      
      private var targetPlayer:Player = null;
      
      public function BotState()
      {
         _phase = IDLE;
         _phaseDelay = 0;
         TargetInAim = false;
         TargetInSight = false;
         ActivateSprintCounter = 0;
         ResetTimer = 0;
         DoFireCheck = false;
         DodgeBullet = false;
         RunAwayFromHazards = false;
         OpponentExist = true;
         PreferJumpOverObstacle = false;
         ActionShotFired = true;
         IgnoreObjectCheckingTimer = 0;
         CancelAimSoon = false;
         FirstRocketTurnDone = false;
         RunOften = true;
         RandomFirePosition = true;
         UnavailablePlayers = new Array();
         UnavailableWeapons = new Array();
         FollowToAimMinimumDistance = 50;
         MeleeToAimMinimumChance = 0.2;
         IgnoreDodgeBulletWhileAiming = false;
         _nextResNode = null;
         PathGridCounter = 0;
         Path = new Array();
         TargetHazardousObject = null;
         targetPlayer = null;
         GrabWeaponTimer = 0;
         _targetWeapon = null;
         super();
      }
      
      public function IsPlayerUnavailable(param1:Player) : Boolean
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < UnavailablePlayers.length)
         {
            if(UnavailablePlayers[_loc2_][0] == param1)
            {
               return true;
            }
            _loc2_++;
         }
         return false;
      }
      
      public function UpdateUnavailableStuff() : void
      {
         var _loc1_:int = 0;
         if(IgnoreObjectCheckingTimer > 0)
         {
            IgnoreObjectCheckingTimer -= 1;
         }
         _loc1_ = UnavailablePlayers.length - 1;
         while(_loc1_ >= 0)
         {
            UnavailablePlayers[_loc1_][1] += 1;
            if(UnavailablePlayers[_loc1_][1] >= UNAVAILABLE_PLAYER_TIMER)
            {
               UnavailablePlayers.splice(_loc1_,1);
            }
            _loc1_--;
         }
         _loc1_ = UnavailableWeapons.length - 1;
         while(_loc1_ >= 0)
         {
            UnavailableWeapons[_loc1_][1] += 1;
            if(UnavailableWeapons[_loc1_][1] >= 20)
            {
               UnavailableWeapons.splice(_loc1_,1);
            }
            _loc1_--;
         }
      }
      
      public function get TargetWeapon() : b2Body
      {
         return _targetWeapon;
      }
      
      public function set Phase(param1:int) : void
      {
         if(_phase != param1)
         {
            _phase = param1;
            if(_phase != INTERRUPTED && _phase != IDLE && _phase != SHOOT && _phase != CANCEL_AIM)
            {
               SetDelay();
            }
            else
            {
               _phaseDelay = 0;
            }
         }
      }
      
      public function get NextResultNode() : PathResultNode
      {
         return _nextResNode;
      }
      
      public function set PhaseDelay(param1:int) : void
      {
         _phaseDelay = param1;
      }
      
      public function get IgnoreObjectChecking() : Boolean
      {
         return IgnoreObjectCheckingTimer > 0;
      }
      
      public function set TargetWeapon(param1:b2Body) : void
      {
         _targetWeapon = param1;
         if(_targetWeapon == null)
         {
            GrabWeaponTimer = 0;
         }
      }
      
      public function get Phase() : int
      {
         return _phase;
      }
      
      public function SetDelay() : void
      {
         switch(Difficulty)
         {
            case EASY:
               _phaseDelay = 6 + Math.floor(Math.random() * 1.99);
               break;
            case MEDIUM:
               _phaseDelay = 3 + Math.floor(Math.random() * 1.99);
               break;
            case HARD:
               _phaseDelay = Math.floor(Math.random() * 2.99);
         }
      }
      
      public function set NextResultNode(param1:PathResultNode) : void
      {
         _nextResNode = param1;
      }
      
      public function get PhaseDelay() : int
      {
         return _phaseDelay;
      }
      
      public function IsWeaponUnavailable(param1:b2Body) : Boolean
      {
         var _loc2_:int = 0;
         _loc2_ = 0;
         while(_loc2_ < UnavailableWeapons.length)
         {
            if(UnavailableWeapons[_loc2_][0] == param1)
            {
               return true;
            }
            _loc2_++;
         }
         return false;
      }
      
      public function set TargetPlayer(param1:Player) : void
      {
         targetPlayer = param1;
         if(targetPlayer == null)
         {
            TargetInAim = false;
            TargetInSight = false;
            TargetHazardousObject = null;
         }
      }
      
      public function get TargetPlayer() : Player
      {
         return targetPlayer;
      }
   }
}

