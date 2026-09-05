import type { WorldManifest } from "../contracts/types";

type HonestyBannerProps = {
  manifest: WorldManifest | null;
  compact?: boolean;
};

export function HonestyBanner({ manifest, compact }: HonestyBannerProps) {
  const asOf = manifest?.acquired_at?.slice(0, 10) ?? "2026-09-03";
  return (
    <section className={compact ? "honesty honesty-slim" : "honesty"} data-testid="honesty-banner">
      {compact ? (
        <p>
          <strong>Authored approximation.</strong> Not a live map, not
          OSM/Overture, not photogrammetry, and not a digital twin. No GTA
          claim, no 1:1 city. Authored 400 m: two official named streets
          plus inner parcel lanes, not a city grid. This frame ends at an
          authored wall — fixture edge, not a city. Menu boards list
          authored fiction goods, not a live market. NOT_PLAN_PASS.
        </p>
      ) : (
        <>
          <p>
            <strong>Authored approximation.</strong> This is not a live map, not
            OSM/Overture, not photogrammetry, and not a digital twin.
          </p>
          <p>
            Map data as of {asOf} (authored fixture). Accuracy class:{" "}
            {manifest?.accuracy_class ?? "authored"}. Heights are estimated.
          </p>
          <p>
            Shops may be the authored lantern stall or a shop you open on this
            PC. Shared on 4175 loopback for two browsers here. Not WAN. Not a
            city shop server. Menu boards list authored fiction goods, not a
            live market. No GTA claim, no 1:1 city, no digital twin.
          </p>
        </>
      )}
      <p data-testid="presence-honesty" className={compact ? "honesty-more" : undefined}>
        Friend bodies use this PC&apos;s 4175 loopback store (two browsers
        here). Not a city shop server. Not a city presence server. Not
        another city&apos;s cloud. Not WAN. Not GPS. NOT_PLAN_PASS.
      </p>
    </section>
  );
}
