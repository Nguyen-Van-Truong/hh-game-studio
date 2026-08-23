/** Last Play run seen after a proven EXTERNAL apply. job.list/status may show it. */

export type PlayJob = {
  id: string;
  kind: "play";
  playing: boolean;
  scene: string;
  previous_run_id: string;
};

let current: PlayJob | undefined;

export function notePlayAfter(actionId: string, after: Record<string, unknown>): void {
  if (
    actionId !== "play.start" &&
    actionId !== "play.stop" &&
    actionId !== "play.restart" &&
    actionId !== "play.debug"
  ) {
    return;
  }
  const runId = typeof after.run_id === "string" ? after.run_id : "";
  if (!runId) {
    if (actionId === "play.stop") {
      if (current) {
        current = { ...current, playing: false };
      }
    }
    return;
  }
  current = {
    id: runId,
    kind: "play",
    playing: after.playing === true,
    scene: typeof after.playing_scene === "string" ? after.playing_scene : typeof after.scene === "string" ? after.scene : "",
    previous_run_id: typeof after.previous_run_id === "string" ? after.previous_run_id : "",
  };
}

export function playJobs(): PlayJob[] {
  return current ? [current] : [];
}

export function playJob(jobId: string): PlayJob | undefined {
  if (!current) {
    return undefined;
  }
  if (current.id === jobId) {
    return current;
  }
  if (current.previous_run_id && current.previous_run_id === jobId) {
    return { ...current, id: jobId, playing: false };
  }
  return undefined;
}
