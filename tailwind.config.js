/** @type {import('tailwindcss').Config} */
module.exports = {

  // Site toggles dark mode via <html class="dark-mode"> (see theme.js),
  // so Tailwind's dark: variant needs to match that selector instead of
  // its default .dark class.
  darkMode: ['selector', '.dark-mode'],
  // site.css already ships its own base reset (body/a/button/input/ul...)
  // and its own .container class with different breakpoints. Tailwind's
  // Preflight and its built-in "container" utility redefine those same
  // selectors, and since output.css loads AFTER site.css, Tailwind's
  // rules were silently winning the cascade for any property both files
  // set. Turning these two core plugins off stops Tailwind from
  // generating them at all, so there's only ever one definition of each.

  corePlugins: {
    preflight: false,
    container: false,
  },
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",


    "./static/vendor/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        wine: {

          50: "#fbf3f4",

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

          50: "#fdf8f8",

          100: "#faf1f2",
          200: "#f3e4e7",
        },
      },
      fontFamily: {
        serif: ["'Cormorant Garamond'", "Georgia", "serif"], // Playfair was never loaded in base.html
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

content: [
  "./templates/**/*.html",
  "./apps/**/templates/**/*.html",
  "./apps/**/*.py",   
  "./static/vendor/js/**/*.js",
]

