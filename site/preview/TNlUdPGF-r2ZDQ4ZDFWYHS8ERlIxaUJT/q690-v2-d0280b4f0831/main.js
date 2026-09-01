'use strict';

/* ============================================================
 * 竖直弹跳笔：碰撞与能量 —— 课堂候选脚本
 * 所有单元的模型、事件说明、速度箭头与能量表示由同一物理状态驱动。
 * 模型用 SVG 矢量绘制，无 Canvas 分辨率问题；h2 > h1。
 * ============================================================ */

/* 模型常量（像素即示意坐标，非按比例） */
const P = {
  W: 420, H: 540, TABLE: 480, CX: 185,
  SHELL_W: 66, SHELL_H: 210,
  CORE_W: 16, CORE_H: 180,
  H1: 140, H2: 250
};

/* 内联 MathML 片段（事件说明中使用） */
const M_H1 = '<math><msub><mi>h</mi><mn>1</mn></msub></math>';
const M_H2 = '<math><msub><mi>h</mi><mn>2</mn></msub></math>';
const M_H21 = '<math><msub><mi>h</mi><mn>2</mn></msub><mo>−</mo><msub><mi>h</mi><mn>1</mn></msub></math>';
const M_V = '<math><mi>v</mi></math>';
const M_V1 = '<math><msub><mi>v</mi><mn>1</mn></msub></math>';

/* ---------- 弹簧折线 ---------- */
function springPath(x, y0, y1) {
  const len = Math.max(y1 - y0, 4);
  const coils = Math.max(2, Math.round(len / 22));
  const amp = len < 26 ? 9 : 13;
  const steps = coils * 2;
  let d = `M ${x} ${y0.toFixed(1)}`;
  for (let i = 1; i < steps; i++) {
    const y = y0 + len * i / steps;
    const xx = x + (i % 2 === 1 ? amp : -amp);
    d += ` L ${xx.toFixed(1)} ${y.toFixed(1)}`;
  }
  d += ` L ${x} ${y1.toFixed(1)}`;
  return d;
}

/* ---------- 钢笔模型绘制 ----------
 * st = {
 *   s        外壳下端距桌面高度（示意像素）
 *   joined   碰撞后内芯随外壳一起运动
 *   speed    归一化速度（1.0 = v1，碰后共同速度 v = 0.8）；arrowConst 时只作动/不动开关
 *   arrow    {base, sub?} 速度箭头标注；speed 过小时不画箭头
 *   arrowConst 箭头固定长度，不编码速度大小（用于未给定速度历程的过程）
 *   flash    碰撞闪光
 *   still    标注“静止”
 *   markers  {h1, h2, seg} 高度标记
 *   note     “示意图，非按比例”
 *   viewBox  自定义取景
 * } */
