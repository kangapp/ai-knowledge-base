# VPS 访问信息

## 访问凭证

**VPS**: 8.134.176.187:22
**用户**: admin
**密钥**: ~/.ssh/vps_deploy_key（无密码）

**连接命令**:
```bash
ssh -i ~/.ssh/vps_deploy_key admin@8.134.176.187
```

## 应用信息

| 项目 | 路径 |
|------|------|
| 应用目录 | /opt/ai-knowledge-base |
| 静态输出 | /opt/ai-knowledge-base/output |
| 数据库 | /opt/ai-knowledge-base/data/kb.db |
| Docker Compose | /opt/ai-knowledge-base/docker-compose.yml |

## 常用操作

**拉取更新代码**:
```bash
cd /opt/ai-knowledge-base && git pull origin master
```

**重启服务**:
```bash
cd /opt/ai-knowledge-base && docker compose restart
```

**查看流水线日志**:
```bash
docker logs -f ai-knowledge-base-pipeline-1 --since 24h | grep '"event"' | jq .
```

**重新构建静态站**（在容器内执行）:
```bash
docker exec ai-knowledge-base-pipeline-1 uv run python -c "
from src.site.builder import SiteBuilder
from src.core.database import Database
from pathlib import Path
import asyncio
asyncio.run(SiteBuilder(Database('data/kb.db'), Path('output'), Path('src/site/templates')).build())
"
```

**进入容器调试**:
```bash
docker exec -it ai-knowledge-base-pipeline-1 /bin/sh
```