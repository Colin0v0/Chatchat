# WSL2 部署指南

## 📋 前置要求

1. **WSL2** 已安装并配置
2. **Docker Desktop** 在WSL2中启用
3. **足够的磁盘空间**（建议20GB+用于模型和数据）

## 🚀 部署步骤

### 1️⃣ 安装Ollama（在WSL2中）

```bash
# 安装ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动ollama服务
ollama serve &

# 验证ollama运行
curl http://localhost:11434/api/version
```

### 2️⃣ 下载所需的Ollama模型

```bash
# 嵌入模型（用于RAG）
ollama pull nomic-embed-text

# 翻译模型（用于网络搜索）
ollama pull translategemma

# 其他你需要的模型（可选）
# ollama pull llama3.2
# ollama pull qwen2.5
```

### 3️⃣ 配置环境变量

```bash
# 在项目根目录
cd /mnt/e/VScodeproject/Chatchat

# 复制WSL2环境配置
cp .env.wsl2 backend/.env

# 编辑配置（根据实际情况修改）
nano backend/.env
```

**重要配置项需要检查：**

- **Ollama地址**: 默认`http://172.17.0.1:11434`（Docker容器访问WSL2主机）
  - 如果不通，可尝试：`http://host.docker.internal:11434` 或 `http://localhost:11434`
- **Obsidian路径**: 默认`/mnt/e/360MoveData/Users/29220/Documents/COLIN_all_in_one_note`
- **模型路径**: 默认`/mnt/f/AI/Models`

### 4️⃣ 创建docker-compose环境变量（可选）

创建 `.env` 文件在项目根目录：

```bash
# docker-compose.yml使用的环境变量
cat > .env << 'EOF'
# Obsidian笔记库在Windows的路径（WSL2格式：/mnt/驱动器/路径）
OBSIDIAN_VAULT_HOST_PATH=/mnt/e/360MoveData/Users/29220/Documents/COLIN_all_in_one_note

# AI模型目录在Windows的路径
MODELS_HOST_PATH=/mnt/f/AI/Models

# HuggingFace缓存目录（可选，避免重复下载）
HF_CACHE_PATH=/home/yourusername/.cache/huggingface

# Ollama地址（Docker容器访问WSL2主机）
OLLAMA_BASE_URL=http://172.17.0.1:11434
EOF
```

### 5️⃣ 验证路径挂载

```bash
# 检查Windows路径在WSL2中是否可访问
ls /mnt/e/360MoveData/Users/29220/Documents/COLIN_all_in_one_note
ls /mnt/f/AI/Models/Florence-2-base-ft

# 确保有读取权限
```

### 6️⃣ 构建并启动服务

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 7️⃣ 验证服务

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 检查Ollama连接
docker exec chatchat-backend curl http://172.17.0.1:11434/api/version

# 访问前端
# 在浏览器打开: http://localhost:3300
```

## 🔧 常见问题排查

### 问题1: Ollama连接失败

**错误**: `Connection refused to http://172.17.0.1:11434`

**解决方案**:

```bash
# 1. 确认ollama在WSL2中运行
ps aux | grep ollama

# 2. 检查ollama监听地址
netstat -tlnp | grep 11434

# 3. 测试不同的连接地址
# 在backend/.env中尝试：
# OLLAMA_BASE_URL=http://localhost:11434  # 如果使用network_mode: host
# OLLAMA_BASE_URL=http://host.docker.internal:11434
# OLLAMA_BASE_URL=http://$(hostname -I | awk '{print $1}'):11434
```

### 问题2: 模型文件找不到

**错误**: `FileNotFoundError: /models/Florence-2-base-ft`

**解决方案**:

```bash
# 1. 验证Windows路径在WSL2中可访问
ls /mnt/f/AI/Models/Florence-2-base-ft

# 2. 检查docker-compose.yml中的挂载配置
docker-compose config

# 3. 进入容器检查
docker exec -it chatchat-backend ls -la /models
```

### 问题3: Obsidian笔记库访问权限

**错误**: `Permission denied: /data/obsidian`

**解决方案**:

```bash
# 1. 检查WSL2中的权限
ls -la /mnt/e/360MoveData/Users/29220/Documents/COLIN_all_in_one_note

# 2. 如需要，修改权限（小心操作）
# sudo chmod -R 755 /mnt/e/360MoveData/Users/29220/Documents/COLIN_all_in_one_note

# 3. 或者在docker-compose.yml中添加user配置
# user: "${UID}:${GID}"
```

### 问题4: GPU不可用（如果有N卡）

**如需启用CUDA**:

```bash
# 1. 安装nvidia-docker2
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# 2. 在docker-compose.yml中添加GPU支持
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: all
#           capabilities: [gpu]

# 3. 修改backend/.env
# IMAGE_VISION_DEVICE=cuda
# AUDIO_TRANSCRIPTION_DEVICE=cuda
```

## 📊 资源监控

```bash
# 查看容器资源使用
docker stats

# 查看容器日志
docker-compose logs -f --tail=100

# 进入容器调试
docker exec -it chatchat-backend /bin/bash
```

## 🔄 更新和维护

```bash
# 更新代码后重新构建
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 清理旧镜像
docker system prune -a

# 备份数据
docker cp chatchat-backend:/app/storage ./backup/
```

## 🛑 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v

# 停止ollama（如需要）
pkill ollama
```

## 📝 性能优化建议

1. **SSD存储**: 将Docker数据目录和模型放在SSD上
2. **内存分配**: 确保Docker Desktop有足够内存（建议8GB+）
3. **CPU限制**: 在docker-compose.yml中合理设置CPU限制
4. **网络优化**: 使用host网络模式可能会更快（需修改配置）

## 🔐 安全建议

1. **API密钥**: 不要将`.env`文件提交到git仓库
2. **网络隔离**: 生产环境建议使用反向代理（nginx/traefik）
3. **防火墙**: 配置WSL2防火墙规则限制访问

## 📚 相关文档

- [Docker Desktop WSL2 Backend](https://docs.docker.com/desktop/wsl/)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [WSL2 网络配置](https://learn.microsoft.com/en-us/windows/wsl/networking)
