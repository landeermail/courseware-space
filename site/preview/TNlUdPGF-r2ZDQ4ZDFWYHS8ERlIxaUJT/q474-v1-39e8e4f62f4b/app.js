/* 474 纵波：弹簧上的标记点 —— 纯原生 JS，无依赖。
 * 内部模型（不在前台显示任何符号与数值）：
 *   自然位置 X_n = -5 + 5n cm（n=0..12）；题图位移 6cos(nπ/4) cm；
 *   右行行波与 u(X,t)=6cos(πX/20−ωt+π/4) 同向；题图状态即其 t=0。
 *   启动包络：波前 X_f 以与波形相同的速度向右推进，未到区域位移严格为 0。
 *   归一化进程 τ∈[0,16]：θ=2πτ/8，X_f=-6+5τ；τ=16 时 θ=4π 且波前已过右端，
 *   精确等于题图状态（λ=40 cm，A=6 cm，点序不反转）。
 * 公式渲染：window.katex 存在时用 LaTeX 源码渲染；失败保留可读文本，不抛错。
 */
'use strict';
(function () {
  var N = 13;
  var A = 6;
  var TWO_PI = Math.PI * 2;
  var TAU_MAX = 16;          // 归一化进程上限；τ=16 精确为题图状态
  var RATE = TAU_MAX / 24;   // 默认 24 墙钟秒走完全程（不标注任何时间）
  var FRONT_W = 12;          // 波前包络过渡宽度（cm，仅内部）
  var PITCH = 1.8;           // 螺旋螺距（仅外观）

  function Xeq(n) { return -5 + 5 * n; }
  // 归一化进程 τ 下的轴向位移（cm）；波前未到区域严格为 0
  function disp(X, tau) {
    var theta = TWO_PI * tau / 8;
    var z = (-6 + 5 * tau - X) / FRONT_W;
    if (z <= 0) { return 0; }
    if (z > 1) { z = 1; }
    var e = z * z * (3 - 2 * z);
    return A * e * Math.cos(Math.PI * X / 20 - theta + Math.PI / 4);
  }

  var state = {
    step: 1,
    tau: 0,
    playing: false,
    s3: { mode: 'live', tau0: 0, t0: 0, alignT: 0, lambda: false, amp: 'off', ampAnim: null, ampT: 0 }
  };

  // ---------- 看振幅：A0–A5 来源链文案（Canvas 标注与公式同步推进） ----------
  var AMP_HTML = [
    '<p>这两个位置的疏密状态相同，两个标记点此刻移动得也相同，所以它们现在相差 40 cm，' +
    '自然伸展时也相差 40 cm。中间共有 8 个原本相等的标记间隔。</p>',
    '<p class="tex tex-d" data-tex="d = \\frac{40\\ \\text{cm}}{8} = 5\\ \\text{cm}">d = 40 cm ÷ 8 = 5 cm</p>',
    '<p>此刻在 9 cm 和 41 cm 的两个点，中间隔着 4 个标记间隔。</p>' +
    '<p class="tex tex-d" data-tex="4d = 4\\times 5\\ \\text{cm} = 20\\ \\text{cm}">4d = 4 × 5 cm = 20 cm</p>',
    '<p class="tex tex-d" data-tex="\\frac{9+41}{2} = 25\\ \\text{cm}">(9 + 41) ÷ 2 = 25 cm</p>' +
    '<p>两个点的共同中点在 25 cm。</p>',
    '<p>从中点向左右各退 10 cm，就是它们自然伸展时的位置。</p>' +
    '<p class="tex tex-d" data-tex="25 - 10 = 15\\ \\text{cm}">25 − 10 = 15 cm</p>' +
    '<p class="tex tex-d" data-tex="25 + 10 = 35\\ \\text{cm}">25 + 10 = 35 cm</p>',
    '<p>左边的点向左 6 cm，右边的点向右 6 cm，两端各是一个 A。</p>' +
    '<p class="tex tex-d" data-tex="15 - 9 = 6\\ \\text{cm}">15 − 9 = 6 cm</p>' +
    '<p class="tex tex-d" data-tex="41 - 35 = 6\\ \\text{cm}">41 − 35 = 6 cm</p>' +
    '<p class="tex tex-d" data-tex="A = 6\\ \\text{cm}">A = 6 cm</p>'
  ];

  // ---------- LaTeX 渲染（带降级） ----------
  function renderTex(root) {
    if (!window.katex) { return; }
    var list = (root || document).querySelectorAll('.tex');
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el.dataset.done) { continue; }
      try {
        window.katex.render(el.dataset.tex || '', el, {
          throwOnError: false,
          displayMode: el.classList.contains('tex-d')
        });
        el.dataset.done = '1';
      } catch (e) { /* 保留原文本 */ }
    }
  }
  window.addEventListener('load', function () { renderTex(document); });

  // ---------- DOM ----------
  function $(id) { return document.getElementById(id); }
  var navBtns = document.querySelectorAll('.steps-nav button');
  var sections = document.querySelectorAll('.step');
  var prevBtn = $('prevBtn'), nextBtn = $('nextBtn');
  var playBtn = $('playBtn'), replayBtn = $('replayBtn'), progSlider = $('progSlider');
  var s3intro = $('s3intro'), snapBtn = $('snapBtn');
  var lambdaBtn = $('lambdaBtn'), ampBtn = $('ampBtn'), ampNextBtn = $('ampNextBtn'), againBtn = $('againBtn');
  var lambdaReveal = $('lambdaReveal'), ampReveal = $('ampReveal');

  // ---------- 画布 ----------
  var HEIGHTS = { springCanvas: 340, stageCanvas: 540 };
  var STEP_CANVASES = { 1: [], 2: ['springCanvas'], 3: ['stageCanvas'] };
  var ctxs = {}, widths = {};

  function fit(id) {
    var canvas = $(id);
    var w = canvas.clientWidth;
    if (!w) { return 0; }
    var ctx = null;
    try { ctx = canvas.getContext('2d'); } catch (e) { ctx = null; }
    if (!ctx) {
      canvas.style.display = 'none';
      if (!canvas.dataset.fbk) {
        canvas.dataset.fbk = '1';
        var d = document.createElement('p');
        d.className = 'caption';
        d.textContent = '当前环境不支持画布。文字说明：驱动杆来回推拉弹簧左端，密的地方从左端出现向右传；' +
          '红点只在原地附近左右动。停在题图那一刻后，红点落到 0–50 cm 刻度图上，' +
          '最靠右两点相差 40 cm（波长）；自然相距 20 cm 的两点此时相距 32 cm，多出两个振幅，A = 6 cm。';
        canvas.parentNode.insertBefore(d, canvas.nextSibling);
      }
      return 0;
    }
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(HEIGHTS[id] * dpr);
    canvas.style.height = HEIGHTS[id] + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctxs[id] = ctx;
    widths[id] = w;
    return w;
  }

  // ---------- 坐标映射（弹簧与刻度图共用，上下严格对齐） ----------
  var HM = { x0: -6, x1: 56, pad: 36 };
  function hmx(w, x) { return HM.pad + (x - HM.x0) / (HM.x1 - HM.x0) * (w - 2 * HM.pad); }

  // ---------- 小绘图工具 ----------
  function circle(ctx, x, y, r, fill, stroke, lw, dash) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, TWO_PI);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lw || 1.5;
      if (dash) { ctx.setLineDash(dash); }
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
  function line(ctx, x1, y1, x2, y2, color, lw, dash) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = color;
    ctx.lineWidth = lw || 1;
    if (dash) { ctx.setLineDash(dash); }
    ctx.stroke();
    ctx.setLineDash([]);
  }
  function arrow(ctx, x1, x2, y, color) {
    line(ctx, x1, y, x2, y, color, 2);
    var dir = x2 >= x1 ? 1 : -1;
    ctx.beginPath();
    ctx.moveTo(x2, y);
    ctx.lineTo(x2 - dir * 6, y - 4);
    ctx.lineTo(x2 - dir * 6, y + 4);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }
  function text(ctx, s, x, y, size, color, align, bold) {
    ctx.fillStyle = color;
    ctx.font = (bold ? '600 ' : '') + size + 'px "PingFang SC","Microsoft YaHei",sans-serif';
    ctx.textAlign = align || 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(s, x, y);
  }
  function ease(t) { return t * t * (3 - 2 * t); }
  function bracket(ctx, xa, xb, y, color, label, labelUp) {
    line(ctx, xa, y, xb, y, color, 2);
    line(ctx, xa, y - 5, xa, y + 5, color, 2);
    line(ctx, xb, y - 5, xb, y + 5, color, 2);
    text(ctx, label, (xa + xb) / 2, y + (labelUp ? -11 : 11), 11.5, color, 'center', true);
  }

  // ---------- 弹簧（固定侧前方正投影螺旋） ----------
  // 返回红点圆心纵坐标 cy
  function drawSpring(ctx, w, cy, Ry, tau, drawDots) {
    var tilt = 6;
    var pts = [];
    for (var X = HM.x0; X <= HM.x1; X += 0.12) {
      var th = TWO_PI * X / PITCH;
      pts.push({
        x: hmx(w, X + disp(X, tau)),
        y: cy + Ry * Math.sin(th) - tilt * Math.cos(th),
        z: Math.cos(th)
      });
    }
    for (var pass = 0; pass < 2; pass++) {
      var back = (pass === 0);
      ctx.strokeStyle = back ? '#b6c2d9' : '#3f5a8a';
      ctx.lineWidth = back ? 1.5 : 2;
      ctx.beginPath();
      for (var i = 0; i < pts.length - 1; i++) {
        var isBack = (pts[i].z + pts[i + 1].z) / 2 < 0;
        if (isBack === back) {
          ctx.moveTo(pts[i].x, pts[i].y);
          ctx.lineTo(pts[i + 1].x, pts[i + 1].y);
        }
      }
      ctx.stroke();
    }
    // 左端驱动杆（只画往复杆，不画内部机构）
    var bx = hmx(w, HM.x0 + disp(HM.x0, tau));
    ctx.fillStyle = '#78909c';
    ctx.fillRect(bx - 13, cy - Ry - 8, 12, 2 * Ry + 16);
    line(ctx, 4, cy, bx - 13, cy, '#78909c', 5);
    text(ctx, '驱动杆', bx - 7, cy - Ry - 18, 11, '#546e7a', 'center', true);
    // 13 个红色标记点（固定在弹簧材料上）
    if (drawDots) {
      for (var n = 0; n < N; n++) {
        circle(ctx, hmx(w, Xeq(n) + disp(Xeq(n), tau)), cy, 6, '#d32f2f', '#fff', 1.5);
      }
    }
  }

  // ---------- 第 2 段 ----------
  function drawStep2() {
    var ctx = ctxs.springCanvas, w = widths.springCanvas;
    if (!ctx) { return; }
    ctx.clearRect(0, 0, w, HEIGHTS.springCanvas);
    drawSpring(ctx, w, 175, 95, state.tau, true);
  }

  // ---------- 第 3 段 ----------
  var C = { helixCy: 125, helixRy: 68, dotY: 400, axisY: 455, chartTop: 332, chartBot: 470 };

  function drawStage() {
    var ctx = ctxs.stageCanvas, w = widths.stageCanvas;
    if (!ctx) { return; }
    ctx.clearRect(0, 0, w, HEIGHTS.stageCanvas);
    var s = state.s3;
    var tau = state.tau;
    var landed = (s.mode === 'done');

    // 弹簧（对齐期间红点正在离开弹簧，故只有 live/toSnap 时画在弹簧上）
    drawSpring(ctx, w, C.helixCy, C.helixRy, tau, s.mode === 'live' || s.mode === 'toSnap');

    // 刻度图框架
    ctx.fillStyle = '#fdf6e3';
    ctx.fillRect(hmx(w, 0), C.chartTop, hmx(w, 50) - hmx(w, 0), C.chartBot - C.chartTop);
    for (var v = 0; v <= 50; v += 5) {
      line(ctx, hmx(w, v), C.chartTop, hmx(w, v), C.axisY, v % 10 === 0 ? '#d8d8d8' : '#ececec', 1);
    }
    line(ctx, hmx(w, 0) - 10, C.axisY, hmx(w, 50) + 16, C.axisY, '#555', 1.2);
    text(ctx, 'x/cm', hmx(w, 50) + 16, C.axisY - 10, 11, '#555', 'end');
    if (s.amp === 'off') {          // 振幅链期间隐藏刻度数字，读数只由当步标注给出
      for (v = 0; v <= 50; v += 10) {
        text(ctx, String(v), hmx(w, v), C.axisY + 13, 12, '#222', 'center', true);
      }
    }
    if (!landed && s.mode !== 'align') {
      text(ctx, '红点将落到这条刻度图上', (hmx(w, 0) + hmx(w, 50)) / 2, C.chartTop + 12, 11, '#8d6e63');
    }

    // 红点位置：对齐动画期间逐点下落，已落下后在刻度图上
    var dotX = [], dotY = [];
    for (var n = 0; n < N; n++) {
      dotX.push(hmx(w, Xeq(n) + disp(Xeq(n), tau)));
      var y = C.helixCy;
      if (s.mode === 'align') {
        var p = Math.min(Math.max((s.alignT - n * 0.05) / 0.7, 0), 1);
        y = C.helixCy + (C.dotY - C.helixCy) * ease(p);
      } else if (landed) {
        y = C.dotY;
      }
      dotY.push(y);
    }

    // 落下后：弹簧与刻度图之间的对齐虚线
    if (landed) {
      for (n = 0; n < N; n++) {
        line(ctx, dotX[n], C.helixCy + C.helixRy + 10, dotX[n], C.dotY - 10, '#d7ccc8', 1, [3, 4]);
      }
    }

    // 看振幅 A5：两个关键点从自然位置 15/35 移向题图位置 9/41
    if (s.amp === 5) {
      var q = (s.ampAnim === 'move') ? ease(Math.min(s.ampT / 1.4, 1)) : 1;
      dotX[4] = hmx(w, 15) + (hmx(w, 9) - hmx(w, 15)) * q;
      dotX[8] = hmx(w, 35) + (hmx(w, 41) - hmx(w, 35)) * q;
    }

    // 画红点（对齐中/已落下/振幅演示）
    if (s.mode === 'align' || landed) {
      for (n = 0; n < N; n++) {
        circle(ctx, dotX[n], dotY[n], 6, '#d32f2f', '#fff', 1.5);
      }
    }

    // 看振幅：A0–A5 来源链标注
    drawAmpChain(ctx, w, dotX);

    // 看波长：一个完整重复区间（最靠右的两点 n=0 与 n=8）
    if (s.lambda && landed) {
      var x0 = hmx(w, 1), x8 = hmx(w, 41);
      circle(ctx, dotX[0], C.dotY, 10, null, '#0d47a1', 2.5);
      circle(ctx, dotX[8], C.dotY, 10, null, '#0d47a1', 2.5);
      bracket(ctx, x0, x8, C.dotY - 48, '#0d47a1', '相差 40 cm', true);
      text(ctx, '起点 1 cm', x0 + 34, C.dotY - 34, 10.5, '#0d47a1', 'center', true);
      text(ctx, '终点 41 cm', x8 - 34, C.dotY - 34, 10.5, '#0d47a1', 'center', true);
    }
  }

  // ---------- 看振幅：A0–A5 来源链画布标注（每步只画当前任务） ----------
  var GAP_LABELS = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'];
  // 关键点：题图 9 cm（n=4）与 41 cm（n=8），每步都同一副标记
  function drawKeyDots(ctx, dotX, labelY) {
    circle(ctx, dotX[4], C.dotY, 12, null, '#c62828', 3);
    circle(ctx, dotX[8], C.dotY, 12, null, '#c62828', 3);
    text(ctx, '9 cm', dotX[4], labelY, 10.5, '#c62828', 'center', true);
    text(ctx, '41 cm', dotX[8], labelY, 10.5, '#c62828', 'center', true);
  }
  // 底部计数带：固定区域等距摆放编号，只数数量，不是当前点距测量尺
  function drawCountBand(ctx, w, count, title, note) {
    var xa = hmx(w, 3), xb = hmx(w, 47);
    text(ctx, title, xa, 482, 11.5, '#37474f', 'left', true);
    for (var i = 0; i < count; i++) {
      var cx = xa + (xb - xa) * (count === 1 ? 0.5 : i / (count - 1));
      circle(ctx, cx, 508, 11, null, '#0d47a1', 1.5);
      text(ctx, GAP_LABELS[i], cx, 508, 12, '#0d47a1', 'center', true);
    }
    if (note) { text(ctx, note, (xa + xb) / 2, 530, 11, '#37474f', 'center', true); }
  }
  function drawAmpChain(ctx, w, dotX) {
    var s = state.s3, st = s.amp;
    if (st === 'off') { return; }
    var i;

    if (st === 0 || st === 1) {
      // A0/A1：九个题图红点（n=0..8）、端点 1/41、相差 40；间隔数量走底部计数带
      for (i = 0; i <= 8; i++) { circle(ctx, dotX[i], C.dotY, 10, null, '#0d47a1', 2.5); }
      bracket(ctx, dotX[0], dotX[8], C.dotY - 48, '#0d47a1', '相差 40 cm', true);
      text(ctx, '起点 1 cm', dotX[0] + 36, C.dotY - 34, 10.5, '#0d47a1', 'center', true);
      text(ctx, '终点 41 cm', dotX[8] - 36, C.dotY - 34, 10.5, '#0d47a1', 'center', true);
      drawCountBand(ctx, w, 8, '只数数量：8 个原本相等的标记间隔',
                    st === 1 ? '每个自然间隔 d = 5 cm' : null);
    } else if (st === 2) {
      // A2：只有 9/41 两个关键点 + 4 个间隔的计数
      drawKeyDots(ctx, dotX, C.dotY - 16);
      bracket(ctx, dotX[4], dotX[8], C.dotY + 26, '#c62828', '相隔 4 个标记间隔', false);
      for (i = 0; i < 4; i++) {
        var cx = dotX[4] + (dotX[8] - dotX[4]) * (i + 0.5) / 4;
        circle(ctx, cx, C.dotY + 78, 10, null, '#c62828', 1.5);
        text(ctx, GAP_LABELS[i], cx, C.dotY + 78, 11, '#c62828', 'center', true);
      }
    } else if (st === 3) {
      // A3：只有两个关键点和中点 25 竖线，中点标签独占一行
      drawKeyDots(ctx, dotX, C.dotY - 16);
      line(ctx, hmx(w, 25), C.chartTop, hmx(w, 25), C.axisY, '#00695c', 1.5, [5, 4]);
      text(ctx, '中点 25 cm', hmx(w, 25), C.chartTop + 12, 11, '#00695c', 'center', true);
    } else if (st === 4) {
      // A4：关键点 + 中点 25 + 向左右各展开 10 的动画；完成后出现灰色自然位置 15/35
      drawKeyDots(ctx, dotX, C.dotY + 22);
      line(ctx, hmx(w, 25), C.chartTop, hmx(w, 25), C.axisY, '#00695c', 1.5, [5, 4]);
      text(ctx, '中点 25 cm', hmx(w, 25), C.chartTop + 12, 11, '#00695c', 'center', true);
      var p = (s.ampAnim === 'grow') ? ease(Math.min(s.ampT / 1.0, 1)) : 1;
      var xMid = hmx(w, 25);
      var xL = xMid + (hmx(w, 15) - xMid) * p;
      var xR = xMid + (hmx(w, 35) - xMid) * p;
      if (p > 0.02) {
        arrow(ctx, xMid, xL, C.dotY - 20, '#666');
        arrow(ctx, xMid, xR, C.dotY - 20, '#666');
        text(ctx, '10 cm', (xMid + xL) / 2, C.dotY - 34, 10.5, '#666', 'center', true);
        text(ctx, '10 cm', (xMid + xR) / 2, C.dotY - 34, 10.5, '#666', 'center', true);
      }
      if (!s.ampAnim) {
        circle(ctx, hmx(w, 15), C.dotY, 8, null, '#777', 2, [4, 3]);
        circle(ctx, hmx(w, 35), C.dotY, 8, null, '#777', 2, [4, 3]);
        text(ctx, '自然位置 15', hmx(w, 15), C.dotY + 40, 10, '#666');
        text(ctx, '自然位置 35', hmx(w, 35), C.dotY + 40, 10, '#666');
      }
    } else if (st === 5) {
      // A5：只有灰色自然位置 15/35、题图位置 9/41、两条 6 cm 方向箭头
      circle(ctx, hmx(w, 15), C.dotY, 8, null, '#777', 2, [4, 3]);
      circle(ctx, hmx(w, 35), C.dotY, 8, null, '#777', 2, [4, 3]);
      text(ctx, '自然位置 15', hmx(w, 15), C.dotY + 40, 10, '#666');
      text(ctx, '自然位置 35', hmx(w, 35), C.dotY + 40, 10, '#666');
      drawKeyDots(ctx, dotX, C.dotY + 22);
      if (!s.ampAnim) {
        arrow(ctx, hmx(w, 15), hmx(w, 9), C.dotY - 20, '#c62828');
        text(ctx, '向左 6 cm', (hmx(w, 15) + hmx(w, 9)) / 2, C.dotY - 34, 11, '#c62828', 'center', true);
        arrow(ctx, hmx(w, 35), hmx(w, 41), C.dotY - 20, '#1565c0');
        text(ctx, '向右 6 cm', (hmx(w, 35) + hmx(w, 41)) / 2, C.dotY - 34, 11, '#1565c0', 'center', true);
      }
    }
  }

  // ---------- 渲染调度 ----------
  function render() {
    if (state.step === 2) { drawStep2(); }
    else if (state.step === 3) { drawStage(); }
  }

  var rafId = null, lastTs = 0;
  function needsLoop() {
    if (state.playing) { return true; }
    var s = state.s3;
    return state.step === 3 && (s.mode === 'toSnap' || s.mode === 'align' || !!s.ampAnim);
  }
  function requestLoop() {
    // 只在从完全停止状态新启动时进入；连续链中不清零 lastTs
    if (rafId === null) { rafId = requestAnimationFrame(frame); }
  }
  function frame(ts) {
    rafId = null;
    var dt = lastTs ? Math.min((ts - lastTs) / 1000, 0.1) : 0;
    lastTs = ts;
    var s = state.s3;

    if (state.playing) {
      state.tau += dt * RATE;
      if (state.tau >= TAU_MAX) { state.tau = TAU_MAX; pause(); }
      progSlider.value = String(Math.round(state.tau / TAU_MAX * 1000));
    }
    if (state.step === 3) {
      if (s.mode === 'toSnap') {
        s.t0 += dt;
        var p = Math.min(s.t0 / 1.8, 1);
        state.tau = s.tau0 + (TAU_MAX - s.tau0) * ease(p);
        if (p >= 1) { state.tau = TAU_MAX; s.mode = 'align'; s.alignT = 0; }
      } else if (s.mode === 'align') {
        s.alignT += dt;
        if (s.alignT >= 0.05 * (N - 1) + 0.7) { s.mode = 'done'; onAligned(); }
      }
      if (s.ampAnim) {
        // A4 展开动画 / A5 外移动画：结束后才揭示当步公式
        s.ampT += dt;
        var dur = s.ampAnim === 'grow' ? 1.0 : 1.4;
        if (s.ampT >= dur) {
          var finished = s.ampAnim;
          s.ampAnim = null;
          ampReveal.innerHTML = AMP_HTML[s.amp];
          renderTex(ampReveal);
          if (finished === 'grow') {
            ampNextBtn.disabled = false;
          } else {
            ampNextBtn.hidden = true;      // A5 完成后不再显示“下一步”
          }
        }
      }
    }
    render();
    if (needsLoop()) {
      requestLoop();          // 续排：保留 lastTs，dt 连续
    } else {
      lastTs = 0;             // 链完全结束：下次新启动从 dt=0 开始
    }
  }

  function pause() {
    state.playing = false;
    playBtn.textContent = '▶ 播放';
  }

  // ---------- 第 2 段控制 ----------
  playBtn.addEventListener('click', function () {
    if (state.playing) {
      pause();
    } else {
      if (state.tau >= TAU_MAX) { state.tau = 0; }
      state.playing = true;
      playBtn.textContent = '⏸ 暂停';
      requestLoop();
    }
  });
  replayBtn.addEventListener('click', function () {
    state.tau = 0;
    progSlider.value = '0';
    state.playing = true;
    playBtn.textContent = '⏸ 暂停';
    requestLoop();
  });
  progSlider.addEventListener('input', function () {
    pause();
    state.tau = Number(progSlider.value) / 1000 * TAU_MAX;
    render();
  });

  // ---------- 第 3 段控制 ----------
  function onAligned() {
    s3intro.textContent = '红点落到了下面的刻度图上——和题图（b）一模一样。';
    snapBtn.hidden = true;
    lambdaBtn.hidden = false;
    ampBtn.hidden = false;
    againBtn.hidden = false;
  }
  snapBtn.addEventListener('click', function () {
    pause();
    collapseAmp();                 // 重新执行停题图前清零振幅子序列
    var s = state.s3;
    s.mode = 'toSnap';
    s.tau0 = state.tau;
    s.t0 = 0;
    requestLoop();
  });
  lambdaBtn.addEventListener('click', function () {
    var s = state.s3;
    if (s.amp !== 'off') { collapseAmp(); }   // 振幅展开中先完整清零，避免叠加
    s.lambda = !s.lambda;
    lambdaReveal.hidden = !s.lambda;
    if (s.lambda) { renderTex(lambdaReveal); }
    lambdaBtn.textContent = s.lambda ? '收起波长' : '看波长';
    render();
  });

  // 清零振幅子序列：状态、过渡、公式、灰点、标记与“下一步”按钮全部复位
  function collapseAmp() {
    var s = state.s3;
    s.amp = 'off';
    s.ampAnim = null;
    ampReveal.hidden = true;
    ampNextBtn.hidden = true;
    ampNextBtn.disabled = false;
    ampBtn.textContent = '看振幅';
  }

  ampBtn.addEventListener('click', function () {
    var s = state.s3;
    if (s.amp === 'off') {
      // 进入 A0：自动收起“看波长”避免叠加
      s.lambda = false;
      lambdaReveal.hidden = true;
      lambdaBtn.textContent = '看波长';
      s.amp = 0;
      s.ampAnim = null;
      ampReveal.innerHTML = AMP_HTML[0];
      ampReveal.hidden = false;
      renderTex(ampReveal);
      ampNextBtn.hidden = false;
      ampNextBtn.disabled = false;
      ampBtn.textContent = '收起振幅';
      render();
    } else {
      collapseAmp();
      render();
    }
  });

  // “下一步”：每次只推进一个状态；动画运行中禁用，重复点击不跳步
  ampNextBtn.addEventListener('click', function () {
    var s = state.s3;
    if (s.amp === 'off' || s.ampAnim || s.amp >= 5) { return; }
    s.amp++;
    if (s.amp === 4) {
      s.ampAnim = 'grow';          // A4：中点向左右各展开 10 cm
      s.ampT = 0;
      ampNextBtn.disabled = true;
      requestLoop();
    } else if (s.amp === 5) {
      s.ampAnim = 'move';          // A5：关键点从 15/35 移向 9/41
      s.ampT = 0;
      ampNextBtn.disabled = true;
      requestLoop();
    } else {
      ampReveal.innerHTML = AMP_HTML[s.amp];
      renderTex(ampReveal);
    }
    render();
  });
  againBtn.addEventListener('click', function () {
    var s = state.s3;
    s.mode = 'live';
    s.lambda = false;
    collapseAmp();                   // 重新放一遍：清零振幅子序列
    state.tau = 0;
    progSlider.value = '0';
    s3intro.textContent = '弹簧还在动。点下面的按钮，让它正好停在题图（b）那一刻。';
    snapBtn.hidden = false;
    lambdaBtn.hidden = true;
    ampBtn.hidden = true;
    againBtn.hidden = true;
    lambdaBtn.textContent = '看波长';
    lambdaReveal.hidden = true;
    state.playing = true;
    playBtn.textContent = '⏸ 暂停';   // 播放状态文案同步
    requestLoop();
  });

  // ---------- 分页导航 ----------
  function setStep(k) {
    if (k !== 3) { collapseAmp(); }   // 返回/直切离开第三段：清零振幅子序列
    state.step = k;
    if (k === 1) { pause(); }
    for (var i = 0; i < sections.length; i++) {
      sections[i].hidden = Number(sections[i].dataset.step) !== k;
    }
    for (var j = 0; j < navBtns.length; j++) {
      navBtns[j].classList.toggle('active', Number(navBtns[j].dataset.step) === k);
    }
    prevBtn.disabled = (k === 1);
    nextBtn.disabled = (k === 3);
    // 导航后按实际播放状态同步第 2 段按钮文案，防陈旧
    playBtn.textContent = state.playing ? '⏸ 暂停' : '▶ 播放';
    var ids = STEP_CANVASES[k];
    for (var c = 0; c < ids.length; c++) { fit(ids[c]); }
    render();
    window.scrollTo(0, 0);
  }

  for (var b = 0; b < navBtns.length; b++) {
    navBtns[b].addEventListener('click', function () {
      setStep(Number(this.dataset.step));
    });
  }
  prevBtn.addEventListener('click', function () { if (state.step > 1) { setStep(state.step - 1); } });
  nextBtn.addEventListener('click', function () { if (state.step < 3) { setStep(state.step + 1); } });

  window.addEventListener('resize', function () {
    var ids = STEP_CANVASES[state.step];
    for (var c = 0; c < ids.length; c++) { fit(ids[c]); }
    render();
  });

  // 页面隐藏自动暂停；回到可见时如有未完成的过渡动画则继续
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      pause();
    } else if (needsLoop()) {
      requestLoop();
    }
  });

  // ---------- 初始化 ----------
  setStep(1);
})();
