"use strict";

/**
 * /cart/ (sepet) sayfasındaki adet kutuları düz bir <form> idi; adet
 * değiştirilince (hatta "Güncelle"ye basılınca bile) fiyatlar hiç
 * değişmiyordu, çünkü:
 *  - kutuya girilen sayı `max` (stok) değerini aşarsa tarayıcı formu
 *    hiç göndermiyordu (sessizce), sayfa eski toplamla kalıyordu.
 *  - "Güncelle" tam sayfa yenilemesi gerektiriyordu.
 * Bu dosya, sepet modalının kullandığı aynı /cart/update/<id>/ endpoint'ini
 * AJAX ile çağırıp birim fiyatı, satır toplamını ve genel toplamı anında
 * günceller; stok/hata durumunda da kutunun altında net bir mesaj gösterir.
 */
(() => {
  const qtyInputs = document.querySelectorAll("[data-cart-qty-input]");
  if (!qtyInputs.length) return;

  const totalEl = document.querySelector("[data-cart-page-total]");

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  const formatPriceValue = (value) =>
    Number(value).toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

  const clearError = (productId) => {
    const err = document.querySelector(`[data-cart-error="${productId}"]`);
    if (err) {
      err.hidden = true;
      err.textContent = "";
    }
  };

  const showError = (productId, message) => {
    const err = document.querySelector(`[data-cart-error="${productId}"]`);
    if (err) {
      err.hidden = false;
      err.textContent = message;
    }
  };

  const applyItem = (item) => {
    const unitEl = document.querySelector(`[data-cart-unit-price="${item.product_id}"]`);
    if (unitEl) unitEl.textContent = formatPriceValue(item.unit_price);

    const lineEl = document.querySelector(`[data-cart-line-total="${item.product_id}"]`);
    if (lineEl) lineEl.textContent = formatPriceValue(item.line_total);

    const qtyInput = document.querySelector(`[data-cart-qty-input="${item.product_id}"]`);
    if (qtyInput) {
      qtyInput.value = item.quantity;
      qtyInput.max = item.stock_quantity;
    }
  };

  const updateQuantity = async (productId, quantity, inputEl) => {
    clearError(productId);
    const previousValue = inputEl.dataset.lastValid || inputEl.defaultValue;

    try {
      const res = await fetch(`/cart/update/${productId}/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "X-Requested-With": "XMLHttpRequest",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: `quantity=${encodeURIComponent(quantity)}`,
      });
      const data = await res.json();

      if (!data.ok) {
        showError(productId, data.error || "Bir hata oluştu.");
        inputEl.value = previousValue;
        return;
      }

      if (quantity < 1) {
        // Item removed (quantity < 1) — reload so the row disappears / the
        // empty-cart state renders correctly.
        window.location.reload();
        return;
      }

      const item = data.items.find((i) => String(i.product_id) === String(productId));
      if (item) {
        applyItem(item);
        inputEl.dataset.lastValid = String(item.quantity);
      }
      if (totalEl) totalEl.textContent = formatPriceValue(data.cart_total_price);
    } catch (err) {
      showError(productId, "Bağlantı hatası, lütfen tekrar deneyin.");
      inputEl.value = previousValue;
    }
  };

  qtyInputs.forEach((input) => {
    const productId = input.dataset.cartQtyInput;
    input.dataset.lastValid = input.value;

    const form = input.closest(".cart-qty-form");
    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      const qty = parseInt(input.value, 10);
      if (Number.isNaN(qty)) return;
      updateQuantity(productId, qty, input);
    });

    input.addEventListener("change", () => {
      const qty = parseInt(input.value, 10);
      if (Number.isNaN(qty)) return;
      updateQuantity(productId, qty, input);
    });
  });
})();
