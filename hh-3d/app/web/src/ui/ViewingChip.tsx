import { VIEWING_SHOP_COPY, type VisibleFriend } from "../friends/presence";
import type { Shop } from "../shops/types";

export function shopNameForViewing(shopId: string, shops: readonly Shop[]): string {
  return shops.find((row) => row.shop_id === shopId)?.name ?? shopId;
}

type ViewingChipProps = {
  remotes: VisibleFriend[];
  shops: readonly Shop[];
  onOpenShop?: (shopId: string) => void;
};

/** Street HUD for a friend in a shelf. Lives outside #play-menu. Not GPS. */
export function ViewingChip({ remotes, shops, onOpenShop }: ViewingChipProps) {
  const viewing = remotes.filter((row) => row.viewing_shop_id);
  if (viewing.length === 0) {
    return null;
  }
  const first = viewing[0];
  const shopId = first.viewing_shop_id ?? "";
  const shopName = shopNameForViewing(shopId, shops);
  return (
    <p
      className="viewing-chip"
      data-testid="play-viewing-chip"
      data-seat={first.seat_id}
      data-shop={shopId}
      data-count={String(viewing.length)}
      title="Friend is looking at a public shelf on this PC. Not a shared interior."
    >
      {VIEWING_SHOP_COPY}
      {" · "}
      <span data-testid="play-viewing-shop">{shopName}</span>
      {" · "}
      <span data-testid="play-viewing-who">{first.display_name}</span>
      {onOpenShop && shopId ? (
        <>
          {" · "}
          <button
            type="button"
            className="viewing-chip-open"
            data-testid="play-viewing-open"
            data-shop={shopId}
            onClick={() => onOpenShop(shopId)}
          >
            Mở kệ
          </button>
        </>
      ) : null}
    </p>
  );
}
