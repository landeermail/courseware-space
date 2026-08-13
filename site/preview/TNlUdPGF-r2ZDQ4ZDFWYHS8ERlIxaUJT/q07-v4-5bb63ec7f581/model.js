/**
 * q07-glass-rod-tir 物理真值模型（唯一状态源）。
 *
 * 几何：二维纵截面，玻璃管长 L=40 cm（x∈[0,L]）、宽 h=4 cm（y∈[0,h]），
 * 光从左端正中心 (0, h/2) 由空气射入，y 轴向上，内部方向先朝右上。
 * 折射率：空气 1，玻璃 n=2/√3；临界角 C 满足 sin C = 1/n，C=60°。
 *
 * 角度定义：
 *   i —— 空气入射角（相对左端面水平法线），自由输入范围 [0°,90°]；
 *   θ —— 管内光线与管轴（水平）夹角，由 Snell 关系 sin i = n·sin θ 决定；
 *   α —— 侧壁（上下表面）入射角（相对竖直法线），α = 90°−θ。
 *
 * 分类：严格全反射 ⟺ α > C ⟺ θ < 30°；θ = 30° 为临界（沿界面折射，
 * 不是全反射）；θ > 30° 在首次侧壁处折射出管，主计数光路终止。
 *
 * 反射计数：第 k 次侧壁命中横坐标 x_k = (4k−2)/tanθ（首段竖直位移 2 cm，
 * 后续每段 4 cm），只有严格 x_k < L 才计为管内反射；管端棱边不计。
 * 右端面入射角 θ < 30° < C，全反射状态下总能从右端出射，出射角等于 i。
 */

export const ROD = Object.freeze({
  L: 40,
  h: 4,
  n: 2 / Math.sqrt(3),
  nAir: 1,
});

export const CRITICAL_DEG = 60; // C，sin C = 1/n = √3/2
export const TIR_LIMIT_DEG = 90 - CRITICAL_DEG; // 严格全反射要求 θ < 30°

const DEG = Math.PI / 180;
const ANGLE_TOL_DEG = 1e-6; // 角度分类容差（度）
const X_TOL_CM = 1e-9; // 反射点是否严格在管内的容差（cm）

function assertFinite(name, value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new TypeError(`${name} 必须是有限数值，收到 ${String(value)}`);
  }
}

/** 正算：由空气入射角 i（度）求管内轴向角 θ（度），θ = asin(sin i / n)。 */
export function thetaForIncidence(iDeg) {
  assertFinite('入射角 i', iDeg);
  const theta = Math.asin(Math.min(1, Math.sin(iDeg * DEG)) / ROD.n) / DEG;
  return theta;
}

/**
 * 反算：由管内轴向角 θ（度）求所需空气入射角 i（度），i = asin(n·sin θ)。
 * θ 必须落在 [0°,90°)；当 n·sin θ > 1（θ > 60°）时该管内方向无法由真实
 * 空气入射产生，抛 RangeError，绝不伪造管内方向。
 */
export function incidenceForTheta(thetaDeg) {
  assertFinite('管内角 θ', thetaDeg);
  if (thetaDeg < 0 || thetaDeg >= 90) {
    throw new RangeError(`管内角 θ 必须在 [0°,90°) 内，收到 ${thetaDeg}`);
  }
  const sinI = ROD.n * Math.sin(thetaDeg * DEG);
  if (sinI > 1 + 1e-12) {
    throw new RangeError(
      `θ=${thetaDeg}° 无法由空气入射实现（需要 sin i=${sinI} > 1）`,
    );
  }
  return Math.asin(Math.min(1, sinI)) / DEG;
}

/** 第 k 次侧壁命中的横坐标（cm）：x_k = (4k−2)/tanθ。θ=0° 时为 Infinity。 */
export function reflectionX(k, thetaDeg) {
  assertFinite('反射序号 k', k);
  assertFinite('管内角 θ', thetaDeg);
  if (!Number.isInteger(k) || k < 1) {
    throw new RangeError(`反射序号 k 必须是正整数，收到 ${k}`);
  }
  if (thetaDeg <= 0) return Infinity;
  if (thetaDeg >= 90) return 0;
  return (4 * k - 2) / Math.tan(thetaDeg * DEG);
}

/** TIR 分类：'tir'（θ<30°）| 'critical'（θ=30°）| 'escape'（θ>30°）。 */
export function classify(thetaDeg) {
  assertFinite('管内角 θ', thetaDeg);
  if (thetaDeg < TIR_LIMIT_DEG - ANGLE_TOL_DEG) return 'tir';
  if (thetaDeg > TIR_LIMIT_DEG + ANGLE_TOL_DEG) return 'escape';
  return 'critical';
}

/**
 * 第 6 / 7 次反射的可行性阈值（度）：
 * x_6 < 40 ⟺ tanθ > 22/40 = 0.55；x_7 < 40 ⟺ tanθ > 26/40 = 0.65。
 */
export function feasibility() {
  return {
    sixMinDeg: Math.atan(22 / ROD.L) / DEG, // ≈28.81°
    sevenMinDeg: Math.atan(26 / ROD.L) / DEG, // ≈33.02°
    tirLimitDeg: TIR_LIMIT_DEG, // 30°
  };
}

