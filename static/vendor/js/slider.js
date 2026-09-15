"use strict";

/**
 * Category Circular Slider (header)
 * Artık tıklanacak ok butonu yok — kullanıcı kendi parmağıyla/fareyle
 * kaydırıyor. Burada sadece track odaklandığında sol/sağ ok tuşlarıyla
 * kaydırma desteği bırakıldı (erişilebilirlik için).
 */
(() => {
  const sliderTrack = document.querySelector("[data-slider-track]");
  if (!sliderTrack) return;

  const getScrollAmount = () => {
    const firstItem = sliderTrack.querySelector(".cat-item");
    return firstItem ? firstItem.clientWidth + 20 : 200; // öğe genişliği + boşluk
  };

  sliderTrack.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight") sliderTrack.scrollBy({ left: getScrollAmount(), behavior: "smooth" });
    if (event.key === "ArrowLeft") sliderTrack.scrollBy({ left: -getScrollAmount(), behavior: "smooth" });
  });
})();
