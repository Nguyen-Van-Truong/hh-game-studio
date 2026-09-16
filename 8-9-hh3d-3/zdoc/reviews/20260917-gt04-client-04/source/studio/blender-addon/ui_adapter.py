"""Private trusted-fixture Blender UI owner with checked native undo/redo."""
from contextlib import contextmanager
import importlib.util
import hashlib
import math
import os
from pathlib import Path

_spec = importlib.util.spec_from_file_location("_gt04_ui_queue", Path(__file__).with_name("ui_queue.py"))
queue_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(queue_module)
base, c = queue_module.base, queue_module.c
_ACTIVE = None


class UIAdapter(base.FixtureAdapter):
    def __init__(self, *, owned_root=None, external_poll=False):
        global _ACTIVE
        base.main_thread()
        if type(external_poll) is not bool:
            raise c.Rejected("BOOLEAN_POLL_OWNER_REQUIRED")
        import bpy
        if (bpy.app.background or bpy.app.version[:3] != (5, 2, 1) or
                not bpy.context.preferences.edit.use_global_undo or
                bpy.context.preferences.edit.undo_steps < 32 or _ACTIVE is not None):
            raise c.Rejected("PINNED_EXCLUSIVE_UI_UNDO_REQUIRED")
        windows = list(bpy.context.window_manager.windows)
        if len(windows) != 1:
            raise c.Rejected("ONE_OWNED_WINDOW_REQUIRED")
        self.bpy = bpy
        self._owned_root = None
        if owned_root is not None:
            root = Path(owned_root).absolute()
            self._check_root(root)
            if any(root.iterdir()):
                raise c.Rejected("FRESH_OWNED_SAVE_DIRECTORY_REQUIRED")
            self._owned_root = root
        self._window = windows[0].as_pointer()
        self._commands, self._held, self._stopped = {}, False, False
        self._pending, self._operator_result, self._operator_error = None, None, None
        self._history, self._cursor = [], 0
        self._closed, self._registered = False, False
        self.queue = queue_module.CommandQueue(self._dispatch)
        self._timer = self._tick
        self._baseline = self.inspect()
        owner = self

        class HH_GT04_OT_apply_fixture(bpy.types.Operator):
            bl_idname = "hh_gt04.apply_fixture"
            bl_label = "HH trusted fixture command"
            bl_options = {"REGISTER", "UNDO", "INTERNAL"}

            @classmethod
            def poll(cls, context):
                return _ACTIVE is owner and owner._pending is not None and not owner._held

            def execute(self, context):
                try:
                    owner._operator_result = base.FixtureAdapter.execute(owner, c.canonical(owner._pending))
                except BaseException as exc:
                    owner._operator_error = exc
                    # A possibly partial edit must retain Blender's undo step;
                    # the queue still returns failure and permanently holds owner.
                    return {"FINISHED"} if owner._held else {"CANCELLED"}
                return {"FINISHED"}

        self._operator = HH_GT04_OT_apply_fixture
        bpy.utils.register_class(self._operator)
        _ACTIVE = self
        try:
            # Baseline belongs to this fresh private UI session. All subsequent
            # semantic edits get automatic operator undo steps.
            with self._view():
                if bpy.ops.ed.undo_push(message="HH fixture initial state") != {"FINISHED"}:
                    raise c.Rejected("UNDO_BASELINE_FAILED")
            if not external_poll:
                bpy.app.timers.register(self._timer, first_interval=0.01, persistent=False)
                self._registered = True
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _view(self):
        base.main_thread()
        windows = [w for w in self.bpy.context.window_manager.windows if w.as_pointer() == self._window]
        if len(windows) != 1:
            raise c.Rejected("OWNED_WINDOW_LOST")
        window = windows[0]
        areas = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not areas:
            raise c.Rejected("VIEW_CONTEXT_LOST")
        area = areas[0]
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if region is None:
            raise c.Rejected("REGION_CONTEXT_LOST")
        with self.bpy.context.temp_override(window=window, area=area, region=region):
            yield

    def inspect(self):
        self._guard()
        with self._view():
            objects = self._objects()
            context = self._context(objects)
            snapshot = self._snapshot()
            # Read the live Edit Mesh representation without toggling modes or
            # producing invisible undo history during inspection.
            if context["mode"] == "EDIT_MESH":
                import bmesh
                for row in snapshot["objects"]:
                    obj = objects[row["object_id"]]
                    if obj.mode != "EDIT":
                        continue
                    bm = bmesh.from_edit_mesh(obj.data)
                    if (len(bm.verts), len(bm.edges), len(bm.faces)) != (8, 12, 6):
                        raise c.Rejected("UNSUPPORTED_EDIT_MESH")
                    vertices = sorted(bm.verts, key=lambda v: v.index)
                    faces = sorted(bm.faces, key=lambda f: f.index)
                    if [v.index for v in vertices] != list(range(8)) or [f.index for f in faces] != list(range(6)):
                        raise c.Rejected("UNSTABLE_EDIT_INDICES")
                    row["vertices"] = [list(v.co) for v in vertices]
                    row["faces"] = [[v.index for v in f.verts] for f in faces]
                    if any(not math.isfinite(x) for v in row["vertices"] for x in v):
                        raise c.Rejected("NONFINITE_NATIVE_STATE")
            return {"revision": c.digest(snapshot), "snapshot": snapshot, "context": context,
                    "public_ack": False, "undo_supported": True}

    def execute(self, raw):
        base.main_thread()
        raise c.Rejected("USE_MAIN_THREAD_QUEUE")

    @staticmethod
    def _check_root(root):
        if not root.is_dir():
            raise c.Rejected("OWNED_SAVE_ROOT_MISSING")
        for path in (root, *root.parents):
            if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                raise c.Rejected("REPARSE_SAVE_ROOT")

    def _save(self, command, before):
        if self._owned_root is None:
            raise c.Rejected("NO_OWNED_SAVE_ROOT")
        self._check_root(self._owned_root)
        name = command["payload"]["slot"] + ".blend"
        target, staged = self._owned_root / name, self._owned_root / ("stage-" + name)
        if target.exists() or staged.exists():
            raise c.Rejected("SAVE_SLOT_EXISTS")
        try:
            result = self.bpy.ops.wm.save_as_mainfile(filepath=str(staged), check_existing=False, copy=True)
            if result != {"FINISHED"} or not staged.is_file():
                raise c.Rejected("NATIVE_SAVE_INCOMPLETE")
            self._check_root(self._owned_root)
            if staged.is_symlink() or getattr(staged.lstat(), "st_file_attributes", 0) & 0x400:
                raise c.Rejected("REPARSE_STAGED_SAVE")
            after = self.inspect()
            if after != before:
                raise c.Rejected("SAVE_CHANGED_SCENE_OR_CONTEXT")
            os.link(staged, target)  # Exclusive name publication in trusted owned root.
            staged.unlink()
            artifact = {"name": name, "size_bytes": target.stat().st_size,
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
            return {"operation": "checkpoint.save", "after": after, "artifact": artifact,
                    "status": "INTERNAL_UI_SAVED", "native_operator_finished": True, "public_ack": False,
                    "durable_publication": False}
        except BaseException:
            self._held = True
            raise

    def _restore_context(self, context):
        # Native undo invalidates object RNA. Resolve stable IDs only now.
        objects = self._objects()
        if self.bpy.context.mode == "EDIT_MESH":
            self._mode("OBJECT")
        for obj in objects.values():
            obj.select_set(False)
        for key in context["selected_ids"]:
            objects[key].select_set(True)
        self.bpy.context.view_layer.objects.active = objects.get(context["active_id"])
        if context["mode"] == "EDIT_MESH":
            self._mode("EDIT")
        if self._context(objects) != context:
            raise c.Rejected("UI_CONTEXT_RESTORE_FAILED")

    def _dispatch(self, command):
        try:
            return self._dispatch_checked(command)
        except c.Rejected as exc:
            if self._held:
                # A partial native effect is not a no-effect rejection. The
                # queue retains HELD, cancels pending work and propagates.
                raise RuntimeError("NATIVE_OWNER_HELD: " + str(exc)) from exc
            raise

    def _dispatch_checked(self, command):
        self._guard()
        operation = command["operation"]
        profile = None
        if operation == "export.prepare":
            path = Path(__file__).with_name("export_profile.py")
            spec = importlib.util.spec_from_file_location("_hh_export_profile", path)
            module = importlib.util.module_from_spec(spec)
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            try:
                profile = module.preflight(self.bpy)
            except module.ExportRejected as exc:
                raise c.Rejected(str(exc)) from exc
        if operation == "scene.inspect":
            return self.inspect()
        before = self.inspect()
        if command["expected_revision"] != before["revision"]:
            raise c.Rejected("STALE_REVISION")
        if command["expected_context"] != before["context"]:
            raise c.Rejected("CONTEXT_DRIFT")
        with self._view():
            if operation == "export.prepare":
                result = self._save(command, before)
                result.update(operation=operation, export_profile=profile)
                return result
            if operation == "checkpoint.save":
                return self._save(command, before)
            if operation in ("history.undo", "history.redo"):
                return self._history_step(operation, before)
            if len(self._history) >= 16:
                raise c.Rejected("HISTORY_CAPACITY")
            known = (self._history[self._cursor - 1][1] if self._cursor else
                     self._history[0][0] if self._history else self._baseline)
            new_segment = before != known
            self._pending = dict(command, schema=c.SCHEMA)
            self._operator_error, self._operator_result = None, None
            try:
                if before["context"]["mode"] == "EDIT_MESH":
                    # Object transforms must use a global undo step, not an
                    # Edit Mesh geometry-only step. Mode calls suppress their
                    # own automatic undo; restore Edit Mode after the push.
                    self._mode("OBJECT")
                    self._pending["expected_context"] = self._context(self._objects())
                if new_segment:
                    # Manual context/scene edits start a new owned history
                    # segment. Never undo across an unowned intervening edit.
                    if self.bpy.ops.ed.undo_push(message="HH current context baseline") != {"FINISHED"}:
                        raise c.Rejected("CONTEXT_UNDO_BASELINE_FAILED")
                    self._history, self._cursor, self._baseline = [], 0, before
                result = self.bpy.ops.hh_gt04.apply_fixture("EXEC_DEFAULT", True)
                if self._operator_error is not None:
                    raise self._operator_error
                if result != {"FINISHED"} or self._operator_result is None:
                    raise c.Rejected("NATIVE_OPERATOR_INCOMPLETE")
                self._restore_context(before["context"])
                after = self.inspect()
                if after["snapshot"] != self._operator_result["after"]["snapshot"] or after["context"] != before["context"]:
                    raise c.Rejected("POST_OPERATOR_READBACK_MISMATCH")
                self._history[self._cursor:] = [(before, after)]
                self._cursor += 1
                return {"operation": operation, "before_revision": before["revision"], "after": after,
                        "native_operator_finished": True, "status": "INTERNAL_UI_READBACK", "public_ack": False}
            except BaseException:
                # Preflight rejections from the base adapter are no-effect;
                # any exception after it returned is uncertain and holds.
                if self._operator_result is not None:
                    self._held = True
                raise
            finally:
                self._pending = None
                if not self._held:
                    try:
                        self._restore_context(before["context"])
                    except BaseException:
                        self._held = True
                        raise

    def _history_step(self, operation, before):
        undo = operation == "history.undo"
        if (undo and self._cursor == 0) or (not undo and self._cursor == len(self._history)):
            raise c.Rejected("NO_OWNED_HISTORY")
        pair = self._history[self._cursor - 1 if undo else self._cursor]
        current, target = (pair[1], pair[0]) if undo else pair
        if current != before:
            raise c.Rejected("HISTORY_STATE_DRIFT")
        try:
            if before["context"]["mode"] == "EDIT_MESH":
                self._mode("OBJECT")
            native = self.bpy.ops.ed.undo if undo else self.bpy.ops.ed.redo
            if not native.poll():
                raise c.Rejected("HISTORY_CONTEXT_REJECTED")
            if native() != {"FINISHED"}:
                raise c.Rejected("NATIVE_HISTORY_INCOMPLETE")
            self._restore_context(target["context"])
            after = self.inspect()  # RNA is resolved again after native undo.
            if after != target:
                raise c.Rejected("HISTORY_READBACK_MISMATCH")
            self._cursor += -1 if undo else 1
            return {"operation": operation, "before_revision": before["revision"], "after": after,
                    "native_operator_finished": True, "status": "INTERNAL_UI_READBACK", "public_ack": False}
        except BaseException:
            self._held = True
            raise

    def _tick(self):
        base.main_thread()
        if self._closed or self._held or self._stopped:
            self.queue.stop()
            return None
        try:
            self.queue.tick()
        except BaseException:
            self._held = True
            self.queue.stop()
            raise
        return 0.01

    def stop(self):
        base.main_thread()
        self._stopped = True
        self.queue.stop()

    def close(self):
        global _ACTIVE
        base.main_thread()
        self.stop()
        if self._registered and self.bpy.app.timers.is_registered(self._timer):
            self.bpy.app.timers.unregister(self._timer)
        self._registered = False
        if _ACTIVE is self:
            self.bpy.utils.unregister_class(self._operator)
            _ACTIVE = None
        self._closed = True
