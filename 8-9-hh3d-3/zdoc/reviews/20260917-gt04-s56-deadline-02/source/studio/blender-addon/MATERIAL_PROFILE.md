# Closed opaque Principled material candidate

AUTHORITY=0; public_ack=false. Operation `material.set_principled` creates or
updates one original material on an existing owned box. Payload fields are
exactly `object_id`, `material_id`, `base_color` (three numbers), `metallic` and
`roughness`. Color and scalars are finite numbers in [0,1]; booleans are refused.
Alpha is fixed at one. Existing scene revision and Object/Edit Mesh context are
required, as for transform edits. Native binary32 values are read back exactly.

At most four materials exist, each assigned to one mesh's sole DATA-linked slot.
Sharing, unused materials, extra slots or face material indices are refused.
Stable material IDs follow the existing fixture ID grammar and names are derived
as `HH_Material_<id>`; callers cannot rename nodes or pass code, paths or node
graphs. Replacing a different material ID on an already assigned mesh is a
no-effect conflict. Updating that mesh's existing ID is supported.

Each material contains exactly one Principled BSDF and one active Material
Output, joined only by BSDF→Surface. All input sockets except Base Color,
Metallic and Roughness equal pinned Blender 5.2.1 defaults recorded in
`material_profile.py`. Node types, properties, links, socket names, viewport
PBR values and opaque alpha are validated. No textures, procedural nodes,
groups, animation, drivers, transmission, coat, emission or custom shader
profile is admitted. Unsupported default values represented as binary32 are kept
exactly, without tolerance-based acceptance of unsupported inputs.

The pinned exporter reads the Principled Base Color, Metallic and Roughness
inputs. ([Blender glTF documentation](https://docs.blender.org/manual/nl/5.2/addons/scene_gltf2.html))
Exporter output is accepted only with bounded metallic-roughness material
factors, no extensions/images/URIs, and matching opaque/double-sided state.
Material names/factors and owning primitives bind to the reopened native
snapshot with the existing 1e-6 GLB float tolerance. Arbitrary glTF materials
remain unsupported.

Creation/update use the actual UI operator UndoRedo path. Checkpoint and export
copies preserve mesh, transforms and material values for fresh-process native
reopen. Material01 retains a failed reopen harness import (the prior 14 native
checks passed); material02 repairs the harness path and is the next candidate.
No failed capture is overwritten or labelled as acceptance.
