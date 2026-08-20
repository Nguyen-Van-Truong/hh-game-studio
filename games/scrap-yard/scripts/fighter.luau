--!strict
-- A4 fighter: original scrap-yard brawler. One script drives Vela (p1) and Rook (p2).
-- gs.get_velocity / gs.set_flip are new; call them only when the host has them.
local M = {}

local MOVE_SPEED = 7
local SPRINT_SPEED = 10
local GROUND_ACCEL = 48
local FRICTION = 96
local AIR_CONTROL = 0.55
local JUMP_SPEED = 11
local JUMP_CUT = 0.4
local COYOTE_TIME = 0.1
local JUMP_BUFFER = 0.1
local JUMP_LOCK = 8
local HITSTUN_TIME = 0.2
local SQUASH_TIME = 0.12
local SQUASH_SY = 0.75
local TAP_WINDOW = 12
local STAMINA_MAX = 60
local STAMINA_DRAIN = 2
local STAMINA_REGEN = 1
local MELEE_TIME = 0.16
local WALK_FRAME = 0.125
local MAX_HP = 5
local BAR_W = 1.5
local BAR_H = 0.25

local ART = {
  p1 = {
    idle = "a_000020",
    walk_a = "a_000021",
    walk_b = "a_000022",
    punch = "a_000023",
    crouch = "a_000024",
    hurt = "a_000025",
  },
  p2 = {
    idle = "a_000030",
    walk_a = "a_000031",
    walk_b = "a_000032",
    punch = "a_000033",
    crouch = "a_000034",
    hurt = "a_000035",
  },
}

local function slot_of(self)
  if self.props.slot == "p2" then
    return "p2"
  end
  return "p1"
end

local function act(self, name)
  return gs.action(name .. "_" .. slot_of(self))
end

local function vel_of(id)
  if gs.get_velocity ~= nil then
    local vx, vy = gs.get_velocity(id)
    if vx ~= nil then
      return vx, vy
    end
  end
  return nil, nil
end

-- gs.set_flip is new; keep the nil-guard until every host has it.
local function face(id, flip_left)
  if gs.set_flip ~= nil then
    gs.set_flip(id, flip_left, false)
  end
end

local function set_anim(self, key)
  local pack = ART[slot_of(self)]
  local id = pack[key]
  if id == nil then
    id = pack.idle
  end
  if self.state.anim == id then
    return
  end
  self.state.anim = id
  if gs.set_sprite ~= nil then
    gs.set_sprite(self.id, { ["$asset"] = id })
  elseif gs.set_component ~= nil then
    gs.set_component(self.id, "Sprite", { asset = id })
  end
end

-- Walkable tops (cell y + 1). Avoids a per-frame raycast against the hull.
local function over_plat(x, y, top, x0, x1)
  return y >= top - 0.125 and y <= top + 0.375 and x >= x0 - 0.25 and x <= x1 + 0.25
end

local function grounded_at(x, y)
  if over_plat(x, y, 1, 0, 40) then
    return true
  end
  if over_plat(x, y, 3, 17, 23) then
    return true
  end
  if over_plat(x, y, 4, 1, 4) or over_plat(x, y, 4, 36, 39) then
    return true
  end
  if over_plat(x, y, 6, 5, 15) or over_plat(x, y, 6, 18, 21) or over_plat(x, y, 6, 26, 35) then
    return true
  end
  if over_plat(x, y, 9, 1, 4) or over_plat(x, y, 9, 36, 39) then
    return true
  end
  if over_plat(x, y, 11, 6, 15) or over_plat(x, y, 11, 16, 21) or over_plat(x, y, 11, 24, 34) then
    return true
  end
  if over_plat(x, y, 14, 1, 4) or over_plat(x, y, 14, 36, 39) then
    return true
  end
  if over_plat(x, y, 16, 5, 13) or over_plat(x, y, 16, 15, 23) or over_plat(x, y, 16, 26, 34) then
    return true
  end
  return false
end

local function follow_bar(id, x, y, sx, z)
  if id == nil then
    return
  end
  gs.set_transform(id, { x = x, y = y, sx = sx, sy = BAR_H, z_index = z })
end

