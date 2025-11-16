from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Tuple

import websockets

WS_ENDPOINT = "wss://fstream.binance.com/stream?streams="

# 缓存类型：symbol -> (open_time_ms, open, high, low, close, quote_volume)
WsCache = Dict[str, Tuple[int, float, float, float, float, float]]


def _build_streams(symbols: List[str]) -> str:
    # e.g. btcusdt@kline_1m/ethusdt@kline_1m
    parts = [f"{s.lower()}@kline_1m" for s in symbols]
    return WS_ENDPOINT + "/".join(parts)


class BinanceKlineWS:
    def __init__(self, symbols: List[str], cache: WsCache):
        self._symbols = symbols
        self._cache = cache
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self):
        url = _build_streams(self._symbols)
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    async for msg in ws:
                        if self._stop.is_set():
                            break
                        try:
                            data = json.loads(msg)
                            k = data.get("data", {}).get("k")
                            if not k:
                                continue
                            if not k.get("x"):
                                # 未收盘的K线，不处理
                                continue
                            sym = k.get("s")
                            if not sym:
                                continue
                            open_time = int(k.get("t"))
                            o = float(k.get("o"))
                            h = float(k.get("h"))
                            l = float(k.get("l"))
                            c = float(k.get("c"))
                            q = float(k.get("q", 0.0))
                            self._cache[sym] = (open_time, o, h, l, c, q)
                        except Exception:
                            # 忽略单条解析错误
                            continue
            except Exception:
                # 自动重连，指数退避至 30s 最大
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2.0)

    async def run_in_background(self):
        self._task = asyncio.create_task(self.start())

    async def stop(self):
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except Exception:
                pass
