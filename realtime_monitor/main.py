from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

from colorama import Fore, Style

from .binance_client import BinanceFuturesClient
from .symbols import build_midnight_baseline, rank_top, secondary_sort_by_delta
from .monitor import SymbolMonitor
from .ws_client import BinanceKlineWS


async def prices_map(client: BinanceFuturesClient) -> Dict[str, float]:
    data = await client.ticker_price_all()
    out: Dict[str, float] = {}
    for d in data:
        try:
            out[d["symbol"]] = float(d["price"])
        except Exception:
            continue
    return out


async def main_loop(
    once: bool = False,
    *,
    secondary_by_delta: bool = True,
    highlight_delta: float | None = 1.0,
    confirm_candles: int = 5,
    interval_seconds: float = 20.0,
    scan_all: bool = False,
    concurrency: int = 20,
    seed_limit: int = 600,
    beep: bool = False,
    delta_windows: list[int] | None = None,
    ws: bool = False,
    events_dir: str | None = "logs",
    enable_events: bool = True,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quote_usdt: float | None = None,
    cooldown_seconds: int = 0,
    secondary_by: str = "1m",
    weights: str | None = None,
):
    client = BinanceFuturesClient()
    try:
        print("初始化：获取USDT永续与本地0点基准...")
        symbols, baselines = await build_midnight_baseline(client)
        print(f"交易对数量：{len(symbols)}，有基准价的：{len(baselines)}")

        # 可选：启动WebSocket聚合（订阅全量USDT永续 1m）
        ws_cache: dict[str, tuple[int, float, float, float, float]] = {}
        ws_feed: BinanceKlineWS | None = None
        if ws:
            ws_feed = BinanceKlineWS(symbols, ws_cache)
            await ws_feed.run_in_background()

        monitor = SymbolMonitor(
            client,
            concurrency=concurrency,
            confirm_candles=confirm_candles,
            seed_limit=seed_limit,
            ws_cache=ws_cache if ws else None,
            min_price=min_price,
            max_price=max_price,
            min_quote_usdt=min_quote_usdt,
            cooldown_seconds=cooldown_seconds,
        )

        tracked: List[str] = []

        windows = sorted(set(delta_windows or [1, 5, 15]))

        while True:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 1) 获取全量价格
            price = await prices_map(client)
            # 2) 排名
            top_gain, top_lose = rank_top(symbols, baselines, price, topn=50)

            # 3) 维护监控集合（并集）并计算1m涨跌幅
            if scan_all:
                # 跟踪全部USDT永续（已成功建立基准的）
                new_tracked = sorted([s for s in symbols if s in baselines])
            else:
                # 仅跟踪当前榜单中出现的交易对
                new_tracked = sorted(list({*[s for s, _, _ in top_gain], *[s for s, _, _ in top_lose]}))
            await monitor.ensure_states(new_tracked)
            delta_maps = monitor.multi_change_map(new_tracked, windows)
            # 供二次排序使用的 1mΔ%
            one_min_map = {s: m.get(1) for s, m in (delta_maps or {}).items() if m and 1 in m}
            five_min_map = {s: m.get(5) for s, m in (delta_maps or {}).items() if m and 5 in m}
            fifteen_min_map = {s: m.get(15) for s, m in (delta_maps or {}).items() if m and 15 in m}

            # 4) 二次排序（可选）并打印榜单（含1mΔ%列）
            from .console import print_board, print_boards_side_by_side
            if secondary_by_delta:
                sort_map = one_min_map
                if secondary_by == "5m":
                    sort_map = five_min_map
                elif secondary_by == "15m":
                    sort_map = fifteen_min_map
                elif secondary_by == "weighted":
                    w1, w5, w15 = 1.0, 0.5, 0.25
                    try:
                        if weights:
                            parts = [p.strip() for p in weights.split(',') if p.strip()]
                            if len(parts) >= 3:
                                w1, w5, w15 = float(parts[0]), float(parts[1]), float(parts[2])
                    except Exception:
                        pass
                    # 以绝对值加权，突出波动强度
                    keys = set(one_min_map.keys()) | set(five_min_map.keys()) | set(fifteen_min_map.keys())
                    sort_map = {}
                    for s in keys:
                        v1 = abs(one_min_map.get(s, 0.0) or 0.0)
                        v5 = abs(five_min_map.get(s, 0.0) or 0.0)
                        v15 = abs(fifteen_min_map.get(s, 0.0) or 0.0)
                        sort_map[s] = w1 * v1 + w5 * v5 + w15 * v15
                top_gain = secondary_sort_by_delta(top_gain, sort_map, mode='gainers')
                top_lose = secondary_sort_by_delta(top_lose, sort_map, mode='losers')
            print(f"\n{Style.BRIGHT}====== {now} ======{Style.RESET_ALL}")
            # 并排对齐展示榜单
            print_boards_side_by_side(
                "涨幅榜 Top 50", top_gain, "跌幅榜 Top 50", top_lose,
                delta_maps=delta_maps, windows=windows,
                highlight_threshold=highlight_delta,
            )

            # 移除不再跟踪的（可选）
            for s in list(monitor.states.keys()):
                if s not in new_tracked:
                    await monitor.drop_state(s)

            # 5) 对入选币种进行1m K线更新与交叉/信号检测
            alerts = await monitor.update_many(new_tracked)
            for ev in alerts:
                msg = ev.get("message", "")
                if ev.get("kind") == "signal":
                    print(f"{Style.BRIGHT}{Fore.YELLOW}★ {msg}{Style.RESET_ALL}")
                    if beep:
                        try:
                            import winsound
                            winsound.Beep(1200, 250); winsound.Beep(1200, 250)
                        except Exception:
                            pass
                else:
                    print(f"{Style.BRIGHT}{Fore.MAGENTA}⚠ {msg}{Style.RESET_ALL}")
                    if beep:
                        try:
                            import winsound
                            winsound.Beep(800, 150)
                        except Exception:
                            pass
                # 事件落盘
                if enable_events and events_dir:
                    try:
                        from .events import append_event
                        await append_event(events_dir, ev)
                    except Exception:
                        pass

            tracked = new_tracked

            if once:
                # 仅运行一轮，便于冒烟测试
                break
            # 6) 等待下一轮
            await asyncio.sleep(max(1.0, float(interval_seconds)))
    finally:
        try:
            if 'ws_feed' in locals() and ws_feed is not None:
                await ws_feed.stop()
        finally:
            await client.aclose()


