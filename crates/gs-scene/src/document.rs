use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};

use crate::blueprint::{
    export_tree, insert_stamped, parse_at, resolve_under_root, stamp_tree, stamped_to_json,
    validate_blueprint_rel,
};
use crate::canonical::to_canonical_vec;
use crate::command::Command;
use crate::components::{
    components_to_json, merge_json_objects, merge_transform, parse_components, transform_json,
    validate_name, ExtraComponents, ParsedComponents,
};
use crate::error::Error;
use crate::id::{format_entity_id, format_revision, parse_entity_id};
use crate::persist::write_tmp_rename;

pub use crate::components::{Name, Tags, Transform2D, SCALE_MIN};

pub const DEFAULT_SCENE_ID: &str = "s_main";
pub const MAX_TXN_COMMANDS: usize = 200;

#[derive(Clone, Debug, PartialEq)]
pub struct Entity {
    pub id: u64,
    pub parent: Option<u64>,
    pub order: u32,
    pub name: Option<Name>,
    pub transform: Option<Transform2D>,
    pub tags: Option<Tags>,
    pub extra: ExtraComponents,
    /// Unknown fields on known component types (I5).
    pub component_unknown: BTreeMap<String, BTreeMap<String, Value>>,
    /// Unknown entity-level fields (not id/parent/order/components).
    pub unknown: BTreeMap<String, Value>,
}

impl Entity {
    pub fn new(id: u64, parent: Option<u64>, order: u32) -> Self {
        Self {
            id,
            parent,
            order,
            name: None,
            transform: None,
            tags: None,
            extra: ExtraComponents::default(),
            component_unknown: BTreeMap::new(),
            unknown: BTreeMap::new(),
        }
    }

