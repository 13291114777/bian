# 云服务器部署 - 快速开始指南

## 📋 前置准备清单

- [ ] 云服务器（推荐：阿里云/腾讯云香港轻量服务器，24-25元/月）
- [ ] SSH客户端（Windows 10+自带，或安装PuTTY）
- [ ] 服务器IP地址和登录密码/密钥
- [ ] 本地项目代码已就绪

## 🚀 5分钟快速部署

### 步骤1: 购买云服务器（5分钟）

**阿里云轻量应用服务器**（推荐）

1. 访问: https://www.aliyun.com/product/swas
2. 选择配置:
   - 地域: **中国香港** (对Binance友好，延迟低)
   - 镜像: **Ubuntu 22.04**
   - 套餐: **2核2GB, 30GB SSD** (24元/月)
3. 购买完成后，在控制台:
   - 记录**公网IP地址**
   - 重置/设置**root密码**

### 步骤2: 连接服务器（1分钟）

**Windows PowerShell**
```powershell
# 替换为你的服务器IP
ssh root@your_server_ip
# 输入密码后回车
```

### 步骤3: 创建工作用户（2分钟）

```bash
# 创建用户
adduser monitor
# 输入密码（两次）和用户信息（可直接回车跳过）

# 添加sudo权限
usermod -aG sudo monitor

# 切换到新用户
su - monitor
```

### 步骤4: 上传部署脚本（1分钟）

**返回Windows PowerShell（新窗口）**
```powershell
# 上传自动部署脚本
scp "C:\Users\Administrator\Desktop\实时监测\deploy\server_setup.sh" monitor@your_server_ip:~/
```

### 步骤5: 上传项目代码（2分钟）

**方式A: 压缩上传（推荐）**
```powershell
# 1. 在本地打包（排除.venv和logs）
cd "C:\Users\Administrator\Desktop\实时监测"
Compress-Archive -Path * -DestinationPath "$env:USERPROFILE\Desktop\monitor.zip" -Force

# 2. 上传到服务器
scp "$env:USERPROFILE\Desktop\monitor.zip" monitor@your_server_ip:~/
```

**方式B: 使用Git（可选）**
```bash
# 在服务器上执行
git clone https://github.com/your_username/your_repo.git ~/binance-monitor
```

### 步骤6: 服务器端部署（5分钟）

**在SSH会话中执行**
```bash
# 创建项目目录
mkdir -p ~/binance-monitor
cd ~/binance-monitor

# 如果使用压缩包方式
unzip ~/monitor.zip
rm ~/monitor.zip

# 运行部署脚本
chmod +x ~/server_setup.sh
./server_setup.sh
```

脚本会自动完成:
- ✅ 安装Python 3.11和依赖
- ✅ 创建虚拟环境
- ✅ 安装项目依赖包
- ✅ 配置systemd服务
- ✅ 设置开机自启
- ✅ 启动监控服务

### 步骤7: 验证运行（1分钟）

```bash
# 查看服务状态
sudo systemctl status binance-monitor

# 查看实时日志
tail -f ~/binance-monitor/monitor.log

# 查看事件日志
cat ~/binance-monitor/logs/alerts.csv
```

## 🎯 完成！

现在监控系统已在云服务器24小时运行。

## 📊 日常管理

### 使用Windows管理脚本（推荐）

```powershell
# 1. 编辑配置
notepad "C:\Users\Administrator\Desktop\实时监测\deploy\manage_server.ps1"
# 修改前3行的服务器IP、用户名等信息

# 2. 运行管理工具
powershell -ExecutionPolicy Bypass -File "C:\Users\Administrator\Desktop\实时监测\deploy\manage_server.ps1"
```

管理功能:
- 🚀 一键上传代码更新
- 📥 定期下载日志到本地
- 📊 查看服务器状态
- 🔄 重启/停止/启动服务
- 🔧 快速SSH连接

### 常用命令速查

```bash
# === 服务管理 ===
sudo systemctl start binance-monitor    # 启动
sudo systemctl stop binance-monitor     # 停止
sudo systemctl restart binance-monitor  # 重启
sudo systemctl status binance-monitor   # 状态

# === 日志查看 ===
tail -f ~/binance-monitor/monitor.log              # 实时主日志
tail -f ~/binance-monitor/logs/alerts.csv          # 实时事件
sudo journalctl -u binance-monitor -f              # systemd日志
sudo journalctl -u binance-monitor -n 100          # 最近100行

# === 调整参数 ===
sudo vim /etc/systemd/system/binance-monitor.service  # 编辑服务配置
sudo systemctl daemon-reload                           # 重载配置
sudo systemctl restart binance-monitor                 # 应用更改

# === 磁盘管理 ===
df -h                                    # 查看磁盘空间
du -sh ~/binance-monitor/logs/*          # 查看日志大小
find ~/binance-monitor/logs -name "*.gz" -mtime +7 -delete  # 清理7天前日志
```

## 🔧 参数优化建议

### 低成本方案（降低API调用）
```bash
# 编辑服务配置
sudo vim /etc/systemd/system/binance-monitor.service

# 修改 ExecStart 行:
ExecStart=... \
  --interval-seconds 60 \      # 增大间隔到60秒
  --concurrency 5 \             # 降低并发到5
  --no-ws \                     # 关闭WebSocket（更稳定）
  ...
```

