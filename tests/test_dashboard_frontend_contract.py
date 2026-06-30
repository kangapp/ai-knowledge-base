from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_dashboard_template_uses_three_tabs_and_summary_kpis():
    html = (ROOT / "src/site/templates/dashboard.html").read_text()

    assert 'data-tab="quality"' in html
    assert 'data-tab="consumption"' in html
    assert 'data-tab="sources"' in html
    assert 'data-tab="runtime"' not in html
    assert 'id="tab-runtime"' not in html

    for element_id in (
        "dash-total-articles",
        "dash-period-articles",
        "dash-pass-rate",
        "dash-period-cost",
        "dash-active-sources",
    ):
        assert f'id="{element_id}"' in html


def test_dashboard_loads_dedicated_scripts_and_app_js_has_no_dashboard_controller():
    html = (ROOT / "src/site/templates/dashboard.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    for script in (
        "/static/js/dashboard/api.js",
        "/static/js/dashboard/state.js",
        "/static/js/dashboard/charts.js",
        "/static/js/dashboard/renderers.js",
        "/static/js/dashboard/main.js",
    ):
        assert script in html
        assert (ROOT / "src/site" / script.lstrip("/")).exists()

    assert "Dashboard Tab Controller" not in app_js
    assert "loadQualityTab" not in app_js
    assert "renderConsumptionDetail" not in app_js


def test_dashboard_source_health_uses_display_names_not_storage_ids():
    renderers = (ROOT / "src/site/static/js/dashboard/renderers.js").read_text()

    assert "function sourceDisplayName" in renderers
    assert "sources.map(sourceDisplayName)" in renderers
    assert "<td>${escapeHtml(sourceDisplayName(s))}</td>" in renderers
    assert "sources.map(s => s.id)" not in renderers


def test_dashboard_source_health_shows_stage_status_and_recent_funnel():
    renderers = (ROOT / "src/site/static/js/dashboard/renderers.js").read_text()
    styles = (ROOT / "src/site/static/css/style.css").read_text()

    assert "function sourceHealthLabel" in renderers
    assert "health_status" in renderers
    assert "last_new_items" in renderers
    assert "last_dedup_skipped" in renderers
    assert "last_analysis_failed" in renderers
    assert "last_run_at" in renderers
    assert "last_error" in renderers
    assert "sources.filter(s => (s.total_collected || 0) > 0)" in renderers
    assert ".source-health-status" in styles


def test_dashboard_renders_source_governance_fields():
    renderers = (ROOT / "src/site/static/js/dashboard/renderers.js").read_text()

    assert "governance_status" in renderers
    assert "health_score" in renderers
    assert "budget_blocked" in renderers
    assert "治理状态" in renderers
    assert "健康分" in renderers


def test_dashboard_error_column_does_not_show_governance_reason_as_error():
    renderers = (ROOT / "src/site/static/js/dashboard/renderers.js").read_text()

    assert "source.last_error || source.last_governance_reason" not in renderers


def test_dashboard_consumption_passes_trend_window_separately():
    api_js = (ROOT / "src/site/static/js/dashboard/api.js").read_text()
    state_js = (ROOT / "src/site/static/js/dashboard/state.js").read_text()
    main_js = (ROOT / "src/site/static/js/dashboard/main.js").read_text()

    assert "trendWindow" in state_js
    assert "week: { days: 7, label: '近 7 天', trendWindow: '4w' }" in state_js
    assert "currentTrendWindow" in state_js
    assert "loadConsumption(period, trendWindow)" in api_js
    assert "trend_window=${trendWindow}" in api_js
    assert "DashboardApi.loadConsumption(period, DashboardState.currentTrendWindow)" in main_js


def test_deep_report_templates_script_builder_and_nav_exist():
    deep_html = (ROOT / "src/site/templates/deep.html").read_text()
    detail_html = (ROOT / "src/site/templates/deep-report.html").read_text()
    base_html = (ROOT / "src/site/templates/base.html").read_text()
    builder_py = (ROOT / "src/site/builder.py").read_text()
    script = (ROOT / "src/site/static/js/deep-reports.js").read_text()

    assert '{% extends "base.html" %}' in deep_html
    assert "深度报告" in deep_html
    assert 'id="deep-reports-list"' in deep_html
    assert "/static/js/deep-reports.js" in deep_html

    assert '{% extends "base.html" %}' in detail_html
    assert 'href="/deep.html"' in detail_html
    assert 'id="deep-report-detail"' in detail_html
    assert "/static/js/deep-reports.js" in detail_html

    assert '<a href="/dashboard.html">仪表盘</a>' in base_html
    assert '<a href="/deep.html">深度报告</a>' in base_html
    assert '<a href="/dag.html">DAG</a>' in base_html
    assert base_html.index("/dashboard.html") < base_html.index("/deep.html") < base_html.index("/dag.html")

    assert "deep.html" in builder_py
    assert "deep-report.html" in builder_py
    assert "config.html" in builder_py
    assert "dag.html" in builder_py

    assert "/api/deep-reports?page=1&page_size=100" in script
    assert "/api/deep-reports/latest" in script
    assert "/api/deep-reports/${safeId}" in script


