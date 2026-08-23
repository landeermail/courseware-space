/* 滑轨上的小球 · 四段互动体验
 * 物理结论与事件顺序全部来自 EXPERIMENT_BRIEF.md，不在此处改动。
 * 动画不对应真实物理秒数；位置沿轨道连续，关键事件动能严格按任务书取值。
 */
(function () {
  'use strict';

  // ---------- 几何（世界坐标，单位 m，y 向上，CD 高度为 0） ----------
  var sinT = 0.6, cosT = 0.8;               // sin37°, cos37°
  var phiA = Math.atan2(sinT, cosT);        // O2A、O1B 与竖直方向夹角
  var Rbig = 2, rsmall = 1;
  var O2 = { x: 0, y: 2 }, O1 = { x: 3, y: 1 };
  var D = { x: 0, y: 0 }, C = { x: 3, y: 0 };
  var A = { x: O2.x + Rbig * sinT, y: O2.y + Rbig * cosT };   // (1.2, 3.6)
  var B = { x: O1.x + rsmall * sinT, y: O1.y + rsmall * cosT }; // (3.6, 1.8)
  var P = { x: O2.x - Rbig, y: O2.y }, Q = { x: O1.x + rsmall, y: O1.y };
  var TOP = { x: O2.x, y: O2.y + Rbig };     // 大圆最高点 (0, 4)

  var MG = 10; // m*g = 1*10

  // 世界 -> 屏幕映射（SVG y 向下）
  var SC = 85, OX = 220.5, OY = 400;
  function sx(x) { return OX + SC * x; }
  function sy(y) { return OY - SC * y; }

  function dist(p, q) { return Math.hypot(q.x - p.x, q.y - p.y); }

  // ---------- 轨道段 ----------
  // 直线段：动能随路程线性变化（恒力，严格正确）
  function lineLeg(p0, p1, K0, K1, opts) {
    var leg = {
      kind: 'line', p0: p0, p1: p1, K0: K0, K1: K1,
      len: dist(p0, p1), fric: 0, onCD: false
    };
    return Object.assign(leg, opts || {});
  }
  // 圆弧段：动能由高度决定 K = K0 - mg*(h-h0)（光滑，严格正确）
  function arcLeg(c, rad, phi0, phi1, K0, opts) {
    var leg = {
      kind: 'arc', c: c, rad: rad, phi0: phi0, phi1: phi1, K0: K0,
      len: rad * Math.abs(phi1 - phi0), fric: 0, onCD: false
    };
    return Object.assign(leg, opts || {});
  }

  function legPoint(leg, s) {
    var t = Math.min(Math.max(s / leg.len, 0), 1);
    if (leg.kind === 'line') {
      return { x: leg.p0.x + (leg.p1.x - leg.p0.x) * t, y: leg.p0.y + (leg.p1.y - leg.p0.y) * t };
    }
    var phi = leg.phi0 + (leg.phi1 - leg.phi0) * t;
    return { x: leg.c.x + leg.rad * Math.sin(phi), y: leg.c.y + leg.rad * Math.cos(phi) };
  }

  function legTangent(leg, s) {
    var t = Math.min(Math.max(s / leg.len, 0), 1);
    if (leg.kind === 'line') {
      var L = leg.len || 1;
      return { x: (leg.p1.x - leg.p0.x) / L, y: (leg.p1.y - leg.p0.y) / L };
    }
    var phi = leg.phi0 + (leg.phi1 - leg.phi0) * t;
    var sgn = leg.phi1 >= leg.phi0 ? 1 : -1;
    return { x: sgn * Math.cos(phi), y: -sgn * Math.sin(phi) };
  }

  function legK(leg, s) {
    var t = Math.min(Math.max(s / leg.len, 0), 1);
    if (leg.kind === 'line') return leg.K0 + (leg.K1 - leg.K0) * t;
    var phi = leg.phi0 + (leg.phi1 - leg.phi0) * t;
    var h0 = leg.c.y + leg.rad * Math.cos(leg.phi0);
    var h = leg.c.y + leg.rad * Math.cos(phi);
    return leg.K0 - MG * (h - h0);
  }

  function legSamples(leg, n) {
    var pts = [];
    for (var i = 0; i <= n; i++) pts.push(legPoint(leg, leg.len * i / n));
    return pts;
  }

  // ---------- 各段定义 ----------
  // 关键数值（来自任务书）：
  // 第一周: B30 -> A4 -> 顶点0 -> D40 -> C30 -> B12
  // 第二次到 D: 12 -> AB上行18/13m转向0 -> 回B 60/13 -> C 294/13 -> D 164/13
  // CD 总路程: 大圆弧转向 -> 回D 164/13 -> C 34/13 -> 小圆弧转向 -> 回C -> 滑行51/65m停
  var T1 = { x: B.x - 0.8 * 18 / 13, y: B.y + 0.6 * 18 / 13 }; // AB 转向点
  var phiBigTurn = 2 * Math.PI - Math.acos(-24 / 65);          // 大圆弧转向点（左侧, h=82/65）
  var phiSmallTurn = Math.acos(-48 / 65);                      // 小圆弧转向点（右侧, h=17/65）
  var stopPt = { x: C.x - 51 / 65, y: 0 };                     // 最终停下点

  var STAGES = {
    2: {
      startK: 30,
      revealAt: 1, // 到达“大圆最高点·临界”（leg 1 结束）前，前台动能读数显示“—”，不泄露 30 J
      legs: [
        lineLeg(B, A, 30, 4, { fric: 8 }),
        arcLeg(O2, Rbig, phiA, 0, 4, { marker: { pos: TOP, label: '最高点', dx: -26, dy: -12, anchor: 'end' } }),
        arcLeg(O2, Rbig, 0, -Math.PI, 0),
        lineLeg(D, C, 40, 30, { fric: 10 }),
        arcLeg(O1, rsmall, Math.PI, phiA, 30)
      ]
    },
    3: {
      startK: 12,
      legs: [
        lineLeg(B, T1, 12, 0, { fric: 48 / 13, marker: { pos: T1, label: '转向', dx: 20, dy: -24, anchor: 'start' } }),
        lineLeg(T1, B, 0, 60 / 13, { fric: 48 / 13 }),
        arcLeg(O1, rsmall, phiA, Math.PI, 60 / 13),
        lineLeg(C, D, 294 / 13, 164 / 13, { fric: 10 })
      ]
    },
    4: {
      startK: 164 / 13,
      cdBase: 6,
      legs: [
        arcLeg(O2, Rbig, Math.PI, phiBigTurn, 164 / 13, {
          marker: { pos: { x: O2.x + Rbig * Math.sin(phiBigTurn), y: O2.y + Rbig * Math.cos(phiBigTurn) }, label: '转向', dx: -24, dy: -8, anchor: 'end' }
        }),
        arcLeg(O2, Rbig, phiBigTurn, Math.PI, 0),
        lineLeg(D, C, 164 / 13, 34 / 13, { fric: 10, onCD: true, cdRow: 3 }),
        arcLeg(O1, rsmall, Math.PI, phiSmallTurn, 34 / 13, {
          marker: { pos: { x: O1.x + rsmall * Math.sin(phiSmallTurn), y: O1.y + rsmall * Math.cos(phiSmallTurn) }, label: '转向', dx: 24, dy: -28, anchor: 'start' }
        }),
        arcLeg(O1, rsmall, phiSmallTurn, Math.PI, 0),
        lineLeg(C, stopPt, 34 / 13, 0, { fric: 34 / 13, onCD: true, cdRow: 4 })
      ]
    }
  };

  // ---------- SVG 轨道 ----------
  var NS = 'http://www.w3.org/2000/svg';

  function arcPts(c, rad, phi0, phi1) {
    var n = Math.max(12, Math.ceil(Math.abs(phi1 - phi0) / 0.04));
    var pts = [];
    for (var i = 0; i <= n; i++) {
      var p = phi0 + (phi1 - phi0) * i / n;
      pts.push({ x: c.x + rad * Math.sin(p), y: c.y + rad * Math.cos(p) });
    }
    return pts;
  }

  function ptsToD(pts, close) {
    var d = 'M' + sx(pts[0].x).toFixed(1) + ',' + sy(pts[0].y).toFixed(1);
    for (var i = 1; i < pts.length; i++) d += 'L' + sx(pts[i].x).toFixed(1) + ',' + sy(pts[i].y).toFixed(1);
    return d + (close ? 'Z' : '');
  }

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function buildTrack(container) {
    var svg = el('svg', { viewBox: '0 0 640 460', role: 'img', 'aria-label': '滑轨示意图' }, container);

    // 轨道：A -(大圆弧过顶点、P)-> D -> C -(小圆弧过Q)-> B -(直轨)-> A
    var loop = [A].concat(arcPts(O2, Rbig, phiA, -Math.PI).slice(1));
    loop.push(C);
    loop = loop.concat(arcPts(O1, rsmall, Math.PI, phiA).slice(1));
    loop.push(A);
    el('path', {
      d: ptsToD(loop, true), fill: 'none', stroke: '#33404f',
      'stroke-width': 5, 'stroke-linejoin': 'round'
    }, svg);

    // 圆心虚线
    var dash = { stroke: '#9aa7b5', 'stroke-width': 1, 'stroke-dasharray': '4 4' };
    el('line', Object.assign({ x1: sx(O2.x), y1: sy(O2.y), x2: sx(D.x), y2: sy(D.y) }, dash), svg);
    el('line', Object.assign({ x1: sx(O1.x), y1: sy(O1.y), x2: sx(C.x), y2: sy(C.y) }, dash), svg);

    // 点标签
    function label(p, text, dx, dy) {
      var t = el('text', {
        x: sx(p.x) + (dx || 0), y: sy(p.y) + (dy || 0),
        'font-size': 16, 'font-weight': 600, fill: '#33404f'
      }, svg);
      t.textContent = text;
    }
    label(A, 'A', 8, -6); label(B, 'B', 10, 4); label(C, 'C', 6, 20);
    label(D, 'D', -16, 20); label(P, 'P', -18, 6); label(Q, 'Q', 10, 6);
    label(TOP, '最高点 4 m', 10, -6);
    label(O2, 'O₂', 8, 4); label(O1, 'O₁', 8, 4);

    // 图层：当前段高亮、事件标记、映射高亮、小球
    var hlG = el('g', {}, svg);
    var markerG = el('g', {}, svg);
    var mapG = el('g', {}, svg);
    var ballG = el('g', {}, svg);
    el('polygon', { points: '14,0 -8,-7 -8,7', fill: '#e8590c', class: 'arrow' }, ballG);
    el('circle', { r: 8, fill: '#ffd8a8', stroke: '#e8590c', 'stroke-width': 3, class: 'ball' }, ballG);

    return { svg: svg, hlG: hlG, markerG: markerG, mapG: mapG, ballG: ballG };
  }

  // ---------- 关键量—模型映射（绿色图层，独立于物理状态） ----------
  var MAP_COL = '#2f9e44';
  function mLine(g, p, q, w) {
    el('line', { x1: sx(p.x), y1: sy(p.y), x2: sx(q.x), y2: sy(q.y), stroke: MAP_COL, 'stroke-width': w || 4, 'stroke-linecap': 'round' }, g);
  }
  function mText(g, p, str) {
    var t = el('text', { x: sx(p.x), y: sy(p.y), 'font-size': 15, 'font-weight': 700, fill: MAP_COL, 'text-anchor': 'middle' }, g);
    t.textContent = str;
  }
  function mTextSub(g, p, base, sub, rest) {
    var t = el('text', { x: sx(p.x), y: sy(p.y), 'font-size': 15, 'font-weight': 700, fill: MAP_COL, 'text-anchor': 'middle' }, g);
    var t1 = el('tspan', {}, t); t1.textContent = base;
    var t2 = el('tspan', { dy: 4, 'font-size': 11 }, t); t2.textContent = sub;
    var t3 = el('tspan', { dy: -4 }, t); t3.textContent = rest;
  }
  function mDot(g, p) {
    el('circle', { cx: sx(p.x), cy: sy(p.y), r: 5, fill: MAP_COL, stroke: '#fff', 'stroke-width': 2 }, g);
  }
  function mArrow(g, p, dir) {
    var a = Math.atan2(-dir.y, dir.x) * 180 / Math.PI;
    el('polygon', { points: '10,0 -6,-6 -6,6', fill: MAP_COL, transform: 'translate(' + sx(p.x) + ',' + sy(p.y) + ') rotate(' + a + ')' }, g);
  }
  // 尺寸线：平行于 p-q 沿单位法向 n 偏移 d，两端带连接短线的可抄画标注
  function mDim(g, p, q, n, d, label) {
    var p2 = { x: p.x + n.x * d, y: p.y + n.y * d };
    var q2 = { x: q.x + n.x * d, y: q.y + n.y * d };
    mLine(g, p2, q2, 2);
    mLine(g, p, { x: p.x + n.x * (d + 0.12), y: p.y + n.y * (d + 0.12) }, 1.5);
    mLine(g, q, { x: q.x + n.x * (d + 0.12), y: q.y + n.y * (d + 0.12) }, 1.5);
    mText(g, { x: (p2.x + q2.x) / 2 + n.x * 0.38, y: (p2.y + q2.y) / 2 + n.y * 0.38 }, label);
  }

  var MAPPINGS = {
    2: {
      L: function (g) {
        mLine(g, A, B, 4); mLine(g, D, C, 4);
        mDim(g, A, B, { x: 0.6, y: 0.8 }, 0.3, 'L = 3 m');
        mDim(g, D, C, { x: 0, y: -1 }, 0.28, 'L = 3 m');
      },
      r: function (g) {
        mLine(g, O1, B, 3); mDot(g, B);
        mText(g, { x: (O1.x + B.x) / 2 + 0.42, y: (O1.y + B.y) / 2 }, 'r = 1 m');
      },
      R: function (g) {
        mLine(g, O2, A, 3); mDot(g, A);
        mText(g, { x: (O2.x + A.x) / 2 - 0.45, y: (O2.y + A.y) / 2 }, 'R = 2 m');
      },
      theta: function (g) {
        el('line', { x1: sx(O2.x), y1: sy(O2.y), x2: sx(O2.x), y2: sy(O2.y + 1.7), stroke: MAP_COL, 'stroke-width': 1.5, 'stroke-dasharray': '4 3' }, g);
        el('path', { d: ptsToD(arcPts(O2, 1.2, 0, phiA), false), fill: 'none', stroke: MAP_COL, 'stroke-width': 2.5 }, g);
        mText(g, { x: O2.x + 1.55 * Math.sin(phiA / 2) + 0.3, y: O2.y + 1.55 * Math.cos(phiA / 2) }, 'θ');
      },
      hB: function (g) {
        mLine(g, { x: B.x, y: 0 }, B, 3);
        mLine(g, { x: B.x - 0.25, y: 0 }, { x: B.x + 0.25, y: 0 }, 2);
        mTextSub(g, { x: B.x + 0.7, y: B.y / 2 }, 'h', 'B', ' = 1.8 m');
      },
      twoR: function (g) {
        mLine(g, D, TOP, 3);
        mText(g, { x: -0.75, y: 2 }, '2R = 4 m');
      },
      fAB: function (g) {
        mLine(g, A, B, 7);
        mText(g, { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 - 0.4 }, '全程摩擦耗散 8 J');
      },
      fCD: function (g) {
        mLine(g, D, C, 7);
        mText(g, { x: 1.5, y: -0.42 }, '全程摩擦耗散 10 J');
      }
    },
    3: {
      s13: function (g) {
        mLine(g, B, T1, 6); mDot(g, B); mDot(g, T1);
        mText(g, { x: (B.x + T1.x) / 2 + 0.35 * 0.6, y: (B.y + T1.y) / 2 + 0.35 * 0.8 }, '18/13 m');
      }
    },
    4: {
      cd1: function (g) {
        mLine(g, D, C, 6); mArrow(g, { x: 1.5, y: 0 }, { x: 1, y: 0 });
        mText(g, { x: 1.5, y: -0.42 }, '① 第一周 D→C：3 m');
      },
      cd2: function (g) {
        mLine(g, D, C, 6); mArrow(g, { x: 1.5, y: 0 }, { x: -1, y: 0 });
        mText(g, { x: 1.5, y: -0.42 }, '② 折返 C→D：3 m');
      },
      cd3: function (g) {
        mLine(g, D, C, 6); mArrow(g, { x: 1.5, y: 0 }, { x: 1, y: 0 });
        mText(g, { x: 1.5, y: -0.42 }, '③ 再次 D→C：3 m');
      },
      cd4: function (g) {
        mLine(g, C, stopPt, 6); mDot(g, stopPt);
        mArrow(g, { x: (C.x + stopPt.x) / 2, y: 0 }, { x: -1, y: 0 });
        mText(g, { x: (C.x + stopPt.x) / 2, y: -0.42 }, '④ 51/65 m');
      }
    }
  };

  // ---------- 单段动画器 ----------
  function createRunner(stageId) {
    var def = STAGES[stageId];
    var sec = document.getElementById('stage-' + stageId);
    var parts = buildTrack(sec.querySelector('.track'));
    var ui = {
      k: sec.querySelector('.kv-k'),
      fric: sec.querySelector('.kv-fric'),
      cd: sec.querySelector('.kv-cd'),
      cdR3: sec.querySelector('.cd-r3'),
      cdR4: sec.querySelector('.cd-r4'),
      cdTotal: sec.querySelector('.cd-total'),
      play: sec.querySelector('.btn-play'),
      next: sec.querySelector('.btn-next'),
      replay: sec.querySelector('.btn-replay'),
      cards: Array.prototype.slice.call(sec.querySelectorAll('.card'))
    };

    var legI = 0, s = 0, playing = false, atEvent = false, finished = false, raf = null, lastT = 0;
    var revealed = false, activeMap = null;

    function legsBefore(i) { return def.legs.slice(0, i); }
    function sumFric(list) { return list.reduce(function (a, l) { return a + l.fric; }, 0); }

    function liveFric() {
      var leg = def.legs[legI];
      return sumFric(legsBefore(legI)) + leg.fric * Math.min(s / leg.len, 1);
    }
    function cdRowDist(row) {
      var v = 0;
      def.legs.forEach(function (leg, i) {
        if (!leg.onCD || leg.cdRow !== row) return;
        if (i < legI) v += leg.len;
        else if (i === legI) v += Math.min(s, leg.len);
      });
      return v;
    }

    function render() {
      var leg = def.legs[legI];
      var p = legPoint(leg, s);
      var tv = legTangent(leg, s);
      var ang = Math.atan2(-tv.y, tv.x) * 180 / Math.PI;
      parts.ballG.setAttribute('transform',
        'translate(' + sx(p.x).toFixed(1) + ',' + sy(p.y).toFixed(1) + ') rotate(' + ang.toFixed(1) + ')');

      var K = legK(leg, s);
      ui.k.textContent = (def.revealAt !== undefined && !revealed) ? '—' : K.toFixed(1) + ' J';
      if (ui.fric) ui.fric.textContent = liveFric().toFixed(1) + ' J';
      if (ui.cd) {
        var r3 = cdRowDist(3), r4 = cdRowDist(4);
        var done = finished;
        ui.cdR3.textContent = r3 >= 3 - 1e-9 ? '3 m' : r3.toFixed(2) + ' m';
        ui.cdR4.textContent = r4 >= 51 / 65 - 1e-9 ? '51/65 m' : r4.toFixed(2) + ' m';
        var tot = def.cdBase + r3 + r4;
        ui.cd.textContent = done ? '636/65 m ≈ 9.78 m' : tot.toFixed(2) + ' m';
        ui.cdTotal.textContent = done ? '636/65 m ≈ 9.78 m' : tot.toFixed(2) + ' m';
      }
    }

    function showCard(key) {
      ui.cards.forEach(function (c) {
        c.hidden = c.getAttribute('data-card') !== String(key);
      });
    }

    function highlightLeg() {
      parts.hlG.innerHTML = '';
      var pts = legSamples(def.legs[legI], 40);
      el('path', {
        d: ptsToD(pts, false), fill: 'none', stroke: 'rgba(31,111,235,0.35)',
        'stroke-width': 11, 'stroke-linecap': 'round'
      }, parts.hlG);
    }

    function addMarker(mk) {
      var g = el('g', {}, parts.markerG);
      el('circle', { cx: sx(mk.pos.x), cy: sy(mk.pos.y), r: 6, fill: '#d6336c', stroke: '#fff', 'stroke-width': 2 }, g);
      // 事件文字：深色字 + 浅色衬底，按事件给定位移/锚点，避开静态点名、轨迹与小球
      var t = el('text', {
        x: sx(mk.pos.x) + (mk.dx !== undefined ? mk.dx : 10),
        y: sy(mk.pos.y) + (mk.dy !== undefined ? mk.dy : -8),
        'font-size': 14, 'font-weight': 700, fill: '#9d174d',
        'text-anchor': mk.anchor || 'start'
      }, g);
      t.textContent = mk.label;
      var bb = t.getBBox();
      var bg = el('rect', {
        x: bb.x - 4, y: bb.y - 2, width: bb.width + 8, height: bb.height + 4,
        rx: 4, fill: 'rgba(255,255,255,0.92)', stroke: '#e3a8bc', 'stroke-width': 1
      }, g);
      g.insertBefore(bg, t);
    }

    function setPlaying(v) {
      playing = v;
      ui.play.textContent = v ? '⏸ 暂停' : '▶ 播放';
    }

    function pause() {
      setPlaying(false);
      if (raf) { cancelAnimationFrame(raf); raf = null; }
    }

    function onLegEnd() {
      s = def.legs[legI].len;
      if (legI === def.revealAt) revealed = true; // 临界事件到达后才揭示 30 J
      if (legI === def.legs.length - 1) finished = true;
      render();
      var leg = def.legs[legI];
      pause();
      atEvent = true;
      showCard(legI);
      if (leg.marker) addMarker(leg.marker);
      if (finished) {
        ui.play.disabled = true;
        ui.next.disabled = true;
      }
    }

    function tick(now) {
      raf = null;
      if (!playing) return;
      var dt = Math.min((now - lastT) / 1000, 0.05);
      lastT = now;
      var leg = def.legs[legI];
      var K = Math.max(legK(leg, s), 0);
      var v = 0.3 + 0.55 * Math.sqrt(K); // 视觉速度，非物理秒数
      s += v * dt;
      if (s >= leg.len) { onLegEnd(); return; }
      render();
      raf = requestAnimationFrame(tick);
    }

    function play() {
      if (finished) return;
      clearMap(); // 播放时清除映射高亮
      if (atEvent) { // 从冻结事件推进到下一 leg
        atEvent = false;
        legI += 1;
        s = 0;
        highlightLeg();
      }
      if (playing) { pause(); render(); return; }
      setPlaying(true);
      lastT = performance.now();
      if (!raf) raf = requestAnimationFrame(tick);
    }

    function clearMap() {
      activeMap = null;
      parts.mapG.innerHTML = '';
      sec.querySelectorAll('[data-map]').forEach(function (b) {
        b.classList.remove('map-on');
        b.setAttribute('aria-pressed', 'false');
      });
    }

    function setMapState(key, on) { // 同键触发器全部同步
      sec.querySelectorAll('[data-map="' + key + '"]').forEach(function (x) {
        x.classList.toggle('map-on', on);
        x.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    function toggleMap(key) {
      if (activeMap === key) { clearMap(); return; }
      clearMap();
      var fn = MAPPINGS[stageId] && MAPPINGS[stageId][key];
      if (!fn) return;
      fn(parts.mapG);
      activeMap = key;
      setMapState(key, true);
    }

    function reset() {
      pause();
      legI = 0; s = 0; atEvent = false; finished = false; revealed = false;
      ui.play.disabled = false;
      ui.next.disabled = false;
      parts.markerG.innerHTML = '';
      clearMap();
      showCard('intro');
      highlightLeg();
      render();
    }

    ui.play.addEventListener('click', play);
    ui.next.addEventListener('click', function () {
      if (finished) return;
      clearMap(); // 下一事件时清除映射高亮
      if (!playing) play(); // 未在播放：推进到下一事件（到达后会自动冻结）
    });
    ui.replay.addEventListener('click', reset);
    sec.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-map]');
      if (b && sec.contains(b)) toggleMap(b.getAttribute('data-map'));
    });
    // 确定性键盘激活：仅 Enter/Space，preventDefault 抑制原生 click，避免双切换
    sec.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      var b = ev.target.closest('[data-map]');
      if (!b || !sec.contains(b)) return;
      ev.preventDefault();
      toggleMap(b.getAttribute('data-map'));
    });

    reset();
    return { pause: pause, reset: reset, clearMap: clearMap };
  }

  // ---------- 段切换 ----------
  var runners = {};
  var currentStage = 1;

  function showStage(n) {
    if (runners[currentStage]) { runners[currentStage].pause(); runners[currentStage].clearMap(); }
    currentStage = n;
    [1, 2, 3, 4].forEach(function (i) {
      document.getElementById('stage-' + i).hidden = i !== n;
    });
    document.querySelectorAll('.tab').forEach(function (t) {
      t.classList.toggle('active', Number(t.getAttribute('data-stage')) === n);
    });
    if (n >= 2 && !runners[n]) runners[n] = createRunner(n);
  }

  document.querySelectorAll('.tab').forEach(function (t) {
    t.addEventListener('click', function () { showStage(Number(t.getAttribute('data-stage'))); });
  });
  document.querySelectorAll('[data-goto]').forEach(function (b) {
    b.addEventListener('click', function () { showStage(Number(b.getAttribute('data-goto'))); });
  });

  // 页面隐藏自动暂停
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      Object.keys(runners).forEach(function (k) { runners[k].pause(); });
    }
  });

  // ---------- 公式渲染（失败时保留可读 LaTeX 文本，不抛异常） ----------
  try {
    if (!window.__katexFailed && typeof window.renderMathInElement === 'function') {
      window.renderMathInElement(document.body, {
        delimiters: [
          { left: '\\(', right: '\\)', display: false },
          { left: '$$', right: '$$', display: true }
        ],
        throwOnError: false
      });
    } else {
      document.body.classList.add('no-katex');
    }
  } catch (e) {
    document.body.classList.add('no-katex');
  }

  showStage(1);
})();
