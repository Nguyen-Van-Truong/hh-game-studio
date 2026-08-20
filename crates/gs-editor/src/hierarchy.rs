//! Hierarchy tree from the open Session document (MASTER 9.3).

use gs_scene::{format_entity_id, Document, Entity};
use serde::{Deserialize, Serialize};

/// One hierarchy node: `{id, name, parent, order, children[]}`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HierarchyNode {
    pub id: String,
    pub name: String,
    pub parent: Option<String>,
    pub order: u32,
    pub children: Vec<HierarchyNode>,
}

/// Forest of root entities, siblings sorted by `order` then id.
pub fn build_hierarchy(doc: &Document) -> Vec<HierarchyNode> {
    let mut ids: Vec<u64> = doc.scene.entities.keys().copied().collect();
    ids.sort_unstable();
    let mut nodes: Vec<HierarchyNode> = ids
        .iter()
        .filter_map(|id| doc.scene.entities.get(id).map(to_node))
        .collect();
    nodes.sort_by(|a, b| a.order.cmp(&b.order).then_with(|| a.id.cmp(&b.id)));

    let mut children_of: std::collections::BTreeMap<String, Vec<HierarchyNode>> =
        std::collections::BTreeMap::new();
    let mut roots = Vec::new();
    for node in nodes {
        match &node.parent {
            Some(parent) => children_of.entry(parent.clone()).or_default().push(node),
            None => roots.push(node),
        }
    }
    for root in &mut roots {
        attach_children(root, &mut children_of);
    }
    roots
}

fn attach_children(
    node: &mut HierarchyNode,
    children_of: &mut std::collections::BTreeMap<String, Vec<HierarchyNode>>,
) {
    if let Some(mut kids) = children_of.remove(&node.id) {
        kids.sort_by(|a, b| a.order.cmp(&b.order).then_with(|| a.id.cmp(&b.id)));
        for kid in &mut kids {
            attach_children(kid, children_of);
        }
        node.children = kids;
    }
}

fn to_node(entity: &Entity) -> HierarchyNode {
    let name = entity
        .name
        .as_ref()
        .map(|n| n.value.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| entity.id_str());
    HierarchyNode {
        id: entity.id_str(),
        name,
        parent: entity.parent.map(format_entity_id),
        order: entity.order,
        children: Vec::new(),
    }
}

/// Walk the forest and return the first node whose id matches.
pub fn find_node<'a>(roots: &'a [HierarchyNode], id: &str) -> Option<&'a HierarchyNode> {
    for node in roots {
        if node.id == id {
            return Some(node);
        }
        if let Some(found) = find_node(&node.children, id) {
            return Some(found);
        }
    }
    None
}
