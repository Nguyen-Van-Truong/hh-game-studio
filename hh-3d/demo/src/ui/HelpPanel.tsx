type HelpPanelProps = {
  open: boolean;
  onClose: () => void;
  onShowStatic: () => void;
};

export function HelpPanel({ open, onClose, onShowStatic }: HelpPanelProps) {
  if (!open) {
    return null;
  }

  return (
    <aside
      id="hon-gio-help"
      className="help-panel"
      role="dialog"
      aria-labelledby="help-title"
    >
      <div className="object-card-head">
        <h2 id="help-title">Cách đi</h2>
        <button type="button" className="ui-button" onClick={onClose}>
          Đóng
        </button>
      </div>
      <ul className="help-list">
        <li>Bấm vào cảnh — khóa chuột</li>
        <li>Chuột trái/phải — quay; xuống nhìn đất, lên nhìn trời</li>
        <li>WASD hoặc mũi tên — đi / strafe theo hướng nhìn</li>
        <li>Space — nhảy</li>
        <li>Shift — chạy</li>
        <li>Cuộn chuột — gần / xa</li>
        <li>E — lên / xuống thuyền</li>
        <li>Sau khi khóa chuột: click trái hoặc F — đấm (chỉ pose, chưa trúng)</li>
        <li>Enter — chat; chữ hiện trực tiếp trên đầu nhân vật</li>
        <li>Esc — thả chuột, rồi đóng thẻ</li>
        <li>Chơi theo sát người; Toàn cảnh xem cả đảo</li>
      </ul>
      <p className="help-note">
        Đây là diorama WebGL nhỏ: đi bộ trên đảo và chèo thúng trong vịnh.
        Không phải thành phố, bản đồ thật, hay game thế giới mở.
      </p>
      <button type="button" className="ui-button" onClick={onShowStatic}>
        Xem bản tĩnh
      </button>
    </aside>
  );
}
