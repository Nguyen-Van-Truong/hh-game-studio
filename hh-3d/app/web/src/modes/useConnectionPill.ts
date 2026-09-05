import { useEffect, useRef, useState } from "react";
import {
  RECONNECT_FLASH_MS,
  nextConnectionPill,
  type ConnectionState,
} from "./modes";

/** Slim connectivity pill flash. Does not reopen friends or invent a server. */
export function useConnectionPill(online: boolean): ConnectionState {
  const [pill, setPill] = useState<ConnectionState>(() =>
    online ? "connected" : "lost",
  );
  const wasOnline = useRef(online);

  useEffect(() => {
    const next = nextConnectionPill(wasOnline.current, online);
    wasOnline.current = online;
    setPill(next);
    if (next !== "reconnecting") {
      return;
    }
    const id = window.setTimeout(() => {
      setPill("connected");
    }, RECONNECT_FLASH_MS);
    return () => window.clearTimeout(id);
  }, [online]);

  return pill;
}
