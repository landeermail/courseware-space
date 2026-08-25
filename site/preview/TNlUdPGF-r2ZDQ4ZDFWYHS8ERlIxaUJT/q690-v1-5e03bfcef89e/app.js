/* 笔的弹跳 · 课堂课件
 * 依据当前修订契约实现：
 *  - 四检查点：离桌 / X1 碰前 / X1 碰后 / 最高点；X1 碰前后同位（同一游标位置，仅切换速度、身份与证据）。
 *  - 碰撞几何：外壳挡点与内芯法兰间距连续减小到 0；碰后两者相对位置固定共同移动。
 *  - 教学公式一律用 MathML 排版（分式、根号、上下标），不使用 Unicode 冒充。
 *  - 动量系统（外壳+内芯，仅 X1）与能量系统（外壳+地球 / 整支笔+地球，按需进入）严格分离。
 */
'use strict';

/* ---------- 几何常量（像素，仅用于绘制） ---------- */
var DESK = 390, H1 = 300, H2 = 210;   // y=0 / h₁ / h₂ 横线
var SHELL_H = 170;
var LEDGE_OFF = 28;                   // 挡点距外壳下端 28px
var FLANGE_REST = 272;                // 内芯法兰上表面（接触面）静止高度
var CORE_TOP_OFF = 32, CORE_BOT_OFF = 118;
var TC = 0.5;                         // 游标中点 = X1（外壳下端恰在 h₁）

var state = {
  view: 'dynamic',        // dynamic | paper
  cursor: 0,
  phase: 'before',        // cursor==0.5 时区分 X1 碰前/碰后
  compared: false,        // 老师已触发“比较碰前/碰后”
  energyMode: false,      // 老师已进入“能量口径比较”
  boundary: 'shell',      // shell=外壳+地球 / pen=整支笔+地球
  s2mark: false,
  reveal: { v: false, u: false, ws: false, el: false },
  highlight: null,
  playing: false
};
var energySnapshot = null;   // 进入能量支线前的物理状态快照

var $ = function (id) { return document.getElementById(id); };

/* ---------- MathML 教学公式 ---------- */
var M = {
  s2eq: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>(</mo><mn>5</mn><mi>m</mi><mo>)</mo><msup><mi>v</mi><mn>2</mn></msup><mo>=</mo><mn>5</mn><mi>m</mi><mi>g</mi><mo>(</mo><msub><mi>h</mi><mn>2</mn></msub><mo>−</mo><msub><mi>h</mi><mn>1</mn></msub><mo>)</mo></mrow></math>',
  vRoot: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>v</mi><mo>=</mo><msqrt><mrow><mn>2</mn><mi>g</mi><mo>(</mo><msub><mi>h</mi><mn>2</mn></msub><mo>−</mo><msub><mi>h</mi><mn>1</mn></msub><mo>)</mo></mrow></msqrt></mrow></math>',
  mom: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mn>4</mn><mi>m</mi><mi>u</mi><mo>=</mo><mn>5</mn><mi>m</mi><mi>v</mi></mrow></math>',
  momLong: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mn>4</mn><mi>m</mi><mi>u</mi><mo>+</mo><mn>0</mn><mo>=</mo><mn>5</mn><mi>m</mi><mi>v</mi></mrow></math>',
  vOfU: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>v</mi><mo>=</mo><mfrac><mn>4</mn><mn>5</mn></mfrac><mi>u</mi></mrow></math>',
  uOfV: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>u</mi><mo>=</mo><mfrac><mn>5</mn><mn>4</mn></mfrac><mi>v</mi></mrow></math>',
  wsShellGen: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>W</mi><mi>s</mi></msub><mo>=</mo><mi>Δ</mi><msub><mi>K</mi><mrow>外壳</mrow></msub><mo>+</mo><mi>Δ</mi><msub><mi>U</mi><mi>g</mi></msub></mrow></math>',
  wsShell: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>W</mi><mi>s</mi></msub><mo>−</mo><mn>4</mn><mi>m</mi><mi>g</mi><msub><mi>h</mi><mn>1</mn></msub><mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>(</mo><mn>4</mn><mi>m</mi><mo>)</mo><msup><mi>u</mi><mn>2</mn></msup></mrow></math>',
  wsFinal: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>W</mi><mi>s</mi></msub><mo>=</mo><mfrac><mrow><mi>m</mi><mi>g</mi></mrow><mn>4</mn></mfrac><mo>(</mo><mn>25</mn><msub><mi>h</mi><mn>2</mn></msub><mo>−</mo><mn>9</mn><msub><mi>h</mi><mn>1</mn></msub><mo>)</mo></mrow></math>',
  elossDef: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>E</mi><mrow>损</mrow></msub><mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>(</mo><mn>4</mn><mi>m</mi><mo>)</mo><msup><mi>u</mi><mn>2</mn></msup><mo>−</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>(</mo><mn>5</mn><mi>m</mi><mo>)</mo><msup><mi>v</mi><mn>2</mn></msup></mrow></math>',
  elossFinal: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>E</mi><mrow>损</mrow></msub><mo>=</mo><mfrac><mn>5</mn><mn>4</mn></mfrac><mi>m</mi><mi>g</mi><mo>(</mo><msub><mi>h</mi><mn>2</mn></msub><mo>−</mo><msub><mi>h</mi><mn>1</mn></msub><mo>)</mo></mrow></math>',
  selfCheck: '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>W</mi><mi>s</mi></msub><mo>−</mo><mi>m</mi><mi>g</mi><mo>(</mo><mn>5</mn><msub><mi>h</mi><mn>2</mn></msub><mo>−</mo><msub><mi>h</mi><mn>1</mn></msub><mo>)</mo><mo>=</mo><msub><mi>E</mi><mrow>损</mrow></msub></mrow></math>'
};

