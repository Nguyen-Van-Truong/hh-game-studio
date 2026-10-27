export function readSetting(key: string): string | null { try { return localStorage.getItem(`superagent-${key}`); } catch { return null; } }
export function writeSetting(key: string,value: string): void { try { localStorage.setItem(`superagent-${key}`,value); } catch { /* Storage may be disabled; settings still work for this session. */ } }
