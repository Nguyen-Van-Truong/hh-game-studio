package Code.Handler
{
   import Code.Box2D.Dynamics.*;
   import Code.Data.PathBind;
   import Code.Data.PathNode;
   import Code.Data.PathResultNode;
   import Code.Data.PathWebNode;
   import flash.display.MovieClip;
   import flash.geom.Point;
   import flash.utils.clearInterval;
   import flash.utils.setInterval;
   
   public class PathGrid
   {
      private var _seekBalance:Number = 4;
      
      private var _visitedNodes:Array;
      
      private var _Handler_Fires:Fires;
      
      private var _analyzeGridTimer:Number;
      
      private var _ladderBinds:Array;
      
      private var _sprintJumpBinds:Array;
      
      private var _nodes:Array;
      
      private var m_world:b2World;
      
      private var _diveBinds:Array;
      
      private var _jumpBinds:Array;
      
      private var _binds:Array;
      
      private var _parentalNodes:Array;
      
      private var _debug_mc:MovieClip;
      
      private var _players:Array;
      
      public function PathGrid()
      {
         _seekBalance = 4;
         super();
         _nodes = new Array();
         _binds = new Array();
         _debug_mc = new MovieClip();
         _visitedNodes = new Array();
         _parentalNodes = new Array();
         _analyzeGridTimer = setInterval(function():*
         {
            clearInterval(_analyzeGridTimer);
            _analyzeGridTimer = setInterval(AnalyzeGrid,500);
         },230);
      }
      
      public function get Nodes() : Array
      {
         return _nodes;
      }
      
      public function GenerateGraphic() : void
      {
         var _loc1_:int = 0;
         _debug_mc.graphics.clear();
         _debug_mc.graphics.lineStyle(2,16777215,0.2);
         _loc1_ = 0;
         while(_loc1_ < _nodes.length)
         {
            _debug_mc.graphics.drawCircle(_nodes[_loc1_].PosX,_nodes[_loc1_].PosY,4);
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < _binds.length)
         {
            _debug_mc.graphics.moveTo(_binds[_loc1_].SourceNode.PosX,_binds[_loc1_].SourceNode.PosY);
            _debug_mc.graphics.lineTo(_binds[_loc1_].TargetNode.PosX,_binds[_loc1_].TargetNode.PosY);
            _loc1_++;
         }
      }
      
      public function UpdatePathGrid() : void
      {
         var _loc1_:int = 0;
         _loc1_ = 0;
         while(_loc1_ < _parentalNodes.length)
         {
            _parentalNodes[_loc1_].CalculateParentLocation();
            _loc1_++;
         }
      }
      
      public function Stop() : void
      {
         clearInterval(_analyzeGridTimer);
      }
      
      public function AddNode(param1:PathNode) : void
      {
         _nodes.push(param1);
         _nodes[_nodes.length - 1].ListIndex = _nodes.length - 1;
         _visitedNodes.push(new PathWebNode());
      }
      
      public function set Nodes(param1:Array) : void
      {
         _nodes = param1;
      }
      
      public function GetNodeAt(param1:Number, param2:Number, param3:Number = 200) : PathNode
      {
         var _loc4_:Number = NaN;
         var _loc5_:int = 0;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         var _loc8_:Number = NaN;
         var _loc9_:int = 0;
         _loc4_ = param3;
         _loc5_ = -1;
         _loc9_ = 0;
         while(_loc9_ < _nodes.length)
         {
            _loc7_ = _nodes[_loc9_].PosY - param2;
            if(param2 < _nodes[_loc9_].PosY + 20)
            {
               _loc6_ = _nodes[_loc9_].PosX - param1;
               _loc8_ = Math.sqrt(_loc6_ * _loc6_ + _loc7_ * _loc7_);
               if(_loc8_ < _loc4_)
               {
                  _loc5_ = _loc9_;
                  _loc4_ = _loc8_;
               }
            }
            _loc9_++;
         }
         if(_loc5_ == -1)
         {
            return null;
         }
         return _nodes[_loc5_];
      }
      
      public function AnalyzeGrid() : void
      {
         var _loc1_:int = 0;
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         var _loc4_:Number = NaN;
         var _loc5_:int = 0;
         var _loc6_:Number = NaN;
         var _loc7_:Number = NaN;
         _loc1_ = 0;
         while(_loc1_ < _ladderBinds.length)
         {
            _ladderBinds[_loc1_][0].Blocked = false;
            _loc2_ = 0;
            while(_loc2_ <= 24)
            {
               if(m_world.GetDynamicBodyAt(_ladderBinds[_loc1_][1].x - 4,_ladderBinds[_loc1_][1].y + _loc2_,false) != null)
               {
                  _ladderBinds[_loc1_][0].Blocked = true;
                  _loc2_ = 99;
               }
               else if(m_world.GetDynamicBodyAt(_ladderBinds[_loc1_][1].x + 4,_ladderBinds[_loc1_][1].y + _loc2_,false) != null)
               {
                  _ladderBinds[_loc1_][0].Blocked = true;
                  _loc2_ = 99;
               }
               _loc2_ += 8;
            }
            _loc3_ = 0;
            while(_loc3_ < _players.length)
            {
               if(!_players[_loc3_].Bot)
               {
                  if(_players[_loc3_].State.HP > 0)
                  {
                     if(_players[_loc3_].PosY() < _ladderBinds[_loc1_][1].y + 40)
                     {
                        _loc4_ = Math.pow(_ladderBinds[_loc1_][1].x - _players[_loc3_].PosX(),2);
                        if(_loc4_ < 4900)
                        {
                           _ladderBinds[_loc1_][0].Blocked = true;
                        }
                     }
                  }
               }
               _loc3_++;
            }
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < _jumpBinds.length)
         {
            _jumpBinds[_loc1_].Blocked = false;
            if(JumpNodeBlocked(_jumpBinds[_loc1_].SourceNode,_jumpBinds[_loc1_].TargetNode))
            {
               _jumpBinds[_loc1_].Blocked = true;
            }
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < _diveBinds.length)
         {
            _diveBinds[_loc1_].Blocked = false;
            if(NodeBlocked(_diveBinds[_loc1_].SourceNode))
            {
               _diveBinds[_loc1_].Blocked = true;
            }
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < _sprintJumpBinds.length)
         {
            _sprintJumpBinds[_loc1_].Blocked = false;
            if(JumpNodeBlocked(_sprintJumpBinds[_loc1_].SourceNode,_sprintJumpBinds[_loc1_].TargetNode))
            {
               _sprintJumpBinds[_loc1_].Blocked = true;
            }
            else if(NodeBlocked(_sprintJumpBinds[_loc1_].SourceNode))
            {
               _sprintJumpBinds[_loc1_].Blocked = true;
            }
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < _nodes.length)
         {
            if(_Handler_Fires.PlayerPosInFire(_nodes[_loc1_].PosX,_nodes[_loc1_].PosY))
            {
               _nodes[_loc1_].InFire = true;
            }
            else
            {
               _nodes[_loc1_].InFire = false;
            }
            _nodes[_loc1_].IsHazard = false;
            _loc1_++;
         }
         _loc1_ = 0;
         while(_loc1_ < m_world.HazardsList.length)
         {
            if(m_world.HazardsList[_loc1_].GetUserData().objectData.IsHazard)
            {
               _loc5_ = 0;
               while(_loc5_ < _nodes.length)
               {
                  _loc6_ = m_world.HazardsList[_loc1_].GetPosition().x * 30 - _nodes[_loc5_].PosX;
                  if(Math.abs(_loc6_) <= 40)
                  {
                     _loc7_ = m_world.HazardsList[_loc1_].GetPosition().y * 30 - _nodes[_loc5_].PosY;
                     if(Math.abs(_loc7_) <= 40)
                     {
                        _nodes[_loc5_].IsHazard = true;
                     }
                  }
                  _loc5_++;
               }
            }
            _loc1_++;
         }
      }
      
      public function get DebugGraphic() : MovieClip
      {
         return _debug_mc;
      }
      
      public function get Binds() : Array
      {
         return _binds;
      }
      
      public function LinkPlayers(param1:Array) : void
      {
         _players = param1;
      }
      
      private function ShortenPath(param1:PathNode, param2:Number, param3:PathNode = null) : void
      {
         var _loc4_:PathNode = null;
         var _loc5_:int = 0;
         var _loc6_:PathBind = null;
         var _loc7_:Number = NaN;
         if(param3 != null)
         {
            _visitedNodes[param1.ListIndex].SourceNode = param3;
         }
         _visitedNodes[param1.ListIndex].Distance -= param2;
         _loc4_ = param1;
         _loc5_ = 0;
         while(_loc5_ < param1.Binds.length)
         {
            _loc6_ = _loc4_.Binds[_loc5_];
            if(_visitedNodes[_loc6_.TargetNode.ListIndex].SourceNode == _loc6_.SourceNode)
            {
               ShortenPath(_loc6_.TargetNode,param2);
            }
            else if(_visitedNodes[_loc6_.TargetNode.ListIndex].SourceNode != null)
            {
               _loc7_ = _visitedNodes[_loc4_.ListIndex].Distance + _loc6_.Distance;
               if(_loc7_ < _visitedNodes[_loc6_.TargetNode.ListIndex].Distance)
               {
                  ShortenPath(_loc6_.TargetNode,_visitedNodes[_loc6_.TargetNode.ListIndex].Distance - _loc7_,_loc4_);
               }
            }
            _loc5_++;
         }
      }
      
      public function GetNode(param1:String) : PathNode
      {
         var _loc2_:int = 0;
         param1 = param1.toUpperCase();
         _loc2_ = int(_nodes.length - 1);
         while(_loc2_ > 0)
         {
            if(_nodes[_loc2_].ID == param1)
            {
               return _nodes[_loc2_];
            }
            _loc2_--;
         }
         return null;
      }
      
      public function JumpNodeBlocked(param1:PathNode, param2:PathNode) : Boolean
      {
         var _loc3_:b2Body = null;
         var _loc4_:int = 0;
         var _loc5_:int = 0;
         if(Math.abs(param1.PosX - param2.PosX) < 25)
         {
            _loc4_ = -3;
            while(_loc4_ <= 3)
            {
               _loc5_ = -3;
               while(_loc5_ <= 3)
               {
                  _loc3_ = m_world.GetDynamicBodyAt(param2.PosX + _loc4_,param2.PosY + _loc5_,false);
                  if(_loc3_ != null)
                  {
                     return true;
                  }
                  _loc5_ += 6;
               }
               _loc4_ += 6;
            }
            return false;
         }
         return NodeBlocked(param2);
      }
      
      public function AddBind(param1:PathBind) : void
      {
         _nodes[param1.SourceNode.ListIndex].Binds.push(param1);
         _binds.push(param1);
      }
      
      public function UpdateSpecials() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Number = NaN;
         var _loc3_:Number = NaN;
         _parentalNodes = new Array();
         _loc1_ = 0;
         while(_loc1_ < _nodes.length)
         {
            _nodes[_loc1_].UpdateIsEndNode();
            if(_nodes[_loc1_].ParentBody != null)
            {
               _parentalNodes.push(_nodes[_loc1_]);
            }
            _loc1_++;
         }
         _ladderBinds = new Array();
         _jumpBinds = new Array();
         _sprintJumpBinds = new Array();
         _diveBinds = new Array();
         _loc1_ = 0;
         while(_loc1_ < _binds.length)
         {
            if(_binds[_loc1_].MovementType == PathBind.LADDER)
            {
               if(_binds[_loc1_].SourceNode.PosY < _binds[_loc1_].TargetNode.PosY)
               {
                  _loc2_ = Number(_binds[_loc1_].TargetNode.PosX);
                  _loc3_ = Number(_binds[_loc1_].SourceNode.PosY);
               }
               else
               {
                  _loc2_ = Number(_binds[_loc1_].SourceNode.PosX);
                  _loc3_ = Number(_binds[_loc1_].TargetNode.PosY);
               }
               _ladderBinds.push([_binds[_loc1_],new Point(_loc2_,_loc3_)]);
            }
            else if(_binds[_loc1_].MovementType == PathBind.SPRINTJUMP)
            {
               _sprintJumpBinds.push(_binds[_loc1_]);
            }
            else if(_binds[_loc1_].MovementType == PathBind.JUMP)
            {
               _jumpBinds.push(_binds[_loc1_]);
            }
            else if(_binds[_loc1_].MovementType == PathBind.DIVE)
            {
               _diveBinds.push(_binds[_loc1_]);
            }
            _loc1_++;
         }
      }
      
      public function NodeBlocked(param1:PathNode) : Boolean
      {
         var _loc2_:b2Body = null;
         var _loc3_:int = 0;
         var _loc4_:int = 0;
         _loc3_ = -3;
         while(_loc3_ <= 3)
         {
            _loc4_ = -3;
            while(_loc4_ <= 3)
            {
               _loc2_ = m_world.GetDynamicBodyAt(param1.PosX + _loc3_,param1.PosY + _loc4_,false);
               if(_loc2_ != null)
               {
                  if(!_loc2_.GetUserData().objectData.IsGlass && !_loc2_.GetUserData().objectData.Kickable)
                  {
                     return true;
                  }
               }
               _loc4_ += 6;
            }
            _loc3_ += 6;
         }
         return false;
      }
      
      public function set Binds(param1:Array) : void
      {
         _binds = param1;
      }
      
      public function RemoveNodes(param1:String) : void
      {
         var _loc2_:int = 0;
         var _loc3_:int = 0;
         param1 = param1.toUpperCase();
         _loc2_ = int(_nodes.length - 1);
         while(_loc2_ > 0)
         {
            if(_nodes[_loc2_].ID == param1)
            {
               _loc3_ = int(_binds.length - 1);
               while(_loc3_ > 0)
               {
                  if(_binds[_loc3_].SourceNode == _nodes[_loc2_] || _binds[_loc3_].TargetNode == _nodes[_loc2_])
                  {
                     _binds[_loc3_].SourceNode.RemoveBind(_binds[_loc3_]);
                     _binds[_loc3_].TargetNode.RemoveBind(_binds[_loc3_]);
                     _binds.splice(_loc3_,1);
                  }
                  _loc3_--;
               }
               _nodes.splice(_loc2_,1);
            }
            _loc2_--;
         }
      }
      
      public function UpdateHandlers(param1:Fires, param2:b2World) : void
      {
         _Handler_Fires = param1;
         m_world = param2;
      }
      
      public function GetPath(param1:PathNode, param2:PathNode, param3:Boolean = false) : Array
      {
         var _loc4_:Array = null;
         var _loc5_:int = 0;
         var _loc6_:Boolean = false;
         var _loc7_:Array = null;
         var _loc8_:Number = NaN;
         var _loc9_:PathNode = null;
         var _loc10_:int = 0;
         var _loc11_:PathBind = null;
         var _loc12_:Number = NaN;
         var _loc13_:PathNode = null;
         var _loc14_:int = 0;
         _loc4_ = new Array();
         _loc5_ = 0;
         while(_loc5_ < _visitedNodes.length)
         {
            _visitedNodes[_loc5_].Clear();
            _loc5_++;
         }
         if(param1 == null)
         {
            return _loc4_;
         }
         _loc6_ = false;
         if(param1.Avoid && !param3)
         {
            _loc6_ = true;
         }
         else
         {
            if(param2 == null)
            {
               return _loc4_;
            }
            if(param1 == param2)
            {
               return _loc4_;
            }
         }
         _loc7_ = new Array();
         _loc7_.push(param1);
         _visitedNodes[param1.ListIndex].Distance = 0;
         _loc8_ = 0;
         while(true)
         {
            _loc8_ += _seekBalance;
            ++_seekBalance;
            _loc5_ = int(_loc7_.length - 1);
            while(_loc5_ >= 0)
            {
               _loc9_ = _loc7_[_loc5_];
               if(_visitedNodes[_loc9_.ListIndex].Distance <= _loc8_)
               {
                  --_seekBalance;
                  if(_seekBalance < 1)
                  {
                     _seekBalance = 1;
                  }
                  _loc10_ = 0;
                  while(_loc10_ < _loc9_.Binds.length)
                  {
                     _loc11_ = _loc9_.Binds[_loc10_];
                     if(!_loc11_.Blocked)
                     {
                        _loc12_ = _visitedNodes[_loc9_.ListIndex].Distance + _loc11_.Distance;
                        if(_loc12_ < _visitedNodes[_loc11_.TargetNode.ListIndex].Distance)
                        {
                           if(_visitedNodes[_loc11_.TargetNode.ListIndex].SourceNode != null)
                           {
                              ShortenPath(_loc11_.TargetNode,_visitedNodes[_loc11_.TargetNode.ListIndex].Distance - _loc12_,_loc9_);
                           }
                           else
                           {
                              _visitedNodes[_loc11_.TargetNode.ListIndex].SourceNode = _loc9_;
                              _visitedNodes[_loc11_.TargetNode.ListIndex].Distance = _loc12_;
                              if(_loc11_.TargetNode.IsEndNode && (_loc11_.TargetNode == param2 || _loc6_ && !_loc11_.TargetNode.Avoid))
                              {
                                 _loc4_.push(new PathResultNode(_loc11_.TargetNode));
                                 _loc13_ = _visitedNodes[_loc11_.TargetNode.ListIndex].SourceNode;
                                 while(_loc13_ != null)
                                 {
                                    _loc4_.push(new PathResultNode(_loc13_));
                                    _loc13_ = _visitedNodes[_loc13_.ListIndex].SourceNode;
                                 }
                                 _loc14_ = 0;
                                 while(_loc14_ < _loc4_.length)
                                 {
                                    if(_loc14_ + 1 < _loc4_.length)
                                    {
                                       _loc4_[_loc14_].PrevBind = _loc4_[_loc14_ + 1].Node.GetBindTo(_loc4_[_loc14_].Node);
                                    }
                                    if(_loc14_ > 0)
                                    {
                                       _loc4_[_loc14_].NextBind = _loc4_[_loc14_].Node.GetBindTo(_loc4_[_loc14_ - 1].Node);
                                    }
                                    _loc14_++;
                                 }
                                 return _loc4_;
                              }
                              if(!_loc11_.TargetNode.Avoid || _loc6_)
                              {
                                 _loc7_.push(_loc11_.TargetNode);
                              }
                           }
                        }
                     }
                     _loc10_++;
                  }
                  _loc7_.splice(_loc5_,1);
                  if(_loc7_.length <= 0)
                  {
                     if(_loc6_)
                     {
                        return GetPath(param1,param2,true);
                     }
                     return _loc4_;
                  }
               }
               _loc5_--;
            }
         }
      }
      
      public function GetConnectedNodes() : Array
      {
         var _loc1_:Array = null;
         var _loc2_:int = 0;
         _loc1_ = new Array();
         _loc2_ = 0;
         while(_loc2_ < _visitedNodes.length)
         {
            if(_visitedNodes[_loc2_].SourceNode != null)
            {
               _loc1_.push(_visitedNodes[_loc2_].SourceNode);
            }
            _loc2_++;
         }
         return _loc1_;
      }
   }
}

