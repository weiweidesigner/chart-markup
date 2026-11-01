#!/usr/bin/env python3
"""Apply evidence-bound chart marks to a generic chart payload."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any


LINE_SCRIPTS = {"line_chart.py", "group_line.py"}
BAR_SCRIPTS = {"bar_chart.py", "grouped_bar.py"}
ITEM_SCRIPTS = {"pie.py", "treemap.py", "waterfall.py", "double_ring_pie.py"}
SUPPORTED_TYPES = {"point", "reference-line", "range", "series-style", "item-style", "text-style", "bar-placeholder"}


def protocol_schema() -> dict[str, Any]:
    return {
        "version": 1,
        "selectionModes": ["auto", "user-specified", "all"],
        "defaultAutoMaxMarks": 5,
        "maxMarks": "optional non-negative user/request limit; values above five are honored",
        "markTypes": sorted(SUPPORTED_TYPES),
        "target": {"series": "exact field or label", "x": "exact x value", "index": "integer", "label": "exact item label", "role": "title|metric"},
        "barPlaceholder": {"referenceSeries": "exact same-row reference field or unique label", "label": "localized missing status", "style": {"color": "optional hatch/outline color"}},
        "invariant": "Every target must resolve uniquely against the payload; unresolved marks are skipped.",
    }


def _component(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("chartPayload"), dict):
        return payload["chartPayload"]
    root = payload.get("root")
    if isinstance(root, dict) and isinstance(root.get("component"), dict):
        return root["component"]
    if isinstance(payload.get("component"), dict):
        return payload["component"]
    return payload


def _props(component: dict[str, Any]) -> dict[str, Any]:
    return component["props"] if isinstance(component.get("props"), dict) else component


def _list(component: dict[str, Any], key: str) -> list[Any]:
    props = _props(component)
    value = component.get(key)
    if not isinstance(value, list):
        value = props.get(key)
    return value if isinstance(value, list) else []


def _series(component: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in ("series", "columnSeries", "lineSeries"):
        result.extend(item for item in _list(component, key) if isinstance(item, dict))
    return result


def _data(component: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _list(component, "data") if isinstance(item, dict)]


def _x_field(component: dict[str, Any]) -> str:
    props = _props(component)
    return str(component.get("xField") or props.get("xField") or "period")


def _style(component: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(component.get("visualStyle"), dict):
        component["visualStyle"] = {}
    return component["visualStyle"]


def _selector(mark: dict[str, Any]) -> dict[str, Any]:
    target = mark.get("target") if isinstance(mark.get("target"), dict) else {}
    merged = dict(target)
    for key in ("series", "x", "index", "label", "role"):
        if key in mark and key not in merged:
            merged[key] = mark[key]
    return merged


def _mark_style(mark: dict[str, Any]) -> dict[str, Any]:
    style = mark.get("style") if isinstance(mark.get("style"), dict) else {}
    merged = dict(style)
    for key in ("color", "fontWeight", "fontSize", "strokeWidth", "opacity", "dasharray", "showPoints", "pointRadius", "radius"):
        if key in mark and key not in merged:
            merged[key] = mark[key]
    return merged


def _matches(value: Any, expected: Any) -> bool:
    return str(value).strip().casefold() == str(expected).strip().casefold()


def _resolve_series(component: dict[str, Any], selector: Any) -> tuple[dict[str, Any] | None, str | None]:
    candidates = _series(component)
    if selector in (None, ""):
        return (candidates[0], None) if len(candidates) == 1 else (None, "series target is required for a multi-series chart")
    matched = [item for item in candidates if _matches(item.get("field"), selector) or _matches(item.get("label"), selector)]
    if len(matched) != 1:
        return None, f"series target {selector!r} resolved to {len(matched)} series"
    return matched[0], None


def _resolve_index(component: dict[str, Any], selector: dict[str, Any]) -> tuple[int | None, str | None]:
    rows = _data(component)
    raw_index = selector.get("index")
    if raw_index is not None:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            return None, "index must be an integer"
        return (index, None) if 0 <= index < len(rows) else (None, f"index {index} is outside the data range")
    x_value = selector.get("x")
    if x_value is None:
        return None, "x or index target is required"
    x_field = _x_field(component)
    matched = [index for index, row in enumerate(rows) if str(row.get(x_field)) == str(x_value)]
    if len(matched) != 1:
        return None, f"x target {x_value!r} resolved to {len(matched)} rows"
    return matched[0], None


def _find_items(component: dict[str, Any], script: str) -> list[dict[str, Any]]:
    if script == "double_ring_pie.py":
        items = [item for item in _list(component, "rings") if isinstance(item, dict)]
        base = component.get("base") or _props(component).get("base")
        metrics = _list(component, "metrics")
        return ([base] if isinstance(base, dict) else []) + items + [item for item in metrics if isinstance(item, dict)]
    roots = [item for item in _list(component, "items") if isinstance(item, dict)]
    if script != "treemap.py":
        return roots
    flattened: list[dict[str, Any]] = []
    stack = list(roots)
    while stack:
        item = stack.pop(0)
        flattened.append(item)
        children = item.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
    return flattened


def _apply_line_mark(component: dict[str, Any], mark: dict[str, Any], mark_type: str) -> tuple[bool, str]:
    selector = _selector(mark)
    style = _mark_style(mark)
    visual = _style(component)
    if mark_type == "series-style":
        series, error = _resolve_series(component, selector.get("series"))
        if error or series is None:
            return False, error or "series not found"
        patch = {"field": series.get("field")}
        patch.update({key: value for key, value in style.items() if key in {"color", "strokeWidth", "opacity", "dasharray", "showPoints", "pointRadius"}})
        visual.setdefault("seriesStyle", []).append(patch)
        return True, "series style applied"
    if mark_type == "text-style":
        if selector.get("role") != "title":
            return False, "line charts currently support text-style only for role=title"
        title_style = visual.setdefault("title", {}).setdefault("style", {})
        title_style.update({key: value for key, value in style.items() if key in {"color", "fontWeight", "fontSize"}})
        return bool(title_style), "title style applied"
    overlays = visual.setdefault("overlays", [])
    if mark_type == "reference-line":
        value = mark.get("value")
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False, "reference-line requires a finite numeric value"
        overlay = {"type": "referenceLine", "value": value, "axis": mark.get("axis") or "right", "label": mark.get("label") or ""}
        overlay.update({key: value for key, value in style.items() if key in {"color", "width", "strokeWidth", "opacity", "dasharray", "fontSize"}})
        if "strokeWidth" in overlay and "width" not in overlay:
            overlay["width"] = overlay.pop("strokeWidth")
        overlays.append(overlay)
        return True, "reference line applied"
    if mark_type == "range":
        rows = _data(component)
        x_field = _x_field(component)
        endpoints: dict[str, int] = {}
        for name in ("from", "to"):
            raw_index = mark.get(f"{name}Index")
            raw_value = mark.get(name)
            if raw_index is not None:
                try:
                    index = int(raw_index)
                except (TypeError, ValueError):
                    return False, f"{name}Index must be an integer"
                if not 0 <= index < len(rows):
                    return False, f"{name}Index is outside the data range"
                endpoints[name] = index
            else:
                matched = [index for index, row in enumerate(rows) if str(row.get(x_field)) == str(raw_value)]
                if len(matched) != 1:
                    return False, f"{name} target {raw_value!r} resolved to {len(matched)} rows"
                endpoints[name] = matched[0]
        overlay = {"type": "selectedBand", "fromIndex": endpoints["from"], "toIndex": endpoints["to"]}
        overlay.update({key: value for key, value in style.items() if key in {"color", "opacity"}})
        overlays.append(overlay)
        return True, "selected range applied"
    if mark_type == "point":
        index, error = _resolve_index(component, selector)
        if error or index is None:
            return False, error or "point target not found"
        series, error = _resolve_series(component, selector.get("series"))
        if error or series is None:
            return False, error or "series target not found"
        overlay = {
            "type": "pointMarkers", "index": index, "targetField": series.get("field"),
            "label": mark.get("label") or mark.get("eventTitle") or "",
            "eventTime": mark.get("eventTime") or "", "eventTitle": mark.get("eventTitle") or mark.get("label") or "",
            "labelBox": bool(mark.get("labelBox", bool(mark.get("eventTime") or mark.get("eventTitle")))),
            "labelPosition": mark.get("labelPosition") or "top", "maxLabels": 1,
        }
        overlay.update({key: value for key, value in style.items() if key in {"color", "radius", "width", "height", "fontSize"}})
        visual.setdefault("overlays", []).append(overlay)
        return True, "point marker applied"
    return False, f"{mark_type} is not supported for line charts"


def _apply_series_mark(component: dict[str, Any], mark: dict[str, Any]) -> tuple[bool, str]:
    selector = _selector(mark)
    style = _mark_style(mark)
    series, error = _resolve_series(component, selector.get("series"))
    if error or series is None:
        return False, error or "series not found"
    changed = False
    for key in ("color", "opacity", "strokeWidth"):
        if key in style:
            series[key] = style[key]
            changed = True
    return changed, "series style applied" if changed else "series-style contains no supported style"


def _apply_bar_item(component: dict[str, Any], mark: dict[str, Any]) -> tuple[bool, str]:
    selector = _selector(mark)
    style = _mark_style(mark)
    color = style.get("color")
    if not isinstance(color, str) or not color.strip():
        return False, "item-style requires color"
    index, error = _resolve_index(component, selector)
    if error or index is None:
        return False, error or "category not found"
    series, error = _resolve_series(component, selector.get("series"))
    if error or series is None:
        return False, error or "series not found"
    row = _data(component)[index]
    colors = row.setdefault("__markColors", {})
    colors[str(series.get("field"))] = color.strip()
    return True, "bar item color applied"


def _apply_bar_placeholder(component: dict[str, Any], mark: dict[str, Any]) -> tuple[bool, str]:
    selector = _selector(mark)
    index, error = _resolve_index(component, selector)
    if error or index is None:
        return False, error or "category not found"
    series, error = _resolve_series(component, selector.get("series"))
    reference, ref_error = _resolve_series(component, mark.get("referenceSeries"))
    if error or ref_error or series is None or reference is None:
        return False, error or ref_error or "both series are required"
    row = _data(component)[index]
    field, ref = str(series["field"]), str(reference["field"])
    if field == ref or row.get(field) not in (None, ""):
        return False, "placeholder requires a missing target and a distinct reference series"
    value = row.get(ref)
    try:
        valid = value not in (None, "") and not isinstance(value, bool) and math.isfinite(float(value))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        return False, "placeholder reference must be a finite same-row value"
    placeholders = _props(component).setdefault("barPlaceholders", [])
    if any(item.get("index") == index and item.get("series") == field for item in placeholders):
        return False, "duplicate placeholder target"
    placeholders.append({"index": index, "series": field, "referenceSeries": ref,
                         "label": str(mark.get("label") or "—"), "style": _mark_style(mark)})
    return True, "hatched missing-bar placeholder applied; source values unchanged"


def _apply_item_mark(component: dict[str, Any], script: str, mark: dict[str, Any], mark_type: str) -> tuple[bool, str]:
    selector = _selector(mark)
    style = _mark_style(mark)
    label = selector.get("label")
    if label in (None, ""):
        return False, "item label is required"
    matched = [item for item in _find_items(component, script) if _matches(item.get("label"), label)]
    if len(matched) != 1:
        return False, f"item target {label!r} resolved to {len(matched)} items"
    item = matched[0]
    if mark_type == "item-style":
        color = style.get("color")
        if not isinstance(color, str) or not color.strip():
            return False, "item-style requires color"
        item["color"] = color.strip()
        return True, "item color applied"
    return False, f"{mark_type} is not supported for {script}"


def apply_marks(payload: dict[str, Any], script: str, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    enhanced = copy.deepcopy(payload)
    component = _component(enhanced)
    raw_marks = plan.get("marks") if isinstance(plan.get("marks"), list) else []
    selection_mode = str(plan.get("selectionMode") or "auto").strip().lower()
    if selection_mode not in {"auto", "user-specified", "all"}:
        selection_mode = "auto"
    if selection_mode == "all":
        limit = len(raw_marks)
    elif "maxMarks" in plan:
        try:
            limit = max(0, int(plan["maxMarks"]))
        except (TypeError, ValueError):
            limit = len(raw_marks) if selection_mode == "user-specified" else 5
    elif selection_mode == "user-specified":
        limit = len(raw_marks)
    else:
        limit = 5
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, raw_mark in enumerate(raw_marks[:limit]):
        if not isinstance(raw_mark, dict):
            skipped.append({"index": index, "reason": "mark must be an object"})
            continue
        mark_type = str(raw_mark.get("type") or "").strip().lower().replace("_", "-")
        if mark_type not in SUPPORTED_TYPES:
            skipped.append({"index": index, "type": mark_type, "reason": "unsupported mark type"})
            continue
        if script in LINE_SCRIPTS:
            ok, reason = _apply_line_mark(component, raw_mark, mark_type)
        elif script in BAR_SCRIPTS:
            if mark_type == "series-style":
                ok, reason = _apply_series_mark(component, raw_mark)
            elif mark_type == "bar-placeholder" and script == "grouped_bar.py":
                ok, reason = _apply_bar_placeholder(component, raw_mark)
            elif mark_type == "item-style":
                ok, reason = _apply_bar_item(component, raw_mark)
            else:
                ok, reason = False, f"{mark_type} is not supported for {script}"
        elif script == "bar_line.py":
            if mark_type == "series-style":
                ok, reason = _apply_series_mark(component, raw_mark)
            elif mark_type == "text-style" and _selector(raw_mark).get("role") == "title":
                title = _style(component).setdefault("title", {}).setdefault("style", {})
                title.update({key: value for key, value in _mark_style(raw_mark).items() if key in {"color", "fontWeight", "fontSize"}})
                ok, reason = bool(title), "title style applied"
            else:
                ok, reason = False, f"{mark_type} is not supported for bar_line.py"
        elif script in ITEM_SCRIPTS:
            ok, reason = _apply_item_mark(component, script, raw_mark, mark_type)
        elif script == "kline.py":
            ok, reason = False, "use the native K-line drawings/annotation contract"
        else:
            ok, reason = False, f"unsupported chart script {script}"
        entry = {"index": index, "type": mark_type, "reason": reason}
        (applied if ok else skipped).append(entry)
    if len(raw_marks) > limit:
        skipped.extend({"index": index, "reason": f"mark exceeds maxMarks={limit}"} for index in range(limit, len(raw_marks)))
    report = {
        "version": 1,
        "chartScript": script,
        "selectionMode": selection_mode,
        "effectiveMaxMarks": limit,
        "applied": applied,
        "skipped": skipped,
    }
    component["_chartMarkup"] = report
    return enhanced, report


def _load_object(path: str | None, raw: str | None, label: str) -> dict[str, Any]:
    if path:
        value: Any = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    elif raw:
        value = json.loads(raw)
    else:
        raise ValueError(f"{label} is required")
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply evidence-bound marks to a chart payload.")
    parser.add_argument("--chart-script")
    parser.add_argument("--payload")
    parser.add_argument("--payload-json")
    parser.add_argument("--marks-json")
    parser.add_argument("--marks-file")
    parser.add_argument("--output")
    parser.add_argument("--report-output")
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(protocol_schema(), ensure_ascii=False, indent=2))
        return 0
    if not args.chart_script or not args.output:
        parser.error("--chart-script and --output are required unless --schema is used")
    payload = _load_object(args.payload, args.payload_json, "payload")
    plan = _load_object(args.marks_file, args.marks_json, "marks plan")
    enhanced, report = apply_marks(payload, Path(args.chart_script).name, plan)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(enhanced, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report_output:
        report_output = Path(args.report_output).expanduser().resolve()
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output), **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
