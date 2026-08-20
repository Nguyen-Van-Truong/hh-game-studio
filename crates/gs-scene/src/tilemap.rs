//! `tilemap.set_cells` / `tilemap.fill_rect` (MASTER 4.2 / 5.2, GS-EC-06).
//!
//! `tile < 0` erases cells. Stored scene RLE never keeps negative tiles.

use std::collections::BTreeMap;

use serde_json::{json, Value};

use crate::command::Command;
use crate::components::{
    Tilemap, TilemapLayer, MAX_TILEMAP_COORD, MAX_TILEMAP_EXPANDED_CELLS,
    MAX_TILEMAP_INLINE_WAL_BYTES,
};
use crate::document::{Document, Entity};
use crate::error::Error;
use crate::id::{format_entity_id, parse_entity_id};

const METHOD_SET: &str = "tilemap.set_cells";
const METHOD_FILL: &str = "tilemap.fill_rect";
const SPLIT_LAYER_HINT: &str = "split into multiple layers";

/// One horizontal run: `(x, len, tile)` with `tile >= 0`.
#[derive(Clone, Debug, Default)]
struct Row {
    runs: Vec<(i64, i64, i64)>,
}

impl Row {
    fn apply(&mut self, x: i64, len: i64, tile: i64) {
        self.punch(x, len);
        if tile >= 0 {
            self.runs.push((x, len, tile));
            self.runs.sort_unstable_by_key(|r| r.0);
            self.merge();
        }
    }

    fn punch(&mut self, x: i64, len: i64) {
        let end = x + len;
        let mut next = Vec::with_capacity(self.runs.len() + 1);
        for (rx, rlen, rtile) in self.runs.drain(..) {
            let rend = rx + rlen;
            if rend <= x || rx >= end {
                next.push((rx, rlen, rtile));
                continue;
            }
            if rx < x {
                next.push((rx, x - rx, rtile));
            }
            if rend > end {
                next.push((end, rend - end, rtile));
            }
        }
        self.runs = next;
    }

    fn previous_coverage(&self, x: i64, len: i64) -> Vec<(i64, i64, i64)> {
        let end = x + len;
        let mut clipped = Vec::new();
        for &(rx, rlen, rtile) in &self.runs {
            let rend = rx + rlen;
            let cx = rx.max(x);
            let cend = rend.min(end);
            if cend > cx {
                clipped.push((cx, cend - cx, rtile));
            }
        }
        let mut out = Vec::new();
        let mut cursor = x;
        for (cx, clen, ctile) in clipped {
            if cx > cursor {
                out.push((cursor, cx - cursor, -1));
            }
            out.push((cx, clen, ctile));
            cursor = cx + clen;
        }
        if cursor < end {
            out.push((cursor, end - cursor, -1));
        }
        out
    }

    fn merge(&mut self) {
        if self.runs.len() < 2 {
            return;
        }
        let mut merged = Vec::with_capacity(self.runs.len());
        let mut cur = self.runs[0];
        for &next in &self.runs[1..] {
            if cur.2 == next.2 && cur.0 + cur.1 == next.0 {
                cur.1 += next.1;
            } else {
                merged.push(cur);
                cur = next;
            }
        }
        merged.push(cur);
        self.runs = merged;
    }
}

pub(crate) fn too_many_cells(method: &str) -> Error {
    Error::invalid(
        method,
        format!("expanded cell count exceeds 1_000_000; {SPLIT_LAYER_HINT}"),
    )
}

pub(crate) fn outside_bounds(method: &str) -> Error {
    Error::invalid(
        method,
        format!("cell outside bounds (|x| or |y| > {MAX_TILEMAP_COORD}); {SPLIT_LAYER_HINT}"),
    )
}