/* ---------- 几何 ---------- */
function shellBottom(t) { return DESK - (DESK - H2) * t; }       // 390 → 210，t=0.5 时恰为 300=h₁
function flangeTop(t) { return t < TC ? FLANGE_REST : shellBottom(t) - LEDGE_OFF; }

function springPoints(cx, yTop, yBottom) {
  if (yBottom - yTop < 10) yBottom = yTop + 10;
  var pts = [cx + ',' + yTop.toFixed(1)];
  var n = 6, w = 14, seg = (yBottom - yTop) / n;
  for (var i = 1; i < n; i++) pts.push((cx + (i % 2 ? w : -w)) + ',' + (yTop + seg * i).toFixed(1));
  pts.push(cx + ',' + yBottom.toFixed(1));
  return pts.join(' ');
}

function renderModel() {
  var t = state.cursor;
  var sb = shellBottom(t);
  var shTop = sb - SHELL_H;
  var ft = flangeTop(t);
  var coreTop = ft - CORE_TOP_OFF, coreBottom = ft + CORE_BOT_OFF;

  // 外壳（挡点随外壳）
  $('shTop').setAttribute('y', shTop);
  $('shL').setAttribute('y', shTop);
  $('shR').setAttribute('y', shTop);
  $('ledgeL').setAttribute('y', sb - LEDGE_OFF);
  $('ledgeR').setAttribute('y', sb - LEDGE_OFF);
  $('shellLabel').setAttribute('y', shTop + 16);
  // 内芯（碰前静止；碰后与挡点保持接触、相对外壳固定）
  $('coreBody').setAttribute('y', coreTop);
  $('coreFlange').setAttribute('y', ft);
  $('coreLabel').setAttribute('y', ft + 62);
  $('coreLabel').textContent = (Math.abs(t - TC) < 1e-4 && state.phase === 'before') ? 'm（速度 0）' : 'm';
  // 弹簧
  $('spring').setAttribute('points', springPoints(190, shTop + 10, coreTop));
  $('springTag').setAttribute('y', ((shTop + 10 + coreTop) / 2).toFixed(1));
  // 外壳下端标记
  $('yrefLine').setAttribute('y1', sb); $('yrefLine').setAttribute('y2', sb);
  $('yrefText').setAttribute('y', sb + 4);
  // 接触间距指示：挡点在下、法兰在上，实际间距 = ledgeY − flangeY
  var gap = (sb - LEDGE_OFF) - ft;
  var showGap = t < TC - 1e-4 && gap > 0.5;
  $('gGap').setAttribute('visibility', showGap ? 'visible' : 'hidden');
  if (showGap) {
    $('gapLine').setAttribute('y1', sb - LEDGE_OFF);
    $('gapLine').setAttribute('y2', ft);
    $('gapTick1').setAttribute('y1', sb - LEDGE_OFF); $('gapTick1').setAttribute('y2', sb - LEDGE_OFF);
    $('gapTick2').setAttribute('y1', ft); $('gapTick2').setAttribute('y2', ft);
    $('gapText').setAttribute('y', ((sb - LEDGE_OFF + ft) / 2 + 4).toFixed(1));
  }
  // 碰撞接触点
  $('gFlash').setAttribute('visibility', Math.abs(t - TC) < 1e-4 ? 'visible' : 'hidden');
  // 速度箭头
  renderArrow(t);
  // 能量口径比较：边界轮廓、成员区与作用标签（切换只改这些与账本，不动几何）
  var em = state.energyMode;
  var bShell = state.boundary === 'shell';
  $('boundShell').setAttribute('visibility', em && bShell ? 'visible' : 'hidden');
  $('boundShell').setAttribute('y', shTop - 6);
  $('boundPen').setAttribute('visibility', em && !bShell ? 'visible' : 'hidden');
  $('boundPen').setAttribute('y', shTop - 8);
  $('boundPen').setAttribute('height', (coreBottom + 8) - (shTop - 8));
  $('earthZone').setAttribute('visibility', em ? 'visible' : 'hidden');
  $('earthLabel').setAttribute('visibility', em ? 'visible' : 'hidden');
  $('boundLabel').setAttribute('y', shTop - 12);
  $('boundOut').setAttribute('y', shTop - 26);
  $('boundLabel').textContent = em ? (bShell ? '边界内：外壳 4m＋地球' : '边界内：弹簧＋内芯＋外壳＋地球') : '';
  $('boundOut').textContent = em ? (bShell ? '边界外：内芯 m、弹簧' : '边界外：无') : '';
  $('springTag').setAttribute('visibility', em ? 'visible' : 'hidden');
  $('springTag').textContent = bShell ? '外部输入 Ws（跨边界）' : '内部通道（弹簧）';
  // h₂−h₁ 指认括号
  $('gBracket').setAttribute('visibility', state.s2mark && t > TC ? 'visible' : 'hidden');
}

