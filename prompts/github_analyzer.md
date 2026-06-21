分析以下 GitHub 仓库，输出 JSON（不要 markdown 包裹）。

仓库: {title}
描述: {description}
URL: {url}
元数据: {metadata}

输出 JSON (schema={schema})
标签从 AI/LLM/Agent/MCP/RAG/Open Source/Tool/Framework/Benchmark 中选择，也可建议新标签。

project_type 必须根据仓库的主要交付物选择：
- coding_tool：直接服务于编码、代码理解/生成、测试、调试、IDE/CLI、开发自动化或 Coding Agent
- ai_infrastructure：通用 LLM 网关、向量库、Agent/RAG 平台或模型服务
- framework：通用编程、ML、深度学习或应用框架
- research：论文、研究实现或模型权重
- dataset：数据集或数据集构建
- benchmark：benchmark、leaderboard、evaluation suite 或 testbed
- resource_collection：awesome list、课程、教程、知识库或资源合集
- other：其他

按主要交付物分类，不因 topics 或偶然出现的关键词改变类型。例如：提供 MCP 接口的日历工具仍是 other；供 Coding Agent 使用的代码文档 MCP 服务是 coding_tool。