def test_dag_page_uses_three_layer_runtime_view():
    html = (ROOT / "src/site/templates/dag.html").read_text()
    script = (ROOT / "src/site/static/js/dag.js").read_text()
    styles = (ROOT / "src/site/static/css/style.css").read_text()

    for element_id in (
        "dag-run-select",
        "pipeline-status-card",
        "publication-status-card",
        "dag-summary-metrics",
        "processing-stages",
        "review-rounds",
        "postprocess-stages",
        "source-funnels",
        "active-items",
        "dag-events",
    ):
        assert f'id="{element_id}"' in html

    assert "/static/js/dag.js" in html
    assert "dag-progress" not in html
    assert "setInterval(fetchDag, 5000)" in script
    assert "processing_stages" in script
    assert "review_rounds" in script
    assert "postprocess" in script
    assert "recent_runs" in script
    assert "run_id=${encodeURIComponent" in script
    assert ".dag-layer" in styles
    assert ".dag-status-card" in styles
    assert ".dag-stage-grid" in styles
    assert ".dag-postprocess-grid" in styles


def test_deep_report_script_contracts_for_v2_rendering_and_safety():
    script = (ROOT / "src/site/static/js/deep-reports.js").read_text()
    styles = (ROOT / "src/site/static/css/style.css").read_text()
    escape_html_block = script.split("function escapeHtml(value) {", 1)[1].split("function safeHttpUrl", 1)[0]
    structured_block = script.split("function renderStructuredReport(item) {", 1)[1].split("function renderList(data)", 1)[0]

    assert "function requestJson" in script
    assert "response.ok" in script
    assert "payload.code !== 0" in script

    assert "function escapeHtml" in script
    assert "value === null || value === undefined ? '' : String(value)" in escape_html_block or "value == null ? '' : String(value)" in escape_html_block
    assert "String(value || '')" not in escape_html_block
    assert "function asObject" in script
    assert "function asStringList" in script
    assert "function asPositiveInt" in script
    assert "function normalizeFlow" in script
    assert "function normalizeArchitecture" in script
    assert "function renderDecision" in script
    assert "function renderArchitectureDiagram" in script
    assert "function renderFlow" in script
    assert "function renderCoreModules" in script
    assert "function renderAdoptionNotes" in script
    assert ".replace(/&/g, '&amp;')" in script
    assert ".replace(/</g, '&lt;')" in script
    assert ".replace(/>/g, '&gt;')" in script
    assert ".replace(/\\\"/g, '&quot;')" in script or '.replace(/"/g, \'&quot;\')' in script

    assert "item.status === 'completed'" in script
    assert "items.filter" in script
    assert "Object.getPrototypeOf(value) === Object.prototype" in script
    assert "typeof item === 'string'" in script
    assert "asObject(item).report_json" in script or "const report = asObject(item.report_json)" in script
    assert "report.summary" in script
    assert "report.tech_stack" in script
    assert "report.decision" in script
    assert "report.architecture" in script
    assert "report.quick_start" in script
    assert "report.deployment" in script
    assert "report.core_modules" in script
    assert "report.runtime_data_flow" in script
    assert "report.use_cases" in script
    assert "report.strengths" in script
    assert "report.limitations" in script
    assert "report.actionable_takeaways" in script
    assert "source_evidence" not in structured_block
    assert "report_version" in script
    assert "报告正在升级，请稍后查看" in script

    assert "function safeHttpUrl" in script
    assert "new URL(" in script
    assert "url.protocol === 'http:'" in script
    assert "url.protocol === 'https:'" in script
    assert 'target="_blank"' in script
    assert 'rel="noopener noreferrer"' in script
    assert "Number(trimmed)" in script
    assert "Number.isSafeInteger" in script
    assert "/^[1-9]\\d*$/" in script
    assert "Number.isInteger(value) && value > 0" in script
    assert 'href="/deep-report.html?id=${safeId}"' in script or "detailHref(item.id)" in script
    assert "const safeId = asPositiveInt(id)" in script
    assert "await requestJson('/api/deep-reports/latest')" in script

    assert "<pre" not in structured_block
    assert "innerHTML = item.report_markdown" not in script
    assert "innerHTML = report.report_markdown" not in script
    assert ".deep-decision-grid" in styles
    assert ".deep-architecture-diagram" in styles
    assert ".deep-architecture-cards" in styles
    assert ".deep-flow" in styles
    assert ".deep-flow-step" in styles
    assert ".deep-module-grid" in styles
    assert "@media (max-width: 700px)" in styles
    mobile_styles = styles.split("@media (max-width: 700px)", 1)[1]
    assert ".deep-architecture-diagram { display: none; }" in mobile_styles
    assert ".deep-architecture-cards { display: grid;" in mobile_styles