function penMarkup(st) {
  const T = P.TABLE, CX = P.CX;
  const shellX = CX - 33;
  const shellY = T - st.s - P.SHELL_H;
  const coreBottom = st.joined ? T - (st.s - P.H1) : T;
  const coreTop = coreBottom - P.CORE_H;
  const springTop = shellY + 3;
  const springBot = coreTop;
  const yH1 = T - P.H1;
  const yH2 = T - P.H2;
  const parts = [];

  /* 桌面 */
  parts.push(`<line x1="16" y1="${T}" x2="404" y2="${T}" stroke="#4a5568" stroke-width="3"/>`);
  let hatch = '';
  for (let x = 32; x <= 392; x += 24) {
    hatch += `<line x1="${x}" y1="${T + 4}" x2="${x - 10}" y2="${T + 16}" stroke="#a0aec0" stroke-width="1.5"/>`;
  }
  parts.push(hatch);
  parts.push(`<text x="404" y="${T + 30}" text-anchor="end" font-size="12" fill="#718096">桌面</text>`);

  /* 高度标记 */
  const mk = st.markers || {};
  if (mk.h1) {
    parts.push(`<line x1="222" y1="${yH1}" x2="330" y2="${yH1}" stroke="#4a5568" stroke-width="1.5" stroke-dasharray="5 4"/>`);
    parts.push(`<line x1="344" y1="${T}" x2="344" y2="${yH1}" stroke="#2d3748" stroke-width="1.5"/>`);
    parts.push(`<line x1="338" y1="${T}" x2="350" y2="${T}" stroke="#2d3748" stroke-width="1.5"/>`);
    parts.push(`<line x1="338" y1="${yH1}" x2="350" y2="${yH1}" stroke="#2d3748" stroke-width="1.5"/>`);
    parts.push(`<text x="356" y="${(T + yH1) / 2 + 5}" font-size="14" fill="#2d3748">h<tspan baseline-shift="sub" font-size="10">1</tspan></text>`);
  }
  if (mk.h2) {
    parts.push(`<line x1="222" y1="${yH2}" x2="344" y2="${yH2}" stroke="#4a5568" stroke-width="1.5" stroke-dasharray="5 4"/>`);
  }
  if (mk.seg) {
    parts.push(`<line x1="344" y1="${yH1}" x2="344" y2="${yH2}" stroke="#b7791f" stroke-width="1.5"/>`);
    parts.push(`<line x1="338" y1="${yH2}" x2="350" y2="${yH2}" stroke="#b7791f" stroke-width="1.5"/>`);
    parts.push(`<text x="356" y="${(yH1 + yH2) / 2 + 5}" font-size="14" fill="#b7791f">h<tspan baseline-shift="sub" font-size="10">2</tspan> − h<tspan baseline-shift="sub" font-size="10">1</tspan></text>`);
  }

  /* 外壳（上端封闭、下端开口的薄壁筒） */
  parts.push(`<rect x="${shellX}" y="${shellY}" width="${P.SHELL_W}" height="${P.SHELL_H}" fill="rgba(43,108,176,0.10)"/>`);
  parts.push(`<path d="M ${shellX} ${shellY + P.SHELL_H} L ${shellX} ${shellY + 8} Q ${shellX} ${shellY} ${shellX + 8} ${shellY} L ${shellX + P.SHELL_W - 8} ${shellY} Q ${shellX + P.SHELL_W} ${shellY} ${shellX + P.SHELL_W} ${shellY + 8} L ${shellX + P.SHELL_W} ${shellY + P.SHELL_H}" fill="none" stroke="#2b6cb0" stroke-width="3"/>`);
  /* 外壳内壁凸起（碰撞时接住内芯凸缘） */
  const ledgeY = T - st.s - 40;
  parts.push(`<rect x="${shellX + 2}" y="${ledgeY}" width="12" height="8" fill="#2b6cb0" opacity="0.85"/>`);
  parts.push(`<rect x="${shellX + P.SHELL_W - 14}" y="${ledgeY}" width="12" height="8" fill="#2b6cb0" opacity="0.85"/>`);

  /* 弹簧 */
  parts.push(`<path d="${springPath(CX, springTop, springBot)}" fill="none" stroke="#4a5568" stroke-width="2"/>`);

  /* 内芯（杆 + 顶部凸缘） */
  parts.push(`<rect x="${CX - P.CORE_W / 2}" y="${coreTop}" width="${P.CORE_W}" height="${P.CORE_H}" fill="#dd6b20"/>`);
  parts.push(`<rect x="${CX - 15}" y="${coreTop}" width="30" height="10" rx="2" fill="#c05621"/>`);

  /* 质量标注 */
  const shellMid = T - st.s - P.SHELL_H / 2;
  parts.push(`<text x="${shellX - 10}" y="${shellMid + 5}" text-anchor="end" font-size="14" font-weight="600" fill="#2b6cb0">4m</text>`);
  parts.push(`<text x="224" y="${coreTop + 92}" font-size="14" font-weight="600" fill="#c05621">m</text>`);
  if (st.still && !st.joined) {
    parts.push(`<text x="224" y="${coreTop + 150}" font-size="12" fill="#a0aec0">静止</text>`);
  }

  /* 速度箭头（arrowConst 时只用固定长度表示“在运动”，不编码速度大小） */
  if (st.speed > 0.03 && st.arrow) {
    const ax = CX + 33 + 28;
    const len = st.arrowConst ? 56 : 26 + 62 * st.speed;
    const tipY = shellMid - len;
    parts.push(`<line x1="${ax}" y1="${shellMid}" x2="${ax}" y2="${tipY}" stroke="#c53030" stroke-width="3"/>`);
    parts.push(`<polygon points="${ax},${tipY - 2} ${ax - 6},${tipY + 12} ${ax + 6},${tipY + 12}" fill="#c53030"/>`);
    const sub = st.arrow.sub ? `<tspan baseline-shift="sub" font-size="10">${st.arrow.sub}</tspan>` : '';
    parts.push(`<text x="${ax}" y="${tipY - 10}" text-anchor="middle" font-size="14" font-weight="600" fill="#c53030">${st.arrow.base}${sub}</text>`);
  }

  /* 碰撞闪光 */
  if (st.flash) {
    const fx = CX, fy = T - P.H1 - 36;
    let rays = '';
    for (let k = 0; k < 8; k++) {
      const a = Math.PI / 4 * k;
      rays += `<line x1="${(fx + Math.cos(a) * 8).toFixed(1)}" y1="${(fy + Math.sin(a) * 8).toFixed(1)}" x2="${(fx + Math.cos(a) * 22).toFixed(1)}" y2="${(fy + Math.sin(a) * 22).toFixed(1)}" stroke="#dd6b20" stroke-width="3" stroke-linecap="round"/>`;
    }
    parts.push(rays);
    parts.push(`<text x="${CX - 66}" y="${fy + 5}" text-anchor="middle" font-size="16" font-weight="bold" fill="#c53030">碰撞</text>`);
  }

  if (st.note) {
    parts.push(`<text x="398" y="528" text-anchor="end" font-size="11" fill="#8a94a6">示意图，非按比例</text>`);
  }
  return parts.join('');
}

