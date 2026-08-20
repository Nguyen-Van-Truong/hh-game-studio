use gs_scene::{format_entity_id, parse_entity_id};

/// Internal numeric ids for `gs.spawn` live in this reserved range so they
/// never collide with document entities (camera is often `1`).
pub const RUNTIME_ID_BASE: u64 = 1 << 40;

/// MASTER 7.2 / 7.6: at most 1000 `gs.spawn` calls commit per simulate frame.
pub const SPAWN_CAP_PER_FRAME: u32 = 1000;

const RUNTIME_PREFIX: &str = "rt_";

/// Public play id: document entities stay `e_000042`; runtime-spawned are `rt_N`.
pub fn format_play_id(id: u64) -> String {
    if let Some(seq) = runtime_seq(id) {
        format!("{RUNTIME_PREFIX}{seq}")
    } else {
        format_entity_id(id)
    }
}

/// Accepts `e_000001` / `e_1` and `rt_1` / `rt_0001`.
pub fn parse_play_id(id: &str) -> Option<u64> {
    if let Some(rest) = id.strip_prefix(RUNTIME_PREFIX) {
        if rest.is_empty() || !rest.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        return rest.parse::<u64>().ok().and_then(runtime_id_from_seq);
    }
    parse_entity_id(id).ok()
}

pub fn runtime_id_from_seq(seq: u64) -> Option<u64> {
    if seq == 0 {
        return None;
    }
    RUNTIME_ID_BASE.checked_add(seq)
}

pub fn runtime_seq(id: u64) -> Option<u64> {
    id.checked_sub(RUNTIME_ID_BASE).filter(|seq| *seq > 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn play_ids_accept_document_and_runtime() {
        assert_eq!(parse_play_id("e_000001"), Some(1));
        assert_eq!(parse_play_id("e_000042"), Some(42));
        assert_eq!(parse_play_id("rt_1"), Some(RUNTIME_ID_BASE + 1));
        assert_eq!(parse_play_id("rt_2"), Some(RUNTIME_ID_BASE + 2));
        assert_eq!(format_play_id(1), "e_000001");
        assert_eq!(format_play_id(RUNTIME_ID_BASE + 1), "rt_1");
        assert_eq!(parse_play_id("rt_0"), None);
        assert_eq!(parse_play_id("nope"), None);
    }
}
