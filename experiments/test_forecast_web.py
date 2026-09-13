"""Execute the actual web renderer's forecast display in Node for regression coverage."""

import ast
import pathlib
import subprocess
import unittest


class ForecastWebTests(unittest.TestCase):
    """Cover forecast visibility, escaping, missing data and view changes."""

    def test_forecast_renderer(self):
        """Run the generated JavaScript, not a duplicate implementation."""
        source = pathlib.Path(__file__).resolve().parents[1] / "apps/predbat/web_helper.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_plan_renderer_js")
        assignment = next(node for node in function.body if isinstance(node, ast.Assign))
        script = ast.literal_eval(assignment.value).replace("<script>", "").replace("</script>", "")
        checks = r"""
        const assert = require('node:assert/strict');
        const container = {innerHTML: ''};
        global.document = {getElementById: id => id === 'planContainer' ? container : null};
        global.window = {};
        global.sessionStorage = {getItem: () => null};
        renderPlanTable = () => '<table>Actionable plan</table>';
        checkStaleness = updateTableColors = adjustResponsiveSizes = () => {};
        const row = {start: '2026-09-14T10:30:00+01:00', band: 'low', import: 18.5, export: 15, load: 0.42, pv: 0.8};
        assert.equal(renderForecastContext({}, 'plan'), '');
        assert.equal(renderForecastContext({forecast_context: null}, 'plan'), '');
        assert.match(renderForecastContext({forecast_context: []}, 'plan'), /No usable forecast/);
        const data = {forecast_context: [row]};
        assert.equal(renderForecastContext(data, 'yesterday'), '');
        assert.equal(renderForecastContext(data, 'baseline'), '');
        const html = renderForecastContext(data, 'plan');
        for (const value of ['Forecast context', 'not scheduled', row.start, '18.50', '15.00', '0.42', '0.80']) assert.ok(html.includes(value), value);
        const unsafe = renderForecastContext({forecast_context: [null, {start: '<img>', band: "<&\"'", import: 'bad', export: Infinity}]}, 'plan');
        assert.ok(!unsafe.includes('<img>'));
        assert.ok(unsafe.includes('&lt;img&gt;'));
        assert.ok(unsafe.includes('&amp;&quot;&#39;'));
        assert.ok(!unsafe.includes('NaN'));
        window.planData = data;
        currentView = 'plan'; refreshPlan(); refreshPlan();
        assert.equal((container.innerHTML.match(/id="forecastContext"/g) || []).length, 1);
        window.yesterdayData = data;
        currentView = 'yesterday'; refreshPlan();
        assert.ok(!container.innerHTML.includes('forecastContext'));
        window.baselineData = data;
        currentView = 'baseline'; refreshPlan();
        assert.ok(!container.innerHTML.includes('forecastContext'));
        currentView = 'plan'; window.planData = {forecast_context: []}; refreshPlan();
        assert.ok(container.innerHTML.includes('No usable forecast'));
        console.log('Forecast web renderer checks passed');
        """
        result = subprocess.run(["node"], input=script + checks, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
