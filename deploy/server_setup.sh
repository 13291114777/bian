#!/bin/bash
# 币安监控系统 - 云服务器一键部署脚本
# 适用于 Ubuntu 22.04 / Debian 11

set -e

echo "=========================================="
echo "  币安永续合约实时监控系统 - 快速部署"
echo "=========================================="
echo ""

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then 
    echo "⚠️  请不要使用root用户运行此脚本"
    echo "建议: 创建普通用户后运行"
    echo "  adduser monitor"
    echo "  su - monitor"
    exit 1
fi

# 配置变量
INSTALL_DIR="$HOME/binance-monitor"
VENV_PATH="$INSTALL_DIR/.venv"
SERVICE_NAME="binance-monitor"

# 1. 更新系统
echo "📦 [1/7] 更新系统包..."
sudo apt update
sudo apt upgrade -y

# 2. 安装依赖
echo "🔧 [2/7] 安装系统依赖..."
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    wget \
    vim \
    screen \
    htop

# 验证Python版本
PYTHON_VERSION=$(python3.11 --version)
echo "✅ Python版本: $PYTHON_VERSION"

# 3. 创建项目目录
echo "📁 [3/7] 创建项目目录..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 4. 上传代码提示
echo "📤 [4/7] 代码上传方式:"
echo ""
echo "方式A - Git克隆（推荐）:"
echo "  git clone https://github.com/your_username/your_repo.git ."
echo ""
echo "方式B - SCP上传（本地执行）:"
echo "  # Windows PowerShell:"
echo "  scp -r C:\\Users\\Administrator\\Desktop\\实时监测\\* $USER@$(curl -s ifconfig.me):$INSTALL_DIR/"
echo ""
read -p "请完成代码上传后按Enter继续..."

# 检查必要文件
if [ ! -f "requirements.txt" ]; then
    echo "❌ 未找到 requirements.txt，请确保代码已上传"
    exit 1
fi

# 5. 创建Python虚拟环境
echo "🐍 [5/7] 创建Python虚拟环境..."
python3.11 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"

# 安装Python依赖
echo "📚 安装Python依赖包..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. 测试运行
echo "🧪 [6/7] 执行单次测试..."
"$VENV_PATH/bin/python" -m realtime_monitor.main --once --interval-seconds 20 --confirm-candles 5

if [ $? -eq 0 ]; then
    echo "✅ 测试运行成功！"
else
    echo "⚠️  测试运行失败，请检查配置"
    read -p "是否继续安装服务？(y/N) " -n 1 -r
    echo
    if [[ ! $REPL =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 7. 配置systemd服务
echo "⚙️  [7/7] 配置systemd服务..."

# 创建服务文件
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Binance USDT Perpetual Real-time Monitor
After=network.target
Documentation=https://github.com/your_username/your_repo

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_PATH/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"

# 主程序命令（可根据需要调整参数）
ExecStart=$VENV_PATH/bin/python -m realtime_monitor.main \\
  --scan-all \\
  --ws \\
  --interval-seconds 20 \\
  --confirm-candles 5 \\
  --delta-columns 1,5,15 \\
  --events-dir logs \\
  --min-price 0.01 \\
  --min-quote-usdt 50000 \\
  --secondary-by weighted \\
  --weights 1,0.5,0.25 \\
  --concurrency 10 \\
  --cooldown-seconds 300

# 自动重启策略
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# 日志输出
StandardOutput=append:$INSTALL_DIR/monitor.log
StandardError=append:$INSTALL_DIR/monitor_error.log

# 安全限制
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# 重载systemd配置
sudo systemctl daemon-reload

# 启用并启动服务
echo "🚀 启动服务..."
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

# 等待服务启动
sleep 3

# 检查服务状态
if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
    echo ""
    echo "=========================================="
    echo "✅ 部署成功！服务已启动"
    echo "=========================================="
    echo ""
    echo "📊 查看服务状态:"
    echo "  sudo systemctl status ${SERVICE_NAME}"
    echo ""
    echo "📋 查看实时日志:"
    echo "  tail -f $INSTALL_DIR/monitor.log"
    echo "  sudo journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo "📁 事件日志位置:"
    echo "  $INSTALL_DIR/logs/alerts.csv"
    echo "  $INSTALL_DIR/logs/alerts.jsonl"
    echo ""
    echo "🔧 管理命令:"
    echo "  启动: sudo systemctl start ${SERVICE_NAME}"
    echo "  停止: sudo systemctl stop ${SERVICE_NAME}"
    echo "  重启: sudo systemctl restart ${SERVICE_NAME}"
    echo "  禁用: sudo systemctl disable ${SERVICE_NAME}"
    echo ""
else
    echo ""
    echo "❌ 服务启动失败，请查看日志:"
    echo "  sudo journalctl -u ${SERVICE_NAME} -n 50"
    exit 1
fi

# 配置日志轮转
echo "🔄 配置日志轮转..."
sudo tee /etc/logrotate.d/${SERVICE_NAME} > /dev/null << EOF
$INSTALL_DIR/monitor.log
$INSTALL_DIR/monitor_error.log
$INSTALL_DIR/logs/*.csv
$INSTALL_DIR/logs/*.jsonl {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload ${SERVICE_NAME} > /dev/null 2>&1 || true
    endscript
}
EOF

echo "✅ 日志轮转配置完成"
echo ""
echo "🎉 全部完成！监控系统正在后台运行"
