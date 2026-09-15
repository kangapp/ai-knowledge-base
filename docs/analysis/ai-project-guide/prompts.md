# 项目 Prompt 工具箱

先在[开始共创](README.md)启动项目对话，再按阶段展开一个模板，填写花括号并复制。需要换会话时，先在原对话中用 P10 生成交接材料。

<ul>
<li><a href="#requirements">需求与 Spec</a>：P01 澄清需求。</li>
<li><a href="#selection">技术选型</a>：P02 比较方案，P03 跑通项目骨架。</li>
<li><a href="#coding">编码与测试</a>：P04 实现功能，P05 验证行为，P06 审查改动，P07 修复缺陷。</li>
<li><a href="#deployment">部署上线</a>：P08 发布、验收与失败恢复。</li>
<li><a href="#operations">运维迭代</a>：P09 建立运维流程，P10 接续下一轮工作。</li>
</ul>

所有模板沿用首页协作约定，每轮只讨论一个主要决定。实施、测试和发布模板会要求 AI 按已有授权实际执行；未执行的检查如实标记。与 OpenAI 提示建议的对应关系见页末。

<h2 id="requirements">需求与 Spec</h2>

<details id="p01">
<summary>P01 · 把想法变成最小 Spec</summary>
<p>适用：有项目想法，但范围、核心规则或验收还不明确。产物：逐步确认的最小 Spec 与待定问题。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p01" aria-describedby="copy-p01" hidden>复制 P01</button>
<span id="copy-p01" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p01" class="starter-prompt"><code>本轮目标：把项目想法整理为可以指导实施的最小 Spec。
初步想法与目标用户：{内容}
已有材料：{文件路径、需求记录或现有产品}
已确认约束与本次不做的事：{内容；未知处写待定}

先读取材料，概括用途、核心场景和现有约定。
找出最影响范围或核心行为的一个问题，给出 2–3 个选项、
推荐前提与影响；允许我自定义或保留，不把沉默当成批准。
按我的决定逐步更新需求，条件、行为、结果和异常写具体。
关键方向明确后，给出简洁结构；经确认后完成最小 Spec。
将核心需求关联到可执行的验收条件，单列阻塞项和非阻塞项。
本轮产出文档与待定清单，不立即展开项目代码。</code></pre>
<p><strong>核对：</strong>仅依据 Spec，能否判断一个正常或失败场景应该得到什么结果？还有哪些问题会改变实现方向？</p>
</details>

<h2 id="selection">技术选型</h2>

<details id="p02">
<summary>P02 · 比较技术方案并验证关键假设</summary>
<p>适用：需要选择框架、存储或托管方式。产物：有来源的比较、最小验证结果与决定记录。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p02" aria-describedby="copy-p02" hidden>复制 P02</button>
<span id="copy-p02" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p02" class="starter-prompt"><code>本轮只决定：{一个技术问题，如数据如何存储}
已确认 Spec：{文件或关键需求}
约束：{运行环境、预期规模、预算、已有技能与依赖}
已有候选：{可选；已有决定不要重新比较}

先核实约束，再提出 2–3 个可行方案。
用相同需求比较适配程度、开发与维护负担、运行成本和限制。
涉及版本、价格或平台能力时查阅当前官方资料，注明来源与日期；
查不到的内容明确标记，不用推测值伪装为事实。
对最影响选择的技术未知项，在现有环境和授权范围内做最小验证；
缺少条件时给出验证办法，单列尚未验证的部分。
推荐一个方案，说明前提、代价及何时需要重新评估，请我决定。
确认后记录结论、理由、影响与遗留问题，再推进依赖它的工作。</code></pre>
<p><strong>核对：</strong>推荐是否符合本项目约束？验证结果、官方说明与 AI 推断是否区分清楚？</p>
</details>

