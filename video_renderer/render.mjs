import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {fileURLToPath} from 'node:url';

const [propsPath, outputPath, publicDir] = process.argv.slice(2);
if (!propsPath || !outputPath || !publicDir) {
  throw new Error('用法：node render.mjs <props.json> <output.mp4> <job-public-dir>');
}

const rendererRoot = path.dirname(fileURLToPath(import.meta.url));
const inputProps = JSON.parse(fs.readFileSync(propsPath, 'utf8'));
const platformBrowserCandidates = process.platform === 'darwin'
  ? [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ]
  : process.platform === 'win32'
    ? [
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
      ]
    : [
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
      ];
const browserCandidates = [
  process.env.REMOTION_BROWSER_EXECUTABLE,
  ...(process.env.REMOTION_USE_SYSTEM_BROWSER === '0' ? [] : platformBrowserCandidates),
].filter(Boolean);
const browserExecutable = browserCandidates.find((candidate) => fs.existsSync(candidate));

const serveUrl = await bundle({
  entryPoint: path.join(rendererRoot, 'src', 'index.tsx'),
  rootDir: rendererRoot,
  publicDir: path.resolve(publicDir),
  webpackOverride: (configuration) => configuration,
});
const rendererOptions = browserExecutable ? {browserExecutable} : {};
const composition = await selectComposition({
  serveUrl,
  id: 'DynamicInfographic',
  inputProps,
  logLevel: 'warn',
  timeoutInMilliseconds: 120000,
  ...rendererOptions,
});
await renderMedia({
  serveUrl,
  composition,
  inputProps,
  codec: 'h264',
  outputLocation: path.resolve(outputPath),
  muted: true,
  crf: 19,
  pixelFormat: 'yuv420p',
  x264Preset: 'medium',
  concurrency: '50%',
  overwrite: true,
  logLevel: 'warn',
  timeoutInMilliseconds: 120000,
  ...rendererOptions,
});
