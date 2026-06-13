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
        'dark-obsidian': 'rgb(16 16 20 / <alpha-value>)',
        'obsidian-lighter': 'rgb(32 32 38 / <alpha-value>)',
        'void': 'rgb(16 16 20 / <alpha-value>)',
        'surface': 'rgb(24 24 28 / <alpha-value>)',
        'border-dim': 'rgb(46 46 52 / <alpha-value>)',
        'stark': 'rgb(245 245 247 / <alpha-value>)',
        'safety': 'rgb(255 69 0 / <alpha-value>)',
        'muted': 'rgb(140 140 150 / <alpha-value>)',
        'alert-bg': 'rgb(30 22 16 / <alpha-value>)',
        'alert-border': 'rgb(64 38 20 / <alpha-value>)',
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
