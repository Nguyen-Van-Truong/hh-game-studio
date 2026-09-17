"""Small Tk reviewer; bounded network workers never call Tk.

The injected client owns authentication and fixed prepared context. It exposes
perform(UiAction)->ReviewerEvent with finite request deadlines. Neither URLs
nor credentials nor arbitrary logs enter this view.
"""
from dataclasses import replace
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Protocol

from .model import (EventKind, Phase, ReviewerEvent, ReviewerState, UiAction, UiCode,
                    cleanup_held, closed, enabled_actions, lane, reduce)

POLL_SECONDS = 1.0
CLOSE_SECONDS = 30.0
_MESSAGES = {
    UiCode.READY: 'Ready to run the prepared replay.', UiCode.QUEUED: 'Request queued.',
    UiCode.RUNNING: 'Replay is running.', UiCode.STOP_REQUESTED: 'Stop requested; waiting for cleanup.',
    UiCode.DRAINING: 'Stop is latched; process cleanup is still being checked.',
    UiCode.STOPPED: 'Runtime cleanup confirmed.', UiCode.COMPLETED: 'Completed replay evidence is available.',
    UiCode.REJECTED: 'Request rejected. Review the bound session and retained result.',
    UiCode.UNKNOWN: 'Outcome is unknown. Look up the same command; do not start another replay.',
    UiCode.DISCONNECTED: 'Connection lost. Reconnect checks the existing command only.',
    UiCode.LOOKUP_REQUIRED: 'Looking up the existing command.', UiCode.INSPECTION_READY: 'Retained inspection page received.',
    UiCode.CAPTURE_READY: 'Retained capture metadata received.', UiCode.INVALID_RESPONSE: 'Response was not admitted.',
    UiCode.CLIENT_ERROR: 'Client operation failed. Look up the existing command.',
    UiCode.BUSY: 'A request is already in progress.', UiCode.CLOSED: 'Reviewer closed.',
    UiCode.NO_COMMAND: 'No recorded command was found. No replay was started.',
    UiCode.CLEANUP_HELD: 'Cleanup could not be confirmed. The window remains open; Stop and lookup are available after the current cleanup call returns.'}
_NEXT = {'play': 'Play the prepared trace.', 'wait': 'Wait for a response.',
         'lookup': 'Look up the existing command.', 'stop': 'Wait or use priority Stop.',
         'review_evidence': 'Inspect completed evidence or view capture metadata.',
         'review_error': 'Review the result, then look up the same command.', 'close': 'Close the reviewer.'}


class ReviewerClient(Protocol):
    def perform(self, action: UiAction) -> ReviewerEvent: ...


class BoundedWorkers:
    """One work, one lookup and one independent Stop slot; no queued retries.

    Each slot stays occupied until its single response is consumed, so the
    three-item mailbox cannot overflow and command responses are never dropped.
    Threads are daemonized only as a last resort; close retains the UI while
    they are running and never treats a timeout as successful cleanup.
    """
    def __init__(self, client: ReviewerClient):
        self.client = client
        self._outbox = queue.Queue(maxsize=3)
        self._slots = {}
        self._lock = threading.Lock()

    def available(self, action):
        with self._lock:
            return lane(action) not in self._slots

    @property
    def active(self):
        with self._lock:
            return len(self._slots)

    def submit(self, action: UiAction, request_id: int) -> bool:
        channel = lane(action)
        with self._lock:
            if channel in self._slots:
                return False
            self._slots[channel] = request_id

        def execute():
            try:
                event = self.client.perform(action)
                if (type(event) is not ReviewerEvent or event.action is not action
                        or event.kind not in (EventKind.UPDATE, EventKind.DISCONNECTED)):
                    raise ValueError('INVALID_CLIENT_EVENT')
                event = replace(event, request_id=request_id)
            except Exception:
                # Exception strings can contain URLs, request headers or keys.
                event = ReviewerEvent(action, Phase.DISCONNECTED, UiCode.DISCONNECTED,
                                      request_id=request_id, kind=EventKind.DISCONNECTED)
            self._outbox.put_nowait((channel, event))

        thread = threading.Thread(target=execute, name='hh-reviewer-' + channel, daemon=True)
        try:
            thread.start()
        except Exception:
            self._outbox.put_nowait((channel, ReviewerEvent(action, Phase.DISCONNECTED, UiCode.CLIENT_ERROR,
                request_id=request_id, kind=EventKind.DISCONNECTED)))
        return True

    def take(self):
        result = []
        for _ in range(3):
            try:
                channel, event = self._outbox.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                self._slots.pop(channel)
            result.append(event)
        return tuple(result)


