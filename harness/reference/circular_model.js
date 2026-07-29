"use strict";

globalThis.coursewareModel = Object.freeze({
  sample(input) {
    const s = input.scenario;
    const r = s.radius_m;
    const m = s.mass_kg;
    const baseSpeed = s.mode === "orbit"
      ? Math.sqrt(s.G_n_m2_kg2 * s.central_mass_kg / r)
      : s.speed_m_s;

    function verticalPeriod() {
      const intervals = 4096;
      const step = 2 * Math.PI / intervals;
      let total = 0;
      for (let index = 0; index <= intervals; index += 1) {
        const angle = index * step;
        const height = r * (1 - Math.cos(angle));
        const speed = Math.sqrt(baseSpeed ** 2 - 2 * s.g_m_s2 * height);
        const weight = index === 0 || index === intervals ? 1 : (index % 2 ? 4 : 2);
        total += weight * r / speed;
      }
      return total * step / 3;
    }

    const states = input.angles_rad.map(angle => {
      const vertical = s.mode === "vertical_string";
      const x = vertical ? r * Math.sin(angle) : r * Math.cos(angle);
      const y = vertical ? r * (1 - Math.cos(angle)) : r * Math.sin(angle);
      const speed = vertical
        ? Math.sqrt(Math.max(0, baseSpeed ** 2 - 2 * s.g_m_s2 * y))
        : baseSpeed;
      const acceleration = speed ** 2 / r;
      const ax = vertical ? -acceleration * Math.sin(angle) : -acceleration * Math.cos(angle);
      const ay = vertical ? acceleration * Math.cos(angle) : -acceleration * Math.sin(angle);
      const radial = m * acceleration;
      const tension = vertical ? radial + m * s.g_m_s2 * Math.cos(angle) : 0;
      const potential = s.mode === "orbit"
        ? -s.G_n_m2_kg2 * s.central_mass_kg * m / r
        : (vertical ? m * s.g_m_s2 * y : 0);
      const kinetic = 0.5 * m * speed ** 2;
      const mechanical = kinetic + potential;
      return {
        angle_rad: angle,
        x_m: x,
        y_m: y,
        speed_m_s: speed,
        ax_m_s2: ax,
        ay_m_s2: ay,
        radial_force_n: radial,
        tension_n: tension,
        kinetic_j: kinetic,
        potential_j: potential,
        mechanical_j: mechanical
      };
    });

    const events = {
      period_s: s.mode === "vertical_string" ? verticalPeriod() : 2 * Math.PI * r / baseSpeed,
      centripetal_acceleration_m_s2: baseSpeed ** 2 / r
    };
    if (s.mode === "vertical_string") {
      events.critical_top_speed_m_s = Math.sqrt(s.g_m_s2 * r);
      events.critical_bottom_speed_m_s = Math.sqrt(5 * s.g_m_s2 * r);
    }
    return {states, events};
  }
});
