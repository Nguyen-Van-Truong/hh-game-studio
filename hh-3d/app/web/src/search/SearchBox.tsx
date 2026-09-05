type SearchBoxProps = {
  query: string;
  onQuery: (value: string) => void;
};

export function SearchBox({ query, onQuery }: SearchBoxProps) {
  return (
    <label className="search">
      <span>Find a place or goods</span>
      <input
        data-testid="place-search"
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        placeholder="Market Hall, cá, túi"
        autoComplete="off"
      />
    </label>
  );
}
