import { redactSecrets } from "./token.js";

export interface SessionLog {
  info(message: string): void;
  error(message: string): void;
}

export function createSessionLog(secrets: () => readonly string[]): SessionLog {
  const write = (line: string): void => {
    process.stderr.write(`${redactSecrets(line, secrets())}\n`);
  };
  return {
    info: write,
    error: write,
  };
}
