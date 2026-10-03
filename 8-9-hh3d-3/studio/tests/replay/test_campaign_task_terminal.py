"""Inert Scheduler fakes verify append-only terminal archival before deletion."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
LAUNCHER = Path(__file__).with_name('campaign_task.ps1')


FIXTURE = r'''
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:HH_TEST_LAUNCHER, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'LAUNCHER_PARSE_ERROR' }
foreach ($name in @('Require', 'Assert-PlainPath', 'Hash-File', 'Hash-Text', 'Write-NewText',
    'Write-NewJson', 'Read-Json', 'Sid-Of', 'Action-Arguments', 'Assert-Definition', 'Assert-Request',
    'Get-OwnTask', 'Get-TaskStatus', 'Assert-DeletionBinding', 'Assert-TerminalStatus', 'Remove-VerifiedTask')) {
    $fn = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $name}, $false)
    if ($null -eq $fn) { throw 'LAUNCHER_FUNCTION_MISSING' }
    . ([scriptblock]::Create($fn.Extent.Text))
}
# Only function ASTs execute. The real launcher COM/registration body never runs.
$CampaignId = 'gt06-inert-terminal'; $Mode = 'campaign'; $LaunchNumber = 2
$taskName = 'HHStudio.GT06.' + $CampaignId + '-launch-02'
$userSid = 'S-1-5-21-123-456-789-1001'
$studio = $env:HH_TEST_TEMP
$outputDirectory = Join-Path $studio 'output'
$null = New-Item -ItemType Directory -Path $outputDirectory
$scriptPath = Join-Path $studio 'inert-script.py'
$pythonPath = Join-Path $studio 'inert-python.exe'
$pythonwPath = Join-Path $studio 'inert-pythonw.exe'
foreach ($path in @($scriptPath, $pythonPath, $pythonwPath)) { Write-NewText $path 'inert: never executed' }
$requestPath = Join-Path $outputDirectory 'request.json'
$xmlPath = Join-Path $outputDirectory 'task-definition.xml'
$terminalPath = Join-Path $outputDirectory 'task-terminal.json'
$deletedPath = Join-Path $outputDirectory 'task-deleted.json'
$request = [ordered]@{schema='HH-GT06-TASK-REQUEST-1'; campaign_id=$CampaignId; mode=$Mode; launch_number=$LaunchNumber
    script_sha256=(Hash-File $scriptPath); python_sha256=(Hash-File $pythonPath); pythonw_sha256=(Hash-File $pythonwPath)}
Write-NewJson $requestPath $request
Assert-Request (Read-Json $requestPath)
$xml = '<Task>inert verified definition</Task>'
Write-NewText $xmlPath $xml
$registration = [pscustomobject]@{request_sha256=(Hash-File $requestPath); task_definition_sha256=(Hash-File $xmlPath)}
$action = [pscustomobject]@{Type=0; Id='campaign-supervisor'; Path=$pythonwPath
    Arguments=(Action-Arguments $Mode); WorkingDirectory=$studio}
$actions = [pscustomobject]@{Count=1; Context='HHStudioCurrentUser'; Action=$action}
$actions | Add-Member ScriptMethod Item {param($number) if ($number -ne 1) { throw 'INERT_ACTION_INDEX' }; return $this.Action}
$settings = [pscustomobject]@{Compatibility=2; ExecutionTimeLimit='PT24H'; Enabled=$true; AllowDemandStart=$true
    AllowHardTerminate=$true; MultipleInstances=2; RestartCount=0; Priority=6; Hidden=$false
    StartWhenAvailable=$false; WakeToRun=$false; RunOnlyIfIdle=$false; RunOnlyIfNetworkAvailable=$false
    DisallowStartIfOnBatteries=$false; StopIfGoingOnBatteries=$false
    IdleSettings=[pscustomobject]@{StopOnIdleEnd=$false; RestartOnIdle=$false}}
$definition = [pscustomobject]@{Principal=[pscustomobject]@{UserId=$userSid; LogonType=3; RunLevel=0; Id='HHStudioCurrentUser'}
    Actions=$actions; Triggers=@(); Settings=$settings}
$task = [pscustomobject]@{Path=('\'+$taskName); Definition=$definition; Xml=$xml; State=3
    LastRunTime=[DateTime]::Parse('2026-10-03T12:34:56.0000000Z').ToUniversalTime()
    LastTaskResult=[long]0; Instances=@()}
$task | Add-Member ScriptMethod GetInstances {param($flags) return ,$this.Instances}
$folder = [pscustomobject]@{Task=$task; DeleteCalls=0; GetCalls=0; DeleteBehavior='normal'
    ChangeAtGet=0; ChangeKind='queued'; TerminalAtDelete=$null; TerminalHashAtDelete=$null}
$folder | Add-Member ScriptMethod GetTask {
    param($name)
    if ($name -cne $taskName) { throw 'INERT_TASK_NAME' }
    $this.GetCalls++
    if ($this.GetCalls -eq $this.ChangeAtGet -and $null -ne $this.Task) {
        if ($this.ChangeKind -eq 'queued') { $this.Task.State = 2 }
        elseif ($this.ChangeKind -eq 'xml') { $this.Task.Xml = '<Task>changed live task</Task>' }
        elseif ($this.ChangeKind -eq 'result') { $this.Task.LastTaskResult = [long]17 }
    }
    if ($null -eq $this.Task) { throw (New-Object System.IO.FileNotFoundException('inert task absent')) }
    return $this.Task
}
$folder | Add-Member ScriptMethod DeleteTask {
    param($name, $flags)
    if ($name -cne $taskName -or $flags -ne 0) { throw 'INERT_DELETE_BINDING' }
    $this.DeleteCalls++
    $this.TerminalAtDelete = Read-Json $terminalPath
    $this.TerminalHashAtDelete = Hash-File $terminalPath
    if ($this.DeleteBehavior -eq 'throw-before') { throw 'INERT_DELETE_BEFORE' }
    if ($this.DeleteBehavior -eq 'retain') { return }
    $this.Task = $null
    if ($this.DeleteBehavior -eq 'throw-after') { throw 'INERT_DELETE_AFTER' }
}
function Attempt-Delete {
    $answer = $null; $problem = $null
    try { $answer = Remove-VerifiedTask $folder $registration }
    catch { $problem = $_.Exception.Message }
    return [pscustomobject]@{error=$problem; answer=$answer}
}
function Saved-Bytes([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return [Convert]::ToBase64String([IO.File]::ReadAllBytes($Path))
}
function Saved-Json([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return Read-Json $Path
}
function Report($Attempt) {
    return [ordered]@{error=$Attempt.error; answer=$Attempt.answer; delete_calls=$folder.DeleteCalls
        task_present=($null -ne $folder.Task); terminal=(Saved-Json $terminalPath); deleted=(Saved-Json $deletedPath)
        terminal_bytes=(Saved-Bytes $terminalPath); deleted_bytes=(Saved-Bytes $deletedPath)
        delete_observation=$folder.TerminalAtDelete; delete_terminal_sha256=$folder.TerminalHashAtDelete}
}
'''


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell launcher functions')
class TerminalArchivalTests(unittest.TestCase):
    def run_case(self, scenario):
        with tempfile.TemporaryDirectory(prefix='hh-terminal-inert-') as directory:
            environment = {**os.environ, 'HH_TEST_TEMP': directory, 'HH_TEST_LAUNCHER': str(LAUNCHER)}
            powershell = Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command',
                                     FIXTURE + '\n' + scenario], capture_output=True, timeout=20,
                                    env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual(result.stderr, b'')
            return json.loads(result.stdout.decode('utf-8-sig'))

    def assert_receipt_join(self, result):
        terminal_raw = base64.b64decode(result['terminal_bytes'])
        digest = hashlib.sha256(terminal_raw).hexdigest()
        self.assertEqual(result['deleted']['terminal_status_sha256'], digest)
        self.assertEqual(result['delete_terminal_sha256'], digest)
        self.assertEqual(result['deleted']['terminal_status_file'], 'task-terminal.json')
        self.assertEqual(result['deleted']['request_sha256'], result['terminal']['request_sha256'])
        self.assertEqual(result['deleted']['task_definition_sha256'], result['terminal']['task_definition_sha256'])
        self.assertFalse(result['deleted']['formal_acceptance'])

    def test_success_and_failed_scheduler_results_archive_exact_status_before_delete(self):
        for state, exit_value in [(3, 0), (1, 2147942405)]:
            with self.subTest(state=state, scheduler_result=exit_value):
                result = self.run_case(f'''
$task.State = {state}; $task.LastTaskResult = [long]{exit_value}
$expected = Get-TaskStatus $task $registration
$attempt = Attempt-Delete
$report = Report $attempt; $report['expected'] = $expected
$report | ConvertTo-Json -Depth 12 -Compress
''')
                self.assertIsNone(result['error'])
                self.assertEqual(result['delete_calls'], 1)
                self.assertFalse(result['task_present'])
                self.assertEqual(result['terminal'], result['expected'])
                self.assertEqual(result['delete_observation'], result['expected'])
                self.assertEqual(result['terminal']['last_task_result'], exit_value)
                self.assertEqual(result['terminal']['state'], state)
                self.assertEqual(result['terminal']['instances'], [])
                self.assertEqual(result['terminal']['campaign_id'], 'gt06-inert-terminal')
                self.assertEqual(result['terminal']['launch_number'], 2)
                self.assertEqual(result['terminal']['mode'], 'campaign')
                self.assertEqual(result['terminal']['task_path'], '\\HHStudio.GT06.gt06-inert-terminal-launch-02')
                self.assertFalse(result['terminal']['formal_acceptance'])
                self.assert_receipt_join(result)

    def test_running_queued_unknown_and_instances_refuse_deletion_without_archival(self):
        for state, instances in [(4, False), (2, False), (0, False), (3, True)]:
            with self.subTest(state=state, instances=instances):
                result = self.run_case(f'''
$task.State = {state}
''' + (r'''
$task.Instances = @([pscustomobject]@{InstanceGuid='inert'; State=4; EnginePID=123})
''' if instances else '') + r'''
Report (Attempt-Delete) | ConvertTo-Json -Depth 12 -Compress
''')
                self.assertIn('DELETE_REFUSED_USE_STOP_REQUEST', result['error'])
                self.assertEqual(result['delete_calls'], 0)
                self.assertTrue(result['task_present'])
                self.assertIsNone(result['terminal'])
                self.assertIsNone(result['deleted'])

    def test_durable_write_failure_never_calls_delete(self):
        result = self.run_case(r'''
function Write-NewText([string]$Path, [string]$Value) { throw 'INERT_WRITE_FAIL' }
Report (Attempt-Delete) | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertEqual(result['error'], 'INERT_WRITE_FAIL')
        self.assertEqual(result['delete_calls'], 0)
        self.assertTrue(result['task_present'])
        self.assertIsNone(result['terminal'])
        self.assertIsNone(result['deleted'])

    def test_durable_readback_failure_never_calls_delete_and_preserves_written_bytes(self):
        result = self.run_case(r'''
$originalHash = ${function:Hash-File}
function Hash-File([string]$Path) {
    if ($Path -ceq $terminalPath) { return ('0' * 64) }
    return (& $originalHash $Path)
}
$attempt = Attempt-Delete
Set-Item -LiteralPath Function:Hash-File -Value $originalHash
Report $attempt | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertEqual(result['error'], 'TASK_WRITE_READBACK')
        self.assertEqual(result['delete_calls'], 0)
        self.assertTrue(result['task_present'])
        self.assertIsNotNone(result['terminal_bytes'])
        self.assertIsNone(result['deleted'])

    def test_retry_after_uncertain_delete_reuses_terminal_without_overwriting_history(self):
        result = self.run_case(r'''
$folder.DeleteBehavior = 'throw-before'
$first = Attempt-Delete; $before = Saved-Bytes $terminalPath
$folder.DeleteBehavior = 'normal'
$second = Attempt-Delete; $deletedBefore = Saved-Bytes $deletedPath
$third = Attempt-Delete
$report = Report $third
$report['first_error'] = $first.error; $report['second_error'] = $second.error
$report['terminal_unchanged'] = ($before -ceq (Saved-Bytes $terminalPath))
$report['deleted_unchanged'] = ($deletedBefore -ceq (Saved-Bytes $deletedPath))
$report | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertIn('INERT_DELETE_BEFORE', result['first_error'])
        self.assertIsNone(result['second_error'])
        self.assertIsNone(result['error'])
        self.assertEqual(result['delete_calls'], 2)
        self.assertTrue(result['terminal_unchanged'])
        self.assertTrue(result['deleted_unchanged'])
        self.assert_receipt_join(result)

    def test_lost_delete_reply_reconciles_absence_without_second_delete(self):
        result = self.run_case(r'''
$folder.DeleteBehavior = 'throw-after'
$first = Attempt-Delete; $before = Saved-Bytes $terminalPath
$deletedAfterFailure = Saved-Bytes $deletedPath
$second = Attempt-Delete
$report = Report $second; $report['first_error'] = $first.error
$report['deleted_after_failure'] = $deletedAfterFailure
$report['terminal_unchanged'] = ($before -ceq (Saved-Bytes $terminalPath))
$report | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertIn('INERT_DELETE_AFTER', result['first_error'])
        self.assertIsNone(result['deleted_after_failure'])
        self.assertIsNone(result['error'])
        self.assertEqual(result['delete_calls'], 1)
        self.assertFalse(result['task_present'])
        self.assertTrue(result['terminal_unchanged'])
        self.assert_receipt_join(result)

    def test_old_terminal_rejects_changed_request_or_xml_binding_on_retry(self):
        for mutation in ('request', 'xml'):
            with self.subTest(binding=mutation):
                change = r'''
$changed = Read-Json $requestPath; $changed.python_sha256 = ('c' * 64)
[IO.File]::WriteAllText($requestPath, (($changed | ConvertTo-Json -Depth 12) + "`n"), $utf8)
$registration.request_sha256 = Hash-File $requestPath
''' if mutation == 'request' else r'''
$task.Xml = '<Task>different binding</Task>'
[IO.File]::WriteAllText($xmlPath, $task.Xml, $utf8)
$registration.task_definition_sha256 = Hash-File $xmlPath
'''
                result = self.run_case(r'''
$folder.DeleteBehavior = 'throw-before'
$first = Attempt-Delete; $before = Saved-Bytes $terminalPath
''' + change + r'''
$folder.DeleteBehavior = 'normal'
$second = Attempt-Delete
$report = Report $second; $report['terminal_unchanged'] = ($before -ceq (Saved-Bytes $terminalPath))
$report | ConvertTo-Json -Depth 12 -Compress
''')
                self.assertEqual(result['error'], 'TASK_TERMINAL_RECEIPT_BINDING')
                self.assertEqual(result['delete_calls'], 1)
                self.assertTrue(result['task_present'])
                self.assertTrue(result['terminal_unchanged'])
                self.assertIsNone(result['deleted'])

    def test_changed_terminal_observation_is_rejected_and_never_rewritten(self):
        result = self.run_case(r'''
$folder.DeleteBehavior = 'throw-before'; $null = Attempt-Delete
$changed = Read-Json $terminalPath; $changed.last_task_result = 17
[IO.File]::WriteAllText($terminalPath, (($changed | ConvertTo-Json -Depth 12) + "`n"), $utf8)
$changedBytes = Saved-Bytes $terminalPath; $folder.DeleteBehavior = 'normal'
$attempt = Attempt-Delete
$report = Report $attempt; $report['changed_bytes_preserved'] = ($changedBytes -ceq (Saved-Bytes $terminalPath))
$report | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertEqual(result['error'], 'TASK_TERMINAL_RECEIPT_CHANGED')
        self.assertEqual(result['delete_calls'], 1)
        self.assertTrue(result['task_present'])
        self.assertTrue(result['changed_bytes_preserved'])
        self.assertEqual(result['terminal']['last_task_result'], 17)
        self.assertIsNone(result['deleted'])

    def test_live_task_is_rechecked_after_archival_before_delete(self):
        for kind, error in [('queued', 'TASK_NONTERMINAL_DELETE_REFUSED_USE_STOP_REQUEST'),
                            ('xml', 'TASK_XML_CHANGED'), ('result', 'TASK_TERMINAL_RECEIPT_CHANGED')]:
            with self.subTest(change=kind):
                result = self.run_case(f'''
$folder.ChangeAtGet = 2; $folder.ChangeKind = '{kind}'
Report (Attempt-Delete) | ConvertTo-Json -Depth 12 -Compress
''')
                self.assertEqual(result['error'], error)
                self.assertEqual(result['delete_calls'], 0)
                self.assertTrue(result['task_present'])
                self.assertEqual(result['terminal']['state'], 3)
                self.assertEqual(result['terminal']['last_task_result'], 0)
                self.assertIsNone(result['deleted'])

    def test_unproven_delete_keeps_terminal_and_does_not_issue_deleted_receipt(self):
        result = self.run_case(r'''
$folder.DeleteBehavior = 'retain'
Report (Attempt-Delete) | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertEqual(result['error'], 'TASK_DELETE_UNPROVEN')
        self.assertEqual(result['delete_calls'], 1)
        self.assertTrue(result['task_present'])
        self.assertIsNotNone(result['terminal'])
        self.assertIsNone(result['deleted'])

    def test_existing_deleted_receipt_must_bind_retained_terminal_hash(self):
        result = self.run_case(r'''
$null = Attempt-Delete
$changed = Read-Json $deletedPath; $changed.terminal_status_sha256 = ('0' * 64)
[IO.File]::WriteAllText($deletedPath, (($changed | ConvertTo-Json -Depth 12) + "`n"), $utf8)
$changedBytes = Saved-Bytes $deletedPath
$report = Report (Attempt-Delete)
$report['changed_bytes_preserved'] = ($changedBytes -ceq (Saved-Bytes $deletedPath))
$report | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertEqual(result['error'], 'TASK_DELETED_RECEIPT_BINDING')
        self.assertEqual(result['delete_calls'], 1)
        self.assertFalse(result['task_present'])
        self.assertTrue(result['changed_bytes_preserved'])

    def test_deleted_identity_cannot_be_reused_to_delete_a_recreated_task(self):
        result = self.run_case(r'''
$null = Attempt-Delete
$before = Saved-Bytes $terminalPath; $deletedBefore = Saved-Bytes $deletedPath
$folder.Task = $task
$report = Report (Attempt-Delete)
$report['terminal_unchanged'] = ($before -ceq (Saved-Bytes $terminalPath))
$report['deleted_unchanged'] = ($deletedBefore -ceq (Saved-Bytes $deletedPath))
$report | ConvertTo-Json -Depth 12 -Compress
''')
        self.assertEqual(result['error'], 'TASK_DELETED_BINDING_REUSED')
        self.assertEqual(result['delete_calls'], 1)
        self.assertTrue(result['task_present'])
        self.assertTrue(result['terminal_unchanged'])
        self.assertTrue(result['deleted_unchanged'])


if __name__ == '__main__':
    unittest.main()
