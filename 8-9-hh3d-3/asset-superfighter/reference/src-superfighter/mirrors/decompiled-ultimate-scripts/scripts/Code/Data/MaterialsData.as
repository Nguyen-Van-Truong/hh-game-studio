package Code.Data
{
   public class MaterialsData
   {
      private var _metal:MaterialData;
      
      private var _wood:MaterialData;
      
      private var _paper:MaterialData;
      
      private var _spark:MaterialData;
      
      private var _beachball:MaterialData;
      
      private var _ragdoll:MaterialData;
      
      private var _ground:MaterialData;
      
      private var _shell:MaterialData;
      
      private var _electric_lamp:MaterialData;
      
      private var _glass:MaterialData;
      
      public function MaterialsData()
      {
         _wood = new MaterialData("wood",3,0.6,0.3,"wood",["ANYTHING"],"BULLET_HITDEFAULT","BULLET_HITWOOD","");
         _metal = new MaterialData("metal",10,0.4,0.1,"metal",["METAL"],"BULLET_HITMETAL","BULLET_HITMETAL","");
         _paper = new MaterialData("paper",5,0.6,0.1,"PAPER_HIT",["ANYTHING"],"PAPER_HIT","BULLET_HITDEFAULT","");
         _shell = new MaterialData("shell",10,0.4,0.1,"",[""],"","","SHELLBOUNCE");
         _ground = new MaterialData("ground",1,0.5,0.2,"",[""],"BULLET_HITDEFAULT","BULLET_HITDEFAULT","");
         _ragdoll = new MaterialData("ragdoll",10,0.4,0.1,"PARTICLE_BLOOD",["ANYTHING"],"PARTICLE_BLOOD","BULLET_HITFLESH","");
         _glass = new MaterialData("glass",3,0.4,0.2,"",[""],"","","");
         _beachball = new MaterialData("beachball",0.6,0.4,0.7,"",[""],"BULLET_HITDEFAULT","BULLET_HITDEFAULT","");
         _electric_lamp = new MaterialData("electric_lamp",3,0.4,0.2,"",[""],"ELECTRIC_SPARK","ELECTRIC_SPARK","");
         _spark = new MaterialData("spark",1,0.1,1,"",[""],"","","");
         super();
      }
      
      public function get Beachball() : MaterialData
      {
         return _beachball.Copy();
      }
      
      public function get Ragdoll() : MaterialData
      {
         return _ragdoll.Copy();
      }
      
      public function get Spark() : MaterialData
      {
         return _spark.Copy();
      }
      
      public function get Wood() : MaterialData
      {
         return _wood.Copy();
      }
      
      public function get Glass() : MaterialData
      {
         return _glass.Copy();
      }
      
      public function get Shell() : MaterialData
      {
         return _shell.Copy();
      }
      
      public function get Metal() : MaterialData
      {
         return _metal.Copy();
      }
      
      public function get Paper() : MaterialData
      {
         return _paper.Copy();
      }
      
      public function get Ground() : MaterialData
      {
         return _ground.Copy();
      }
      
      public function get ElectricLamp() : MaterialData
      {
         return _electric_lamp.Copy();
      }
   }
}

