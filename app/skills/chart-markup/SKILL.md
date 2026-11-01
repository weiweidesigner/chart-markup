---
name: chart-markup
description: 为已有通用图表或业务 K 线增加证据驱动的 Mark 标记层。适用于画参考线、区间、事件点、系列/分类变色、重点文本加粗或变色；不负责取数或替代图表渲染。
---

# Chart Markup

Use this skill after a chart renderer and trustworthy data have been selected. It translates an analytical emphasis into a small, schema-valid annotation layer without changing the chart's underlying values.

## Required workflow

1. Resolve every mark target against the final chart payload or a verified upstream observation.
2. Express the request with the common `marks` protocol in [references/mark-protocol.md](references/mark-protocol.md).
3. Run `scripts/chart_markup.py` to merge supported marks into a copy of the payload.
4. Render the enhanced payload with the original chart script. Keep the renderer's defaults unless the user explicitly requested another visual change.
5. Surface skipped marks and warnings; never silently move a mark to a nearby date, category, series, or value.

Inside the Aime Chart route planner, keep the original renderer as the executable step and compile resolved marks directly into its native payload or `--style-json`; do not add `chart_markup.py` as a separate route step because it is a deterministic authoring/validation helper, not a visible renderer.

## JEV integration

JEV may choose a semantic `markStrategy`, such as turning points, event callouts, thresholds, leaders/laggards, contribution focus, or risk outliers. This is only an analytical objective. JEV does not supply factual coordinates.

- Convert the strategy into concrete marks only after upstream data identifies the exact target.
- In automatic mode, prefer one to three decisive marks and use five only as the soft default maximum.
- User intent overrides the automatic default. If the user specifies a count, requests all events, or supplies an explicit mark set, preserve that scope with `selectionMode: user-specified|all`; do not truncate it to five.
- When many marks may crowd the chart, preserve the marks and adapt label density, interaction, or layout instead of silently deleting user-requested events.
- A mark must explain a claim in the surrounding answer. Do not add decorative marks.
- If evidence cannot uniquely identify a target, omit the mark and continue with the unmodified chart.
- Signed bar values are a semantic exception to sparse focal marks: when bars encode rise/fall, return, growth, delta, or profit/loss, use `signed-direction` and apply positive green (`#00b899`), negative red (`#ff2f57`), and zero neutral (`#94a3b8`) to every resolved bar. This should be selected automatically even when the user did not explicitly ask for colors; explicit user colors still take precedence.
- A signed distribution is different: when the x-axis bins encode return/change and the y-axis encodes frequency, use `distribution-polarity`. Resolve polarity from each x bin, color negative bins red, positive bins green, zero-crossing bins neutral, and show the zero reference. Never infer polarity from the positive frequency height.
- Route compilation must pass `distribution-polarity` to the downstream `bar_chart.py` or `grouped_bar.py` step even when `code_interpreter.py` produced the chart payload. As a conservative direct-call fallback, those renderers may auto-detect explicit signed distribution bins only when both negative and positive bins are present and the title/x labels express distribution or rise/fall semantics.

## Renderer mapping

- `line_chart.py`, `group_line.py`: point/event markers, reference lines, selected ranges, series color/width/opacity, title text style.
- `grouped_bar.py` additionally supports explicit `bar-placeholder` marks: hatched missing-value bars whose height references another same-row series. Keep target data null, use localized status in tooltip/legend, and compile to native `barPlaceholders`; see the protocol. Never synthesize actual values or switch to custom HTML for this capability.
- `bar_chart.py`, `grouped_bar.py`: series emphasis, exact category/series recoloring, value-driven `colorRules` for signed-direction bars, and x-bin-driven `distributionColor` for signed distributions.
- `bar_line.py`: bar/line series emphasis, signed-direction `colorRules` for column series, and title text style.
- `pie.py`, `treemap.py`, `waterfall.py`: exact item recoloring; treemap lookup may match a unique nested label.
- `double_ring_pie.py`: exact base/ring recoloring.
- `kline.py`: keep using the business K-line drawing/annotation contract; do not create a second K-line renderer. Bind every mark to the period tab where it was created (`period`, such as `1d` or `1w`) so it is hidden on other periods. Price-line labels use the renderer's collision-free left label lane, leaving the newest candles and right price axis unobstructed. Callout/text bubbles share a collision-free layout, keep numeric and percentage tokens unbroken, and render their connectors before all opaque label boxes so chart lines never cross label text.

The adapter reports unsupported combinations instead of inventing a visual approximation.

## CLI

```bash
python scripts/chart_markup.py \
  --chart-script line_chart.py \
  --payload /path/to/chart-payload.json \
  --marks-json '{"version":1,"marks":[...]}' \
  --output /path/to/enhanced-payload.json \
  --report-output /path/to/mark-report.json
```

Use `--schema` to print the common protocol. `--payload-json` is available when the payload is already serialized.
