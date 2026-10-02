# 和 AI 共创 Spec 的指南

先看清整体需求，再按场景补充细节。你决定关键取舍，AI 持续维护完整文档，让每次修改后的规则、图表和验收保持一致。

## 1. 从你的想法开始

把下面的提示词复制到 AI 对话，填入想法和已有材料。先确认方向，暂不展开长篇正文。

<button type="button" class="prompt-copy" data-copy-target="spec-starter" aria-describedby="copy-feedback" hidden>复制启动提示词</button>
<span id="copy-feedback" class="copy-feedback" role="status" aria-live="polite"></span>

<details class="starter-details">
<summary>查看与修改启动提示词</summary>
<pre id="spec-starter" class="starter-prompt"><code>我想与你共创一份可以交付实施的 Spec。
初步想法：{我想解决的问题}
已有材料与约束：{可选，文档、代码或已知限制}

请主持“对齐目标 → 确认全景 → 演示场景 → 完善全文 → 审校定稿”。

先复述你对目标、读者、范围和成功标准的理解，区分事实、假设、建议与待定问题。
接着给出简短、完整的需求全景：谁遇到什么问题、怎样操作、系统如何响应、
失败怎么办、怎样验收。未知处显式标记；大纲不能代替行为共识。
优先澄清会改变整体方向的问题，每轮一个主要决定，给出具体场景、
2–3 个选项及影响，允许自定义答案或保留问题，不把沉默当成确认。

维护同一份完整草稿与审阅页面。默认展示本轮变化和一个待决定问题，
保留整体概览与全文入口；解释和依据按需展开，不反复粘贴全文。
优先用 HTML 演示需要比较或操作的行为；用流程图、状态图或决策表解释规则。
工具不支持网页时，使用短文本和表格，并说明尚未生成网页。
静态页面中的选项只供预览；只有反馈已提交并收到明确确认，才记为决定。

确认全景后，按场景完善正文、设计、图表与验收，持续更新整份草稿。
必要定义、核心规则和关键约束写入文档；外部链接提供来源，不能替代结论。
区分代码现状与本次设计，来源冲突时提出差异，不直接把旧约定当成新需求。
借鉴 ASD-STE100 的简明表达原则：短句、一句一个主要意思、主动表达、术语统一。
中文文档不宣称严格符合英语规范；保留必要条件、例外和事实依据。

为核心规则编号，记录确认状态和对应正文、图表、设计、验收的位置。
修改时：记录新决定 → 列出影响 → 同步修订 → 全文核对 → 更新版本。
新提议未确认时保留当前约定；关联问题未解决时标记“正在修订”，
保留上一份完整基线，不将新旧规则混合的内容交付为完成版本。
复用同一套标题、术语、表格、图注和页面样式，不因局部修改重新设计排版。

定稿前核对需求覆盖、文内自洽、规则冲突、图文和验收一致性、实际渲染。
常规修正由你完成，关键业务取舍由我确认；未执行的验收必须标为待执行。
现在先用简短摘要复述理解，提出最影响方向的第一个问题。</code></pre>
</details>

## 2. 五步推进，每轮都保留全景

<ol class="spec-workflow" aria-label="Spec 共创的五个步骤">
<li><strong>对齐目标</strong><span>复述问题、读者、范围和成功标准。</span><small>你确认：有没有理解偏。</small></li>
<li><strong>确认全景</strong><span>展示核心流程、主要规则和未知项。</span><small>你确认：整体行为是否符合想法。</small></li>
<li><strong>演示场景</strong><span>比较正常、失败和边界情况的实际结果。</span><small>你确认：具体行为和关键取舍。</small></li>
<li><strong>完善全文</strong><span>按场景补齐正文、设计、图表与验收。</span><small>你确认：是否足以实施。</small></li>
<li><strong>审校定稿</strong><span>检查全文逻辑、来源、展示和验证方式。</span><small>你确认：最终交付版本。</small></li>
</ol>

**讨论范围可以小，维护范围必须覆盖全文。** 发现新的方向问题时，回到全景重新确认。章节用于组织交付内容，不作为彼此独立的生成任务。

