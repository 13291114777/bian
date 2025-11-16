from __future__ import annotations

import os
import json
import csv
from datetime import datetime, timezone
from typing import Dict, Any


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _csv_path(dir_path: str) -> str:
    return os.path.join(dir_path, "alerts.csv")


def _jsonl_path(dir_path: str) -> str:
    return os.path.join(dir_path, "alerts.jsonl")


def _ts_iso(ts: int) -> str:
    # ts in seconds
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat()


async def append_event(dir_path: str, ev: Dict[str, Any]) -> None:
    _ensure_dir(dir_path)
    # enrich
    ev = dict(ev)
    ts = int(ev.get("ts") or (ev.get("open_time", 0) // 1000))
    ev["ts"] = ts
    ev["ts_iso"] = _ts_iso(ts)

    # JSONL append
    jpath = _jsonl_path(dir_path)
    with open(jpath, "a", encoding="utf-8") as jf:
        jf.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # CSV append
    cpath = _csv_path(dir_path)
    fieldnames = [
        "ts","ts_iso","symbol","kind","direction","open_time","price","ema21","high","low","quote_volume","confirm_candles","message"
    ]
    write_header = not os.path.exists(cpath) or os.path.getsize(cpath) == 0
    with open(cpath, "a", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        row = {k: ev.get(k) for k in fieldnames}
        writer.writerow(row)