pub(crate) fn validate_rle_run(
    x: i64,
    y: i64,
    len: i64,
    tile: i64,
    method: &str,
    allow_erase: bool,
) -> Result<(), Error> {
    if len <= 0 {
        return Err(Error::invalid(method, "RLE len must be > 0"));
    }
    if len > MAX_TILEMAP_EXPANDED_CELLS {
        return Err(too_many_cells(method));
    }
    if !allow_erase && tile < 0 {
        return Err(Error::invalid(method, "RLE tile must be >= 0"));
    }
    if !coord_ok(x) || !coord_ok(y) {
        return Err(outside_bounds(method));
    }
    let last_x = x
        .checked_add(len)
        .and_then(|s| s.checked_sub(1))
        .ok_or_else(|| Error::invalid(method, "RLE range overflow"))?;
    if !coord_ok(last_x) {
        return Err(outside_bounds(method));
    }
    Ok(())
}

fn coord_ok(v: i64) -> bool {
    (-MAX_TILEMAP_COORD..=MAX_TILEMAP_COORD).contains(&v)
}

/// Sort by (y, x) and merge adjacent same-tile runs on a row. Later input
/// runs win on overlap. Erase tiles (`tile < 0`) are dropped.
pub(crate) fn canonicalize_cells(cells: &[[i64; 4]]) -> Vec<[i64; 4]> {
    let mut rows: BTreeMap<i64, Row> = BTreeMap::new();
    for &[x, y, len, tile] in cells {
        rows.entry(y).or_default().apply(x, len, tile);
    }
    cells_from_rows(&rows)
}

fn cells_from_rows(rows: &BTreeMap<i64, Row>) -> Vec<[i64; 4]> {
    let mut cells = Vec::new();
    for (&y, row) in rows {
        for &(x, len, tile) in &row.runs {
            cells.push([x, y, len, tile]);
        }
    }
    cells
}

pub(crate) fn sum_run_lens(cells: &[[i64; 4]], method: &str) -> Result<i64, Error> {
    let mut n = 0i64;
    for run in cells {
        n = n
            .checked_add(run[2])
            .ok_or_else(|| too_many_cells(method))?;
        if n > MAX_TILEMAP_EXPANDED_CELLS {
            return Err(too_many_cells(method));
        }
    }
    Ok(n)
}

pub(crate) fn tilemap_expanded_count(tilemap: &Tilemap, method: &str) -> Result<i64, Error> {
    let mut n = 0i64;
    for layer in &tilemap.layers {
        n = n
            .checked_add(sum_run_lens(&layer.cells, method)?)
            .ok_or_else(|| too_many_cells(method))?;
        if n > MAX_TILEMAP_EXPANDED_CELLS {
            return Err(too_many_cells(method));
        }
    }
    Ok(n)
}

pub(crate) fn parse_rle_run(
    run: &Value,
    method: &str,
    allow_erase: bool,
) -> Result<[i64; 4], Error> {
    let arr = run
        .as_array()
        .ok_or_else(|| Error::invalid(method, "RLE run must be an array"))?;
    let (x, y, len, tile) = match arr.len() {
        4 => (
            json_i64(&arr[0], method, "RLE x")?,
            json_i64(&arr[1], method, "RLE y")?,
            json_i64(&arr[2], method, "RLE len")?,
            json_i64(&arr[3], method, "RLE tile")?,
        ),
        3 => (
            json_i64(&arr[0], method, "RLE x")?,
            json_i64(&arr[1], method, "RLE y")?,
            1,
            json_i64(&arr[2], method, "RLE tile")?,
        ),
        _ => {
            return Err(Error::invalid(
                method,
                "RLE run must be [x,y,len,tile] or [x,y,tile]",
            ));
        }
    };
    validate_rle_run(x, y, len, tile, method, allow_erase)?;
    Ok([x, y, len, tile])
}

fn json_i64(v: &Value, method: &str, what: &str) -> Result<i64, Error> {
    v.as_i64()
        .ok_or_else(|| Error::invalid(method, format!("{what} must be int")))
}

fn reject_large_inline(method: &str, params: &Value) -> Result<(), Error> {
    let n = serde_json::to_vec(params).map(|b| b.len()).unwrap_or(0);
    if n > MAX_TILEMAP_INLINE_WAL_BYTES {
        return Err(Error::invalid(
            method,
            "patch exceeds 1MB; split the tilemap edit (WAL blob CAS is not implemented)",
        ));
    }
    Ok(())
}

