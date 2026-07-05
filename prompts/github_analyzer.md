分析以下 GitHub 仓库，输出 JSON（不要 markdown 包裹）。

仓库: {title}
描述: {description}
URL: {url}
元数据: {metadata}

输出 JSON (schema={schema})
tags 只能从以下词表选择，最多 3 个：模型与基础设施、Agent 与自动化、RAG 与知识系统、开发工具与框架、研究与评测、产品与行业应用、商业与市场、安全与治理、LLM、多模态、AI芯片、Agent、Coding Agent、自动化、RAG、知识库、数据治理、MCP、Tool、Framework、Open Source、Claude Code、Codex、研究、Benchmark、Dataset、医疗AI、具身智能、XR、融资、产业趋势、监管、安全。
第一个 tag 选最主要的一级分类；不要输出 AI、人工智能、大模型等泛标签，也不要为单篇文章发明新标签。

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