### 高频方案（最快响应）
```bash
ExecStart=... \
  --interval-seconds 10 \       # 10秒间隔
  --ws \                        # 启用WebSocket
  --concurrency 20 \            # 提高并发
  ...
```

### 仅交易时段运行（省成本）
```bash
# 添加定时任务
crontab -e

# UTC时间 0:00启动，23:59停止（对应北京时间8:00-次日7:59）
0 0 * * * sudo systemctl start binance-monitor
59 23 * * * sudo systemctl stop binance-monitor
```

## 📥 下载日志到本地

### 方式1: 使用管理脚本（推荐）
```powershell
# 运行管理工具，选择 "2. 下载日志"
powershell -ExecutionPolicy Bypass -File "C:\Users\Administrator\Desktop\实时监测\deploy\manage_server.ps1"
```

### 方式2: 手动SCP下载
```powershell
# 下载所有日志
scp -r monitor@your_server_ip:~/binance-monitor/logs/* "C:\Users\Administrator\Desktop\monitor_logs\"

# 下载主日志
scp monitor@your_server_ip:~/binance-monitor/monitor.log "C:\Users\Administrator\Desktop\monitor.log"
```

### 方式3: 定时自动下载（Windows计划任务）
```powershell
# 创建下载脚本
@"
scp -r monitor@your_server_ip:~/binance-monitor/logs/* C:\monitor_logs\$(Get-Date -Format 'yyyyMMdd')
"@ | Out-File -FilePath "$env:USERPROFILE\Desktop\download_logs.ps1"

# 添加到Windows任务计划（每天凌晨1点）
# 打开"任务计划程序" -> 创建基本任务 -> 选择上述脚本
```

## 🛡️ 安全加固（可选）

### 1. 更改SSH端口
```bash
sudo vim /etc/ssh/sshd_config
# 修改: Port 22222
sudo systemctl restart sshd

# 防火墙放行新端口
sudo ufw allow 22222/tcp
sudo ufw enable
```

### 2. 配置SSH密钥登录（更安全）
```powershell
# Windows生成密钥（如果没有）
ssh-keygen -t rsa -b 4096

# 上传公钥
type $env:USERPROFILE\.ssh\id_rsa.pub | ssh monitor@your_server_ip "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# 之后可免密登录
ssh monitor@your_server_ip
```

### 3. 禁用root登录
```bash
sudo vim /etc/ssh/sshd_config
# 修改: PermitRootLogin no
sudo systemctl restart sshd
```

## ❓ 常见问题

### Q1: 服务启动失败
```bash
# 查看详细错误
sudo journalctl -u binance-monitor -n 50 --no-pager

# 常见原因:
# 1. 依赖未安装 -> 重新运行 pip install -r requirements.txt
# 2. 权限问题 -> sudo chown -R monitor:monitor ~/binance-monitor
# 3. 端口占用 -> lsof -i :8080
```

### Q2: 依然遇到418限频
```bash
# 方案1: 等待5-10分钟后重试
# 方案2: 换区域（新加坡/日本服务器）
# 方案3: 降低频率
#   编辑配置: sudo vim /etc/systemd/system/binance-monitor.service
#   改为: --interval-seconds 60 --concurrency 5
```

### Q3: 磁盘空间不足
```bash
# 查看空间
df -h

# 清理旧日志
find ~/binance-monitor/logs -name "*.csv" -mtime +7 -delete
find ~/binance-monitor/logs -name "*.jsonl" -mtime +7 -delete

# 启用自动清理（已在部署脚本中配置logrotate）
```

### Q4: 内存不足
```bash
# 查看内存使用
free -h

# 添加2GB swap（临时方案）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 持久化（重启后生效）
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Q5: 如何更新代码
```powershell
# 方式1: 使用管理脚本（推荐）
# 运行管理工具，选择 "1. 上传代码"

# 方式2: Git拉取
ssh monitor@your_server_ip
cd ~/binance-monitor
git pull
sudo systemctl restart binance-monitor

# 方式3: 手动上传
scp -r "C:\Users\Administrator\Desktop\实时监测\*" monitor@your_server_ip:~/binance-monitor/
ssh monitor@your_server_ip "sudo systemctl restart binance-monitor"
```

## 💰 成本估算

| 配置 | 价格 | 适用场景 |
|------|------|---------|
| 阿里云香港 2核2GB | 24元/月 | 推荐，稳定可靠 |
| 腾讯云香港 2核2GB | 25元/月 | 备选，性能相近 |
| Vultr新加坡 1核1GB | $6/月 | 国际支付，按小时计费 |
| AWS Lightsail | $5/月 | 需国际信用卡 |

**年费**: 约 300元/年（阿里云/腾讯云）

## 🎓 进阶功能

### 1. 多实例负载均衡
- 部署2-3个相同服务器
- 使用nginx做负载均衡
- 实现高可用性

### 2. 数据持久化到数据库
- 安装PostgreSQL/MySQL
- 修改events.py支持数据库写入
- 使用Grafana可视化

### 3. 实时通知集成
- 飞书/钉钉/企业微信 Webhook
- Telegram Bot
- 邮件/短信告警

### 4. Web控制面板
- Flask/FastAPI后端API
- React/Vue前端界面
- 实时图表展示

## 📞 技术支持

如遇问题，请提供以下信息:
- 服务器系统版本: `cat /etc/os-release`
- Python版本: `python3.11 --version`
- 错误日志: `sudo journalctl -u binance-monitor -n 100`

---

**祝运行顺利！** 🚀