function renderArrow(t) {
  var g = $('gArrow'), lab = $('arrowLabel');
  var eps = 1e-4;
  if (t < eps || t > 1 - eps) { g.setAttribute('visibility', 'hidden'); return; }
  var len, txt;
  if (t < TC - eps) { len = 30; txt = ''; }                                  // S1：仅方向
  else if (Math.abs(t - TC) < eps) {
    if (state.phase === 'before') { len = 46; txt = 'u↑'; }
    else { len = 37; txt = 'v↑'; }
  } else {                                                                    // S2：v 连续降为 0
    var s = (t - TC) / (1 - TC);
    len = 37 * Math.sqrt(1 - s);
    txt = '共同速度 v→0';
    if (len < 1.5) { g.setAttribute('visibility', 'hidden'); return; }
  }
  g.setAttribute('visibility', 'visible');
  $('arrowLine').setAttribute('y2', 366 - len);
  $('arrowHead').setAttribute('points', '250,' + (372 - len) + ' 262,' + (372 - len) + ' 256,' + (362 - len));
  lab.setAttribute('y', 366 - len - 6);
  lab.textContent = txt;
}

/* ---------- 检查点 ---------- */
var CP_NAMES = ['① 离桌（y=0）', '② X1 碰前（y=h₁）', '③ X1 碰后（同一位置 y=h₁）', '④ 最高点（y=h₂）'];
function cpIndex() {
  var t = state.cursor, eps = 1e-4;
  if (t < TC - eps) return 0;
  if (t > TC + eps) return t > 1 - eps ? 3 : 2.5;
  return state.phase === 'after' ? 2 : 1;
}
function region() {
  var t = state.cursor, eps = 1e-4;
  if (t < TC - eps) return 'S1';
  if (t > TC + eps) return 'S2';
  return state.phase === 'after' ? 'X1a' : 'X1b';
}

function compareX1() {
  state.compared = true;
  state.phase = 'after';
  state.cursor = TC;
  $('cursor').value = 500;
  renderAll();
}

