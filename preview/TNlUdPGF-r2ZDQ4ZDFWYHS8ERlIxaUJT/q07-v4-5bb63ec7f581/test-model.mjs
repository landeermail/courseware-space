/**
 * q07-glass-rod-tir A0 模型确定性断言。
 * 运行：node trial/private/courseware/q07-glass-rod-tir/test-model.mjs
 * 覆盖：θ=0°/29°/30°/35° 全状态；Snell 正反算往返一致；α 与 C 分类；
 * x_1、x_6、x_7 数值；严格 x_k<40 边界；右端出射；无效输入与钳制。
 */

import {
  ROD,
  CRITICAL_DEG,
  TIR_LIMIT_DEG,
  classify,
  computeFromIncidence,
  computeFromTheta,
  feasibility,
  incidenceForTheta,
  reflectionX,
  thetaForIncidence,
} from './model.js';

let passed = 0;
let failed = 0;

function ok(condition, label) {
  if (condition) {
    passed += 1;
    console.log(`PASS ${label}`);
  } else {
    failed += 1;
    console.error(`FAIL ${label}`);
  }
}

function near(actual, expected, tol, label) {
  const diff = Math.abs(actual - expected);
  ok(
    Number.isFinite(actual) && diff <= tol,
    `${label}（实际 ${actual}，期望 ${expected}±${tol}）`,
  );
}

function throws(fn, ErrorType, label) {
  try {
    fn();
    failed += 1;
    console.error(`FAIL ${label}（未抛出 ${ErrorType.name}）`);
  } catch (error) {
    ok(error instanceof ErrorType, `${label}（抛出 ${error.constructor.name}）`);
  }
}

// ---------- 常量 ----------
near(ROD.n, 2 / Math.sqrt(3), 1e-15, '折射率 n = 2/√3');
near(CRITICAL_DEG, 60, 1e-12, '临界角 C = 60°');
near(TIR_LIMIT_DEG, 30, 1e-12, '全反射上限 θ<30°');

// ---------- Snell 正算（自由输入 i → θ） ----------
near(thetaForIncidence(0), 0, 1e-12, 'i=0° → θ=0°');
near(
  thetaForIncidence(90),
  Math.asin(1 / ROD.n) / (Math.PI / 180),
  1e-9,
  'i=90° → θ=asin(1/n)=60°',
);
near(thetaForIncidence(34.04), 29, 1e-2, 'i≈34.04° → θ≈29°（锚点）');

// ---------- Snell 反算（预设 θ → i），不伪造管内方向 ----------
near(incidenceForTheta(0), 0, 1e-12, '预设 θ=0° → i=0°');
near(incidenceForTheta(29), 34.04, 1e-2, '预设 θ=29° → i≈34.04°（锚点）');
near(
  incidenceForTheta(30),
  Math.asin(1 / Math.sqrt(3)) / (Math.PI / 180),
  1e-9,
  '预设 θ=30° → i=asin(1/√3)≈35.26°',
);
near(incidenceForTheta(35), 41.48, 1e-2, '预设 θ=35° → i≈41.48°');

// 往返一致：i → θ → i、θ → i → θ
for (const i of [0, 5, 20, 34.04, 60, 89.9]) {
  near(
    incidenceForTheta(thetaForIncidence(i)),
    i,
    1e-9,
    `往返一致 i=${i}° → θ → i`,
  );
}
for (const theta of [0, 10, 20, 29, 30, 35, 59]) {
  near(
    thetaForIncidence(incidenceForTheta(theta)),
    theta,
    1e-9,
    `往返一致 θ=${theta}° → i → θ`,
  );
}

// ---------- α 与 C 分类 ----------
near(computeFromTheta(29).alphaDeg, 61, 1e-9, 'θ=29° → α=61°（>C=60°）');
ok(classify(29) === 'tir', 'θ=29° 分类 tir');
ok(classify(0) === 'tir', 'θ=0° 分类 tir');
ok(classify(30) === 'critical', 'θ=30° 分类 critical（不标全反射）');
ok(classify(35) === 'escape', 'θ=35° 分类 escape');
ok(classify(30 - 1e-7) === 'critical', 'θ=30°−ε 容差内仍判 critical');
ok(classify(29.99999) === 'tir', 'θ 略小于 30° 判 tir');
ok(classify(30.00001) === 'escape', 'θ 略大于 30° 判 escape');

