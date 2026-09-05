type StreetHelpProps = {
  nearbyName: string | null;
  nearbyShopId?: string | null;
  stallName: string | null;
  stallRangeM: number | null;
  shopCount: number;
  followOn: boolean;
  pose: "idle" | "walk";
  heading: number;
  airborne?: boolean;
  sprint?: boolean;
  turning?: boolean;
  looking?: boolean;
  compact?: boolean;
  onOpenNearby: () => void;
  onRecenter: () => void;
};

export function StreetHelp({
  nearbyName,
  nearbyShopId = null,
  stallName,
  stallRangeM,
  shopCount,
  followOn,
  pose,
  heading,
  airborne,
  sprint,
  turning,
  looking,
  compact,
  onOpenNearby,
  onRecenter,
}: StreetHelpProps) {
  const facing =
    heading >= 315 || heading < 45
      ? "north"
      : heading < 135
        ? "east"
        : heading < 225
          ? "south"
          : "west";
  const rangeLabel =
    stallRangeM === null ? "—" : `${stallRangeM < 10 ? stallRangeM.toFixed(1) : Math.round(stallRangeM)} m`;
  return (
    <div
      className={nearbyName ? "street-help is-nearby" : "street-help"}
      data-nearby-shop={nearbyShopId ?? ""}
    >
      <p className="avatar-status" data-testid="avatar-status">
        You:{" "}
        {airborne
          ? "jumping"
          : sprint && pose === "walk"
            ? "sprinting"
            : pose === "walk"
              ? "walking"
              : turning
                ? "turning"
                : "standing"}{" "}
        · facing {facing}
        {compact
          ? looking
            ? " · looking · Shift sprint · A/D strafe · Space"
            : " · click canvas to look · Esc · Shift sprint · A/D strafe · Space"
          : " · in-app position, not GPS"}
      </p>
      {compact ? null : (
        <p className="muted">
          Click the street to look (yaw/pitch); Esc releases. Right-drag also
          looks. WASD and pad walk along look (A/D and ◀/▶ strafe, like Hòn
          Gió). Hold Shift or pad ≫ to sprint; release is walk. Space jumps.
        </p>
      )}
      <p data-testid="stall-hint" data-nearby-shop={nearbyShopId ?? ""}>
        {nearbyName
          ? `Press E or tap Open to enter ${nearbyName}.`
          : compact
            ? `E opens a stall when you are next to it.`
            : shopCount > 1
              ? `Walk toward a shop. ${shopCount} public shops on this map. E does nothing until you are at a stall.`
              : `Walk toward ${stallName ?? "the stall"}. E does nothing until you are at the stall.`}
      </p>
      <p
        className="muted"
        data-testid="shop-range"
        data-range={nearbyName ? (stallRangeM ?? "") : ""}
        data-shop-count={shopCount}
      >
        {nearbyName
          ? `${nearbyName}: ${rangeLabel} away`
          : shopCount > 0
            ? "Walk to a stall."
            : "No public stall on this map."}
      </p>
      <div className="card-actions">
        <button
          type="button"
          data-testid="recenter-avatar"
          data-follow={followOn ? "on" : "off"}
          onClick={onRecenter}
        >
          {followOn ? "Following you" : "Back to character"}
        </button>
        {nearbyName ? (
          <button type="button" data-testid="open-nearby-shop" onClick={onOpenNearby}>
            Open {nearbyName}
          </button>
        ) : null}
      </div>
    </div>
  );
}
