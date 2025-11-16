# 云服务器部署指南

## 一、云服务器选型与购买

### 推荐配置

**基础配置（适合单实例监控）**
- CPU: 1-2核
- 内存: 2GB
- 带宽: 1-3Mbps
- 系统: Ubuntu 22.04 LTS / Debian 11
- 地域: 香港/新加坡/日本（靠近币安服务器，延迟低）

**推荐云服务商**
1. **阿里云** - 香港轻量应用服务器（24元/月起）
2. **腾讯云** - 香港轻量应用服务器（25元/月起）
3. **AWS Lightsail** - 新加坡节点（$5/月，需国际信用卡）
4. **Vultr** - 东京/新加坡节点（$6/月）

### 购买步骤（以阿里云为例）

1. 访问 [阿里云轻量应用服务器](https://www.aliyun.com/product/swas)
2. 选择配置：
   - 地域：中国香港
   - 镜像：Ubuntu 22.04
   - 套餐：2核2GB（24元/月）
3. 购买后记录：
   - 公网IP地址
   - root密码（或使用密钥对）

## 二、服务器初始化配置

### 1. 连接服务器

**Windows (使用 PowerShell)**
```powershell
# 方式1: SSH命令（Win10+自带）
ssh root@your_server_ip

# 方式2: 使用 PuTTY
# 下载: https://www.putty.org/
# 输入IP和端口22，点击Open
```

### 2. 系统更新与依赖安装

```bash
# 更新系统
apt update && apt upgrade -y

# 安装必要工具
apt install -y python3.11 python3.11-venv python3-pip git curl wget vim screen unzip

# 验证Python版本
python3.11 --version  # 应显示 3.11.x
```

### 3. 创建工作用户（安全实践）

以下操作必须使用 root 身份执行（先用 Windows 端 `ssh root@your_server_ip` 登录）。

```bash
# 1) 创建专用用户（root 执行）
adduser monitor

# 2) 将 monitor 加入 sudo 组（root 执行）
usermod -aG sudo monitor

# 3) 如遇 "cannot lock /etc/passwd"（上一条命令被中断留下锁），请确保没有并发的用户管理命令在运行，
#    然后清理残留锁文件后重试（root 执行，谨慎操作）：
ls -l /etc/passwd.lock /etc/shadow.lock /etc/group.lock /etc/gshadow.lock 2>/dev/null || true
rm -f /etc/passwd.lock /etc/shadow.lock /etc/group.lock /etc/gshadow.lock
usermod -aG sudo monitor

# 4) 验证组成员
id monitor
getent group sudo

# 5) 退出 root（或另开终端），以 monitor 身份重新登录后再使用 sudo
exit
```

### 4. 配置 SSH 公钥登录（Windows 一键）

推荐在 Windows 本机生成或复用公钥，并写入服务器上 `monitor` 用户的 `authorized_keys`，后续即可免密登录。

```powershell
# Windows 端：如果还没有密钥，先生成（推荐 ed25519）
ssh-keygen -t ed25519 -C "monitor@aliyun"

# Windows 端：将本机公钥写入服务器（用 root 账户接收并写到 monitor 名下）
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@your_server_ip "install -d -m 700 -o monitor -g monitor /home/monitor/.ssh; cat >> /home/monitor/.ssh/authorized_keys; chown monitor:monitor /home/monitor/.ssh/authorized_keys; chmod 600 /home/monitor/.ssh/authorized_keys"
```

备选方案（服务器端直接复制 root 的公钥到 monitor）：

```bash
# 在服务器用 root 执行（如果 root 已配置了 authorized_keys）
install -d -m 700 -o monitor -g monitor /home/monitor/.ssh
cp /root/.ssh/authorized_keys /home/monitor/.ssh/authorized_keys
chown monitor:monitor /home/monitor/.ssh/authorized_keys
chmod 600 /home/monitor/.ssh/authorized_keys
```

提示：上面命令中的 -o/-g 需要 root 权限。如果你当前在 monitor 会话下操作，请在命令前加 sudo，或使用以下等价方式：

```bash
# 以 monitor 身份创建目录与权限（无需 -o/-g）
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 如需从 root 复制 authorized_keys，需要 sudo 权限
sudo cp /root/.ssh/authorized_keys ~/.ssh/authorized_keys
sudo chown monitor:monitor ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 5. 验证免密与 sudo

```powershell
# Windows 端验证免密
ssh monitor@your_server_ip
```

```bash
# 登录后验证 sudo 能力（应不再提示 Permission denied）
sudo -l
```

## 三、代码部署

### 方式1: 使用 Git（推荐）

```bash
# 1. 在本地创建Git仓库（Windows）
cd C:\Users\Administrator\Desktop\实时监测
git init
git add .
git commit -m "Initial commit"

# 2. 推送到远程仓库（GitHub/Gitee）
# GitHub: https://github.com/new
# Gitee: https://gitee.com/projects/new

# 3. 服务器上克隆
cd ~
git clone https://github.com/your_username/your_repo.git monitor
cd monitor
```

### 方式2: 直接传输（简单快速）

**Windows 使用 SCP**

注意：
- 不要在 IP 周围使用尖括号 <>；直接写 IP，例如 43.103.51.65。
- 如果 SSH 端口不是 22，用 `-P` 指定端口，例如 `-P 22222`。
- 可直接用 `monitor` 账户上传：`scp <文件> monitor@<IP>:/home/monitor/`。

示例：
```powershell
# 打包项目（排除 .venv 和 logs）
cd C:\Users\Administrator\Desktop\实时监测
# 手动压缩为 monitor.zip（排除 .venv, logs, __pycache__）

# 使用 WinSCP 或命令上传（22 端口）
scp monitor.zip monitor@your_server_ip:/home/monitor/
# 如端口为 22222：
# scp -P 22222 monitor.zip monitor@your_server_ip:/home/monitor/
```

**服务器解压**
```bash
cd /home/monitor
unzip monitor.zip
cd 实时监测  # 或你的项目目录名
```

## 四、环境配置与运行

### 1. 创建虚拟环境

```bash
cd /home/monitor/实时监测

# 创建虚拟环境
python3.11 -m venv .venv

# 激活环境
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

```bash
# 创建环境变量文件
cat > .env << 'EOF'
# BINANCE_BASE_URL=https://fapi.binance.com
# 说明：客户端已内置 fapi/fapi2/fapi3/fapi4 端点自动轮换与重试，
# 若未特殊需要，建议暂时不要显式设置 BINANCE_BASE_URL，
# 以便在遇到 302/403/418/451/429 时自动切换端点。
# 其他可选配置
# PROXY_URL=http://proxy.example.com:8080  # 如需走可信代理可开启（支持 http/https/socks5）
# HTTP2=off  # 若服务器未安装 h2，建议关闭 HTTP/2；留空则自动检测
EOF

# 加载环境变量
source .env
```

### 3. 测试运行

```bash
# 单次运行测试
.venv/bin/python -m realtime_monitor.main \
  --once \
  --scan-all \
  --ws \
  --interval-seconds 20 \
  --confirm-candles 5 \
  --delta-columns 1,5,15 \
  --events-dir logs \
  --min-price 0.01 \
  --min-quote-usdt 50000 \
  --secondary-by weighted \
  --weights 1,0.5,0.25

# 查看是否有输出和日志文件
ls -lh logs/
```

## 五、后台持久运行方案

### 方案A: systemd服务（推荐，开机自启）

```bash
# 1. 创建服务文件
sudo vim /etc/systemd/system/binance-monitor.service
```

**服务配置内容：**
```ini
[Unit]
Description=Binance Futures Real-time Monitor
After=network.target

[Service]
Type=simple
User=monitor
WorkingDirectory=/home/monitor/实时监测
Environment="PATH=/home/monitor/实时监测/.venv/bin:/usr/bin"
ExecStart=/home/monitor/实时监测/.venv/bin/python -m realtime_monitor.main \
  --scan-all \
  --ws \
  --interval-seconds 20 \
  --confirm-candles 5 \
  --delta-columns 1,5,15 \
  --events-dir logs \
  --min-price 0.01 \
  --min-quote-usdt 50000 \
  --secondary-by weighted \
  --weights 1,0.5,0.25 \
  --concurrency 10 \
  --cooldown-seconds 300

# 自动重启策略
Restart=always
RestartSec=10

# 日志
StandardOutput=append:/home/monitor/实时监测/monitor.log
StandardError=append:/home/monitor/实时监测/monitor_error.log

[Install]
WantedBy=multi-user.target
```

**启动服务：**
```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start binance-monitor

# 设置开机自启
sudo systemctl enable binance-monitor

# 查看状态
sudo systemctl status binance-monitor

# 查看日志
sudo journalctl -u binance-monitor -f

# 停止服务
sudo systemctl stop binance-monitor

# 重启服务
sudo systemctl restart binance-monitor
```

### 方案B: Screen会话（简单，手动管理）

```bash
# 1. 创建启动脚本
cat > ~/start_monitor.sh << 'EOF'
#!/bin/bash
cd /home/monitor/实时监测
source .venv/bin/activate
python -m realtime_monitor.main \
  --scan-all \
  --ws \
  --interval-seconds 20 \
  --confirm-candles 5 \
  --delta-columns 1,5,15 \
  --events-dir logs \
  --min-price 0.01 \
  --min-quote-usdt 50000 \
  --secondary-by weighted \
  --weights 1,0.5,0.25 \
  --concurrency 10 \
  --cooldown-seconds 300
EOF

chmod +x ~/start_monitor.sh

# 2. 启动screen会话
screen -S monitor
./start_monitor.sh

# 3. 退出screen（保持后台运行）
# 按 Ctrl+A 然后按 D

# 4. 重新连接会话
screen -r monitor

# 5. 查看所有会话
screen -ls

# 6. 结束会话（先连接，然后Ctrl+C停止程序，再输入exit）
```

### 方案C: nohup（最简单，无交互）

```bash
# 后台运行
nohup .venv/bin/python -m realtime_monitor.main \
  --scan-all \
  --ws \
  --interval-seconds 20 \
  --confirm-candles 5 \
  --delta-columns 1,5,15 \
  --events-dir logs \
  --min-price 0.01 \
  --min-quote-usdt 50000 \
  --secondary-by weighted \
  --weights 1,0.5,0.25 \
  > monitor.log 2>&1 &

# 查看进程
ps aux | grep realtime_monitor

# 停止进程（找到PID后）
kill <PID>
```

## 六、日志与监控

### 1. 实时查看日志

```bash
# 方式1: tail命令
tail -f /home/monitor/实时监测/monitor.log

# 方式2: systemd日志
sudo journalctl -u binance-monitor -f

# 方式3: 事件日志
tail -f /home/monitor/实时监测/logs/alerts.csv
```

### 2. 日志轮转（防止磁盘占满）

```bash
# 创建logrotate配置
sudo vim /etc/logrotate.d/binance-monitor
```

**配置内容：**
```
/home/monitor/实时监测/monitor.log
/home/monitor/实时监测/monitor_error.log
/home/monitor/实时监测/logs/alerts.csv
/home/monitor/实时监测/logs/alerts.jsonl {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 monitor monitor
    postrotate
        systemctl reload binance-monitor > /dev/null 2>&1 || true
    endscript
}
```

### 3. 磁盘空间监控

```bash
# 创建磁盘检查脚本
cat > ~/check_disk.sh << 'EOF'
#!/bin/bash
THRESHOLD=80
USAGE=$(df -h /home | tail -1 | awk '{print $5}' | sed 's/%//')

if [ $USAGE -gt $THRESHOLD ]; then
    echo "警告：磁盘使用率 ${USAGE}% 超过阈值 ${THRESHOLD}%"
    # 清理7天前的日志
    find /home/monitor/实时监测/logs -name "*.gz" -mtime +7 -delete
fi
EOF

chmod +x ~/check_disk.sh

# 添加到crontab（每天检查）
crontab -e
# 添加行：0 3 * * * /home/monitor/check_disk.sh
```

## 七、远程访问事件数据

### 方案A: HTTP文件服务（简单）

```bash
# 安装nginx
sudo apt install -y nginx

# 配置静态文件服务
sudo vim /etc/nginx/sites-available/monitor
```

**nginx配置：**
```nginx
server {
    listen 8080;
    server_name _;
    
    location /logs/ {
        alias /home/monitor/实时监测/logs/;
        autoindex on;
        auth_basic "Monitor Logs";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

```bash
# 创建密码文件
sudo apt install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin

# 启用配置
sudo ln -s /etc/nginx/sites-available/monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 访问: http://your_server_ip:8080/logs/
```

### 方案B: SCP定期下载（安全）

**Windows定时任务脚本：**
```powershell
# 保存为 download_logs.ps1
$SERVER = "your_server_ip"
$USER = "monitor"
$REMOTE_PATH = "/home/monitor/实时监测/logs/"
$LOCAL_PATH = "C:\Users\Administrator\Desktop\monitor_logs\"

# 使用SCP下载（需配置SSH密钥）
scp -r ${USER}@${SERVER}:${REMOTE_PATH} $LOCAL_PATH

# 添加到Windows任务计划（每小时执行）
# 打开"任务计划程序" -> 创建基本任务 -> 选择脚本
```

### 方案C: 实时推送到数据库（高级）

参考后续章节"数据持久化增强"。

## 八、安全加固

### 1. SSH安全配置

```bash
# 编辑SSH配置
sudo vim /etc/ssh/sshd_config

# 修改以下项：
# Port 22222  # 更改默认端口
# PermitRootLogin no  # 禁止root登录
# PasswordAuthentication no  # 仅允许密钥登录

# 重启SSH服务
sudo systemctl restart sshd
```

### 2. 防火墙配置

```bash
# 安装ufw
sudo apt install -y ufw

# 允许SSH（如果改了端口，改成新端口）
sudo ufw allow 22/tcp

# 如果配置了nginx
sudo ufw allow 8080/tcp

# 启用防火墙
sudo ufw enable
```

### 3. 配置SSH密钥（Windows）

```powershell
# 生成密钥对（如果没有）
ssh-keygen -t rsa -b 4096

# 上传公钥到服务器
type $env:USERPROFILE\.ssh\id_rsa.pub | ssh root@your_server_ip "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# 之后可免密登录
ssh monitor@your_server_ip
```

## 九、故障排查

### 常见问题

**1. 服务启动失败**
```bash
# 查看详细日志
sudo journalctl -u binance-monitor -n 50 --no-pager

# 检查权限
ls -la /home/monitor/实时监测
sudo chown -R monitor:monitor /home/monitor/实时监测
```

**2. 依然遇到 302/418/403（被风控或跳转）**
```bash
# 程序已内置端点轮换（fapi / fapi2 / fapi3 / fapi4）。如仍持续失败：
# 1) 暂时不要设置 BINANCE_BASE_URL，让内置轮换生效
# 2) 关闭 HTTP/2：导出 HTTP2=off
# 3) 降低并发、拉长间隔、去掉 --ws（改走 REST）
# 4) 几分钟后再试，或更换地域/云厂商
# 5) 如条件允许，配置可信代理：设置 PROXY_URL=http(s):// 或 socks5://

# 额外排查：检测 IP 与连通性
curl -I https://fapi.binance.com/fapi/v1/exchangeInfo

# 尝试更换地域的服务器（香港 -> 新加坡 -> 日本）
```

**3. 内存不足**
```bash
# 检查内存使用
free -h
htop

# 添加swap（临时方案）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**4. WebSocket连接频繁断开**
```bash
# 检查网络稳定性
ping -c 10 fstream.binance.com

# 关闭WS改用纯REST（更稳定但更慢）
# 启动时去掉 --ws 参数
```

## 十、成本优化

### 按需启动策略

```bash
# 创建cron定时任务（仅交易时段运行）
crontab -e

# 添加：UTC时间 0:00-23:59 运行（北京时间 8:00-次日7:59）
0 0 * * * systemctl start binance-monitor
59 23 * * * systemctl stop binance-monitor
```

### 流量优化

- 使用 `--ws` 模式减少REST调用
- 增大 `--interval-seconds` 到 30-60 秒
- 降低 `--concurrency` 到 5-10

## 十一、数据持久化增强（可选）

### 使用SQLite本地存储

```bash
# 在服务器安装SQLite
sudo apt install -y sqlite3

# 创建数据库表（项目后续可增强）
sqlite3 ~/monitor_data.db << 'EOF'
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER,
    ts_iso TEXT,
    symbol TEXT,
    kind TEXT,
    direction TEXT,
    open_time INTEGER,
    price REAL,
    ema21 REAL,
    high REAL,
    low REAL,
    quote_volume REAL,
    confirm_candles INTEGER,
    message TEXT
);
CREATE INDEX idx_symbol ON alerts(symbol);
CREATE INDEX idx_ts ON alerts(ts);
EOF

# 定期导入CSV到数据库
# （需要额外脚本，后续可提供）
```

## 十二、快速部署脚本（一键安装）

```bash
# 服务器端保存为 setup.sh
cat > ~/setup.sh << 'EOF'
#!/bin/bash
set -e

echo "=== 开始部署币安监控系统 ==="

# 1. 更新系统
echo "1/6 更新系统..."
sudo apt update && sudo apt upgrade -y

# 2. 安装依赖
echo "2/6 安装依赖..."
sudo apt install -y python3.11 python3.11-venv python3-pip git screen

# 3. 克隆代码（修改为你的仓库地址）
echo "3/6 克隆代码..."
cd ~
# git clone https://github.com/your_username/your_repo.git monitor
# cd monitor

# 4. 安装Python依赖
echo "4/6 安装Python依赖..."
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. 测试运行
echo "5/6 测试运行..."
.venv/bin/python -m realtime_monitor.main --once

# 6. 配置systemd服务
echo "6/6 配置systemd服务..."
sudo tee /etc/systemd/system/binance-monitor.service > /dev/null << 'SERVICE'
[Unit]
Description=Binance Futures Monitor
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/实时监测
Environment="PATH=$HOME/实时监测/.venv/bin:/usr/bin"
ExecStart=$HOME/实时监测/.venv/bin/python -m realtime_monitor.main \
  --scan-all --ws --interval-seconds 20 --confirm-candles 5 \
  --delta-columns 1,5,15 --events-dir logs \
  --min-price 0.01 --min-quote-usdt 50000 \
  --secondary-by weighted --weights 1,0.5,0.25
Restart=always
RestartSec=10
StandardOutput=append:$HOME/实时监测/monitor.log
StandardError=append:$HOME/实时监测/monitor_error.log

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable binance-monitor
sudo systemctl start binance-monitor

echo "=== 部署完成！ ==="
echo "查看状态: sudo systemctl status binance-monitor"
echo "查看日志: tail -f ~/实时监测/monitor.log"
EOF

chmod +x ~/setup.sh
```

## 总结

**推荐流程：**
1. 购买香港/新加坡轻量服务器（阿里云/腾讯云 24-25元/月）
2. 使用Git或SCP上传代码
3. 配置systemd服务实现开机自启和自动重启
4. 配置日志轮转防止磁盘占满
5. 通过nginx或定期SCP下载查看事件日志

**关键优势：**
- ✅ IP不会被频繁封禁（香港/新加坡节点对Binance友好）
- ✅ 24小时稳定运行，自动重启
- ✅ 低延迟（10-50ms vs 国内200-500ms）
- ✅ 成本可控（24元/月起）
- ✅ 可扩展（未来可部署多实例、数据库等）