<details id="p03">
<summary>P03 · 制定实施顺序并跑通项目骨架</summary>
<p>适用：核心需求与技术方案已确认，准备开始实现。产物：实施顺序、最小可运行骨架和启动说明。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p03" aria-describedby="copy-p03" hidden>复制 P03</button>
<span id="copy-p03" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p03" class="starter-prompt"><code>已确认需求与技术决定：{文件路径}
项目目录与现有材料：{路径；新项目注明当前为空}
本轮要跑通的最小路径：{例如入口接收请求并完成一次数据读写}
环境与执行范围：{本地环境、允许使用的服务及约束}

先读取相关文件，检查已有代码和项目约定，复用现有模式。
将实施拆成可以独立验证的小步，注明每步产物、依赖和通过条件。
在已确认方案内直接搭建本轮骨架；新的关键技术取舍回来澄清。
只加入跑通这条路径所需的依赖与配置，记录安装和启动方式。
实际启动并验证最小路径；配置文档只记录名称和取得方式，不含密钥。
交付改动位置、启动命令、实际验证结果及下一步。</code></pre>
<p><strong>核对：</strong>按文档是否能够启动？这次骨架只验证了哪些能力，哪些业务功能还未实现？</p>
</details>

<h2 id="coding">编码与测试</h2>

<details id="p04">
<summary>P04 · 实现一个可验证的功能增量</summary>
<p>适用：需求明确，准备完成一项用户行为。产物：最小相关改动、必要测试和同步文档。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p04" aria-describedby="copy-p04" hidden>复制 P04</button>
<span id="copy-p04" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p04" class="starter-prompt"><code>本轮实现：{一个用户行为}
对应需求与验收：{Spec 位置、条件和预期结果}
相关代码与参考实现：{路径}
必须保留的行为、接口和数据约定：{约束}

先阅读相关代码与测试，确认改动位置和现有约定。
按最小必要范围完成实现，复用已有模式，不顺手重构无关模块。
覆盖本次行为涉及的正常、异常和边界；有界面时实际检查交互。
运行与改动相关的必要测试，失败时定位原因并修正后再次验证。
发现会改变范围或核心行为的歧义时，提出一个主要决定供我选择。
同步必要文档，报告改动、测试命令与结果，以及未验证的部分。</code></pre>
<p><strong>核对：</strong>代码改动是否都能对应需求？测试是否验证了用户行为，而非仅重复代码内部实现？</p>
</details>

<details id="p05">
<summary>P05 · 按需求完成测试与验收</summary>
<p>适用：功能已有实现，需要确认是否符合约定。产物：执行过的检查、失败证据与剩余验证范围。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p05" aria-describedby="copy-p05" hidden>复制 P05</button>
<span id="copy-p05" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p05" class="starter-prompt"><code>待验收功能与版本：{内容}
验收依据：{Spec、场景和预期结果}
运行环境、已有测试与执行范围：{路径、命令、可用环境}

先检查现有测试与需求的对应关系，再补充必要的行为验证。
根据实际风险选择正常、异常和边界场景，不为覆盖数量机械加测试。
在指定范围内执行检查，记录环境、版本、操作、预期和实际结果。
涉及界面时在浏览器中操作，必要时检查适用的屏幕宽度。
失败时保留复现证据，区分实现问题、环境问题和需求歧义；
对范围内的明确问题修正后重跑相关检查，不擅自改变验收标准。
最终列出通过、失败与未执行项，并说明它们是否阻塞下一步。</code></pre>
<p><strong>核对：</strong>“通过”是否有实际执行证据？未执行、环境受限或不适用的检查是否明确说明？</p>
</details>

<details id="p06">
<summary>P06 · 审查代码与 Spec 是否一致</summary>
<p>适用：完成一批改动，准备合并或交付。产物：有位置、证据和影响说明的审查结论。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p06" aria-describedby="copy-p06" hidden>复制 P06</button>
<span id="copy-p06" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p06" class="starter-prompt"><code>请审查以下改动：{工作区改动、提交或明确的比较基准}
需求与项目约定：{Spec 和相关规范路径}
重点关注：{可选，如兼容性、失败处理、访问限制或数据一致性}

