import { useEffect, useMemo, useRef, useState } from "react";
import type { AvatarState } from "../avatar/walk";
import type { PresenceMode } from "../modes/modes";
import {
  pullDemoBus,
  publishLocalLeave,
  publishLocalPresence,
  pushDemoBus,
  subscribeLocalBus,
} from "./bus";
import type { FriendGraph } from "./graph";
import {
  isDocumentStreetVisible,
  makePresencePacket,
  PRESENCE_IDLE_MS,
  PRESENCE_MOVE_MS,
  shouldPublishStreetPresence,
  streetPresenceIntent,
  visibleFriends,
  type PresencePacket,
  type VisibleFriend,
} from "./presence";
import type { SeatId } from "./seats";

export function usePresence(input: {
  seat: SeatId;
  avatar: AvatarState;
  mode: PresenceMode;
  optedIn: boolean;
  connected: boolean;
  graph: FriendGraph;
  viewingShopId?: string | null;
}): {
  remotes: VisibleFriend[];
  heard: PresencePacket[];
} {
  const [heardMap, setHeardMap] = useState<Partial<Record<SeatId, PresencePacket>>>({});
  const avatarRef = useRef(input.avatar);
  const modeRef = useRef(input.mode);
  const optedRef = useRef(input.optedIn);
  const connectedRef = useRef(input.connected);
  const lastPubRef = useRef(0);
  const publishingRef = useRef(false);
  const publishNowRef = useRef<(force: boolean) => void>(() => {});
  const viewingRef = useRef<string | null>(input.viewingShopId ?? null);
  avatarRef.current = input.avatar;
  modeRef.current = input.mode;
  optedRef.current = input.optedIn;
  connectedRef.current = input.connected;
  viewingRef.current = input.viewingShopId ?? null;

  const upsert = (packet: PresencePacket) => {
    setHeardMap((prev) => {
      const prevRow = prev[packet.seat_id];
      if (
        prevRow &&
        prevRow.ts === packet.ts &&
        prevRow.lon === packet.lon &&
        prevRow.lat === packet.lat &&
        prevRow.pose === packet.pose &&
        prevRow.sprint === packet.sprint &&
        prevRow.mode === packet.mode &&
        prevRow.opted_in === packet.opted_in &&
        prevRow.viewing_shop_id === packet.viewing_shop_id
      ) {
        return prev;
      }
      return { ...prev, [packet.seat_id]: packet };
    });
  };

  useEffect(() => {
    const stop = subscribeLocalBus((event) => {
      if (event.type === "presence" && event.packet.seat_id !== input.seat) {
        upsert(event.packet);
      }
      if (event.type === "leave" && event.seat_id !== input.seat) {
        setHeardMap((prev) => {
          if (!prev[event.seat_id]) {
            return prev;
          }
          const next = { ...prev };
          delete next[event.seat_id];
          return next;
        });
      }
    });
    const pull = async () => {
      const snap = await pullDemoBus();
      if (!snap) {
        return;
      }
      setHeardMap((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const seat of ["a", "b", "c"] as const) {
          if (seat === input.seat) {
            continue;
          }
          const packet = snap.presence[seat];
          if (!packet) {
            if (next[seat]) {
              delete next[seat];
              changed = true;
            }
            continue;
          }
          const prevRow = next[seat];
          if (
            !prevRow ||
            prevRow.ts !== packet.ts ||
            prevRow.lon !== packet.lon ||
            prevRow.lat !== packet.lat ||
            prevRow.viewing_shop_id !== packet.viewing_shop_id
          ) {
            next[seat] = packet;
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    };
    void pull();
    const poll = window.setInterval(() => {
      void pull();
    }, 250);
    return () => {
      stop();
      window.clearInterval(poll);
    };
  }, [input.seat]);

  useEffect(() => {
    const session = `${input.seat}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const leaveStreet = () => {
      publishingRef.current = false;
      publishLocalLeave(input.seat);
      void pushDemoBus({ leave: input.seat, leave_session: session });
    };
    const publish = (force: boolean) => {
      const avatar = avatarRef.current;
      const mode = modeRef.current;
      const optedIn = optedRef.current;
      const connected = connectedRef.current;
      const now = Date.now();
      const documentVisible = isDocumentStreetVisible(
        typeof document !== "undefined" ? document : null,
      );
      const live = shouldPublishStreetPresence({
        mode,
        opted_in: optedIn,
        connected,
        documentVisible,
      });
      const intent = streetPresenceIntent({
        shouldPublish: live,
        wasPublishing: publishingRef.current,
      });
      if (intent === "leave") {
        leaveStreet();
        lastPubRef.current = now;
        return;
      }
      if (intent === "hold") {
        return;
      }
      const interval = avatar.pose === "walk" ? PRESENCE_MOVE_MS : PRESENCE_IDLE_MS;
      if (!force && now - lastPubRef.current < interval) {
        return;
      }
      publishingRef.current = true;
      const packet = makePresencePacket({
        seat: input.seat,
        mode,
        optedIn,
        lon: avatar.lon,
        lat: avatar.lat,
        heading: avatar.heading,
        pose: avatar.pose,
        sprint: avatar.sprint,
        viewingShopId: viewingRef.current,
        presenceSession: session,
        now,
      });
      publishLocalPresence(packet);
      void pushDemoBus({ presence: packet });
      lastPubRef.current = now;
    };
    publishNowRef.current = publish;
    publish(true);
    const id = window.setInterval(() => publish(false), PRESENCE_MOVE_MS);
    const onUnload = () => {
      if (isDocumentStreetVisible(typeof document !== "undefined" ? document : null)) {
        return;
      }
      leaveStreet();
    };
    const onVisibility = () => {
      publish(true);
    };
    window.addEventListener("pagehide", onUnload);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("pagehide", onUnload);
      document.removeEventListener("visibilitychange", onVisibility);
      publishNowRef.current = () => {};
      leaveStreet();
    };
  }, [input.seat]);

  useEffect(() => {
    publishNowRef.current(true);
  }, [input.mode, input.optedIn, input.connected, input.viewingShopId]);

  const remotes = useMemo(() => {
    return visibleFriends({
      viewer: input.seat,
      viewerMode: input.mode,
      viewerOptedIn: input.optedIn,
      connected: input.connected,
      graph: input.graph,
      others: Object.values(heardMap).filter((row): row is PresencePacket => Boolean(row)),
      now: Date.now(),
    });
  }, [heardMap, input.connected, input.graph, input.mode, input.optedIn, input.seat]);

  const heard = useMemo(
    () => Object.values(heardMap).filter((row): row is PresencePacket => Boolean(row)),
    [heardMap],
  );

  return { remotes, heard };
}
