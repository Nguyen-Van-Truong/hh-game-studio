import type { Place } from "../contracts/types";

type PlaceListProps = {
  places: Place[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export function PlaceList({ places, selectedId, onSelect }: PlaceListProps) {
  return (
    <section className="list" data-testid="place-list">
      <h2>Places</h2>
      {places.length === 0 ? (
        <p>No places match.</p>
      ) : (
        <ul>
          {places.map((place) => (
            <li key={place.id}>
              <button
                type="button"
                className={place.id === selectedId ? "active" : ""}
                onClick={() => onSelect(place.id)}
              >
                <span>{place.name}</span>
                <small>approx</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
