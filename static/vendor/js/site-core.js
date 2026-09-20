"use strict";

/**
 * Global Site Behaviors: Preloader, Mobile Nav, Scroll Actions, Reveal Animations
 * Tüm kod bir IIFE içinde — global scope'u kirletmiyor, diğer script'lerle çakışmıyor.
 */
(() => {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);

  const addEventOnElements = (elements, eventType, callback, options = {}) => {
    elements.forEach((element) => element.addEventListener(eventType, callback, options));
  };

  /* ==========================================================================
     1. PRELOADER HANDLER
     ========================================================================== */
  const preloader = $("[data-preloader]");

  window.addEventListener("load", () => {
    if (preloader) preloader.classList.add("loaded");
    document.body.classList.add("loaded");
  });

  /* ==========================================================================
     2. MOBILE NAVIGATION TOGGLE
     ========================================================================== */
  const navbar = $("[data-navbar]");
  const overlay = $("[data-overlay]");
  const navTogglers = $$("[data-nav-toggler]");

  const toggleNav = () => {
    if (!navbar || !overlay) return;

    const isActive = navbar.classList.toggle("active");
    overlay.classList.toggle("active");
    document.body.classList.toggle("nav-active");

    // Menü açıkken arka planın kaymasını engelle
    document.body.style.overflow = isActive ? "hidden" : "";

    navTogglers.forEach((btn) => btn.setAttribute("aria-expanded", isActive ? "true" : "false"));
    overlay.setAttribute("aria-hidden", isActive ? "false" : "true");
  };

  addEventOnElements(navTogglers, "click", toggleNav);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && navbar?.classList.contains("active")) {
      toggleNav();
    }
  });

  /* ==========================================================================
     3. SCROLL ACTIONS (Header & Back To Top) — rAF ile throttle edilmiş
     ========================================================================== */
  const header = $("[data-header]");
  const backTopBtn = $("[data-back-top-btn]");

  let scrollTicking = false;

  const activeElementOnScroll = () => {
    const isScrolled = window.scrollY > 100;
    if (header) header.classList.toggle("active", isScrolled);
    if (backTopBtn) backTopBtn.classList.toggle("active", isScrolled);
    scrollTicking = false;
  };

  window.addEventListener(
    "scroll",
    () => {
      if (!scrollTicking) {
        requestAnimationFrame(activeElementOnScroll);
        scrollTicking = true;
      }
    },
    { passive: true }
  );

  // Yukarı çık butonu: element vardı ama tıklama davranışı eksikti
  backTopBtn?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  /* ==========================================================================
     4. SCROLL REVEAL ANIMATION (Intersection Observer)
     ========================================================================== */
  const revealElements = $$("[data-reveal]");

  if (revealElements.length > 0) {
    const observer = new IntersectionObserver(
      (entries, observerInstance) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
            observerInstance.unobserve(entry.target); // performans için tekrar izlenmesin
          }
        });
      },
      { threshold: 0.15 }
    );

    revealElements.forEach((element) => observer.observe(element));
  }
})();