local function respawn(self)
  local sx = self.state.spawn_x
  local sy = self.state.spawn_y
  if sx == nil then
    sx = 6
  end
  if sy == nil then
    sy = 2.25
  end
  self.state.hp = MAX_HP
  self.state.hitstun = 0
  self.state.vx = 0
  self.state.vy = 0
  self.state.coyote = 0
  self.state.jump_buf = 0
  gs.set_pos(self.id, sx, sy)
  gs.velocity(self.id, 0, 0)
  gs.emit("FighterDown", { id = self.id, slot = slot_of(self), reason = "fall" })
end

local function take_hit(self, amount)
  local hp = self.state.hp
  if hp == nil then
    hp = MAX_HP
  end
  hp = hp - amount
  if hp < 0 then
    hp = 0
  end
  self.state.hp = hp
  self.state.hitstun = HITSTUN_TIME
  local x, y = gs.get_pos(self.id)
  if x ~= nil and y ~= nil then
    follow_bar(self.props.bar_back, x, y + 2.25, BAR_W, 8)
    follow_bar(self.props.bar_fill, x, y + 2.25, BAR_W * (hp / MAX_HP), 9)
  end
  if hp <= 0 then
    respawn(self)
    return true
  end
  return false
end

local function try_melee(self, facing)
  local reach = 0.95
  if self.state.weapon == "pipe" then
    reach = 1.55
  end
  local ov = gs.overlaps(self.id)
  local ids = ov.ids
  if ids == nil then
    return
  end
  local x = gs.get_pos(self.id)
  if x == nil then
    return
  end
  for i = 1, #ids do
    local other = ids[i]
    if other ~= self.id and gs.has_tag(other, "fighter") then
      local ox = gs.get_pos(other)
      if ox ~= nil then
        local dx = ox - x
        if dx * facing >= -0.05 and math.abs(dx) <= reach + 0.35 then
          local knock = 5.5
          if self.state.weapon == "pipe" then
            knock = 7.5
          end
          gs.impulse(other, facing * knock, 3.2)
          gs.add_tag(other, "pending_hit")
          gs.emit("Hit", { by = self.id, target = other, amount = 1 })
        end
      end
    end
  end
end

local function try_pickup(self)
  local ov = gs.overlaps(self.id)
  local ids = ov.ids
  if ids == nil then
    return
  end
  for i = 1, #ids do
    local id = ids[i]
    if gs.has_tag(id, "pickup") and not gs.has_tag(id, "taken") then
      if gs.has_tag(id, "pickup_blaster") then
        self.state.weapon = "blaster"
      elseif gs.has_tag(id, "pickup_bomb") then
        self.state.bombs = 1
      elseif gs.has_tag(id, "pickup_clock") then
        self.state.has_clock = 1
      else
        self.state.weapon = "pipe"
      end
      gs.add_tag(id, "taken")
      gs.set_pos(id, -8, -8)
      return
    end
  end
end

local function ai_steer(self, ax, jump, crouch, melee)
  if ax ~= 0 or jump > 0 or crouch > 0 or melee > 0 then
    return ax, jump, crouch, melee
  end
  if self.props.ai ~= true then
    return ax, jump, crouch, melee
  end
  local foe = self.state.foe
  if foe == nil then
    return ax, jump, crouch, melee
  end
  local x, y = gs.get_pos(self.id)
  local ox, oy = gs.get_pos(foe)
  if x == nil or ox == nil then
    return 0, 0, 0, 0
  end
  local dx = ox - x
  if math.abs(dx) > 1.1 then
    if dx > 0 then
      ax = 1
    else
      ax = -1
    end
  end
  if oy > y + 0.8 then
    jump = 1
  end
  if math.abs(dx) < 1.2 and math.abs(oy - y) < 0.8 then
    melee = 1
  end
  return ax, jump, crouch, melee
end

local function approach(cur, target, rate)
  if cur < target then
    local n = cur + rate
    if n > target then
      return target
    end
    return n
  end
  local n = cur - rate
  if n < target then
    return target
  end
  return n
end

