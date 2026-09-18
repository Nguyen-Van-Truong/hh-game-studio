"""Actual Windows private blobs/log/custody; all editor facts remain synthetic."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


fx=load('gt03_v5_native_fixtures',Path(__file__).with_name('test_publication_state_v5.py'))
v4=load('gt03_v5_native_legacy',Path(__file__).with_name('test_publication_journal_v4.py'))
journal,state=fx.journal,fx.state
from studio.protocol.core import canonical_bytes,parse_json,ValidationError


@unittest.skipUnless(os.name=='nt','actual Windows protected roots and Registry required')
class JournalV5Tests(v4.JournalV4Tests):
    # Also execute the five inherited save/script/CAS regressions through V5.
    def create(self):
        config=fx.fx.configuration()
        for key in ('initial','content_root_identity'):del config[key]
        config['observed_ms']=v4.now()
        try:owner=journal.PublicationJournalV5.create(self.base,storage_id=self.storage_id,
                config=config,initial_bundle=fx.fx.bundle())
        except journal.PublicationJournalV5Error as error:
            if error.cleanup_owner is not None:self.owners.append(error.cleanup_owner)
            raise
        self.owners.append(owner);return owner

    def reopen(self):
        try:owner=journal.PublicationJournalV5.reopen(self.storage_id,project_id='v4-journal-test')
        except journal.PublicationJournalV5Error as error:
            if error.cleanup_owner is not None:self.owners.append(error.cleanup_owner)
            raise
        self.owners.append(owner);return owner

    def edit_intent(self,owner,command='edit.one'):
        proposed=fx.prepared(owner._state,at=v4.now(owner),command=command)
        return owner.edit_prepared(command,fx.fx.rev(command),operation=proposed['operation'],
            projection=fx.projection(command),expected_revision=proposed['before_scene_revision'],editor=proposed['editor'],
            editor_generation=1,root_instance_id=1,admission=proposed['admission'],scratch_name=proposed['scratch_name'],
            lease_owner=proposed['lease_owner'],observed_ms=proposed['observed_ms'])

    def edit_ready(self,owner,command='edit.one'):
        c=self.edit_intent(owner,command);t=v4.now(owner)
        captured=fx.raw_capture(c,t)
        return owner.edit_checkpoint(command,c['digest'],capture=captured,scene_bytes=fx.SCENE,observed_ms=t)

    def edit_done(self,owner,command='edit.one'):
        c=self.edit_ready(owner,command);t=v4.now(owner)
        return owner.edit_committed(command,c['digest'],observation=fx.raw_edit(c,t),observed_ms=t)

    def test_native_edit_checkpoint_response_dedupe_and_readonly_reopen(self):
        owner=self.create();selection=owner.selection_facts();bundle=owner.read_selected_bundle()
        before=owner._head;c=self.edit_intent(owner)
        self.assertGreater(owner._head.sequence,before.sequence)
        self.assertEqual(list(owner._blobs.root.glob('blob-*')),[])
        t=v4.now(owner);c=owner.edit_checkpoint('edit.one',c['digest'],capture=fx.raw_capture(c,t),scene_bytes=fx.SCENE,observed_ms=t)
        self.assertEqual(len(list(owner._blobs.root.glob('blob-*'))),2)
        self.assertEqual(owner.checkpoint_bytes('edit.one',c['digest']),fx.SCENE)
        t=v4.now(owner);observation=fx.raw_edit(c,t)
        result=owner.edit_committed('edit.one',c['digest'],observation=observation,observed_ms=t)
        response=owner.lookup_response('edit.one',c['digest']);head=owner._head
        self.assertEqual(len(list(owner._blobs.root.glob('blob-*'))),3)
        self.assertEqual(response,canonical_bytes(result['response']))
        self.assertIs(parse_json(response)['postconditions']['files_saved'],False)
        self.assertEqual(owner.edit_committed('edit.one',c['digest'],observation=observation,observed_ms=v4.now(owner)),result)
        self.assertEqual(owner._head,head);self.assertEqual(owner.selection_facts(),selection)
        self.assertEqual(owner.read_selected_bundle(),bundle)
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.lookup_response('edit.one',c['digest']),response)
        self.assertEqual(reopened.checkpoint_bytes('edit.one',c['digest']),fx.SCENE)
        self.assertEqual(reopened.selection_facts(),selection)
        with self.assertRaisesRegex(journal.PublicationJournalV5Error,'READ_ONLY'):
            reopened.edit_committed('edit.one',c['digest'],observation=observation,observed_ms=v4.now(reopened))

    def test_invalid_checkpoint_or_projection_has_no_blob_write(self):
        owner=self.create();p=fx.projection();p['expected_generation']=True;proposed=fx.prepared(owner._state,at=v4.now(owner))
        with self.assertRaises(ValidationError):
            owner.edit_prepared('edit.one',fx.fx.rev('edit.one'),operation=proposed['operation'],projection=p,
                expected_revision=proposed['before_scene_revision'],editor=proposed['editor'],editor_generation=1,
                root_instance_id=1,admission=proposed['admission'],scratch_name=proposed['scratch_name'],
                lease_owner=proposed['lease_owner'],observed_ms=proposed['observed_ms'])
        c=self.edit_intent(owner);head=owner._head;t=v4.now(owner)
        with self.assertRaises(journal.PublicationJournalV5Error):
            owner.edit_checkpoint('edit.one',c['digest'],capture=fx.raw_capture(c,t),scene_bytes=b'changed',observed_ms=t)
        self.assertEqual(owner._head,head);self.assertEqual(list(owner._blobs.root.glob('blob-*')),[])

    def test_stop_ready_keeps_checkpoint_and_unknown_response_after_reopen(self):
        owner=self.create();selection=owner.selection_facts();c=self.edit_ready(owner)
        owner.stop(reason='user-stop',observed_ms=v4.now(owner))
        response=owner.lookup_response('edit.one',c['digest'])
        self.assertEqual(parse_json(response)['status'],'UNKNOWN')
        self.assertIs(parse_json(response)['postconditions']['public_ack'],False)
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.lookup_response('edit.one',c['digest']),response)
        self.assertEqual(reopened.checkpoint_bytes('edit.one',c['digest']),fx.SCENE)
        self.assertEqual(reopened.selection_facts(),selection)

    def test_blob_failure_retains_unknown_owner_and_intent_without_ready(self):
        owner=self.create();c=self.edit_intent(owner);t=v4.now(owner)
        with mock.patch.object(owner._blobs,'put_bytes',side_effect=OSError('injected storage failure')):
            with self.assertRaises(journal.PublicationJournalV5Error) as caught:
                owner.edit_checkpoint('edit.one',c['digest'],capture=fx.raw_capture(c,t),scene_bytes=fx.SCENE,observed_ms=t)
        self.assertTrue(caught.exception.outcome_unknown);self.assertIs(caught.exception.cleanup_owner,owner)
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.lookup('edit.one')['phase'],'EDIT_INTENT')
        with self.assertRaises(ValidationError):reopened.lookup_response('edit.one',c['digest'])

    def test_changed_checkpoint_blob_is_rejected_on_native_reopen(self):
        owner=self.create();c=self.edit_ready(owner)
        path=owner._blobs.root/c['checkpoint']['scene_blob']['object_id'];owner.close()
        path.relative_to(self.base)
        with path.open('r+b') as handle:handle.write(b'X')
        with self.assertRaises(journal.PublicationJournalV5Error):self.reopen()

    def test_mixed_edit_then_actual_save_same_custody_replays_both_responses(self):
        owner=self.create();c=self.edit_done(owner);edit_response=owner.lookup_response('edit.one',c['digest'])
        value=self.activate(owner,'scene.save');owner.select_prepared('command.one',fx.fx.rev('command.one'),observed_ms=v4.now(owner))
        t=v4.now(owner);owner.readback('command.one',fx.fx.rev('command.one'),v4.fixtures.adoption_facts(self.command(owner),t),observed_ms=t)
        owner.commit('command.one',fx.fx.rev('command.one'),observed_ms=v4.now(owner));owner.close()
        reopened=self.reopen();self.assertEqual(reopened.lookup_response('edit.one',c['digest']),edit_response)
        self.assertEqual(reopened.read_selected_bundle(),value)
        self.assertEqual(parse_json(reopened.lookup_response('command.one',fx.fx.rev('command.one')))['code'],'GODOT_MANAGED_SCENE_SAVED')


if __name__=='__main__':unittest.main(verbosity=2)
