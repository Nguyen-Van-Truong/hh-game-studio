import type { DemoIdentity } from "../account/demoIdentity";
import { DEMO_DISPLAY_NAME } from "../account/demoIdentity";
import { isMenuLeftoverShop, MENU_LEFTOVER_LABEL } from "../avatar/walk";
import { ListProductForm } from "./ListProductForm";
import { isLocalListingId, type LocalListing } from "./localListings";
import { kindLabel, publicListings } from "./catalog";
import type { Listing, ListingKind, Shop, ShopCatalog } from "./types";

type ShopPanelProps = {
  shop: Shop | null;
  catalog: ShopCatalog | null;
  ownerOfflineSim: boolean;
  onOwnerOfflineSim: (value: boolean) => void;
  networkCutSim: boolean;
  onNetworkCutSim: (value: boolean) => void;
  identity: DemoIdentity;
  drafts: LocalListing[];
  canPublish: boolean;
  onBecomeOwner: () => void;
  onLeaveOwner: () => void;
  onListProduct: (title: string, kind: ListingKind) => LocalListing | null;
  onRetryDraft: (listingId: string) => void;
  onClose: () => void;
};

export function ShopPanel({
  shop,
  catalog,
  ownerOfflineSim,
  onOwnerOfflineSim,
  networkCutSim,
  onNetworkCutSim,
  identity,
  drafts,
  canPublish,
  onBecomeOwner,
  onLeaveOwner,
  onListProduct,
  onRetryDraft,
  onClose,
}: ShopPanelProps) {
  if (!shop || !catalog) {
    return null;
  }
  const listings: Listing[] = publicListings(catalog, shop.shop_id);
  const leftover = isMenuLeftoverShop(shop);
  const kindCopy = leftover
    ? MENU_LEFTOVER_LABEL
    : shop.shop_id.startsWith("shop-local-")
      ? "public shop · opened on this machine"
      : "public shop · authored example among many";
  const ownerDrafts = identity.signed_in
    ? drafts.filter((row) => row.shop_id === shop.shop_id && row.status === "draft")
    : [];
  return (
    <article
      className={
        leftover
          ? "card shop-panel shop-sheet shop-panel-leftover"
          : "card shop-panel shop-sheet shop-panel-street"
      }
      data-testid="shop-panel"
      data-shop={shop.shop_id}
      data-leftover={leftover ? "1" : "0"}
      data-street={leftover ? "0" : "1"}
      data-keep-out={leftover ? "1" : "0"}
      data-minimap-clear="1"
    >
      <div className="card-head">
        <h2>{shop.name}</h2>
        <button type="button" data-testid="close-shop" onClick={onClose}>
          Close shelf
        </button>
      </div>
      {leftover ? (
        <p className="shop-panel-leftover-banner" data-testid="shop-leftover-banner">
          {MENU_LEFTOVER_LABEL}
        </p>
      ) : null}
      <p
        className={leftover ? "approx shop-panel-leftover-copy" : "approx"}
        data-testid="shop-panel-kind"
      >
        {kindCopy}
      </p>
      {listings.length === 0 ? (
        <p data-testid="shop-empty">Chưa có sản phẩm</p>
      ) : (
        <ul className="goods" data-testid="shop-listings">
          {listings.map((row) => (
            <li
              key={row.listing_id}
              data-listing={row.listing_id}
              data-kind={row.kind}
              data-status="published"
              data-source={isLocalListingId(row.listing_id) ? "local-demo" : "authored"}
            >
              <strong>{row.title}</strong>
              <span className="kind-pill">{kindLabel(row.kind)}</span>
              <span className="kind-pill" data-public="yes">
                public
              </span>
              <p>{row.description}</p>
              <p className="muted">{row.price_label}</p>
            </li>
          ))}
        </ul>
      )}
      <p data-testid="shop-panel-desc">
        {leftover
          ? `${MENU_LEFTOVER_LABEL}. Not a street stall. Nearby E does not open this shelf.`
          : shop.description}
      </p>
      <p data-testid="owner-presence">
        {ownerOfflineSim
          ? "Shop owner: Offline. Public listings stay open."
          : "Shop owner: local Online label only. Not live presence. Shop still public."}
      </p>
      <label className="owner-sim">
        <input
          type="checkbox"
          data-testid="owner-offline-sim"
          checked={ownerOfflineSim}
          onChange={(event) => onOwnerOfflineSim(event.target.checked)}
        />
        Simulate owner Offline / logged out / app closed. This label does not take
        the public shelf down.
      </label>
      <p className="muted">
        Listing updated {shop.updated_at.slice(0, 16)} — not the same clock as Map
        data as of.
      </p>
      <p className="muted">Authored drafts stay off this shelf. No checkout in this slice.</p>
      <section className="demo-owner" data-testid="demo-owner-block">
        <p data-testid="demo-owner-label">
          {identity.signed_in
            ? `${DEMO_DISPLAY_NAME} — local demo identity. NOT a real account. NOT Google/OIDC. NOT_PLAN_PASS.`
            : "Guest on this machine. Browse does not need friends or an account."}
        </p>
        {identity.signed_in ? (
          <button type="button" data-testid="leave-demo-owner" onClick={onLeaveOwner}>
            Leave demo owner (back to guest)
          </button>
        ) : (
          <button type="button" data-testid="become-demo-owner" onClick={onBecomeOwner}>
            Become {DEMO_DISPLAY_NAME}
          </button>
        )}
        <label className="owner-sim">
          <input
            type="checkbox"
            data-testid="shop-network-cut"
            checked={networkCutSim}
            onChange={(event) => onNetworkCutSim(event.target.checked)}
          />
          Simulate no-network (not Offline stroll). New item stays Chưa đăng.
        </label>
        {identity.signed_in ? (
          <ListProductForm canPublish={canPublish} onList={onListProduct} />
        ) : (
          <p className="muted">
            R4-WP0B account/OIDC is not built. Become the local demo owner to list
            a sample. Public posted goods stay visible after you leave.
          </p>
        )}
        {identity.signed_in && ownerDrafts.length > 0 ? (
          <ul className="drafts" data-testid="owner-drafts">
            {ownerDrafts.map((row) => (
              <li
                key={row.listing_id}
                data-draft={row.listing_id}
                data-status="draft"
                data-queued={row.queued ? "yes" : "no"}
              >
                <strong>{row.title}</strong>
                <span className="kind-pill">Chưa đăng</span>
                {row.queued ? (
                  <button
                    type="button"
                    data-testid="retry-publish"
                    disabled={!canPublish}
                    onClick={() => onRetryDraft(row.listing_id)}
                  >
                    {canPublish ? "Retry publish (this machine)" : "Queued until network"}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </article>
  );
}