    pub fn id_str(&self) -> String {
        format_entity_id(self.id)
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Scene {
    pub schema_version: u32,
    pub mode: String,
    pub entities: BTreeMap<u64, Entity>,
    pub unknown: BTreeMap<String, Value>,
}

impl Default for Scene {
    fn default() -> Self {
        Self {
            schema_version: 1,
            mode: "2d".into(),
            entities: BTreeMap::new(),
            unknown: BTreeMap::new(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Document {
    pub schema_version: u32,
    pub revision: u64,
    pub next_entity: u64,
    pub next_asset: u64,
    pub scene_id: String,
    pub scene: Scene,
    pub unknown: BTreeMap<String, Value>,
    /// Set by Session; not serialized. Used for blueprint/script/inputmap I/O (I7).
    pub project_root: Option<PathBuf>,
}

impl Default for Document {
    fn default() -> Self {
        Self {
            schema_version: 1,
            revision: 0,
            next_entity: 1,
            next_asset: 1,
            scene_id: DEFAULT_SCENE_ID.into(),
            scene: Scene::default(),
            unknown: BTreeMap::new(),
            project_root: None,
        }
    }
}

impl Document {
    pub fn revision_label(&self) -> String {
        format_revision(self.revision)
    }

    pub fn entity(&self, id: u64) -> Option<&Entity> {
        self.scene.entities.get(&id)
    }

    pub fn entity_count(&self) -> usize {
        self.scene.entities.len()
    }

    pub fn canonical_scene_bytes(&self) -> Vec<u8> {
        to_canonical_vec(&self.scene.to_canonical_value())
    }

    pub fn canonical_project_bytes(&self) -> Vec<u8> {
        to_canonical_vec(&self.project_canonical_value())
    }

    pub fn project_canonical_value(&self) -> Value {
        let mut map = Map::new();
        map.insert("next_asset".into(), json!(self.next_asset));
        map.insert("next_entity".into(), json!(self.next_entity));
        map.insert("revision".into(), json!(self.revision));
        map.insert("schema_version".into(), json!(self.schema_version));
        for (k, v) in &self.unknown {
            map.insert(k.clone(), v.clone());
        }
        Value::Object(map)
    }

    pub fn to_wire(&self) -> DocumentWire {
        DocumentWire {
            schema_version: self.schema_version,
            revision: self.revision,
            next_entity: self.next_entity,
            next_asset: self.next_asset,
            scene_id: self.scene_id.clone(),
            last_committed_seq: None,
            scene: self.scene.to_file(),
            unknown: self.unknown.clone(),
        }
    }

    pub fn from_wire(wire: DocumentWire) -> Result<Self, Error> {
        Ok(Self {
            schema_version: wire.schema_version,
            revision: wire.revision,
            next_entity: wire.next_entity,
            next_asset: wire.next_asset,
            scene_id: wire.scene_id,
            scene: Scene::from_file(wire.scene)?,
            unknown: wire.unknown,
            project_root: None,
        })
    }

    /// Validate + normalize one command. Does not mutate. Allocates spawn ids
    /// against a clone of counters when `allocate` is true.
    pub fn validate(&self, cmd: &Command, allocate: bool) -> Result<Command, Error> {
        self.validate_on(&mut self.clone(), cmd, allocate)
    }

    fn validate_on(
        &self,
        scratch: &mut Document,
        cmd: &Command,
        allocate: bool,
    ) -> Result<Command, Error> {
        match cmd.method.as_str() {
            "entity.spawn" => scratch.normalize_spawn(cmd, allocate),
            "entity.destroy" => scratch.normalize_destroy(cmd),
            "entity.reparent" => scratch.normalize_reparent(cmd),
            "entity.set_order" => scratch.normalize_set_order(cmd),
            "entity.rename" => scratch.normalize_rename(cmd),
            "entity.duplicate" => scratch.normalize_duplicate(cmd, allocate),
            "component.set" => scratch.normalize_component_set(cmd),
            "blueprint.create" => scratch.normalize_blueprint_create(cmd),
            "blueprint.instantiate" => scratch.normalize_blueprint_instantiate(cmd, allocate),
            "script.create" => scratch.normalize_script_create(cmd),
            "script.set_source" => scratch.normalize_script_set_source(cmd),
            "script.ingest_external" => scratch.normalize_script_ingest_external(cmd),
            "script.get_source" => Err(crate::script::get_source_is_readonly()),
            "inputmap.set" => scratch.normalize_inputmap_set(cmd),
            "inputmap.get" => Err(crate::inputmap::get_is_readonly()),
            "tilemap.set_cells" => scratch.normalize_tilemap_set_cells(cmd),
            "tilemap.fill_rect" => scratch.normalize_tilemap_fill_rect(cmd),
            "entity.lock" => scratch.normalize_entity_lock(cmd),
            "entity.unlock" => scratch.normalize_entity_unlock(cmd),
            "project.settings_set" => scratch.normalize_settings_set(cmd),
            "project.settings_get" => Err(crate::settings::get_is_readonly()),
            "transaction.execute" => Err(Error::invalid(
                "transaction.execute",
                "nesting transaction.execute is not allowed",
            )),
            other => Err(Error::UnknownMethod(other.to_string())),
        }
    }

    /// Plan a txn: validate/normalize every command, apply on a clone, return
    /// normalized commands + inverses (undo order) + resulting document.
    pub fn plan_txn(&self, commands: &[Command]) -> Result<PlannedTxn, Error> {
        if commands.is_empty() {
            return Err(Error::invalid("txn", "empty command list"));
        }
        if commands.len() > MAX_TXN_COMMANDS {
            return Err(Error::invalid(
                "txn",
                format!("at most {MAX_TXN_COMMANDS} commands"),
            ));
        }
        let mut planned = self.clone();
        let mut normalized = Vec::with_capacity(commands.len());
        let mut inverses = Vec::new();
        for cmd in commands {
            let cmd = self.validate_on(&mut planned, cmd, true)?;
            inverses.extend(planned.apply_normalized(&cmd)?);
            normalized.push(cmd);
        }
        inverses.reverse();
        planned.revision = planned.revision.saturating_add(1);
        Ok(PlannedTxn {
            commands: normalized,
            inverses,
            document: planned,
        })
    }

    /// Apply already-normalized commands (WAL replay). Bumps revision once.
    pub fn apply_txn(&mut self, commands: &[Command]) -> Result<Vec<Command>, Error> {
        let planned = self.plan_txn(commands)?;
        let inverses = planned.inverses;
        *self = planned.document;
        Ok(inverses)
    }

    pub fn apply_normalized(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        match cmd.method.as_str() {
            "entity.spawn" => self.apply_spawn(cmd),
            "entity.destroy" => self.apply_destroy(cmd),
            "entity.reparent" => self.apply_reparent(cmd),
            "entity.set_order" => self.apply_set_order(cmd),
            "entity.rename" => self.apply_rename(cmd),
            "entity.duplicate" => self.apply_stamped_entities(cmd, "entity.duplicate"),
            "component.set" => self.apply_component_set(cmd),
            "blueprint.create" => self.apply_blueprint_create(cmd),
            "blueprint.instantiate" => self.apply_stamped_entities(cmd, "blueprint.instantiate"),
            "script.create" | "script.set_source" | "script.ingest_external" => {
                self.apply_script_file(cmd)
            }
            "script.get_source" => Err(crate::script::get_source_is_readonly()),
            "inputmap.set" => self.apply_inputmap_set(cmd),
            "inputmap.get" => Err(crate::inputmap::get_is_readonly()),
            "tilemap.set_cells" => self.apply_tilemap_set_cells(cmd),
            "tilemap.fill_rect" => self.apply_tilemap_fill_rect(cmd),
            "entity.lock" => self.apply_entity_lock(cmd),
            "entity.unlock" => self.apply_entity_unlock(cmd),
            "project.settings_set" => self.apply_settings_set(cmd),
            "project.settings_get" => Err(crate::settings::get_is_readonly()),
            other => Err(Error::UnknownMethod(other.to_string())),
        }
    }

    pub fn touched_entity_ids(commands: &[Command]) -> BTreeSet<u64> {
        let mut out = BTreeSet::new();
        for cmd in commands {
            collect_touched(&cmd.params, &mut out);
            if cmd.method == "entity.spawn" {
                if let Some(id) = cmd.params.get("id").and_then(Value::as_str) {
                    if let Ok(n) = parse_entity_id(id) {
                        out.insert(n);
                    }
                }
            }
        }
        out
    }

    fn normalize_spawn(&mut self, cmd: &Command, allocate: bool) -> Result<Command, Error> {
        let scene_id = string_field(&cmd.params, "scene_id", "entity.spawn")?;
        if scene_id != self.scene_id {
            return Err(Error::NotFound(scene_id));
        }
        let name = optional_string(&cmd.params, "name", "entity.spawn")?;
        if let Some(ref n) = name {
            validate_name(n)?;
        }
        let parent = optional_id(&cmd.params, "parent", "entity.spawn")?;
        if let Some(p) = parent {
            if !self.scene.entities.contains_key(&p) {
                return Err(Error::NotFound(format_entity_id(p)));
            }
        }
        let components = cmd
            .params
            .get("components")
            .cloned()
            .unwrap_or_else(|| json!({}));
        if !components.is_object() {
            return Err(Error::invalid(
                "entity.spawn",
                "components must be an object",
            ));
        }
        let parsed = parse_components(&components)?;
        if parsed.name.is_none() {
            if let Some(ref n) = name {
                validate_name(n)?;
            }
        }
        if parsed.transform.is_none() {
            Transform2D::identity().validate()?;
        }

        let id = if let Some(existing) = optional_id(&cmd.params, "id", "entity.spawn")? {
            if allocate && self.scene.entities.contains_key(&existing) {
                return Err(Error::invalid(
                    "entity.spawn",
                    format!("id {} already exists", format_entity_id(existing)),
                ));
            }
            if existing >= self.next_entity {
                self.next_entity = existing.saturating_add(1);
            }
            existing
        } else if allocate {
            let id = self.next_entity;
            self.next_entity = self.next_entity.saturating_add(1);
            id
        } else {
            return Err(Error::invalid("entity.spawn", "id required on replay"));
        };

        let mut params = serde_json::Map::new();
        params.insert("scene_id".into(), json!(scene_id));
        params.insert("id".into(), json!(format_entity_id(id)));
        if let Some(n) = name {
            params.insert("name".into(), json!(n));
        }
        params.insert(
            "parent".into(),
            parent
                .map(format_entity_id)
                .map(Value::String)
                .unwrap_or(Value::Null),
        );
        params.insert("components".into(), components_to_json(&parsed));
        Ok(Command::new("entity.spawn", Value::Object(params)))
    }

    fn normalize_destroy(&self, cmd: &Command) -> Result<Command, Error> {
        let ids = id_list(&cmd.params, "ids", "entity.destroy")?;
        if ids.is_empty() {
            return Err(Error::invalid("entity.destroy", "ids must be non-empty"));
        }
        for id in &ids {
            if !self.scene.entities.contains_key(id) {
                return Err(Error::NotFound(format_entity_id(*id)));
            }
        }
        Ok(Command::entity_destroy(
            ids.into_iter().map(format_entity_id).collect(),
        ))
    }

    fn normalize_reparent(&self, cmd: &Command) -> Result<Command, Error> {
        let ids = id_list(&cmd.params, "ids", "entity.reparent")?;
        if ids.is_empty() {
            return Err(Error::invalid("entity.reparent", "ids must be non-empty"));
        }
        let new_parent = optional_id(&cmd.params, "new_parent", "entity.reparent")?;
        let keep_world = cmd
            .params
            .get("keep_world")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        if let Some(p) = new_parent {
            if !self.scene.entities.contains_key(&p) {
                return Err(Error::NotFound(format_entity_id(p)));
            }
        }
        for id in &ids {
            if !self.scene.entities.contains_key(id) {
                return Err(Error::NotFound(format_entity_id(*id)));
            }
            if let Some(p) = new_parent {
                if would_cycle(&self.scene, *id, Some(p)) {
                    return Err(Error::Cycle {
                        id: format_entity_id(*id),
                        new_parent: format_entity_id(p),
                    });
                }
            }
        }
        Ok(Command::entity_reparent(
            ids.into_iter().map(format_entity_id).collect(),
            new_parent.map(format_entity_id),
            keep_world,
        ))
    }

    fn normalize_set_order(&self, cmd: &Command) -> Result<Command, Error> {
        let id = required_id(&cmd.params, "id", "entity.set_order")?;
        if !self.scene.entities.contains_key(&id) {
            return Err(Error::NotFound(format_entity_id(id)));
        }
        let sibling_index = u32_field(&cmd.params, "sibling_index", "entity.set_order")?;
        Ok(Command::entity_set_order(
            format_entity_id(id),
            sibling_index,
        ))
    }

    fn normalize_rename(&self, cmd: &Command) -> Result<Command, Error> {
        let id = required_id(&cmd.params, "id", "entity.rename")?;
        if !self.scene.entities.contains_key(&id) {
            return Err(Error::NotFound(format_entity_id(id)));
        }
        let name = string_field(&cmd.params, "name", "entity.rename")?;
        validate_name(&name)?;
        Ok(Command::entity_rename(format_entity_id(id), name))
    }

    fn normalize_component_set(&self, cmd: &Command) -> Result<Command, Error> {
        let id = required_id(&cmd.params, "id", "component.set")?;
        if !self.scene.entities.contains_key(&id) {
            return Err(Error::NotFound(format_entity_id(id)));
        }
        let type_name = string_field(&cmd.params, "type", "component.set")?;
        let patch = cmd
            .params
            .get("patch")
            .cloned()
            .ok_or_else(|| Error::invalid("component.set", "missing patch"))?;
        if !patch.is_object() {
            return Err(Error::invalid("component.set", "patch must be an object"));
        }
        let entity = self.scene.entities.get(&id).expect("checked");
        let current = entity_components_map(entity)
            .get(&type_name)
            .cloned()
            .unwrap_or_else(|| json!({}));
        let merged = merge_json_objects(current, &patch);
        parse_components(&json!({ type_name.clone(): merged }))?;
        Ok(Command::component_set(
            format_entity_id(id),
            type_name,
            patch,
        ))
    }

    fn apply_spawn(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let id = required_id(&cmd.params, "id", "entity.spawn")?;
        let parent = optional_id(&cmd.params, "parent", "entity.spawn")?;
        let name = optional_string(&cmd.params, "name", "entity.spawn")?;
        let components = cmd
            .params
            .get("components")
            .cloned()
            .unwrap_or_else(|| json!({}));
        let mut parsed = parse_components(&components)?;
        if parsed.name.is_none() {
            if let Some(n) = name {
                parsed.name = Some(Name { value: n });
            }
        }
        if parsed.transform.is_none() {
            parsed.transform = Some(Transform2D::identity());
        }
        if id >= self.next_entity {
            self.next_entity = id.saturating_add(1);
        }
        let order = cmd
            .params
            .get("order")
            .and_then(Value::as_u64)
            .and_then(|n| u32::try_from(n).ok())
            .unwrap_or_else(|| next_sibling_order(&self.scene, parent));
        let mut ent = Entity::new(id, parent, order);
        ent.name = parsed.name;
        ent.transform = parsed.transform;
        ent.tags = parsed.tags;
        ent.extra = parsed.extra;
        ent.component_unknown = parsed.field_unknown;
        self.scene.entities.insert(id, ent);
        Ok(vec![Command::entity_destroy(vec![format_entity_id(id)])])
    }

    fn apply_destroy(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let ids = id_list(&cmd.params, "ids", "entity.destroy")?;
        let mut remove = BTreeSet::new();
        for id in ids {
            collect_cascade(&self.scene, id, &mut remove);
        }
        let mut snapshots = Vec::new();
        let mut depths: Vec<(u32, u64)> = remove
            .iter()
            .map(|&id| (depth(&self.scene, id), id))
            .collect();
        depths.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
        for (_, id) in depths {
            if let Some(ent) = self.scene.entities.remove(&id) {
                snapshots.push(spawn_from_entity(&self.scene_id, &ent));
            }
        }
        Ok(snapshots)
    }

    fn apply_reparent(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let ids = id_list(&cmd.params, "ids", "entity.reparent")?;
        let new_parent = optional_id(&cmd.params, "new_parent", "entity.reparent")?;
        let keep_world = cmd
            .params
            .get("keep_world")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let mut inverses = Vec::new();
        for id in ids {
            let old_parent = self
                .scene
                .entities
                .get(&id)
                .ok_or_else(|| Error::NotFound(format_entity_id(id)))?
                .parent;
            let old_transform = self
                .scene
                .entities
                .get(&id)
                .and_then(|e| e.transform.clone())
                .unwrap_or_else(Transform2D::identity);
            if keep_world {
                let world = world_transform(&self.scene, id);
                let local = match new_parent {
                    Some(p) => relative_to(&world, &world_transform(&self.scene, p)),
                    None => world,
                };
                if let Some(ent) = self.scene.entities.get_mut(&id) {
                    ent.transform = Some(local);
                }
                inverses.push(Command::set_transform(format_entity_id(id), old_transform));
            }
            if let Some(ent) = self.scene.entities.get_mut(&id) {
                ent.parent = new_parent;
            }
            inverses.push(Command::entity_reparent(
                vec![format_entity_id(id)],
                old_parent.map(format_entity_id),
                false,
            ));
        }
        Ok(inverses)
    }

    fn apply_set_order(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let id = required_id(&cmd.params, "id", "entity.set_order")?;
        let sibling_index = u32_field(&cmd.params, "sibling_index", "entity.set_order")?;
        let ent = self
            .scene
            .entities
            .get_mut(&id)
            .ok_or_else(|| Error::NotFound(format_entity_id(id)))?;
        let old = ent.order;
        ent.order = sibling_index;
        Ok(vec![Command::entity_set_order(format_entity_id(id), old)])
    }

    fn apply_rename(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let id = required_id(&cmd.params, "id", "entity.rename")?;
        let name = string_field(&cmd.params, "name", "entity.rename")?;
        let ent = self
            .scene
            .entities
            .get_mut(&id)
            .ok_or_else(|| Error::NotFound(format_entity_id(id)))?;
        let old = ent
            .name
            .as_ref()
            .map(|n| n.value.clone())
            .unwrap_or_default();
        ent.name = Some(Name { value: name });
        Ok(vec![Command::entity_rename(format_entity_id(id), old)])
    }

    fn apply_component_set(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let id = required_id(&cmd.params, "id", "component.set")?;
        let type_name = string_field(&cmd.params, "type", "component.set")?;
        let patch = cmd
            .params
            .get("patch")
            .cloned()
            .ok_or_else(|| Error::invalid("component.set", "missing patch"))?;
        let ent = self
            .scene
            .entities
            .get_mut(&id)
            .ok_or_else(|| Error::NotFound(format_entity_id(id)))?;
        let old_patch = entity_components_map(ent)
            .get(&type_name)
            .cloned()
            .unwrap_or_else(|| json!({}));
        let merged = merge_json_objects(old_patch.clone(), &patch);
        let parsed = parse_components(&json!({ type_name.clone(): merged }))?;
        apply_parsed_component(ent, &type_name, parsed);
        Ok(vec![Command::component_set(
            format_entity_id(id),
            type_name,
            old_patch,
        )])
    }

    fn normalize_duplicate(&mut self, cmd: &Command, allocate: bool) -> Result<Command, Error> {
        let id = required_id(&cmd.params, "id", "entity.duplicate")?;
        if !self.scene.entities.contains_key(&id) {
            return Err(Error::NotFound(format_entity_id(id)));
        }
        if !allocate {
            return Ok(cmd.clone());
        }
        let gbp = export_tree(&self.scene, id)?;
        let prefix = optional_string(&cmd.params, "name_prefix", "entity.duplicate")?;
        let (stamped, next) = stamp_tree(&gbp, self.next_entity, None, prefix.as_deref())?;
        self.next_entity = next;
        let mut params = serde_json::Map::new();
        params.insert("id".into(), json!(format_entity_id(id)));
        params.insert("entities".into(), stamped_to_json(&stamped));
        if let Some(p) = prefix {
            params.insert("name_prefix".into(), json!(p));
        }
        Ok(Command::new("entity.duplicate", Value::Object(params)))
    }

    fn normalize_blueprint_create(&self, cmd: &Command) -> Result<Command, Error> {
        let from = required_id(&cmd.params, "from_entity", "blueprint.create")?;
        if !self.scene.entities.contains_key(&from) {
            return Err(Error::NotFound(format_entity_id(from)));
        }
        let path = string_field(&cmd.params, "path", "blueprint.create")?;
        validate_blueprint_rel(&path)?;
        let payload = if let Some(p) = cmd.params.get("payload") {
            p.clone()
        } else {
            export_tree(&self.scene, from)?
        };
        let previous = cmd.params.get("previous").cloned().unwrap_or(Value::Null);
        Ok(Command::new(
            "blueprint.create",
            json!({
                "from_entity": format_entity_id(from),
                "path": path,
                "payload": payload,
                "previous": previous,
            }),
        ))
    }

    fn normalize_blueprint_instantiate(
        &mut self,
        cmd: &Command,
        allocate: bool,
    ) -> Result<Command, Error> {
        if cmd.params.get("entities").is_some() {
            if allocate {
                if let Some(arr) = cmd.params.get("entities").and_then(Value::as_array) {
                    for e in arr {
                        if let Some(id) = e.get("id").and_then(Value::as_str) {
                            if let Ok(n) = parse_entity_id(id) {
                                if n >= self.next_entity {
                                    self.next_entity = n.saturating_add(1);
                                }
                            }
                        }
                    }
                }
            }
            return Ok(cmd.clone());
        }
        let path = string_field(&cmd.params, "path", "blueprint.instantiate")?;
        validate_blueprint_rel(&path)?;
        let at = parse_at(cmd.params.get("at"))?;
        let prefix = optional_string(&cmd.params, "name_prefix", "blueprint.instantiate")?;
        let root = self.project_root.as_ref().ok_or_else(|| {
            Error::invalid("blueprint.instantiate", "session has no project root")
        })?;
        let abs = resolve_under_root(root, &path)?;
        let text = std::fs::read_to_string(&abs).map_err(|_| Error::NotFound(path.clone()))?;
        crate::persist::reject_conflict_markers(&text, &abs)?;
        let gbp: Value = serde_json::from_str(&text)?;
        if !allocate {
            return Ok(cmd.clone());
        }
        let (stamped, next) = stamp_tree(&gbp, self.next_entity, at, prefix.as_deref())?;
        self.next_entity = next;
        let mut params = serde_json::Map::new();
        params.insert("path".into(), json!(path));
        params.insert("entities".into(), stamped_to_json(&stamped));
        if let Some(p) = prefix {
            params.insert("name_prefix".into(), json!(p));
        }
        if let Some(at_v) = cmd.params.get("at") {
            params.insert("at".into(), at_v.clone());
        }
        Ok(Command::new("blueprint.instantiate", Value::Object(params)))
    }

    fn apply_blueprint_create(&self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let path = string_field(&cmd.params, "path", "blueprint.create")?;
        validate_blueprint_rel(&path)?;
        let previous = self.read_blueprint_payload(&path)?;
        let from = cmd
            .params
            .get("from_entity")
            .cloned()
            .unwrap_or(Value::Null);
        Ok(vec![Command::new(
            "blueprint.create",
            json!({
                "from_entity": from,
                "path": path,
                "payload": cmd.params.get("previous").cloned().unwrap_or(Value::Null),
                "previous": previous,
            }),
        )])
    }

    fn read_blueprint_payload(&self, rel: &str) -> Result<Value, Error> {
        let Some(root) = self.project_root.as_ref() else {
            return Ok(Value::Null);
        };
        let abs = resolve_under_root(root, rel)?;
        if !abs.exists() {
            return Ok(Value::Null);
        }
        let text = std::fs::read_to_string(&abs)?;
        Ok(serde_json::from_str(&text).unwrap_or(Value::Null))
    }

    /// Write/delete blueprint file after WAL fsync (I2). Called from Dispatcher.
    pub fn persist_blueprint_create(&self, cmd: &Command) -> Result<(), Error> {
        let path = string_field(&cmd.params, "path", "blueprint.create")?;
        validate_blueprint_rel(&path)?;
        let root = self
            .project_root
            .as_ref()
            .ok_or_else(|| Error::invalid("blueprint.create", "session has no project root"))?;
        let abs = resolve_under_root(root, &path)?;
        if let Some(parent) = abs.parent() {
            std::fs::create_dir_all(parent)?;
        }
        match cmd.params.get("payload") {
            None | Some(Value::Null) => {
                if abs.exists() {
                    std::fs::remove_file(&abs)?;
                }
            }
            Some(payload) => {
                let bytes = crate::canonical::to_canonical_vec(payload);
                write_tmp_rename(&abs, &bytes)?;
            }
        }
        Ok(())
    }

    fn apply_stamped_entities(
        &mut self,
        cmd: &Command,
        method: &str,
    ) -> Result<Vec<Command>, Error> {
        let arr = cmd
            .params
            .get("entities")
            .and_then(Value::as_array)
            .ok_or_else(|| Error::invalid(method, "missing entities"))?;
        let mut stamped = Vec::new();
        let mut ids = Vec::new();
        for e in arr {
            let id_s = e
                .get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| Error::invalid(method, "entity missing id"))?;
            let id = parse_entity_id(id_s)?;
            ids.push(format_entity_id(id));
            if id >= self.next_entity {
                self.next_entity = id.saturating_add(1);
            }
            let parent = match e.get("parent") {
                None | Some(Value::Null) => None,
                Some(Value::String(p)) => Some(parse_entity_id(p)?),
                _ => return Err(Error::invalid(method, "parent must be string or null")),
            };
            let order = e.get("order").and_then(Value::as_u64).unwrap_or(0) as u32;
            let mut unknown = BTreeMap::new();
            if let Some(obj) = e.as_object() {
                for (k, v) in obj {
                    if matches!(k.as_str(), "id" | "parent" | "order" | "components") {
                        continue;
                    }
                    unknown.insert(k.clone(), v.clone());
                }
            }
            stamped.push(crate::blueprint::StampedEntity {
                id,
                parent,
                order,
                components: e.get("components").cloned().unwrap_or_else(|| json!({})),
                unknown,
            });
        }
        insert_stamped(&mut self.scene, &stamped)?;
        Ok(vec![Command::entity_destroy(ids)])
    }
}

fn apply_parsed_component(ent: &mut Entity, type_name: &str, parsed: ParsedComponents) {
    match type_name {
        "Name" => ent.name = parsed.name,
        "Tags" => ent.tags = parsed.tags,
        "Transform2D" => ent.transform = parsed.transform,
        "Sprite" => ent.extra.sprite = parsed.extra.sprite,
        "AnimFlipbook" => ent.extra.anim_flipbook = parsed.extra.anim_flipbook,
        "Camera2D" => ent.extra.camera = parsed.extra.camera,
        "RigidBody2D" => ent.extra.rigid_body = parsed.extra.rigid_body,
        "Collider2D" => ent.extra.collider = parsed.extra.collider,
        "Tilemap" => ent.extra.tilemap = parsed.extra.tilemap,
        "Text2D" => ent.extra.text = parsed.extra.text,
        "AudioSource" => ent.extra.audio = parsed.extra.audio,
        "Script" => ent.extra.script = parsed.extra.script,
        "Visibility" => ent.extra.visibility = parsed.extra.visibility,
        other => {
            if let Some(v) = parsed.extra.unknown.get(other) {
                ent.extra.unknown.insert(other.to_string(), v.clone());
            }
        }
    }
    if let Some(unk) = parsed.field_unknown.get(type_name) {
        ent.component_unknown
            .insert(type_name.to_string(), unk.clone());
    } else {
        ent.component_unknown.remove(type_name);
    }
}

#[derive(Debug)]
pub struct PlannedTxn {
    pub commands: Vec<Command>,
    pub inverses: Vec<Command>,
    pub document: Document,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct DocumentWire {
    pub schema_version: u32,
    pub revision: u64,
    pub next_entity: u64,
    pub next_asset: u64,
    pub scene_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_committed_seq: Option<u64>,
    pub scene: SceneFile,
    #[serde(flatten, default)]
    pub unknown: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SceneFile {
    pub schema_version: u32,
    pub mode: String,
    pub entities: Vec<EntityFile>,
    #[serde(flatten, default)]
    pub unknown: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct EntityFile {
    pub id: String,
    pub parent: Option<String>,
    pub order: u32,
    pub components: BTreeMap<String, Value>,
    #[serde(flatten, default)]
    pub unknown: BTreeMap<String, Value>,
}

impl Scene {
    pub fn to_file(&self) -> SceneFile {
        let mut entities: Vec<EntityFile> = self
            .entities
            .values()
            .map(|e| EntityFile {
                id: e.id_str(),
                parent: e.parent.map(format_entity_id),
                order: e.order,
                components: entity_components_map(e),
                unknown: e.unknown.clone(),
            })
            .collect();
        entities.sort_by(|a, b| {
            let na = parse_entity_id(&a.id).unwrap_or(0);
            let nb = parse_entity_id(&b.id).unwrap_or(0);
            na.cmp(&nb)
        });
        SceneFile {
            schema_version: self.schema_version,
            mode: self.mode.clone(),
            entities,
            unknown: self.unknown.clone(),
        }
    }

    pub fn from_file(file: SceneFile) -> Result<Self, Error> {
        let mut entities = BTreeMap::new();
        for e in file.entities {
            let id = parse_entity_id(&e.id)?;
            let parent = match e.parent {
                Some(p) => Some(parse_entity_id(&p)?),
                None => None,
            };
            let parsed = parse_components(&Value::Object(e.components.into_iter().collect()))?;
            let mut ent = Entity::new(id, parent, e.order);
            ent.name = parsed.name;
            ent.transform = parsed.transform;
            ent.tags = parsed.tags;
            ent.extra = parsed.extra;
            ent.component_unknown = parsed.field_unknown;
            ent.unknown = e.unknown;
            entities.insert(id, ent);
        }
        Ok(Self {
            schema_version: file.schema_version,
            mode: file.mode,
            entities,
            unknown: file.unknown,
        })
    }

    pub fn to_canonical_value(&self) -> Value {
        let file = self.to_file();
        let mut entities = Vec::new();
        for e in file.entities {
            let mut obj = Map::new();
            obj.insert(
                "components".into(),
                components_map_to_sorted_value(&e.components),
            );
            obj.insert("id".into(), json!(e.id));
            obj.insert("order".into(), json!(e.order));
            obj.insert(
                "parent".into(),
                e.parent.map(Value::String).unwrap_or(Value::Null),
            );
            for (k, v) in e.unknown {
                obj.insert(k, v);
            }
            entities.push(Value::Object(obj));
        }
        let mut root = Map::new();
        root.insert("entities".into(), Value::Array(entities));
        root.insert("mode".into(), json!(file.mode));
        root.insert("schema_version".into(), json!(file.schema_version));
        for (k, v) in file.unknown {
            root.insert(k, v);
        }
        Value::Object(root)
    }
}

pub(crate) fn entity_components_map(e: &Entity) -> BTreeMap<String, Value> {
    let parsed = ParsedComponents {
        name: e.name.clone(),
        transform: e.transform.clone(),
        tags: e.tags.clone(),
        extra: e.extra.clone(),
        field_unknown: e.component_unknown.clone(),
    };
    match components_to_json(&parsed) {
        Value::Object(m) => m.into_iter().collect(),
        _ => BTreeMap::new(),
    }
}

fn components_map_to_sorted_value(map: &BTreeMap<String, Value>) -> Value {
    let mut obj = Map::new();
    for (k, v) in map {
        obj.insert(k.clone(), canonicalize_component_value(k, v));
    }
    Value::Object(obj)
}

fn canonicalize_component_value(type_name: &str, value: &Value) -> Value {
    match type_name {
        "Name" => {
            let parsed = parse_components(&json!({ "Name": value })).ok();
            parsed
                .map(|p| {
                    components_to_json(&p)
                        .get("Name")
                        .cloned()
                        .unwrap_or(value.clone())
                })
                .unwrap_or_else(|| value.clone())
        }
        "Tags" => {
            let parsed = parse_components(&json!({ "Tags": value })).ok();
            parsed
                .map(|p| {
                    components_to_json(&p)
                        .get("Tags")
                        .cloned()
                        .unwrap_or(value.clone())
                })
                .unwrap_or_else(|| value.clone())
        }
        "Transform2D" => {
            let t = merge_transform(None, value).unwrap_or_else(|_| Transform2D::identity());
            let mut v = transform_json(Some(&t));
            if let (Value::Object(known), Value::Object(src)) = (&mut v, value) {
                for (k, extra) in src {
                    if !known.contains_key(k) {
                        known.insert(k.clone(), extra.clone());
                    }
                }
            }
            v
        }
        _ => value.clone(),
    }
}

fn would_cycle(scene: &Scene, id: u64, new_parent: Option<u64>) -> bool {
    let Some(mut cur) = new_parent else {
        return false;
    };
    if cur == id {
        return true;
    }
    let mut guard = 0u32;
    while let Some(p) = scene.entities.get(&cur).and_then(|e| e.parent) {
        if p == id {
            return true;
        }
        cur = p;
        guard += 1;
        if guard > 10_000 {
            return true;
        }
    }
    false
}

pub(crate) fn collect_cascade(scene: &Scene, id: u64, out: &mut BTreeSet<u64>) {
    if !out.insert(id) {
        return;
    }
    let children: Vec<u64> = scene
        .entities
        .values()
        .filter(|e| e.parent == Some(id))
        .map(|e| e.id)
        .collect();
    for c in children {
        collect_cascade(scene, c, out);
    }
}

fn depth(scene: &Scene, id: u64) -> u32 {
    let mut d = 0;
    let mut cur = scene.entities.get(&id).and_then(|e| e.parent);
    while let Some(p) = cur {
        d += 1;
        cur = scene.entities.get(&p).and_then(|e| e.parent);
        if d > 10_000 {
            break;
        }
    }
    d
}

fn next_sibling_order(scene: &Scene, parent: Option<u64>) -> u32 {
    scene
        .entities
        .values()
        .filter(|e| e.parent == parent)
        .map(|e| e.order)
        .max()
        .map(|m| m.saturating_add(1))
        .unwrap_or(0)
}

fn spawn_from_entity(scene_id: &str, ent: &Entity) -> Command {
    let components = entity_components_map(ent);
    let mut cmd = Command::entity_spawn(
        scene_id,
        ent.name.as_ref().map(|n| n.value.clone()),
        ent.parent.map(format_entity_id),
        components,
    );
    if let Value::Object(ref mut map) = cmd.params {
        map.insert("id".into(), json!(ent.id_str()));
        map.insert("order".into(), json!(ent.order));
    }
    cmd
}

fn world_transform(scene: &Scene, id: u64) -> Transform2D {
    let mut chain = Vec::new();
    let mut cur = Some(id);
    let mut guard = 0;
    while let Some(cid) = cur {
        if let Some(e) = scene.entities.get(&cid) {
            chain.push(e.transform.clone().unwrap_or_else(Transform2D::identity));
            cur = e.parent;
        } else {
            break;
        }
        guard += 1;
        if guard > 10_000 {
            break;
        }
    }
    chain.reverse();
    let mut world = Transform2D::identity();
    world.sx = 1.0;
    world.sy = 1.0;
    for local in chain {
        world = compose(&world, &local);
    }
    world
}

fn compose(parent: &Transform2D, local: &Transform2D) -> Transform2D {
    let (sin, cos) = parent.rot.sin_cos();
    let x = parent.x + (local.x * parent.sx * cos - local.y * parent.sy * sin);
    let y = parent.y + (local.x * parent.sx * sin + local.y * parent.sy * cos);
    Transform2D {
        x,
        y,
        rot: parent.rot + local.rot,
        sx: parent.sx * local.sx,
        sy: parent.sy * local.sy,
        z_index: local.z_index,
    }
}

fn relative_to(world: &Transform2D, parent_world: &Transform2D) -> Transform2D {
    let (sin, cos) = parent_world.rot.sin_cos();
    let dx = world.x - parent_world.x;
    let dy = world.y - parent_world.y;
    let sx = if parent_world.sx.abs() < SCALE_MIN {
        SCALE_MIN
    } else {
        parent_world.sx
    };
    let sy = if parent_world.sy.abs() < SCALE_MIN {
        SCALE_MIN
    } else {
        parent_world.sy
    };
    Transform2D {
        x: (dx * cos + dy * sin) / sx,
        y: (-dx * sin + dy * cos) / sy,
        rot: world.rot - parent_world.rot,
        sx: world.sx / sx,
        sy: world.sy / sy,
        z_index: world.z_index,
    }
}

fn collect_touched(value: &Value, out: &mut BTreeSet<u64>) {
    match value {
        Value::String(s) => {
            if let Ok(n) = parse_entity_id(s) {
                out.insert(n);
            }
        }
        Value::Array(items) => {
            for i in items {
                collect_touched(i, out);
            }
        }
        Value::Object(map) => {
            if let Some(id) = map.get("$entity").and_then(Value::as_str) {
                if let Ok(n) = parse_entity_id(id) {
                    out.insert(n);
                }
            }
            for (k, v) in map {
                if k == "id"
                    || k == "ids"
                    || k == "entity_id"
                    || k == "parent"
                    || k == "new_parent"
                    || k == "from_entity"
                    || k == "$entity"
                    || k == "entities"
                {
                    collect_touched(v, out);
                }
            }
        }
        _ => {}
    }
}

pub(crate) fn string_field(params: &Value, key: &str, method: &str) -> Result<String, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    v.as_str()
        .map(str::to_string)
        .ok_or_else(|| Error::invalid(method, format!("{key} must be string")))
}

pub(crate) fn optional_string(
    params: &Value,
    key: &str,
    method: &str,
) -> Result<Option<String>, Error> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v
            .as_str()
            .map(|s| Some(s.to_string()))
            .ok_or_else(|| Error::invalid(method, format!("{key} must be string"))),
    }
}

fn required_id(params: &Value, key: &str, method: &str) -> Result<u64, Error> {
    let s = string_field(params, key, method)?;
    parse_entity_id(&s)
}

fn optional_id(params: &Value, key: &str, method: &str) -> Result<Option<u64>, Error> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => {
            let s = v
                .as_str()
                .ok_or_else(|| Error::invalid(method, format!("{key} must be string or null")))?;
            Ok(Some(parse_entity_id(s)?))
        }
    }
}

pub(crate) fn id_list(params: &Value, key: &str, method: &str) -> Result<Vec<u64>, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    let arr = v
        .as_array()
        .ok_or_else(|| Error::invalid(method, format!("{key} must be an array")))?;
    let mut ids = Vec::with_capacity(arr.len());
    for item in arr {
        let s = item
            .as_str()
            .ok_or_else(|| Error::invalid(method, format!("{key} entries must be strings")))?;
        ids.push(parse_entity_id(s)?);
    }
    Ok(ids)
}

fn u32_field(params: &Value, key: &str, method: &str) -> Result<u32, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    if let Some(n) = v.as_u64() {
        return u32::try_from(n).map_err(|_| Error::invalid(method, format!("{key} out of range")));
    }
    Err(Error::invalid(method, format!("{key} must be u32")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cycle_detects_parent_of_child() {
        let mut doc = Document::default();
        let a = Command::entity_spawn("s_main", Some("a".into()), None, BTreeMap::new());
        doc.apply_txn(&[a]).unwrap();
        let b = Command::entity_spawn(
            "s_main",
            Some("b".into()),
            Some("e_000001".into()),
            BTreeMap::new(),
        );
        doc.apply_txn(&[b]).unwrap();
        let err = doc
            .plan_txn(&[Command::entity_reparent(
                vec!["e_000001".into()],
                Some("e_000002".into()),
                false,
            )])
            .unwrap_err();
        assert!(matches!(err, Error::Cycle { .. }));
    }
}