function nextCp() {
  var t = state.cursor, eps = 1e-4;
  if (t < TC - eps) { setCursor(TC); state.phase = 'before'; }
  else if (Math.abs(t - TC) < eps && state.phase === 'before') { compareX1(); return; }
  else if (t < 1 - eps) { setCursor(1); }
  else { setView('paper'); return; }   // 末端主动作：最高点 → 进入纸笔整理
  renderAll();
}
function prevCp() {
  var t = state.cursor, eps = 1e-4;
  if (t > TC + eps) { setCursor(TC); state.phase = state.compared ? 'after' : 'before'; }
  else if (Math.abs(t - TC) < eps && state.phase === 'after') { state.phase = 'before'; }
  else if (Math.abs(t - TC) < eps) { setCursor(0); }
  renderAll();
}

function setCursor(t, fromUser) {
  if (!state.compared && t > TC) {          // 揭示门：比较前不得越过 X1
    t = TC;
    if (fromUser) pulseCompare();
  }
  state.cursor = Math.max(0, Math.min(1, t));
  if (state.cursor < TC - 1e-4) state.phase = 'before';
  if (state.cursor > TC + 1e-4) state.phase = 'after';
  $('cursor').value = Math.round(state.cursor * 1000);
  renderAll();
}

function pulseCompare() {
  var b = $('btnNextCp');
  b.classList.remove('pulse'); void b.offsetWidth; b.classList.add('pulse');
}

/* ---------- 播放（辅助，到检查点自停） ---------- */
var rafId = null;
function playLoop() {
  if (!state.playing) return;
  var t = state.cursor + 0.0022;
  var stop = state.cursor < TC ? TC : 1;
  if (t >= stop) {
    if (stop === TC) { setCursor(TC); } else { setCursor(1); }
    pausePlay(); return;
  }
  setCursor(t);
  rafId = requestAnimationFrame(playLoop);
}
function startPlay() {
  if (Math.abs(state.cursor - TC) < 1e-4 && state.phase === 'before') { pulseCompare(); return; }
  state.playing = true; $('btnPlay').textContent = '⏸ 暂停';
  rafId = requestAnimationFrame(playLoop);
}
function pausePlay() {
  state.playing = false; $('btnPlay').textContent = '▶ 播放（辅助，到下一检查点自停）';
  if (rafId) cancelAnimationFrame(rafId);
}
document.addEventListener('visibilitychange', function () {
  if (document.hidden && state.playing) pausePlay();
});

/* ---------- 逐状态证据（只显示当前有效内容） ---------- */
function taskText() {
  switch (region()) {
    case 'S1':
      return '<b>S1 · 外壳离桌上升：</b>只有外壳上升，内芯静止在桌面（原题给定）。' +
        '拖动过程位置或单步，观察外壳挡点与内芯接触面之间的间距连续减小到 0。' +
        (Math.abs(state.cursor) < 1e-4 ? ' 当前 y=0，外壳从静止释放。' : '');
    case 'X1b':
      return '<b>X1 碰前瞬间（y=h₁，间距=0）：</b>外壳 4m 速度记为 u↑，内芯 m 速度为 0。' +
        '先口头判断：碰后共同速度 v 与 u 谁大？再由老师点「比较碰前/碰后」。';
    case 'X1a':
      return '<b>X1 碰后瞬间（同一位置 y=h₁，几何未动）：</b>两部分锁定为共同整体 5m，以共同速度 v↑ 运动。';
    default:
      if (state.cursor > 1 - 1e-4) {
        return '<b>最高点（y=h₂）：</b>共同速度降为 0。本段有效关系：<span class="eqInline">' + M.s2eq + '</span>';
      }
      return '<b>S2 · 共同上升：</b>内芯与外壳相对位置固定、始终同速；共同速度从 v 连续降为 0；' +
        '本段上升的高度差是 h₂−h₁（起点在 h₁）；碰撞损失在本段保持常量，不再增加。' +
        '本段有效关系：<span class="eqInline">' + M.s2eq + '</span>';
  }
}

