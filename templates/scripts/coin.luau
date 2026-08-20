--!strict
local M = {}

function M.on_event(self, name, data)
  if name ~= "collision_enter" then
    return
  end
  if gs.has_tag(data.other, "player") then
    gs.emit("CoinPicked", { coin = self.id })
    gs.destroy(self.id)
  end
end

return M
