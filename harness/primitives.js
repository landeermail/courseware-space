"use strict";

globalThis.CoursewarePrimitives = Object.freeze({
  createTimeline(options) {
    const duration = Number(options.durationPhysicalS);
    const onChange = options.onChange;
    if (!Number.isFinite(duration) || duration <= 0 || typeof onChange !== "function") {
      throw new Error("invalid timeline options");
    }
    let physicalTime = 0;
    let demoRate = 0.5;
    let playing = false;
    let frame = 0;
    let previous = 0;
    const emit = () => {
      if (typeof document !== "undefined" && document.documentElement) {
        document.documentElement.setAttribute("data-harness-physical-time", physicalTime.toFixed(6));
        document.documentElement.setAttribute("data-harness-playing", playing ? "true" : "false");
      }
      onChange(Object.freeze({ physicalTimeS: physicalTime, demoRate, playing }));
    };
    const tick = now => {
      if (!playing) return;
      if (!previous) previous = now;
      physicalTime = Math.min(duration, physicalTime + ((now - previous) / 1000) * demoRate);
      previous = now;
      emit();
      if (physicalTime >= duration) {
        playing = false;
        emit();
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    const controller = Object.freeze({
      play() {
        if (playing || physicalTime >= duration) return;
        playing = true;
        previous = 0;
        emit();
        frame = requestAnimationFrame(tick);
      },
      pause() {
        playing = false;
        cancelAnimationFrame(frame);
        emit();
      },
      replay() {
        playing = false;
        cancelAnimationFrame(frame);
        physicalTime = 0;
        previous = 0;
        emit();
      },
      seek(value) {
        physicalTime = Math.max(0, Math.min(duration, Number(value)));
        emit();
      },
      setDemoRate(value) {
        const next = Number(value);
        if (!Number.isFinite(next) || next < 0.1 || next > 4) throw new Error("invalid demo rate");
        demoRate = next;
        emit();
      },
      snapshot() { return Object.freeze({ physicalTimeS: physicalTime, demoRate, playing }); },
    });
    emit();
    return controller;
  },
  formatPhysicalTime(value) { return `${Number(value).toFixed(2)} s（物理时间）`; },
  formatDemoRate(value) { return `${Number(value).toFixed(2)}×（演示倍率）`; },
});
