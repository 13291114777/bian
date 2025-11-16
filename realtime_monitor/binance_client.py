from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential
import random

# 仅在显式设置环境变量时使用，否则为 None
BASE_URL = os.getenv("BINANCE_BASE_URL")

# 备用端点轮换列表（仅在显式配置 BASE_URL 时启用完整轮换）
DEFAULT_BASE_URLS: List[str] = [
    "https://fapi.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
    "https://fapi4.binance.com",
]


class BinanceFuturesClient:
    def __init__(self, *, timeout: float = 15.0, max_connections: int = 50):
        self._timeout = timeout
        self._limits = httpx.Limits(max_keepalive_connections=max_connections, max_connections=max_connections)
        # 通过常见浏览器 UA 与合理的 Accept 头，降低被风控命中的概率；
        # 同时启用 HTTP/2 提升长连接复用效率（可选）。
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        # HTTP/2 可提升复用，但在未安装 h2 依赖时自动降级为 HTTP/1.1；
        # 你也可以通过环境变量 HTTP2=on/off 强制开关。
        http2_env = os.getenv("HTTP2", "auto").lower()
        if http2_env == "on":
            self._http2_enabled = True
        elif http2_env == "off":
            self._http2_enabled = False
        else:
            try:
                import h2  # type: ignore  # noqa: F401
                self._http2_enabled = True
            except Exception:
                self._http2_enabled = False

        # 代理支持：优先读取 PROXY_URL；httpx>=0.28 移除了 proxies 参数，
        # 因此这里将 PROXY_URL 映射到标准环境变量并依赖 trust_env=True。
        self._proxy_url = os.getenv("PROXY_URL")
        if self._proxy_url:
            # 覆盖三类常用代理环境变量，确保 https 请求走代理
            os.environ["HTTPS_PROXY"] = self._proxy_url
            os.environ["HTTP_PROXY"] = self._proxy_url
            os.environ["ALL_PROXY"] = self._proxy_url

        # 端点轮换：若指定了 BINANCE_BASE_URL，则将其置于列表首位；
        # 否则仅用 fapi 主端点，避免轮换到可能被 429 的备用端点
        self._base_urls: List[str] = []
        if BASE_URL:
            self._base_urls.append(BASE_URL)
            # 若显式配置了端点，也加入其他备用以便轮换
            for u in DEFAULT_BASE_URLS:
                if u not in self._base_urls:
                    self._base_urls.append(u)
        else:
            # 未配置时，仅用主端点 fapi，备用暂不加入（避免频繁 429）
            self._base_urls.append("https://fapi.binance.com")
        self._base_idx = 0

        self._client = self._build_client(self._base_urls[self._base_idx])

    def _build_client(self, base_url: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=base_url,
            timeout=self._timeout,
            limits=self._limits,
            headers=self._headers,
            http2=self._http2_enabled,
            trust_env=True,  # 允许使用 HTTP(S)_PROXY 等系统代理
        )

    async def _rotate_base(self, reason: str = "") -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass
        prev = str(self._client.base_url)
        self._base_idx = (self._base_idx + 1) % len(self._base_urls)
        new = self._base_urls[self._base_idx]
        # 记录轮换原因，便于排障
        print(f"[binance] rotate base: {prev} -> {new} (reason={reason})")
        self._client = self._build_client(new)

    async def aclose(self):
        await self._client.aclose()

    async def _get_json(self, path: str, *, params: Optional[Dict[str, Any]] = None, allow_rotate: bool = True) -> Any:
        """基础 GET 封装：在遇到 302/403/418/451/429 时尝试端点轮换并重试。
        注意：不使用 follow_redirects，以便识别到重定向到 www.binance.com 的风控场景。
        """
        attempts = 0
        max_attempts = len(self._base_urls) * 3  # 每个端点最多尝试3次，提升韧性
        last_exc: Optional[Exception] = None
        while attempts < max_attempts:
            try:
                r = await self._client.get(path, params=params)
                # 明确拦截风控/跳转/限流
                sc = r.status_code
                if sc == 200:
                    # 仍可能返回 HTML（被 WAF 拦截但返回 200），尝试检查内容类型
                    ctype = r.headers.get("Content-Type", "").lower()
                    if "application/json" in ctype or "json" in ctype:
                        return r.json()
                    # 非 JSON 内容，视为风控，切换端点
                    if allow_rotate and len(self._base_urls) > 1:
                        # 记录为最后异常，便于抛出更有信息量的错误
                        try:
                            preview = r.text[:160]
                        except Exception:
                            preview = "<no-body>"
                        cur = str(self._client.base_url)
                        last_exc = RuntimeError(
                            f"Non-JSON 200 from {cur}{path} content-type={ctype} preview={preview!r}"
                        )
                        await self._rotate_base("non-json-200")
                        attempts += 1
                        await asyncio.sleep(random.uniform(0.2, 0.6))
                        continue
                    r.raise_for_status()
                elif sc in (301, 302, 307, 308, 403, 451):
                    if allow_rotate and len(self._base_urls) > 1:
                        await self._rotate_base(f"status-{sc}")
                        attempts += 1
                        await asyncio.sleep(random.uniform(0.3, 0.9))
                        continue
                    r.raise_for_status()
                elif sc == 418:
                    # 418: "I'm a teapot"通常是 WAF 轻量限流，优先本端点重试并退避
                    # 若反复 418 再考虑轮换，避免把正常端点标记为不可用
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    attempts += 1
                    if attempts % 3 == 0 and allow_rotate and len(self._base_urls) > 1:
                        await self._rotate_base(f"status-418-after-retry")
                    continue
                elif sc == 429:
                    # 限流，退避更长时间；若当前端点多次 429，考虑轮换
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    attempts += 1
                    if attempts % 2 == 0 and allow_rotate and len(self._base_urls) > 1:
                        await self._rotate_base(f"status-429-after-retry")
                    continue
                else:
                    r.raise_for_status()
            except httpx.HTTPStatusError as e:
                last_exc = e
                if allow_rotate and len(self._base_urls) > 1:
                    await self._rotate_base("HTTPStatusError")
                    attempts += 1
                    await asyncio.sleep(random.uniform(0.3, 0.9))
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ReadError) as e:
                last_exc = e
                # 连接/读取/超时异常：短暂等待后重试，必要时轮换
                if allow_rotate and len(self._base_urls) > 1:
                    await self._rotate_base(f"net-error-{type(e).__name__}")
                attempts += 1
                await asyncio.sleep(random.uniform(0.5, 1.2))
                continue

        # 仍失败：抛出最后一次异常或通用错误
        if last_exc:
            raise last_exc
        cur = str(self._client.base_url)
        raise RuntimeError(f"Failed to fetch JSON from Binance after rotating endpoints. last_base={cur} path={path}")

    @retry(wait=wait_random_exponential(multiplier=0.5, max=5), stop=stop_after_attempt(3))
    async def exchange_info(self) -> Dict[str, Any]:
        # 小抖动，避免多实例同步打点
        await asyncio.sleep(random.uniform(0.03, 0.08))
        return await self._get_json("/fapi/v1/exchangeInfo")

    @retry(wait=wait_random_exponential(multiplier=0.5, max=5), stop=stop_after_attempt(3))
    async def klines(self, symbol: str, interval: str = "1m", limit: int = 500, startTime: Optional[int] = None, endTime: Optional[int] = None) -> List[List[Any]]:
        params: Dict[str, Any] = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        # 为密集请求增加细微抖动，避免模式化触发 WAF；不影响总体吞吐。
        await asyncio.sleep(random.uniform(0.03, 0.12))
        return await self._get_json("/fapi/v1/klines", params=params)

    @retry(wait=wait_random_exponential(multiplier=0.5, max=5), stop=stop_after_attempt(3))
    async def ticker_price_all(self) -> List[Dict[str, str]]:
        await asyncio.sleep(random.uniform(0.02, 0.06))
        return await self._get_json("/fapi/v1/ticker/price")