fn resolve_entity_id(params: &Value, method: &str) -> Result<u64, Error> {
    let raw = if params.get("id").is_some() {
        string_field(params, "id", method)?
    } else if params.get("entity_id").is_some() {
        string_field(params, "entity_id", method)?
    } else {
        return Err(Error::invalid(method, "missing id"));
    };
    parse_entity_id(&raw)
}

fn string_field(params: &Value, key: &str, method: &str) -> Result<String, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    v.as_str()
        .map(str::to_string)
        .ok_or_else(|| Error::invalid(method, format!("{key} must be string")))
}

fn i64_field(params: &Value, key: &str, method: &str) -> Result<i64, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    v.as_i64()
        .ok_or_else(|| Error::invalid(method, format!("{key} must be int")))
}

fn resolve_layer_index(
    layers: &[TilemapLayer],
    layer: &Value,
    method: &str,
) -> Result<usize, Error> {
    if let Some(name) = layer.as_str() {
        return layers
            .iter()
            .position(|l| l.name == name)
            .ok_or_else(|| Error::invalid(method, format!("layer {name:?} not found")));
    }
    if let Some(n) = layer.as_i64() {
        if n < 0 {
            return Err(Error::invalid(method, "layer index must be >= 0"));
        }
        let idx =
            usize::try_from(n).map_err(|_| Error::invalid(method, "layer index out of range"))?;
        if idx >= layers.len() {
            return Err(Error::invalid(
                method,
                format!("layer index {idx} out of range"),
            ));
        }
        return Ok(idx);
    }
    Err(Error::invalid(method, "layer must be a name or index"))
}

fn require_tilemap<'a>(ent: &'a Entity, method: &str) -> Result<&'a Tilemap, Error> {
    ent.extra
        .tilemap
        .as_ref()
        .ok_or_else(|| Error::invalid(method, "entity has no Tilemap"))
}

fn parse_set_cells(params: &Value) -> Result<(u64, Value, Vec<[i64; 4]>), Error> {
    let id = resolve_entity_id(params, METHOD_SET)?;
    let layer = params
        .get("layer")
        .cloned()
        .ok_or_else(|| Error::invalid(METHOD_SET, "missing layer"))?;
    let cells_v = params
        .get("cells")
        .ok_or_else(|| Error::invalid(METHOD_SET, "missing cells"))?;
    let arr = cells_v
        .as_array()
        .ok_or_else(|| Error::invalid(METHOD_SET, "cells must be an array"))?;
    let mut cells = Vec::with_capacity(arr.len());
    let mut expanded = 0i64;
    for run in arr {
        let cell = parse_rle_run(run, METHOD_SET, true)?;
        expanded = expanded
            .checked_add(cell[2])
            .ok_or_else(|| too_many_cells(METHOD_SET))?;
        if expanded > MAX_TILEMAP_EXPANDED_CELLS {
            return Err(too_many_cells(METHOD_SET));
        }
        cells.push(cell);
    }
    Ok((id, layer, cells))
}

struct FillRect {
    id: u64,
    layer: Value,
    x: i64,
    y: i64,
    w: i64,
    h: i64,
    tile: i64,
}