/* X1 动量证据：系统固定为“外壳+内芯”，与能量口径切换无关 */
function x1EvidenceHtml() {
  if (Math.abs(state.cursor - TC) > 1e-4) return '';
  if (state.phase === 'before') {
    return '<div class="cardTitle">碰撞前状态（预测用）</div>' +
      '<ul><li>外壳 4m：速度 u↑　｜　内芯 m：速度 0</li>' +
      '<li>碰撞损失：0（尚未发生碰撞）</li></ul>' +
      '<p class="note">口头预测 v 与 u 的关系后，由上方「比较碰前/碰后 ▶」主动作继续（同一位置，只切换速度与身份）。</p>';
  }
  return '<div class="cardTitle">碰撞证据（碰后，同一位置）</div>' +
    '<ul><li>共同整体 5m：速度 v↑　｜　几何位置与碰前完全相同</li></ul>' +
    '<div class="sysTag">碰撞系统：外壳 + 内芯（碰撞期间重力冲量可忽略；与下方能量口径无关）</div>' +
    '<div class="eq">碰前动量 − 碰后动量：<span class="eqInline">' + M.momLong + '</span>（前后相等）</div>' +
    '<div class="eq">所以 <span class="eqInline">' + M.vOfU + '</span>，即 <span class="eqInline">' + M.uOfV + '</span></div>' +
    '<ul><li>机械能减少量 = 内能增加量（等量，只在这次碰撞发生一次）</li></ul>';
}

/* 能量口径账本：只在老师进入“能量口径比较”后出现 */
function energyBoxHtml() {
  if (!state.energyMode) {
    return '<p class="note">进入后可在同一物理状态切换研究对象（两种都包含地球），观察边界、作用分类与能量账本的同步变化；退出后回到原状态，不改变物理过程。</p>' +
      '<button id="btnEnergyOn" type="button">进入能量口径比较</button>';
  }
  var r = region();
  var bShell = state.boundary === 'shell';
  var chips = '<div class="chips">' +
    '<button class="chip' + (bShell ? ' active' : '') + '" data-b="shell" type="button">外壳+地球</button>' +
    '<button class="chip' + (bShell ? '' : ' active') + '" data-b="pen" type="button">整支笔+地球</button></div>';
  var items, eqs = '';
  if (bShell) {
    if (r === 'S1') {
      items = ['边界内：外壳 4m 与地球；内芯和弹簧在系统外',
        '弹簧作用跨边界：对系统输入外部功 W<sub>s</sub>',
        '外壳重力势能 4mgy 随高度增加；外壳动能从 0 增加'];
      eqs = '<div class="eq">S1 段：<span class="eqInline">' + M.wsShellGen + '</span></div>';
    } else if (r === 'X1b') {
      items = ['边界内：外壳 4m 与地球；内芯和弹簧在系统外',
        '碰前瞬间：外壳动能与重力势能取 S1 末态值'];
      eqs = '<div class="eq">S1 起末两态：<span class="eqInline">' + M.wsShell + '</span></div>';
    } else {
      items = ['碰后内芯对外壳的接触作用属于跨边界交换',
        '本口径不用于 S2 整段方程：请回到 S1/X1 状态使用，或切换「整支笔+地球」'];
    }
    return chips + '<div class="cardTitle">能量账本 · 外壳+地球</div><ul><li>' + items.join('</li><li>') + '</li></ul>' + eqs +
      '<button id="btnEnergyOff" type="button">退出比较（返回原状态）</button>';
  }
  // 整支笔+地球
  if (r === 'S1') {
    items = ['边界内：弹簧、内芯 m、外壳 4m 与地球',
      '弹簧能是系统内部通道（内部转换，不是外部输入，也不是损失）',
      '内能：0　｜　碰撞损失：0'];
  } else if (r === 'X1b') {
    items = ['边界内：弹簧、内芯 m、外壳 4m 与地球；弹簧能为内部通道',
      '内能：0　｜　碰撞损失：0（尚未碰撞）'];
  } else if (r === 'X1a') {
    items = ['碰后共同 5m 的机械能进入本账本',
      '机械能减少量 = 内能增加量（等量，只在碰撞处发生一次）',
      '碰撞损失：已发生，此后保持常量'];
    eqs = '<div class="eq eqLose">碰撞处：机械能 ↓ ＝ 内能 ↑（总能量不消失）</div>';
  } else {
    items = ['机械能守恒：共同动能转化为重力势能',
      '碰撞损失：保持常量，不随高度继续累计',
      '弹簧：碰后长度不变，不再起通道作用'];
    if (state.cursor > 1 - 1e-4) eqs = '<div class="eq"><span class="eqInline">' + M.s2eq + '</span></div>';
  }
  return chips + '<div class="cardTitle">能量账本 · 整支笔+地球</div><ul><li>' + items.join('</li><li>') + '</li></ul>' + eqs +
    '<button id="btnEnergyOff" type="button">退出比较（返回原状态）</button>';
}

