type HeaderProps = {
  menuOpen?: boolean;
  onMenu?: () => void;
};

export function Header({ menuOpen, onMenu }: HeaderProps) {
  return (
    <header className="topbar">
      <div className="topbar-row">
        <p className="brand">HH World</p>
        {onMenu ? (
          <button
            type="button"
            className="play-menu-toggle"
            data-testid="play-menu-toggle"
            aria-expanded={menuOpen ? "true" : "false"}
            aria-controls="play-menu"
            onClick={onMenu}
          >
            {menuOpen ? "Close" : "Menu"}
            <span className="play-menu-key">Tab</span>
          </button>
        ) : null}
      </div>
      <p className="brand-sub">
        Walk the authored 400 m street · open a shop · friends demo · Bến Thành
        vicinity
      </p>
    </header>
  );
}