fn parse_fill_rect(params: &Value) -> Result<FillRect, Error> {
    let id = resolve_entity_id(params, METHOD_FILL)?;
    let layer = params
        .get("layer")
        .cloned()
        .ok_or_else(|| Error::invalid(METHOD_FILL, "missing layer"))?;
    let x = i64_field(params, "x", METHOD_FILL)?;
    let y = i64_field(params, "y", METHOD_FILL)?;
    let w = i64_field(params, "w", METHOD_FILL)?;
    let h = i64_field(params, "h", METHOD_FILL)?;
    let tile = i64_field(params, "tile", METHOD_FILL)?;
    if w <= 0 || h <= 0 {
        return Err(Error::invalid(METHOD_FILL, "w and h must be > 0"));
    }
    let area = w
        .checked_mul(h)
        .ok_or_else(|| too_many_cells(METHOD_FILL))?;
    if area > MAX_TILEMAP_EXPANDED_CELLS {
        return Err(too_many_cells(METHOD_FILL));
    }
    if !coord_ok(x) || !coord_ok(y) {
        return Err(outside_bounds(METHOD_FILL));
    }
    let last_x = x
        .checked_add(w)
        .and_then(|s| s.checked_sub(1))
        .ok_or_else(|| Error::invalid(METHOD_FILL, "fill range overflow"))?;
    let last_y = y
        .checked_add(h)
        .and_then(|s| s.checked_sub(1))
        .ok_or_else(|| Error::invalid(METHOD_FILL, "fill range overflow"))?;
    if !coord_ok(last_x) || !coord_ok(last_y) {
        return Err(outside_bounds(METHOD_FILL));
    }
    Ok(FillRect {
        id,
        layer,
        x,
        y,
        w,
        h,
        tile,
    })
}

fn fill_runs(x: i64, y: i64, w: i64, h: i64, tile: i64) -> Vec<[i64; 4]> {
    let mut runs = Vec::with_capacity(usize::try_from(h).unwrap_or(0));
    for row in 0..h {
        runs.push([x, y + row, w, tile]);
    }
    runs
}

fn apply_patches(cells: &[[i64; 4]], patches: &[[i64; 4]]) -> (Vec<[i64; 4]>, Vec<[i64; 4]>) {
    let mut rows: BTreeMap<i64, Row> = BTreeMap::new();
    for &[x, y, len, tile] in cells {
        rows.entry(y).or_default().apply(x, len, tile);
    }

    let mut touched: BTreeMap<i64, Vec<(i64, i64)>> = BTreeMap::new();
    for &[x, y, len, _] in patches {
        union_range(touched.entry(y).or_default(), x, len);
    }

    let mut inverse = Vec::new();
    for (&y, ranges) in &touched {
        let row = rows.get(&y).cloned().unwrap_or_default();
        for &(x, len) in ranges {
            for (px, plen, ptile) in row.previous_coverage(x, len) {
                inverse.push([px, y, plen, ptile]);
            }
        }
    }

    for &[x, y, len, tile] in patches {
        rows.entry(y).or_default().apply(x, len, tile);
    }
    (cells_from_rows(&rows), inverse)
}

fn union_range(ranges: &mut Vec<(i64, i64)>, x: i64, len: i64) {
    ranges.push((x, len));
    ranges.sort_unstable_by_key(|r| r.0);
    let mut merged = Vec::with_capacity(ranges.len());
    let mut cur = ranges[0];
    for &next in &ranges[1..] {
        let cur_end = cur.0 + cur.1;
        let next_end = next.0 + next.1;
        if cur_end >= next.0 {
            cur.1 = cur_end.max(next_end) - cur.0;
        } else {
            merged.push(cur);
            cur = next;
        }
    }
    merged.push(cur);
    *ranges = merged;
}

fn set_cells_command(id: &str, layer: &Value, cells: &[[i64; 4]]) -> Command {
    Command::new(
        METHOD_SET,
        json!({
            "id": id,
            "layer": layer,
            "cells": cells,
        }),
    )
}

fn fill_rect_command(
    id: &str,
    layer: &Value,
    x: i64,
    y: i64,
    w: i64,
    h: i64,
    tile: i64,
) -> Command {
    Command::new(
        METHOD_FILL,
        json!({
            "id": id,
            "layer": layer,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "tile": tile,
        }),
    )
}

impl Document {
    pub(crate) fn normalize_tilemap_set_cells(&self, cmd: &Command) -> Result<Command, Error> {
        let (id, layer, cells) = parse_set_cells(&cmd.params)?;
        let ent = self
            .scene
            .entities
            .get(&id)
            .ok_or_else(|| Error::NotFound(format_entity_id(id)))?;
        let tilemap = require_tilemap(ent, METHOD_SET)?;
        resolve_layer_index(&tilemap.layers, &layer, METHOD_SET)?;
        let normalized = set_cells_command(&format_entity_id(id), &layer, &cells);
        reject_large_inline(METHOD_SET, &normalized.params)?;
        Ok(normalized)
    }

