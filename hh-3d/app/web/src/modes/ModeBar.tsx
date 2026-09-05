import { DEMO_DISPLAY_NAME } from "../account/demoIdentity";
import { VIEWING_SHOP_COPY, type VisibleFriend } from "../friends/presence";
import type { SeatId } from "../friends/seats";
import { DEMO_SEATS } from "../friends/seats";
import {
  connectionAttr,
  connectionCopy,
  presenceCopy,
  type ConnectionState,
  type PresenceMode,
} from "./modes";

type ModeBarProps = {
  networkCutSim: boolean;
  onNetworkCutSim: (value: boolean) => void;
  identitySignedIn: boolean;
  presenceMode: PresenceMode;
  optedIn: boolean;
  onPresenceMode: (mode: PresenceMode) => void;
  onOptedIn: (value: boolean) => void;
  remotes: VisibleFriend[];
  seat: SeatId;
  connected: boolean;
  connection: ConnectionState;
};

export function ModeBar({
  networkCutSim,
  onNetworkCutSim,
  identitySignedIn,
  presenceMode,
  optedIn,
  onPresenceMode,
  onOptedIn,
  remotes,
  seat,
  connected,
  connection,
}: ModeBarProps) {
  const netCopy = connectionCopy(connection);
  const streetRemotes = remotes.filter((row) => !row.viewing_shop_id);
  const viewingRemotes = remotes.filter((row) => row.viewing_shop_id);
  const peopleLabel =
    presenceMode === "offline"
      ? "none (you are Offline)"
      : !connected
        ? "none (Đã mất kết nối; tạm thời không hiện bạn bè)"
        : streetRemotes.length === 0
          ? "none (no accepted friend Online on this street)"
          : streetRemotes.map((row) => row.display_name).join(", ");
  const viewingLabel =
    viewingRemotes.length === 0
      ? ""
      : ` ${VIEWING_SHOP_COPY}: ${viewingRemotes.map((row) => row.display_name).join(", ")}.`;
  return (
    <section className="mode-bar" data-testid="mode-bar">
      <p>
        <strong data-testid="presence-mode">{presenceCopy(presenceMode)}</strong>
      </p>
      <p
        data-testid="people-layer"
        data-remote-count={remotes.length}
        data-street-count={streetRemotes.length}
        data-viewing-count={viewingRemotes.length}
        data-seat={seat}
      >
        Other people on the street: {peopleLabel}.{viewingLabel}
      </p>
      <p className="mode-actions">
        <button
          type="button"
          data-testid="offline-btn"
          data-active={presenceMode === "offline" ? "yes" : "no"}
          onClick={() => onPresenceMode("offline")}
        >
          Offline — Stroll alone; shops still open
        </button>
        <button
          type="button"
          data-testid="online-btn"
          data-active={presenceMode === "online" ? "yes" : "no"}
          disabled={false}
          onClick={() => {
            onPresenceMode("online");
            if (!optedIn) {
              onOptedIn(true);
            }
          }}
        >
          Online — Meet friends on this machine (local demo)
        </button>
      </p>
      <p>
        <label className="presence-opt-in">
          <input
            type="checkbox"
            data-testid="presence-opt-in"
            checked={optedIn}
            onChange={(event) => onOptedIn(event.target.checked)}
          />
          Show my character to accepted friends on this machine (opt-in)
        </label>
      </p>
      {presenceMode === "online" ? (
        <p className="muted" data-testid="online-hint">
          {DEMO_SEATS[seat].display_name}: this-PC demo has 2 friend seats
          (A/B). Seat C is a stranger and cannot friend. Not 20 people. Not
          WAN. Not a city presence server. Not GPS.
        </p>
      ) : null}
      <p
        className="muted"
        data-testid="connection-label"
        data-connection={connectionAttr(connection)}
      >
        <strong data-testid="menu-connection">{netCopy}</strong>
        {connection === "lost"
          ? " · showing the local copy if it already loaded; otherwise Chưa tải."
          : connection === "reconnecting"
            ? " · this-PC 4175 loopback coming back, not WAN. Not a city."
            : " · this-PC 4175 loopback shop store, not WAN. Not a city."}
        {!connected && presenceMode === "online"
          ? " Đã mất kết nối; tạm thời không hiện bạn bè."
          : ""}
        <label className="network-cut">
          <input
            type="checkbox"
            data-testid="network-cut-sim"
            checked={networkCutSim}
            onChange={(event) => onNetworkCutSim(event.target.checked)}
          />
          Simulate no-network (not Offline stroll)
        </label>
      </p>
      <p className="muted" data-testid="demo-identity" data-signed-in={identitySignedIn ? "yes" : "no"}>
        {identitySignedIn
          ? `${DEMO_DISPLAY_NAME} · local demo, not a real account`
          : "Guest · shops public; friends not required"}
      </p>
    </section>
  );
}
