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