function M.on_init(self)
  local st = self.state
  if st.hp == nil then
    st.hp = MAX_HP
  end
  if st.weapon == nil then
    st.weapon = "fists"
  end
  if st.facing == nil then
    if slot_of(self) == "p2" then
      st.facing = -1
    else
      st.facing = 1
    end
  end
  if st.jump_lock == nil then
    st.jump_lock = 0
  end
  if st.tap_age == nil then
    st.tap_age = 99
  end
  if st.tap_dir == nil then
    st.tap_dir = 0
  end
  if st.tap_up == nil then
    st.tap_up = 1
  end
  if st.sprint == nil then
    st.sprint = 0
  end
  if st.stamina == nil then
    st.stamina = STAMINA_MAX
  end
  if st.was_melee == nil then
    st.was_melee = 0
  end
  if st.was_jump == nil then
    st.was_jump = 0
  end
  if st.vx == nil then
    st.vx = 0
  end
  if st.vy == nil then
    st.vy = 0
  end
  if st.coyote == nil then
    st.coyote = 0
  end
  if st.jump_buf == nil then
    st.jump_buf = 0
  end
  if st.hitstun == nil then
    st.hitstun = 0
  end
  if st.squash == nil then
    st.squash = 0
  end
  if st.melee_left == nil then
    st.melee_left = 0
  end
  if st.walk_t == nil then
    st.walk_t = 0
  end
  if st.was_ground == nil then
    st.was_ground = 1
  end
  local x, y = gs.get_pos(self.id)
  if st.spawn_x == nil then
    st.spawn_x = x
  end
  if st.spawn_y == nil then
    st.spawn_y = y
  end
  st.last_x = x
  st.last_y = y
  if slot_of(self) == "p1" then
    st.foe = "e_000021"
  else
    st.foe = "e_000020"
  end
  face(self.id, st.facing < 0)
end

function M.on_event(self, name, data)
  if name ~= "Hit" or data == nil or data.target ~= self.id then
    return
  end
  local amount = 1
  if data.amount ~= nil then
    amount = data.amount
  end
  if gs.has_tag(self.id, "pending_hit") then
    gs.remove_tag(self.id, "pending_hit")
  end
  take_hit(self, amount)
end

