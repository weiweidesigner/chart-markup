# Mark protocol

Top-level shape:

```json
{
  "version": 1,
  "selectionMode": "auto|user-specified|all",
  "maxMarks": 10,
  "marks": [
    {
      "type": "point|reference-line|range|series-style|item-style|text-style",
      "target": {"series": "field or label", "x": "exact x value", "index": 0, "label": "exact item label", "role": "title|metric"},
      "style": {"color": "#ef4444", "fontWeight": 700, "strokeWidth": 3, "opacity": 1},
      "label": "reader-facing annotation",
      "eventTime": "2026-09-23",
      "eventTitle": "Verified event title",
      "value": 100,
      "from": "2026-01-01",
      "to": "2026-03-31"
    }
  ]
}
```

## Selection and quantity

- `selectionMode` defaults to `auto`. When neither a count nor a mode is specified, automatic analysis uses a soft maximum of five marks and normally prefers one to three.
- Set `selectionMode: user-specified` when the user names a count or provides an explicit set. `maxMarks` is then the requested count; if omitted, every supplied mark is retained.
- Set `selectionMode: all` when the user asks for all verified/important events. Every supplied mark is retained, and `maxMarks` is ignored.
- A caller-supplied `maxMarks` above five is valid and must be honored. Five is not a hard protocol limit.
- Resolve visual crowding with label density, hover/click detail, event lanes, or responsive layout. Do not solve it by silently dropping requested marks.

## Target rules

- `series` matches a `field` or reader-facing `label`, case-insensitively, and must resolve uniquely.
- `x` matches the payload's x field exactly after string conversion. `index` must be in range.
- `label` matches an item/ring/metric label exactly and uniquely. Nested treemap labels are supported.
- `reference-line` requires a finite numeric `value`.
- `range` requires existing `from` and `to` x values or valid `fromIndex` and `toIndex`.
- `point` requires an existing x/index and, for multi-series charts, a resolvable series.
- K-line marks require `period` (for example `1d` or `1w`). A mark is rendered only when its owning period Tab is active; marks created without an explicit period inherit the active Tab.
- Do not use nearest-date matching, substring matching, fabricated thresholds, or inferred event dates.

## Mark semantics

- `point`: a point/event callout. Use `eventTime` plus `eventTitle` for the framed two-line line-chart label.
- `reference-line`: a horizontal labeled benchmark, target, support/resistance, or threshold.
- `range`: a selected x interval.
- `series-style`: color, width, opacity, dash pattern, point visibility, or point radius for one series.
- `item-style`: color one exact category, slice, treemap node, waterfall step, ring, or bar.
- `text-style`: title or exact metric text emphasis. Unsupported text roles are reported rather than approximated.
- `signed-direction`: renderer-level semantic color rules for signed bars. Positive values use `#00b899`, negative values use `#ff2f57`, and zero uses `#94a3b8`; unlike sparse focal marks, this rule applies to every resolved bar and does not count against `maxMarks`.
- `distribution-polarity`: renderer-level semantic encoding for signed distributions. The x-axis bin determines polarity while the y-axis remains frequency/frequency share: negative bins use `#ff2f57`, positive bins use `#00b899`, bins containing zero use `#94a3b8`, and the renderer shows a zero reference. It does not count against `maxMarks`.

Generated payloads include `_chartMarkup` metadata with applied and skipped marks. This metadata is provenance, not a renderer instruction.