    pub(crate) fn normalize_tilemap_fill_rect(&self, cmd: &Command) -> Result<Command, Error> {
        let fill = parse_fill_rect(&cmd.params)?;
        let ent = self
            .scene
            .entities
            .get(&fill.id)
            .ok_or_else(|| Error::NotFound(format_entity_id(fill.id)))?;
        let tilemap = require_tilemap(ent, METHOD_FILL)?;
        resolve_layer_index(&tilemap.layers, &fill.layer, METHOD_FILL)?;
        let normalized = fill_rect_command(
            &format_entity_id(fill.id),
            &fill.layer,
            fill.x,
            fill.y,
            fill.w,
            fill.h,
            fill.tile,
        );
        reject_large_inline(METHOD_FILL, &normalized.params)?;
        Ok(normalized)
    }

    pub(crate) fn apply_tilemap_set_cells(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let (id, layer, patches) = parse_set_cells(&cmd.params)?;
        self.patch_tilemap_cells(id, &layer, &patches, METHOD_SET)
    }

    pub(crate) fn apply_tilemap_fill_rect(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let fill = parse_fill_rect(&cmd.params)?;
        let patches = fill_runs(fill.x, fill.y, fill.w, fill.h, fill.tile);
        self.patch_tilemap_cells(fill.id, &fill.layer, &patches, METHOD_FILL)
    }

    fn patch_tilemap_cells(
        &mut self,
        id: u64,
        layer: &Value,
        patches: &[[i64; 4]],
        method: &str,
    ) -> Result<Vec<Command>, Error> {
        let ent = self
            .scene
            .entities
            .get_mut(&id)
            .ok_or_else(|| Error::NotFound(format_entity_id(id)))?;
        let tilemap = ent
            .extra
            .tilemap
            .as_mut()
            .ok_or_else(|| Error::invalid(method, "entity has no Tilemap"))?;
        let idx = resolve_layer_index(&tilemap.layers, layer, method)?;
        let (next, inverse) = apply_patches(&tilemap.layers[idx].cells, patches);
        tilemap.layers[idx].cells = next;
        tilemap_expanded_count(tilemap, method)?;
        let inverse_cmd = set_cells_command(&format_entity_id(id), layer, &inverse);
        reject_large_inline(method, &inverse_cmd.params)?;
        Ok(vec![inverse_cmd])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonicalize_merges_adjacent_same_tile() {
        let out = canonicalize_cells(&[[2, 0, 2, 1], [0, 0, 2, 1]]);
        assert_eq!(out, vec![[0, 0, 4, 1]]);
    }

    #[test]
    fn canonicalize_later_run_wins_and_splits() {
        let out = canonicalize_cells(&[[0, 0, 5, 1], [1, 0, 2, 2]]);
        assert_eq!(out, vec![[0, 0, 1, 1], [1, 0, 2, 2], [3, 0, 2, 1]]);
    }

    #[test]
    fn canonicalize_sorts_by_y_then_x() {
        let out = canonicalize_cells(&[[3, 2, 1, 1], [0, 1, 1, 1], [1, 1, 1, 2]]);
        assert_eq!(out, vec![[0, 1, 1, 1], [1, 1, 1, 2], [3, 2, 1, 1]]);
    }

    #[test]
    fn million_len_run_rejected_without_expanding() {
        let err = validate_rle_run(0, 0, 1_000_001, 1, "Tilemap", false).unwrap_err();
        match err {
            Error::Invalid { reason, .. } => {
                assert!(reason.contains("1_000_000") || reason.contains("1000000"));
                assert!(reason.contains("split"));
            }
            other => panic!("expected Invalid, got {other:?}"),
        }
    }
}
