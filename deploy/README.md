# deploy/ 目录说明

本目录包含云服务器部署相关的脚本和文档。

## 📁 文件清单

- **QUICKSTART.md** - 快速开始指南（5分钟部署教程）
- **server_setup.sh** - Linux服务器自动部署脚本
- **manage_server.ps1** - Windows管理工具（一键操作）

## 🚀 使用流程

### 1. 阅读快速指南
```
QUICKSTART.md - 包含完整的部署步骤和常见问题
```

### 2. 上传部署脚本到服务器
```powershell
scp server_setup.sh monitor@your_server_ip:~/
```

### 3. 服务器端执行部署
```bash
chmod +x ~/server_setup.sh
./server_setup.sh
```

### 4. 本地使用管理工具
```powershell
# 编辑配置（修改服务器IP等信息）
notepad manage_server.ps1

# 运行管理工具
powershell -ExecutionPolicy Bypass -File manage_server.ps1
```

## 📖 详细文档

完整部署文档请查看项目根目录的 `DEPLOYMENT.md`
