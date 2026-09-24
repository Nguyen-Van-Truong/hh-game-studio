# S221 — S218 retained RSS gate failure

The fresh formal campaign `gt06-s218-formal-01` completed six captured batches (0–5) and stopped during batch 5 joint observation with `CAMPAIGN_RSS_GROWTH`. Raw evidence is sealed before any follow-up. Batch 4 to batch 5 editor RSS rose from 105934848 to 161259520 bytes while editor objects remained 71128, resources 6, and held handles 555; host handles remained 204. This is a gate-row observation only and does not prove a leak, ownership, or root cause.

Authority remains 0. The 10×35 gate, timeout, baseline, profile, counter and RSS policy are unchanged; partial batches are not merged. The next step is review of a proven RSS measurement boundary or an owner ADR, then a fresh campaign ID only.
