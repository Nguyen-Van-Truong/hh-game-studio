import assert from "node:assert/strict";
import test from "node:test";

const RECONNECT_FLASH_MS = 800;

function nextConnectionPill(wasOnline, online) {
  if (!online) {
    return "lost";
  }
  if (!wasOnline) {
    return "reconnecting";
  }
  return "connected";
}

function connectionCopy(state) {
  if (state === "lost") {
    return "Mất kết nối";
  }
  if (state === "reconnecting") {
    return "Đang kết nối lại";
  }
  return "Máy này · 4175";
}

function presenceCopy(mode) {
  if (mode === "online") {
    return "Online — Meet friends on this machine.";
  }
  return "Offline — Stroll alone; shops still open.";
}

function presenceChipCopy(mode) {
  return mode === "online" ? "Online" : "Offline";
}

test("internet copy is not the social Offline word", () => {
  assert.equal(connectionCopy("connected"), "Máy này · 4175");
  assert.equal(connectionCopy("lost"), "Mất kết nối");
  assert.equal(connectionCopy("reconnecting"), "Đang kết nối lại");
  assert.equal(/offline/i.test(connectionCopy("connected")), false);
  assert.equal(/offline/i.test(connectionCopy("lost")), false);
  assert.equal(/offline/i.test(connectionCopy("reconnecting")), false);
});

test("lost-to-online flashes reconnecting; stay-online does not", () => {
  assert.equal(nextConnectionPill(true, true), "connected");
  assert.equal(nextConnectionPill(false, false), "lost");
  assert.equal(nextConnectionPill(true, false), "lost");
  assert.equal(nextConnectionPill(false, true), "reconnecting");
  assert.ok(RECONNECT_FLASH_MS >= 400 && RECONNECT_FLASH_MS <= 1200);
});

test("social Offline stays the stroll label", () => {
  assert.equal(presenceChipCopy("offline"), "Offline");
  assert.equal(presenceChipCopy("online"), "Online");
  assert.match(presenceCopy("offline"), /Stroll alone/);
  assert.match(presenceCopy("online"), /Meet friends/);
});
