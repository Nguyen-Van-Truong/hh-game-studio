--!strict
-- 2D platformer player: gs.action("move_x") + grounded jump.
local M = {}

local MOVE_SPEED = 6
local JUMP_SPEED = 8
local JUMP_LOCK_FRAMES = 10

function M.on_init(self)
  if self.state.jump_lock == nil then
    self.state.jump_lock = 0
  end
  gs.camera_follow(self.id)
end

function M.on_update(self)
  local ax = gs.action("move_x")
  local x, y = gs.get_pos(self.id)
  if x == nil or y == nil then
    return
  end

  local lock = self.state.jump_lock
  if lock == nil then
    lock = 0
  end

  -- Cast from just below the box so the ray does not hit self.
  local ray = gs.raycast(x, y - 0.55, x, y - 0.95)
  local grounded = ray ~= nil and ray.hit ~= nil and ray.hit.id ~= self.id

  if gs.action("jump") > 0 and grounded and lock <= 0 then
    gs.impulse(self.id, 0, JUMP_SPEED)
    self.state.jump_lock = JUMP_LOCK_FRAMES
  elseif grounded and lock <= 0 then
    -- No get_velocity: while standing, vy 0 is the physics rest value.
    gs.velocity(self.id, ax * MOVE_SPEED, 0)
  elseif ax ~= 0 then
    gs.impulse(self.id, ax * 1.2, 0)
  end

  if lock > 0 then
    self.state.jump_lock = lock - 1
  end
end

return M
