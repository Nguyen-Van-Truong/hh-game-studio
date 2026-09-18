"""Coherent inspection with inert native boundaries; not Windows evidence."""
import copy
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('recovery_inspection_fixtures',STUDIO/'tests/godot/test_publication_recovery.py')
fixtures=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fixtures;spec.loader.exec_module(fixtures)
recovery=fixtures.recovery


@dataclass(frozen=True)
class InertHead:
    sequence:int=20
    sha256:str='1'*64
    size:int=3000


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.publication,self.snapshot,self.command=fixtures.material('scene.save','COMMITTED')
        self.selected=copy.deepcopy(self.snapshot['selected'])
        self.recovered={'attempts':[],'stopped':False,'held':False,'blocked_original_commands':[]}
        self.bundle=object()
        self.owner=object.__new__(recovery.RecoveryJournal)
        self.owner._mutex=threading.RLock();self.owner._closed=self.owner._held=False
        self.owner._head=InertHead();self.owner._events=self.publication.events
        self.owner._storage_id='a'*32;self.owner._project_id=self.snapshot['project_id']
        self.owner._expected_source=self.snapshot['source_closure_sha256']
        self.owner._verify_owners=mock.Mock();self.owner._read_unbound=mock.Mock(return_value=())
        self.owner._validate_view=mock.Mock(return_value=(self.publication,self.recovered,
            self.publication.events,self.selected,self.bundle))
        self.digest=fixtures.fixtures.rev('command.one')

    def inspect(self,digest=None):return self.owner.inspect_command('command.one',digest or self.digest)

    def test_single_native_pass_yields_coherent_detached_command_selection_and_head(self):
        snapshot,command,bundle,context=self.inspect()
        self.owner._read_unbound.assert_called_once();self.owner._validate_view.assert_called_once()
        self.assertIs(bundle,self.bundle);self.assertEqual(command,self.command)
        self.assertEqual(snapshot['selected'],context['selected'])
        self.assertEqual(context['native_head']['sequence'],20)
        snapshot['selected']['selector_version']['file_id']='f'*32
        context['selected']['selector_version']['file_id']='e'*32
        command['phase']='UNKNOWN'
        fresh=self.inspect()
        self.assertEqual(fresh[0]['selected'],self.selected)
        self.assertEqual(fresh[1]['phase'],'COMMITTED')
        self.assertEqual(self.owner._read_unbound.call_count,2)

    def test_changed_native_owner_and_next_fold_failure_cannot_reuse_previous_view(self):
        for boundary in ('_verify_owners','_validate_view'):
            with self.subTest(boundary=boundary):
                self.inspect()
                method=getattr(self.owner,boundary)
                method.side_effect=recovery.RecoveryError('native.changed')
                with self.assertRaisesRegex(recovery.RecoveryError,'native.changed'):self.inspect()
                method.side_effect=None

    def test_unexpected_native_history_and_digest_conflict_reject(self):
        self.owner._events=(*self.publication.events,b'{}')
        with self.assertRaisesRegex(recovery.RecoveryError,'HISTORY_CHANGED'):self.inspect()
        self.owner._events=self.publication.events
        with self.assertRaisesRegex(ValueError,'CONFLICT'):self.inspect('sha256:'+'0'*64)

    def test_fresh_stop_and_higher_recovery_epoch_are_visible(self):
        self.inspect()
        self.recovered.update(stopped=True,held=True,attempts=[{'admission':{'authority_epoch':42}}])
        snapshot,command,bundle,context=self.inspect()
        self.assertIs(snapshot['stopped'],True)
        self.assertEqual(context['minimum_authority_epoch'],42)
        self.assertEqual(command,self.command)


if __name__=='__main__':unittest.main(verbosity=2)
