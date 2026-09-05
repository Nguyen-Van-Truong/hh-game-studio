import { STREET_HUD_EMPTY, STREET_HUD_KIND } from "../play/world";

type StreetChipProps = {
  name: string;
  role: string;
};

/** One slim authored-name chip. Not a panel. Not GPS. */
export function StreetChip({ name, role }: StreetChipProps) {
  const label = name || STREET_HUD_EMPTY;
  return (
    <p
      className="street-chip"
      data-testid="play-street-chip"
      data-street-hud={STREET_HUD_KIND}
      data-street-name={label}
      data-street-role={role}
      title="Authored street name. Fixture only — not GPS, not OSM."
    >
      {label}
    </p>
  );
}