// ---------- x_k 数值锚点（θ=29°） ----------
const anchors = [3.61, 10.82, 18.04, 25.26, 32.47, 39.69];
anchors.forEach((expected, index) => {
  near(reflectionX(index + 1, 29), expected, 5e-3, `θ=29° x_${index + 1}≈${expected}`);
});
near(reflectionX(7, 29), 46.91, 5e-3, 'θ=29° x_7≈46.91（超出管长）');

// ---------- 状态：θ=0° ----------
{
  const s = computeFromTheta(0);
  ok(s.classification === 'tir', 'θ=0° 状态分类 tir');
  ok(s.count === 0 && s.reflections.length === 0, 'θ=0° 0 次反射');
  ok(s.exit && s.exit.x === ROD.L && Math.abs(s.exit.y - 2) < 1e-12, 'θ=0° 从右端中心出射');
  near(s.path[1].y, 2, 1e-12, 'θ=0° 光路沿中线 y=2');
}

// ---------- 状态：θ=29°（6 次反射 + 右端出射） ----------
{
  const s = computeFromTheta(29);
  ok(s.classification === 'tir', 'θ=29° 状态分类 tir');
  ok(s.count === 6, 'θ=29° 计数为 6');
  near(s.reflections[0].x, 3.61, 5e-3, 'θ=29° 第 1 反射点 x≈3.61');
  near(s.reflections[5].x, 39.69, 5e-3, 'θ=29° 第 6 反射点 x≈39.69');
  ok(s.reflections.every((r) => r.x < ROD.L), 'θ=29° 全部反射点严格在管内');
  ok(s.reflections[0].wall === 'top' && s.reflections[1].wall === 'bottom', '反射点上下交替');
  ok(s.exit && s.exit.x === ROD.L, 'θ=29° 右端出射');
  near(s.exit.angleDeg, s.iDeg, 1e-9, '右端出射角等于空气入射角 i');
  ok(s.exit.y >= 0 && s.exit.y <= ROD.h, '右端出射点在管宽范围内');
  ok(s.path.length === 2 + 6, 'θ=29° 光路折线 = 入口 + 6 反射点 + 出口');
}

// ---------- 状态：θ=30°（临界，沿界面折射，不计全反射） ----------
{
  const s = computeFromTheta(30);
  ok(s.classification === 'critical', 'θ=30° 状态分类 critical');
  ok(s.count === 0 && s.reflections.length === 0, 'θ=30° 不计全反射反射');
  ok(s.critical && Math.abs(s.critical.y - ROD.h) < 1e-9, 'θ=30° 临界折射沿上界面');
  near(s.critical.x, 2 * Math.sqrt(3), 1e-9, 'θ=30° 首次侧壁命中 x=2√3≈3.46');
  const last = s.path[s.path.length - 1];
  ok(last.x === ROD.L && Math.abs(last.y - ROD.h) < 1e-9, 'θ=30° 沿界面到达右端上棱');
}

// ---------- 状态：θ=35°（首次侧壁折射出管，主光路终止） ----------
{
  const s = computeFromTheta(35);
  ok(s.classification === 'escape', 'θ=35° 状态分类 escape');
  ok(s.count === 0 && s.reflections.length === 0, 'θ=35° 主计数光路终止，计数 0');
  near(s.escape.x, 2 / Math.tan((35 * Math.PI) / 180), 1e-9, 'θ=35° 逃逸点 x=x_1≈2.86');
  ok(
    s.escape.refractionFromNormalDeg > 0 && s.escape.refractionFromNormalDeg < 90,
    'θ=35° 折射出管角度有效',
  );
  ok(s.path[s.path.length - 1].x === s.escape.x, 'θ=35° 光路在逃逸点终止');
}

