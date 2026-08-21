import type { Credential } from "../credentials.js";
import { E, HostError } from "../errors.js";
import type { ModelContext, ModelTurn, Provider } from "./types.js";

/**
 * Pins model/config from the user store. Does not open a network session
 * in this pin — official tests use the fake provider.
 */
export class ConfiguredProvider implements Provider {
  readonly name = "configured";
  readonly model: string;

  constructor(cred: Credential) {
    this.model = cred.model;
  }

  generate(_ctx: ModelContext): ModelTurn {
    throw new HostError(
      E.E_EXTERNAL,
      "configured provider does not open a network session in this pin",
      "network",
    );
  }
}
