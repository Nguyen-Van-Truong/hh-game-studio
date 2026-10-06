"""Bounded, message-free failure boundaries for native diagnostic receipts."""
from pathlib import Path
import re


def failure_boundary(error: BaseException) -> dict:
    """Inspect an already-raised error, never trace or alter native execution.

    Exception messages, paths and locals may contain credentials. Retain only
    typed codes and code locations, including wrapper causes otherwise lost.
    """
    chain, seen = [], set()
    current = error
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        kind = type(current).__name__
        code = getattr(current, 'code', None)
        row = {'type': kind, 'code': code if type(code) is str and
               re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code) else kind}
        frames, trace = [], current.__traceback__
        while trace is not None:
            frames.append({'file': Path(trace.tb_frame.f_code.co_filename).name,
                           'function': trace.tb_frame.f_code.co_name,
                           'line': trace.tb_lineno})
            trace = trace.tb_next
        row['frames'] = frames[-8:]
        chain.append(row)
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__)
    return {**chain[0], 'causes': chain[1:]}
