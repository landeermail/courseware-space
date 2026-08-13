#!/usr/bin/env python3
"""Build five deterministic image questions for the media confirmation acceptance run."""

from __future__ import annotations

import html
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

SAMPLES = [
    {
        "id": "image-01",
        "field": "垂直纸面向里",
        "symbol": "×",
        "motion": "向右",
        "arrow_x1": 720,
        "arrow_x2": 850,
        "B": 0.50,
        "L": 1.00,
        "v": 2.00,
        "R": 0.40,
        "asks": "求感应电动势大小，并判断杆中电流方向。",
    },
    {
        "id": "image-02",
        "field": "垂直纸面向外",
        "symbol": "•",
        "motion": "向右",
        "arrow_x1": 720,
        "arrow_x2": 850,
        "B": 0.80,
        "L": 0.60,
        "v": 3.00,
        "R": 1.20,
        "asks": "求回路中的电流大小和方向。",
    },
    {
        "id": "image-03",
        "field": "垂直纸面向里",
        "symbol": "×",
        "motion": "向左",
        "arrow_x1": 560,
        "arrow_x2": 430,
        "B": 0.25,
        "L": 1.20,
        "v": 4.00,
        "R": 0.50,
        "asks": "判断 c、d 两端电势高低，并求安培力大小。",
    },
    {
        "id": "image-04",
        "field": "垂直纸面向外",
        "symbol": "•",
        "motion": "向左",
        "arrow_x1": 560,
        "arrow_x2": 430,
        "B": 1.20,
        "L": 0.80,
        "v": 1.50,
        "R": 0.60,
        "asks": "求感应电流方向与电阻的焦耳功率。",
    },
    {
        "id": "image-05",
        "field": "垂直纸面向里",
        "symbol": "×",
        "motion": "向右",
        "arrow_x1": 720,
        "arrow_x2": 850,
        "B": 0.35,
        "L": 1.50,
        "v": 5.00,
        "R": 0.75,
        "asks": "求电动势、电流、安培力，并说明能量转化关系。",
    },
]


