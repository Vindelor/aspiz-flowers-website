"use strict";

/**
 * Footer üstü Türkiye haritası:
 *  - bildirimler sırayla (karışık) görünür, her biri şehrinin noktasında belirir
 *  - İstanbul (İSTOÇ) merkezinden aktif şehre altın bir "sevkiyat" çizgisi çizilir
 *  - bölüm ekrana girince kart ve metin animasyonla açılır
 * Üzerine gelince/odaklanınca, sekme arka plandayken veya bölüm ekranda değilken
 * bildirim değişimi durur. Linkler HTML'de zaten durur (JS kapalıysa da görünür).
 */
(() => {
  const root = document.querySelector("[data-tmap]");
  if (!root) return;
  const map = root.querySelector("[data-tmap-map]");
  const items = Array.from(root.querySelectorAll("[data-tm-item]"));
  if (!map || items.length === 0) return;

  const VB_W = 592, VB_H = 264;          // SVG viewBox (turkey_map.html ile aynı)
  const INTERVAL = 3800;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  root.classList.add("js");

  // Merkez (İstanbul / İSTOÇ) — data-tm-hub="x%,y%"
  const [hx, hy] = (map.dataset.tmHub || "16.2,19.5").split(",").map(parseFloat);
  const hub = { x: (hx / 100) * VB_W, y: (hy / 100) * VB_H };
  const arc = root.querySelector("[data-tm-arc]");
  const hubDot = root.querySelector("[data-tm-hubdot]");
  if (hubDot) { hubDot.setAttribute("cx", hub.x); hubDot.setAttribute("cy", hub.y); }

  // Ekrana girince aç
  if ("IntersectionObserver" in window) {
    const reveal = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) { root.classList.add("is-in"); reveal.disconnect(); }
    }, { threshold: 0.2 });
    reveal.observe(root);
  } else {
    root.classList.add("is-in");
  }

  // Her yüklemede farklı sıra (Fisher-Yates)
  const order = items.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }

  let pos = 0, current = null, timer = null, hovering = false, visible = true;

  // Balon harita kenarından taşarsa içeri it (özellikle dar ekranlarda)
  function nudge(item) {
    const bubble = item.querySelector(".tm-bubble");
    if (!bubble) return;
    bubble.style.setProperty("--tm-nudge", "0px");
    const m = map.getBoundingClientRect();
    const b = bubble.getBoundingClientRect();
    let dx = 0;
    if (b.right > m.right) dx = m.right - b.right;
    if (b.left + dx < m.left) dx = m.left - b.left;
    bubble.style.setProperty("--tm-nudge", dx + "px");
  }

  // Merkezden şehre kavisli altın çizgi
  function drawArc(item) {
    if (!arc) return;
    const x = (parseFloat(item.style.getPropertyValue("--x")) / 100) * VB_W;
    const y = (parseFloat(item.style.getPropertyValue("--y")) / 100) * VB_H;
    const len = Math.hypot(x - hub.x, y - hub.y);
    arc.classList.remove("draw");
    if (len < 12) { arc.setAttribute("d", "M0 0"); return; }   // İstanbul'un kendisi
    const cx = (x + hub.x) / 2;
    const cy = (y + hub.y) / 2 - Math.min(60, len * 0.28);
    arc.setAttribute("d", `M${hub.x} ${hub.y} Q${cx} ${cy} ${x} ${y}`);
    arc.style.setProperty("--len", Math.ceil(len * 1.3));
    if (!reduceMotion) { void arc.getBoundingClientRect(); arc.classList.add("draw"); }
  }

  function show(item) {
    if (current) current.classList.remove("is-active");
    item.classList.add("is-active");
    nudge(item);
    drawArc(item);
    current = item;
  }

  function next() {
    show(items[order[pos]]);
    pos = (pos + 1) % order.length;
  }

  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  function start() {
    if (timer || hovering || !visible || document.hidden) return;
    timer = setInterval(next, INTERVAL);
  }

  next();
  start();

  map.addEventListener("mouseenter", () => { hovering = true; stop(); });
  map.addEventListener("mouseleave", () => { hovering = false; start(); });
  map.addEventListener("focusin", () => { hovering = true; stop(); });
  map.addEventListener("focusout", () => { hovering = false; start(); });
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
  window.addEventListener("resize", () => current && nudge(current));

  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      visible = entries[0].isIntersecting;
      visible ? start() : stop();
    }, { threshold: 0.15 }).observe(root);
  }
})();