function renderPen(svg, st) {
  svg.setAttribute('viewBox', st.viewBox || '0 0 420 540');
  svg.innerHTML = penMarkup(st);
}

/* ---------- 播放器（播放/暂停/重放/定位；页面不可见时暂停） ---------- */
const players = [];
function makePlayer(duration, update) {
  let t = 0, playing = false, raf = 0, last = 0, onState = null;
  function frame(now) {
    if (!playing) return;
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    t += dt;
    if (t >= duration) {
      t = duration;
      playing = false;
      update(t);
      if (onState) onState(false);
      return;
    }
    update(t);
    raf = requestAnimationFrame(frame);
  }
  const api = {
    play() {
      if (playing) return;
      if (t >= duration) t = 0;
      playing = true;
      last = performance.now();
      raf = requestAnimationFrame(frame);
      if (onState) onState(true);
    },
    pause() {
      if (!playing) return;
      playing = false;
      cancelAnimationFrame(raf);
      if (onState) onState(false);
    },
    toggle() { if (playing) { api.pause(); } else { api.play(); } },
    replay() { api.pause(); t = 0; update(0); api.play(); },
    seek(x) { api.pause(); t = Math.max(0, Math.min(x, duration)); update(t); },
    setOnState(fn) { onState = fn; }
  };
  players.push(api);
  return api;
}

/* ============================================================
 * 单元一：完整三段过程
 * 时间线：0–2.4 弹簧推外壳上升（静止释放，不定量渐入，不暗示 v(t) 规律）；
 *        2.4–2.9 碰撞（v1 → v = 4v1/5，内芯并入）；
 *        2.9–5.7 共同匀减速上升至 h2，速度减为 0。
 * ============================================================ */
const svgU1 = document.getElementById('svgU1');
const capU1 = document.getElementById('capU1');
const u1PlayBtn = document.getElementById('u1Play');

function u1Update(t) {
  const st = { markers: { h1: true, h2: true, seg: true }, note: true };
  let cap;
  if (t < 2.4) {
    /* 第①段：原题未给弹簧劲度系数与压缩量，不能确定碰前逐时速度规律。
     * 上升用光滑渐入曲线（由静止释放、碰前仍在运动），
     * 速度箭头固定长度，只表示“向上运动”，不编码速度大小；v1 在碰撞瞬间标记。 */
    const u = t / 2.4;
    st.s = P.H1 * (1 - Math.cos(Math.PI * u / 2));
    st.speed = u === 0 ? 0 : 0.6;
    st.arrowConst = true;
    st.joined = false;
    st.still = true;
    st.arrow = { base: '外壳速度' };
    cap = `第①段：弹簧推动外壳上升，内芯静止在桌面上；碰前瞬间外壳速度为 ${M_V1}。`;
  } else if (t < 2.9) {
    st.s = P.H1;
    st.joined = t >= 2.55;
    st.flash = t < 2.72;
    st.speed = st.joined ? 0.8 : 1.0;
    st.arrow = st.joined ? { base: '共同速度 v' } : { base: 'v', sub: '1' };
    cap = `第②段：外壳下端到达 ${M_H1}，与静止的内芯碰撞；碰后总质量 5m，以共同速度 ${M_V} 上升。`;
  } else if (t < 5.7) {
    const u = (t - 2.9) / 2.8;
    st.s = P.H1 + (P.H2 - P.H1) * (1 - (1 - u) * (1 - u));
    st.speed = 0.8 * (1 - u);
    st.joined = true;
    st.arrow = { base: '共同速度 v' };
    cap = '第③段：外壳与内芯以共同速度一起上升，速度逐渐减小。';
  } else {
    st.s = P.H2;
    st.speed = 0;
    st.joined = true;
    st.arrow = null;
    cap = `外壳下端到达 ${M_H2}，共同速度刚好减为 0：碰后共同上升的距离是 ${M_H21}。`;
  }
  renderPen(svgU1, st);
  capU1.innerHTML = cap;
}

