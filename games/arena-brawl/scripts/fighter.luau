--!strict
-- Stick-ring scrap: two colored fighters, punch on overlap, jump, knockback.
local M = {}

local MOVE_SPEED = 6
local JUMP_SPEED = 8
local JUMP_LOCK_FRAMES = 10
local HIT_IX = 6
local HIT_IY = 4

local function on_hit_self(self)
  local hp = self.state.hp
  if hp == nil then
    hp = 3
  end
  hp = hp - 1
  self.state.hp = hp
  if hp <= 0 then
    gs.emit("FighterDown", { id = self.id })
    gs.destroy(self.id)
    return true
  end
  return false
end

local function try_attack(self)
  local facing = self.state.facing
  if facing == nil or facing == 0 then
    facing = 1
  end
  local ov = gs.overlaps(self.id)
  local ids = ov.ids
  if ids == nil then
    return
  end
  local x, y = gs.get_pos(self.id)
  if x == nil or y == nil then
    return
  end
  for i = 1, #ids do
    local other = ids[i]
    if other ~= self.id and gs.has_tag(other, "fighter") then
      local ox, oy = gs.get_pos(other)
      if ox ~= nil and oy ~= nil then
        local dx = ox - x
        if dx * facing >= 0 then
          gs.impulse(other, facing * HIT_IX, HIT_IY)
          gs.emit("Hit", { by = self.id, target = other })
          -- gs.emit is play_events only; mailbox delivers Hit to the other instance.
          gs.add_tag(other, "pending_hit")
        end
      end
    end
  end
end

function M.on_init(self)
  if self.state.hp == nil then
    self.state.hp = 3
  end
  if self.state.jump_lock == nil then
    self.state.jump_lock = 0
  end
  if self.state.was_attack == nil then
    self.state.was_attack = 0
  end
  if self.state.facing == nil then
    if self.props.team == "b" then
      self.state.facing = -1
    else
      self.state.facing = 1
    end
  end
end

function M.on_event(self, name, data)
  if name ~= "Hit" or data == nil then
    return
  end
  if data.target ~= self.id then
    return
  end
  if gs.has_tag(self.id, "pending_hit") then
    gs.remove_tag(self.id, "pending_hit")
  end
  on_hit_self(self)
end

local function slot_of(self)
  if self.props.team == "b" then
    return "p2"
  end
  return "p1"
end

function M.on_update(self)
  local stunned = false
  if gs.has_tag(self.id, "pending_hit") then
    gs.remove_tag(self.id, "pending_hit")
    if on_hit_self(self) then
      return
    end
    stunned = true
  end

  local slot = slot_of(self)
  local ax = gs.action("move_x_" .. slot)
  local x, y = gs.get_pos(self.id)
  if x == nil or y == nil then
    return
  end

  if ax ~= 0 then
    if ax > 0 then
      self.state.facing = 1
    else
      self.state.facing = -1
    end
  end

  local lock = self.state.jump_lock
  if lock == nil then
    lock = 0
  end

  -- Cast from just below the box so the ray does not hit self.
  local ray = gs.raycast(x, y - 0.55, x, y - 0.95)
  local grounded = ray ~= nil and ray.hit ~= nil and ray.hit.id ~= self.id

  if gs.action("jump_" .. slot) > 0 and grounded and lock <= 0 then
    gs.impulse(self.id, 0, JUMP_SPEED)
    self.state.jump_lock = JUMP_LOCK_FRAMES
  elseif grounded and lock <= 0 then
    gs.velocity(self.id, ax * MOVE_SPEED, 0)
  elseif ax ~= 0 then
    gs.impulse(self.id, ax * 1.2, 0)
  end

  if lock > 0 then
    self.state.jump_lock = lock - 1
  end

  local pressed = gs.action("attack_" .. slot)
  local was = self.state.was_attack
  if was == nil then
    was = 0
  end
  if not stunned and pressed > 0 and was <= 0 then
    try_attack(self)
  end
  self.state.was_attack = pressed
end

return M
