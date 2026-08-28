import { copyFile, mkdir } from 'node:fs/promises';
await mkdir(new URL('../app/static/vendor/', import.meta.url), { recursive: true });
await copyFile(new URL('../node_modules/chart.js/dist/chart.umd.js', import.meta.url), new URL('../app/static/vendor/chart.umd.min.js', import.meta.url));
