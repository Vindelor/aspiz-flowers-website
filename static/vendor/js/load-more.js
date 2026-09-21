/**
 * "Daha Fazla Göster" button: fetches the next page of products and appends
 * the cards to the current grid, instead of navigating to a new page.
 * Works by fetching the next page's full HTML and pulling the product cards
 * (and the next button's new data-next-url) out of it — no backend changes needed.
 */
document.addEventListener('click', function (e) {
  const btn = e.target.closest('[data-load-more-btn]');
  if (!btn) return;

  const grid = document.querySelector('[data-product-grid]');
  const nextUrl = btn.dataset.nextUrl;
  if (!grid || !nextUrl) return;

  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Yükleniyor...';

  fetch(nextUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then((res) => res.text())
    .then((html) => {
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const newGrid = doc.querySelector('[data-product-grid]');
      const newBtn = doc.querySelector('[data-load-more-btn]');

      if (newGrid) {
        Array.from(newGrid.children).forEach((card) => grid.appendChild(card));
      }

      if (newBtn) {
        btn.dataset.nextUrl = newBtn.dataset.nextUrl;
        btn.disabled = false;
        btn.textContent = originalLabel;
      } else {
        // No more pages left to load.
        btn.remove();
      }
    })
    .catch(() => {
      btn.disabled = false;
      btn.textContent = originalLabel;
    });
});