from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
from collections import deque
import time

from .ema import EMASet, detect_cross
from .binance_client import (
    BinanceFuturesClient,
    fetch_latest_closed_kline,
    fetch_recent_closes,
)


@dataclass
class CrossWatch:
    direction: str  # 'up' | 'down'
    start_open_time: int  # 该交叉发生的K线openTime（ms）
    candles_left: int = 5  # 交叉后需要观察的K线根数（默认第5根收盘时判断）
    broken: bool = False  # 观察期内是否已触发“破EMA21”


@dataclass
class SymbolState:
    symbol: str
    ema: EMASet
    last_open_time: Optional[int] = None
    prev_snapshot: Optional[Tuple[float, float, float, float]] = None
    watch: Optional[CrossWatch] = None
    prev_close: Optional[float] = None
    last_close: Optional[float] = None
    recent_closes: deque[float] = field(default_factory=lambda: deque(maxlen=64))
    last_quote_volume: Optional[float] = None


class SymbolMonitor:
    def __init__(
        self,
        client: BinanceFuturesClient,
        concurrency: int = 20,
        confirm_candles: int = 5,
        seed_limit: int = 600,
        ws_cache: Optional[Dict[str, Tuple[int, float, float, float, float, float]]] = None,
        *,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_quote_usdt: Optional[float] = None,
        cooldown_seconds: int = 0,
    ):
        self.client = client
        self.states: Dict[str, SymbolState] = {}
        self._sem = asyncio.Semaphore(concurrency)
        self.confirm_candles = max(1, int(confirm_candles))
        self.seed_limit = max(100, int(seed_limit))  # 至少保证>83
        self.ws_cache = ws_cache or {}
        # 风控
        self.min_price = float(min_price) if min_price is not None else None
        self.max_price = float(max_price) if max_price is not None else None
        self.min_quote_usdt = float(min_quote_usdt) if min_quote_usdt is not None else None
        self.cooldown_seconds = max(0, int(cooldown_seconds))
        self._last_alert_at: Dict[str, int] = {}

    async def ensure_state(self, symbol: str):
        if symbol in self.states:
            return
        # 初始化EMA（取至少 seed_limit 根，保证 seed 充足）
        closes = [c for _, c in await fetch_recent_closes(self.client, symbol, limit=self.seed_limit)]
        ema = EMASet.create_seeded(closes)
        prev_close = closes[-2] if len(closes) >= 2 else None
        last_close = closes[-1] if len(closes) >= 1 else None
        self.states[symbol] = SymbolState(
            symbol=symbol,
            ema=ema,
            last_open_time=None,
            prev_snapshot=ema.snapshot(),
            prev_close=prev_close,
            last_close=last_close,
            recent_closes=deque(closes[-64:], maxlen=64),
        )

    async def drop_state(self, symbol: str):
        self.states.pop(symbol, None)

    async def update_symbol_once(self, symbol: str) -> Optional[dict]:
        # 返回可能的提示文本（入场信号）
        # 优先使用 WebSocket 缓存的已收盘K线
        k = self.ws_cache.get(symbol) if self.ws_cache else None
        if k is None:
            async with self._sem:
                k = await fetch_latest_closed_kline(self.client, symbol)
        if not k:
            return None
        # 兼容 ws/REST：均为 (t, o, h, l, c, qv)
        open_time, _o, high, low, close = k[:5]
        quote_vol = float(k[5]) if len(k) > 5 else None
        st = self.states.get(symbol)
        if st is None:
            await self.ensure_state(symbol)
            st = self.states[symbol]

        if st.last_open_time is not None and open_time <= st.last_open_time:
            return None  # 没有新K线

        prev = st.ema.snapshot()
        st.ema.update(close)
        cur = st.ema.snapshot()
        st.last_open_time = open_time
        # 维护1m收盘价对比
        st.prev_close = st.last_close
        st.last_close = close
        # 维护滚动收盘窗口（用于 1/5/15m Δ% 计算）
        st.recent_closes.append(close)
        st.last_quote_volume = quote_vol

        # 交叉检测
        cross = detect_cross(prev, cur)
        if cross:
            # 记录观察窗口：交叉后统计接下来5根K线
            st.watch = CrossWatch(
                direction=cross,
                start_open_time=open_time,
                candles_left=self.confirm_candles,
                broken=False,
            )

        # 观察窗口中的条件监控（统计交叉后的接下来N根K线）
        if st.watch:
            _, ema21, _, _ = cur
            out_tip: Optional[str] = None
            if st.watch.direction == "up":
                crossed = low < ema21
                if crossed:
                    # 回调中“穿过”EMA21
                    if close <= ema21:
                        out_tip = f"[{symbol}] 上穿后回调本根跌破EMA21且收盘未站上EMA21 -> 提示"
                    st.watch.broken = True
            else:
                crossed = high > ema21
                if crossed:
                    # 回调中“穿过”EMA21
                    if close <= ema21:
                        out_tip = f"[{symbol}] 下穿后反弹本根涨破EMA21但收盘未站上EMA21 -> 提示"
                    st.watch.broken = True

            # 统计根数递减，到第N根收盘时判断
            st.watch.candles_left -= 1
            if st.watch.candles_left <= 0:
                event_sig = None
                if not st.watch.broken:
                    event_sig = {
                        "symbol": symbol,
                        "kind": "signal",
                        "direction": st.watch.direction,
                        "open_time": open_time,
                        "price": close,
                        "ema21": ema21,
                        "high": high,
                        "low": low,
                        "quote_volume": quote_vol,
                        "confirm_candles": self.confirm_candles,
                        "message": f"[{symbol}] {st.watch.direction.upper()} 交叉后第{self.confirm_candles}根K线未{'跌破' if st.watch.direction=='up' else '涨破'} EMA21 -> 入场信号",
                    }
                st.watch = None
                # 若前面已有提示，优先返回提示；否则返回信号
                return self._maybe_allow_event(symbol, out_tip, open_time, close, quote_vol, ema21, high, low) or (
                    self._maybe_allow_event(symbol, event_sig, open_time, close, quote_vol, ema21, high, low) if event_sig else None
                )

            # 若未到期，但有提示，立即返回提示
            if out_tip:
                tip_event = {
                    "symbol": symbol,
                    "kind": "tip",
                    "direction": st.watch.direction,
                    "open_time": open_time,
                    "price": close,
                    "ema21": ema21,
                    "high": high,
                    "low": low,
                    "quote_volume": quote_vol,
                    "message": out_tip,
                }
                return self._maybe_allow_event(symbol, tip_event, open_time, close, quote_vol, ema21, high, low)

        st.prev_snapshot = cur
        return None

    def _maybe_allow_event(
        self,
        symbol: str,
        event: Optional[dict],
        open_time: int,
        close: float,
        quote_vol: Optional[float],
        ema21: float,
        high: float,
        low: float,
    ) -> Optional[dict]:
        if not event:
            return None
        # 价格过滤
        if self.min_price is not None and close < self.min_price:
            return None
        if self.max_price is not None and close > self.max_price:
            return None
        # 成交额过滤（1m报价量，单位约等于USDT）
        if self.min_quote_usdt is not None and (quote_vol is None or quote_vol < self.min_quote_usdt):
            return None
        # 冷却时间
        now_s = open_time // 1000
        last = self._last_alert_at.get(symbol, 0)
        if self.cooldown_seconds > 0 and now_s - last < self.cooldown_seconds:
            return None
        # 通过，记录时间戳并返回
        self._last_alert_at[symbol] = now_s
        # 附带补充字段（冗余安全）
        event.setdefault("ts", now_s)
        return event

    async def update_many(self, symbols: List[str]) -> List[dict]:
        # 初始化缺失state
        tasks_init = [self.ensure_state(s) for s in symbols if s not in self.states]
        if tasks_init:
            await asyncio.gather(*tasks_init)
        # 并发轮询
        results: List[Optional[dict]] = await asyncio.gather(*[self.update_symbol_once(s) for s in symbols])
        return [r for r in results if r]

    async def ensure_states(self, symbols: List[str]):
        tasks_init = [self.ensure_state(s) for s in symbols if s not in self.states]
        if tasks_init:
            await asyncio.gather(*tasks_init)

    def minute_change_map(self, symbols: List[str]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for s in symbols:
            st = self.states.get(s)
            if not st or st.prev_close is None or st.last_close is None or st.prev_close == 0:
                continue
            out[s] = (st.last_close - st.prev_close) / st.prev_close * 100.0
        return out

    def multi_change_map(self, symbols: List[str], windows: List[int]) -> Dict[str, Dict[int, float]]:
        # 返回 {symbol: {window: pct, ...}, ...}
        res: Dict[str, Dict[int, float]] = {}
        uniq_windows = sorted(set(int(w) for w in windows if int(w) > 0))
        for s in symbols:
            st = self.states.get(s)
            if not st or not st.recent_closes:
                continue
            n = len(st.recent_closes)
            mp: Dict[int, float] = {}
            last = st.recent_closes[-1]
            for w in uniq_windows:
                if n <= w:
                    continue
                base = st.recent_closes[-1 - w]
                if base:
                    mp[w] = (last - base) / base * 100.0
            if mp:
                res[s] = mp
        return res