/** 把展开坐标 y（cm，可超出 [0,h]）折回管内，返回 { y, goingUp }。 */
function foldY(yUnfolded) {
  const period = 2 * ROD.h;
  let m = yUnfolded % period;
  if (m < 0) m += period;
  if (m <= ROD.h) return { y: m, goingUp: true };
  return { y: period - m, goingUp: false };
}

/**
 * 由空气入射角 i（度）计算完整光路状态。
 * 超出 [0°,90°] 的有限输入被钳制到边界并置 input.clamped=true。
 */
export function computeFromIncidence(iDeg) {
  assertFinite('入射角 i', iDeg);
  const clamped = iDeg < 0 || iDeg > 90;
  const i = Math.min(90, Math.max(0, iDeg));
  const thetaDeg = thetaForIncidence(i);
  const alphaDeg = 90 - thetaDeg;
  const classification = classify(thetaDeg);

  const state = {
    input: { iDeg: i, requestedIDeg: iDeg, clamped },
    iDeg: i,
    thetaDeg,
    alphaDeg,
    criticalDeg: CRITICAL_DEG,
    classification,
    reflections: [], // [{k, x, wall:'top'|'bottom'}]，仅严格 x_k < L
    count: 0,
    firstHit: null, // 首次侧壁命中（若 x_1 < L），逃逸/临界时也在此终止主光路
    path: [], // 主光路折线 [{x, y}]，cm，y 向上
    exit: null, // 右端出射 {x, y, angleDeg, goingUp}
    escape: null, // 逃逸 {x, y, wall, refractionFromNormalDeg}
    critical: null, // 临界 {x, y, wall}（此后沿界面到右端）
    edgeHit: null, // 反射点恰落在管端棱边 {k, x, y}（不计数）
  };

  const y0 = ROD.h / 2;
  state.path.push({ x: 0, y: y0 });

  if (thetaDeg <= 0) {
    // θ=0°：沿中线直行，0 次反射，右端出射。
    state.path.push({ x: ROD.L, y: y0 });
    state.exit = { x: ROD.L, y: y0, angleDeg: i, goingUp: true };
    return state;
  }

  const tanTheta = Math.tan(thetaDeg * DEG);

  // 依次收集严格位于管内的侧壁命中点。
  const hits = [];
  let edgeHit = null;
  for (let k = 1; ; k += 1) {
    const x = reflectionX(k, thetaDeg);
    if (x < ROD.L - X_TOL_CM) {
      hits.push({ k, x, wall: k % 2 === 1 ? 'top' : 'bottom' });
    } else if (Math.abs(x - ROD.L) <= X_TOL_CM) {
      edgeHit = { k, x: ROD.L, y: k % 2 === 1 ? ROD.h : 0 };
      break;
    } else {
      break;
    }
  }

  const firstHit = hits.length > 0 ? hits[0] : null;
  state.firstHit = firstHit;
  state.edgeHit = edgeHit;

  if (classification === 'escape') {
    // θ>30°：主计数光路在首次侧壁处折射出管（若首次命中在管内）。
    if (firstHit) {
      const y = firstHit.wall === 'top' ? ROD.h : 0;
      state.path.push({ x: firstHit.x, y });
      const sinBeta = ROD.n * Math.sin(alphaDeg * DEG); // 玻璃→空气
      state.escape = {
        x: firstHit.x,
        y,
        wall: firstHit.wall,
        refractionFromNormalDeg: Math.asin(Math.min(1, sinBeta)) / DEG,
      };
    } else {
      // 极陡方向首次命中已在管外：直接到达右端。
      const { y, goingUp } = foldY(y0 + ROD.L * tanTheta);
      state.path.push({ x: ROD.L, y });
      state.exit = { x: ROD.L, y, angleDeg: i, goingUp };
    }
    return state;
  }

  if (classification === 'critical') {
    // θ=30°：临界，折射光沿界面传播；侧壁命中不算全反射反射。
    if (firstHit) {
      const y = firstHit.wall === 'top' ? ROD.h : 0;
      state.path.push({ x: firstHit.x, y });
      state.path.push({ x: ROD.L, y });
      state.critical = { x: firstHit.x, y, wall: firstHit.wall };
    } else {
      const { y, goingUp } = foldY(y0 + ROD.L * tanTheta);
      state.path.push({ x: ROD.L, y });
      state.exit = { x: ROD.L, y, angleDeg: i, goingUp };
    }
    return state;
  }

  // 严格全反射：hits 全部为真实反射点。
  state.reflections = hits;
  state.count = hits.length;
  for (const hit of hits) {
    state.path.push({ x: hit.x, y: hit.wall === 'top' ? ROD.h : 0 });
  }

  // 右端出射（入射角 θ < 30° < C，不发生全反射），出射角等于 i。
  if (edgeHit) {
    // 下一反射点恰在管端棱边：棱边不计侧壁反射，光在棱边处离管。
    state.path.push({ x: ROD.L, y: edgeHit.y });
    state.exit = {
      x: ROD.L,
      y: edgeHit.y,
      angleDeg: i,
      goingUp: edgeHit.k % 2 === 1,
    };
  } else {
    const { y, goingUp } = foldY(y0 + ROD.L * tanTheta);
    state.path.push({ x: ROD.L, y });
    state.exit = { x: ROD.L, y, angleDeg: i, goingUp };
  }
  return state;
}

/** 由预设管内角 θ（度）经 Snell 反算真实空气入射方向后计算状态。 */
export function computeFromTheta(thetaDeg) {
  return computeFromIncidence(incidenceForTheta(thetaDeg));
}
