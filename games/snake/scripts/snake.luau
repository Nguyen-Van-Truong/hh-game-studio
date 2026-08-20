--!strict
-- Classic Snake: grid step, grow on food, die on wall/self.
local M = {}

local STEP = 0.15
local MIN_X = 1
local MAX_X = 14
local MIN_Y = 1
local MAX_Y = 10
local FOOD_ID = "e_000011"
local BODY_IDS = { "e_000012", "e_000013", "e_000014", "e_000015" }
local PARK_X = -20
local PARK_Y = -20

local function cell(v: number): number
  return math.floor(v + 0.5)
end

local function is_wall(x: number, y: number): boolean
  return x < MIN_X or x > MAX_X or y < MIN_Y or y > MAX_Y
end

local function body_len(self): number
  local body = self.state.body
  if type(body) ~= "table" then
    return 0
  end
  return #body
end

local function segment_xy(self, index: number): (number?, number?)
  local body = self.state.body
  if type(body) ~= "table" then
    return nil, nil
  end
  local seg = body[index]
  if type(seg) ~= "table" then
    return nil, nil
  end
  local x = seg.x
  local y = seg.y
  if type(x) ~= "number" or type(y) ~= "number" then
    return nil, nil
  end
  return x, y
end

local function occupies(self, x: number, y: number, skip_tail: boolean): boolean
  if self.state.x == x and self.state.y == y then
    return true
  end
  local n = body_len(self)
  local start = 1
  if skip_tail and n >= 1 then
    start = 2
  end
  for i = start, n do
    local sx, sy = segment_xy(self, i)
    if sx == x and sy == y then
      return true
    end
  end
  return false
end

local function sync_body(self)
  local n = body_len(self)
  for i, id in ipairs(BODY_IDS) do
    if gs.has_tag(id, "body") then
      if i <= n then
        local sx, sy = segment_xy(self, i)
        if sx ~= nil and sy ~= nil then
          gs.set_pos(id, sx, sy)
        else
          gs.set_pos(id, PARK_X, PARK_Y)
        end
      else
        gs.set_pos(id, PARK_X, PARK_Y)
      end
    end
  end
end

local function place_food(self, food_id: string)
  for x = MIN_X, MAX_X do
    for y = MIN_Y, MAX_Y do
      if not occupies(self, x, y, false) then
        gs.set_pos(food_id, x, y)
        return
      end
    end
  end
end

local function apply_input(self)
  local ax = gs.action("move_x")
  local ay = gs.action("move_y")
  local cdx = self.state.dx
  local cdy = self.state.dy
  if type(cdx) ~= "number" then
    cdx = 1
  end
  if type(cdy) ~= "number" then
    cdy = 0
  end
  local ndx = cdx
  local ndy = cdy
  if ax ~= 0 then
    local sx = 1
    if ax < 0 then
      sx = -1
    end
    if sx ~= -cdx or cdy ~= 0 then
      ndx = sx
      ndy = 0
    end
  end
  if ay ~= 0 then
    local sy = 1
    if ay < 0 then
      sy = -1
    end
    if sy ~= -cdy or cdx ~= 0 then
      ndx = 0
      ndy = sy
    end
  end
  self.state.dx = ndx
  self.state.dy = ndy
end

local function die(self)
  self.state.dead = true
  gs.emit("SnakeDied", { head = self.id })
end

local function step_cell(self)
  local dx = self.state.dx
  local dy = self.state.dy
  local hx = self.state.x
  local hy = self.state.y
  if type(dx) ~= "number" or type(dy) ~= "number" then
    return
  end
  if type(hx) ~= "number" or type(hy) ~= "number" then
    return
  end
  local nx = hx + dx
  local ny = hy + dy
  if is_wall(nx, ny) then
    die(self)
    return
  end

  local ate = false
  if gs.has_tag(FOOD_ID, "food") then
    local fx, fy = gs.get_pos(FOOD_ID)
    if fx ~= nil and fy ~= nil and cell(fx) == nx and cell(fy) == ny then
      ate = true
    end
  end

  if occupies(self, nx, ny, not ate) then
    die(self)
    return
  end

  local body = self.state.body
  if type(body) ~= "table" then
    body = {}
    self.state.body = body
  end
  table.insert(body, { x = hx, y = hy })
  if not ate then
    table.remove(body, 1)
  else
    gs.emit("FoodEaten", { food = FOOD_ID })
    self.state.x = nx
    self.state.y = ny
    gs.set_pos(self.id, nx, ny)
    place_food(self, FOOD_ID)
    sync_body(self)
    return
  end

  self.state.x = nx
  self.state.y = ny
  gs.set_pos(self.id, nx, ny)
  sync_body(self)
end

function M.on_init(self)
  if self.state.acc == nil then
    self.state.acc = 0
  end
  if self.state.dx == nil then
    self.state.dx = 1
  end
  if self.state.dy == nil then
    self.state.dy = 0
  end
  if self.state.dead == nil then
    self.state.dead = false
  end
  local x, y = gs.get_pos(self.id)
  if x ~= nil and y ~= nil then
    self.state.x = cell(x)
    self.state.y = cell(y)
  else
    self.state.x = 5
    self.state.y = 6
  end
  if type(self.state.body) ~= "table" then
    local hx = self.state.x
    local hy = self.state.y
    if type(hx) == "number" and type(hy) == "number" and hx >= MIN_X + 2 then
      self.state.body = {
        { x = hx - 2, y = hy },
        { x = hx - 1, y = hy },
      }
    else
      self.state.body = {}
    end
  end
  sync_body(self)
end

function M.on_update(self)
  if self.state.dead == true then
    return
  end
  apply_input(self)
  local acc = self.state.acc
  if type(acc) ~= "number" then
    acc = 0
  end
  acc = acc + gs.dt()
  self.state.acc = acc
  self.state.frame = gs.time().frame
  if acc < STEP then
    return
  end
  self.state.acc = acc - STEP
  step_cell(self)
end

return M
