# AI Knowledge Base

自动化技术情报收集与分析系统，持续追踪 GitHub Trending、Hacker News、arXiv 等来源，将分散的技术资讯转化为结构化、可检索的知识条目。

## 项目结构

```
v1-skeleton/
├── CLAUDE.md                          # 项目定义文件
├── .env.example                       # 环境变量模板
├── README.md                          # 本文件
├── .claude/
│   ├── agents/                        # Agent 角色定义
│   │   ├── collector.md               # 采集 Agent
│   │   ├── analyzer.md                # 分析 Agent
│   │   └── organizer.md               # 整理 Agent
│   └── skills/                        # 技能定义
│       ├── github-trending/          # GitHub Trending 采集
│       └── tech-summary/             # 技术摘要生成
└── knowledge/
    ├── raw/                           # 原始采集数据
    └── articles/                      # 整理后的知识条目
```

## 快速开始

1. 复制环境变量模板并配置：
   ```bash
   cp .env.example .env
   ```

2. 使用 ClaudeCode 运行流水线：
   ```
   @collector 采集今天的 GitHub Trending
   @analyzer 分析昨天的采集数据
   @organizer 整理所有已分析的数据
   ```

## 数据格式

### 原始数据
`knowledge/raw/{source}-{YYYY-MM-DD}.json`

### 知识条目
`knowledge/articles/{YYYY-MM-DD}-{slug}.json`

每个条目包含：`id`, `title`, `source`, `url`, `collected_at`, `summary`, `tags`, `relevance_score`
