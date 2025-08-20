from __future__ import annotations

import runpy
import sys
import cProfile
import pstats
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional
from pyinstrument import Profiler

@dataclass
class Row:
    ncalls: int
    tottime: float
    cumtime: float
    filename: str
    line: int
    func: str

def _row_from_stat(key, stat) -> Row:
    (filename, line, funcname) = key
    cc, nc, tt, ct, callers = stat  # ccalls, ncalls, tottime, cumtime, callers
    return Row(ncalls=nc, tottime=tt, cumtime=ct, filename=filename, line=line, func=funcname)

def profile_cprofile(script: Path, args: Optional[List[str]] = None, sort_by: str = "cumulative", limit: int = 10) -> List[Row]:
    script = script.resolve()
    if not script.exists():
        raise FileNotFoundError(f"Script no encontrado: {script}")

    old_argv = sys.argv
    sys.argv = [str(script)] + (args or [])
    try:
        pr = cProfile.Profile()
        pr.enable()
        runpy.run_path(str(script), run_name="__main__")
        pr.disable()
    finally:
        sys.argv = old_argv

    stats = pstats.Stats(pr)
    if sort_by == "time":
        stats.sort_stats(pstats.SortKey.TIME)
    else:
        stats.sort_stats(pstats.SortKey.CUMULATIVE)

    rows: List[Row] = []
    for (key, stat) in list(stats.stats.items()):
        rows.append(_row_from_stat(key, stat))

    rows.sort(key=(lambda r: r.cumtime if sort_by != "time" else r.tottime), reverse=True)
    return rows[: max(1, limit)]

def rows_to_json(rows: List[Row]) -> List[Dict[str, Any]]:
    return [
        {
            "ncalls": r.ncalls,
            "tottime": r.tottime,
            "cumtime": r.cumtime,
            "location": f"{Path(r.filename).name}:{r.line}",
            "function": r.func,
        }
        for r in rows
    ]

def profile_pyinstrument(script: Path, args: Optional[List[str]] = None) -> str:
    old_argv = sys.argv
    sys.argv = [str(script)] + (args or [])
    try:
        profiler = Profiler()
        profiler.start()
        runpy.run_path(str(script), run_name="__main__")
        profiler.stop()
        return profiler.output_text(unicode=True, color=False)
    finally:
        sys.argv = old_argv
