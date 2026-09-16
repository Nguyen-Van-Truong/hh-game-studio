import importlib.util
import json
from pathlib import Path
import threading
import unittest

spec = importlib.util.spec_from_file_location("gt04_test_queue", Path(__file__).resolve().parents[2] / "blender-addon/ui_queue.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def command(key="create-one", operation="mesh.create_box"):
    value = {"schema": q.SCHEMA, "command_id": key, "operation": operation,
             "expected_revision": "sha256:" + "1" * 64,
             "expected_context": {"mode": "OBJECT", "active_id": None, "selected_ids": []},
             "payload": {"object_id": "one", "size": [1, 1, 1]}}
    if operation.startswith("history."):
        value["payload"] = {}
    elif operation == "scene.inspect":
        value.update(expected_revision=None,expected_context=None,payload={})
    return q.c.canonical(value)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.calls = []
        self.owner = q.CommandQueue(lambda c: self.calls.append(c["command_id"]) or {"revision": "native"}, clock=lambda: self.now)

    def test_no_effect_on_submit_and_one_per_tick(self):
        self.owner.submit(command("one"))
        self.owner.submit(command("two"))
        self.assertEqual(self.calls, [])
        self.owner.tick()
        self.assertEqual(self.calls, ["one"])
        self.assertEqual(self.owner.result("two")["state"], "PENDING")

    def _arm_writer(self):
        self.lease_now=100
        self.owner._lease_clock=lambda:self.lease_now
        lease={'fencing_epoch':1,'expires_ms':1000}
        self.owner.arm_lease(lease)
        return lease

    def test_inspect_without_lease_after_writer_arms_and_expires(self):
        self._arm_writer()
        self.owner.submit(command('read-before-expiry','scene.inspect'))
        self.lease_now=1000
        self.owner.tick()
        self.assertEqual(self.owner.result('read-before-expiry')['state'],'COMPLETED')
        self.owner.submit(command('read-after-expiry','scene.inspect'))
        self.owner.tick()
        self.assertEqual(self.owner.result('read-after-expiry')['state'],'COMPLETED')
        self.assertEqual(self.calls,['read-before-expiry','read-after-expiry'])

    def test_inspect_queued_before_writer_arms_keeps_read_authority(self):
        self.owner.submit(command('queued-read','scene.inspect'))
        self._arm_writer();self.owner.tick()
        self.assertEqual(self.owner.result('queued-read')['state'],'COMPLETED')

    def test_inspect_explicit_lease_is_checked_before_admission(self):
        lease=self._arm_writer()
        for invalid in ({},dict(lease,fencing_epoch=2),dict(lease,expires_ms=1001),
                        dict(lease,fencing_epoch=True)):
            with self.subTest(lease=invalid),self.assertRaises(q.c.Rejected):
                self.owner.submit(command('invalid-read','scene.inspect'),lease=invalid)
        self.lease_now=1000
        with self.assertRaisesRegex(q.c.Rejected,'WRITER_FENCED_OR_EXPIRED'):
            self.owner.submit(command('expired-read','scene.inspect'),lease=lease)
        self.assertEqual(self.calls,[]);self.assertEqual(self.owner._rows,{})

    def test_inspect_explicit_lease_is_rechecked_at_dispatch(self):
        lease=self._arm_writer()
        self.owner.submit(command('explicit-read','scene.inspect'),lease=lease)
        self.lease_now=1000;self.owner.tick()
        self.assertEqual(self.owner.result('explicit-read')['state'],'REJECTED')
        self.assertEqual(self.owner.result('explicit-read')['reason'],'WRITER_FENCED_OR_EXPIRED')
        self.assertEqual(self.calls,[])

    def test_inspect_read_exemption_preserves_stop_and_deadline(self):
        self._arm_writer()
        self.owner.submit(command('expired-read','scene.inspect'),ttl_ms=1)
        self.now=.002;self.owner.tick()
        self.assertEqual(self.owner.result('expired-read')['state'],'EXPIRED')
        self.owner.submit(command('stopped-read','scene.inspect'))
        self.owner.stop();self.owner.tick()
        self.assertEqual(self.owner.result('stopped-read')['state'],'CANCELLED')
        with self.assertRaisesRegex(q.c.Rejected,'STOPPED'):
            self.owner.submit(command('new-read','scene.inspect'))
        self.assertEqual(self.calls,[])

    def test_read_exemption_does_not_authorize_any_mutation(self):
        lease=self._arm_writer()
        payloads={
            'mesh.create_box':{'object_id':'one','size':[1,1,1]},
            'object.transform.set':{'object_id':'one','location':[0,0,0],'rotation':[0,0,0],'scale':[1,1,1]},
            'material.set_principled':{'object_id':'one','material_id':'color','base_color':[1,1,1],
                'metallic':0,'roughness':.5},
            'history.undo':{},'history.redo':{},'checkpoint.save':{'slot':'checkpoint'},
            'export.prepare':{'slot':'export'},
        }
        for index,(operation,payload) in enumerate(payloads.items()):
            value=json.loads(command('mutation-'+str(index),operation));value['payload']=payload
            raw=q.c.canonical(value)
            with self.subTest(operation=operation),self.assertRaisesRegex(q.c.Rejected,'WRITER_FENCED_OR_EXPIRED'):
                self.owner.submit(raw)
            self.owner.submit(raw,lease=lease)
        self.lease_now=1000
        for _ in payloads:self.owner.tick()
        self.assertTrue(all(row['state']=='REJECTED' for row in self.owner._rows.values()))
        self.assertEqual(self.calls,[])

    def test_duplicate_pending_and_completed_detached(self):
        raw = command()
        self.owner.submit(raw)
        self.owner.submit(raw)
        self.owner.tick()
        row = self.owner.result("create-one")
        detached = self.owner.submit(raw)
        detached["result"]["revision"] = "changed"
        self.assertEqual(self.owner.submit(raw), row)
        self.assertEqual(len(self.calls), 1)

    def test_history_duplicate_does_not_dispatch_twice(self):
        raw = command("undo-one", "history.undo")
        self.owner.submit(raw)
        self.owner.tick()
        self.owner.submit(raw)
        self.owner.tick()
        self.assertEqual(self.calls, ["undo-one"])

    def test_duplicate_conflict(self):
        self.owner.submit(command())
        value = json.loads(command())
        value["payload"]["size"] = [2, 2, 2]
        with self.assertRaisesRegex(q.c.Rejected, "COMMAND_CONFLICT"):
            self.owner.submit(q.c.canonical(value))

    def test_deadline_no_effect_and_retry_cannot_extend(self):
        raw = command()
        self.owner.submit(raw, ttl_ms=1)
        self.now = 0.002
        self.owner.submit(raw, ttl_ms=5000)
        self.owner.tick()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.owner.result("create-one")["state"], "EXPIRED")

    def test_bad_deadlines(self):
        for ttl in (0, -1, 5001, True, 1.5):
            with self.subTest(ttl=ttl), self.assertRaises(q.c.Rejected):
                self.owner.submit(command(), ttl_ms=ttl)

    def test_pending_capacity(self):
        for i in range(q.MAX_PENDING):
            self.owner.submit(command("cmd-" + str(i)))
        with self.assertRaisesRegex(q.c.Rejected, "QUEUE_CAPACITY"):
            self.owner.submit(command("extra"))

    def test_total_receipt_capacity(self):
        for i in range(q.MAX_REQUESTS):
            self.owner.submit(command("cmd-" + str(i)))
            self.owner.tick()
        with self.assertRaisesRegex(q.c.Rejected, "QUEUE_CAPACITY"):
            self.owner.submit(command("extra"))

    def test_stop_cancels_pending_retains_results(self):
        self.owner.submit(command("one"))
        self.owner.tick()
        original = self.owner.result("one")
        self.owner.submit(command("two"))
        self.owner.stop()
        self.owner.tick()
        self.assertEqual(self.owner.result("two")["state"], "CANCELLED")
        self.assertEqual(self.owner.submit(command("one")), original)
        with self.assertRaisesRegex(q.c.Rejected, "STOPPED"):
            self.owner.submit(command("three"))

    def test_rejection_is_retained(self):
        def reject(value):
            raise q.c.Rejected("STALE_REVISION")
        self.owner._dispatch = reject
        self.owner.submit(command())
        self.owner.tick()
        self.assertEqual(self.owner.result("create-one")["reason"], "STALE_REVISION")

    def test_cancellation_holds_and_stops(self):
        def cancel(value):
            raise KeyboardInterrupt()
        self.owner._dispatch = cancel
        self.owner.submit(command())
        self.owner.submit(command("second"))
        with self.assertRaises(KeyboardInterrupt):
            self.owner.tick()
        self.assertEqual(self.owner.result("create-one")["state"], "HELD")
        self.assertEqual(self.owner.result("second")["state"], "CANCELLED")

    def test_no_thread_entry(self):
        outcomes = []
        def worker():
            for action in (lambda: self.owner.submit(command()),
                           lambda: self.owner.submit(command('read','scene.inspect')),self.owner.tick,self.owner.stop):
                try:
                    action()
                except q.c.Rejected as exc:
                    outcomes.append(str(exc))
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(2)
        self.assertEqual(outcomes, ["MAIN_THREAD_REQUIRED"] * 4)
        self.assertFalse(thread.is_alive())

    def test_history_requires_revision_context_and_empty_payload(self):
        for key, value in (("expected_revision", None), ("expected_context", {}), ("payload", {"index": 1})):
            cmd = json.loads(command("undo", "history.undo"))
            cmd[key] = value
            with self.subTest(key=key), self.assertRaises(q.c.Rejected):
                q.parse(q.c.canonical(cmd))

    def test_unsafe_payloads(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"x":NaN}', b" " * 4097, b"[" * 2000 + b"]" * 2000,
                    command(operation="python.exec"), command(operation="file.open")):
            with self.subTest(raw=raw[:50]), self.assertRaises(q.c.Rejected):
                q.parse(raw)

    def test_fixed_save_slots(self):
        for slot in ("checkpoint", "fixture"):
            value = json.loads(command(operation="checkpoint.save"))
            value["payload"] = {"slot": slot}
            self.assertEqual(q.parse(q.c.canonical(value))["payload"], {"slot": slot})

    def test_save_rejects_paths_and_extra_fields(self):
        for payload in ({"slot": "../artist"}, {"slot": "C:\\artist.blend"}, {"slot": "fixture", "path": "other"}, {}):
            value = json.loads(command(operation="checkpoint.save"))
            value["payload"] = payload
            with self.subTest(payload=payload), self.assertRaises(q.c.Rejected):
                q.parse(q.c.canonical(value))

    def test_export_requires_exact_fixed_slot(self):
        value = json.loads(command(operation="export.prepare"))
        value["payload"] = {"slot": "export"}
        self.assertEqual(q.parse(q.c.canonical(value)), value)
        for payload in ({"slot": "fixture"}, {"slot": "../export"}, {"slot": "export", "path": "x"}, {}):
            with self.subTest(payload=payload), self.assertRaises(q.c.Rejected):
                q.parse(q.c.canonical(dict(value, payload=payload)))

    def test_export_requires_revision_and_context(self):
        value = json.loads(command(operation="export.prepare"))
        value["payload"] = {"slot": "export"}
        for key, field in (("expected_revision", None), ("expected_context", {})):
            with self.subTest(key=key), self.assertRaises(q.c.Rejected):
                q.parse(q.c.canonical(dict(value, **{key: field})))

    def test_export_duplicate_has_one_effect_and_conflict_rejected(self):
        value = json.loads(command(operation="export.prepare"))
        value["payload"] = {"slot": "export"}
        raw = q.c.canonical(value)
        self.owner.submit(raw); self.owner.tick()
        original = self.owner.result(value["command_id"])
        self.assertEqual(self.owner.submit(raw), original)
        self.owner.tick()
        self.assertEqual(self.calls, [value["command_id"]])
        value["expected_revision"] = "sha256:" + "2" * 64
        with self.assertRaisesRegex(q.c.Rejected, "COMMAND_CONFLICT"):
            self.owner.submit(q.c.canonical(value))

    def test_ui_partial_effect_is_held_not_rejected(self):
        spec = importlib.util.spec_from_file_location("gt04_ui_held_test", Path(q.__file__).with_name("ui_adapter.py"))
        ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ui)
        owner = object.__new__(ui.UIAdapter)
        owner._held = True
        def fail(command):
            raise ui.c.Rejected("POSTCONDITION_FAILED")
        owner._dispatch_checked = fail
        queue = ui.queue_module.CommandQueue(owner._dispatch)
        queue.submit(command())
        with self.assertRaisesRegex(RuntimeError, "NATIVE_OWNER_HELD"):
            queue.tick()
        self.assertEqual(queue.result("create-one")["state"], "HELD")

    def test_ui_no_effect_rejection_remains_rejected(self):
        spec = importlib.util.spec_from_file_location("gt04_ui_reject_test", Path(q.__file__).with_name("ui_adapter.py"))
        ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ui)
        owner = object.__new__(ui.UIAdapter)
        owner._held = False
        def fail(command):
            raise ui.c.Rejected("STALE_REVISION")
        owner._dispatch_checked = fail
        queue = ui.queue_module.CommandQueue(owner._dispatch)
        queue.submit(command())
        queue.tick()
        self.assertEqual(queue.result("create-one")["state"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
