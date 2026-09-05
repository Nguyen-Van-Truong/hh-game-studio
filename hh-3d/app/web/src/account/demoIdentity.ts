export const DEMO_IDENTITY_KEY = "hh-world.demo-identity.v1";
export const DEMO_OWNER_ID = "owner-local-demo-machine";
export const DEMO_DISPLAY_NAME = "Chủ quầy (máy này)";

export type DemoIdentity = {
  v: 1;
  kind: "local-demo";
  owner_id: typeof DEMO_OWNER_ID;
  display_name: typeof DEMO_DISPLAY_NAME;
  signed_in: boolean;
  not_real_account: true;
  not_oidc: true;
  not_google: true;
  not_plan_pass: true;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

export function guestIdentity(): DemoIdentity {
  return {
    v: 1,
    kind: "local-demo",
    owner_id: DEMO_OWNER_ID,
    display_name: DEMO_DISPLAY_NAME,
    signed_in: false,
    not_real_account: true,
    not_oidc: true,
    not_google: true,
    not_plan_pass: true,
  };
}

export function sanitizeDemoIdentity(value: unknown): DemoIdentity | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["kind"] !== "local-demo") {
    return null;
  }
  if (rec["owner_id"] !== DEMO_OWNER_ID) {
    return null;
  }
  if (rec["not_real_account"] !== true || rec["not_oidc"] !== true) {
    return null;
  }
  if (rec["not_google"] !== true || rec["not_plan_pass"] !== true) {
    return null;
  }
  if (typeof rec["signed_in"] !== "boolean") {
    return null;
  }
  return {
    ...guestIdentity(),
    signed_in: rec["signed_in"],
  };
}

function writeIdentity(row: DemoIdentity): DemoIdentity {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(DEMO_IDENTITY_KEY, JSON.stringify(row));
  }
  return row;
}

export function loadDemoIdentity(): DemoIdentity {
  if (typeof localStorage === "undefined") {
    return guestIdentity();
  }
  try {
    const raw = localStorage.getItem(DEMO_IDENTITY_KEY);
    if (!raw) {
      return guestIdentity();
    }
    return sanitizeDemoIdentity(JSON.parse(raw)) ?? guestIdentity();
  } catch {
    return guestIdentity();
  }
}

export function becomeDemoOwner(): DemoIdentity {
  return writeIdentity({ ...guestIdentity(), signed_in: true });
}

export function leaveDemoOwner(): DemoIdentity {
  return writeIdentity(guestIdentity());
}
