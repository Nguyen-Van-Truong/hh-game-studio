export type ShopStatus = "draft" | "published" | "hidden" | "closed";
export type ListingStatus = "draft" | "published" | "sold_out" | "hidden" | "deleted";
export type ListingKind = "fish" | "bag" | "other";
export type OwnerPresence = "offline" | "online";

export type Shop = {
  shop_id: string;
  owner_id: string;
  name: string;
  description: string;
  place_id: string;
  lon: number;
  lat: number;
  status: ShopStatus;
  owner_presence: OwnerPresence;
  updated_at: string;
  version: number;
  world_id: string;
};

export type Listing = {
  listing_id: string;
  shop_id: string;
  title: string;
  description: string;
  kind: ListingKind;
  price_label: string;
  status: ListingStatus;
  updated_at: string;
  version: number;
};

export type ShopCatalog = {
  schema: "hh-world-shop-catalog/v0";
  world_id: string;
  authored_or_source: "authored";
  accuracy_class: string;
  published_at: string;
  updated_at: string;
  honesty: string[];
  shops: Shop[];
  listings: Listing[];
};

export type CatalogLoad =
  | { status: "loading" }
  | { status: "ok"; catalog: ShopCatalog; loadedAt: string }
  | { status: "unavailable"; reason: string };