const u1 = makePlayer(5.7, u1Update);
u1.setOnState((playing) => { u1PlayBtn.textContent = playing ? '暂停' : '播放'; });
u1PlayBtn.addEventListener('click', () => u1.toggle());
document.getElementById('u1Replay').addEventListener('click', () => u1.replay());
document.querySelectorAll('#u1 [data-seek]').forEach((btn) => {
  btn.addEventListener('click', () => u1.seek(parseFloat(btn.dataset.seek)));
});

/* ============================================================
 * 单元二：碰撞瞬间（碰前/碰后对照 + 碰撞瞬间重放）
 * ============================================================ */
const svgU2 = document.getElementById('svgU2');
const capU2 = document.getElementById('capU2');

function u2ShowBefore() {
  renderPen(svgU2, {
    s: P.H1, joined: false, speed: 1.0, still: true,
    arrow: { base: 'v', sub: '1' },
    markers: { h1: true }, note: true
  });
  capU2.innerHTML = `碰前瞬间：外壳（4m）以 ${M_V1} 向上运动，内芯（m）静止。`;
}
function u2ShowAfter() {
  renderPen(svgU2, {
    s: P.H1 + 22, joined: true, speed: 0.8,
    arrow: { base: 'v' },
    markers: { h1: true }, note: true
  });
  capU2.innerHTML = `碰后瞬间：外壳与内芯总质量 5m，以共同速度 ${M_V} 一起向上。`;
}
function u2Update(t) {
  const st = { markers: { h1: true }, note: true };
  let cap;
  if (t < 0.9) {
    st.s = P.H1 - 50 + 50 * (t / 0.9);
    st.speed = 1;
    st.joined = false;
    st.still = true;
    st.arrow = { base: 'v', sub: '1' };
    cap = `碰前：外壳以 ${M_V1} 上升，内芯静止。`;
  } else if (t < 1.3) {
    st.s = P.H1;
    st.joined = t >= 1.05;
    st.flash = t < 1.18;
    st.speed = st.joined ? 0.8 : 1;
    st.arrow = st.joined ? { base: 'v' } : { base: 'v', sub: '1' };
    cap = '碰撞：撞击力远大于重力，碰撞时间极短。';
  } else {
    const u = Math.min((t - 1.3) / 0.9, 1);
    st.s = P.H1 + 30 * u;
    st.speed = 0.8 - 0.25 * u;
    st.joined = true;
    st.arrow = { base: 'v' };
    cap = `碰后：总质量 5m，以共同速度 ${M_V} 一起上升。`;
  }
  renderPen(svgU2, st);
  capU2.innerHTML = cap;
}
const u2p = makePlayer(2.2, u2Update);
document.getElementById('u2Before').addEventListener('click', () => { u2p.pause(); u2ShowBefore(); });
document.getElementById('u2After').addEventListener('click', () => { u2p.pause(); u2ShowAfter(); });
document.getElementById('u2ReplayBtn').addEventListener('click', () => u2p.replay());

/* ============================================================
 * 单元三：弹簧做功（外壳离开桌面 → 碰前）
 * 原题只给符号 h1、h2，未给弹簧劲度系数与压缩量：
 * 本单元不做定量能量份额，也不假定碰前逐时速度规律。
 * 上升用光滑的渐入曲线（从静止释放、碰前仍在运动），
 * 速度箭头只用固定长度表示“在运动”，碰前瞬间明确标记 v1；
 * 能量只做不定量的同步“计入账本”状态。
 * ============================================================ */