function actionsHtml() {
  var html = '';
  if (state.cursor > TC + 1e-4) {
    html += '<button id="btnS2Mark" type="button">' +
      (state.s2mark ? '取消位移指认' : '指认本段位移：高亮起点 h₁ 与高度差 h₂−h₁') + '</button> ';
    html += '<button id="btnRevealV" type="button">' +
      (state.reveal.v ? '隐藏' : '教师揭示') + '：第(1)问共同速度</button>';
    if (state.reveal.v) {
      html += '<div class="answer shown"><b>第(1)问：</b>由 <span class="eqInline">' + M.s2eq + '</span> 得 <span class="eqInline">' + M.vRoot + '</span>。</div>';
    }
  }
  return html;
}

/* ---------- 渲染汇总 ---------- */
function renderAll() {
  renderModel();
  var cp = cpIndex();
  $('cpName').textContent = cp === 2.5 ? '③→④ 共同上升途中' : CP_NAMES[cp];
  var atX1b = Math.abs(state.cursor - TC) < 1e-4 && state.phase === 'before';
  var atTop = state.cursor > 1 - 1e-4;
  $('btnNextCp').textContent = atX1b ? '比较碰前/碰后 ▶' : (atTop ? '进入纸笔整理 →' : '下一检查点 ▶');
  $('btnNextCp').classList.toggle('compareBtn', atX1b);
  $('btnPrevCp').disabled = state.cursor < 1e-4;   // 起点无上一检查点，端点按钮名实相符
  $('btnReplay').disabled = state.cursor < 1e-4 && state.phase === 'before';
  $('taskLine').innerHTML = taskText() + '<div id="ctxActions" style="margin-top:8px">' + actionsHtml() + '</div>';
  var x1 = $('x1Evidence');
  var x1html = x1EvidenceHtml();
  x1.hidden = !x1html;
  x1.innerHTML = x1html;
  $('energyBox').innerHTML = energyBoxHtml();
  bindDynamic();
  applyHighlight();
  if (state.view === 'paper') renderPaper();
}

function bindDynamic() {
  var bm = $('btnS2Mark');
  if (bm) bm.addEventListener('click', function () {
    state.s2mark = !state.s2mark;
    if (state.s2mark) pulseMarker('h1');
    renderAll();
  });
  var rv = $('btnRevealV');
  if (rv) rv.addEventListener('click', function () { state.reveal.v = !state.reveal.v; renderAll(); });
  var eon = $('btnEnergyOn');
  if (eon) eon.addEventListener('click', function () {
    // 进入支线前保存同一物理状态与过程位置
    energySnapshot = { cursor: state.cursor, phase: state.phase, s2mark: state.s2mark };
    state.energyMode = true; renderAll();
  });
  var eoff = $('btnEnergyOff');
  if (eoff) eoff.addEventListener('click', function () {
    state.energyMode = false;
    // 退出支线：精确恢复进入前的物理状态、碰前/碰后相位与过程游标
    if (energySnapshot) {
      state.cursor = energySnapshot.cursor;
      state.phase = energySnapshot.phase;
      state.s2mark = energySnapshot.s2mark;
      $('cursor').value = Math.round(state.cursor * 1000);
      energySnapshot = null;
    }
    renderAll();
  });
  document.querySelectorAll('#energyBox .chip[data-b]').forEach(function (c) {
    c.addEventListener('click', function () { state.boundary = c.dataset.b; renderAll(); });
  });
}

