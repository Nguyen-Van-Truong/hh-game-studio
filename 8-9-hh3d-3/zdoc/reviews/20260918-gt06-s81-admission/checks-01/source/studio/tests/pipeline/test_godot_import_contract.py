"""Pure consumer contract tests; no engine, native handles or acceptance claim."""
from copy import deepcopy
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.godot import consumer as c


def trs():
    return {'position': [0,0,0], 'rotation_xyzw': [0,0,0,1], 'scale': [1,1,1]}


def capture_png(width=640, height=640, *, srgb=True, blank=False, transparent=False):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind+value))
    pixel = bytes((18,24,32,0 if transparent else 255))
    row = pixel*width if blank else pixel*(width//2) + bytes((160,92,28,255))*(width-width//2)
    raw = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',width,height,8,6,0,0,0))
    if srgb:
        raw += chunk(b'sRGB', b'\0')
    return raw + chunk(b'IDAT', zlib.compress((b'\0'+row)*height)) + chunk(b'IEND', b'')


def visual_observation():
    """Synthetic report only: independent analytic camera rotations, no engine claim."""
    s, t = math.sin(math.atan(1/8)/2), math.cos(math.atan(1/8)/2)
    h = math.sqrt(.5)
    views = {'front': ([0,2,8], [-s,0,0,t]), 'back': ([0,2,-8], [0,t,s,0]),
             'left': ([-8,2,0], [-s*h,-t*h,-s*h,t*h]), 'right': ([8,2,0], [-s*h,t*h,s*h,t*h]),
             'top': ([0,9,0], [-h,0,0,h]), 'bottom': ([0,-7,0], [0,h,-h,0])}
    original = {'name': 'mat_fixture_crate', 'textures': {'0': {'decoded_rgba8_sha256': 'a'*64}}}
    authored = {'override_mesh': 'prp_fixture_crate_lod0',
                'material': {'name': 'mat_authored_override', 'base_color': [.18,.48,.72,1]}}
    observation = {'schema': 'HH-GT05-GODOT-OBSERVATION-1', 'phase': 'visual', 'pid': 1234,
        'formal_acceptance': False, 'engine': {'major': 4, 'minor': 7, 'patch': 2, 'status': 'stable', 'hash': 'ed1daf0bf'},
        'input_sha256': {'fixture.glb': 'b'*64, 'producer-report.json': 'c'*64}, 'consumer_sha256': 'd'*64,
        'meshes': {'prp_fixture_crate_lod0': {'surfaces': [{'material': deepcopy(original)}]}},
        'visual_material': {'mesh': 'prp_fixture_crate_lod0', 'original_material': original, 'override_disabled': True},
        'authored': authored, 'authored_after_capture': deepcopy(authored), 'captures': {},
        'clips': {'idle': {'length': 1.0, 'loop_mode': 1}, 'walk': {'length': 1.0, 'loop_mode': 1}}}
    observation['visual_lighting'] = {'key_energy': .65, 'fill_energy': .35, 'ambient_energy': .2,
        'key_transform': dict(trs(), rotation_xyzw=[-.36497167621709875,-.27781593346944056,-.11507512748638375,.8811195706053617]),
        'key_color': [1,1,1], 'fill_color': [1,1,1], 'ambient_color': [.8,.8,.8], 'background_color': [.055,.065,.08],
        'tonemap_mode': 0, 'exposure': 1, 'fill_transform_local': trs(), 'fill_is_camera_child': True, 'shadows_enabled': False}
    labels = [*views] + [f'{clip}_{frame:02d}' for clip in ('idle','walk') for frame in range(31)]
    for order,label in enumerate(labels, 1):
        clip, frame = ('idle',0) if label in views else (label[:-3], int(label[-2:]))
        position, quaternion = views[label if label in views else 'front']
        observation['captures'][label] = {'sha256': 'e'*64, 'width': 640, 'height': 640, 'pid': 1234,
            'frame': 100+order, 'rendered_frame': 50+order, 'captured_at_unix': 1_700_000_000+order/60,
            'monotonic_us': order*20000, 'source_sha256': 'b'*64, 'producer_report_sha256': 'c'*64,
            'consumer_sha256': 'd'*64, 'clip': clip, 'requested_time': frame/30,
            'clip_time': 0.0 if frame == 30 else frame/30, 'sample_frame': frame,
            'camera': {'transform': dict(trs(), position=position, rotation_xyzw=quaternion), 'projection': 1,
                       'size': 6, 'near': .05, 'far': 100, 'target': [0,1,0]},
            'draw_calls': {'visible': 8, 'shadow': 0, 'total': 8}, 'material_name': 'mat_fixture_crate',
            'override_is_null': True, 'prop_visible': True}
    return observation


def navigation_observation():
    name = 'env_fixture_axis_cube_nav'
    mesh = {'gltf_world_bounds': {'min': [-3,-.05,-2], 'max': [3,0,2]}}
    observed = {'pid': 456, 'input_sha256': {'fixture.glb': 'a'*64}, 'consumer_sha256': 'b'*64}
    role = {'kind': 'nav', 'region_class': 'NavigationRegion3D', 'enabled': True, 'vertices': 4, 'polygons': 2,
        'surface_policy': 'imported_box_top_triangles', 'surface_area': 24,
        'surface_vertices_world': [[-3,0,-2],[3,0,-2],[3,0,2],[-3,0,2]], 'map_iteration_before': 4}
    query = {'pid': 456, 'source_sha256': 'a'*64, 'consumer_sha256': 'b'*64, 'map_id': 123,
        'region_id': 4567, 'region_name': name+'_region', 'map_active': True, 'region_enabled': True,
        'navigation_layers': 1, 'map_iteration': 6, 'map_iteration_after': 6, 'region_iteration': 2,
        'sync_wait_frames': 1, 'sync_elapsed_ms': 16, 'physics_frame': 12, 'optimize': True, 'queries': {},
        'sync_observations': [
            {'map_iteration': 5, 'region_iteration': 2, 'physics_frame': 11, 'endpoint_owner_region_ids': [0,0,0,0]},
            {'map_iteration': 6, 'region_iteration': 2, 'physics_frame': 12, 'endpoint_owner_region_ids': [4567]*4}]}
    for label, start, end in (('diagonal_a',[-2.5,0,-1.5],[2.5,0,1.5]),
                               ('diagonal_b',[-2.5,0,1.5],[2.5,0,-1.5])):
        query['queries'][label] = {'requested_start': start, 'requested_end': end, 'points': [start,end],
            'surface_points': [start,end], 'surface_normals': [[0,1,0],[0,1,0]],
            'owner_region_ids': [4567,4567], 'path_length': math.sqrt(34)}
    role['path_query'] = query
    return role, mesh, observed, name


class ConsumerContractTests(unittest.TestCase):
    def test_navigation_requires_reachable_routes_on_actual_proxy_top(self):
        role, mesh, observed, name = navigation_observation()
        c._nav_path(role, mesh, observed, name)
        row = role['path_query']['queries']['diagonal_a']
        row['points'].insert(1, [0,0,0]); row['surface_points'].insert(1, [0,0,0])
        row['surface_normals'].insert(1, [0,1,0]); row['owner_region_ids'].insert(1,4567)
        c._nav_path(role, mesh, observed, name)

    def test_navigation_counts_and_enabled_are_insufficient_without_query(self):
        role, mesh, observed, name = navigation_observation(); role.pop('path_query')
        with self.assertRaisesRegex(c.ConsumerRejected, 'NAV_QUERY_FIELDS'):
            c._nav_path(role, mesh, observed, name)
        role, mesh, observed, name = navigation_observation(); role['path_query']['queries'].pop('diagonal_b')
        with self.assertRaisesRegex(c.ConsumerRejected, 'NAV_QUERY_SET'):
            c._nav_path(role, mesh, observed, name)

    def test_navigation_waits_for_region_visibility_in_map_snapshot(self):
        role, mesh, observed, name = navigation_observation()
        # Real async ordering: both counters are positive and newer than the
        # initial map, but only the second snapshot can query the new region.
        c._nav_path(role, mesh, observed, name)
        query = role['path_query']
        query['sync_observations'].pop()
        query.update(map_iteration=5, map_iteration_after=5, physics_frame=11, sync_wait_frames=0)
        with self.assertRaisesRegex(c.ConsumerRejected, 'NAV_SYNC_SNAPSHOT'):
            c._nav_path(role, mesh, observed, name)
        query['sync_observations'][0]['endpoint_owner_region_ids'] = [4567]*4
        c._nav_path(role, mesh, observed, name)

    def test_navigation_rejects_missing_inconsistent_or_foreign_sync_witness(self):
        edits = [('map_iteration', 4), ('region_iteration', 1), ('physics_frame', 11),
                 ('endpoint_owner_region_ids', [4567,4567,4567,9999]),
                 ('endpoint_owner_region_ids', [4567,4567,4567]),
                 ('endpoint_owner_region_ids', [4567,4567,4567,True])]
        for field, value in edits:
            role, mesh, observed, name = navigation_observation()
            role['path_query']['sync_observations'][-1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(c.ConsumerRejected):
                c._nav_path(role, mesh, observed, name)
        for history in ([], None, [{}]):
            role, mesh, observed, name = navigation_observation()
            role['path_query']['sync_observations'] = history
            with self.subTest(history=history), self.assertRaises(c.ConsumerRejected):
                c._nav_path(role, mesh, observed, name)

    def test_navigation_rejects_uninitialized_stale_changed_or_wrong_map_witness(self):
        edits = {'map_iteration': 0, 'map_iteration_after': 7, 'region_iteration': 0, 'map_id': 0,
                 'region_id': True, 'physics_frame': 0, 'map_active': False, 'region_enabled': False,
                 'navigation_layers': 2, 'region_name': 'another_region', 'sync_wait_frames': 121,
                 'sync_elapsed_ms': 2001, 'source_sha256': 'c'*64, 'consumer_sha256': 'c'*64, 'pid': 457}
        for field,value in edits.items():
            role, mesh, observed, name = navigation_observation(); role['path_query'][field] = value
            with self.subTest(field=field), self.assertRaises(c.ConsumerRejected):
                c._nav_path(role, mesh, observed, name)
        role, mesh, observed, name = navigation_observation(); role['map_iteration_before'] = 6
        with self.assertRaisesRegex(c.ConsumerRejected, 'NAV_SYNC_READBACK'):
            c._nav_path(role, mesh, observed, name)

    def test_navigation_rejects_empty_partial_snapped_and_displaced_routes(self):
        edits = [('points', []), ('points', [[-2.5,0,-1.5],[0,0,0]]),
                 ('points', [[-2.5,0,-1.5],[2.4,0,1.5]]),
                 ('requested_end', [2.4,0,1.5]), ('surface_points', [[-2.5,0,-1.5],[2.5,-.05,1.5]]),
                 ('surface_normals', [[0,-1,0],[0,-1,0]]), ('owner_region_ids', [4567,4568]),
                 ('path_length', 1.0)]
        for field,value in edits:
            role, mesh, observed, name = navigation_observation()
            role['path_query']['queries']['diagonal_a'][field] = value
            with self.subTest(field=field,value=value), self.assertRaises(c.ConsumerRejected):
                c._nav_path(role, mesh, observed, name)

    def test_navigation_midpoint_must_remain_on_walkable_floor_and_inside_bounds(self):
        for middle in ([0,-.05,0], [0,.002,0], [4,0,0], [0,0,3], [0,0,1]):
            role, mesh, observed, name = navigation_observation()
            row = role['path_query']['queries']['diagonal_a']
            row['points'].insert(1,middle); row['surface_points'].insert(1,middle)
            row['surface_normals'].insert(1,[0,1,0]); row['owner_region_ids'].insert(1,4567)
            row['path_length'] = sum(math.dist(a,b) for a,b in zip(row['points'],row['points'][1:]))
            with self.subTest(middle=middle), self.assertRaises(c.ConsumerRejected):
                c._nav_path(role, mesh, observed, name)

    def test_navigation_rejects_box_sides_bottom_or_incomplete_top_selection(self):
        for field,value in (('polygons',12), ('surface_policy','all_box_faces'), ('surface_area',12),
                             ('surface_vertices_world',[[-3,-.05,-2],[3,-.05,-2],[3,-.05,2],[-3,-.05,2]]),
                             ('surface_vertices_world',[[-3,0,-2],[3,0,-2],[3,0,2],[3,0,2]])):
            role, mesh, observed, name = navigation_observation(); role[field] = value
            with self.subTest(field=field), self.assertRaises(c.ConsumerRejected):
                c._nav_path(role, mesh, observed, name)

    def test_visual_requires_six_views_and_all_31_samples_per_clip(self):
        observed = visual_observation()
        self.assertEqual(len(observed['captures']), 68)
        c._verify_visual_observation(observed)
        for label in ('top','bottom','idle_30','walk_00'):
            changed = deepcopy(observed); changed['captures'].pop(label)
            with self.subTest(missing=label), self.assertRaisesRegex(c.ConsumerRejected, 'VISUAL_SET'):
                c._verify_visual_observation(changed)
        observed['captures']['pbr_detail'] = deepcopy(observed['captures']['front'])
        with self.assertRaisesRegex(c.ConsumerRejected, 'VISUAL_SET'):
            c._verify_visual_observation(observed)

    def test_legacy_visual_with_override_and_no_material_witness_is_rejected(self):
        observed = visual_observation(); observed.pop('visual_material')
        with self.assertRaisesRegex(c.ConsumerRejected, 'VISUAL_MATERIAL_FIELDS'):
            c._verify_visual_observation(observed)

    def test_visual_original_material_and_restored_authored_state_are_bound(self):
        edits = [
            (('visual_material','override_disabled'), False),
            (('visual_material','original_material','name'), 'mat_authored_override'),
            (('visual_material','original_material','textures','0','decoded_rgba8_sha256'), '0'*64),
            (('authored_after_capture','material','base_color'), [1,1,1,1]),
            (('captures','walk_15','material_name'), 'mat_authored_override'),
            (('captures','idle_20','override_is_null'), False),
            (('captures','back','prop_visible'), False),
        ]
        for path, value in edits:
            observed = visual_observation(); target = observed
            for key in path[:-1]: target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(c.ConsumerRejected):
                c._verify_visual_observation(observed)

    def test_visual_draw_calls_are_actual_positive_integral_bounded_counts(self):
        for calls in ({'visible': 0, 'shadow': 0, 'total': 0}, {'visible': 151, 'shadow': 0, 'total': 151},
                      {'visible': 8, 'shadow': 0, 'total': 1}, {'visible': True, 'shadow': 0, 'total': 1},
                      {'visible': 8.0, 'shadow': 0, 'total': 8}, {'visible': 8, 'shadow': -1, 'total': 7},
                      {'visible': 8, 'shadow': 1, 'total': 9}, {'total': 8}):
            observed = visual_observation(); observed['captures']['walk_29']['draw_calls'] = calls
            with self.subTest(calls=calls), self.assertRaisesRegex(c.ConsumerRejected, 'DRAW_CALL'):
                c._verify_visual_observation(observed)
        observed = visual_observation()
        observed['captures']['walk_29']['draw_calls'] = {'visible': 150, 'shadow': 0, 'total': 150}
        c._verify_visual_observation(observed)

    def test_each_visual_frame_binds_pid_source_and_exact_clip_sample(self):
        edits = {'pid': 1235, 'source_sha256': '0'*64, 'producer_report_sha256': '0'*64,
                 'consumer_sha256': '0'*64, 'clip': 'idle', 'sample_frame': 0, 'clip_time': .5,
                 'requested_time': .5, 'width': 320, 'height': 320}
        for field, value in edits.items():
            observed = visual_observation(); observed['captures']['walk_20'][field] = value
            with self.subTest(field=field), self.assertRaises(c.ConsumerRejected):
                c._verify_visual_observation(observed)
        observed = visual_observation(); observed['captures']['left']['sample_frame'] = True
        with self.assertRaisesRegex(c.ConsumerRejected, 'CLIP_SAMPLE'):
            c._verify_visual_observation(observed)

    def test_native_one_second_loop_endpoint_wraps_only_at_final_sample(self):
        # Actual s62-01 native readback: requested 29/30 -> .966666666666667,
        # requested 1.0 -> 0.0, for both verified LOOP_LINEAR, length=1 clips.
        observed = visual_observation()
        for clip in ('idle','walk'):
            observed['captures'][clip+'_29']['requested_time'] = .966666666666667
            observed['captures'][clip+'_29']['clip_time'] = .966666666666667
            observed['captures'][clip+'_30']['requested_time'] = 1.0
            observed['captures'][clip+'_30']['clip_time'] = 0.0
        c._verify_visual_observation(observed)
        for clip in ('idle','walk'):
            for frame in (1,15,29):
                wrong = deepcopy(observed); wrong['captures'][f'{clip}_{frame:02d}']['clip_time'] = 0.0
                with self.subTest(clip=clip, early_frame=frame), self.assertRaisesRegex(c.ConsumerRejected, 'NUMERIC_MISMATCH'):
                    c._verify_visual_observation(wrong)
            for value in (1.0, 1e-12, True):
                wrong = deepcopy(observed); wrong['captures'][clip+'_30']['clip_time'] = value
                with self.subTest(clip=clip, endpoint=value), self.assertRaises(c.ConsumerRejected):
                    c._verify_visual_observation(wrong)

    def test_visual_endpoint_requires_native_loop_and_exact_length(self):
        for field, value in (('loop_mode',0), ('loop_mode',2), ('loop_mode',True), ('length',.999), ('length',True)):
            observed = visual_observation(); observed['clips']['idle'][field] = value
            with self.subTest(field=field,value=value), self.assertRaisesRegex(c.ConsumerRejected, 'LOOP_READBACK'):
                c._verify_visual_observation(observed)
        observed = visual_observation(); observed['clips']['walk'].pop('loop_mode')
        with self.assertRaisesRegex(c.ConsumerRejected, 'LOOP_READBACK'):
            c._verify_visual_observation(observed)

    def test_repeated_out_of_order_or_nonfinite_frame_witnesses_fail(self):
        for field in ('frame','rendered_frame','monotonic_us','captured_at_unix'):
            observed = visual_observation()
            observed['captures']['back'][field] = observed['captures']['front'][field]
            with self.subTest(field=field), self.assertRaisesRegex(c.ConsumerRejected, '(FRAME|TIME)_ORDER'):
                c._verify_visual_observation(observed)
        observed = visual_observation(); observed['captures']['front']['captured_at_unix'] = float('nan')
        with self.assertRaisesRegex(c.ConsumerRejected, 'FINITE_VECTOR'):
            c._verify_visual_observation(observed)

    def test_camera_labels_cannot_reuse_front_transform_or_point_away(self):
        for label in ('back','left','right','top','bottom'):
            observed = visual_observation()
            observed['captures'][label]['camera'] = deepcopy(observed['captures']['front']['camera'])
            with self.subTest(label=label), self.assertRaises(c.ConsumerRejected):
                c._verify_visual_observation(observed)
        for field, value in (('projection', 0), ('size', 60), ('target', [0,0,0])):
            observed = visual_observation(); observed['captures']['front']['camera'][field] = value
            with self.subTest(field=field), self.assertRaises(c.ConsumerRejected):
                c._verify_visual_observation(observed)
        observed = visual_observation()
        observed['captures']['front']['camera']['transform']['rotation_xyzw'] = [0,1,0,0]
        with self.assertRaises(c.ConsumerRejected):
            c._verify_visual_observation(observed)

    def test_neutral_visual_lighting_is_read_back_and_fixed(self):
        for field, value in (('key_color',[1,0,0]), ('ambient_color',[0,0,1]), ('exposure',10),
                             ('tonemap_mode',1), ('fill_energy',0), ('shadows_enabled',True),
                             ('fill_is_camera_child',False), ('key_transform',trs())):
            observed = visual_observation(); observed['visual_lighting'][field] = value
            with self.subTest(field=field), self.assertRaises(c.ConsumerRejected):
                c._verify_visual_observation(observed)

    def test_native_png_validates_actual_pixels_dimensions_and_srgb_crc(self):
        for srgb in (False,True):
            c._verify_visual_png(capture_png(srgb=srgb))
        for raw, code in ((capture_png(width=320), 'DIMENSIONS'), (capture_png(blank=True), 'EMPTY'),
                          (capture_png(transparent=True), 'EMPTY'), (b'not a screenshot'*5, 'INVALID')):
            with self.subTest(code=code), self.assertRaisesRegex(c.ConsumerRejected, code):
                c._verify_visual_png(raw)
        raw = bytearray(capture_png()); raw[45] ^= 1
        with self.assertRaisesRegex(c.ConsumerRejected, 'SRGB'):
            c._verify_visual_png(bytes(raw))
        raw = bytearray(capture_png()); raw[-1] ^= 1
        with self.assertRaisesRegex(c.ConsumerRejected, 'INVALID'):
            c._verify_visual_png(bytes(raw))

    def test_binding_checks_image_bytes_and_dimensions_even_with_rebound_report_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder); (project/'input').mkdir(); (project/'out').mkdir()
            inputs = {'fixture.glb': b'fixed fixture', 'producer-report.json': b'fixed producer report'}
            for name, raw in inputs.items(): (project/'input'/name).write_bytes(raw)
            seed = {'input_sha256': {name: c.sha(raw) for name,raw in inputs.items()}, 'authored_sha256': {}}
            (project/'input/consumer.json').write_bytes(c.encoded(seed))
            observed = visual_observation(); observed.update(seed)
            observed['consumer_sha256'] = c.sha(c.encoded(seed))
            png = capture_png()
            for label, capture in observed['captures'].items():
                capture.update(source_sha256=seed['input_sha256']['fixture.glb'],
                    producer_report_sha256=seed['input_sha256']['producer-report.json'],
                    consumer_sha256=observed['consumer_sha256'], sha256=c.sha(png))
                (project/'out'/(label+'.png')).write_bytes(png)
            def verify():
                raw = c.encoded(observed); (project/'out/visual.json').write_bytes(raw)
                stdout = b'GT05_GODOT_OBSERVED ' + c.encoded({'phase': 'visual', 'pid': observed['pid'],
                    'report_sha256': c.sha(raw), 'formal_acceptance': False})
                return c.verify_binding(project, phase='visual', stdout=stdout)
            self.assertEqual(len(verify()['captures']), 68)
            extra = project/'out/pbr_detail.png'; extra.write_bytes(png)
            with self.assertRaisesRegex(c.ConsumerRejected, 'VISUAL_FILE_SET'): verify()
            extra.unlink()
            target = project/'out/walk_30.png'; target.write_bytes(b'changed pixels')
            with self.assertRaisesRegex(c.ConsumerRejected, 'VISUAL_BYTES'): verify()
            wrong_size = capture_png(width=320); target.write_bytes(wrong_size)
            observed['captures']['walk_30']['sha256'] = c.sha(wrong_size)
            with self.assertRaisesRegex(c.ConsumerRejected, 'PNG_DIMENSIONS'): verify()

    def test_imported_albedo_rgb_returns_to_linear_factor_domain_and_preserves_alpha(self):
        # Independent sRGB reference values cover both transfer-function branches.
        actual = c._albedo_linear([.5, .040, 1, .37])
        c._near(actual, [.21404114048223255, .0030959752321981426, 1, .37], 1e-12)
        c._near(c._albedo_linear([.854305863380432, .6651850938797, .506386458873749, 1]),
                [.7,.4,.22,1], .0001)

    def test_color_conversion_does_not_hide_actual_factor_or_alpha_edits(self):
        expected = [.21404114048223255, 0, 0, .37]
        for native in ([.51,0,0,.37], [.5,0,0,.38]):
            with self.subTest(native=native), self.assertRaisesRegex(c.ConsumerRejected, 'NUMERIC_MISMATCH'):
                c._near(c._albedo_linear(native), expected, .0001)

    def test_inverse_bind_uses_rotated_translation_and_exact_bone_names(self):
        joint = {'position': [2,3,0], 'rotation_xyzw': [0,0,math.sqrt(.5),math.sqrt(.5)], 'scale': [1,1,1]}
        inverse = {'position': [-3,2,0], 'rotation_xyzw': [0,0,-math.sqrt(.5),math.sqrt(.5)], 'scale': [1,1,1]}
        c._trs(c._inverse_rigid_trs(joint), inverse)
        bones = {'bn_root': {'rest_gltf_world': trs()}, 'bn_hand': {'rest_gltf_world': joint}}
        # Bind array order can differ from skeleton bone order, but names cannot.
        actual = {'skin_bind_names': ['bn_hand','bn_root'], 'skin_bind_poses': [inverse,trs()]}
        c._skin_inverse_binds(actual, bones)
        actual['skin_bind_names'] = ['bn_root','bn_hand']
        with self.assertRaises(c.ConsumerRejected):
            c._skin_inverse_binds(actual, bones)

    def test_missing_duplicate_and_corrupted_inverse_binds_fail(self):
        bones = {'bn_root': {'rest_gltf_world': trs()}}
        for names, poses in (([], []), (['bn_root'], []), (['bn_root','bn_root'], [trs(),trs()])):
            with self.subTest(names=names), self.assertRaisesRegex(c.ConsumerRejected, 'SKIN_BIND_POSE_SET'):
                c._skin_inverse_binds({'skin_bind_names': names, 'skin_bind_poses': poses}, bones)
        wrong = trs(); wrong['position'] = [.002,0,0]
        with self.assertRaisesRegex(c.ConsumerRejected, 'NUMERIC_MISMATCH'):
            c._skin_inverse_binds({'skin_bind_names': ['bn_root'], 'skin_bind_poses': [wrong]}, bones)

    def test_quaternion_sign_does_not_change_orientation(self):
        expected = trs(); actual = trs(); actual['rotation_xyzw'] = [0,0,0,-1]
        c._trs(actual, expected)

    def test_allowed_quaternion_norm_roundoff_cannot_create_false_angular_error(self):
        # Without dot/(norm_a*norm_b), this same orientation appears ~0.11 deg apart.
        actual = trs(); actual['rotation_xyzw'] = [0,0,0,.9999995]
        c._trs(actual, trs())

    def test_pose_grid_contains_every_30hz_frame_and_existing_half_frame_checks(self):
        self.assertEqual(len(c.SAMPLE_TIMES), 33)
        self.assertEqual(c.SAMPLE_TIMES, sorted([frame/30 for frame in range(31)] + [.25,.75]))

    def test_position_uses_euclidean_error(self):
        actual = trs(); actual['position'] = [.0008,.0008,0]
        with self.assertRaisesRegex(c.ConsumerRejected, 'NUMERIC_MISMATCH'):
            c._trs(actual, trs())

    def test_scaled_quaternion_cannot_hide_orientation(self):
        actual = trs(); actual['rotation_xyzw'] = [0,0,0,1.5]
        with self.assertRaisesRegex(c.ConsumerRejected, 'UNIT_QUATERNION'):
            c._trs(actual, trs())

    def test_rotation_threshold_is_geodesic(self):
        actual = trs(); angle = math.radians(.2)/2
        actual['rotation_xyzw'] = [0,math.sin(angle),0,math.cos(angle)]
        with self.assertRaisesRegex(c.ConsumerRejected, 'ROTATION_MISMATCH'):
            c._trs(actual, trs())

    def test_nonfinite_bool_and_wrong_shape_rejected(self):
        for vector in ([True,0,0], [float('nan'),0,0], [0,0]):
            actual = trs(); actual['position'] = vector
            with self.subTest(vector=vector), self.assertRaises(c.ConsumerRejected):
                c._trs(actual, trs())

    def test_strict_json_rejects_duplicate_nonfinite_and_deep(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e400}', b'{"x":'+b'['*40+b'0'+b']'*40+b'}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(c.ConsumerRejected):
                c.strict(raw)

    def test_traversal_rejected_before_normalization(self):
        with self.assertRaisesRegex(c.ConsumerRejected, 'TRAVERSAL'):
            c._path(Path('owned')/'..'/'outside')

    def test_fixed_command_arguments_have_no_eval_or_external_script(self):
        path = Path('owned')
        self.assertEqual(c.command(Path('pinned.exe'), path, 'baseline')[-5:],
                         ['--script', 'res://probe.gd', '--', '--phase', 'baseline'])
        for phase in ('../../outside', '--eval', 'passed'):
            with self.assertRaisesRegex(c.ConsumerRejected, 'PHASE'):
                c.command(Path('pinned.exe'), path, phase)

    def test_empty_claim_cannot_count_as_required_fixture(self):
        expected = {'meshes': {}, 'rig': {'bones': {}}, 'clips': {}}
        producer = {'schema': c.contract.SCHEMA, 'catalog': c.contract.asset_catalog(),
                    'observed': expected, 'observed_sha256': c.contract.digest(expected),
                    'artifacts': {'fixture.glb': {'sha256': 'a'*64}}, 'passed': True}
        observation = {'schema': 'HH-GT05-GODOT-OBSERVATION-1', 'formal_acceptance': False,
                       'input_sha256': {'fixture.glb': 'a'*64}, 'passed': True}
        with self.assertRaisesRegex(c.ConsumerRejected, 'REQUIRED_FIXTURE'):
            c.compare_observation(producer, observation)

    def test_reimport_rejects_wrong_baseline_before_replacing_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder); (project/'input').mkdir(); (project/'out').mkdir()
            seed = {'input_sha256': {'fixture.glb': 'a'*64}, 'authored_sha256': {}}
            (project/'input/consumer.json').write_bytes(c.encoded(seed))
            (project/'out/baseline.json').write_bytes(c.encoded({'input_sha256': {'fixture.glb': 'b'*64}}))
            with self.assertRaisesRegex(c.ConsumerRejected, 'BASELINE_BINDING'):
                c.replace_inputs(project, glb=b'not admitted', manifest=b'{}', producer_report=b'{}')
            self.assertFalse((project/'input/fixture.glb').exists())


if __name__ == '__main__':
    unittest.main()
