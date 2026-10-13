from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "app" / "skills" / "chart-markup" / "scripts" / "chart_markup.py"
SPEC = importlib.util.spec_from_file_location("chart_markup", SCRIPT)
assert SPEC and SPEC.loader
chart_markup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chart_markup)


def test_line_marks_map_to_native_visual_style_without_mutating_source() -> None:
    payload = {
        "type": "line",
        "xField": "date",
        "series": [{"field": "close", "label": "收盘价", "axis": "right"}],
        "data": [{"date": "2026-09-22", "close": 101}, {"date": "2026-09-23", "close": 108}],
    }
    plan = {
        "marks": [
            {
                "type": "point",
                "target": {"series": "收盘价", "x": "2026-09-23"},
                "eventTime": "2026-09-23",
                "eventTitle": "产品发布",
                "style": {"color": "#ef4444"},
            },
            {"type": "reference-line", "value": 105, "label": "目标位", "style": {"color": "#f59e0b"}},
            {"type": "text-style", "target": {"role": "title"}, "style": {"color": "#7c3aed", "fontWeight": 800}},
        ]
    }

    enhanced, report = chart_markup.apply_marks(payload, "line_chart.py", plan)

    assert "visualStyle" not in payload
    overlays = enhanced["visualStyle"]["overlays"]
    assert overlays[0]["type"] == "pointMarkers"
    assert overlays[0]["index"] == 1
    assert overlays[0]["eventTitle"] == "产品发布"
    assert overlays[1]["type"] == "referenceLine"
    assert enhanced["visualStyle"]["title"]["style"] == {"color": "#7c3aed", "fontWeight": 800}
    assert len(report["applied"]) == 3
    assert report["skipped"] == []


def test_bar_item_mark_adds_renderer_consumed_color_override() -> None:
    payload = {
        "type": "bar",
        "xField": "quarter",
        "series": [{"field": "revenue", "label": "营收", "color": "#4387f5"}],
        "data": [{"quarter": "Q1", "revenue": 10}, {"quarter": "Q2", "revenue": 16}],
    }
    plan = {"marks": [{"type": "item-style", "target": {"series": "营收", "x": "Q2"}, "style": {"color": "#ef4444"}}]}

    enhanced, report = chart_markup.apply_marks(payload, "bar_chart.py", plan)

    assert enhanced["data"][1]["__markColors"] == {"revenue": "#ef4444"}
    assert len(report["applied"]) == 1


def test_nested_treemap_item_can_be_recolored_by_unique_exact_label() -> None:
    payload = {
        "type": "treemap",
        "items": [
            {"label": "科技", "value": 100, "children": [{"label": "半导体", "value": 60, "color": "#4387f5"}]}
        ],
    }
    plan = {"marks": [{"type": "item-style", "target": {"label": "半导体"}, "style": {"color": "#ef4444"}}]}

    enhanced, report = chart_markup.apply_marks(payload, "treemap.py", plan)

    assert enhanced["items"][0]["children"][0]["color"] == "#ef4444"
    assert report["skipped"] == []


def test_unresolved_target_is_skipped_instead_of_guessing() -> None:
    payload = {
        "type": "line",
        "xField": "date",
        "series": [{"field": "close", "label": "收盘价"}],
        "data": [{"date": "2026-09-23", "close": 108}],
    }
    plan = {"marks": [{"type": "point", "target": {"x": "2026-09-24"}, "label": "未知事件"}]}

    enhanced, report = chart_markup.apply_marks(payload, "line_chart.py", plan)

    assert report["applied"] == []
    assert "resolved to 0 rows" in report["skipped"][0]["reason"]
    assert enhanced["visualStyle"]["overlays"] == []


def test_automatic_mark_selection_uses_five_as_a_soft_default() -> None:
    payload = {"type": "pie", "items": [{"label": f"I{i}", "value": i + 1} for i in range(6)]}
    plan = {"marks": [{"type": "item-style", "target": {"label": f"I{i}"}, "style": {"color": "#ef4444"}} for i in range(6)]}

    enhanced, report = chart_markup.apply_marks(payload, "pie.py", plan)

    assert sum(item.get("color") == "#ef4444" for item in enhanced["items"]) == 5
    assert report["skipped"][-1]["reason"] == "mark exceeds maxMarks=5"


def test_user_specified_mark_count_above_five_is_honored() -> None:
    payload = {"type": "pie", "items": [{"label": f"I{i}", "value": i + 1} for i in range(10)]}
    plan = {
        "selectionMode": "user-specified",
        "maxMarks": 10,
        "marks": [{"type": "item-style", "target": {"label": f"I{i}"}, "style": {"color": "#ef4444"}} for i in range(10)],
    }

    enhanced, report = chart_markup.apply_marks(payload, "pie.py", plan)

    assert sum(item.get("color") == "#ef4444" for item in enhanced["items"]) == 10
    assert report["effectiveMaxMarks"] == 10
    assert report["skipped"] == []


def test_all_mode_preserves_every_supplied_mark_without_max_marks() -> None:
    payload = {"type": "pie", "items": [{"label": f"I{i}", "value": i + 1} for i in range(12)]}
    plan = {
        "selectionMode": "all",
        "marks": [{"type": "item-style", "target": {"label": f"I{i}"}, "style": {"color": "#2563eb"}} for i in range(12)],
    }

    enhanced, report = chart_markup.apply_marks(payload, "pie.py", plan)

    assert sum(item.get("color") == "#2563eb" for item in enhanced["items"]) == 12
    assert report["effectiveMaxMarks"] == 12
    assert report["skipped"] == []
