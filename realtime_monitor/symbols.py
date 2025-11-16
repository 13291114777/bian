from __future__ import annotations

import asyncio
from typing import Dict, List, Tuple

from .binance_client import BinanceFuturesClient, fetch_usdt_perp_symbols, fetch_midnight_close
from .time_utils import local_midnight_utc_ms


async def build_midnight_baseline(client: BinanceFuturesClient) -> Tuple[List[str], Dict[str, float]]:
    symbols = await fetch_usdt_perp_symbols(client)
    base_ts = local_midnight_utc_ms()
    baselines: Dict[str, float] = {}

    sem = asyncio.Semaphore(20)

    async def _one(sym: str):
        async with sem:
            v = await fetch_midnight_close(client, sym, base_ts)
            if v is not None and v > 0:
                baselines[sym] = v

    await asyncio.gather(*[_one(s) for s in symbols])
    return symbols, baselines


def rank_top(symbols: List[str], baselines: Dict[str, float], prices: Dict[str, float], topn: int = 50) -> Tuple[List[Tuple[str, float, float]], List[Tuple[str, float, float]]]:
    rows: List[Tuple[str, float, float]] = []  # (symbol, price, pct)
    for s in symbols:
        b = baselines.get(s)
        p = prices.get(s)
        if b and p:
            pct = (p - b) / b * 100.0
            rows.append((s, p, pct))
    rows.sort(key=lambda x: x[2], reverse=True)
    top_gain = rows[:topn]
    top_lose = sorted(rows, key=lambda x: x[2])[:topn]
    return top_gain, top_lose

def secondary_sort_by_delta(
    rows: List[Tuple[str, float, float]],
    delta_map: Dict[str, float],
    *,
    mode: str,
) -> List[Tuple[str, float, float]]:
    # mode: 'gainers' or 'losers'
    if mode == 'gainers':
        # 主排序已按 pct 降序，这里在同等 pct 附近用 delta 降序微调
        return sorted(rows, key=lambda x: (round(x[2], 6), delta_map.get(x[0], 0.0)), reverse=True)
    else:
        # 跌幅榜：按 pct 升序，delta 升序（更负的更靠前）
        return sorted(rows, key=lambda x: (round(x[2], 6), delta_map.get(x[0], 0.0)))
