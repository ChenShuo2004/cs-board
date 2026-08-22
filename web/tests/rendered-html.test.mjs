import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the whiteboard video application", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<html lang="zh-CN">/i);
  assert.match(html, /<title>有温度出品<\/title>/i);
  assert.match(html, /把你的表达，画成一支会说话的白板视频/);
  assert.match(html, /上传参考音频/);
  assert.match(html, /开始生成视频/);
  assert.match(html, /API 设置/);
  assert.doesNotMatch(html, /Your site is taking shape|Building your site/);
});

test("keeps public defaults portable and free of local configuration", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /tts_url:"http:\/\/127\.0\.0\.1:7860"/);
  assert.match(page, /api_key:""/);
  assert.doesNotMatch(page, /192\.168\.|10\.\d+\.\d+\.\d+/);
  assert.match(layout, /title:\s*"有温度出品"/);
  assert.match(packageJson, /"build": "vinext build"/);
  assert.match(packageJson, /"test": "npm run build/);
});
