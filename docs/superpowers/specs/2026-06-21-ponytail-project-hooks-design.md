# Ponytail 项目级 Hooks 设计

## 目标

在当前仓库中启用 Ponytail 的 Codex 生命周期 hooks。新会话默认使用
`full` 模式，并允许通过用户指令切换或关闭模式。配置只对当前项目生效。

## 方案

- 在 `.codex/hooks.json` 注册 `SessionStart` 和 `UserPromptSubmit`。
- 在 `.agents/hooks/` 保存 Ponytail 上游提供的 Node.js hook 脚本。
- hook 脚本直接读取现有 `.agents/skills/ponytail/SKILL.md`，不复制规则内容。
- 默认模式固定为 `full`；仍允许 `PONYTAIL_DEFAULT_MODE` 覆盖。
- 运行状态写入 Codex 提供的插件数据目录；不在工作树生成状态文件。

## 行为

### 会话启动

`SessionStart` 调用 `ponytail-activate.js`，向 Codex 注入 `full` 模式规则。
如果 Node.js 不可用，hook 静默跳过，不阻塞 Codex 启动。

### 模式切换

`UserPromptSubmit` 调用 `ponytail-mode-tracker.js`，识别：

- `@ponytail lite`
- `@ponytail full`
- `@ponytail ultra`
- `@ponytail off`
- `stop ponytail`
- `normal mode`

### 安全边界

- 只运行仓库中可审查的 Node.js 文件，不下载内容、不调用网络。
- hook 超时为 5 秒。
- 脚本失败不阻塞当前会话。
- 首次加载时由 Codex 的项目信任机制决定是否允许运行。

## 文件范围

```text
.codex/hooks.json
.agents/hooks/ponytail-activate.js
.agents/hooks/ponytail-config.js
.agents/hooks/ponytail-instructions.js
.agents/hooks/ponytail-mode-tracker.js
.agents/hooks/ponytail-runtime.js
```

不安装完整 Ponytail 插件、marketplace、状态栏脚本或其他平台适配文件。

## 验证

1. 校验 `.codex/hooks.json` 是合法 JSON。
2. 直接执行启动 hook，确认输出包含 `PONYTAIL:FULL` 和附加规则。
3. 向模式跟踪 hook 输入 `@ponytail ultra`，确认输出模式变为 `ultra`。
4. 检查 Git 状态，确认只新增设计与预期 hook 文件。
