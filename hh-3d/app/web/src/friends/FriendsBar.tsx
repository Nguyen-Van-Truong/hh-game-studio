import { tunicShirtForSeat } from "../play/Person";
import { canFriend, relation, type FriendGraph, type FriendRelation, type GraphOp } from "./graph";
import { VIEWING_SHOP_COPY, type VisibleFriend } from "./presence";
import { DEMO_SEATS, SEAT_IDS, type SeatId } from "./seats";

type FriendsBarProps = {
  seat: SeatId;
  graph: FriendGraph;
  remotes: VisibleFriend[];
  onSeat: (seat: SeatId) => void;
  onOp: (op: GraphOp) => void;
  onOpenShop?: (shopId: string) => void;
};

function relationCopy(rel: FriendRelation): string {
  if (rel === "accepted") {
    return "accepted friends";
  }
  if (rel === "outgoing") {
    return "invite sent";
  }
  if (rel === "incoming") {
    return "invite received";
  }
  return "not friends";
}

export function FriendsBar({ seat, graph, remotes, onSeat, onOp, onOpenShop }: FriendsBarProps) {
  const me = DEMO_SEATS[seat];
  return (
    <section className="friends-bar" data-testid="friends-bar">
      <p data-testid="friends-honesty">
        This-PC shared store on 4175 loopback (127.0.0.1). Two browsers on
        THIS machine share shops, friends, and presence. Not a city presence
        server. Not another city&apos;s cloud. Not WAN. Not GPS. NOT_PLAN_PASS.
      </p>
      <p className="friends-seats" data-testid="seat-switcher" data-seat={seat}>
        This tab: <strong data-testid="current-seat">{me.display_name}</strong>
        {SEAT_IDS.map((id) => (
          <button
            key={id}
            type="button"
            data-testid={`seat-${id}`}
            data-active={id === seat ? "yes" : "no"}
            onClick={() => onSeat(id)}
          >
            Seat {id.toUpperCase()}
          </button>
        ))}
        {SEAT_IDS.map((id) => (
          <a
            key={`open-${id}`}
            data-testid={`open-tab-${id}`}
            href={`/?seat=${id}`}
            target="_blank"
            rel="noreferrer"
          >
            Open {id.toUpperCase()} in another tab
          </a>
        ))}
      </p>
      <ul className="friend-rows" data-testid="friend-list">
        {SEAT_IDS.filter((id) => id !== seat).map((id) => {
          const other = DEMO_SEATS[id];
          const rel = relation(graph, seat, id);
          const allowed = canFriend(seat, id);
          return (
            <li
              key={id}
              data-testid={`friend-row-${id}`}
              data-relation={other.stranger ? "stranger" : rel}
            >
              <span>
                {other.display_name}
                {other.stranger ? " — stranger seat, cannot friend in this demo" : ` — ${relationCopy(rel)}`}
              </span>
              {allowed && rel === "none" ? (
                <button
                  type="button"
                  data-testid={`add-friend-${id}`}
                  onClick={() => onOp({ op: "request", from: seat, to: id })}
                >
                  Add friend
                </button>
              ) : null}
              {allowed && rel === "incoming" ? (
                <button
                  type="button"
                  data-testid={`accept-friend-${id}`}
                  onClick={() => onOp({ op: "accept", from: seat, to: id })}
                >
                  Accept
                </button>
              ) : null}
              {allowed && (rel === "accepted" || rel === "outgoing") ? (
                <button
                  type="button"
                  data-testid={`unfriend-${id}`}
                  onClick={() => onOp({ op: "unfriend", from: seat, to: id })}
                >
                  Unfriend
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
      <div className="people-rows" data-testid="people-rows" data-count={remotes.length}>
        {remotes.length === 0 ? (
          <p data-testid="people-empty">Chưa có bạn nào trên phố</p>
        ) : (
          remotes.map((row) => (
            <p
              key={row.seat_id}
              data-testid={`people-row-${row.seat_id}`}
              data-seat={row.seat_id}
              data-body="tunic-humanoid"
              data-tunic={tunicShirtForSeat(row.seat_id)}
              data-pose={row.pose}
              data-heading={String(Math.round(row.heading))}
              data-lon={row.lon.toFixed(7)}
              data-lat={row.lat.toFixed(7)}
              data-street={row.viewing_shop_id ? "0" : "1"}
              data-viewing-shop={row.viewing_shop_id ?? ""}
            >
              {row.viewing_shop_id
                ? `${row.display_name} · ${VIEWING_SHOP_COPY}`
                : `${row.display_name} · ${row.pose === "walk" ? "walking" : "standing"} · in-app, not GPS`}
              {row.viewing_shop_id && onOpenShop ? (
                <>
                  {" · "}
                  <button
                    type="button"
                    data-testid={`people-open-shop-${row.seat_id}`}
                    onClick={() => onOpenShop(row.viewing_shop_id as string)}
                  >
                    Mở kệ
                  </button>
                </>
              ) : null}
            </p>
          ))
        )}
      </div>
    </section>
  );
}
