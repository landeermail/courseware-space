/**
 * q07-glass-rod-tir 学习者操作 → 模型输入 → 视图输出 的适配层。
 * 全部物理量、光路、反射点、计数均来自 model.js 的同一输出；
 * 本文件只负责渲染与交互，不重算物理。
 */

import {
  ROD,
  classify,
  computeFromIncidence,
  computeFromTheta,
  feasibility,
  incidenceForTheta,
  reflectionX,
  thetaForIncidence,
} from './model.js';

const DEG = Math.PI / 180;

// ---------- 全局状态 ----------
const state = {
  scene: 's0',
  previousScene: 's0',
  iDeg: incidenceForTheta(20), // 首次进入「找边界」前的初始方向
  visited: {},
  notice: '',
  prediction0: '',
  prediction2: '',
  choice6: '',
  choice7: '',
  reason4: '',
  show6: false,
  show7: false,
  selectedK: 1,
  unfold: false,
  highlight: null, // 'i' | 'theta' | 'alpha' | 'C' | 'first' | 'period' | 'xk'
  finderStep: 'angles', // 场景1「找边界」场内步骤：angles | explore | verify
  crossedBoundary: false, // 已在「连续探索」中真实跨越一次临界
  showKeyCheck: false, // 「用关键值核对」已展开
};

let model = computeFromIncidence(state.iDeg);

function setIncidence(iDeg) {
  model = computeFromIncidence(iDeg);
  state.iDeg = model.iDeg;
  if (state.selectedK > Math.max(1, model.count)) {
    state.selectedK = Math.max(1, model.count);
  }
}

function applyThetaPreset(thetaDeg) {
  // 预设通过 Snell 反算真实空气入射方向，不伪造管内方向。
  setIncidence(incidenceForTheta(thetaDeg));
}

// ---------- 连续操控（场景 1「找边界」：滑条与图中把手共用） ----------
// 学习者可见量为管内轴向角 θ；每个 θ 都经 i=incidenceForTheta(θ) 反算
// 真实空气入射方向，绝不伪造管内光路。
const THETA_MIN = 0;
const THETA_MAX = 35;
const THETA_STEP = 0.1;

function setThetaContinuous(thetaDeg) {
  const snapped = Math.round(thetaDeg / THETA_STEP) * THETA_STEP;
  const clamped = Math.min(THETA_MAX, Math.max(THETA_MIN, snapped));
  const prev = model.classification;
  setIncidence(incidenceForTheta(clamped));
  if (
    state.scene === 's1' &&
    state.finderStep === 'explore' &&
    prev === 'tir' &&
    model.classification !== 'tir' &&
    !state.crossedBoundary
  ) {
    state.crossedBoundary = true; // 完成一次跨越临界的连续探索
  }
  requestDynamic();
}

let rafQueued = false;

/** 拖动期间合并到每帧一次局部更新，不重建整个场景、不重排全部 KaTeX。 */
function requestDynamic() {
  if (state.scene !== 's1') {
    render();
    return;
  }
  if (rafQueued) return;
  rafQueued = true;
  requestAnimationFrame(() => {
    rafQueued = false;
    updateDynamic();
  });
}

/** 场景 1 局部更新：只重建主舞台、状态条与读数，公式面板保持稳定 DOM。 */
function updateDynamic() {
  const stage = sceneRoot.querySelector('[data-stage]');
  if (!stage) return;
  const hadHandleFocus =
    document.activeElement && document.activeElement.hasAttribute('data-handle');
  const step = state.finderStep;
  const g = tubeSvg(model, {
    withAngles: step !== 'explore',
    withNumbers: step === 'explore',
    withDrag: true,
  });
  stage.innerHTML = g.svg + g.labels;
  renderTex(stage);
  bindHandle(stage);

  // 滑条 ← 模型：双向同步（程序赋值不会触发 input 事件）
  const slider = sceneRoot.querySelector('[data-theta-slider]');
  if (slider) {
    slider.value = fmt(model.thetaDeg, 1);
    slider.setAttribute('aria-valuetext', `θ = ${fmt(model.thetaDeg, 1)}°`);
  }
  const readout = sceneRoot.querySelector('[data-theta-readout]');
  if (readout) {
    readout.innerHTML = tex(`\\theta = ${fmt(model.thetaDeg, 1)}^\\circ`);
    renderTex(readout);
  }

  // 状态条（连续探索与静态核对步骤在场）：状态标签、i/θ/α/C、反射次数全部来自同一模型输出
  const strip = sceneRoot.querySelector('[data-status]');
  if (strip) {
    strip.dataset.theta = String(model.thetaDeg);
    strip.dataset.classification = model.classification;
    strip.dataset.count = String(model.count);
    strip.innerHTML = `${statusTag(model)}${angleStrip(model)}<span data-count-line>${countLineText(model)}</span>`;
    renderTex(strip);
  }

  // 角度识别步骤的读数行
  const readings = sceneRoot.querySelector('[data-readings]');
  if (readings) {
    readings.dataset.i = String(model.iDeg);
    readings.dataset.theta = String(model.thetaDeg);
    readings.dataset.alpha = String(model.alphaDeg);
    readings.innerHTML = angleStrip(model);
    renderTex(readings);
  }

  // 关键值核对的选中态与「用关键值核对」入口（跨越临界后出现）
  sceneRoot.querySelectorAll('[data-preset]').forEach((btn) => {
    btn.classList.toggle(
      'active',
      Math.abs(model.thetaDeg - Number(btn.dataset.preset)) < 0.05,
    );
  });
  const gate = sceneRoot.querySelector('[data-preset-gate]');
  if (gate) gate.hidden = !state.crossedBoundary || state.showKeyCheck;

  // 连续探索中的「已跨越临界」提示
  const crossedNote = sceneRoot.querySelector('[data-crossed-note]');
  if (crossedNote) crossedNote.hidden = !state.crossedBoundary;

  if (hadHandleFocus) {
    const handle = stage.querySelector('[data-handle]');
    if (handle) handle.focus();
  }
}

