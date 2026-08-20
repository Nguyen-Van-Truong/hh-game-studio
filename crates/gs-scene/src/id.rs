use crate::error::Error;

pub const ENTITY_PREFIX: &str = "e_";
pub const ASSET_PREFIX: &str = "a_";
pub const TXN_PREFIX: &str = "t-";
pub const REVISION_PREFIX: &str = "r-";
pub const BLUEPRINT_PREFIX: &str = "b_";

/// Parse the numeric u64 after a fixed prefix. Comparison/sort uses this value
/// (MASTER 5.1 / C19) — not bytewise string order.
pub fn parse_id_number(id: &str, prefix: &str) -> Result<u64, Error> {
    let rest = id
        .strip_prefix(prefix)
        .ok_or_else(|| Error::invalid("id", format!("id {id:?} must start with {prefix:?}")))?;
    if rest.is_empty() || !rest.bytes().all(|b| b.is_ascii_digit()) {
        return Err(Error::invalid(
            "id",
            format!("id {id:?} must be {prefix}<digits>"),
        ));
    }
    rest.parse::<u64>()
        .map_err(|_| Error::invalid("id", format!("id {id:?} overflow")))
}

pub fn format_entity_id(n: u64) -> String {
    format!("{ENTITY_PREFIX}{n:06}")
}

/// Blueprint-local stable id (`b_1`, `b_2`, …) — not an array index (MASTER 5.3).
pub fn format_blueprint_id(n: u64) -> String {
    format!("{BLUEPRINT_PREFIX}{n}")
}

pub fn parse_blueprint_id(id: &str) -> Result<u64, Error> {
    parse_id_number(id, BLUEPRINT_PREFIX)
}

pub fn format_revision(n: u64) -> String {
    format!("{REVISION_PREFIX}{n:06}")
}

pub fn format_txn_id(seq: u64) -> String {
    format!("{TXN_PREFIX}{seq:06}")
}

pub fn parse_entity_id(id: &str) -> Result<u64, Error> {
    parse_id_number(id, ENTITY_PREFIX)
}

pub fn parse_asset_id(id: &str) -> Result<u64, Error> {
    parse_id_number(id, ASSET_PREFIX)
}

pub fn parse_revision(label: &str) -> Result<u64, Error> {
    parse_id_number(label, REVISION_PREFIX)
}

/// Sort key: numeric value after prefix. Unknown prefixes fall back to the
/// full string so the writer still produces a total order.
pub fn id_sort_key(id: &str) -> (u8, u64, &str) {
    for (rank, prefix) in [
        ENTITY_PREFIX,
        ASSET_PREFIX,
        TXN_PREFIX,
        REVISION_PREFIX,
        BLUEPRINT_PREFIX,
    ]
    .into_iter()
    .enumerate()
    {
        if let Ok(n) = parse_id_number(id, prefix) {
            return (rank as u8, n, "");
        }
    }
    (255, 0, id)
}

pub fn cmp_ids(a: &str, b: &str) -> std::cmp::Ordering {
    let ka = id_sort_key(a);
    let kb = id_sort_key(b);
    ka.0.cmp(&kb.0)
        .then_with(|| ka.1.cmp(&kb.1))
        .then_with(|| ka.2.cmp(kb.2))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numeric_id_order_not_bytewise() {
        assert_eq!(cmp_ids("e_999999", "e_1000000"), std::cmp::Ordering::Less);
        assert_eq!(cmp_ids("e_1", "e_000001"), std::cmp::Ordering::Equal);
        assert_eq!(parse_entity_id("e_000042").unwrap(), 42);
    }
}