/* ---------- 高亮（题图/来源 ↔ 模型双向） ---------- */
var HL_SVG = {
  shell: ['gShell'], core: ['gCore'], spring: ['spring', 'springTag'], yref: ['gYRef'],
  desk: ['deskLine'], h1: ['mkH1line', 'mkH1text'], h2: ['mkH2line', 'mkH2text'],
  u: ['gArrow', 'mkH1line', 'mkH1text'], v: ['gArrow', 'mkH1line', 'mkH1text'],
  ws: ['spring', 'springTag'], eloss: ['gFlash', 'mkH1line', 'mkH1text']
};
function applyHighlight() {
  var h = state.highlight;
  // 先统一清除所有可高亮目标，再只添加当前项，避免共享目标被后续 key 覆盖
  var all = [];
  Object.keys(HL_SVG).forEach(function (k) {
    HL_SVG[k].forEach(function (id) { if (all.indexOf(id) < 0) all.push(id); });
  });
  all.forEach(function (id) {
    var el = $(id);
    if (el) el.classList.remove('svg-hl');
  });
  if (h && HL_SVG[h]) {
    HL_SVG[h].forEach(function (id) {
      var el = $(id);
      if (el) el.classList.add('svg-hl');
    });
  }
  document.querySelectorAll('.chip[data-obj]').forEach(function (c) {
    c.classList.toggle('active', c.dataset.obj === h);
  });
  document.querySelectorAll('.hl-box').forEach(function (b) {
    b.classList.toggle('on', b.dataset.obj === h);
  });
  // u/v 的稳定可见 referent：X1 高度标记高亮 + 仅映射态短标签（不含任何速度关系）
  var tag = $('uvTag');
  if (h === 'u' || h === 'v') {
    tag.textContent = h === 'u' ? 'u：碰前外壳速度' : 'v：碰后共同速度';
    tag.setAttribute('visibility', 'visible');
  } else {
    tag.setAttribute('visibility', 'hidden');
  }
}
function pulseMarker(which) {
  (HL_SVG[which] || []).forEach(function (id) {
    var el = $(id);
    if (el) { el.classList.remove('pulse'); void el.getBoundingClientRect(); el.classList.add('pulse'); }
  });
}

/* ---------- 纸笔整理视图（纯静态） ---------- */
function renderPaper() {
  var pv = $('paperView');
  var seg = '<h2>纸笔整理（考场顺序）</h2>' +
    '<h3>最少分段</h3>' +
    '<p><code>S1：0→h₁（外壳+地球；内芯静止）　/　X1：同位 碰前→碰后（碰撞系统：外壳+内芯）　/　S2：h₁→h₂（整支笔+地球）</code></p>';
  var chain = '<details class="srcChain"><summary>关键量来源链（题面给定 / 过程定义 / 题目待求，按需展开）</summary>' +
    '<table class="cmp"><tr><th>量</th><th>类别</th><th>来源</th><th>去向（方程）</th></tr>' +
    '<tr><td>m / 4m</td><td>题面给定</td><td>题干「内芯和外壳质量分别为 m 和 4m」</td><td>各方程的质量</td></tr>' +
    '<tr><td>g</td><td>题面给定</td><td>题干</td><td>重力势能、第(1)(3)问结果</td></tr>' +
    '<tr><td>y=0</td><td>题面给定</td><td>桌面（图 a–c 虚线）</td><td>S1 起点</td></tr>' +
    '<tr><td>h₁</td><td>题面给定</td><td>图 b</td><td>X1 同一位置；S1 末 / S2 初</td></tr>' +
    '<tr><td>h₂</td><td>题面给定</td><td>图 c</td><td>S2 末态</td></tr>' +
    '<tr><td>u</td><td>过程定义</td><td>X1 碰前外壳速度（模型 h₁ 处箭头）</td><td>碰撞式与 S1 功能式</td></tr>' +
    '<tr><td>v</td><td>过程定义</td><td>X1 碰后共同速度（模型 h₁ 处箭头）</td><td>S2 能量式、第(1)问</td></tr>' +
    '<tr><td>W<sub>s</sub></td><td>题目待求 (2)</td><td>题干求(2)（弹簧对外壳做功）</td><td>S1 功能式（外壳+地球口径）</td></tr>' +
    '<tr><td>E<sub>损</sub></td><td>题目待求 (3)</td><td>题干求(3)（笔损失的机械能）</td><td>X1 动能差（整支笔+地球口径）</td></tr></table></details>';
  if (!state.compared) {
    pv.innerHTML = seg +
      '<p class="gateNote">方程整理需要先完成碰撞观察：请回到「动态证据」，在 X1 碰前由老师点击「比较碰前/碰后」。</p>' +
      chain;
    return;
  }
  pv.innerHTML = seg +
    '<h3>方程（按考场顺序）</h3>' +
    paperRow('S2 → 求 v', M.s2eq, 'v', '第(1)问：' + M.vRoot) +
    paperRow('X1 → 求 u', M.mom, 'u', M.uOfV) +
    paperRow('S1 → 求 Ws', M.wsShell, 'ws', '第(2)问：' + M.wsFinal) +
    paperRow('X1 → 求 E损', M.elossDef, 'el', '第(3)问：' + M.elossFinal + '（恰为碰前外壳动能的 1/5）') +
    ((state.reveal.v && state.reveal.u && state.reveal.ws && state.reveal.el) ?
      '<p class="note">自检：<span class="eqInline">' + M.selfCheck + '</span> ✓</p>' : '') +
    chain;
  pv.querySelectorAll('button[data-rev]').forEach(function (b) {
    b.addEventListener('click', function () {
      state.reveal[b.dataset.rev] = !state.reveal[b.dataset.rev];
      renderPaper();
    });
  });
}
function paperRow(seg, eq, key, ans) {
  return '<table class="cmp"><tr><th style="width:120px">' + seg + '</th>' +
    '<td><div class="eq" style="margin:0"><span class="eqInline">' + eq + '</span></div></td>' +
    '<td style="width:210px"><button data-rev="' + key + '" type="button">' +
    (state.reveal[key] ? '隐藏结果' : '教师揭示结果') + '</button>' +
    '<div class="answer' + (state.reveal[key] ? ' shown' : '') + '"><b><span class="eqInline">' + ans + '</span></b></div></td></tr></table>';
}