def run():
    try:
        import argparse
        parser = argparse.ArgumentParser(description="Realtime Binance Futures monitor")
        parser.add_argument("--once", action="store_true", help="Run one iteration and exit")
        parser.add_argument("--no-secondary-by-delta", action="store_true", help="Disable secondary sort by 1m delta within boards")
        parser.add_argument("--highlight-delta", type=float, default=1.0, help="Highlight threshold for 1m delta in percent (abs)")
        parser.add_argument("--confirm-candles", type=int, default=5, help="Number of 1m candles to confirm after cross (default 5)")
        parser.add_argument("--interval-seconds", type=float, default=20.0, help="Polling interval seconds (default 20)")
        parser.add_argument("--scan-all", action="store_true", help="Track all USDT perpetual symbols for EMA cross scan")
        parser.add_argument("--concurrency", type=int, default=20, help="Max concurrent requests for symbol updates")
        parser.add_argument("--seed-limit", type=int, default=600, help="Initial 1m close count for EMA seeding (>=100)")
        parser.add_argument("--beep", action="store_true", help="Play a short beep on alerts (Windows)")
        parser.add_argument("--delta-columns", type=str, default="1,5,15", help="Comma-separated minute windows for Δ%% columns, e.g. 1,5,15")
        parser.add_argument("--ws", action="store_true", help="Use WebSocket 1m kline feed to reduce REST calls (subscribes all symbols)")
        parser.add_argument("--events-dir", type=str, default="logs", help="Directory to write alert events (CSV and JSONL)")
        parser.add_argument("--no-events", action="store_true", help="Disable writing events to files")
        parser.add_argument("--min-price", type=float, default=None, help="Min last close price filter")
        parser.add_argument("--max-price", type=float, default=None, help="Max last close price filter")
        parser.add_argument("--min-quote-usdt", type=float, default=None, help="Min 1m quote volume (USDT) to allow alerts")
        parser.add_argument("--cooldown-seconds", type=int, default=0, help="Cooldown seconds between alerts for the same symbol")
        parser.add_argument("--secondary-by", type=str, choices=["1m","5m","15m","weighted"], default="1m", help="Secondary sort source: 1m/5m/15m or weighted")
        parser.add_argument("--weights", type=str, default=None, help="Weights for weighted sort, format: w1,w5,w15")
        args = parser.parse_args()

        def _parse_windows(s: str) -> list[int]:
            out: list[int] = []
            for part in (s or "").split(','):
                part = part.strip()
                if not part:
                    continue
                try:
                    v = int(part)
                    if v > 0:
                        out.append(v)
                except Exception:
                    continue
            return out or [1]

        asyncio.run(
            main_loop(
                once=args.once,
                secondary_by_delta=(not args.no_secondary_by_delta),
                highlight_delta=args.highlight_delta,
                confirm_candles=args.confirm_candles,
                interval_seconds=args.interval_seconds,
                scan_all=args.scan_all,
                concurrency=args.concurrency,
                seed_limit=args.seed_limit,
                beep=args.beep,
                delta_windows=_parse_windows(args.delta_columns),
                ws=args.ws,
                events_dir=args.events_dir,
                enable_events=(not args.no_events),
                min_price=args.min_price,
                max_price=args.max_price,
                min_quote_usdt=args.min_quote_usdt,
                cooldown_seconds=args.cooldown_seconds,
                secondary_by=args.secondary_by,
                weights=args.weights,
            )
        )
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    run()
