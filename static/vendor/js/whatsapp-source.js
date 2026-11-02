"use strict";

/**
 * Sitedeki tüm WhatsApp (wa.me) bağlantılarının mesajının altına,
 * kullanıcının geldiği sayfanın linkini ekler. Böylece gelen mesajın
 * siteden (ve hangi sayfadan) geldiği anlaşılır.
 *
 * - Mesajı olmayan linklere (header, footer, banner) varsayılan bir selam eklenir.
 * - Mesajı zaten site linkini içeren linklere (sipariş mesajı) dokunulmaz.
 */
(() => {
  const DEFAULT_TEXT = "Merhaba, bilgi almak istiyorum.";
  const SELECTOR = 'a[href*="wa.me/"], a[href*="api.whatsapp.com/send"]';

  const pageUrl = () => window.location.origin + window.location.pathname;

  const tagLink = (anchor) => {
    if (anchor.dataset.waTagged) return;

    let url;
    try {
      url = new URL(anchor.href);
    } catch (e) {
      return;
    }
    if (url.hostname !== "wa.me" && url.hostname !== "api.whatsapp.com") return;

    anchor.dataset.waTagged = "1";

    const text = url.searchParams.get("text") || DEFAULT_TEXT;
    if (text.includes(window.location.origin)) return;

    url.search = "?text=" + encodeURIComponent(text + "\n\n🌐 " + pageUrl());
    anchor.href = url.toString();
  };

  const tagAll = () => document.querySelectorAll(SELECTOR).forEach(tagLink);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", tagAll);
  } else {
    tagAll();
  }

  // Sonradan eklenen linkler için güvence: tıklama anında da etiketle.
  document.addEventListener(
    "click",
    (event) => {
      const anchor = event.target.closest && event.target.closest(SELECTOR);
      if (anchor) tagLink(anchor);
    },
    true
  );
})();