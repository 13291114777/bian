from __future__ import annotations

import re
from typing import Iterable, List, Tuple, Dict
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# 列宽定义（保持两个榜单对齐）
SYM_W = 16
PRICE_W = 14
PCT_W = 10
DELTA_W = 8

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _visual_len(s: str) -> int:
    return len(ANSI_RE.sub("", s))


def _pad_visual(s: str, total: int) -> str:
    vis = _visual_len(s)
    if vis < total:
        return s + (" " * (total - vis))
    return s


def _format_row(
    symbol: str,
    price: float,
    pct: float,
    deltas: Dict[int, float] | None = None,
    windows: List[int] | None = None,
    *,
    colorize: bool = True,
    highlight_threshold: float | None = None,
) -> str:
    # 百分比包含符号，右对齐
    pct_str = f"{pct:+.3f}%"
    if colorize:
        pct_str = (Fore.RED if pct < 0 else Fore.GREEN) + pct_str + Style.RESET_ALL
    left = f"{symbol:<{SYM_W}} {price:>{PRICE_W}.6f} "
    mid = _pad_visual(pct_str, PCT_W)
    # 多窗口Δ%
    pieces: List[str] = []
    for w in (windows or []):
        val = None if not deltas else deltas.get(w)
        if val is None:
            pieces.append(" " * DELTA_W)
            continue
        dstr = f"{val:+.3f}%"
        is_highlight = highlight_threshold is not None and abs(val) >= float(highlight_threshold)
        if colorize:
            color = Fore.RED if val < 0 else Fore.GREEN
            if is_highlight:
                dstr = Style.BRIGHT + color + dstr + Style.RESET_ALL
            else:
                dstr = color + dstr + Style.RESET_ALL
        pieces.append(_pad_visual(dstr, DELTA_W))
    return left + mid + " " + " ".join(pieces)


def print_board(
    title: str,
    rows: Iterable[Tuple[str, float, float]],
    delta_maps: Dict[str, Dict[int, float]] | None = None,
    windows: List[int] | None = None,
    *,
    highlight_threshold: float | None = None,
):
    print(f"\n{Style.BRIGHT}{title}{Style.RESET_ALL}")
    # 动态列头
    wlist = windows or []
    extras = " ".join([f"{str(w)+'mΔ%':>{DELTA_W}}" for w in wlist])
    header = f"{'Symbol':<{SYM_W}} {'Price':>{PRICE_W}} {'Change%':>{PCT_W}} {extras}"
    print(header)
    print("-" * _visual_len(header))
    for s, p, pct in rows:
        dmap = (delta_maps or {}).get(s)
        print(_format_row(s, p, pct, deltas=dmap, windows=wlist, colorize=True, highlight_threshold=highlight_threshold))


def print_boards_side_by_side(
    left_title: str,
    left_rows: List[Tuple[str, float, float]],
    right_title: str,
    right_rows: List[Tuple[str, float, float]],
    delta_maps: Dict[str, Dict[int, float]] | None = None,
    windows: List[int] | None = None,
    *,
    highlight_threshold: float | None = None,
):
    # 标题行
    wlist = windows or []
    extras = " ".join([f"{str(w)+'mΔ%':>{DELTA_W}}" for w in wlist])
    head = f"{'Symbol':<{SYM_W}} {'Price':>{PRICE_W}} {'Change%':>{PCT_W}} {extras}"
    board_w = _visual_len(head)
    left_head = f"{left_title}".center(board_w)
    right_head = f"{right_title}".center(board_w)
    print(f"\n{Style.BRIGHT}{left_head}{Style.RESET_ALL}   |   {Style.BRIGHT}{right_head}{Style.RESET_ALL}")

    # 列头
    print(f"{head}   |   {head}")
    print(f"{'-' * len(head)}   |   {'-' * len(head)}")

    n = max(len(left_rows), len(right_rows))
    for i in range(n):
        if i < len(left_rows):
            ls, lp, lpc = left_rows[i]
            ldmap = (delta_maps or {}).get(ls)
            ltxt = _format_row(ls, lp, lpc, deltas=ldmap, windows=wlist, colorize=True, highlight_threshold=highlight_threshold)
        else:
            ltxt = " " * board_w
        if i < len(right_rows):
            rs, rp, rpc = right_rows[i]
            rdmap = (delta_maps or {}).get(rs)
            rtxt = _format_row(rs, rp, rpc, deltas=rdmap, windows=wlist, colorize=True, highlight_threshold=highlight_threshold)
        else:
            rtxt = " " * board_w
        print(f"{ltxt}   |   {rtxt}")