/* ---------- 视图切换 ---------- */
function setView(v) {
  state.view = v;
  pausePlay();
  $('dynView').hidden = v !== 'dynamic';
  $('paperView').hidden = v !== 'paper';
  $('btnView').textContent = v === 'dynamic' ? '切换到纸笔整理' : '返回动态证据';
  if (v === 'paper') renderPaper(); else renderAll();   // 返回动态证据时恢复进入前状态
}

/* ---------- 绑定 ---------- */
$('cursor').addEventListener('input', function () {
  pausePlay(); setCursor($('cursor').value / 1000, true);
});
$('btnPrevCp').addEventListener('click', function () { pausePlay(); prevCp(); });
$('btnNextCp').addEventListener('click', function () { pausePlay(); nextCp(); });
$('btnPlay').addEventListener('click', function () { state.playing ? pausePlay() : startPlay(); });
$('btnReplay').addEventListener('click', function () {
  pausePlay();
  state.cursor = 0; state.phase = 'before'; state.s2mark = false;
  $('cursor').value = 0;
  renderAll();
});
$('btnView').addEventListener('click', function () {
  setView(state.view === 'dynamic' ? 'paper' : 'dynamic');
});
$('btnReset').addEventListener('click', function () {
  pausePlay();
  state.cursor = 0; state.phase = 'before'; state.compared = false;
  state.energyMode = false; state.boundary = 'shell'; state.s2mark = false; state.highlight = null;
  state.reveal = { v: false, u: false, ws: false, el: false };
  energySnapshot = null;
  $('cursor').value = 0;
  setView('dynamic');
  renderAll();
});
document.querySelectorAll('.chip[data-obj]').forEach(function (c) {
  c.addEventListener('click', function () {
    state.highlight = (state.highlight === c.dataset.obj) ? null : c.dataset.obj;
    applyHighlight();
  });
});

/* ---------- 初始化 ---------- */
(function init() {
  var hatch = '';
  for (var x = 48; x <= 340; x += 16) {
    hatch += '<line x1="' + x + '" y1="392" x2="' + (x - 8) + '" y2="402" class="deskHatch"/>';
  }
  $('deskHatch').innerHTML = hatch;
  renderAll();
})();
