"""Native Windows v4 storage/selection; editor/auth facts are synthetic.

These cases deliberately launch no engine and do not establish a public ACK.
The real publication owner must verify actual registered observations first.
"""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


fixtures=load('gt03_v4_native_fixtures',Path(__file__).with_name('test_publication_state_v4.py'))
legacy=load('gt03_v4_native_cleanup',Path(__file__).with_name('test_publication_journal.py'))
journal,state,codec=fixtures.journal,fixtures.state,fixtures.codec
from studio.protocol.core import parse_json,canonical_bytes,ValidationError
from studio.host.core.custody_registry import RegistryCustody


def now(owner=None):
    return max(time.time_ns()//1_000_000,0 if owner is None else owner._state.snapshot()['last_observed_ms'])


@unittest.skipUnless(os.name=='nt','actual Windows protected roots and Registry required')
class JournalV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):RegistryCustody.provision_base()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-gt03-journal-')
        self.base=Path(self.temp.name).resolve();self.storage_id,self.owners=uuid.uuid4().hex,[]
        self.addCleanup(lambda:legacy.PublicationJournalTests.cleanup(self))

    def create(self):
        config=fixtures.configuration()
        for key in ('initial','content_root_identity'):del config[key]
        config['observed_ms']=now()
        try:owner=journal.PublicationJournalV4.create(self.base,storage_id=self.storage_id,config=config,initial_bundle=fixtures.bundle())
        except journal.PublicationJournalV4Error as exc:
            if exc.cleanup_owner is not None:self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner);return owner

    def reopen(self):
        try:owner=journal.PublicationJournalV4.reopen(self.storage_id,project_id='v4-journal-test')
        except journal.PublicationJournalV4Error as exc:
            if exc.cleanup_owner is not None:self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner);return owner

    def command(self,owner):return state.lookup(owner._state,'command.one')

    def capture(self,owner,operation='script_text.replace'):
        proposed=fixtures.prepared(owner._state,operation,at=now(owner))
        owner.capture_prepared('command.one',fixtures.rev('command.one'),operation=operation,
            script_change=proposed['script_change'],expected_revision=proposed['before_scene_revision'],
            editor=proposed['editor'],editor_generation=1,root_instance_id=1,admission=proposed['admission'],
            scratch_name=proposed['scratch_name'],observed_ms=proposed['observed_ms'])
        t=now(owner);owner.captured('command.one',fixtures.rev('command.one'),fixtures.capture_facts(self.command(owner),t),observed_ms=t)
        return fixtures.bundle('captured-scene',script='replacement-script' if operation=='script_text.replace' else 'initial-script',
                               revision='replacement-state' if operation=='script_text.replace' else 'captured-state')

    def validated(self,owner,operation='script_text.replace'):
        value=self.capture(owner,operation);before={p.name for p in owner._files.root.iterdir()}
        owner.prepare('command.one',fixtures.rev('command.one'),value,observed_ms=now(owner))
        self.assertEqual(before,{p.name for p in owner._files.root.iterdir()})
        owner.stage_prepared('command.one',fixtures.rev('command.one'),observed_ms=now(owner))
        self.assertEqual(len({p.name for p in owner._files.root.iterdir()}-before),12)
        t=now(owner);owner.validated('command.one',fixtures.rev('command.one'),fixtures.validation_facts(self.command(owner),t),observed_ms=t)
        return value

    def retire_intent(self,owner):
        c=self.command(owner);t=now(owner)
        owner.retire_prepared('command.one',fixtures.rev('command.one'),current=state.activation_current(c['capture_prepared']),
            retirement_intent_id='retire-intent',deadline_ms=t+10000,observed_ms=t)

    def activate(self,owner,operation='script_text.replace'):
        value=self.validated(owner,operation)
        if operation=='script_text.replace':
            self.retire_intent(owner);t=now(owner)
            owner.retired('command.one',fixtures.rev('command.one'),fixtures.retirement_facts(self.command(owner),t),observed_ms=t)
        current=state.activation_current(self.command(owner)['capture_prepared'])
        owner.prepare_activation('command.one',fixtures.rev('command.one'),current=current,observed_ms=now(owner))
        return value

    def test_script_whole_bundle_cas_exact_response_then_readonly_reopen(self):
        owner=self.create();old=owner.selection_facts();value=self.activate(owner)
        owner.select_prepared('command.one',fixtures.rev('command.one'),observed_ms=now(owner))
        selected=owner.selection_facts();self.assertNotEqual(old['selector_version']['file_id'],selected['selector_version']['file_id'])
        self.assertEqual(owner.read_selected_bundle(),value)
        t=now(owner);owner.readback('command.one',fixtures.rev('command.one'),fixtures.adoption_facts(self.command(owner),t),observed_ms=t)
        result=owner.commit('command.one',fixtures.rev('command.one'),observed_ms=now(owner))
        response=owner.lookup_response('command.one',fixtures.rev('command.one'))
        self.assertEqual(response,canonical_bytes(result['response']))
        self.assertEqual(parse_json(response)['code'],'GODOT_MANAGED_SCRIPT_REPLACED')
        self.assertIs(result['public_ack'],False);self.assertIs(result['engine_effects_verified'],False)
        head=owner._head;self.assertEqual(owner.commit('command.one',fixtures.rev('command.one'),observed_ms=now(owner)),result)
        self.assertEqual(owner._head,head)
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.lookup_response('command.one',fixtures.rev('command.one')),response)
        self.assertEqual(reopened.read_selected_bundle(),value);self.assertEqual(reopened.selection_facts(),selected)
        with self.assertRaisesRegex(journal.PublicationJournalV4Error,'READ_ONLY'):
            reopened.commit('command.one',fixtures.rev('command.one'),observed_ms=now(reopened))
        with self.assertRaises(ValidationError):reopened.lookup_response('command.one',fixtures.rev('changed'))
        with self.assertRaises(journal.PublicationJournalV4Error):journal.base.PublicationJournalV3.reopen(self.storage_id,project_id='v4-journal-test')

    def test_save_uses_same_native_chain_with_preserved_script_and_original_response(self):
        owner=self.create();value=self.activate(owner,'scene.save')
        owner.select_prepared('command.one',fixtures.rev('command.one'),observed_ms=now(owner))
        t=now(owner);owner.readback('command.one',fixtures.rev('command.one'),fixtures.adoption_facts(self.command(owner),t),observed_ms=t)
        owner.commit('command.one',fixtures.rev('command.one'),observed_ms=now(owner))
        response=owner.lookup_response('command.one',fixtures.rev('command.one'))
        self.assertEqual(parse_json(response)['code'],'GODOT_MANAGED_SCENE_SAVED')
        self.assertEqual(owner.read_selected_bundle().files[codec.SCRIPT_PATH],b'initial-script')
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.read_selected_bundle(),value);self.assertEqual(reopened.lookup_response('command.one',fixtures.rev('command.one')),response)

    def test_wrong_script_delta_rejected_before_native_stage(self):
        owner=self.create();self.capture(owner);head=owner._head;before={p.name for p in owner._files.root.iterdir()}
        bad=fixtures.bundle('captured-scene',script='different-script',revision='replacement-state')
        with self.assertRaises(ValidationError):owner.prepare('command.one',fixtures.rev('command.one'),bad,observed_ms=now(owner))
        self.assertEqual(owner._head,head);self.assertEqual(before,{p.name for p in owner._files.root.iterdir()})
        self.assertEqual(owner.lookup('command.one')['phase'],'CAPTURED')

    def test_failed_retirement_cannot_select_stop_is_durable_unknown(self):
        owner=self.create();old=owner.selection_facts();self.validated(owner);self.retire_intent(owner)
        t=now(owner);bad=fixtures.retirement_facts(self.command(owner),t);bad['job_closed']=False;head=owner._head
        with self.assertRaises(ValidationError):owner.retired('command.one',fixtures.rev('command.one'),bad,observed_ms=t)
        self.assertEqual(owner._head,head)
        current=state.activation_current(self.command(owner)['capture_prepared'])
        with self.assertRaises(journal.PublicationJournalV4Error):owner.prepare_activation('command.one',fixtures.rev('command.one'),current=current,observed_ms=now(owner))
        owner.stop(reason='user-stop',observed_ms=now(owner))
        response=owner.lookup_response('command.one',fixtures.rev('command.one'))
        self.assertEqual(parse_json(response)['status'],'UNKNOWN');self.assertEqual(owner.selection_facts(),old)
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.lookup_response('command.one',fixtures.rev('command.one')),response)
        self.assertEqual(reopened.selection_facts(),old);self.assertIs(reopened.snapshot()['stopped'],True)

    def test_after_real_cas_loss_holds_without_terminal_ack(self):
        owner=self.create();self.activate(owner);actual=owner._store.select
        def lose_return(intent):
            actual(intent)
            raise OSError('injected return loss after actual selector CAS')
        with mock.patch.object(owner._store,'select',side_effect=lose_return):
            with self.assertRaises(journal.PublicationJournalV4Error) as raised:
                owner.select_prepared('command.one',fixtures.rev('command.one'),observed_ms=now(owner))
        self.assertTrue(raised.exception.outcome_unknown);self.assertIs(raised.exception.cleanup_owner,owner)
        self.assertEqual(self.command(owner)['phase'],'ACTIVATING')
        owner.close()
        with self.assertRaises(journal.PublicationJournalV4Error):self.reopen()


if __name__=='__main__':unittest.main(verbosity=2)