class ReviewerWindow:
    def __init__(self, root: tk.Tk, client: ReviewerClient, initial_state: ReviewerState | None = None,
                 *, on_close: Callable[[], bool] | None = None):
        self.root, self.state = root, initial_state or ReviewerState()
        self.workers = BoundedWorkers(client)
        self._on_close = on_close
        self._sequence = 0
        self._last_lookup = 0.0
        self._closing = self._destroyed = False
        self._close_deadline = 0.0
        self._cleanup_started = False
        self._cleanup_result = queue.Queue(maxsize=1)
        self._cleanup_thread = None
        self._cleanup_outcome = None
        self._progress_running = False
        root.title('HH Studio · Replay reviewer')
        root.minsize(720, 480)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-p>', lambda event: self._shortcut(UiAction.PLAY))
        root.bind('<Escape>', lambda event: self._shortcut(UiAction.STOP))
        root.bind('<Control-l>', lambda event: self._shortcut(UiAction.LOOKUP))
        self._build()
        self._render()
        self.buttons[UiAction.PLAY].focus_set()
        self._timer = root.after(40, self.pump)

    def _build(self):
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Prepared replay', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Fixed input trace · completed observations are historical', wraplength=700).pack(anchor='w', pady=(2, 12))
        self.status = tk.StringVar()
        self.message = tk.StringVar()
        self.next_step = tk.StringVar()
        self.progress_text = tk.StringVar()
        ttk.Label(frame, textvariable=self.status, font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(frame, textvariable=self.message, wraplength=720).pack(anchor='w', pady=4)
        ttk.Label(frame, textvariable=self.next_step, wraplength=720).pack(anchor='w', pady=(0, 8))
        self.progress = ttk.Progressbar(frame, mode='determinate', maximum=100)
        self.progress.pack(fill='x')
        ttk.Label(frame, textvariable=self.progress_text).pack(anchor='w', pady=(2, 12))
        bar = ttk.Frame(frame)
        bar.pack(fill='x')
        labels = {UiAction.PLAY: 'Play · Ctrl+P', UiAction.STOP: 'Stop · Esc',
                  UiAction.LOOKUP: 'Reconnect / lookup · Ctrl+L', UiAction.INSPECT: 'Inspect retained',
                  UiAction.CAPTURE: 'Capture metadata'}
        self.buttons = {}
        for action in UiAction:
            button = ttk.Button(bar, text=labels[action], command=lambda item=action: self.dispatch(item), takefocus=True)
            button.pack(side='left', padx=(0, 6))
            self.buttons[action] = button
        ttk.Label(frame, text='Retained evidence · no live debugger', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(18, 6))
        self.evidence = tk.Text(frame, height=12, wrap='word', state='disabled', takefocus=True)
        self.evidence.pack(fill='both', expand=True)
        self.diagnostics = tk.StringVar()
        ttk.Label(frame, textvariable=self.diagnostics, wraplength=720).pack(anchor='w', pady=(8, 0))

    def _shortcut(self, action):
        self.dispatch(action)
        return 'break'

    def dispatch(self, action: UiAction) -> bool:
        if (self._destroyed or type(action) is not UiAction or action not in enabled_actions(self.state)
                or self._cleanup_started
                or self._closing and action not in (UiAction.STOP, UiAction.LOOKUP)
                or not self.workers.available(action) or self._sequence >= 1_000_000):
            return False
        self._sequence += 1
        event = ReviewerEvent(action, self.state.phase, UiCode.QUEUED,
                              request_id=self._sequence, kind=EventKind.REQUESTED)
        next_state = reduce(self.state, event)
        if next_state is self.state:
            return False
        # Render the Stop latch before scheduling any potentially slow I/O.
        self.state = next_state
        self._render()
        if action is UiAction.LOOKUP:
            self._last_lookup = time.monotonic()
        self.workers.submit(action, self._sequence)
        return True

    def pump(self):
        if self._destroyed:
            return
        for event in self.workers.take():
            self.state = reduce(self.state, event)
        now = time.monotonic()
        if (not self._closing and not self._cleanup_started
                and not any(action is UiAction.PLAY for _, action in self.state.pending)
                and self.state.phase in (Phase.QUEUED, Phase.RUNNING, Phase.DRAINING)
                and now - self._last_lookup >= POLL_SECONDS):
            self.dispatch(UiAction.LOOKUP)
        self._check_close(now)
        if not self._destroyed:
            self._render()
            self._timer = self.root.after(40, self.pump)

    def close(self):
        if self._destroyed or self._closing:
            return
        self._closing = True
        self._close_deadline = time.monotonic() + CLOSE_SECONDS
        self.dispatch(UiAction.STOP)
        self._render()

    def _check_close(self, now):
        if not self._closing and not self._cleanup_started:
            return
        if self._cleanup_started:
            try:
                self._cleanup_outcome = self._cleanup_result.get_nowait()
            except queue.Empty:
                pass
            if self._cleanup_outcome is True and self.workers.active == 0 and not self.state.pending:
                self._destroy()
                return
            if self._cleanup_outcome is False:
                self._cleanup_started = False
                self._cleanup_outcome = None
                self._cleanup_thread = None
                self._close_failed()
                return
        elif self.workers.active == 0 and not self.state.pending:
            if self._on_close is None:
                if self.state.stop_confirmed:
                    self._destroy()
                    return
            else:
                self._cleanup_started = True

                def cleanup():
                    try:
                        cleaned = self._on_close() is True
                    except Exception:
                        cleaned = False
                    self._cleanup_result.put_nowait(cleaned)

                self._cleanup_thread = threading.Thread(target=cleanup, name='hh-reviewer-cleanup', daemon=True)
                try:
                    self._cleanup_thread.start()
                except Exception:
                    self._cleanup_result.put_nowait(False)
        if self._closing and now >= self._close_deadline:
            self._close_failed()

    def _close_failed(self):
        self.state = cleanup_held(self.state)
        self._closing = False
        # A still-running cleanup callback retains its ownership. Do not launch
        # a second callback on another close click or discard its eventual result.

    def _destroy(self):
        self.state = closed(self.state)
        self._destroyed = True
        self.root.destroy()

    def _render(self):
        render_key = (self.state, self._closing, self._cleanup_started)
        if getattr(self, '_last_render_key', None) == render_key:
            return
        self._last_render_key = render_key
        self.status.set(self.state.phase.value.upper())
        self.message.set(_MESSAGES[self.state.code])
        self.next_step.set('Next: ' + _NEXT[self.state.next_action.value])
        busy = self.state.phase in (Phase.QUEUED, Phase.RUNNING, Phase.DRAINING)
        indeterminate = busy and self.state.progress is None
        if indeterminate and not self._progress_running:
            self.progress.configure(mode='indeterminate')
            self.progress.start(20)
        elif not indeterminate:
            self.progress.stop()
            self.progress.configure(mode='determinate', value=self.state.progress or 0)
        self._progress_running = indeterminate
        self.progress_text.set('Progress unknown' if self.state.progress is None else str(self.state.progress) + '% observed')
        enabled = enabled_actions(self.state)
        for action, button in self.buttons.items():
            allowed = (not self._cleanup_started and action in enabled
                       and (not self._closing or action in (UiAction.STOP, UiAction.LOOKUP)))
            button.configure(state='normal' if allowed else 'disabled')
        summary = self.state.historical
        lines = ['No retained evidence received.']
        if summary is not None:
            lines = ['Historical completed replay; this view does not change runtime state.']
            if summary.pid is not None:
                lines.append('Process ' + str(summary.pid) + ' · generation ' + str(summary.generation))
            for name in ('report_sha256', 'source_sha256', 'snapshot_sha256', 'trace_sha256'):
                value = getattr(summary, name)
                if value is not None:
                    lines.append(name + ': ' + value)
            if summary.rows:
                lines.append('Rows: ' + str(len(summary.rows)) + ' of ' + str(summary.total_matches))
                for row in summary.rows:
                    position = ', '.join(format(value, '.3f') for value in row.body_position)
                    lines.append(f'Tick {row.tick} · {row.phase} · sim {row.sim_tick} · UI {row.ui_tick} · ({position})')
                if summary.has_next:
                    lines.append('More retained rows are available through Inspect retained.')
            if summary.capture is not None:
                capture = summary.capture
                lines.extend((f'Capture {capture.label} · tick {capture.tick} · {capture.phase} · {capture.size_bytes} bytes',
                              'capture_sha256: ' + capture.sha256))
        self.evidence.configure(state='normal')
        self.evidence.delete('1.0', 'end')
        self.evidence.insert('1.0', '\n'.join(lines))
        self.evidence.configure(state='disabled')
        self.diagnostics.set('Recent states: ' + ', '.join(code.value for code in self.state.history)
                             + ' · stale updates ignored: ' + str(self.state.dropped_updates))