function M.on_update(self)
  if gs.has_tag(self.id, "pending_hit") then
    gs.remove_tag(self.id, "pending_hit")
    if take_hit(self, 1) then
      return
    end
  end

  local x, y = gs.get_pos(self.id)
  if x == nil or y == nil then
    return
  end
  if y < 0 or y > 24 or x < -1 or x > 41 then
    respawn(self)
    return
  end

  local dt = gs.dt()
  local st = self.state
  local vx, vy = vel_of(self.id)
  if vx == nil then
    vx = st.vx or 0
  end
  if vy == nil then
    if st.last_y ~= nil and dt > 0 then
      vy = (y - st.last_y) / dt
    else
      vy = 0
    end
  end
  if vy < 2 and (st.vy or 0) > 2 and (st.jump_lock or 0) > 0 then
    vy = st.vy
  end
  st.last_x = x
  st.last_y = y

  local ax = act(self, "move_x")
  local jump = act(self, "jump")
  local crouch = act(self, "crouch")
  local melee = act(self, "melee")
  ax, jump, crouch, melee = ai_steer(self, ax, jump, crouch, melee)

  local stun = st.hitstun or 0
  if stun > 0 then
    stun = stun - dt
    if stun < 0 then
      stun = 0
    end
    st.hitstun = stun
    ax = 0
    jump = 0
    crouch = 0
    melee = 0
  end

  local lock = st.jump_lock or 0
  local on_floor = grounded_at(x, y) and vy <= 3
  if on_floor then
    st.coyote = COYOTE_TIME
    if st.was_ground == 0 and vy < -6 then
      st.squash = SQUASH_TIME
    end
    st.was_ground = 1
  else
    if st.coyote > 0 then
      st.coyote = st.coyote - dt
      if st.coyote < 0 then
        st.coyote = 0
      end
    end
    st.was_ground = 0
  end

  if jump > 0 then
    st.jump_buf = JUMP_BUFFER
  elseif st.jump_buf > 0 then
    st.jump_buf = st.jump_buf - dt
    if st.jump_buf < 0 then
      st.jump_buf = 0
    end
  end

  if ax ~= 0 then
    local dir = 1
    if ax < 0 then
      dir = -1
    end
    if st.tap_up == 1 and st.tap_age < TAP_WINDOW and st.tap_dir == dir then
      st.sprint = 1
    end
    st.tap_dir = dir
    st.tap_age = 0
    st.tap_up = 0
    st.facing = dir
  else
    st.tap_up = 1
    st.tap_age = st.tap_age + 1
    if st.tap_age > TAP_WINDOW then
      st.sprint = 0
    end
  end

  local did_jump = false
  if (on_floor or st.coyote > 0) and lock <= 0 and st.jump_buf > 0 then
    vy = JUMP_SPEED
    st.jump_lock = JUMP_LOCK
    st.jump_buf = 0
    st.coyote = 0
    st.was_ground = 0
    did_jump = true
  end
  if not did_jump and (st.was_jump or 0) > 0 and jump <= 0 and vy > 0.5 then
    vy = vy * JUMP_CUT
  end
  if lock > 0 then
    st.jump_lock = lock - 1
  end

  local stam = st.stamina or STAMINA_MAX
  if st.sprint > 0 and stam > 0 then
    stam = stam - STAMINA_DRAIN
    if stam <= 0 then
      stam = 0
      st.sprint = 0
    end
  else
    stam = stam + STAMINA_REGEN
    if stam > STAMINA_MAX then
      stam = STAMINA_MAX
    end
  end
  st.stamina = stam

  local speed = MOVE_SPEED
  if st.sprint > 0 and stam > 0 then
    speed = SPRINT_SPEED
  end

  if stun <= 0 then
    local target = ax * speed
    if on_floor then
      if ax == 0 then
        if crouch > 0 then
          vx = 0
        else
          vx = approach(vx, 0, FRICTION * dt)
        end
      else
        vx = approach(vx, target, GROUND_ACCEL * dt)
      end
      if not did_jump and lock <= 0 then
        vy = 0
      end
    else
      vx = approach(vx, target, GROUND_ACCEL * AIR_CONTROL * dt)
      if vx > 6.5 then
        vx = 6.5
      elseif vx < -6.5 then
        vx = -6.5
      end
    end
    if vy < -18 then
      vy = -18
    end
    st.vx = vx
    st.vy = vy
    gs.velocity(self.id, vx, vy)
  else
    st.vx = vx
  end

  local sx = 1.5
  local sy = 2.0
  local crouch_mul = 1
  local crouched = stun <= 0 and crouch > 0 and on_floor
  if crouched then
    crouch_mul = 0.75
    sy = 1.5
  end
  if st.squash > 0 then
    local t = st.squash / SQUASH_TIME
    sy = sy * (SQUASH_SY + (1 - SQUASH_SY) * (1 - t))
    st.squash = st.squash - dt
    if st.squash < 0 then
      st.squash = 0
    end
  end
  if st.body_sx ~= sx or st.body_sy ~= sy then
    st.body_sx = sx
    st.body_sy = sy
    gs.set_transform(self.id, { sx = sx, sy = sy })
  end
  if st.face_left ~= (st.facing < 0) then
    st.face_left = st.facing < 0
    face(self.id, st.facing < 0)
  end

  if stun <= 0 and melee > 0 and (st.was_melee or 0) <= 0 then
    if crouch > 0 then
      try_pickup(self)
    end
    try_melee(self, st.facing)
    st.melee_left = MELEE_TIME
  end
  if st.melee_left > 0 then
    st.melee_left = st.melee_left - dt
    if st.melee_left < 0 then
      st.melee_left = 0
    end
  end

  if stun > 0 then
    set_anim(self, "hurt")
  elseif st.melee_left > 0 then
    set_anim(self, "punch")
  elseif crouched or st.squash > 0 then
    set_anim(self, "crouch")
  elseif on_floor and math.abs(vx) > 0.4 then
    st.walk_t = (st.walk_t or 0) + dt
    if (math.floor(st.walk_t / WALK_FRAME) % 2) == 0 then
      set_anim(self, "walk_a")
    else
      set_anim(self, "walk_b")
    end
  else
    set_anim(self, "idle")
  end

  st.was_melee = melee
  st.was_jump = jump

  local hp = st.hp or MAX_HP
  if hp < 0 then
    hp = 0
  end
  if x ~= st.hud_x or y ~= st.hud_y or hp ~= st.hud_hp or crouch_mul ~= st.hud_c then
    st.hud_x = x
    st.hud_y = y
    st.hud_hp = hp
    st.hud_c = crouch_mul
    local by = y + 2.25 * crouch_mul
    follow_bar(self.props.bar_back, x, by, BAR_W, 8)
    follow_bar(self.props.bar_fill, x, by, BAR_W * (hp / MAX_HP), 9)
    if self.props.tag ~= nil then
      gs.set_transform(self.props.tag, { x = x, y = by + 0.5, sx = 0.25, sy = 0.25, z_index = 10 })
    end
  end
end

return M
