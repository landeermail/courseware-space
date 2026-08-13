globalThis.coursewareModel = Object.freeze({
  sample(input) {
    var scenario = (input && input.scenario) || {};
    var angles = (input && Array.isArray(input.angles_rad) && input.angles_rad.length > 0) ? input.angles_rad : [0];
    var mode = typeof scenario.mode === 'string' ? scenario.mode : 'uniform';
    var m = Number(scenario.mass_kg) || 0;
    var r = Number(scenario.radius_m) || 0;
    var G = Number(scenario.G_n_m2_kg2) || 6.6743e-11;
    var M = Number(scenario.central_mass_kg) || 0;
    var g = Number(scenario.g_m_s2) || 0;
    var vGiven = Number(scenario.speed_m_s) || 0;

    function makeState(th, x, y, v, ax, ay, Frad, T, ke, pe) {
      return {
        angle_rad: th,
        x_m: x,
        y_m: y,
        speed_m_s: v,
        ax_m_s2: ax,
        ay_m_s2: ay,
        radial_force_n: Frad,
        tension_n: T,
        kinetic_j: ke,
        potential_j: pe,
        mechanical_j: ke + pe
      };
    }

    var states = [];
    var events = { period_s: 0, centripetal_acceleration_m_s2: 0 };
    var i, th;

    if (mode === 'orbit') {
      var vOrb = Math.sqrt(G * M / r);
      var aOrb = G * M / (r * r);
      var FOrb = G * M * m / (r * r);
      var keOrb = 0.5 * m * vOrb * vOrb;
      var peOrb = -G * M * m / r;
      for (i = 0; i < angles.length; i++) {
        th = angles[i];
        states.push(makeState(
          th,
          r * Math.cos(th),
          r * Math.sin(th),
          vOrb,
          -aOrb * Math.cos(th),
          -aOrb * Math.sin(th),
          FOrb,
          0,
          keOrb,
          peOrb
        ));
      }
      events.period_s = 2 * Math.PI * Math.sqrt((r * r * r) / (G * M));
      events.centripetal_acceleration_m_s2 = aOrb;
    } else if (mode === 'vertical_string') {
      var v0 = vGiven;
      var v0sq = v0 * v0;
      for (i = 0; i < angles.length; i++) {
        th = angles[i];
        var sn = Math.sin(th);
        var cs = Math.cos(th);
        var v2 = v0sq - 2 * g * r * (1 - cs);
        if (v2 < 0) { v2 = 0; }
        var v = Math.sqrt(v2);
        var arad = (r > 0) ? (v2 / r) : 0;
        var atang = -g * sn;
        var ax = -arad * sn + atang * cs;
        var ay = arad * cs + atang * sn;
        var tension = m * (arad + g * cs);
        var ke = 0.5 * m * v2;
        var pe = m * g * r * (1 - cs);
        states.push(makeState(
          th,
          r * sn,
          -r * cs,
          v,
          ax,
          ay,
          m * arad,
          tension,
          ke,
          pe
        ));
      }
      var period;
      if (v0sq - 4 * g * r <= 0) {
        period = Infinity;
      } else {
        var N = 20000;
        var h = (Math.PI / 2) / N;
        var sum = 0;
        for (i = 0; i <= N; i++) {
          var thi = i * h;
          var v2i = v0sq - 2 * g * r * (1 - Math.cos(thi));
          if (v2i < 1e-30) { v2i = 1e-30; }
          var f = r / Math.sqrt(v2i);
          var w = (i === 0 || i === N) ? 1 : ((i % 2 === 1) ? 4 : 2);
          sum += w * f;
        }
        period = 4 * (sum * h / 3);
      }
      events.period_s = period;
      events.centripetal_acceleration_m_s2 = (r > 0) ? (v0sq / r) : 0;
      events.critical_top_speed_m_s = Math.sqrt(g * r);
      events.critical_bottom_speed_m_s = Math.sqrt(5 * g * r);
    } else {
      var vU = vGiven;
      var aU = (r > 0) ? (vU * vU / r) : 0;
      var FU = m * aU;
      var keU = 0.5 * m * vU * vU;
      for (i = 0; i < angles.length; i++) {
        th = angles[i];
        states.push(makeState(
          th,
          r * Math.cos(th),
          r * Math.sin(th),
          vU,
          -aU * Math.cos(th),
          -aU * Math.sin(th),
          FU,
          FU,
          keU,
          0
        ));
      }
      events.period_s = (vU > 0) ? (2 * Math.PI * r / vU) : Infinity;
      events.centripetal_acceleration_m_s2 = aU;
    }

    return { states: states, events: events };
  }
});
