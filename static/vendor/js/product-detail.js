"use strict";

/**
 * Ürün detay sayfası: galeri (küçük resme tıklayınca veya ana görseli
 * sağa/sola kaydırınca ana görsel + sayaç değişir), fiyat kademesi kutuları (tıklanınca adet inputunu doldurur;
 * adet elle değiştirilince de doğru kademeyi otomatik vurgular) ve
 * açıklama/kargo/ödeme accordion'ı.
 */
(() => {
  // --- Gallery ---
  const mainImg = document.querySelector("[data-gallery-main]");
  const counter = document.querySelector("[data-gallery-counter]");
  const thumbs = document.querySelectorAll("[data-gallery-thumb]");

  let currentIdx = 0;

  const showImage = (idx) => {
    const thumb = thumbs[idx];
    if (!thumb) return;
    currentIdx = idx;
    if (mainImg && mainImg.tagName === "IMG") {
      mainImg.src = thumb.dataset.fullSrc;
    }
    thumbs.forEach((t) => t.classList.remove("thumb-active"));
    thumb.classList.add("thumb-active");
    if (counter) counter.textContent = `${idx + 1}/${thumbs.length}`;
  };

  thumbs.forEach((thumb, idx) => {
    thumb.addEventListener("click", () => showImage(idx));
  });

  // Mobile: swipe left / right on the main image to change it (like a gallery).
  const swipeArea = mainImg && mainImg.tagName === "IMG" ? mainImg.parentElement : null;
  if (swipeArea && thumbs.length > 1) {
    swipeArea.style.touchAction = "pan-y"; // vertical page scroll still works
    let startX = 0;
    let startY = 0;

    swipeArea.addEventListener("touchstart", (e) => {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }, { passive: true });

    swipeArea.addEventListener("touchend", (e) => {
      const t = e.changedTouches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      // wrap around: after the last image comes the first, and vice versa
      const next = (currentIdx + (dx < 0 ? 1 : -1) + thumbs.length) % thumbs.length;
      showImage(next);
      thumbs[next].scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }, { passive: true });
  }

  // --- Price tier selector + quantity stepper + live total ---
  const tierBoxes = document.querySelectorAll("[data-tier-select]");
  const contactTier = document.querySelector("[data-tier-contact]");
  const qtyInput = document.querySelector("[data-qty-input]");
  const decBtn = document.querySelector("[data-qty-dec]");
  const incBtn = document.querySelector("[data-qty-inc]");
  const totalBox = document.querySelector("[data-qty-total]");
  const totalFormula = document.querySelector("[data-total-formula]");
  const totalAmount = document.querySelector("[data-total-amount]");

  // Fiyatlı kademeler, adedi büyükten küçüğe sıralı (cart.unit_price ile aynı kural)
  const pricedTiers = Array.from(tierBoxes)
    .map((box) => ({
      min: parseInt(box.dataset.tierMinQty, 10),
      price: parseFloat(box.dataset.tierPrice),
    }))
    .filter((t) => !Number.isNaN(t.price))
    .sort((a, b) => b.min - a.min);
  const contactMin = contactTier ? parseInt(contactTier.dataset.tierMinQty, 10) : null;
  const fmt = (n) => n.toLocaleString("tr-TR", { maximumFractionDigits: 2 });

  const unitPriceFor = (qty) => {
    const hit = pricedTiers.find((t) => qty >= t.min);
    return hit ? hit.price : pricedTiers.length ? pricedTiers[pricedTiers.length - 1].price : null;
  };

  const updateTotal = (qty) => {
    if (!totalBox || !totalFormula || !totalAmount) return;
    const unit = unitPriceFor(qty);
    if (qty < 1 || unit === null) {
      totalBox.hidden = true;
      return;
    }
    totalBox.hidden = false;
    if (contactMin !== null && qty >= contactMin) {
      totalFormula.textContent = `${fmt(qty)} adet için`;
      totalAmount.textContent = "Teklif alın";
      return;
    }
    totalFormula.textContent = `${fmt(qty)} × ${fmt(unit)}₺`;
    totalAmount.textContent = `${fmt(qty * unit)}₺`;
  };

  const highlightTierForQty = (qty) => {
    let active = null;
    tierBoxes.forEach((box) => {
      box.classList.remove("tier-active");
      if (qty >= parseInt(box.dataset.tierMinQty, 10)) active = box;
    });
    active?.classList.add("tier-active");
  };

  const applyQty = (qty) => {
    highlightTierForQty(qty);
    updateTotal(qty);
  };

  const clampQty = (qty) => {
    const max = qtyInput ? parseInt(qtyInput.max, 10) : NaN;
    let q = Math.max(1, qty);
    if (!Number.isNaN(max) && max > 0) q = Math.min(q, max);
    return q;
  };

  tierBoxes.forEach((box) => {
    box.addEventListener("click", () => {
      if (qtyInput) qtyInput.value = box.dataset.tierMinQty;
      tierBoxes.forEach((t) => t.classList.remove("tier-active"));
      box.classList.add("tier-active");
      updateTotal(parseInt(box.dataset.tierMinQty, 10));
    });
  });

  qtyInput?.addEventListener("input", () => {
    applyQty(parseInt(qtyInput.value, 10) || 0);
  });

  decBtn?.addEventListener("click", () => {
    if (!qtyInput) return;
    const next = clampQty((parseInt(qtyInput.value, 10) || 1) - 1);
    qtyInput.value = next;
    applyQty(next);
  });

  incBtn?.addEventListener("click", () => {
    if (!qtyInput) return;
    const next = clampQty((parseInt(qtyInput.value, 10) || 0) + 1);
    qtyInput.value = next;
    applyQty(next);
  });

  if (qtyInput && !qtyInput.disabled) updateTotal(parseInt(qtyInput.value, 10) || 0);

  // --- Accordion ---
  document.querySelectorAll("[data-accordion-trigger]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = btn.nextElementSibling;
      if (!panel) return;
      const isOpen = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!isOpen));
      panel.style.maxHeight = isOpen ? null : `${panel.scrollHeight}px`;
      btn.querySelector("[data-accordion-icon], .accordion-icon")?.classList.toggle("rotate-180", !isOpen);
    });
  });
})();