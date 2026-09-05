import type { Bookmark, Place } from "../contracts/types";

type BookmarkPanelProps = {
  bookmarks: Bookmark[];
  places: Place[];
  onOpen: (id: string) => void;
  onReset: () => void;
  onExport: () => void;
};

export function BookmarkPanel({
  bookmarks,
  places,
  onOpen,
  onReset,
  onExport,
}: BookmarkPanelProps) {
  return (
    <section className="bookmarks" data-testid="bookmark-panel">
      <h2>Local bookmarks</h2>
      <p className="muted">Stored in this browser only. No login.</p>
      {bookmarks.length === 0 ? (
        <p>None yet.</p>
      ) : (
        <ul>
          {bookmarks.map((row) => {
            const place = places.find((item) => item.id === row.id);
            return (
              <li key={row.id}>
                <button type="button" onClick={() => onOpen(row.id)}>
                  {place?.name ?? row.id}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <div className="card-actions">
        <button type="button" data-testid="export-bookmarks" onClick={onExport}>
          Export
        </button>
        <button type="button" data-testid="reset-bookmarks" onClick={onReset}>
          Reset
        </button>
      </div>
    </section>
  );
}
