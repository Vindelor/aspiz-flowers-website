/* Blog page: soft gold light that follows the pointer (desktop only,
   skipped for touch screens and "reduce motion"). */
(function () {
  var glow = document.querySelector('[data-bp-glow]');
  if (!glow) return;
  if (!window.matchMedia('(hover: hover) and (prefers-reduced-motion: no-preference)').matches) return;

  var x = 0, y = 0, raf = 0;
  function paint() {
    raf = 0;
    glow.style.setProperty('--mx', x + 'px');
    glow.style.setProperty('--my', y + 'px');
  }
  window.addEventListener('pointermove', function (e) {
    x = e.clientX;
    y = e.clientY;
    glow.classList.add('on');
    if (!raf) raf = requestAnimationFrame(paint);
  }, { passive: true });
  document.addEventListener('pointerleave', function () { glow.classList.remove('on'); });
})();