先读取改动及其相关调用代码、测试和文档，再对照需求判断。
检查功能遗漏、行为回退、异常路径、数据影响与测试缺口。
每个实际问题给出位置、触发条件、证据、影响和最小修正建议。
将阻塞问题与一般建议分开；不把风格偏好当成功能缺陷。
必要时运行不改变业务数据的针对性验证，并说明实际范围。
本轮只审查，不修改代码或发布；若未发现问题，也说明检查范围和局限。</code></pre>
<p><strong>核对：</strong>发现能否被复现或由代码证据支持？“未发现问题”是否被误写成没有任何风险？</p>
</details>

<details id="p07">
<summary>P07 · 根据证据定位并修复缺陷</summary>
<p>适用：出现可描述的错误或行为不符。产物：复现、根因、最小修复与验证结果。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p07" aria-describedby="copy-p07" hidden>复制 P07</button>
<span id="copy-p07" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p07" class="starter-prompt"><code>问题现象：{发生了什么，预期是什么}
复现步骤、时间与版本：{内容}
相关日志、代码和最近变更：{路径或脱敏摘录}
环境与执行范围：{开发或生产；允许的操作及已确认约束}

先读取证据，在可用且允许的环境中复现，区分事实与原因假设。
优先检查最可能的原因，用针对性观察或检查逐项验证，再修改代码。
无法复现时说明缺少什么证据，不把猜测写成确定根因。
完成最小相关修复；有复发风险时补充能捕获该问题的回归检查。
重跑原复现步骤与受影响的检查，报告是否恢复预期行为。
生产环境的重启、回滚或数据恢复按已有授权执行；超出范围的操作先澄清。
最后说明根因、改动位置、验证证据与尚未解决的问题。</code></pre>
<p><strong>核对：</strong>修改是否针对已经验证的原因？原故障和受影响的关联行为是否都得到检查？</p>
</details>

<h2 id="deployment">部署上线</h2>

<details id="p08">
<summary>P08 · 部署、验收并处理发布失败</summary>
<p>适用：准备将已验证的版本发布到目标环境。产物：部署结果、目标版本、线上验收与恢复记录。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p08" aria-describedby="copy-p08" hidden>复制 P08</button>
<span id="copy-p08" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p08" class="starter-prompt"><code>请发布以下版本：{提交、标签或构建产物}
目标环境与访问范围：{开发、预发布或生产；服务入口}
现有部署文档与流程：{路径或配置}
验收要求、执行授权与约束：{核心操作、允许的变更及风险边界}

先检查现有流程和待发布改动，确认配置、持久数据与版本标识。
检查部署前必要验证、上一可用版本和发布失败后的恢复步骤。
涉及数据结构变化时，单独核对备份、兼容性和恢复条件。
在已确认授权内完成发布；目标或影响范围不明确时提出一个关键问题，
并继续不受影响的准备工作，不重复索取已有授权。
等待部署流程结束，验证目标入口、核心行为和实际运行版本。
若验收失败，按已确认方案修复或恢复，再验证服务状态。
交付访问地址、版本、执行与验收结果；触发回滚时如实报告，不能算上线成功。
缺权限或工具时，给出准备好的步骤和具体阻塞点，不宣称已经部署。</code></pre>
<p><strong>核对：</strong>是否验证了真实目标环境和版本？构建成功、命令成功与上线验收通过是否分别记录？</p>
</details>

<h2 id="operations">运维迭代</h2>

<details id="p09">
<summary>P09 · 建立可执行的运行维护流程</summary>
<p>适用：服务已上线，需要明确检查、排障和数据恢复方式。产物：运行手册、范围内的配置与实际验证记录。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p09" aria-describedby="copy-p09" hidden>复制 P09</button>
<span id="copy-p09" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p09" class="starter-prompt"><code>服务与当前部署：{入口、版本、环境和文档}
已有监控、日志和备份方式：{配置路径或现状}
可接受的中断、数据损失及维护投入：{已确认要求；未知处标待定}
本轮执行范围：{允许配置或验证的内容}

