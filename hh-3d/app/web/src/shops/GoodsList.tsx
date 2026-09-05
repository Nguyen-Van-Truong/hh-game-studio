import { isStreetPlayShop, MENU_LEFTOVER_LABEL, sortMenuShops } from "../avatar/walk";
import { kindLabel, listingMatchesQuery } from "./catalog";
import type { Listing, Shop } from "./types";

type GoodsListProps = {
  shops: Shop[];
  listings: Listing[];
  query: string;
  loadedAt?: string | null;
  onOpenShop: (shopId: string) => void;
};

export function GoodsList({ shops, listings, query, loadedAt, onOpenShop }: GoodsListProps) {
  const needle = query.trim().toLowerCase();
  const leftoverIds = new Set(
    shops.filter((shop) => !isStreetPlayShop(shop)).map((shop) => shop.shop_id),
  );
  const orderedShops = sortMenuShops(shops);
  const leftoverCount = leftoverIds.size;
  const streetCount = orderedShops.length - leftoverCount;
  const visible = listings.filter((row) => listingMatchesQuery(row, needle));
  const orderedGoods = [...visible].sort((a, b) => {
    const aLeftover = leftoverIds.has(a.shop_id) ? 1 : 0;
    const bLeftover = leftoverIds.has(b.shop_id) ? 1 : 0;
    return aLeftover - bLeftover;
  });
  return (
    <section className="list goods-list" data-testid="goods-list">
      <h2>Public goods</h2>
      <p className="muted">
        Walk to a shop marker and press E. The lantern stall is one example.
        This list is a fallback.
      </p>
      {loadedAt ? (
        <p className="muted" data-testid="goods-loaded-at">
          Bản lưu lúc {loadedAt.slice(0, 19)}; local fixture, not a live server.
        </p>
      ) : null}
      <ul
        className="public-shop-names"
        data-testid="public-shop-names"
        data-count={orderedShops.length}
        data-street-count={streetCount}
        data-leftover-count={leftoverCount}
      >
        {orderedShops.map((shop) => {
          const leftover = leftoverIds.has(shop.shop_id);
          return (
            <li
              key={shop.shop_id}
              className={leftover ? "menu-shop-leftover" : "menu-shop-street"}
              data-shop={shop.shop_id}
              data-source={shop.shop_id.startsWith("shop-local-") ? "local-demo" : "authored"}
              data-keep-out={leftover ? "1" : "0"}
              data-leftover={leftover ? "1" : "0"}
              data-street={leftover ? "0" : "1"}
            >
              <button type="button" data-testid={`open-shop-${shop.shop_id}`} onClick={() => onOpenShop(shop.shop_id)}>
                <span className="menu-shop-name">{shop.name}</span>
                {leftover ? (
                  <small
                    className="menu-shop-leftover-label"
                    data-testid={`leftover-label-${shop.shop_id}`}
                  >
                    {` · ${MENU_LEFTOVER_LABEL}`}
                  </small>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
      {orderedGoods.length === 0 ? (
        <p>No published goods match.</p>
      ) : (
        <ul data-testid="public-goods-rows">
          {orderedGoods.map((row) => {
            const shop = shops.find((item) => item.shop_id === row.shop_id);
            const leftover = leftoverIds.has(row.shop_id);
            return (
              <li
                key={row.listing_id}
                className={leftover ? "goods-leftover" : "goods-street"}
                data-listing={row.listing_id}
                data-shop={row.shop_id}
                data-keep-out={leftover ? "1" : "0"}
                data-leftover={leftover ? "1" : "0"}
              >
                <button
                  type="button"
                  data-testid={`goods-${row.listing_id}`}
                  onClick={() => onOpenShop(row.shop_id)}
                >
                  <span>
                    {row.title}
                    <small>
                      {kindLabel(row.kind)}
                      {shop ? ` · ${shop.name}` : ""}
                    </small>
                    {leftover ? (
                      <small className="menu-shop-leftover-label">{` · ${MENU_LEFTOVER_LABEL}`}</small>
                    ) : null}
                  </span>
                  <small>public</small>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
