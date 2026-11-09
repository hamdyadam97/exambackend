const fs = require('fs');
const path = require('path');

const vendorDir = path.join(__dirname, '../static/admin/vendor');
if (!fs.existsSync(vendorDir)) {
  fs.mkdirSync(vendorDir, { recursive: true });
}

const files = [
  ['htmx.org/dist/htmx.min.js', 'htmx.min.js'],
  ['alpinejs/dist/cdn.min.js', 'alpine.min.js'],
  ['chart.js/dist/chart.umd.js', 'chart.js'],
];

for (const [src, dest] of files) {
  const srcPath = path.join(__dirname, 'node_modules', src);
  const destPath = path.join(vendorDir, dest);
  if (!fs.existsSync(srcPath)) {
    console.warn(`Missing vendor source: ${srcPath}`);
    continue;
  }
  // Source maps are not shipped; a dangling sourceMappingURL makes collectstatic
  // (whitenoise manifest storage) fail with MissingFileError.
  const code = fs.readFileSync(srcPath, 'utf8').replace(/\n\/\/# sourceMappingURL=.*\s*$/, '\n');
  fs.writeFileSync(destPath, code);
  console.log(`Copied ${src} -> ${destPath}`);
}