先核对现状，整理健康检查、核心功能检查、日志入口和异常处理责任。
有持久数据时，明确备份范围、频率、保留时间、存放位置和恢复步骤。
方案需要新的成本或恢复能力取舍时，给出选项让我决定。
在已授权范围内完成必要配置和检查；备份恢复在隔离环境验证，
核对数据和应用可用性，并说明实际覆盖的故障范围。
需要定时检查时，明确周期和执行条件，实际配置后检查任务是否生效。
记录已配置、已验证、待执行和需要人工处理的部分。
交付简洁运行手册；一次对话或一份监控方案不代表持续检查已开始。</code></pre>
<p><strong>核对：</strong>发生目标故障时备份能否取得并恢复？检查任务是否实际运行，异常由谁处理是否明确？</p>
</details>

<details id="p10">
<summary>P10 · 交接当前状态，接续下一轮迭代</summary>
<p>适用：长对话接续、换会话，或准备开展下一轮需求。产物：可核查的项目交接摘要与下一步。</p>
<button type="button" class="prompt-copy" data-copy-target="project-p10" aria-describedby="copy-p10" hidden>复制 P10</button>
<span id="copy-p10" class="copy-feedback" role="status" aria-live="polite"></span>
<pre id="project-p10" class="starter-prompt"><code>请为项目的下一轮工作生成交接摘要。
当前材料：{Spec、代码、决定记录和运行说明路径}
下一轮目标：{已有想法；未知则写待定}

先核对当前产物，将目标、范围和有效决定与历史提议区分开。
记录代码版本、工作区未提交改动和已知部署状态；无法核实的部分标明来源与时间。
列出启动、测试、发布和排障入口，以及实际通过、失败和未执行的检查。
单列假设、建议、待定问题与阻塞影响，不把旧提议写成已确认决定。
根据新目标说明受影响的需求、代码、数据和运行方式，给出最小下一步。
只保留接续工作必需的信息，用文件位置和记录支持结论，不复制整段聊天。
本轮输出交接摘要，不自动发布或展开下一轮功能实现。</code></pre>
<p><strong>核对：</strong>接手者能否找到当前文件、区分代码与线上状态，并明确从哪一步继续？</p>
</details>

<h2 id="official-basis">如何对应 OpenAI 的提示建议</h2>

资料核对：2026-09-15。本页按<strong>目标、材料、约束、执行、验证</strong>组织提示，是结合官方建议与本指南工作流编写的实践模板，不是官方原文。项目阶段、授权边界和具体交付清单由本指南结合实际协作需要整理。

<ul>
<li><strong>说明行为、上下文与验证方式：</strong>每条模板给出任务、材料入口和验收要求；排错模板包含复现信息，编码模板关联相关代码。参见 <a href="https://learn.chatgpt.com/docs/prompting#use-editor-context">OpenAI：Prompting Codex</a>。</li>
<li><strong>把不同信息分清楚：</strong>用标题或清晰标签区分任务指令、输入材料和约束；材料较长时可用 Markdown 或 XML 标记边界。参见 <a href="https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml">OpenAI：提示中的结构与分隔</a>。</li>
<li><strong>直接描述目标和约束：</strong>对推理模型，不必要求展示完整内部推理过程；本页要求的是结论、关键依据、取舍和可核验结果。参见 <a href="https://developers.openai.com/api/docs/guides/reasoning-best-practices#how-to-prompt-reasoning-models-effectively">OpenAI：推理模型提示建议</a>。</li>
<li><strong>先用清楚的指令，按需补示例：</strong>若输出仍偏离格式或行为要求，再提供少量与本任务一致的输入和期望输出示例，避免示例与文字约束冲突。依据同上。</li>
</ul>

例如，把“帮我写好收藏功能”改成“按 Spec 中的重复收藏规则，修改相关保存逻辑；保留原时间，验证首次保存、重复请求和保存失败，并报告实际检查结果”。更具体的行为与验证标准，比堆叠“专业、完整、完美”等形容词更便于检查输出。

模板不能替代项目材料和实际验证。若输出偏离要求，先指出具体差异，补充缺失依据或约束，再修改对应模板；需要阶段完成条件时，查看[阶段检查与记录](reference.md)。
