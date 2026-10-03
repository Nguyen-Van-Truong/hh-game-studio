"""Meaningful rejection checks for mixed-task or forged terminal closeout."""
import copy
import json
import unittest
import verify_terminal_supplement as verifier


class TerminalBindingTests(unittest.TestCase):
    def setUp(self):
        self.call = verifier.read(verifier.RAW/'tool-call.json')
        self.result = verifier.read(verifier.RAW/'tool-result.json')
        root = verifier.SUPERVISOR
        self.args = [verifier.read(root/name) for name in
                     ('request.json', 'start.json', 'task-start.json', 'task-deleted.json')]
        self.request_sha = verifier.sha(root/'request.json')

    def validate(self):
        return verifier.validate(self.call, self.result, *self.args, self.request_sha)

    def change_status(self, **updates):
        item = self.result['payload']['output'][1]
        tool = json.loads(item['text'])
        status = json.loads(tool['output'])
        status.update(updates)
        tool['output'] = json.dumps(status)
        item['text'] = json.dumps(tool)

    def test_original_task_observation_joins_exact_request_and_launch(self):
        status = self.validate()
        self.assertEqual(status['campaign_id'], 'gt06-o4-formal-25')
        self.assertEqual(status['last_task_result'], 0)

    def test_successful_quiet_chain_cannot_replace_formal_receipt(self):
        self.change_status(campaign_id='gt06-o9-chain-f25-r01',
                           task_path='\\HHStudio.GT06.gt06-o9-chain-f25-r01')
        with self.assertRaisesRegex(ValueError, 'CAMPAIGN_BINDING'):
            self.validate()

    def test_running_failed_or_nonempty_instances_are_not_terminal_success(self):
        original = copy.deepcopy(self.result)
        for changed in ({'state': 4}, {'last_task_result': 267009}, {'last_task_result': True},
                        {'instances': [{'state': 4}]}):
            self.result = copy.deepcopy(original)
            self.change_status(**changed)
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'TERMINAL_RESULT'):
                self.validate()

    def test_unrelated_tool_call_cannot_be_spliced(self):
        self.result['payload']['call_id'] += '-other'
        with self.assertRaisesRegex(ValueError, 'CALL_ID_BINDING'):
            self.validate()

    def test_failed_status_command_cannot_supply_successful_scheduler_fields(self):
        item = self.result['payload']['output'][1]
        tool = json.loads(item['text'])
        tool['exit_code'] = 1
        item['text'] = json.dumps(tool)
        with self.assertRaisesRegex(ValueError, 'STATUS_QUERY_EXIT'):
            self.validate()

    def test_query_for_another_task_is_rejected(self):
        self.call['payload']['input'] = self.call['payload']['input'].replace(
            '-CampaignId gt06-o4-formal-25', '-CampaignId gt06-o4-formal-24')
        with self.assertRaisesRegex(ValueError, 'STATUS_COMMAND_BINDING'):
            self.validate()

    def test_observation_after_deletion_cannot_prove_predelete_terminal_state(self):
        self.result['timestamp'] = '2026-10-03T11:09:00Z'
        with self.assertRaisesRegex(ValueError, 'TERMINAL_TIME_BINDING'):
            self.validate()

    def test_changed_request_or_pid_does_not_bind_to_formal_launch(self):
        original = copy.deepcopy(self.args)
        for key, value in (('request_sha256', '0'*64), ('pid', 39364)):
            self.args = copy.deepcopy(original)
            self.args[1][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'START_BINDING'):
                self.validate()

    def test_another_launch_or_output_directory_is_rejected(self):
        original = copy.deepcopy(self.result)
        for changes, code in (({'launch_number': 2}, 'LAUNCH_BINDING'),
                              ({'output_directory': str(verifier.RAW)}, 'OUTPUT_BINDING'),
                              ({'last_run_time': '2026-10-03T15:41:12'}, 'LAST_RUN_BINDING')):
            self.result = copy.deepcopy(original)
            self.change_status(**changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, code):
                self.validate()


if __name__ == '__main__':
    unittest.main()
