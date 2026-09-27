// index.html と lessons.js の構造テスト。node tests/app.test.cjs
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const lessonsJs = fs.readFileSync(path.join(root, 'lessons.js'), 'utf8');

// lessons.js が読めて、hash が index.html の ?v= と一致する
const ctx = { window: {} };
vm.runInNewContext(lessonsJs, ctx);
const D = ctx.window.LESSONS;
assert.ok(D && Array.isArray(D.lessons) && D.lessons.length > 0, 'lessons.js に lessons が無い');
const v = html.match(/lessons\.js\?v=(\w+)/)?.[1];
assert.equal(v, D.hash, 'index.html の lessons.js?v= が lessons.js の hash と一致しない（build_lessons.py を実行）');

// アプリ JS が構文エラーなく読める
const appJs = html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/)?.[1];
assert.ok(appJs, 'アプリ JS が見つからない');
new vm.Script(appJs);

// レッスンの整合性: 課題 ID の重複なし、scored の予測/クイズに answer がある、steps の最終行数が rowCount の answer と一致
const ids = new Set();
for (const l of D.lessons) {
  assert.ok(D.levels.some(lv => lv.id === l.level), `${l.id}: level ${l.level} が levels.yaml に無い`);
  for (const t of l.tasks) {
    assert.ok(!ids.has(t.id), `課題 ID 重複 ${t.id}`); ids.add(t.id);
    if (t.type === 'predict') {
      assert.ok(t.steps && t.steps.length, `${t.id}: steps が無い`);
      if (t.ask === 'rowCount') assert.equal(t.steps.at(-1).rows.length, t.answer, `${t.id}: rowCount 不一致`);
    }
    if (t.type === 'quiz') assert.ok(Number.isInteger(t.answer) && t.answer < t.choices.length, `${t.id}: quiz answer 不正`);
  }
}

// 用語辞書: 全項目に ja がある
for (const [k, g] of Object.entries(D.glossary)) assert.ok(g.ja, `glossary ${k} に ja が無い`);

// CDN 依存が無い（file:// オフラインで動く前提）
assert.ok(!/https?:\/\/[^"']+\.(js|css)/.test(html), 'index.html が外部 js/css を参照している');

console.log(`OK: ${D.lessons.length} レッスン / ${ids.size} 課題`);
