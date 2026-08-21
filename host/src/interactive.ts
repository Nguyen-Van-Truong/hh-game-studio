/**
 * Interactive Codex / Cursor / Claude: the IDE client IS the Host.
 * This module re-exports the same Host class used by the persistent process
 * so both paths share plan state and tool results.
 */
export { Host, type HostOptions, type HostReport } from "./host.js";
