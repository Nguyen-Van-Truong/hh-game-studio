use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::document::Transform2D;
use crate::error::Error;

/// On-disk / WAL command: method + full normalized params (MASTER 5.5).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Command {
    pub method: String,
    pub params: Value,
}

impl Command {
    pub fn new(method: impl Into<String>, params: Value) -> Self {
        Self {
            method: method.into(),
            params,
        }
    }

    pub fn entity_spawn(
        scene_id: impl Into<String>,
        name: Option<String>,
        parent: Option<String>,
        components: BTreeMap<String, Value>,
    ) -> Self {
        let mut params = serde_json::Map::new();
        params.insert("scene_id".into(), json!(scene_id.into()));
        if let Some(name) = name {
            params.insert("name".into(), json!(name));
        }
        match parent {
            Some(p) => params.insert("parent".into(), json!(p)),
            None => params.insert("parent".into(), Value::Null),
        };
        params.insert(
            "components".into(),
            Value::Object(components.into_iter().collect()),
        );
        Self::new("entity.spawn", Value::Object(params))
    }

    pub fn entity_destroy(ids: Vec<String>) -> Self {
        Self::new("entity.destroy", json!({ "ids": ids }))
    }

    pub fn entity_reparent(ids: Vec<String>, new_parent: Option<String>, keep_world: bool) -> Self {
        Self::new(
            "entity.reparent",
            json!({
                "ids": ids,
                "new_parent": new_parent,
                "keep_world": keep_world,
            }),
        )
    }

    pub fn entity_set_order(id: impl Into<String>, sibling_index: u32) -> Self {
        Self::new(
            "entity.set_order",
            json!({ "id": id.into(), "sibling_index": sibling_index }),
        )
    }

    pub fn entity_rename(id: impl Into<String>, name: impl Into<String>) -> Self {
        Self::new(
            "entity.rename",
            json!({ "id": id.into(), "name": name.into() }),
        )
    }

    pub fn component_set(
        id: impl Into<String>,
        type_name: impl Into<String>,
        patch: Value,
    ) -> Self {
        Self::new(
            "component.set",
            json!({
                "id": id.into(),
                "type": type_name.into(),
                "patch": patch,
            }),
        )
    }

    /// Typed Transform2D set. Non-finite values are encoded as strings so the
    /// validator can reject NaN/Inf (JSON numbers cannot hold them).
    pub fn set_transform(id: impl Into<String>, t: Transform2D) -> Self {
        Self::component_set(id, "Transform2D", transform_patch(&t))
    }

    pub fn entity_duplicate(id: impl Into<String>, name_prefix: Option<String>) -> Self {
        let mut params = serde_json::Map::new();
        params.insert("id".into(), json!(id.into()));
        if let Some(p) = name_prefix {
            params.insert("name_prefix".into(), json!(p));
        }
        Self::new("entity.duplicate", Value::Object(params))
    }

    pub fn blueprint_create(from_entity: impl Into<String>, path: impl Into<String>) -> Self {
        Self::new(
            "blueprint.create",
            json!({
                "from_entity": from_entity.into(),
                "path": path.into(),
            }),
        )
    }

    pub fn blueprint_instantiate(
        path: impl Into<String>,
        at: Option<Value>,
        name_prefix: Option<String>,
    ) -> Self {
        let mut params = serde_json::Map::new();
        params.insert("path".into(), json!(path.into()));
        if let Some(at) = at {
            params.insert("at".into(), at);
        }
        if let Some(p) = name_prefix {
            params.insert("name_prefix".into(), json!(p));
        }
        Self::new("blueprint.instantiate", Value::Object(params))
    }

    pub fn script_create(path: impl Into<String>, template: Option<String>) -> Self {
        let mut params = serde_json::Map::new();
        params.insert("path".into(), json!(path.into()));
        if let Some(template) = template {
            params.insert("template".into(), json!(template));
        }
        Self::new("script.create", Value::Object(params))
    }

    pub fn script_set_source(path: impl Into<String>, source: impl Into<String>) -> Self {
        Self::new(
            "script.set_source",
            json!({
                "path": path.into(),
                "source": source.into(),
            }),
        )
    }

    pub fn script_ingest_external(
        path: impl Into<String>,
        previous_source: Option<String>,
    ) -> Self {
        let mut params = serde_json::Map::new();
        params.insert("path".into(), json!(path.into()));
        if let Some(previous_source) = previous_source {
            params.insert("previous_source".into(), json!(previous_source));
        }
        Self::new("script.ingest_external", Value::Object(params))
    }

