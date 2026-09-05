import {
  connectionAttr,
  connectionCopy,
  presenceChipCopy,
  type ConnectionState,
  type PresenceMode,
} from "./modes";

type ModeStatusProps = {
  presenceMode: PresenceMode;
  connection: ConnectionState;
};

/** Slim HUD pair: social stroll vs this-PC 4175 network. Not a dashboard. */
export function ModeStatus({ presenceMode, connection }: ModeStatusProps) {
  const presence = presenceChipCopy(presenceMode);
  const net = connectionCopy(connection);
  const connTitle =
    connection === "lost"
      ? "Browser has no network. Social Offline/Online is unchanged."
      : connection === "reconnecting"
        ? "This PC 4175 loopback coming back. Not a city. Not a presence server."
        : "This PC 4175 loopback. Not a city.";
  return (
    <p
      className="mode-status"
      data-testid="mode-status"
      title="Social Offline/Online is stroll with friends. Máy này · 4175 / Mất kết nối / Đang kết nối lại is this-PC loopback, not a city."
    >
      <span
        data-testid="hud-presence"
        data-presence={presenceMode}
        title={
          presenceMode === "offline"
            ? "Stroll alone; shops still open. Not internet."
            : "Meet friends on this machine. Not internet."
        }
      >
        {presence}
      </span>
      <span className="mode-status-sep" aria-hidden="true">
        ·
      </span>
      <span
        data-testid="hud-connection"
        data-connection={connectionAttr(connection)}
        title={connTitle}
      >
        {net}
      </span>
    </p>
  );
}