/** 图中入射光把手的指针拖动与键盘调节；与滑条经同一 θ 入口双向同步。 */
function bindHandle(stage) {
  const handle = stage.querySelector('[data-handle]');
  if (!handle) return;
  const svg = stage.querySelector('svg');
  const viewW = Number(svg.getAttribute('width'));
  const viewH = Number(svg.getAttribute('height'));
  const startDrag = (event) => {
    event.preventDefault();
    const move = (ev) => {
      const rect = stage.getBoundingClientRect();
      const px = ((ev.clientX - rect.left) / rect.width) * viewW;
      const py = ((ev.clientY - rect.top) / rect.height) * viewH;
      // 反解像素 → cm（与 fitView 参数一致：场景 1 的共用视图）
      const v = fitView(-10.5, 44, -3.2, 7.6, viewW, viewH, 24);
      const xCm = -10.5 + (px - 24) / v.scale;
      const yCm = -3.2 + (viewH - 24 - py) / v.scale;
      const dx = 0 - xCm;
      const dy = ROD.h / 2 - yCm;
      if (dx <= 0.01) return;
      const i = Math.min(90, Math.max(0, Math.atan2(Math.max(0, dy), dx) / DEG));
      // 像素方向先换算成 θ 并与滑条步长对齐，再经 Snell 反算入射方向
      setThetaContinuous(thetaForIncidence(i));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    move(event);
  };
  handle.addEventListener('pointerdown', startDrag);
  const hitArea = stage.querySelector('[data-handle-hit]');
  if (hitArea) hitArea.addEventListener('pointerdown', startDrag);

  handle.addEventListener('keydown', (event) => {
    let next = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next = model.thetaDeg + 0.5;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next = model.thetaDeg - 0.5;
    if (event.key === 'Home') next = THETA_MIN;
    if (event.key === 'End') next = THETA_MAX;
    if (next !== null) {
      event.preventDefault();
      setThetaContinuous(next);
    }
  });
}

// 原生 range 拇指占据轨道两端各约半个拇指宽，位置映射按此内缩（px）。
const SLIDER_THUMB_HALF_PX = 8;

/**
 * 场景 1 水平滑条的显式 pointer 拖动。
 * pointerdown 开始并按轨道实际几何位置把指针映射到 θ=0°–35°，
 * 连续 pointermove 经 0.1° 钳制调用 setThetaContinuous；
 * pointerup/pointercancel 正确清理；优先 pointer capture，
 * 不可用时窗口监听等价保证拖出拇指区域后仍能继续。
 * 原生 range 的键盘、focus、ARIA 与 input 事件全部保留。
 */
function bindThetaSlider(slider) {
  slider.style.touchAction = 'pan-y'; // 水平拖动不被纵向滚动抢占（等价样式，不改动 styles.css）

  const thetaFromClientX = (clientX) => {
    const rect = slider.getBoundingClientRect();
    const usable = Math.max(1, rect.width - 2 * SLIDER_THUMB_HALF_PX);
    const ratio = (clientX - rect.left - SLIDER_THUMB_HALF_PX) / usable;
    const clamped = Math.min(1, Math.max(0, ratio));
    return THETA_MIN + clamped * (THETA_MAX - THETA_MIN);
  };

  // 原生通道：键盘、辅助技术与任何原生值变化仍经 input 进入同一 θ 入口
  slider.addEventListener('input', () => {
    setThetaContinuous(Number(slider.value));
  });

  let activePointerId = null;
  const moveFromEvent = (event) => {
    if (activePointerId === null || event.pointerId !== activePointerId) return;
    setThetaContinuous(thetaFromClientX(event.clientX));
  };
  const endDrag = (event) => {
    if (activePointerId === null || event.pointerId !== activePointerId) return;
    activePointerId = null;
    if (slider.hasPointerCapture && slider.hasPointerCapture(event.pointerId)) {
      slider.releasePointerCapture(event.pointerId);
    }
    window.removeEventListener('pointermove', moveFromEvent);
    window.removeEventListener('pointerup', endDrag);
    window.removeEventListener('pointercancel', endDrag);
  };

  slider.addEventListener('pointerdown', (event) => {
    if (activePointerId !== null) return;
    activePointerId = event.pointerId;
    // 阻止原生 range 默认拖动（该路径在受支持环境中只聚焦不改值）；
    // 手动保持与原生一致的按下即聚焦行为
    event.preventDefault();
    slider.focus();
    try {
      slider.setPointerCapture(event.pointerId);
    } catch {
      // pointer capture 不可用时，窗口监听等价保证拖出拇指后仍能继续
    }
    window.addEventListener('pointermove', moveFromEvent);
    window.addEventListener('pointerup', endDrag);
    window.addEventListener('pointercancel', endDrag);
    moveFromEvent(event); // 轨道点击/按下即定位，与原生轨道点击语义一致
  });
}

// ---------- 短时图式高亮（2 秒自动清除，重复激活重新计时） ----------
let highlightTimer = null;

function refreshHighlight() {
  if (state.scene === 's1') updateDynamic();
  else render();
}

function setHighlight(key) {
  state.highlight = key;
  if (highlightTimer !== null) window.clearTimeout(highlightTimer);
  highlightTimer = window.setTimeout(() => {
    highlightTimer = null;
    state.highlight = null;
    refreshHighlight();
  }, 2000);
  refreshHighlight();
}

function clearHighlight() {
  if (highlightTimer !== null) {
    window.clearTimeout(highlightTimer);
    highlightTimer = null;
  }
  state.highlight = null;
}

// ---------- 通用渲染辅助 ----------
function fmt(value, digits = 2) {
  if (!Number.isFinite(value)) return '—';
  const fixed = value.toFixed(digits);
  return fixed.replace(/\.0+$|(\.\d*?)0+$/, '$1');
}

function tex(source) {
  return `<span class="tex" data-tex="${source}"></span>`;
}

// KaTeX 输出对同一源码确定；缓存避免拖动期间重复排版静态标签。
const texCache = new Map();

function renderTex(root) {
  root.querySelectorAll('[data-tex]').forEach((el) => {
    const cached = texCache.get(el.dataset.tex);
    if (cached !== undefined) {
      el.innerHTML = cached;
      return;
    }
    window.katex.render(el.dataset.tex, el, { throwOnError: false });
    texCache.set(el.dataset.tex, el.innerHTML);
  });
}

/** 公式块：竖排具名式，可选代入行与图式绑定。 */
function formulaBlock(id, name, texSource, { sub = '', hl = [] } = {}) {
  const chips = hl
    .map(
      (item) =>
        `<button type="button" class="chip" data-hl="${item.key}" data-physics-ref="${item.key}">${tex(item.symbol)}</button>`,
    )
    .join('');
  return `
    <div class="formula-block" data-physics-id="${id}" id="formula-${id}">
      <span class="formula-name">${name}</span>
      <span class="formula-line">${tex(texSource)}</span>
      ${sub ? `<span class="formula-sub">${tex(sub)}</span>` : ''}
      ${chips ? `<span class="chip-row">在图中找：${chips}</span>` : ''}
    </div>`;
}

/** 文本中的公式引用：可点击高亮定位目标式。 */
function refLink(targetId, label) {
  return `<button type="button" class="chip" data-formula-ref="${targetId}" data-physics-ref="${targetId}">${label}</button>`;
}

// ---------- SVG 几何辅助 ----------
function fitView(minX, maxX, minY, maxY, viewW, viewH, margin) {
  const scale = Math.min(
    (viewW - 2 * margin) / (maxX - minX),
    (viewH - 2 * margin) / (maxY - minY),
  );
  return {
    scale,
    viewW,
    viewH,
    X: (x) => margin + (x - minX) * scale,
    Y: (y) => viewH - margin - (y - minY) * scale,
  };
}

/** 以 (cx,cy) 为圆心、数学角（度，y 向上）从 a0 到 a1 的弧线路径。 */
function arcPath(X, Y, cx, cy, r, a0, a1) {
  const p = (a) => `${(X(cx) + r * Math.cos(a * DEG)).toFixed(2)},${(Y(cy) - r * Math.sin(a * DEG)).toFixed(2)}`;
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  const sweep = a1 > a0 ? 0 : 1; // y 翻转后方向相反
  return `M ${p(a0)} A ${r},${r} 0 ${large} ${sweep} ${p(a1)}`;
}

/** 弧线中点（用于放置角标）。 */
function arcMid(X, Y, cx, cy, r, a0, a1) {
  const a = ((a0 + a1) / 2) * DEG;
  return { x: X(cx) + r * Math.cos(a), y: Y(cy) - r * Math.sin(a) };
}

function labelAt(xPx, yPx, texSource, extraClass = '') {
  return `<span class="svg-label ${extraClass}" style="left:${xPx.toFixed(1)}px;top:${yPx.toFixed(1)}px" data-tex="${texSource}"></span>`;
}

const SVG_DEFS = `
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#c0392b"></path>
    </marker>
    <marker id="arrow-dim" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#37485a"></path>
    </marker>
  </defs>`;

function line(x1, y1, x2, y2, attrs) {
  return `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" ${attrs}></line>`;
}

// ---------- 玻璃管与光路（折叠视图，场景 1 各步骤共用） ----------
function tubeSvg(m, { withAngles, withNumbers, withDrag }) {
  const viewW = 640;
  const viewH = 250;
  const v = fitView(-10.5, 44, -3.2, 7.6, viewW, viewH, 24);
  const { X, Y } = v;
  const parts = [];
  const labels = [];

  // 玻璃管
  parts.push(
    `<rect x="${X(0)}" y="${Y(ROD.h)}" width="${X(ROD.L) - X(0)}" height="${Y(0) - Y(ROD.h)}" fill="#e8f1f8" stroke="#173a5e" stroke-width="2"></rect>`,
  );
  // 尺寸标注（与原题一致的题设量）
  parts.push(
    line(X(0), Y(ROD.h + 1.1), X(ROD.L), Y(ROD.h + 1.1), 'stroke="#5a6b7b" stroke-width="1" marker-start="url(#arrow-dim)" marker-end="url(#arrow-dim)"'),
    line(X(ROD.L + 1.2), Y(ROD.h), X(ROD.L + 1.2), Y(0), 'stroke="#5a6b7b" stroke-width="1" marker-start="url(#arrow-dim)" marker-end="url(#arrow-dim)"'),
  );
  labels.push(labelAt((X(0) + X(ROD.L)) / 2, Y(ROD.h + 1.7), '40\\ \\text{cm}'));
  labels.push(labelAt(X(ROD.L + 2.3), Y(ROD.h / 2), '4\\ \\text{cm}'));

  const entry = { x: 0, y: ROD.h / 2 };

  // 左端面法线（水平虚线，伸入空气侧）
  parts.push(
    line(X(-9.5), Y(entry.y), X(4), Y(entry.y), 'stroke="#2b6cb0" stroke-width="1.4" stroke-dasharray="6,5"'),
  );

  // 空气中的入射光（带箭头，方向指向入射点）
  const airLen = 7;
  const air = {
    x: entry.x - airLen * Math.cos(m.iDeg * DEG),
    y: entry.y - airLen * Math.sin(m.iDeg * DEG),
  };
  parts.push(
    line(X(air.x), Y(air.y), X(entry.x), Y(entry.y), 'stroke="#c0392b" stroke-width="2.4" marker-end="url(#arrow)"'),
  );

  // 入射角 i 角弧（法线反向与入射光之间）
  const rArc = 26;
  parts.push(
    `<path d="${arcPath(X, Y, entry.x, entry.y, rArc, 180, 180 + m.iDeg)}" fill="none" stroke="#c0392b" stroke-width="2" class="hl-target ${state.highlight === 'i' ? 'hl-on' : ''}" data-hl-target="i" data-physics-id="i"></path>`,
  );
  const iMid = arcMid(X, Y, entry.x, entry.y, rArc + 12, 180, 180 + m.iDeg);
  labels.push(labelAt(iMid.x, iMid.y, 'i', state.highlight === 'i' ? 'hl-on' : ''));

  // 管内光路（模型输出的折线）
  const pts = m.path.map((p) => `${X(p.x).toFixed(2)},${Y(p.y).toFixed(2)}`).join(' ');
  parts.push(
    `<polyline points="${pts}" fill="none" stroke="#c0392b" stroke-width="2.4" marker-end="url(#arrow)"></polyline>`,
  );

  // θ 角弧（管轴与管内光线之间，画在入射点）
  if (m.thetaDeg > 0.05) {
    parts.push(
      `<path d="${arcPath(X, Y, entry.x, entry.y, rArc + 14, 0, m.thetaDeg)}" fill="none" stroke="#2e7d32" stroke-width="2" class="hl-target ${state.highlight === 'theta' ? 'hl-on' : ''}" data-hl-target="theta" data-physics-id="theta"></path>`,
    );
    const tMid = arcMid(X, Y, entry.x, entry.y, rArc + 26, 0, m.thetaDeg);
    labels.push(labelAt(tMid.x, tMid.y, '\\theta', state.highlight === 'theta' ? 'hl-on' : ''));
  }

  // 右端出射光（短段，出射角等于 i）
  if (m.exit && m.thetaDeg > 0.05) {
    const sign = m.exit.goingUp ? 1 : -1;
    const outLen = 2.6;
    const out = {
      x: m.exit.x + outLen * Math.cos(m.exit.angleDeg * DEG),
      y: m.exit.y + sign * outLen * Math.sin(m.exit.angleDeg * DEG),
    };
    parts.push(
      line(X(m.exit.x), Y(m.exit.y), X(out.x), Y(out.y), 'stroke="#c0392b" stroke-width="2.4" marker-end="url(#arrow)"'),
    );
  }

  // 首次侧壁命中点：竖直法线、α 弧、C 参考弧
  if (m.firstHit) {
    const hit = { x: m.firstHit.x, y: m.firstHit.wall === 'top' ? ROD.h : 0 };
    const inward = m.firstHit.wall === 'top' ? 270 : 90; // 指向管内
    parts.push(
      line(X(hit.x), Y(hit.y - (m.firstHit.wall === 'top' ? 1.6 : -1.6)), X(hit.x), Y(hit.y + (m.firstHit.wall === 'top' ? ROD.h + 0.6 : -(ROD.h + 0.6))), 'stroke="#2b6cb0" stroke-width="1.4" stroke-dasharray="6,5"'),
    );
    if (withAngles && m.thetaDeg > 0.05) {
      // α：入射光反向（指向来路，180°+θ）与竖直法线之间
      parts.push(
        `<path d="${arcPath(X, Y, hit.x, hit.y, rArc, 180 + m.thetaDeg, inward)}" fill="none" stroke="#6a3fb5" stroke-width="2" class="hl-target ${state.highlight === 'alpha' ? 'hl-on' : ''}" data-hl-target="alpha" data-physics-id="alpha"></path>`,
      );
      const aMid = arcMid(X, Y, hit.x, hit.y, rArc + 12, 180 + m.thetaDeg, inward);
      labels.push(labelAt(aMid.x, aMid.y, '\\alpha', state.highlight === 'alpha' ? 'hl-on' : ''));
      // C：相对同一竖直法线的 60° 参考弧（虚线）
      const cStart = inward === 270 ? 270 - 60 : 90 + 60;
      parts.push(
        `<path d="${arcPath(X, Y, hit.x, hit.y, rArc + 26, Math.min(cStart, inward), Math.max(cStart, inward))}" fill="none" stroke="#e65100" stroke-width="2" stroke-dasharray="5,4" class="hl-target ${state.highlight === 'C' ? 'hl-on' : ''}" data-hl-target="C" data-physics-id="C"></path>`,
      );
      const cMid = arcMid(X, Y, hit.x, hit.y, rArc + 38, Math.min(cStart, inward), Math.max(cStart, inward));
      labels.push(labelAt(cMid.x, cMid.y, 'C', state.highlight === 'C' ? 'hl-on' : ''));
    }
  }

  // 临界：沿界面的折射光
  if (m.critical) {
    parts.push(
      line(X(m.critical.x), Y(m.critical.y), X(ROD.L), Y(m.critical.y), 'stroke="#e65100" stroke-width="2.4" stroke-dasharray="8,5" marker-end="url(#arrow)"'),
    );
    labels.push(labelAt(X((m.critical.x + ROD.L) / 2), Y(m.critical.y + (m.critical.wall === 'top' ? -1.6 : 1.6)), '\\text{沿界面折射}'));
  }

  // 逃逸：折射出管
  if (m.escape) {
    const beta = m.escape.refractionFromNormalDeg;
    const sign = m.escape.wall === 'top' ? 1 : -1;
    const outLen = 3.2;
    const out = {
      x: m.escape.x + outLen * Math.sin(beta * DEG),
      y: m.escape.y + sign * outLen * Math.cos(beta * DEG),
    };
    parts.push(
      line(X(m.escape.x), Y(m.escape.y), X(out.x), Y(out.y), 'stroke="#c0392b" stroke-width="2.4" marker-end="url(#arrow)"'),
    );
  }

  // 反射点序号
  if (withNumbers) {
    m.reflections.forEach((r) => {
      const y = r.wall === 'top' ? ROD.h : 0;
      parts.push(
        `<circle cx="${X(r.x)}" cy="${Y(y)}" r="3.4" fill="#173a5e" data-reflection-k="${r.k}" data-reflection-x="${r.x}"></circle>`,
      );
      const off = r.wall === 'top' ? -1.1 : 1.1;
      labels.push(labelAt(X(r.x), Y(y) + off, `${r.k}`, ''));
    });
  }

  // 拖动把手（空气入射光外端），与滑条共用 θ 入口
  if (withDrag) {
    parts.push(
      `<circle data-handle tabindex="0" role="slider" aria-label="入射光把手：方向键调节管内方向角 θ" aria-valuemin="0" aria-valuemax="35" aria-valuenow="${fmt(m.thetaDeg, 1)}" aria-valuetext="θ = ${fmt(m.thetaDeg, 1)}°" cx="${X(air.x)}" cy="${Y(air.y)}" r="9" fill="#fff" stroke="#c0392b" stroke-width="2.6" style="cursor:grab"></circle>`,
      `<circle cx="${X(air.x)}" cy="${Y(air.y)}" r="16" fill="transparent" data-handle-hit></circle>`,
    );
  }

  return {
    viewW,
    viewH,
    svg: `<svg width="${viewW}" height="${viewH}" viewBox="0 0 ${viewW} ${viewH}" role="img" aria-label="玻璃管纵截面光路图">${SVG_DEFS}${parts.join('')}</svg>`,
    labels: labels.join(''),
    fit: v,
  };
}

// ---------- 状态条文案（全部来自模型输出） ----------
function statusTag(m) {
  if (m.classification === 'tir') {
    return `<span class="status-tag tir">侧壁：全反射（${tex('\\alpha \\gt C')}）</span>`;
  }
  if (m.classification === 'critical') {
    return `<span class="status-tag critical">侧壁：临界（${tex('\\alpha = C')}，折射光沿界面，不算全反射）</span>`;
  }
  return `<span class="status-tag escape">侧壁：${tex('\\alpha \\lt C')}，不能维持全反射，光在首次侧壁折射出管</span>`;
}

function angleStrip(m) {
  return `<span class="kv-line">
    <span>${tex(`i = ${fmt(m.iDeg, 1)}^\\circ`)}</span>
    <span>${tex(`\\theta = ${fmt(m.thetaDeg, 1)}^\\circ`)}</span>
    <span>${tex(`\\alpha = ${fmt(m.alphaDeg, 1)}^\\circ`)}</span>
    <span>${tex(`C = ${fmt(m.criticalDeg, 0)}^\\circ`)}</span>
  </span>`;
}

/** 场景 1「找边界」的水平连续滑条：可见量 θ，范围 0°–35°，步长 0.1°。 */
function thetaSliderHtml() {
  return `
  <div class="theta-slider" data-theta-control>
    <label for="theta-range">拖动滑条连续改变管内方向角 ${tex('\\theta')}；管内方向永远由折射定律反算，不是画出来的。</label>
    <div class="theta-slider-row">
      <span class="theta-end">0°</span>
      <input type="range" id="theta-range" data-theta-slider min="0" max="35" step="0.1"
        value="${fmt(model.thetaDeg, 1)}"
        aria-label="管内方向角 θ，0 到 35 度"
        aria-valuetext="θ = ${fmt(model.thetaDeg, 1)}°">
      <span class="theta-end">35°</span>
      <span class="theta-value" data-theta-readout>${tex(`\\theta = ${fmt(model.thetaDeg, 1)}^\\circ`)}</span>
    </div>
  </div>`;
}

/** 场景 1 状态条末行的计数文案（全部来自模型输出）。 */
function countLineText(m) {
  if (m.classification === 'tir') {
    return m.count === 0
      ? '管内反射 0 次：光沿中线直行，从右端出射。'
      : `管内反射 ${m.count} 次（反射点已在图中编号），随后从右端出射。`;
  }
  if (m.classification === 'critical') {
    return '临界方向：折射光沿界面传播，不计入管内反射。';
  }
  return '主光路在首次侧壁处折射出管，管内反射计数在此终止（界面附近可能仍有微弱反射，此处不画出）。';
}

// ---------- 场景 0：读原题 ----------
function renderScene0() {
  return `
  <section class="scene" data-scene="s0">
    <div class="task-bar">任务：读原题，不看任何解答。然后先凭直觉预测一次——这个预测不计对错，之后可以用课件检验它。</div>
    <figure class="source-fig">
      <img src="assets/source.png" alt="原题截图：实心玻璃管长 40 cm、宽 4 cm、折射率 2/√3，光从左端正中心射入，求最多反射次数。">
      <figcaption>原题（题干与题图）。注意：题图只画了一条示意光线，并没有给出角度数值。</figcaption>
    </figure>
    <div class="panel" style="max-width:980px">
      <h2>先预测</h2>
      <p>如果让入射光的方向改变，光在管中反射的次数会怎样变化？</p>
      <div class="radio-group" role="radiogroup" aria-label="预测反射次数如何变化">
        <label><input type="radio" name="p0" value="flatter" ${state.prediction0 === 'flatter' ? 'checked' : ''}> 方向越平（越贴近管轴），反射越多</label>
        <label><input type="radio" name="p0" value="steeper" ${state.prediction0 === 'steeper' ? 'checked' : ''}> 方向越陡（越接近某个上限），反射越多</label>
        <label><input type="radio" name="p0" value="none" ${state.prediction0 === 'none' ? 'checked' : ''}> 反射次数与方向无关</label>
      </div>
      <p class="hint">预测可以随时改写。带着它去「找边界」看看光到底是怎么走的。</p>
    </div>
  </section>`;
}

// ---------- 场景 1：找边界（角度识别 → 连续探索 → 静态核对，同一场内步骤） ----------
function finderStepTabs() {
  const steps = [
    ['angles', '角度识别'],
    ['explore', '连续探索'],
    ['verify', '静态核对'],
  ];
  const buttons = steps
    .map(
      ([key, label], idx) =>
        `<button type="button" role="tab" data-finder-step="${key}" aria-selected="${state.finderStep === key}">${idx + 1}. ${label}</button>`,
    )
    .join('');
  return `<div class="step-tabs" role="tablist" aria-label="找边界场内步骤">${buttons}</div>`;
}

function renderScene1() {
  const step = state.finderStep;
  const g = tubeSvg(model, {
    withAngles: step !== 'explore',
    withNumbers: step === 'explore',
    withDrag: true,
  });
  const taskText = {
    angles: `任务：拖动滑条（也可以拖图中的入射光把手，或用 <kbd>←</kbd><kbd>→</kbd> 方向键）改变入射方向，看清 ${tex('i')}、${tex('\\theta')}、${tex('\\alpha')}、${tex('C')} 分别是相对哪条法线量出来的角。点击符号可在图中高亮对应角弧。`,
    explore: `任务：把滑条从 ${tex('\\theta = 0^\\circ')} 缓慢拖向更大的角度，观察反射点怎样变多；当侧壁状态第一次变成「临界」时停下来，记下此刻的角度。`,
    verify: '任务：把观察写成关系式。核对三条关系和严格不等式，再用几个关键角度做考试语义的核对。',
  }[step];

  // 状态条只在连续探索与静态核对步骤在场；角度识别步骤不显示分类与反射次数
  const statusStrip =
    step === 'angles'
      ? ''
      : `<div class="status-strip" data-status data-theta="${model.thetaDeg}" data-classification="${model.classification}" data-count="${model.count}">
        ${statusTag(model)}
        ${angleStrip(model)}
        <span data-count-line>${countLineText(model)}</span>
      </div>`;

  let explain = '';
  if (step === 'angles') {
    const angleChips = [
      { key: 'i', symbol: 'i' },
      { key: 'theta', symbol: '\\theta' },
      { key: 'alpha', symbol: '\\alpha' },
      { key: 'C', symbol: 'C' },
    ]
      .map(
        (item) =>
          `<button type="button" class="chip" data-hl="${item.key}" data-physics-ref="${item.key}">${tex(item.symbol)}</button>`,
      )
      .join('');
    explain = `
      <p>图中有两条法线：左端面的法线是<strong>水平</strong>的（蓝色虚线），侧壁的法线是<strong>竖直</strong>的。每个角都相对自己的那条法线量出，拖动时它们一起联动。</p>
      <div class="chip-row">在图中找：${angleChips}</div>
      <div class="readings" data-readings data-i="${model.iDeg}" data-theta="${model.thetaDeg}" data-alpha="${model.alphaDeg}">${angleStrip(model)}</div>
      <p class="hint">这里只认清「哪个角对哪条法线」，不急着下结论；它们之间的确切关系和全反射的边界，先用连续拖动去发现，再写成式子。</p>`;
  } else if (step === 'explore') {
    explain = `
      <div class="predict-inline" role="radiogroup" aria-label="预测角度变平后反射次数">
        <span>先预测：让 ${tex('\\theta')} 更小（光更平），反射次数会——</span>
        <label><input type="radio" name="p2" value="more" ${state.prediction2 === 'more' ? 'checked' : ''}> 变多</label>
        <label><input type="radio" name="p2" value="less" ${state.prediction2 === 'less' ? 'checked' : ''}> 变少</label>
        <label><input type="radio" name="p2" value="flat" ${state.prediction2 === 'flat' ? 'checked' : ''}> 不变</label>
      </div>
      <p>从 ${tex('\\theta = 0^\\circ')}（水平直行）出发，缓慢把滑条拖大。观察反射点什么时候出现、怎样变密，以及侧壁状态标签什么时候从「全反射」变成「临界」。</p>
      <p class="hint">状态第一次变成「临界」时就停下来，记下此刻的 ${tex('\\theta')}；再拖过它一点，看光路发生了什么。</p>
      <p class="notice-line" data-crossed-note ${state.crossedBoundary ? '' : 'hidden'}>已完成一次跨越临界的连续探索。「静态核对」中的关键值核对现在可以使用了。</p>`;
  } else {
    const presets = [
      { theta: 0, label: '\\theta = 0^\\circ', name: '水平直行' },
      { theta: 29, label: '\\theta = 29^\\circ', name: '接近边界' },
      { theta: 30, label: '\\theta = 30^\\circ', name: '临界' },
      { theta: 35, label: '\\theta = 35^\\circ', name: '越过边界' },
    ];
    const buttons = presets
      .map(
        (p) =>
          `<button type="button" data-preset="${p.theta}" class="${Math.abs(model.thetaDeg - p.theta) < 0.05 ? 'active' : ''}">${tex(p.label)} ${p.name}</button>`,
      )
      .join('');
    const presetBlock = state.showKeyCheck
      ? `<div class="preset-row" data-presets>选方向核对：${buttons}<span class="drag-hint">关键值同样由折射定律反算，滑条与把手保持同步</span></div>`
      : '';
    // 未真实跨越临界前，关键值核对只作为次级提示，不作为首要体验
    const keyCheck = state.crossedBoundary
      ? `<button type="button" class="action-btn" data-preset-gate ${state.showKeyCheck ? 'hidden' : ''}>用关键值核对（0° / 29° / 30° / 35°）</button>${presetBlock}`
      : '<p class="hint">关键值核对是次级工具：先在「连续探索」中真实跨越一次临界，再回来用它固定考试语义。</p>';
    explain = `
      <p>三条关系（顺序即推导），符号与图中角弧一一对应：</p>
      ${formulaBlock('eq-snell', '式(1) 折射定律（左端面，法线水平）', '\\sin i = n\\,\\sin\\theta', {
        hl: [
          { key: 'i', symbol: 'i' },
          { key: 'theta', symbol: '\\theta' },
        ],
      })}
      ${formulaBlock('eq-complement', '式(2) 互余关系（侧壁法线竖直）', '\\alpha = 90^\\circ - \\theta', {
        hl: [
          { key: 'alpha', symbol: '\\alpha' },
          { key: 'theta', symbol: '\\theta' },
        ],
      })}
      ${formulaBlock('eq-critical', '式(3) 临界角（玻璃到空气）', '\\sin C = \\dfrac{1}{n}', {
        sub: `\\sin C = \\dfrac{\\sqrt{3}}{2},\\quad C = 60^\\circ`,
        hl: [{ key: 'C', symbol: 'C' }],
      })}
      <p>全反射要求侧壁入射角严格大于临界角：${tex('\\alpha \\gt C')}。用${refLink('eq-complement', '式(2)')}换成轴向角，就是 ${tex('\\theta \\lt 30^\\circ')}。${tex('\\theta = 30^\\circ')} 是临界而不是全反射，所以 ${tex('30^\\circ')} 本身取不到；要反射最多，方向要从 ${tex('30^\\circ')} 左侧逼近。</p>
      ${keyCheck}
      <p class="hint">最终最多反射多少次，这里不直接给答案——带着 ${tex('\\theta \\lt 30^\\circ')} 去「判定上限」证明它。</p>`;
  }

  return `
  <section class="scene scene-finder" data-scene="s1">
    <div class="task-bar">${taskText}</div>
    <div class="finder-layout">
      <div class="visual-col" data-visual>
        <div class="stage" data-stage style="width:${g.viewW}px;height:${g.viewH}px">
          ${g.svg}
          ${g.labels}
        </div>
        ${statusStrip}
        ${thetaSliderHtml()}
      </div>
      <div class="explain-col" data-explain>
        ${finderStepTabs()}
        ${explain}
      </div>
    </div>
  </section>`;
}

// ---------- 场景 3：拆开步长 ----------
function foldedStepSvg(m, k) {
  const viewW = 640;
  const viewH = 250;
  const v = fitView(-3, 44, -4.2, 7.6, viewW, viewH, 24);
  const { X, Y } = v;
  const parts = [];
  const labels = [];
  parts.push(
    `<rect x="${X(0)}" y="${Y(ROD.h)}" width="${X(ROD.L) - X(0)}" height="${Y(0) - Y(ROD.h)}" fill="#e8f1f8" stroke="#173a5e" stroke-width="2"></rect>`,
  );
  const pts = m.path.map((p) => `${X(p.x).toFixed(2)},${Y(p.y).toFixed(2)}`).join(' ');
  parts.push(`<polyline points="${pts}" fill="none" stroke="#c0392b" stroke-width="2.4" marker-end="url(#arrow)"></polyline>`);
  m.reflections.forEach((r) => {
    const y = r.wall === 'top' ? ROD.h : 0;
    const isSel = r.k === k;
    parts.push(
      `<circle cx="${X(r.x)}" cy="${Y(y)}" r="${isSel ? 5.4 : 3.4}" fill="${isSel ? '#e65100' : '#173a5e'}" data-reflection-k="${r.k}" data-reflection-x="${r.x}"></circle>`,
    );
    const off = r.wall === 'top' ? -1.1 : 1.1;
    labels.push(labelAt(X(r.x), Y(y) + off, `${r.k}`));
  });
  annotateStep(v, m, k, parts, labels, false);
  return {
    viewW,
    viewH,
    svg: `<svg width="${viewW}" height="${viewH}" viewBox="0 0 ${viewW} ${viewH}" role="img" aria-label="折叠光路：玻璃管内实际反射路径">${SVG_DEFS}${parts.join('')}</svg>`,
    labels: labels.join(''),
  };
}

function unfoldedStepSvg(m, k) {
  const tanTheta = Math.tan(m.thetaDeg * DEG);
  const yEnd = ROD.h / 2 + ROD.L * tanTheta;
  const viewW = 640;
  const viewH = 330;
  const v = fitView(-3, 43, -4.2, yEnd + 2.5, viewW, viewH, 24);
  const { X, Y } = v;
  const parts = [];
  const labels = [];
  // 镜像展开的管：每一格高 4 cm，交替加深
  const bands = Math.ceil(yEnd / ROD.h);
  for (let b = 0; b <= bands; b += 1) {
    const y0 = b * ROD.h;
    const fill = b % 2 === 0 ? '#e8f1f8' : '#dbe7f0';
    parts.push(
      `<rect x="${X(0)}" y="${Y(y0 + ROD.h)}" width="${X(ROD.L) - X(0)}" height="${Y(y0) - Y(y0 + ROD.h)}" fill="${fill}" stroke="#173a5e" stroke-width="1.2"></rect>`,
    );
  }
  // 展开后光路是一条直线
  parts.push(
    line(X(0), Y(ROD.h / 2), X(ROD.L), Y(yEnd), 'stroke="#c0392b" stroke-width="2.4" marker-end="url(#arrow)"'),
  );
  // 同一组反射事件：直线与格线的交点，序号与折叠图一致
  m.reflections.forEach((r) => {
    const yU = ROD.h / 2 + r.x * tanTheta;
    const isSel = r.k === k;
    parts.push(
      `<circle cx="${X(r.x)}" cy="${Y(yU)}" r="${isSel ? 5.4 : 3.4}" fill="${isSel ? '#e65100' : '#173a5e'}" data-reflection-k="${r.k}" data-reflection-x="${r.x}"></circle>`,
    );
    labels.push(labelAt(X(r.x), Y(yU) - 0.9, `${r.k}`));
  });
  // 选中段的高亮（展开坐标）
  if (k >= 1 && k <= m.count) {
    const xPrev = k === 1 ? 0 : m.reflections[k - 2].x;
    const xHit = m.reflections[k - 1].x;
    parts.push(
      line(X(xPrev), Y(ROD.h / 2 + xPrev * tanTheta), X(xHit), Y(ROD.h / 2 + xHit * tanTheta), `stroke="#e65100" stroke-width="5" opacity="0.45" class="hl-target ${state.highlight === 'xk' ? 'hl-on' : ''}" data-hl-target="xk" data-physics-id="xk"`),
    );
    // 竖直位移标注：首段 2 cm，后续 4 cm
    const dy = k === 1 ? 2 : 4;
    const xMark = xHit + 1.0;
    parts.push(
      line(X(xMark), Y(ROD.h / 2 + xPrev * tanTheta), X(xMark), Y(ROD.h / 2 + xHit * tanTheta), `stroke="#2e7d32" stroke-width="1.6" marker-start="url(#arrow-dim)" marker-end="url(#arrow-dim)" class="hl-target ${state.highlight === (k === 1 ? 'first' : 'period') ? 'hl-on' : ''}" data-hl-target="${k === 1 ? 'first' : 'period'}" data-physics-id="${k === 1 ? 'first' : 'period'}"`),
    );
    labels.push(
      labelAt(X(xMark) + 14, (Y(ROD.h / 2 + xPrev * tanTheta) + Y(ROD.h / 2 + xHit * tanTheta)) / 2, `${dy}\\ \\text{cm}`, state.highlight === (k === 1 ? 'first' : 'period') ? 'hl-on' : ''),
    );
  }
  // x_k 水平位置标注
  if (k >= 1 && k <= m.count) {
    const xk = m.reflections[k - 1].x;
    parts.push(
      line(X(0), Y(-2.2), X(xk), Y(-2.2), 'stroke="#37485a" stroke-width="1.4" marker-start="url(#arrow-dim)" marker-end="url(#arrow-dim)"'),
      line(X(0), Y(-2.8), X(0), Y(-1.4), 'stroke="#37485a" stroke-width="1.2"'),
      line(X(xk), Y(-2.8), X(xk), Y(-1.4), 'stroke="#37485a" stroke-width="1.2"'),
    );
    labels.push(labelAt((X(0) + X(xk)) / 2, Y(-3.3), `x_{${k}}`, state.highlight === 'xk' ? 'hl-on' : ''));
  }
  return {
    viewW,
    viewH,
    svg: `<svg width="${viewW}" height="${viewH}" viewBox="0 0 ${viewW} ${viewH}" role="img" aria-label="展开光路：把每次反射后的管镜像翻折，光路成为一条直线">${SVG_DEFS}${parts.join('')}</svg>`,
    labels: labels.join(''),
  };
}

/** 折叠视图中选中段的竖直位移与水平位置标注。 */
function annotateStep(v, m, k, parts, labels) {
  if (k < 1 || k > m.count) return;
  const { X, Y } = v;
  const hit = m.reflections[k - 1];
  const prev = k === 1 ? { x: 0, y: ROD.h / 2 } : {
    x: m.reflections[k - 2].x,
    y: m.reflections[k - 2].wall === 'top' ? ROD.h : 0,
  };
  const hitY = hit.wall === 'top' ? ROD.h : 0;
  // 高亮选中段
  parts.push(
    line(X(prev.x), Y(prev.y), X(hit.x), Y(hitY), `stroke="#e65100" stroke-width="5" opacity="0.45" class="hl-target ${state.highlight === 'xk' ? 'hl-on' : ''}" data-hl-target="xk" data-physics-id="xk"`),
  );
  // 竖直位移：首段 2 cm、后续 4 cm
  const dy = k === 1 ? 2 : 4;
  const xMark = Math.min(hit.x + 1.0, ROD.L - 1.5);
  parts.push(
    line(X(xMark), Y(prev.y), X(xMark), Y(hitY), `stroke="#2e7d32" stroke-width="1.6" marker-start="url(#arrow-dim)" marker-end="url(#arrow-dim)" class="hl-target ${state.highlight === (k === 1 ? 'first' : 'period') ? 'hl-on' : ''}" data-hl-target="${k === 1 ? 'first' : 'period'}" data-physics-id="${k === 1 ? 'first' : 'period'}"`),
  );
  labels.push(
    labelAt(X(xMark) + 16, (Y(prev.y) + Y(hitY)) / 2, `${dy}\\ \\text{cm}`, state.highlight === (k === 1 ? 'first' : 'period') ? 'hl-on' : ''),
  );
  // 水平位置 x_k（距左端）
  parts.push(
    line(X(0), Y(-2.2), X(hit.x), Y(-2.2), 'stroke="#37485a" stroke-width="1.4" marker-start="url(#arrow-dim)" marker-end="url(#arrow-dim)"'),
    line(X(0), Y(-2.8), X(0), Y(-1.4), 'stroke="#37485a" stroke-width="1.2"'),
    line(X(hit.x), Y(-2.8), X(hit.x), Y(-1.4), 'stroke="#37485a" stroke-width="1.2"'),
  );
  labels.push(labelAt((X(0) + X(hit.x)) / 2, Y(-3.3), `x_{${k}}`, state.highlight === 'xk' ? 'hl-on' : ''));
}

function renderScene3() {
  const k = state.selectedK;
  const g = state.unfold ? unfoldedStepSvg(model, k) : foldedStepSvg(model, k);
  const maxK = Math.max(1, model.count);
  const sub = k <= model.count
    ? `x_{${k}} = \\dfrac{4\\times ${k} - 2}{\\tan ${fmt(model.thetaDeg, 0)}^\\circ} = \\dfrac{${4 * k - 2}}{${fmt(Math.tan(model.thetaDeg * DEG), 4)}} \\approx ${fmt(model.reflections[k - 1].x, 2)}\\ \\text{cm}`
    : '';
  return `
  <section class="scene" data-scene="s3">
    ${state.notice ? `<div class="notice-bar">${state.notice}</div>` : ''}
    <div class="task-bar">任务：把弹来弹去的光路拆成能算的步长。先看首段与后面每一段有什么不同，再点选反射点，核对它的水平位置怎么算出来。</div>
    <div class="panel" style="max-width:none">
      <div class="preset-row">
        <button type="button" class="action-btn ${state.unfold ? '' : 'primary'}" data-view="folded">折叠光路（管内真实路径）</button>
        <button type="button" class="action-btn ${state.unfold ? 'primary' : ''}" data-view="unfolded">展开光路（镜像翻折成直线）</button>
        <span class="hint">两种看法是同一条光路、同一组反射事件，序号一一对应。</span>
      </div>
      <div class="preset-row">
        <span>点选反射点：</span>
        <button type="button" class="action-btn ${k === 1 ? 'primary' : ''}" data-select-k="1">第 1 个</button>
        <button type="button" class="action-btn ${k === 2 ? 'primary' : ''}" data-select-k="2" ${maxK < 2 ? 'disabled' : ''}>第 2 个</button>
        <label>第 <input type="number" data-select-k-input min="1" max="${maxK}" step="1" value="${k}" style="width:64px"> 个（共 ${model.count} 个）</label>
      </div>
    </div>
    <div class="scene-body">
      <div class="stage" data-stage style="width:${g.viewW}px;height:${g.viewH}px">
        ${g.svg}
        ${g.labels}
      </div>
      <div class="panel">
        <h2>从步长到通项</h2>
        <p>首段竖直位移 <button type="button" class="chip" data-hl="first" data-physics-ref="first">${tex('2\\ \\text{cm}')}</button>（半个管宽），之后每段 <button type="button" class="chip" data-hl="period" data-physics-ref="period">${tex('4\\ \\text{cm}')}</button>（一个管宽）；各段水平方向都是同一个 ${tex('\\theta')}。</p>
        ${formulaBlock('eq-xk', '式(4) 反射点位置', 'x_k = \\dfrac{2 + 4(k-1)}{\\tan\\theta} = \\dfrac{4k - 2}{\\tan\\theta}', {
          sub,
          hl: [{ key: 'xk', symbol: 'x_k' }],
        })}
        <p class="hint">注意区分：相邻两个反射点的间距是 ${tex('\\dfrac{4}{\\tan\\theta}')}，而第 ${k} 个反射点的位置 ${tex(`x_{${k}}`)} 是从左端量起的（${refLink('eq-xk', '式(4)')}）。全量反射点表与最终最大值留到「判定上限」。</p>
      </div>
    </div>
  </section>`;
}

// ---------- 场景 4：判定上限 ----------
function intervalSvg() {
  const f = feasibility();
  const viewW = 620;
  const viewH = 150;
  const minT = 27;
  const maxT = 35;
  const margin = 30;
  const X = (t) => margin + ((t - minT) / (maxT - minT)) * (viewW - 2 * margin);
  const rows = [
    { y: 50, min: f.sixMinDeg, ok: true, title: '第 6 次' },
    { y: 110, min: f.sevenMinDeg, ok: false, title: '第 7 次' },
  ];
  const parts = [];
  const labels = [];
  rows.forEach((row) => {
    // 全反射允许区 θ<30°：浅色底
    parts.push(
      `<rect x="${X(minT)}" y="${row.y - 8}" width="${X(f.tirLimitDeg) - X(minT)}" height="16" fill="#e6f4ea"></rect>`,
      `<rect x="${X(f.tirLimitDeg)}" y="${row.y - 8}" width="${X(maxT) - X(f.tirLimitDeg)}" height="16" fill="#fdecea"></rect>`,
    );
    parts.push(
      line(X(minT), row.y, X(maxT), row.y, 'stroke="#37485a" stroke-width="1.4" marker-end="url(#arrow-dim)"'),
    );
    [28, 29, 30, 31, 32, 33, 34].forEach((t) => {
      parts.push(line(X(t), row.y - 4, X(t), row.y + 4, 'stroke="#37485a" stroke-width="1"'));
      labels.push(labelAt(X(t), row.y + 14, `${t}^\\circ`));
    });
    // 计数可行要求 θ > 阈值：粗线标出要求区间
    parts.push(
      line(X(row.min), row.y, X(maxT), row.y, `stroke="${row.ok ? '#2e7d32' : '#c62828'}" stroke-width="5" opacity="0.55"`),
    );
    labels.push(labelAt(X(row.min), row.y - 14, `${fmt(row.min, 2)}^\\circ`));
    labels.push(labelAt(X(minT) - 6, row.y, `\\text{${row.title}}`));
  });
  labels.push(labelAt(X(f.tirLimitDeg), 24, '\\theta = 30^\\circ\\ \\text{（全反射上限，取不到）}'));
  parts.push(line(X(f.tirLimitDeg), 34, X(f.tirLimitDeg), 124, 'stroke="#e65100" stroke-width="1.6" stroke-dasharray="6,4"'));
  return `<svg width="${viewW}" height="${viewH}" viewBox="0 0 ${viewW} ${viewH}" role="img" aria-label="第 6 次与第 7 次反射的可行区间数轴">${SVG_DEFS}${parts.join('')}</svg>${labels.join('')}`;
}

function renderScene4() {
  const f = feasibility();
  const choicesMade = state.choice6 !== '' && state.choice7 !== '';
  const bothShown = state.show6 && state.show7;
  const block6 = state.show6
    ? `<div class="reveal-block" data-reveal="6">
        ${formulaBlock('eq-six', '式(5) 第 6 次可行的条件', 'x_6 \\lt 40\\ \\text{cm} \\iff \\tan\\theta \\gt \\dfrac{22}{40} = 0.55', {
          sub: `\\theta \\gt ${fmt(f.sixMinDeg, 2)}^\\circ,\\quad \\text{与 } \\theta \\lt 30^\\circ \\text{ 联立：} ${fmt(f.sixMinDeg, 2)}^\\circ \\lt \\theta \\lt 30^\\circ`,
        })}
        <p>这个开区间非空（例如 ${tex('\\theta = 29^\\circ')}），所以第 6 次反射<strong>可行</strong>。你的选择：${state.choice6 === 'yes' ? '可行' : '不可行'}。</p>
      </div>`
    : '';
  const block7 = state.show7
    ? `<div class="reveal-block" data-reveal="7">
        ${formulaBlock('eq-seven', '式(6) 第 7 次可行的条件', 'x_7 \\lt 40\\ \\text{cm} \\iff \\tan\\theta \\gt \\dfrac{26}{40} = 0.65', {
          sub: `\\theta \\gt ${fmt(f.sevenMinDeg, 2)}^\\circ \\gt 30^\\circ,\\quad \\text{与全反射限制冲突}`,
        })}
        <p>满足第 7 次的方向必然失去全反射，所以第 7 次<strong>不可行</strong>。你的选择：${state.choice7 === 'yes' ? '可行' : '不可行'}。</p>
      </div>`
    : '';
  const conclusion = bothShown
    ? `<div class="conclusion" data-conclusion>
        <strong>结论：光最多可以在管中反射 6 次。</strong><br>
        证明骨架：${tex('\\sin C = 1/n')} 得 ${tex('C = 60^\\circ')}；${tex('\\alpha = 90^\\circ - \\theta \\gt C')} 给出严格限制 ${tex('\\theta \\lt 30^\\circ')}；${refLink('eq-xk-4', '式(4)')} ${tex('x_k = (4k-2)/\\tan\\theta')}；由${refLink('eq-six', '式(5)')}与${refLink('eq-seven', '式(6)')}：6 次可行、7 次不可行。<br>
        边界约定：${tex('x_k = 40\\ \\text{cm}')} 恰好落在右端棱边上时<strong>不计</strong>为管内反射（严格小于）；${tex('\\theta = 30^\\circ')} 是临界而不是全反射，所以区间右端取不到——但开区间 ${tex(`(${fmt(f.sixMinDeg, 2)}^\\circ,\\ 30^\\circ)`)} 内任意方向都能实现 6 次。
      </div>`
    : '';
  return `
  <section class="scene" data-scene="s4">
    <div class="task-bar">任务：不翻前面的动画，用两条不等式判定：第 6 次反射可不可行？第 7 次呢？先写下你的判断，再展开检查。</div>
    <div class="panel" style="max-width:none">
      <h2>题设与必要关系</h2>
      <p>管长 ${tex('L = 40\\ \\text{cm}')}、宽 ${tex('h = 4\\ \\text{cm}')}、折射率 ${tex('n = \\dfrac{2}{\\sqrt{3}}')}，光从左端正中心射入；${tex('C = 60^\\circ')}（式(3)）。</p>
      <p>全反射限制：${tex('\\theta \\lt 30^\\circ')}（由式(2)、式(3)）；只有严格 ${tex('x_k \\lt 40\\ \\text{cm}')} 的侧壁命中才计入反射次数。</p>
      ${formulaBlock('eq-xk-4', '式(4) 反射点位置', 'x_k = \\dfrac{4k - 2}{\\tan\\theta}')}
    </div>
    <div class="panel" style="max-width:none">
      <h2>先作判断</h2>
      <div class="preset-row">
        <span>第 6 次反射可行吗？</span>
        <label><input type="radio" name="c6" value="yes" ${state.choice6 === 'yes' ? 'checked' : ''}> 可行</label>
        <label><input type="radio" name="c6" value="no" ${state.choice6 === 'no' ? 'checked' : ''}> 不可行</label>
      </div>
      <div class="preset-row">
        <span>第 7 次反射可行吗？</span>
        <label><input type="radio" name="c7" value="yes" ${state.choice7 === 'yes' ? 'checked' : ''}> 可行</label>
        <label><input type="radio" name="c7" value="no" ${state.choice7 === 'no' ? 'checked' : ''}> 不可行</label>
      </div>
      <p>理由方向：<input type="text" data-reason size="52" maxlength="120" placeholder="例如：要看 θ 能否同时满足位置条件和全反射限制" value="${state.reason4.replace(/"/g, '&quot;')}"></p>
      <div class="preset-row">
        <button type="button" class="action-btn" data-reveal-btn="6" ${choicesMade && !state.show6 ? '' : 'disabled'}>展开第 6 次的检查</button>
        <button type="button" class="action-btn" data-reveal-btn="7" ${choicesMade && !state.show7 ? '' : 'disabled'}>展开第 7 次的检查</button>
        ${choicesMade ? '' : '<span class="hint">先完成上面两个选择，再展开检查。</span>'}
      </div>
    </div>
    ${block6}
    ${block7}
    ${bothShown ? `<div class="stage" data-stage style="width:620px;height:150px">${intervalSvg()}</div>` : ''}
    ${conclusion}
  </section>`;
}

// ---------- 老师审计 ----------
function renderAudit() {
  const f = feasibility();
  const s29 = computeFromTheta(29);
  const s30 = computeFromTheta(30);
  const s35 = computeFromTheta(35);
  const s0 = computeFromTheta(0);
  const edgeTheta = Math.atan(0.55) / DEG;
  const sEdge = computeFromTheta(edgeTheta);
  const mid = (f.sixMinDeg + f.tirLimitDeg) / 2;
  const sMid = computeFromTheta(mid);
  const assertions = [
    [`${tex('\\theta = 30^\\circ')} 分类为临界，不标为全反射`, s30.classification === 'critical' && s30.count === 0],
    [`${tex('\\theta = 29^\\circ')}：${tex('\\alpha = 61^\\circ \\gt C = 60^\\circ')}，严格全反射`, s29.classification === 'tir' && Math.abs(s29.alphaDeg - 61) < 1e-9],
    [`${tex('\\theta = 29^\\circ')}：反射 6 次，${tex(`x_6 \\approx ${fmt(reflectionX(6, 29), 2)}\\ \\text{cm} \\lt 40`)}，${tex(`x_7 \\approx ${fmt(reflectionX(7, 29), 2)}\\ \\text{cm} \\gt 40`)}`, s29.count === 6 && reflectionX(6, 29) < ROD.L && reflectionX(7, 29) > ROD.L],
    [`${tex('\\theta = 29^\\circ')}：入口 ${tex(`i \\approx ${fmt(s29.iDeg, 2)}^\\circ`)} 由 Snell 反算产生，右端出射角等于 ${tex('i')}`, Math.abs(s29.iDeg - 34.04) < 0.01 && Math.abs(s29.exit.angleDeg - s29.iDeg) < 1e-9],
    [`${tex('\\theta = 35^\\circ')}：首次侧壁折射出管，主计数光路终止`, s35.classification === 'escape' && s35.count === 0 && s35.escape !== null],
    [`${tex('\\theta = 0^\\circ')}：0 次反射，沿中线从右端中心出射`, s0.count === 0 && Math.abs(s0.exit.y - ROD.h / 2) < 1e-9],
    [`${tex('x_6 = 40\\ \\text{cm}')} 恰在棱边（${tex('\\tan\\theta = 0.55')}）：只计 5 次，端点不计`, sEdge.count === 5 && sEdge.edgeHit !== null && sEdge.edgeHit.k === 6],
    [`第 6 次可行开区间 ${tex(`(${fmt(f.sixMinDeg, 2)}^\\circ,\\ 30^\\circ)`)} 非空，中点真实实现 6 次`, f.sixMinDeg < f.tirLimitDeg && sMid.count === 6 && sMid.classification === 'tir'],
    [`第 7 次要求 ${tex(`\\theta \\gt ${fmt(f.sevenMinDeg, 2)}^\\circ`)}，与全反射限制冲突`, f.sevenMinDeg > f.tirLimitDeg],
  ];
  const items = assertions
    .map(
      ([text, pass]) =>
        `<li class="${pass ? 'pass' : 'fail'}" data-assertion="${pass ? 'pass' : 'fail'}">${pass ? '✓' : '✗'} ${text}</li>`,
    )
    .join('');
  return `
  <section class="scene" data-scene="audit" data-audience="internal">
    <div class="task-bar">老师审计视图：关系式、关键节点值与硬断言一页收齐。此页不进入学生学习路径。<button type="button" class="action-btn" data-audit-back>返回学习路径</button></div>
    <div class="audit-section">
      <h2>关系式</h2>
      ${formulaBlock('audit-eq1', '式(1) 折射定律（空气折射率取 1，玻璃为 n）', '\\sin i = n\\,\\sin\\theta,\\quad n = \\dfrac{2}{\\sqrt{3}}')}
      ${formulaBlock('audit-eq2', '式(2) 互余关系', '\\alpha = 90^\\circ - \\theta')}
      ${formulaBlock('audit-eq3', '式(3) 临界角', '\\sin C = \\dfrac{1}{n} = \\dfrac{\\sqrt{3}}{2},\\quad C = 60^\\circ', {
        sub: '\\text{严格全反射 } \\alpha \\gt C \\iff \\theta \\lt 30^\\circ',
      })}
      ${formulaBlock('audit-eq4', '式(4) 反射点位置（首段 2 cm，周期段 4 cm）', 'x_k = \\dfrac{4k - 2}{\\tan\\theta},\\quad \\text{严格 } x_k \\lt 40\\ \\text{cm} \\text{ 才计数}')}
      ${formulaBlock('audit-eq5', '式(5)(6) 第 6/7 次阈值', 'x_6 \\lt 40 \\iff \\tan\\theta \\gt 0.55;\\qquad x_7 \\lt 40 \\iff \\tan\\theta \\gt 0.65', {
        sub: `\\theta \\gt ${fmt(f.sixMinDeg, 2)}^\\circ\\ (\\text{可行});\\qquad \\theta \\gt ${fmt(f.sevenMinDeg, 2)}^\\circ\\ (\\text{与全反射冲突})`,
      })}
    </div>
    <div class="audit-section">
      <h2>关键节点值</h2>
      <p class="kv-line">
        <span>${tex('\\theta = 29^\\circ')}</span>
        <span>${tex(`i \\approx ${fmt(s29.iDeg, 2)}^\\circ`)}</span>
        <span>${tex('\\alpha = 61^\\circ')}</span>
        <span>${tex(`x_1 \\approx ${fmt(reflectionX(1, 29), 2)}\\ \\text{cm}`)}</span>
        <span>${tex(`x_6 \\approx ${fmt(reflectionX(6, 29), 2)}\\ \\text{cm} \\lt 40`)}</span>
        <span>${tex(`x_7 \\approx ${fmt(reflectionX(7, 29), 2)}\\ \\text{cm} \\gt 40`)}</span>
      </p>
      <p class="kv-line">
        <span>${tex('\\theta = 30^\\circ')}</span><span>临界，沿界面折射</span>
        <span>${tex('\\theta = 35^\\circ')}</span><span>首次侧壁折射出管</span>
        <span>${tex('\\theta = 0^\\circ')}</span><span>0 次反射，右端中心出射</span>
      </p>
    </div>
    <div class="audit-section">
      <h2>硬断言（由模型实时计算）</h2>
      <ul class="assertion-list" data-assertions>${items}</ul>
    </div>
  </section>`;
}

// ---------- 场景切换与事件 ----------
const sceneRoot = document.getElementById('scene-root');

function currentRender() {
  switch (state.scene) {
    case 's0': return renderScene0();
    case 's1': return renderScene1();
    case 's3': return renderScene3();
    case 's4': return renderScene4();
    case 'audit': return renderAudit();
    default: return renderScene0();
  }
}

function render() {
  state.notice = state.notice || '';
  sceneRoot.innerHTML = currentRender().replace(
    'NOTICE_THETA29',
    `已把光路设为 ${tex('\\theta = 29^\\circ')}（接近边界且能保持全反射的可行方向），本场景在这条冻结光路上拆步长。`,
  );
  renderTex(sceneRoot);
  bindEvents();
  document.querySelectorAll('[data-scene-tab]').forEach((btn) => {
    btn.setAttribute('aria-selected', btn.dataset.sceneTab === state.scene ? 'true' : 'false');
  });
  state.notice = '';
}

function showScene(name) {
  state.previousScene = state.scene;
  state.scene = name;
  if (name === 's1' && !state.visited.s1) {
    state.finderStep = 'angles'; // 直接进入默认从角度识别步骤开始
    applyThetaPreset(20); // 直接进入默认 θ=20°
  }
  if (name === 's3') {
    // 每次进入都明确切换到可行预设 θ=29° 并提示
    applyThetaPreset(29);
    state.selectedK = 1;
    state.notice = 'NOTICE_THETA29';
  }
  state.visited[name] = true;
  clearHighlight(); // 切换场景立即清除高亮与定时器
  render();
}

function bindEvents() {
  // 预测与选择
  sceneRoot.querySelectorAll('input[name="p0"]').forEach((el) => {
    el.addEventListener('change', () => { state.prediction0 = el.value; });
  });
  sceneRoot.querySelectorAll('input[name="p2"]').forEach((el) => {
    el.addEventListener('change', () => { state.prediction2 = el.value; });
  });
  sceneRoot.querySelectorAll('input[name="c6"]').forEach((el) => {
    el.addEventListener('change', () => { state.choice6 = el.value; render(); });
  });
  sceneRoot.querySelectorAll('input[name="c7"]').forEach((el) => {
    el.addEventListener('change', () => { state.choice7 = el.value; render(); });
  });
  const reasonInput = sceneRoot.querySelector('[data-reason]');
  if (reasonInput) {
    reasonInput.addEventListener('input', () => { state.reason4 = reasonInput.value; });
  }

  // 关键值核对（场景 1 静态核对步骤，连续探索跨越临界后由学习者展开）
  sceneRoot.querySelectorAll('[data-preset]').forEach((btn) => {
    btn.addEventListener('click', () => {
      setThetaContinuous(Number(btn.dataset.preset));
    });
  });
  const presetGate = sceneRoot.querySelector('[data-preset-gate]');
  if (presetGate) {
    presetGate.addEventListener('click', () => {
      state.showKeyCheck = true;
      render();
    });
  }

  // 「找边界」场内步骤：可直接选择；进入连续探索总是重置为 θ=0°，
  // 重复激活当前步骤不重复制造状态
  sceneRoot.querySelectorAll('[data-finder-step]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const next = btn.dataset.finderStep;
      if (next === state.finderStep) return;
      state.finderStep = next;
      if (next === 'explore') {
        applyThetaPreset(0); // 连续探索从水平直行开始
      }
      clearHighlight();
      render();
    });
  });

  // 连续滑条（场景 1）：显式 pointer 拖动 + 原生 input 双通道
  const slider = sceneRoot.querySelector('[data-theta-slider]');
  if (slider) bindThetaSlider(slider);

  // 视图切换与反射点选择（场景 3）
  sceneRoot.querySelectorAll('[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.unfold = btn.dataset.view === 'unfolded';
      render();
    });
  });
  sceneRoot.querySelectorAll('[data-select-k]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.selectedK = Number(btn.dataset.selectK);
      render();
    });
  });
  const kInput = sceneRoot.querySelector('[data-select-k-input]');
  if (kInput) {
    kInput.addEventListener('change', () => {
      const k = Math.round(Number(kInput.value));
      if (Number.isInteger(k) && k >= 1 && k <= Math.max(1, model.count)) {
        state.selectedK = k;
        render();
      }
    });
  }

  // 展开检查（场景 4）
  sceneRoot.querySelectorAll('[data-reveal-btn]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.dataset.revealBtn === '6') state.show6 = true;
      if (btn.dataset.revealBtn === '7') state.show7 = true;
      render();
    });
  });

  // 审计返回
  const back = sceneRoot.querySelector('[data-audit-back]');
  if (back) {
    back.addEventListener('click', () => {
      state.scene = state.previousScene === 'audit' ? 's0' : state.previousScene;
      render();
    });
  }

  // 图式绑定：点击/触控/键盘激活公式符号 → 对应角弧高亮 2 秒后自动清除；
  // 单纯聚焦只显示 focus outline，不触发图式高亮。
  sceneRoot.querySelectorAll('[data-hl]').forEach((el) => {
    el.addEventListener('click', () => setHighlight(el.dataset.hl));
  });

  // 文本引用 → 公式定位高亮
  sceneRoot.querySelectorAll('[data-formula-ref]').forEach((el) => {
    el.addEventListener('click', () => {
      const target = sceneRoot.querySelector(`#formula-${el.dataset.formulaRef}`);
      if (target) {
        target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        target.classList.add('flash');
        window.setTimeout(() => target.classList.remove('flash'), 1600);
      }
    });
  });

  // 图中入射光把手（场景 1）：指针拖动 + 键盘，与滑条双向同步
  const stage = sceneRoot.querySelector('[data-stage]');
  if (stage && stage.querySelector('[data-handle]')) {
    bindHandle(stage);
  }
}

// 页签与审计入口
document.querySelectorAll('[data-scene-tab]').forEach((btn) => {
  btn.addEventListener('click', () => showScene(btn.dataset.sceneTab));
});
document.getElementById('audit-entry').addEventListener('click', () => {
  state.previousScene = state.scene;
  state.scene = 'audit';
  clearHighlight();
  render();
});

render();
