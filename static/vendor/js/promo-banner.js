"use strict";

/**
 * İnce reklam bandı: slaytları otomatik değiştirir (4,5 sn), noktalarla ve
 * parmakla/fareyle kaydırarak da gezilir. Üzerine gelince veya sekme arka
 * plandayken durur; "hareketi azalt" ayarı açıksa otomatik geçiş yapmaz.
 */
(() => {
  const root = document.querySelector("[data-promo-banner]");
  if (!root) return;
  const track = root.querySelector("[data-pb-track]");
  const dotsBox = root.querySelector("[data-pb-dots]");
  const slides = Array.from(track.children);
  if (slides.length < 2) { dotsBox?.remove(); return; }

  const INTERVAL = 4500;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let idx = 0;
  let timer = null;

  const dots = slides.map((_, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pb-dot";
    b.setAttribute("aria-label", `Slayt ${i + 1}`);
    b.addEventListener("click", () => { go(i); restart(); });
    dotsBox.appendChild(b);
    return b;
  });

  function go(i) {
    idx = (i + slides.length) % slides.length;
    track.style.transform = `translateX(-${idx * 100}%)`;
    dots.forEach((d, n) => d.setAttribute("aria-current", String(n === idx)));
    slides.forEach((s, n) => {
      s.setAttribute("aria-hidden", String(n !== idx));
      s.tabIndex = n === idx ? 0 : -1;
    });
  }

  function stop() { clearInterval(timer); timer = null; }
  function start() { if (!reduceMotion && !timer) timer = setInterval(() => go(idx + 1), INTERVAL); }
  function restart() { stop(); start(); }

  root.addEventListener("mouseenter", stop);
  root.addEventListener("mouseleave", start);
  root.addEventListener("focusin", stop);
  root.addEventListener("focusout", start);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));

  // Kaydırma (dokunmatik)
  let sx = 0, sy = 0;
  root.addEventListener("touchstart", (e) => {
    sx = e.touches[0].clientX; sy = e.touches[0].clientY; stop();
  }, { passive: true });
  root.addEventListener("touchend", (e) => {
    const t = e.changedTouches[0];
    const dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) go(idx + (dx < 0 ? 1 : -1));
    start();
  }, { passive: true });

  go(0);
  start();
})();