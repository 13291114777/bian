# 实时监测（币安U本位永续）

功能概览：

- 以本地时间 0:00 为基准，计算所有USDT永续合约的涨跌幅；
- 每分钟更新：
  - 涨幅榜前50、跌幅榜前50（显示实时价格、涨跌幅与多周期 Δ% 列，默认 1m/5m/15m，可配置）；
  - 对入选币种实时计算 EMA13/EMA21/EMA72/EMA83；
  - 当 EMA13、EMA21 上/下穿 EMA72、EMA83 后，进入“确认窗口”（默认第5根K线，可配置）：
    - 多头：确认窗口内若价格回落但“未跌破”EMA21，于第N根收盘给出入场信号；
    - 空头：确认窗口内若价格反弹但“未涨破”EMA21，于第N根收盘给出入场信号；
    - 观察期内若出现“盘中穿越 EMA21 但收盘未站回/未下回”，会即时给出提示（与入场信号样式区分）。

说明：

- “以K线收盘”为准：EMA 与交叉判断基于 1m K线的收盘价；
- 观察窗口内“未跌破/未涨破”默认按K线的“最低/最高”与当根收盘EMA21比较（近似处理）；
- 排名以本地0点那根1m K线的收盘价为基准；
- 提供 REST 轮询与 WebSocket 两种模式：WS 模式可减少 REST 压力（订阅全量 1m kline，处理已收盘的数据）。

## 运行

1. 创建/激活虚拟环境（可选）并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

1. 快速运行（推荐参数）

仅冒烟一轮：

```powershell
.\.venv\Scripts\python.exe -m realtime_monitor.main --once --scan-all --ws --interval-seconds 20 --confirm-candles 5 --delta-columns 1,5,15 --events-dir logs --min-price 0.01 --min-quote-usdt 50000 --secondary-by weighted --weights 1,0.5,0.25
```

持续运行：

```powershell
.\.venv\Scripts\python.exe -m realtime_monitor.main --scan-all --ws --interval-seconds 20 --confirm-candles 5 --delta-columns 1,5,15 --events-dir logs --min-price 0.01 --min-quote-usdt 50000 --secondary-by weighted --weights 1,0.5,0.25
```

或直接运行根目录脚本（等价）：

```powershell
.\.venv\Scripts\python.exe .\run.py --scan-all --ws --interval-seconds 20 --confirm-candles 5 --delta-columns 1,5,15 --events-dir logs --min-price 0.01 --min-quote-usdt 50000 --secondary-by weighted --weights 1,0.5,0.25
```

运行后在控制台可看到：

- 并排的“涨幅/跌幅”前50列表（含可配置的 Δ% 列，如 1m/5m/15m）；
- 实时“提示（tip）/入场（signal）”，并可选 `--beep` 发声（Windows）。

## 事件持久化（CSV/JSONL）

- 通过 `--events-dir <dir>` 指定事件输出目录（默认 `logs`）。
- 生成文件：`alerts.csv` 与 `alerts.jsonl`。
- 典型字段：`symbol, kind (tip/signal), direction (up/down), open_time, price, ema21, high, low, quote_volume, confirm_candles, message, ts, ts_iso`。
- 关闭落盘：`--no-events`。

## 风险过滤与冷却

- `--min-price/--max-price`：过滤不在价格区间内的事件；
- `--min-quote-usdt`：按最近1m的报价成交额（USDT）过滤低流动性噪声；
- `--cooldown-seconds`：对同一交易对的提示/信号设置冷却时间，避免过于频繁。

## 二次排序与 Δ% 列

- `--delta-columns`：Δ% 列展示的分钟窗口（逗号分隔），默认 `1,5,15`；
- `--no-secondary-by-delta`：关闭二次排序；
- `--secondary-by {1m|5m|15m|weighted}`：二次排序来源；
- `--weights w1,w5,w15`：加权模式下的权重（对绝对值加权，突出波动强度）。

## 其他参数

- `--interval-seconds` 轮询间隔秒数，默认 20；
- `--confirm-candles` 上/下穿后确认K线根数，默认 5；
- `--scan-all` 跟踪“全部”USDT永续交易对进行EMA交叉扫描（默认仅跟踪当前榜单内的交易对）。
- `--concurrency` 并发请求最大数量（默认 20）；
- `--seed-limit` 初始化 EMA 的历史收盘数（默认 600，至少 100，需 ≥83 才能稳定计算 EMA83）；
- `--beep` Windows 上为“提示/入场信号”播放提示音。
- `--ws` 启用 1m kline WebSocket 聚合，降低 REST 压力。

## 注意

- 首次启动会为所有USDT永续拉取本地0点基准价格（每个交易对1次K线查询），随后每轮仅一次全量价格查询 + 入选币种的1m最新K线/或WS聚合；
- 若本机时间或时区不正确会影响0点基准；
- 本项目仅用于技术研究，不构成投资建议。

## 故障排查

- 若出现 `HTTP 418` / `302` 或短时间多次失败，通常为限频或临时封禁：
  - **优先方案**：等待 2-5 分钟再试（Binance 反爬规则会放宽），或降低 `--concurrency`、适当增大 `--interval-seconds`；
  - **备用方案**：通过环境变量切换域名（试验阶段，不保证成功）：

    ```powershell
    # 临时设置（仅当前会话）
    $env:BINANCE_BASE_URL = "https://fapi2.binance.com"  # 或 fapi3/fapi4
    .\.venv\Scripts\python.exe .\run.py --once --scan-all --ws ...
    ```

  - **高级方案**：配置可信代理（如 VPS/VPN），并为 httpx 设置代理与 User-Agent（需修改 `binance_client.py` 的 `__init__` 参数）。
- Windows 蜂鸣若报错，可去掉 `--beep`；
- 控制台乱码可尝试更换字体或使用支持 ANSI 的终端。