const svgU3 = document.getElementById('svgU3');
const capU3 = document.getElementById('capU3');
const u3PlayBtn = document.getElementById('u3Play');
const u3LedPE = document.getElementById('u3LedPE');
const u3LedKE = document.getElementById('u3LedKE');

function u3SetLedger(el, text, cls) {
  const chip = el.querySelector('.ledger-chip');
  chip.textContent = text;
  chip.className = 'ledger-chip ' + cls;
}

function u3Update(t) {
  const u = Math.min(t / 3.0, 1);
  const s = P.H1 * (1 - Math.cos(Math.PI * u / 2));
  renderPen(svgU3, {
    s: s,
    joined: false,
    speed: u === 0 ? 0 : 0.6,
    arrowConst: true,
    still: true,
    arrow: u >= 1 ? { base: 'v', sub: '1' } : { base: '外壳速度' },
    markers: { h1: true },
    note: true
  });
  if (u === 0) {
    u3SetLedger(u3LedPE, '未开始', 'idle');
    u3SetLedger(u3LedKE, '未开始', 'idle');
  } else if (u < 1) {
    u3SetLedger(u3LedPE, '随过程计入', 'on');
    u3SetLedger(u3LedKE, '随过程计入', 'on');
  } else {
    u3SetLedger(u3LedPE, '碰前已全部计入', 'done');
    u3SetLedger(u3LedKE, '碰前已全部计入', 'done');
  }
  capU3.innerHTML = u < 1
    ? '外壳上升中：弹簧形变减小并对外壳做功，外壳变高、向上运动；内芯静止。'
    : `碰前瞬间：外壳高度 ${M_H1}、速度 ${M_V1}；弹簧做的功已全部变成外壳的重力势能与动能。`;
}
const u3 = makePlayer(3.0, u3Update);
u3.setOnState((playing) => { u3PlayBtn.textContent = playing ? '暂停' : '播放'; });
u3PlayBtn.addEventListener('click', () => u3.toggle());
document.getElementById('u3Replay').addEventListener('click', () => u3.replay());

/* ============================================================
 * 单元四：碰撞能量损失（静态对照模型 + 动量/动能对比条）
 * ============================================================ */
const svgU4a = document.getElementById('svgU4a');
const svgU4b = document.getElementById('svgU4b');
function u4Render() {
  renderPen(svgU4a, {
    s: P.H1, joined: false, speed: 1.0, still: true,
    arrow: { base: 'v', sub: '1' },
    markers: { h1: true },
    viewBox: '95 90 305 420'
  });
  renderPen(svgU4b, {
    s: P.H1 + 22, joined: true, speed: 0.8,
    arrow: { base: 'v' },
    markers: {},
    viewBox: '95 90 305 420'
  });
}

/* ---------- 页签切换（切换时暂停其他单元的动画） ---------- */
function activateUnit(id) {
  players.forEach((p) => p.pause());
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.unit === id);
  });
  document.querySelectorAll('.unit').forEach((sec) => {
    sec.classList.toggle('active', sec.id === id);
  });
}
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => activateUnit(tab.dataset.unit));
});

/* ---------- 揭示切换 ---------- */
document.querySelectorAll('[data-reveal]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const box = document.getElementById(btn.dataset.reveal);
    const show = box.hidden;
    box.hidden = !show;
    btn.textContent = show ? '收起公式与结果' : '显示公式与结果';
  });
});

/* ---------- 完整原题弹窗（不改变教学状态） ---------- */
const modal = document.getElementById('problemModal');
document.getElementById('btnProblem').addEventListener('click', () => { modal.hidden = false; });
document.getElementById('btnCloseModal').addEventListener('click', () => { modal.hidden = true; });
modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) modal.hidden = true; });

/* ---------- 页面不可见时暂停所有动画 ---------- */
document.addEventListener('visibilitychange', () => {
  if (document.hidden) players.forEach((p) => p.pause());
});

/* ---------- 初始化（不自动播放） ---------- */
u1Update(0);
u2ShowBefore();
u3Update(0);
u4Render();
if (['u1', 'u2', 'u3', 'u4'].includes(location.hash.slice(1))) {
  activateUnit(location.hash.slice(1));
}