    pub fn inputmap_set(actions: Value) -> Self {
        Self::new("inputmap.set", json!({ "actions": actions }))
    }

    pub fn tilemap_set_cells(id: impl Into<String>, layer: Value, cells: Value) -> Self {
        Self::new(
            "tilemap.set_cells",
            json!({
                "id": id.into(),
                "layer": layer,
                "cells": cells,
            }),
        )
    }

    pub fn entity_lock(ids: Vec<String>, note: Option<String>) -> Self {
        let mut params = serde_json::Map::new();
        params.insert("ids".into(), json!(ids));
        if let Some(note) = note {
            params.insert("note".into(), json!(note));
        }
        Self::new("entity.lock", Value::Object(params))
    }

    pub fn entity_unlock(ids: Vec<String>, force: bool) -> Self {
        Self::new(
            "entity.unlock",
            json!({
                "ids": ids,
                "force": force,
            }),
        )
    }

    pub fn project_settings_set(patch: Value) -> Self {
        Self::new("project.settings_set", json!({ "patch": patch }))
    }

    pub fn tilemap_fill_rect(
        id: impl Into<String>,
        layer: Value,
        x: i64,
        y: i64,
        w: i64,
        h: i64,
        tile: i64,
    ) -> Self {
        Self::new(
            "tilemap.fill_rect",
            json!({
                "id": id.into(),
                "layer": layer,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "tile": tile,
            }),
        )
    }
}

fn transform_patch(t: &Transform2D) -> Value {
    json!({
        "x": float_token(t.x),
        "y": float_token(t.y),
        "rot": float_token(t.rot),
        "sx": float_token(t.sx),
        "sy": float_token(t.sy),
        "z_index": t.z_index,
    })
}

fn float_token(v: f32) -> Value {
    if v.is_nan() {
        json!("NaN")
    } else if v.is_infinite() {
        if v.is_sign_positive() {
            json!("Infinity")
        } else {
            json!("-Infinity")
        }
    } else {
        json!(f64::from(v))
    }
}

/// Outer mutating request. `command_id` is required (I11).
#[derive(Clone, Debug)]
pub struct DispatchRequest {
    pub command_id: String,
    pub actor_id: String,
    pub expected_revision: Option<String>,
    pub commands: Vec<Command>,
    pub dry_run: bool,
}

impl DispatchRequest {
    pub fn new(
        command_id: impl Into<String>,
        actor_id: impl Into<String>,
        command: Command,
    ) -> Self {
        Self {
            command_id: command_id.into(),
            actor_id: actor_id.into(),
            expected_revision: None,
            commands: vec![command],
            dry_run: false,
        }
    }

    pub fn transaction(
        command_id: impl Into<String>,
        actor_id: impl Into<String>,
        commands: Vec<Command>,
    ) -> Self {
        Self {
            command_id: command_id.into(),
            actor_id: actor_id.into(),
            expected_revision: None,
            commands,
            dry_run: false,
        }
    }

    pub fn as_dry_run(mut self) -> Self {
        self.dry_run = true;
        self
    }

    pub fn with_expected_revision(mut self, revision: impl Into<String>) -> Self {
        self.expected_revision = Some(revision.into());
        self
    }

    pub fn spawn(
        command_id: impl Into<String>,
        actor_id: impl Into<String>,
        scene_id: impl Into<String>,
        name: impl Into<String>,
    ) -> Self {
        Self::new(
            command_id,
            actor_id,
            Command::entity_spawn(scene_id, Some(name.into()), None, BTreeMap::new()),
        )
    }

    pub fn set_transform(
        command_id: impl Into<String>,
        actor_id: impl Into<String>,
        id: impl Into<String>,
        transform: Transform2D,
    ) -> Self {
        Self::new(command_id, actor_id, Command::set_transform(id, transform))
    }

    pub fn reparent(
        command_id: impl Into<String>,
        actor_id: impl Into<String>,
        ids: Vec<String>,
        new_parent: Option<String>,
        keep_world: bool,
    ) -> Self {
        Self::new(
            command_id,
            actor_id,
            Command::entity_reparent(ids, new_parent, keep_world),
        )
    }

    pub fn validate_command_id(&self) -> Result<(), Error> {
        if ulid::Ulid::from_string(&self.command_id).is_err() {
            return Err(Error::InvalidCommandId);
        }
        Ok(())
    }
}