async def fetch_usdt_perp_symbols(client: BinanceFuturesClient) -> List[str]:
    info = await client.exchange_info()
    syms: List[str] = []
    for s in info.get("symbols", []):
        if (
            s.get("quoteAsset") == "USDT"
            and s.get("contractType") == "PERPETUAL"
            and s.get("status") == "TRADING"
        ):
            syms.append(s["symbol"])
    return syms


async def fetch_midnight_close(client: BinanceFuturesClient, symbol: str, midnight_utc_ms: int) -> Optional[float]:
    # 获取本地0点那一根1mK线（openTime == midnight_utc_ms）
    # 若直接limit=1可能拿到下一根，保险起见limit=2并检查openTime。
    kl = await client.klines(symbol, interval="1m", limit=2, startTime=midnight_utc_ms)
    for k in kl:
        # kline: [openTime, open, high, low, close, volume, closeTime, ...]
        if int(k[0]) == midnight_utc_ms:
            return float(k[4])
    # 若未命中，尝试取第一根作为最接近0点后的第一根
    if kl:
        return float(kl[0][4])
    return None


async def fetch_latest_closed_kline(client: BinanceFuturesClient, symbol: str) -> Optional[Tuple[int, float, float, float, float, float]]:
    # 取最近2根，第一根是已收盘的倒数第二根，第二根可能未收盘
    kl = await client.klines(symbol, interval="1m", limit=2)
    if not kl:
        return None
    if len(kl) == 1:
        k = kl[0]
    else:
        k = kl[-2]  # 上一根（已收盘）
    # 返回 (openTime, open, high, low, close, quoteVolume)
    quote_vol = float(k[7]) if len(k) > 7 else 0.0
    return (int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), quote_vol)


async def fetch_recent_closes(client: BinanceFuturesClient, symbol: str, limit: int = 600) -> List[Tuple[int, float]]:
    kl = await client.klines(symbol, interval="1m", limit=limit)
    return [(int(k[0]), float(k[4])) for k in kl]
