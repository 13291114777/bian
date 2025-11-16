# Windows本地管理脚本 - 用于与云服务器交互

# 配置你的服务器信息
$SERVER_IP = "your_server_ip"          # 服务器公网IP
$SERVER_USER = "monitor"               # 服务器用户名
$SERVER_PATH = "/home/monitor/binance-monitor"  # 服务器项目路径
$LOCAL_PROJECT = "C:\Users\Administrator\Desktop\实时监测"  # 本地项目路径
$LOCAL_LOGS = "C:\Users\Administrator\Desktop\monitor_logs"  # 本地日志存储

# 颜色输出函数
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

# 显示菜单
function Show-Menu {
    Clear-Host
    Write-ColorOutput Yellow "=========================================="
    Write-ColorOutput Yellow "  币安监控系统 - 云服务器管理工具"
    Write-ColorOutput Yellow "=========================================="
    Write-Output ""
    Write-Output "服务器: $SERVER_IP"
    Write-Output "用户: $SERVER_USER"
    Write-Output ""
    Write-Output "1. 🚀 上传代码到服务器"
    Write-Output "2. 📥 下载日志到本地"
    Write-Output "3. 📊 查看服务器状态"
    Write-Output "4. 📋 查看实时日志"
    Write-Output "5. 🔄 重启监控服务"
    Write-Output "6. 🛑 停止监控服务"
    Write-Output "7. ▶️  启动监控服务"
    Write-Output "8. 🔧 SSH连接到服务器"
    Write-Output "9. 📦 打包项目（准备上传）"
    Write-Output "0. ❌ 退出"
    Write-Output ""
}

# 1. 上传代码
function Upload-Code {
    Write-ColorOutput Green "📤 开始上传代码..."
    
    # 检查本地项目
    if (-not (Test-Path $LOCAL_PROJECT)) {
        Write-ColorOutput Red "❌ 本地项目路径不存在: $LOCAL_PROJECT"
        return
    }
    
    # 排除不需要上传的文件
    $excludeItems = @(".venv", "logs", "__pycache__", "*.pyc", ".git", "*.log")
    
    # 使用rsync（如果安装了）或scp
    Write-Output "正在压缩..."
    $zipFile = "$env:TEMP\monitor_upload.zip"
    
    # 压缩（排除指定文件）
    $compress = @{
        Path = Get-ChildItem $LOCAL_PROJECT -Exclude $excludeItems
        DestinationPath = $zipFile
        Force = $true
    }
    Compress-Archive @compress
    
    Write-Output "正在上传到服务器..."
    scp $zipFile "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/monitor_update.zip"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Output "正在解压..."
        ssh "${SERVER_USER}@${SERVER_IP}" "cd $SERVER_PATH && unzip -o monitor_update.zip && rm monitor_update.zip"
        Write-ColorOutput Green "✅ 代码上传成功！"
        
        $restart = Read-Host "是否重启服务以应用更新？(Y/n)"
        if ($restart -ne 'n' -and $restart -ne 'N') {
            Restart-Service
        }
    } else {
        Write-ColorOutput Red "❌ 上传失败"
    }
    
    # 清理临时文件
    Remove-Item $zipFile -ErrorAction SilentlyContinue
}

# 2. 下载日志
function Download-Logs {
    Write-ColorOutput Green "📥 开始下载日志..."
    
    # 创建本地日志目录
    if (-not (Test-Path $LOCAL_LOGS)) {
        New-Item -ItemType Directory -Path $LOCAL_LOGS | Out-Null
    }
    
    # 添加时间戳
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $targetDir = "$LOCAL_LOGS\$timestamp"
    New-Item -ItemType Directory -Path $targetDir | Out-Null
    
    # 下载日志文件
    scp -r "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/logs/*" $targetDir
    scp "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/monitor.log" "$targetDir\monitor.log"
    scp "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/monitor_error.log" "$targetDir\monitor_error.log" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput Green "✅ 日志下载完成！"
        Write-Output "位置: $targetDir"
        
        $open = Read-Host "是否打开日志目录？(Y/n)"
        if ($open -ne 'n' -and $open -ne 'N') {
            explorer $targetDir
        }
    } else {
        Write-ColorOutput Red "❌ 下载失败"
    }
}

