/**
 * Local demo allowlist. Not a legal review and not M1-WP1.
 * Blocks obvious illegal / CSAM / doxxing strings. Does not claim complete policy.
 * Match after fold: lowercase, strip Vietnamese diacritics, collapse spaces/punctuation
 * so "ban sung", "bán-súng", and "BÁN SÚNG" hit the same rule as "bán súng".
 */
const BLOCKED: RegExp[] = [
  /\bcsam\b/i,
  /\bchild\s*porn/i,
  /\bchild\s*sexual\b/i,
  /\bsexual(?:ized)?\s+(?:content\s+)?(?:of\s+)?(?:a\s+)?(?:minor|child|children|kid)\b/i,
  /anh\s*nong\s*(?:tre|be|em\s*nho)/i,
  /tre\s*em.{0,24}(?:tinh\s*duc|sex|nude)/i,
  /\bdoxx?(?:ing)?\b/i,
  /\b(?:ssn|social\s*security\s*number)\b/i,
  /\b(?:cmnd|cccd)\s*\d/i,
  /passport\s*(?:no|number|\d)/i,
  /home\s*address/i,
  /so\s*nha\s*\d+/i,
  /\b(?:cocaine|heroin|fentanyl|methamphetamine)\b/i,
  /(?:ban|mua)\s*(?:ma\s*tuy|heroin)/i,
  /\b(?:unlicensed\s*firearm|ban\s*sung)\b/i,
  /\b(?:c4\s*explosive|ricin)\b/i,
];

function foldForMatch(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/\p{M}+/gu, "")
    .replace(/đ/gi, "d")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

export function isProhibitedText(raw: string): boolean {
  const text = raw.trim();
  if (!text) {
    return false;
  }
  const folded = foldForMatch(text);
  if (!folded) {
    return false;
  }
  return BLOCKED.some((rule) => rule.test(folded));
}

export function sanitizePublicText(raw: string): string | null {
  const title = raw.trim().replace(/\s+/g, " ");
  if (title.length < 2 || title.length > 80) {
    return null;
  }
  if (/[<>]/.test(title)) {
    return null;
  }
  if (isProhibitedText(title)) {
    return null;
  }
  return title;
}
