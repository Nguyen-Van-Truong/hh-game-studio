import { useState } from "react";
import { DEMO_DISPLAY_NAME, type DemoIdentity } from "../account/demoIdentity";
import type { LocalListing } from "./localListings";
import type { LocalShop } from "./localShops";

type CreateShopFormProps = {
  identity: DemoIdentity;
  canPublish: boolean;
  publicCount: number;
  onBecomeOwner: () => void;
  onLeaveOwner: () => void;
  onCreate: (name: string, sells: string) => { shop: LocalShop; listing: LocalListing | null } | null;
};

export function CreateShopForm({
  identity,
  canPublish,
  publicCount,
  onBecomeOwner,
  onLeaveOwner,
  onCreate,
}: CreateShopFormProps) {
  const [name, setName] = useState("Quầy Phở Nhà");
  const [sells, setSells] = useState("Phở bò");
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ shop: LocalShop; listing: LocalListing | null } | null>(
    null,
  );

  return (
    <section className="create-shop" data-testid="create-shop">
      <h2>Open a shop</h2>
      <p className="muted">
        Name the stall and say what it sells (cá, túi, phở, sách, …). The lantern
        stall is one example among many. Marker appears at your character.
        NOT a real account. NOT_PLAN_PASS.
      </p>
      <p data-testid="public-shop-count" data-count={publicCount}>
        Public shops on this map: {publicCount}
      </p>
      <p data-testid="create-shop-identity">
        {identity.signed_in
          ? `${DEMO_DISPLAY_NAME} — local demo identity. NOT a real account. NOT Google/OIDC. NOT_PLAN_PASS.`
          : "Guest on this machine. Become the local demo owner to open a shop."}
      </p>
      {identity.signed_in ? (
        <button type="button" data-testid="leave-demo-owner" onClick={onLeaveOwner}>
          Leave demo owner (back to guest)
        </button>
      ) : (
        <button type="button" data-testid="become-demo-owner" onClick={onBecomeOwner}>
          Become {DEMO_DISPLAY_NAME}
        </button>
      )}
      {identity.signed_in ? (
        <form
          className="list-form"
          data-testid="create-shop-form"
          data-network={canPublish ? "on" : "off"}
          onSubmit={(event) => {
            event.preventDefault();
            const created = onCreate(name, sells);
            if (!created) {
              setResult(null);
              setError("Name or goods rejected. Plain text, 2–80 characters. No prohibited items.");
              return;
            }
            setError("");
            setResult(created);
          }}
        >
          <label>
            Shop name
            <input
              data-testid="create-shop-name"
              value={name}
              maxLength={80}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            What this shop sells
            <input
              data-testid="create-shop-good"
              value={sells}
              maxLength={80}
              onChange={(event) => setSells(event.target.value)}
            />
          </label>
          <button type="submit" data-testid="create-shop-submit">
            {canPublish ? "Open shop at my character (this machine)" : "Save shop as draft / queue"}
          </button>
          {error ? <p className="error">{error}</p> : null}
          {result ? (
            <p
              data-testid="create-shop-result"
              data-status={result.shop.status}
              data-shop={result.shop.shop_id}
              data-listing={result.listing?.listing_id ?? ""}
            >
              {result.shop.status === "published"
                ? `Shop is on the map. Walk up to the stall (~4 m) and press E. Not a server ACK. Not a real account.`
                : "Chưa đăng — nháp chờ mạng. Not posted."}
            </p>
          ) : null}
        </form>
      ) : (
        <p className="muted">
          Browse does not need an account. Opening a shop uses the labeled local
          demo identity only. R4-WP0B is not built.
        </p>
      )}
    </section>
  );
}
