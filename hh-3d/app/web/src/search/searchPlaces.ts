import type { Place } from "../contracts/types";
import { shopMatchesQuery } from "../shops/catalog";
import type { Listing, Shop } from "../shops/types";

export function searchPlaces(
  places: Place[],
  query: string,
  shops: Shop[] = [],
  listings: Listing[] = [],
): Place[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return places;
  }
  const shopPlaceIds = new Set(
    shops.filter((shop) => shopMatchesQuery(shop, listings, needle)).map((shop) => shop.place_id),
  );
  return places.filter((place) => {
    return (
      place.name.toLowerCase().includes(needle) ||
      place.summary.toLowerCase().includes(needle) ||
      place.id.toLowerCase().includes(needle) ||
      shopPlaceIds.has(place.id)
    );
  });
}

export function findPlace(places: Place[], id: string | null): Place | null {
  if (!id) {
    return null;
  }
  return places.find((place) => place.id === id) ?? null;
}
