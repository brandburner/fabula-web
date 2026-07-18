/** Tailwind config — compiled build (ISS-021), replacing the Play CDN.
 * Rebuild after class changes:
 *   npx tailwindcss@3.4.17 -c tailwind.config.js \
 *     -i static/src/tailwind.css -o static/vendor/tailwind.css --minify
 * The compiled static/vendor/tailwind.css is committed (zero-build deploys).
 */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './narrative/templates/**/*.html',
    './narrative/static/**/*.js',
  ],
  safelist: [
    // marketing blocks compose md:grid-cols-{{ N }} from StreamField counts
    { pattern: /grid-cols-(1|2|3|4|5|6)/, variants: ['md'] },
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#0a0a0f',
        },
      },
    },
  },
};
