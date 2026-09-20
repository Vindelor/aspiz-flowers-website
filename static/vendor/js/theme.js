"use strict";

(() => {
  const themeToggleBtn = document.getElementById("themeToggle");

  const getPreferredTheme = () => {
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) return savedTheme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const setTheme = (theme) => {
    const isDark = theme === "dark";
    document.documentElement.classList.toggle("dark-mode", isDark);
    localStorage.setItem("theme", theme);

    if (themeToggleBtn) {
      themeToggleBtn.setAttribute("aria-pressed", isDark ? "true" : "false");
    }
  };

  // Apply saved/preferred theme immediately
  setTheme(getPreferredTheme());

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const isCurrentDark = document.documentElement.classList.contains("dark-mode");
      setTheme(isCurrentDark ? "light" : "dark");
    });
  }
})();