## 3. 先看结果，再作决定

下面是教学演示，所有数据与规则都是示例。目标是稍后找回文章；范围是个人收藏、取消和收藏列表。服务器保存状态，保存成功后更新界面，列表按收藏时间倒序排列。

<div class="spec-demo" data-spec-demo>
<p><strong>本轮问题：再次收藏同一文章，要不要更新时间？</strong></p>
<p>初始列表：文章 B（10:00）、文章 A（09:00）。现在于 11:00 再次收藏 A。关系数量保持不变。</p>
<fieldset>
<legend>比较两种行为，仅在本页预览</legend>
<label><input type="radio" name="spec-repeat" value="keep" checked> A．保留原时间，适合保持顺序稳定</label>
<label><input type="radio" name="spec-repeat" value="refresh"> B．更新为当前时间，适合让最近操作靠前</label>
</fieldset>
<div class="spec-demo-result" aria-live="polite" aria-atomic="true">
<p><strong>预览结果</strong>：<span data-demo-order>文章 B（10:00） → 文章 A（09:00）</span></p>
<p data-demo-rule>规则：重复收藏保留原关系与时间。</p>
<p data-demo-check>验收：再次收藏 A 后，关系数量、时间和排序均不变。</p>
<p data-demo-impact>关联检查：正文、排序说明、接口处理、图示与验收均沿用原规则。</p>
<p data-demo-open>重试：相同请求再次执行，也不改变时间。</p>
</div>
<p class="spec-demo-note">本页点击不保存、不提交给 AI，也不确认需求。B 的时间语义还需明确请求重试行为，不能仅改排序演示就定稿。</p>
</div>

## 4. 一次反馈，完成一组修订

**记录决定 → 列出影响 → 同步修订 → 核对全文 → 更新版本。**

比如你提出“再次收藏应置顶”，AI 先指出它会影响重复操作、排序、重试和验收；确认新行为后，再更新所有相关位置。仍有未决影响时，展示修订草稿，保留上一份完整版本。

<details>
<summary>交付前必须能回答的四个问题</summary>
<ul>
<li>符合想法：你确认过核心场景的结果，而不只是目录。</li>
<li>文内自洽：不打开外部链接，也能理解必要定义、规则与边界。</li>
<li>修改完整：受影响的正文、图表、设计和验收均已核对，没有遗留旧规则。</li>
<li>展示一致：复用同一套版式，实际检查网页、图表和窄屏展示。</li>
</ul>
<p>验收计划与执行结果分别记录。生成案例不代表实现已经通过测试。</p>
</details>

<details>
<summary>按需参考：方法、案例和提示词</summary>
<ul>
<li><a href="workflow.html">五步流程详解</a>：阶段产物、审阅页面与修改机制。</li>
<li><a href="writing.html">结构与写作</a>：文内自洽、简明表达与统一排版。</li>
<li><a href="scenarios.html">场景指南</a>：需求设计、实现设计与业务逻辑的不同重点。</li>
<li><a href="example.html">收藏功能案例</a>：完整基线与一次跨全文修订。</li>
<li><a href="prompts.html">进阶 Prompt 工具箱</a>：针对当前阶段追加要求。</li>
</ul>
</details>

<details>
<summary>方法依据与适用说明</summary>
<p>本指南是共创实践建议，不是官方 Spec 标准。借鉴简明写作、图表与交互网页来降低理解成本；业务方向由人确认，一致性需要持续维护和检查，不能仅凭输出格式保证。</p>
<p><a href="https://www.asd-ste100.org/about.html">ASD-STE100 官方说明</a>：英语受控写作规则与词汇。本指南将短句、明确动作和术语一致用于中文表达，不宣称通过 STE 合规认证。</p>
<p><a href="https://developers.openai.com/api/docs/guides/prompt-engineering">Prompt engineering</a>：明确任务、上下文和输出结构。</p>
<p><a href="https://developers.openai.com/api/docs/guides/evaluation-best-practices">Evaluation best practices</a>：按具体任务检查，并结合人工判断修正。</p>
</details>
