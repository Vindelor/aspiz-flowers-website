"use strict";

/**
 * Cart Modal: gerçek Django sepetine bağlı (localStorage YOK).
 * Modal her açıldığında GET /cart/state/ ile içerik çekilir; +/-/sil
 * butonları POST /cart/update|remove/<product_id>/ çağırır ve dönen JSON
 * ile modal yeniden çizilir. Ürün kartlarındaki "Sepete Ekle" (base.html'de
 * zaten var olan handler) da aynı /cart/add/ endpoint'ini kullanıyor; o
 * yüzden header rozeti (data-cart-count) her yerde otomatik güncel kalıyor.
 */
(() => {
  const modal = document.querySelector("[data-cart-modal]");
  if (!modal) return;

  const panel = modal.querySelector(".login-modal-panel");
  const openButtons = document.querySelectorAll("[data-cart-open]");
  const closeButtons = modal.querySelectorAll("[data-cart-close]");

  const emptyState = modal.querySelector("[data-cart-empty]");
  const loadingState = modal.querySelector("[data-cart-loading]");
  const itemsList = modal.querySelector("[data-cart-items]");
  const footer = modal.querySelector("[data-cart-footer]");
  const totalEl = modal.querySelector("[data-cart-total]");
  const modalCountEl = modal.querySelector("[data-cart-modal-count]");
  const headerCountEls = document.querySelectorAll("[data-cart-count]");

  let lastFocusedEl = null;

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  // Whole-number prices show with no decimals (20 ₺); only prices the admin
  // has actually given a fractional value to (19,50 ₺) keep their decimals.
  const formatPriceValue = (value) =>
    Number(value).toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

  const formatPrice = (value) => `${formatPriceValue(value)} ₺`;

  const escapeHtml = (str) =>
    String(str).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

  const buildItemRow = (item) => `
    <li class="cart-item" data-cart-item-id="${item.product_id}">
      <div class="cart-item-thumb">
        ${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="lazy">` : ""}
      </div>
      <div class="cart-item-info">
        <span class="cart-item-name">${escapeHtml(item.name)}</span>
        <span class="cart-item-price price-display">
          <span class="price-value">${formatPriceValue(item.unit_price)}</span>
          <span class="price-unit">₺</span>
        </span>
      </div>
      <div class="cart-item-qty">
        <button type="button" class="cart-qty-btn" data-cart-decrease="${item.product_id}" aria-label="Azalt">−</button>
        <span class="cart-qty-value">${item.quantity}</span>
        <button type="button" class="cart-qty-btn" data-cart-increase="${item.product_id}" aria-label="Artır"
          ${item.quantity >= item.stock_quantity ? "disabled" : ""}>+</button>
      </div>
      <button type="button" class="cart-item-remove" data-cart-remove="${item.product_id}" aria-label="Sepetten çıkar">
        <i class="fa-solid fa-trash-can"></i>
      </button>
    </li>`;

  const applyState = (data) => {
    headerCountEls.forEach((el) => { el.textContent = data.cart_item_count; });
    document.querySelectorAll("[data-cart-open]").forEach((btn) => {
      btn.setAttribute("aria-label", `Sepetim, ${data.cart_item_count} ürün`);
    });
    if (modalCountEl) modalCountEl.textContent = `${data.cart_item_count} ürün`;

    loadingState?.classList.remove("active");

    if (!data.items || data.items.length === 0) {
      emptyState.hidden = false;
      itemsList.hidden = true;
      footer.hidden = true;
      itemsList.innerHTML = "";
      return;
    }

    emptyState.hidden = true;
    itemsList.hidden = false;
    footer.hidden = false;
    itemsList.innerHTML = data.items.map(buildItemRow).join("");
    if (totalEl) {
      totalEl.innerHTML = `<span class="price-display price-display-total"><span class="price-value">${formatPriceValue(data.cart_total_price)}</span><span class="price-unit">₺</span></span>`;
    }
  };

  const postCart = async (url, quantity) => {
    const body = quantity === undefined ? "" : `quantity=${encodeURIComponent(quantity)}`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Bir hata oluştu.");
      return null;
    }
    applyState(data);
    return data;
  };

  const fetchState = async () => {
    loadingState?.classList.add("active");
    itemsList.hidden = true;
    footer.hidden = true;
    emptyState.hidden = true;
    try {
      const res = await fetch("/cart/state/", { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await res.json();
      applyState(data);
    } catch (err) {
      loadingState?.classList.remove("active");
      emptyState.hidden = false;
    }
  };

  itemsList?.addEventListener("click", (event) => {
    const increaseBtn = event.target.closest("[data-cart-increase]");
    const decreaseBtn = event.target.closest("[data-cart-decrease]");
    const removeBtn = event.target.closest("[data-cart-remove]");

    if (increaseBtn) {
      const id = increaseBtn.dataset.cartIncrease;
      const currentQty = parseInt(increaseBtn.closest(".cart-item").querySelector(".cart-qty-value").textContent, 10);
      postCart(`/cart/update/${id}/`, currentQty + 1);
    }

    if (decreaseBtn) {
      const id = decreaseBtn.dataset.cartDecrease;
      const currentQty = parseInt(decreaseBtn.closest(".cart-item").querySelector(".cart-qty-value").textContent, 10);
      postCart(`/cart/update/${id}/`, currentQty - 1);
    }

    if (removeBtn) {
      postCart(`/cart/remove/${removeBtn.dataset.cartRemove}/`);
    }
  });

  const openModal = () => {
    lastFocusedEl = document.activeElement;
    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    fetchState();
  };

  const closeModal = () => {
    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    lastFocusedEl?.focus();
  };

  openButtons.forEach((btn) =>
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      openModal();
    })
  );

  closeButtons.forEach((btn) => btn.addEventListener("click", closeModal));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.classList.contains("active")) {
      closeModal();
    }
  });

  panel?.addEventListener("click", (e) => e.stopPropagation());
})();
