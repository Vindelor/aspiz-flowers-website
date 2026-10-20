"use strict";

/**
 * Promo countdown: 6-hour cycle that restarts from the beginning by itself.
 * The cycle is anchored to the clock (00:00, 06:00, 12:00, 18:00 Istanbul time,
 * which are also 6-hour boundaries in UTC), so every visitor sees the same
 * remaining time and a page refresh never resets it.
 */
(() => {
  const timers = document.querySelectorAll("[data-promo-timer]");
  if (!timers.length) return;

  const CYCLE_MS = 6 * 60 * 60 * 1000;
  const pad = (n) => String(n).padStart(2, "0");

  const tick = () => {
    const remaining = CYCLE_MS - (Date.now() % CYCLE_MS);
    const total = Math.floor(remaining / 1000);
    const h = pad(Math.floor(total / 3600));
    const m = pad(Math.floor((total % 3600) / 60));
    const s = pad(total % 60);

    timers.forEach((timer) => {
      const hEl = timer.querySelector("[data-promo-h]");
      const mEl = timer.querySelector("[data-promo-m]");
      const sEl = timer.querySelector("[data-promo-s]");
      if (hEl) hEl.textContent = h;
      if (mEl) mEl.textContent = m;
      if (sEl) sEl.textContent = s;
    });
  };

  tick();
  setInterval(tick, 1000);
})();