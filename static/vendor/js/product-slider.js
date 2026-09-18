"use strict";

/**
 * Product Section Carousel
 * Ana sayfadaki ve ürün detayındaki "10'lu" ürün şeritleri artık tamamen
 * kullanıcı kontrolünde kayıyor (parmak/touch, trackpad, fare tekerleği +
 * shift). Buradaki tek iş: track odaklandığında sol/sağ ok tuşlarıyla da
 * kaydırılabilsin diye klavye erişilebilirliği eklemek — tıklanacak ok
 * butonu yok.
 */
(() => {
  const tracks = document.querySelectorAll("[data-product-track]");
  if (!tracks.length) return;

  tracks.forEach((track) => {
    const getScrollAmount = () => {
      const firstItem = track.querySelector(".product-track-item");
      return firstItem ? firstItem.getBoundingClientRect().width + 16 : track.clientWidth * 0.8;
    };

    track.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") track.scrollBy({ left: getScrollAmount(), behavior: "smooth" });
      if (event.key === "ArrowLeft") track.scrollBy({ left: -getScrollAmount(), behavior: "smooth" });
    });
  });
})();
