import { useEffect, useMemo, useRef, useState } from "react";
import { StreetHelp } from "../avatar/StreetHelp";
import { isTypingTarget, useAvatar } from "../avatar/useAvatar";
import { WalkPad } from "../avatar/WalkPad";
import { distanceM, NEARBY_SHOP_M, nearestPublishedShop, streetPlayShops } from "../avatar/walk";
import { BookmarkPanel } from "../bookmarks/BookmarkPanel";
import {
  exportBookmarks,
  isBookmarked,
  loadBookmarks,
  resetBookmarks,
  toggleBookmark,
} from "../bookmarks/storage";
import {
  becomeDemoOwner,
  leaveDemoOwner,
  loadDemoIdentity,
} from "../account/demoIdentity";
import type { Bookmark, FeatureCollection, Place, WorldManifest } from "../contracts/types";
import { MapView } from "../map/MapView";
import { AOI_BBOX, buildingsFromCollection, placesFromCollection } from "../map/aoi";
import { MINIMAP_DEFER_KIND, MINIMAP_DEFER_MS, minimapMayConstruct } from "../map/minimapDefer";
import { FpsChip } from "../play/FpsChip";
import { detectPlayWebgl, PlayAvatarHud, PlayLoading, PlayView } from "../play/PlayView";
import {
  marketSpillFromCollection,
  marketSpillSolids,
  namedStreetHudAtLonLat,
  shopPlayLngLat,
  shopStallSolids,
  worldFromCollection,
  streetHudLabel,
  streetPlaqueSolidsFromCollection,
  streetPropSolidsFromCollection,
} from "../play/world";
import { FriendsBar } from "../friends/FriendsBar";
import { loadSeatMode, saveSeatMode } from "../friends/seatMode";
import { readSeatFromUrl, SEAT_LOOK_PITCH, SEAT_LOOK_YAW, SEAT_SPAWNS, type SeatId } from "../friends/seats";
import { useFriendGraph } from "../friends/useFriendGraph";
import { usePresence } from "../friends/usePresence";
import { ModeBar } from "../modes/ModeBar";
import { ModeStatus } from "../modes/ModeStatus";
import type { PresenceMode } from "../modes/modes";
import { useConnectionPill } from "../modes/useConnectionPill";
import { SearchBox } from "../search/SearchBox";
import { findPlace, searchPlaces } from "../search/searchPlaces";
import {
  emptyShopCatalog,
  keepLocalDrafts,
  publishLocalCatalog,
  publishedShopCatalog,
  pullDemoBus,
  pushDemoBus,
  subscribeLocalBus,
} from "../friends/bus";
import {
  findShop,
  mergeCatalogListings,
  mergeCatalogShops,
  parseShopCatalog,
  publicListings,
  publicShops,
  shopByPlace,
} from "../shops/catalog";
import { CreateShopForm } from "../shops/CreateShopForm";
import { GoodsList } from "../shops/GoodsList";
import {
  createLocalListing,
  inferKind,
  loadLocalListings,
  networkAllowsPublish,
  retryQueuedListing,
  saveLocalListings,
  toCatalogListings,
} from "../shops/localListings";
import {
  createLocalShop,
  loadLocalShops,
  saveLocalShops,
  toCatalogShops,
} from "../shops/localShops";
import { ShopPanel } from "../shops/ShopPanel";
import type { CatalogLoad, ListingKind } from "../shops/types";
import { Header } from "../ui/Header";
import { HonestyBanner } from "../ui/HonestyBanner";
import { StreetChip } from "../ui/StreetChip";
import { ViewingChip } from "../ui/ViewingChip";
import { PlaceCard } from "../ui/PlaceCard";
import { PlaceList } from "../ui/PlaceList";

function readPlaceFromUrl(): string | null {
  const id = new URLSearchParams(window.location.search).get("place");
  return id && id.startsWith("place-") ? id : null;
}

function readShopFromUrl(): string | null {
  const id = new URLSearchParams(window.location.search).get("shop");
  return id && id.startsWith("shop-") ? id : null;
}

