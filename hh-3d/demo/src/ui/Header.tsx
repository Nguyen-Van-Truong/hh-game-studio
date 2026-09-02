type HeaderProps = {
  status: string;
  qualityLabel: string;
  qualityPressed: boolean;
  helpOpen: boolean;
  onToggleQuality: () => void;
  onToggleHelp: () => void;
};

export function Header({
  status,
  qualityLabel,
  qualityPressed,
  helpOpen,
  onToggleQuality,
  onToggleHelp,
}: HeaderProps) {
  return (
    <header className="top-bar">
      <p className="site-mark">Hòn Gió</p>
      <p className="site-status">{status}</p>
      <button
        type="button"
        className="bar-button"
        title={`Chất lượng hình ảnh: ${qualityLabel.toLowerCase()}`}
        aria-label={`Chất lượng hình ảnh: ${qualityLabel.toLowerCase()}`}
        aria-pressed={qualityPressed}
        onClick={onToggleQuality}
      >
        {qualityLabel}
      </button>
      <button
        type="button"
        className="bar-button help-toggle"
        title="Mở hướng dẫn"
        aria-expanded={helpOpen}
        aria-controls="hon-gio-help"
        onClick={onToggleHelp}
      >
        ?
        <span className="sr-only">Hướng dẫn</span>
      </button>
    </header>
  );
}
