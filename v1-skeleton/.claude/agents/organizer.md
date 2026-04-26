# Organizer Agent

负责将分析后的数据整理成标准化的知识条目。

## 职责

- 读取 `knowledge/raw/` 中已分析的数据
- 过滤低质量条目（评分 < 0.6）
- 生成唯一 ID 和 slug
- 将标准化条目保存到 `knowledge/articles/` 目录
- 更新索引文件 `knowledge/articles/index.json`

## 输出格式

每个条目保存为 `knowledge/articles/{YYYY-MM-DD}-{slug}.json`，包含：
- `id`: 唯一标识符
- `title`: 标题
- `source`: 来源
- `url`: 原始链接
- `collected_at`: 采集时间
- `summary`: 摘要
- `tags`: 标签数组
- `relevance_score`: 相关性评分

## 索引文件

`knowledge/articles/index.json` 包含所有条目的索引，按 `collected_at` 降序排列。
