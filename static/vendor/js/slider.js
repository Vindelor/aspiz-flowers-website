"use strict";

/**
 * Category Circular Slider
 * Ok tuşlarıyla kaydırma + klavye erişilebilirliği eklendi.
 */
(() => {
  const sliderTrack = document.querySelector("[data-slider-track]");
  const prevBtn = document.querySelector("[data-slider-prev]");
  const nextBtn = document.querySelector("[data-slider-next]");

  if (!sliderTrack || !prevBtn || !nextBtn) return;

  const getScrollAmount = () => {
    const firstItem = sliderTrack.querySelector(".cat-item");
    return firstItem ? firstItem.clientWidth + 20 : 200; // öğe genişliği + boşluk
  };

  const updateButtonStates = () => {
    const maxScroll = sliderTrack.scrollWidth - sliderTrack.clientWidth;
    prevBtn.disabled = sliderTrack.scrollLeft <= 0;
    nextBtn.disabled = Math.ceil(sliderTrack.scrollLeft) >= maxScroll;
  };

  const scrollNext = () => sliderTrack.scrollBy({ left: getScrollAmount(), behavior: "smooth" });
  const scrollPrev = () => sliderTrack.scrollBy({ left: -getScrollAmount(), behavior: "smooth" });

  nextBtn.addEventListener("click", scrollNext);
  prevBtn.addEventListener("click", scrollPrev);

  // Klavye ile erişilebilirlik (sol/sağ ok tuşları)
  sliderTrack.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight") scrollNext();
    if (event.key === "ArrowLeft") scrollPrev();
  });

  sliderTrack.addEventListener("scroll", updateButtonStates, { passive: true });

  // window 'resize' yerine ResizeObserver: sadece slider'ın kendi boyutu
  // değiştiğinde tetiklenir, daha performanslı
  if (window.ResizeObserver) {
    new ResizeObserver(updateButtonStates).observe(sliderTrack);
  } else {
    window.addEventListener("resize", updateButtonStates, { passive: true });
  }

  // Initial check
  updateButtonStates();
})();