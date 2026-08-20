--!strict
-- Fixed camera: the whole 40 x 22 yard stays in one shot.
local M = {}

function M.on_init(self)
  local cam = self.props.camera
  if cam == nil then
    cam = "e_000001"
  end
  if gs.exists(cam) then
    gs.set_pos(cam, 20, 11)
  end
end

return M
