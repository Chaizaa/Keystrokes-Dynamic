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
        'neon-orange': '#FF4500',
        'neon-orange-light': '#FF6A33',
        'soft-blue': '#8fb3ff',
        'dark-obsidian': '#000000',
        'obsidian-lighter': '#111111',
      },
      fontFamily: {
        sans: ['system-ui', 'sans-serif'],
        mono: ['Monaco', 'Courier New', 'monospace'],
        brutal: ['Oswald', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
