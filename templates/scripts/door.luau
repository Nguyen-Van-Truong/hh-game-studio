--!strict
local M = {}

function M.on_init(self)
  -- self.props từ Script component (5.4): locked, key_tag, open_sprite
  if self.state.locked == nil then
    self.state.locked = self.props.locked
  end
end

function M.on_event(self, name, data)
  if name ~= "collision_enter" then return end
  if not self.state.locked then return end
  -- key_pickup.luau đã gs.add_tag(player, self.props.key_tag)
  if gs.has_tag(data.other, "player")
     and gs.has_tag(data.other, self.props.key_tag) then
    self.state.locked = false
    gs.set_sprite(self.id, self.props.open_sprite)
    gs.set_component(self.id, "Collider2D", { is_sensor = true })
    gs.emit("DoorOpened", { door = self.id, by = data.other })
  end
end

return M
