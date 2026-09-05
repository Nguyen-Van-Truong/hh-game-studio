import { useEffect, useState } from "react";
import { pullDemoBus, publishLocalGraph, pushDemoBus, subscribeLocalBus } from "./bus";
import {
  applyGraphOp,
  emptyGraph,
  loadGraph,
  saveGraph,
  type FriendGraph,
  type GraphOp,
} from "./graph";

export function useFriendGraph(): {
  graph: FriendGraph;
  applyOp: (op: GraphOp) => void;
} {
  const [graph, setGraphState] = useState<FriendGraph>(emptyGraph);

  useEffect(() => {
    const stop = subscribeLocalBus((event) => {
      if (event.type === "graph") {
        setGraphState(event.graph);
        saveGraph(event.graph);
      }
    });
    const pull = async () => {
      const snap = await pullDemoBus();
      if (!snap) {
        const cached = loadGraph();
        if (cached.pairs.length > 0) {
          setGraphState(cached);
        }
        return;
      }
      setGraphState((prev) => {
        const next = snap.graph;
        if (
          prev.updated_at === next.updated_at &&
          JSON.stringify(prev.pairs) === JSON.stringify(next.pairs)
        ) {
          return prev;
        }
        saveGraph(next);
        return next;
      });
    };
    void pull();
    const id = window.setInterval(() => {
      void pull();
    }, 400);
    return () => {
      stop();
      window.clearInterval(id);
    };
  }, []);

  const applyOp = (op: GraphOp) => {
    setGraphState((prev) => {
      const next = { ...applyGraphOp(prev, op), updated_at: Date.now() };
      saveGraph(next);
      publishLocalGraph(next);
      void pushDemoBus({ graph_op: op });
      return next;
    });
  };

  return { graph, applyOp };
}