def svg(sample: dict[str, object]) -> str:
    symbols = "".join(
        f'<text x="{x}" y="{y}" class="field">{sample["symbol"]}</text>'
        for y in (330, 430, 530, 630)
        for x in (360, 480, 600, 720, 840)
    )
    statement_lines = [
        f'两根平行光滑金属导轨间距 L={sample["L"]:.2f} m，左端接 R={sample["R"]:.2f} Ω 的电阻，其余电阻不计。',
        f'装置处在 B={sample["B"]:.2f} T、{sample["field"]}的匀强磁场中，导体杆 cd 始终与导轨垂直，',
        f'以 v={sample["v"]:.2f} m/s {sample["motion"]}做匀速直线运动。',
    ]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">
  <defs>
    <marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="18" markerHeight="18" refX="16" refY="9" orient="auto"><path d="M0,0 L18,9 L0,18 Z" fill="#1769aa"/></marker>
    <filter id="shadow"><feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#22324d" flood-opacity=".12"/></filter>
  </defs>
  <style>
    .cn {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; fill:#182236; }}
    .field {{ font-family: Arial, sans-serif; font-size:54px; font-weight:700; fill:#6a7990; text-anchor:middle; dominant-baseline:middle; }}
    .label {{ font-family: Arial, sans-serif; font-size:34px; font-weight:700; fill:#25334c; }}
  </style>
  <rect width="1400" height="900" fill="#f5f8fc"/>
  <rect x="50" y="45" width="1300" height="810" rx="26" fill="white" filter="url(#shadow)"/>
  <text x="95" y="115" class="cn" font-size="30" font-weight="800">高中物理 · 电磁感应</text>
  <text x="95" y="158" class="cn" font-size="25">{html.escape(statement_lines[0])}</text>
  <text x="95" y="196" class="cn" font-size="25">{html.escape(statement_lines[1])}</text>
  <text x="95" y="234" class="cn" font-size="25">{html.escape(statement_lines[2])}</text>
  <text x="95" y="274" class="cn" font-size="25" font-weight="700">{html.escape(str(sample["asks"]))}</text>
  <rect x="310" y="270" width="590" height="430" rx="18" fill="#edf3ff"/>
  {symbols}
  <line x1="260" y1="300" x2="950" y2="300" stroke="#26364f" stroke-width="16" stroke-linecap="round"/>
  <line x1="260" y1="680" x2="950" y2="680" stroke="#26364f" stroke-width="16" stroke-linecap="round"/>
  <line x1="260" y1="300" x2="260" y2="390" stroke="#26364f" stroke-width="16"/>
  <rect x="225" y="390" width="70" height="190" rx="18" fill="white" stroke="#26364f" stroke-width="12"/>
  <line x1="260" y1="580" x2="260" y2="680" stroke="#26364f" stroke-width="16"/>
  <line x1="640" y1="300" x2="640" y2="680" stroke="#111827" stroke-width="22" stroke-linecap="round"/>
  <circle cx="640" cy="300" r="19" fill="#111827"/><circle cx="640" cy="680" r="19" fill="#111827"/>
  <text x="665" y="290" class="label">c</text><text x="665" y="735" class="label">d</text>
  <text x="175" y="490" class="label">R</text>
  <line x1="{sample["arrow_x1"]}" y1="278" x2="{sample["arrow_x2"]}" y2="278" stroke="#1769aa" stroke-width="9" marker-end="url(#arrow)"/>
  <text x="985" y="350" class="cn" font-size="28" font-weight="800">图示信息</text>
  <text x="985" y="410" class="cn" font-size="27">B = {sample["B"]:.2f} T</text>
  <text x="985" y="458" class="cn" font-size="27">L = {sample["L"]:.2f} m</text>
  <text x="985" y="506" class="cn" font-size="27">v = {sample["v"]:.2f} m/s</text>
  <text x="985" y="554" class="cn" font-size="27">R = {sample["R"]:.2f} Ω</text>
  <text x="985" y="618" class="cn" font-size="25" fill="#415a77">磁场：{sample["field"]}</text>
  <text x="985" y="666" class="cn" font-size="25" fill="#1769aa">运动：{sample["motion"]}</text>
  <text x="95" y="810" class="cn" font-size="21" fill="#6a7990">样本编号：{sample["id"]}　｜　所有数值均为题目直接给出</text>
</svg>'''


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        svg_path = ROOT / f'{sample["id"]}.svg'
        png_path = ROOT / f'{sample["id"]}.png'
        svg_path.write_text(svg(sample), encoding="utf-8")
        if not CHROME.is_file():
            raise SystemExit("未找到 Google Chrome，无法渲染 PNG 验收样本")
        subprocess.run(
            [
                str(CHROME),
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1400,900",
                f"--screenshot={png_path}",
                svg_path.resolve().as_uri(),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    low_sources = [
        svg(SAMPLES[0])
        .replace("B=0.50 T", "B=? T")
        .replace("B = 0.50 T", "B = ? T")
        .replace("R=0.40 Ω", "R=? Ω")
        .replace("R = 0.40 Ω", "R = ? Ω"),
        svg(SAMPLES[1])
        .replace("垂直纸面向外", "方向标记模糊")
        .replace(">•</text>", ">?</text>"),
        re.sub(
            r'  <line x1="560" y1="278"[^\n]+\n',
            "",
            svg(SAMPLES[2]).replace("向左做匀速直线运动", "沿导轨做匀速直线运动，方向标记缺失").replace("运动：向左", "运动：方向未标明"),
        ),
    ]
    for index, source in enumerate(low_sources, 1):
        sample_id = f"uncertain-{index:02d}"
        svg_path = ROOT / f"{sample_id}.svg"
        png_path = ROOT / f"{sample_id}.png"
        svg_path.write_text(source.replace("image-01", sample_id).replace("image-02", sample_id).replace("image-03", sample_id), encoding="utf-8")
        subprocess.run(
            [str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=1400,900", f"--screenshot={png_path}", svg_path.resolve().as_uri()],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )

    pdf_html = ROOT / "multi-question.html"
    pdf_path = ROOT / "multi-question.pdf"
    pdf_html.write_text(
        """<!doctype html><meta charset=\"utf-8\"><style>@page{size:A3 landscape;margin:8mm}*{box-sizing:border-box}body{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:8mm}figure{margin:0;border:1px solid #ccd5e3;border-radius:12px;padding:4mm;break-inside:avoid}img{display:block;width:100%;height:auto}figcaption{font:700 16px -apple-system,'PingFang SC',sans-serif;margin-bottom:3mm}</style><figure><figcaption>第 1 题</figcaption><img src=\"image-01.png\"></figure><figure><figcaption>第 2 题</figcaption><img src=\"image-04.png\"></figure>""",
        encoding="utf-8",
    )
    subprocess.run(
        [str(CHROME), "--headless", "--disable-gpu", "--print-to-pdf-no-header", f"--print-to-pdf={pdf_path}", pdf_html.resolve().as_uri()],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    print(f"已生成 {len(SAMPLES)} 张标准图片、{len(low_sources)} 张不确定样本和 1 份一页多题 PDF。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