# 3. 查看状态
function Show-Status {
    Write-ColorOutput Green "📊 查询服务器状态..."
    Write-Output ""
    
    ssh "${SERVER_USER}@${SERVER_IP}" "sudo systemctl status binance-monitor --no-pager -l"
}

# 4. 查看实时日志
function Show-Logs {
    Write-ColorOutput Green "📋 连接实时日志（Ctrl+C 退出）..."
    Write-Output ""
    
    ssh "${SERVER_USER}@${SERVER_IP}" "tail -f ${SERVER_PATH}/monitor.log"
}

# 5. 重启服务
function Restart-Service {
    Write-ColorOutput Yellow "🔄 重启监控服务..."
    
    ssh "${SERVER_USER}@${SERVER_IP}" "sudo systemctl restart binance-monitor"
    
    if ($LASTEXITCODE -eq 0) {
        Start-Sleep -Seconds 2
        ssh "${SERVER_USER}@${SERVER_IP}" "sudo systemctl is-active binance-monitor" | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput Green "✅ 服务重启成功！"
        } else {
            Write-ColorOutput Red "❌ 服务启动失败，查看日志:"
            ssh "${SERVER_USER}@${SERVER_IP}" "sudo journalctl -u binance-monitor -n 20 --no-pager"
        }
    } else {
        Write-ColorOutput Red "❌ 重启命令失败"
    }
}

# 6. 停止服务
function Stop-Service {
    Write-ColorOutput Yellow "🛑 停止监控服务..."
    
    ssh "${SERVER_USER}@${SERVER_IP}" "sudo systemctl stop binance-monitor"
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput Green "✅ 服务已停止"
    } else {
        Write-ColorOutput Red "❌ 停止失败"
    }
}

# 7. 启动服务
function Start-Service {
    Write-ColorOutput Yellow "▶️  启动监控服务..."
    
    ssh "${SERVER_USER}@${SERVER_IP}" "sudo systemctl start binance-monitor"
    
    if ($LASTEXITCODE -eq 0) {
        Start-Sleep -Seconds 2
        ssh "${SERVER_USER}@${SERVER_IP}" "sudo systemctl is-active binance-monitor" | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput Green "✅ 服务启动成功！"
        } else {
            Write-ColorOutput Red "❌ 服务启动失败"
        }
    } else {
        Write-ColorOutput Red "❌ 启动命令失败"
    }
}

# 8. SSH连接
function Connect-SSH {
    Write-ColorOutput Green "🔧 连接到服务器..."
    Write-Output ""
    
    ssh "${SERVER_USER}@${SERVER_IP}"
}

# 9. 打包项目
function Pack-Project {
    Write-ColorOutput Green "📦 打包项目..."
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $zipFile = "$env:USERPROFILE\Desktop\monitor_backup_$timestamp.zip"
    
    $excludeItems = @(".venv", "logs", "__pycache__", "*.pyc", ".git", "*.log")
    
    $compress = @{
        Path = Get-ChildItem $LOCAL_PROJECT -Exclude $excludeItems
        DestinationPath = $zipFile
        Force = $true
    }
    Compress-Archive @compress
    
    Write-ColorOutput Green "✅ 打包完成！"
    Write-Output "位置: $zipFile"
    Write-Output "大小: $([Math]::Round((Get-Item $zipFile).Length / 1MB, 2)) MB"
}

# 主循环
while ($true) {
    Show-Menu
    $choice = Read-Host "请选择操作"
    
    switch ($choice) {
        '1' { Upload-Code }
        '2' { Download-Logs }
        '3' { Show-Status }
        '4' { Show-Logs }
        '5' { Restart-Service }
        '6' { Stop-Service }
        '7' { Start-Service }
        '8' { Connect-SSH; break }  # SSH后退出脚本
        '9' { Pack-Project }
        '0' { 
            Write-ColorOutput Green "👋 再见！"
            exit 
        }
        default {
            Write-ColorOutput Red "❌ 无效选择"
        }
    }
    
    Write-Output ""
    Read-Host "按Enter继续"
}
