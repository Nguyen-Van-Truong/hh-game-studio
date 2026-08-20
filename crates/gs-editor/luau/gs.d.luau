--!strict
-- Type stubs for implemented `gs.*` (docs/LUAU_API.md / WP-M3-2).
-- Editor never loads this into a VM (I3). `luau-analyze --defs` only.
-- Expected analyze binary version: Luau 0.709 (docs/VERSIONS.md).

export type GsTransform = {
	x: number,
	y: number,
	rot: number,
	sx: number,
	sy: number,
	z_index: number,
}

export type GsTime = {
	frame: number,
	seconds: number,
}

export type GsSpawnAt = {
	x: number?,
	y: number?,
}

export type ScriptSelf = {
	id: string,
	props: any,
	state: { [string]: any },
}

declare gs: {
	exists: (id: string) -> boolean,
	get_pos: (id: string) -> (number?, number?),
	get_transform: (id: string) -> GsTransform?,
	get_component: (id: string, typename: string) -> any,
	has_tag: (id: string, tag: string) -> boolean,
	dt: () -> number,
	time: () -> GsTime,
	action: (name: string) -> number,
	log: (level: string, msg: string) -> (),
	set_pos: (id: string, x: number, y: number) -> (),
	set_transform: (id: string, patch: any) -> (),
	set_component: (id: string, typename: string, patch: any) -> (),
	set_sprite: (id: string, asset_ref: any) -> (),
	add_tag: (id: string, tag: string) -> (),
	remove_tag: (id: string, tag: string) -> (),
	emit: (name: string, data: any) -> (),
	spawn: (blueprint_path: string, at: GsSpawnAt) -> string?,
	destroy: (id: string) -> (),
	overlaps: (id: string) -> { any },
	raycast: (...any) -> any,
}
