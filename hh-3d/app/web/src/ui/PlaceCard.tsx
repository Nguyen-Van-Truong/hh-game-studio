import type { Place } from "../contracts/types";

type PlaceCardProps = {
  place: Place | null;
  bookmarked: boolean;
  copyMsg: string;
  shopName?: string | null;
  onOpenShop?: () => void;
  onBookmark: () => void;
  onShare: () => void;
  onClose: () => void;
};

export function PlaceCard({
  place,
  bookmarked,
  copyMsg,
  shopName,
  onOpenShop,
  onBookmark,
  onShare,
  onClose,
}: PlaceCardProps) {
  if (!place) {
    return (
      <article className="card" data-testid="place-card-empty">
        <h2>Place card</h2>
        <p>Select a place on the map or in the list.</p>
      </article>
    );
  }

  return (
    <article className="card" data-testid="place-card">
      <div className="card-head">
        <h2>{place.name}</h2>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="approx" data-testid="place-approx">
        approx
      </p>
      <p>{place.summary}</p>
      <dl>
        <div>
          <dt>Map data as of</dt>
          <dd>{place.acquired_at.slice(0, 10)}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{place.authored_or_source}</dd>
        </div>
        <div>
          <dt>Accuracy</dt>
          <dd>{place.accuracy_class}</dd>
        </div>
        <div>
          <dt>Height</dt>
          <dd>
            {place.height_m === null
              ? "unknown"
              : `${place.height_m} m (${place.height_confidence})`}
          </dd>
        </div>
      </dl>
      <p className="muted">{place.honesty}</p>
      <div className="card-actions">
        {shopName && onOpenShop ? (
          <button type="button" data-testid="open-place-shop" onClick={onOpenShop}>
            Open {shopName}
          </button>
        ) : null}
        <button type="button" data-testid="bookmark-btn" onClick={onBookmark}>
          {bookmarked ? "Remove bookmark" : "Bookmark locally"}
        </button>
        <button type="button" data-testid="share-btn" onClick={onShare}>
          Copy local link
        </button>
      </div>
      {copyMsg ? <p className="copy-msg">{copyMsg}</p> : null}
    </article>
  );
}
