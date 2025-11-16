from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple


@dataclass
class EMA:
    period: int
    value: Optional[float] = None
    _k: Optional[float] = None
    _seeded: bool = False

    def __post_init__(self):
        self._k = 2.0 / (self.period + 1.0)

    def seed(self, closes: Iterable[float]):
        """用前 period 个收盘价进行SMA初始化，再继续EMA推进。"""
        it = iter(closes)
        first_vals = []
        try:
            for _ in range(self.period):
                first_vals.append(float(next(it)))
        except StopIteration:
            raise ValueError(f"初始化EMA{self.period}需要至少{self.period}个收盘价")
        sma = sum(first_vals) / self.period
        self.value = sma
        self._seeded = True
        for c in it:
            self.update(float(c))

    def update(self, close: float) -> float:
        if not self._seeded:
            # 若尚未seed，用第一个close作为起点
            self.value = float(close) if self.value is None else self.value
            self._seeded = True
            return self.value
        assert self.value is not None
        self.value = (close - self.value) * self._k + self.value
        return self.value


@dataclass
class EMASet:
    ema13: EMA
    ema21: EMA
    ema72: EMA
    ema83: EMA

    @classmethod
    def create_seeded(cls, closes: Iterable[float]) -> "EMASet":
        closes = list(map(float, closes))
        if len(closes) < 83:
            raise ValueError("初始化EMA需要至少83根1m收盘价")
        e13 = EMA(13)
        e13.seed(closes)
        e21 = EMA(21)
        e21.seed(closes)
        e72 = EMA(72)
        e72.seed(closes)
        e83 = EMA(83)
        e83.seed(closes)
        return cls(e13, e21, e72, e83)

    def update(self, close: float) -> Tuple[float, float, float, float]:
        return (
            self.ema13.update(close),
            self.ema21.update(close),
            self.ema72.update(close),
            self.ema83.update(close),
        )

    def snapshot(self) -> Tuple[float, float, float, float]:
        assert self.ema13.value is not None and self.ema21.value is not None
        assert self.ema72.value is not None and self.ema83.value is not None
        return (self.ema13.value, self.ema21.value, self.ema72.value, self.ema83.value)


def detect_cross(prev: Tuple[float, float, float, float], cur: Tuple[float, float, float, float]) -> Optional[str]:
    """检测交叉：
    - 返回 'up' 当 min(EMA13, EMA21) 从 <= max(EMA72, EMA83) 变为 >;
    - 返回 'down' 当 max(EMA13, EMA21) 从 >= min(EMA72, EMA83) 变为 <;
    - 否则返回 None。
    基于收盘价计算。
    """
    p13, p21, p72, p83 = prev
    c13, c21, c72, c83 = cur
    p_fast_min, p_slow_max = min(p13, p21), max(p72, p83)
    c_fast_min, c_slow_max = min(c13, c21), max(c72, c83)
    p_fast_max, p_slow_min = max(p13, p21), min(p72, p83)
    c_fast_max, c_slow_min = max(c13, c21), min(c72, c83)

    if p_fast_min <= p_slow_max and c_fast_min > c_slow_max:
        return "up"
    if p_fast_max >= p_slow_min and c_fast_max < c_slow_min:
        return "down"
    return None
