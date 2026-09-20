/** @type {import('tailwindcss').Config} */
module.exports = {
  // Site toggles dark mode via <html class="dark-mode"> (see theme.js),
  // so Tailwind's dark: variant needs to match that selector instead of
  // its default .dark class.
  darkMode: ['selector', '.dark-mode'],
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        wine: {
          50:  "#fbf3f4",
          100: "#f5e6e9",
          200: "#e9c6cf",
          300: "#d99aab",
          400: "#c06b83",
          700: "#7d2140",
          800: "#6d1a35",
          900: "#4a0f24",
        },
        rose: {
          300: "#f0c4cf",
          400: "#e8a9b8",
        },
        cream: {
          50:  "#fdf8f8",
          100: "#faf1f2",
          200: "#f3e4e7",
        },
      },
      fontFamily: {
        serif: ["'Playfair Display'", "serif"],
        sans: ["'Inter'", "sans-serif"],
        display: ["'Bebas Neue'", "'Inter'", "sans-serif"],
      },
      borderRadius: {
        pill: "999px",
      },
    },
  },
  plugins: [],
};