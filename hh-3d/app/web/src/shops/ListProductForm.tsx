import { useState } from "react";
import { inferKind, presetForKind } from "./localListings";
import type { LocalListing } from "./localListings";
import type { ListingKind } from "./types";

type ListProductFormProps = {
  canPublish: boolean;
  onList: (title: string, kind: ListingKind) => LocalListing | null;
};

export function ListProductForm({ canPublish, onList }: ListProductFormProps) {
  const [kind, setKind] = useState<ListingKind>("fish");
  const [title, setTitle] = useState(presetForKind("fish").title);
  const [result, setResult] = useState<LocalListing | null>(null);
  const [error, setError] = useState("");

  const applyKind = (next: ListingKind) => {
    setKind(next);
    setTitle(presetForKind(next).title);
  };

  return (
    <form
      className="list-form"
      data-testid="list-product-form"
      data-network={canPublish ? "on" : "off"}
      onSubmit={(event) => {
        event.preventDefault();
        const nextKind = kind === "other" ? inferKind(title) : kind;
        const row = onList(title, nextKind);
        if (!row) {
          setResult(null);
          setError("Title was rejected. Use plain text, 2–80 characters. No prohibited items.");
          return;
        }
        setError("");
        setResult(row);
      }}
    >
      <p className="muted">
        List any allowed good on this shelf (cá, túi, phở, sách, …). Social
        Offline does not block listing when the browser has network.
      </p>
      <p data-testid="list-kind" data-kind={kind}>
        Kind shortcut:{" "}
        <button
          type="button"
          data-testid="list-kind-fish"
          aria-pressed={kind === "fish"}
          onClick={() => applyKind("fish")}
        >
          Cá / fish
        </button>
        <button
          type="button"
          data-testid="list-kind-bag"
          aria-pressed={kind === "bag"}
          onClick={() => applyKind("bag")}
        >
          Túi / bag
        </button>
        <button
          type="button"
          data-testid="list-kind-other"
          aria-pressed={kind === "other"}
          onClick={() => applyKind("other")}
        >
          Khác / other
        </button>
      </p>
      <label>
        Title
        <input
          data-testid="list-title"
          value={title}
          maxLength={80}
          onChange={(event) => {
            setTitle(event.target.value);
            setKind(inferKind(event.target.value));
          }}
        />
      </label>
      <button type="submit" data-testid="list-submit">
        {canPublish ? "Put on the public shelf (this machine)" : "Save as draft / queue"}
      </button>
      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <p
          data-testid="list-result"
          data-status={result.status}
          data-listing={result.listing_id}
        >
          {result.status === "published"
            ? "On the public shelf (this machine). Not a server ACK. Not a real account."
            : "Chưa đăng — nháp chờ mạng. Not posted."}
        </p>
      ) : null}
    </form>
  );
}
