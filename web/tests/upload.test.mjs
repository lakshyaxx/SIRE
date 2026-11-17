import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');

// Execute the actual JSX event handler, not a copy of its implementation.
function actualPickerHandler(refName, upload) {
  const source = ts.createSourceFile('Chat.tsx', readFileSync(new URL('../src/features/chat/Chat.tsx', import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let expression;
  function visit(node) {
    if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(source) === 'input') {
      const attrs = node.attributes.properties;
      const ref = attrs.find(a => a.name?.getText(source) === 'ref');
      if (ref?.initializer?.expression?.getText(source) === refName) expression = attrs.find(a => a.name?.getText(source) === 'onChange')?.initializer?.expression;
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(expression, `Actual ${refName} input has a wired change handler`);
  const javascript = ts.transpileModule(`(${expression.getText(source)})`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function('upload', `return ${javascript}`)(upload);
}

for (const picker of ['file', 'camera']) {
  test(`${picker} picker preserves selected bytes when its live FileList is cleared before async upload`, async () => {
    const original = new File(['explicit test-only file bytes'], 'test-only.txt', {type:'text/plain'});
    let selection = [original];
    const liveFiles = { get length() { return selection.length; }, *[Symbol.iterator]() { yield* selection; } };
    const input = { files:liveFiles, set value(value) { if (value === '') selection = []; } };
    const submitted = [];
    const handler = actualPickerHandler(picker, async files => {
      await Promise.resolve(); // Real upload awaits conversation creation first.
      submitted.push(...Array.from(files));
    });
    handler({target:input,currentTarget:input});
    await Promise.resolve();
    assert.equal(submitted.length, 1);
    assert.equal(await submitted[0].text(), await original.text());
    assert.equal(liveFiles.length, 0, 'Input reset permits choosing the same file again');
  });
}