function writeUrl(placeId: string | null, shopId: string | null, seat: SeatId): void {
  const url = new URL(window.location.href);
  if (placeId) {
    url.searchParams.set("place", placeId);
  } else {
    url.searchParams.delete("place");
  }
  if (shopId) {
    url.searchParams.set("shop", shopId);
  } else {
    url.searchParams.delete("shop");
  }
  url.searchParams.set("seat", seat);
  window.history.replaceState({}, "", url);
}

export default function App() {
  const [collection, setCollection] = useState<FeatureCollection | null>(null);
  const [manifest, setManifest] = useState<WorldManifest | null>(null);
  const [places, setPlaces] = useState<Place[]>([]);
  const [catalogLoad, setCatalogLoad] = useState<CatalogLoad>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(readPlaceFromUrl);
  const [selectedShopId, setSelectedShopId] = useState<string | null>(readShopFromUrl);
  const [query, setQuery] = useState("");
  const extrusionOn = true;
  const [menuOpen, setMenuOpen] = useState(false);
  const [webglOk, setWebglOk] = useState(() =>
    typeof window === "undefined" ? true : detectPlayWebgl(),
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [playPainted, setPlayPainted] = useState(false);
  const [minimapLive, setMinimapLive] = useState(false);
  const poseRef = useRef<"idle" | "walk">("idle");
  const isMoveHeldRef = useRef<() => boolean>(() => false);
  const [copyMsg, setCopyMsg] = useState("");
  const [bookmarks, setBookmarks] = useState<Bookmark[]>(() => loadBookmarks());
  const [followAvatar, setFollowAvatar] = useState(true);
  const [ownerOfflineSim, setOwnerOfflineSim] = useState(true);
  const [networkCutSim, setNetworkCutSim] = useState(false);
  const [demoIdentity, setDemoIdentity] = useState(() => loadDemoIdentity());
  const [localRows, setLocalRows] = useState(() => loadLocalListings());
  const [localShops, setLocalShops] = useState(() => loadLocalShops());
  const [seat, setSeat] = useState<SeatId>(() => readSeatFromUrl());
  const [presenceMode, setPresenceMode] = useState<PresenceMode>(
    () => loadSeatMode(readSeatFromUrl()).mode,
  );
  const [optedIn, setOptedIn] = useState(() => loadSeatMode(readSeatFromUrl()).opted_in);
  const [browserOnline, setBrowserOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  const { graph, applyOp } = useFriendGraph();
  const connected = browserOnline && !networkCutSim;
  const connection = useConnectionPill(connected);

  const buildings = useMemo(
    () => (collection ? buildingsFromCollection(collection) : []),
    [collection],
  );
  const mergedCatalog = useMemo(() => {
    if (catalogLoad.status !== "ok") {
      return null;
    }
    const withShops = mergeCatalogShops(catalogLoad.catalog, toCatalogShops(localShops));
    return mergeCatalogListings(withShops, toCatalogListings(localRows));
  }, [catalogLoad, localRows, localShops]);
  const shops = useMemo(
    () => (mergedCatalog ? publicShops(mergedCatalog) : []),
    [mergedCatalog],
  );
  const listings = useMemo(
    () => (mergedCatalog ? publicListings(mergedCatalog) : []),
    [mergedCatalog],
  );
  const playStreets = useMemo(
    () => (collection ? worldFromCollection(collection).streets : []),
    [collection],
  );
  const walkSolids = useMemo(
    () =>
      collection
        ? [
            ...buildings,
            ...streetPropSolidsFromCollection(collection),
            ...streetPlaqueSolidsFromCollection(collection),
            ...shopStallSolids(shops, playStreets),
            ...marketSpillSolids(marketSpillFromCollection(collection, shops)),
          ]
        : buildings,
    [buildings, collection, playStreets, shops],
  );
  const canPublish = networkAllowsPublish(browserOnline, networkCutSim);

  const openShop = (id: string) => {
    if (!shops.some((shop) => shop.shop_id === id)) {
      return;
    }
    const shop = findShop(shops, id);
    setSelectedShopId(id);
    if (shop) {
      setSelectedId(shop.place_id);
    }
    setCopyMsg("");
  };

  const closeShop = () => {
    setSelectedShopId(null);
    setFollowAvatar(true);
  };

  const interactRef = useRef(() => {});
  const spawn = SEAT_SPAWNS[seat];
  const { avatar, blocked, slid, look, applyLookDeltaPx, setLookMode, setPad, resetPad, jump, isMoveHeld } =
    useAvatar(
    walkSolids,
    AOI_BBOX,
    () => {
      interactRef.current();
    },
    spawn,
    SEAT_LOOK_PITCH[seat],
    SEAT_LOOK_YAW[seat],
  );
  poseRef.current = avatar.pose;
  isMoveHeldRef.current = isMoveHeld;
  const listsOpen = !webglOk || menuOpen;
  const { remotes } = usePresence({
    seat,
    avatar,
    mode: presenceMode,
    optedIn,
    connected,
    graph,
    viewingShopId: selectedShopId,
  });
  const streetHud = useMemo(
    () => (collection ? namedStreetHudAtLonLat(collection, avatar.lon, avatar.lat) : null),
    [avatar.lat, avatar.lon, collection],
  );
  interactRef.current = () => {
    const near = nearestPublishedShop(
      avatar,
      shops,
      NEARBY_SHOP_M,
      (shop) => shopPlayLngLat(shop, playStreets),
      streetHud?.distM,
    );
    if (near) {
      openShop(near.shop_id);
    }
  };

  useEffect(() => {
    if (!webglOk || !playPainted || minimapLive) {
      return;
    }
    let cancelled = false;
    let raf = 0;
    let last = performance.now();
    let idlePoseMs = 0;
    const tick = (now: number) => {
      if (cancelled) {
        return;
      }
      const dt = Math.max(0, now - last);
      last = now;
      const walkHeld = isMoveHeldRef.current();
      const pose = poseRef.current;
      if (walkHeld || pose === "walk") {
        idlePoseMs = 0;
      } else {
        idlePoseMs += dt;
      }
      if (minimapMayConstruct(true, idlePoseMs, pose, walkHeld)) {
        setMinimapLive(true);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [webglOk, playPainted, minimapLive]);

  useEffect(() => {
    let cancelled = false;
    fetch("/data/ben-thanh-400m.authored.geojson")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`GeoJSON HTTP ${res.status}`);
        }
        return res.json() as Promise<FeatureCollection>;
      })
      .then((geo) => {
        if (cancelled) {
          return;
        }
        setCollection(geo);
        setPlaces(placesFromCollection(geo));
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load local fixture");
        }
      });
    fetch("/data/world-manifest.json")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Manifest HTTP ${res.status}`);
        }
        return res.json() as Promise<WorldManifest>;
      })
      .then((world) => {
        if (!cancelled) {
          setManifest(world);
        }
      })
      .catch(() => {
        /* honesty still renders without manifest dates */
      });
    fetch("/data/shops.json")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Shops HTTP ${res.status}`);
        }
        return res.json() as Promise<unknown>;
      })
      .then((shopRaw) => {
        if (cancelled) {
          return;
        }
        const parsed = parseShopCatalog(shopRaw);
        if (!parsed) {
          setCatalogLoad({ status: "unavailable", reason: "invalid catalog" });
          return;
        }
        setCatalogLoad({
          status: "ok",
          catalog: parsed,
          loadedAt: new Date().toISOString(),
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setCatalogLoad({
            status: "unavailable",
            reason: err instanceof Error ? err.message : "Chưa tải cửa hàng này",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    writeUrl(selectedId, selectedShopId, seat);
  }, [selectedId, selectedShopId, seat]);

  useEffect(() => {
    saveSeatMode(seat, { mode: presenceMode, opted_in: optedIn });
  }, [seat, presenceMode, optedIn]);

  const changeSeat = (next: SeatId) => {
    const saved = loadSeatMode(next);
    setSeat(next);
    setPresenceMode(saved.mode);
    setOptedIn(saved.opted_in);
    setFollowAvatar(true);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) {
        return;
      }
      if (event.key === "Escape") {
        if (selectedShopId) {
          closeShop();
          return;
        }
        if (menuOpen) {
          setMenuOpen(false);
          return;
        }
        setSelectedId(null);
      }
      if (event.key === "Tab" && webglOk) {
        event.preventDefault();
        setMenuOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedShopId, menuOpen, webglOk]);

  useEffect(() => {
    const on = () => setBrowserOnline(true);
    const off = () => setBrowserOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  useEffect(() => {
    const applyIncoming = (incoming: {
      shops: typeof localShops;
      listings: typeof localRows;
    }) => {
      const publishedShops = incoming.shops.filter((row) => row.status === "published");
      const publishedListings = incoming.listings.filter((row) => row.status === "published");
      setLocalShops((prev) => {
        const merged = keepLocalDrafts(prev, publishedShops, (row) => row.shop_id);
        if (merged.length === prev.length && merged.every((row, i) => row.shop_id === prev[i]?.shop_id && row.version === prev[i]?.version && row.status === prev[i]?.status)) {
          return prev;
        }
        return saveLocalShops(merged);
      });
      setLocalRows((prev) => {
        const merged = keepLocalDrafts(prev, publishedListings, (row) => row.listing_id);
        if (
          merged.length === prev.length &&
          merged.every((row, i) => row.listing_id === prev[i]?.listing_id && row.version === prev[i]?.version && row.status === prev[i]?.status)
        ) {
          return prev;
        }
        return saveLocalListings(merged);
      });
    };
    const stop = subscribeLocalBus((event) => {
      if (event.type === "catalog") {
        applyIncoming(event.catalog);
      }
    });
    const pull = async () => {
      const snap = await pullDemoBus();
      if (!snap) {
        return;
      }
      applyIncoming(snap.catalog);
    };
    void pull();
    const id = window.setInterval(() => {
      void pull();
    }, 400);
    return () => {
      stop();
      window.clearInterval(id);
    };
  }, []);

  const selected = findPlace(places, selectedId);
  const selectedShop = findShop(shops, selectedShopId);
  const placeShop = shopByPlace(shops, selectedId);
  const playShops = streetPlayShops(shops);
  const nearby = nearestPublishedShop(
    avatar,
    playShops,
    NEARBY_SHOP_M,
    (shop) => shopPlayLngLat(shop, playStreets),
    streetHud?.distM,
  );
  const authoredStall =
    playShops.find((shop) => shop.shop_id === "shop-lantern-fish") ?? playShops[0] ?? null;
  const stall = nearby ?? authoredStall;
  const stallRangeM = stall ? distanceM(avatar, shopPlayLngLat(stall, playStreets)) : null;
  const visible = useMemo(
    () => searchPlaces(places, query, shops, listings),
    [places, query, shops, listings],
  );

  const selectPlace = (id: string) => {
    if (!places.some((place) => place.id === id)) {
      return;
    }
    setSelectedId(id);
    setFollowAvatar(false);
    setCopyMsg("");
  };

  const share = async () => {
    if (!selected) {
      return;
    }
    const shopPart = selectedShopId ? `&shop=${encodeURIComponent(selectedShopId)}` : "";
    const link = `${window.location.origin}/?place=${encodeURIComponent(selected.id)}${shopPart}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopyMsg("Copied local link.");
    } catch {
      setCopyMsg(link);
    }
  };

  const publishCatalog = (shops: typeof localShops, rows: typeof localRows) => {
    const catalog = publishedShopCatalog({
      ...emptyShopCatalog(Date.now()),
      shops,
      listings: rows,
    });
    publishLocalCatalog(catalog);
    void pushDemoBus({ catalog });
  };

  const listProduct = (title: string, kind: ListingKind) => {
    if (!selectedShopId) {
      return null;
    }
    const row = createLocalListing({
      shopId: selectedShopId,
      title,
      kind,
      canPublish,
    });
    if (!row) {
      return null;
    }
    const nextRows = saveLocalListings([...localRows, row]);
    setLocalRows(nextRows);
    publishCatalog(localShops, nextRows);
    return row;
  };

  const retryDraft = (listingId: string) => {
    const nextRows = saveLocalListings(retryQueuedListing(localRows, listingId, canPublish));
    setLocalRows(nextRows);
    publishCatalog(localShops, nextRows);
  };

  const createShop = (name: string, sells: string) => {
    const shop = createLocalShop({
      name,
      sells,
      lon: avatar.lon,
      lat: avatar.lat,
      canPublish,
      existing: shops,
      streets: playStreets,
    });
    if (!shop) {
      return null;
    }
    const listing = createLocalListing({
      shopId: shop.shop_id,
      title: sells,
      kind: inferKind(sells),
      canPublish,
    });
    const nextShops = saveLocalShops([...localShops, shop]);
    const nextRows = listing ? saveLocalListings([...localRows, listing]) : localRows;
    setLocalShops(nextShops);
    setLocalRows(nextRows);
    publishCatalog(nextShops, nextRows);
    return { shop, listing };
  };

  const exportLocal = () => {
    const blob = new Blob([exportBookmarks(bookmarks)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hh-world-bookmarks.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const mapShared = {
    collection,
    places: visible,
    shops,
    selectedId,
    selectedShopId,
    extrusionOn,
    avatar,
    followAvatar,
    seat,
    remotes,
    onSelect: selectPlace,
    onSelectShop: openShop,
    onWebgl: setWebglOk,
    onBearing: () => {},
    onCameraFreed: () => setFollowAvatar(false),
    activeLaneName: streetHud?.name ?? "",
    activeLaneRole: streetHud?.role ?? "",
  };

  return (
    <div
      className={webglOk ? "app app-play" : "app"}
      data-menu={listsOpen ? "open" : "closed"}
    >
      {webglOk && collection ? (
        <PlayView
          collection={collection}
          buildings={buildings}
          avatar={avatar}
          look={look}
          seat={seat}
          remotes={remotes}
          shops={shops}
          listings={listings}
          selectedShopId={selectedShopId}
          onSelectShop={openShop}
          onLookDelta={applyLookDeltaPx}
          onLookMode={setLookMode}
          onFirstFrame={() => setPlayPainted(true)}
          blocked={blocked}
          slid={slid}
        />
      ) : null}
      {webglOk && (!collection || !playPainted) ? <PlayLoading /> : null}
      <div className="hud-top">
        <Header
          menuOpen={listsOpen}
          onMenu={webglOk ? () => setMenuOpen((open) => !open) : undefined}
        />
        <HonestyBanner manifest={manifest} compact={webglOk} />
        {webglOk ? (
          <StreetChip name={streetHudLabel(streetHud)} role={streetHud?.role ?? ""} />
        ) : null}
        {webglOk ? <FpsChip /> : null}
        {webglOk ? (
          <ViewingChip remotes={remotes} shops={shops} onOpenShop={openShop} />
        ) : null}
        <ModeStatus presenceMode={presenceMode} connection={connection} />
      </div>
      {loadError ? <p className="error hud-error">Could not load local fixture: {loadError}</p> : null}
      {catalogLoad.status === "unavailable" ? (
        <p className="error hud-error" data-testid="shop-unavailable">
          Chưa tải cửa hàng này ({catalogLoad.reason})
        </p>
      ) : null}
      <div className="workspace">
        <section className={webglOk ? "map-pane map-pane-play" : "map-pane"}>
          {webglOk ? (
            <>
              <PlayAvatarHud
                avatar={avatar}
                look={look}
                seat={seat}
                buildings={buildings}
                blocked={blocked}
                slid={slid}
              />
              <div
                className="minimap-wrap"
                data-testid="hh-world-minimap-wrap"
                data-minimap-defer={minimapLive ? "live" : "pending"}
                data-minimap-defer-kind={MINIMAP_DEFER_KIND}
                data-minimap-defer-ms={String(MINIMAP_DEFER_MS)}
                data-minimap-clear={selectedShop ? "1" : "0"}
                data-minimap-attrib="caption"
              >
                <p className="minimap-caption">2D · not OSM</p>
                {minimapLive ? (
                  <MapView {...mapShared} variant="minimap" />
                ) : (
                  <div className="map-host map-host-mini" aria-hidden="true" />
                )}
              </div>
            </>
          ) : (
            <>
              <p className="fallback" data-testid="webgl-fallback">
                WebGL is off. Use the place list and goods list. Your character still
                walks in-app (WASD / pad). 2D map is the fallback, not Play.
              </p>
              <MapView {...mapShared} variant="world" />
            </>
          )}
          <StreetHelp
            nearbyName={nearby?.name ?? null}
            nearbyShopId={nearby?.shop_id ?? null}
            stallName={stall?.name ?? null}
            stallRangeM={stallRangeM}
            shopCount={playShops.length}
            followOn={followAvatar}
            pose={avatar.pose}
            heading={avatar.heading}
            airborne={avatar.airborne}
            sprint={avatar.sprint}
            turning={avatar.turning}
            looking={look.mode !== "off"}
            compact={webglOk}
            onOpenNearby={() => {
              if (nearby) {
                openShop(nearby.shop_id);
              }
            }}
            onRecenter={() => setFollowAvatar(true)}
          />
          <WalkPad
            onPad={setPad}
            onRelease={resetPad}
            canInteract={Boolean(nearby)}
            onInteract={() => {
              if (nearby) {
                openShop(nearby.shop_id);
              }
            }}
            onJump={jump}
          />
        </section>
        <aside
          id="play-menu"
          className="side"
          data-testid="play-menu"
          data-open={listsOpen ? "yes" : "no"}
          hidden={!listsOpen}
        >
          <ModeBar
            networkCutSim={networkCutSim}
            onNetworkCutSim={setNetworkCutSim}
            identitySignedIn={demoIdentity.signed_in}
            presenceMode={presenceMode}
            optedIn={optedIn}
            onPresenceMode={setPresenceMode}
            onOptedIn={setOptedIn}
            remotes={remotes}
            seat={seat}
            connected={connected}
            connection={connection}
          />
          <FriendsBar
            seat={seat}
            graph={graph}
            remotes={remotes}
            onSeat={changeSeat}
            onOp={applyOp}
            onOpenShop={openShop}
          />
          <SearchBox query={query} onQuery={setQuery} />
          <CreateShopForm
            identity={demoIdentity}
            canPublish={canPublish}
            publicCount={shops.length}
            onBecomeOwner={() => setDemoIdentity(becomeDemoOwner())}
            onLeaveOwner={() => setDemoIdentity(leaveDemoOwner())}
            onCreate={createShop}
          />
          <PlaceList places={visible} selectedId={selectedId} onSelect={selectPlace} />
          <GoodsList
            shops={shops}
            listings={listings}
            query={query}
            loadedAt={catalogLoad.status === "ok" ? catalogLoad.loadedAt : null}
            onOpenShop={openShop}
          />
          <PlaceCard
            place={selected}
            bookmarked={selected ? isBookmarked(bookmarks, selected.id) : false}
            copyMsg={copyMsg}
            shopName={placeShop?.name ?? null}
            onOpenShop={placeShop ? () => openShop(placeShop.shop_id) : undefined}
            onBookmark={() => {
              if (!selected) {
                return;
              }
              setBookmarks(
                toggleBookmark(bookmarks, selected.id, new Date().toISOString()),
              );
            }}
            onShare={() => {
              void share();
            }}
            onClose={() => setSelectedId(null)}
          />
          <BookmarkPanel
            bookmarks={bookmarks}
            places={places}
            onOpen={selectPlace}
            onReset={() => setBookmarks(resetBookmarks())}
            onExport={exportLocal}
          />
        </aside>
        <ShopPanel
          shop={selectedShop}
          catalog={mergedCatalog}
          ownerOfflineSim={ownerOfflineSim}
          onOwnerOfflineSim={setOwnerOfflineSim}
          networkCutSim={networkCutSim}
          onNetworkCutSim={setNetworkCutSim}
          identity={demoIdentity}
          drafts={localRows}
          canPublish={canPublish}
          onBecomeOwner={() => setDemoIdentity(becomeDemoOwner())}
          onLeaveOwner={() => setDemoIdentity(leaveDemoOwner())}
          onListProduct={listProduct}
          onRetryDraft={retryDraft}
          onClose={closeShop}
        />
      </div>
    </div>
  );
}
