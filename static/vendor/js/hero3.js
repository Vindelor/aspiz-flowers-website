"use strict";

/**
 * Hero banner (homepage): splits the headline into words so they can fade in
 * one by one, then starts the entrance animation. Without JS everything stays
 * visible (the hidden "pre-play" state only applies when html.hero3-js is set).
 */
(() => {
  const hero = document.querySelector("[data-hero3]");
  if (!hero) return;

  const headline = hero.querySelector("[data-hero3-split]");
  if (headline) {
    headline.setAttribute("aria-label", headline.textContent.trim().replace(/\s+/g, " "));
    let index = 0;
    const walk = (node) => {
      Array.from(node.childNodes).forEach((child) => {
        if (child.nodeType === Node.TEXT_NODE) {
          const fragment = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach((part) => {
            if (!part) return;
            if (/^\s+$/.test(part)) {
              fragment.appendChild(document.createTextNode(" "));
              return;
            }
            const word = document.createElement("span");
            word.className = "hero3-word";
            word.setAttribute("aria-hidden", "true");
            word.style.setProperty("--i", index++);
            word.textContent = part;
            fragment.appendChild(word);
          });
          node.replaceChild(fragment, child);
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          walk(child);
        }
      });
    };
    walk(headline);
  }

  requestAnimationFrame(() => hero.classList.add("play"));
})();