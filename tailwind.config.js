/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./templates/**/*.jinja",
    "./templates/**/*.jinja2",
  ],
  theme: {
    extend: {
      colors: {
        'neon-orange': 'rgb(255 69 0 / <alpha-value>)',
        'neon-orange-light': 'rgb(255 106 51 / <alpha-value>)',
        'soft-blue': 'rgb(143 179 255 / <alpha-value>)',
        'dark-obsidian': 'rgb(0 0 0 / <alpha-value>)',
        'obsidian-lighter': 'rgb(17 17 17 / <alpha-value>)',
        'void': 'rgb(0 0 0 / <alpha-value>)',
        'surface': 'rgb(2 2 2 / <alpha-value>)',
        'border-dim': 'rgb(24 24 27 / <alpha-value>)',
        'stark': 'rgb(255 255 255 / <alpha-value>)',
        'safety': 'rgb(255 69 0 / <alpha-value>)',
        'muted': 'rgb(113 113 122 / <alpha-value>)',
        'alert-bg': 'rgb(26 18 12 / <alpha-value>)',
        'alert-border': 'rgb(58 32 16 / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Figtree', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        brutal: ['Oswald', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
