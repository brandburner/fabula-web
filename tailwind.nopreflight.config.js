/** No-preflight Tailwind build for marketing_base.html / catalog_base.html —
 * they layer utilities over the v2 site.css primitives, so Tailwind's reset
 * must stay off. Same content/theme as tailwind.config.js.
 * Rebuild:
 *   npx tailwindcss@3.4.17 -c tailwind.nopreflight.config.js \
 *     -i static/src/tailwind.css -o static/vendor/tailwind-nopreflight.css --minify
 */
const base = require('./tailwind.config.js');

module.exports = {
  ...base,
  corePlugins: { preflight: false },
};