// ---------- 严格 x_k < 40 的边界行为 ----------
{
  // 构造 x_1 恰等于 40：tanθ = 2/40 = 0.05。
  const thetaEdge = Math.atan(0.05) / (Math.PI / 180);
  const s = computeFromTheta(thetaEdge);
  ok(s.count === 0, 'x_1=40 恰在棱边：不计反射（严格小于）');
  ok(s.edgeHit && s.edgeHit.k === 1, 'x_1=40 记录为管端棱边命中');
  ok(s.exit && s.exit.x === ROD.L && Math.abs(s.exit.y - ROD.h) < 1e-9, 'x_1=40 在右上棱边离管');

  // x_1 略小于 40：计 1 次反射。
  const thetaIn = thetaEdge + 0.01;
  const sIn = computeFromTheta(thetaIn);
  ok(sIn.count === 1, 'x_1 略小于 40：计 1 次反射');
  ok(sIn.exit && sIn.exit.x === ROD.L, 'x_1 略小于 40：随后右端出射');

  // x_1 略大于 40：0 次反射，直接右端出射。
  const thetaOut = thetaEdge - 0.01;
  const sOut = computeFromTheta(thetaOut);
  ok(sOut.count === 0, 'x_1 略大于 40：0 次反射');
  ok(sOut.exit && sOut.exit.x === ROD.L, 'x_1 略大于 40：右端出射');
  near(sOut.exit.y, ROD.h, 0.2, 'x_1 略大于 40：出射点接近上棱边');

  // 第 6 次恰在棱边：tanθ = 22/40 = 0.55 → x_6=40 不计，x_5≈32.7 计入。
  const theta6Edge = Math.atan(0.55) / (Math.PI / 180);
  const s6 = computeFromTheta(theta6Edge);
  ok(s6.count === 5, 'x_6=40 恰在棱边：只计 5 次（端点棱边不计）');
  ok(s6.edgeHit && s6.edgeHit.k === 6, 'x_6=40 记录第 6 次为棱边命中');
}

// ---------- 第 6/7 次可行性阈值 ----------
{
  const f = feasibility();
  near(f.sixMinDeg, 28.81, 1e-2, '第 6 次要求 θ>arctan(0.55)≈28.81°');
  near(f.sevenMinDeg, 33.02, 1e-2, '第 7 次要求 θ>arctan(0.65)≈33.02°');
  ok(f.sixMinDeg < f.tirLimitDeg, '第 6 次区间 (28.81°,30°) 非空：可行');
  ok(f.sevenMinDeg > f.tirLimitDeg, '第 7 次要求与全反射冲突：不可行');
  // 开区间中点真实可实现 6 次。
  const mid = (f.sixMinDeg + f.tirLimitDeg) / 2;
  const sMid = computeFromTheta(mid);
  ok(sMid.classification === 'tir' && sMid.count === 6, '开区间中点 θ≈29.4° 真实实现 6 次');
  // 区间下端之外（θ 略小于 28.81°）只有 5 次。
  const sBelow = computeFromTheta(f.sixMinDeg - 0.1);
  ok(sBelow.count === 5, 'θ 略低于阈值时只有 5 次');
}

// ---------- 无效输入与边界钳制 ----------
throws(() => computeFromIncidence(NaN), TypeError, 'i=NaN 抛 TypeError');
throws(() => computeFromIncidence(Infinity), TypeError, 'i=Infinity 抛 TypeError');
throws(() => computeFromIncidence('30'), TypeError, 'i 为字符串抛 TypeError');
throws(() => thetaForIncidence(NaN), TypeError, 'thetaForIncidence(NaN) 抛 TypeError');
throws(() => incidenceForTheta(-1), RangeError, '预设 θ<0 抛 RangeError');
throws(() => incidenceForTheta(90), RangeError, '预设 θ=90° 抛 RangeError');
throws(() => incidenceForTheta(61), RangeError, '预设 θ=61° 不可实现（sin i>1）抛 RangeError');
throws(() => reflectionX(0, 29), RangeError, 'k=0 抛 RangeError');
throws(() => reflectionX(1.5, 29), RangeError, 'k 非整数抛 RangeError');

{
  const s = computeFromIncidence(-5);
  ok(s.input.clamped && s.iDeg === 0, 'i=−5° 钳制到 0° 并标记 clamped');
  ok(s.count === 0 && s.exit, '钳制后 θ=0° 正常出射');
}
{
  const s = computeFromIncidence(120);
  ok(s.input.clamped && s.iDeg === 90, 'i=120° 钳制到 90° 并标记 clamped');
  near(s.thetaDeg, 60, 1e-9, '钳制到 i=90° 后 θ=60°');
  ok(s.classification === 'escape', 'i=90°（θ=60°）分类 escape');
}

console.log(`\n共 ${passed + failed} 条断言：${passed} 通过，${failed} 失败`);
if (failed > 0) {
  process.exitCode = 1;
}
