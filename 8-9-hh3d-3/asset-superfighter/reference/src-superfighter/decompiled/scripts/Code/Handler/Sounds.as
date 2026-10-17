package Code.Handler
{
   import flash.events.*;
   import flash.media.*;
   
   public class Sounds
   {
      private var _inMenu:Boolean = false;
      
      private var menu_channelTransform:SoundTransform;
      
      private var _sound_effect_volume:Number = 1;
      
      private var ambient_channel:SoundChannel;
      
      private var _mighty_sounds:Array;
      
      private var _sounds:Array;
      
      private var ambient_song:Sound;
      
      private var _Handler_Output:OutputTrace;
      
      private var ambient_channelTransform:SoundTransform;
      
      private var _lastSlowmo:Number = 0;
      
      private var menu_channel:SoundChannel;
      
      private var menu_song:Sound;
      
      public function Sounds(param1:OutputTrace)
      {
         _sounds = new Array();
         _mighty_sounds = new Array();
         _sound_effect_volume = 1;
         _inMenu = false;
         _lastSlowmo = 0;
         super();
         _Handler_Output = param1;
         menu_song = new superfighters_theme();
         ambient_song = new ambient_loop_1();
         playAmbient();
         stopAmbient();
         _sounds.push(["SHELLBOUNCE",2,[new shellbounce00(),new shellbounce01()]]);
         _sounds.push(["BARREL_EXPLOSION",1,[new explosion00(),new explosion01(),new explosion02(),new explosion03()]]);
         _sounds.push(["MELEE_HIT",1,[new punch00(),new punch01(),new punch02(),new punch03()]]);
         _sounds.push(["MELEE_SWING",4,[new svisch4(),new svisch6()]]);
         _sounds.push(["KICK_SWING",4,[new svisch4(),new svisch6()]]);
         _sounds.push(["KATANA_HIT",1,[new cut00(),new cut01(),new cut02()]]);
         _sounds.push(["KICK",1,[new punch00(),new punch01(),new punch02(),new punch03()]]);
         _sounds.push(["STAIRBOUNCE",1,[new punch00(),new punch01(),new punch02(),new punch03()]]);
         _sounds.push(["OBJECTBOUNCE",1,[new punch00(),new punch01(),new punch02(),new punch03()]]);
         _sounds.push(["JUMP",0.06,[new jump_00()]]);
         _sounds.push(["ROLL",0.75,[new roll()]]);
         _sounds.push(["DIVE_CATCH",0.7,[new dive_catch()]]);
         _sounds.push(["BODYFALL",1,[new punch00(),new punch01(),new punch02(),new punch03()]]);
         _sounds.push(["PISTOL_AIM",1,[new aim_small()]]);
         _sounds.push(["PISTOL_FIRE",1,[new gun00(),new gun01(),new gun02(),new gun03()]]);
         _sounds.push(["RIFLE_AIM",1,[new rifle_draw()]]);
         _sounds.push(["RIFLE_FIRE",1,[new rifle00(),new rifle01()]]);
         _sounds.push(["UZI_AIM",1,[new aim_small()]]);
         _sounds.push(["UZI_FIRE",1,[new uzi00(),new uzi01()]]);
         _sounds.push(["MAGNUM_AIM",1,[new aim_small()]]);
         _sounds.push(["MAGNUM_FIRE",1,[new magnum()]]);
         _sounds.push(["BAZOOKA_AIM",1,[new bazooka_aim()]]);
         _sounds.push(["BAZOOKA_FIRE",1,[new bazooka()]]);
         _sounds.push(["FLAMETHROWER_AIM",1,[new bazooka_aim()]]);
         _sounds.push(["FLAMETHROWER_FIRE",1,[new fireplosion()]]);
         _sounds.push(["SHOTGUN_AIM",1,[new shotgun_aim()]]);
         _sounds.push(["SHOTGUN_FIRE",1,[new shotgun00(),new shotgun01(),new shotgun02()]]);
         _sounds.push(["SHOTGUN_PUMP_P1",1,[new shotgun_pump_p1()]]);
         _sounds.push(["SHOTGUN_PUMP_P2",1,[new shotgun_pump_p2()]]);
         _sounds.push(["SNIPER_AIM",1,[new rifle_draw()]]);
         _sounds.push(["SNIPER_FIRE",1,[new sniper00(),new sniper01()]]);
         _sounds.push(["COMP_EXPLODE",0.6,[new comp_explode_01(),new comp_explode_02()]]);
         _sounds.push(["BULLET_HITWOOD",1,[new wood_impact00()]]);
         _sounds.push(["BULLET_HITDEFAULT",1,[new ric00()]]);
         _sounds.push(["BULLET_HITMETAL",0.65,[new bullet_hitmetal_01(),new bullet_hitmetal_02(),new bullet_hitmetal_03(),new bullet_hitmetal_04(),new bullet_hitmetal_05()]]);
         _sounds.push(["BULLET_HITFLESH",0.55,[new bullet_hit_1(),new bullet_hit_2(),new bullet_hit_3()]]);
         _sounds.push(["NOAMMO_LIGHT",1,[new outofammo_light()]]);
         _sounds.push(["NOAMMO_HEAVY",1,[new outofammo_heavy()]]);
         _sounds.push(["ROCKET_EXPLOSION",1,[new explosion00(),new explosion01(),new explosion02(),new explosion03()]]);
         _sounds.push(["BUSTWOOD",1,[new bustwood_1(),new bustwood_2()]]);
         _sounds.push(["FIREBURST",1,[new fireplosion()]]);
         _sounds.push(["MELEE_GRAB",1,[new katana_01()]]);
         _sounds.push(["GRENADE_SAFE",1,[new grenade_safe()]]);
         _sounds.push(["HEARTBEAT",1.5,[new heartbeat()]]);
         _sounds.push(["GIB",1,[new gib_00()]]);
         _sounds.push(["GET_HEALTH",0.5,[new getHealth_00()]]);
         _sounds.push(["BUSTGLASS",1,[new glass_1()]]);
         _sounds.push(["BUSTMOLOTOV",1,[new glass_2()]]);
         _sounds.push(["ELECTRIC_SPARK",0.4,[new voltage_02()]]);
         _sounds.push(["GROOVY",0.6,[new groovy00()]]);
         _sounds.push(["WILHELM",1,[new wilhelm()]]);
         _mighty_sounds.push(["ACCEPT",1,[new accept_02()]]);
         _mighty_sounds.push(["CANCEL",1,[new cancel_02()]]);
         _Handler_Output.Trace("Sounds Created");
      }
      
      public function ChangeEffectVolume(param1:Number) : void
      {
         _sound_effect_volume += param1;
         if(_sound_effect_volume > 1)
         {
            _sound_effect_volume = 1;
         }
         if(_sound_effect_volume < 0)
         {
            _sound_effect_volume = 0;
         }
         menu_channelTransform = menu_channel.soundTransform;
         menu_channelTransform.volume = _sound_effect_volume;
         menu_channel.soundTransform = menu_channelTransform;
      }
      
      public function set InMenu(param1:Boolean) : void
      {
         if(_inMenu != param1)
         {
            _inMenu = param1;
            if(param1)
            {
               stopAmbient();
               playMusic();
            }
            else
            {
               stopMusic();
               playAmbient();
            }
         }
      }
      
      private function stopMusic() : void
      {
         menu_channel.stop();
         menu_channel.removeEventListener(Event.SOUND_COMPLETE,loopMusic);
      }
      
      public function get InMenu() : Boolean
      {
         return _inMenu;
      }
      
      private function setAmbientVolume() : void
      {
         ambient_channelTransform = ambient_channel.soundTransform;
         ambient_channelTransform.volume = _sound_effect_volume * _lastSlowmo * 0.1;
         ambient_channel.soundTransform = ambient_channelTransform;
      }
      
      private function playMusic() : void
      {
         menu_channel = menu_song.play();
         menu_channel.addEventListener(Event.SOUND_COMPLETE,loopMusic);
         menu_channelTransform = menu_channel.soundTransform;
         menu_channelTransform.volume = _sound_effect_volume;
         menu_channel.soundTransform = menu_channelTransform;
      }
      
      private function playAmbient() : void
      {
         ambient_channel = ambient_song.play();
         ambient_channel.addEventListener(Event.SOUND_COMPLETE,loopAmbient);
         setAmbientVolume();
      }
      
      private function loopAmbient(param1:Event) : void
      {
         stopAmbient();
         playAmbient();
      }
      
      public function PlaySound(param1:String, param2:Number, param3:Number) : void
      {
         var _loc4_:SoundChannel = null;
         var _loc5_:String = null;
         var _loc6_:int = 0;
         var _loc7_:SoundTransform = null;
         if(param1 == "" || param1.toUpperCase() == "NONE" || _sound_effect_volume <= 0 || InMenu)
         {
            return;
         }
         _loc5_ = param1.toUpperCase();
         _loc6_ = 0;
         while(_loc6_ < _sounds.length)
         {
            if(_sounds[_loc6_][0] == _loc5_)
            {
               if(_sounds[_loc6_][2].length > 1)
               {
                  _loc4_ = _sounds[_loc6_][2][Math.round(Math.random() * (_sounds[_loc6_][2].length - 1))].play();
               }
               else
               {
                  _loc4_ = _sounds[_loc6_][2][0].play();
               }
               _loc7_ = _loc4_.soundTransform;
               _loc7_.volume = _sounds[_loc6_][1] * _sound_effect_volume;
               _loc4_.soundTransform = _loc7_;
               return;
            }
            _loc6_++;
         }
         _Handler_Output.Trace("Sound \'" + param1.toUpperCase() + "\' not found");
      }
      
      private function loopMusic(param1:Event) : void
      {
         stopMusic();
         playMusic();
      }
      
      public function StopAllSounds() : void
      {
         SoundMixer.stopAll();
      }
      
      public function Update(param1:Number) : void
      {
         if(!_inMenu)
         {
            if(_lastSlowmo != param1)
            {
               _lastSlowmo = param1;
               setAmbientVolume();
            }
         }
      }
      
      public function ChangeVolume(param1:Number) : void
      {
         var _loc2_:SoundTransform = null;
         _loc2_ = new SoundTransform();
         _loc2_.volume = param1;
         SoundMixer.soundTransform = _loc2_;
      }
      
      public function PlaySoundAt(param1:String, param2:Number, param3:Number) : void
      {
         PlaySound(param1,param2,param3);
      }
      
      public function set SoundEffectVolume(param1:Number) : void
      {
         _sound_effect_volume = param1;
      }
      
      private function stopAmbient() : void
      {
         ambient_channel.stop();
         ambient_channel.removeEventListener(Event.SOUND_COMPLETE,loopAmbient);
      }
      
      public function PlayMightySound(param1:String) : void
      {
         var _loc2_:SoundChannel = null;
         var _loc3_:String = null;
         var _loc4_:int = 0;
         var _loc5_:SoundTransform = null;
         _loc3_ = param1.toUpperCase();
         _loc4_ = 0;
         while(_loc4_ < _mighty_sounds.length)
         {
            if(_mighty_sounds[_loc4_][0] == _loc3_)
            {
               if(_mighty_sounds[_loc4_][2].length > 1)
               {
                  _loc2_ = _mighty_sounds[_loc4_][2][Math.round(Math.random() * (_mighty_sounds[_loc4_][2].length - 1))].play();
               }
               else
               {
                  _loc2_ = _mighty_sounds[_loc4_][2][0].play();
               }
               _loc5_ = _loc2_.soundTransform;
               _loc5_.volume = _mighty_sounds[_loc4_][1] * _sound_effect_volume;
               _loc2_.soundTransform = _loc5_;
               return;
            }
            _loc4_++;
         }
         _Handler_Output.Trace("MightySound \'" + param1.toUpperCase() + "\' not found");
      }
      
      public function get SoundEffectVolume() : Number
      {
         return _sound_effect_volume;
      }
      
      public function PlaySoundAt_Box2DScale(param1:String, param2:Number, param3:Number) : void
      {
         PlaySoundAt(param1,param2 * 30,param3 * 30);
      }
   }
}

