# Chart Markup

对已有图表 payload 增加证据驱动的标记层，支持参考线、区间、事件点、分类或系列颜色和文本强调。保留数据数值，不生成图表；输出增强后的 payload 和跳过标记的报告。

建议 Python 3.11+，运行时只需标准库：

```bash
python app/skills/chart-markup/scripts/chart_markup.py --schema
python app/skills/chart-markup/scripts/chart_markup.py --chart-script line_chart.py --payload /path/to/payload.json --marks-json '{"version":1,"marks":[]}' --output outputs/enhanced.json --report-output outputs/report.json
```

完整协议见 `app/skills/chart-markup/references/mark-protocol.md`，调用规范见同目录 `SKILL.md`。使用原图表仓库渲染增强后的 payload；源数据不足时标记会被跳过并返回报告。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```
