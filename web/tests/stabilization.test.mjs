import test from 'node:test';
import assert from 'node:assert/strict';
import { actualSource } from './source.mjs';

test('a late running snapshot cannot revive a cancelled or complete job', () => {
  const { acceptJobUpdate } = actualSource('../src/features/chat/BackgroundInvestigation.tsx');
  for (const status of ['complete', 'cancelled', 'error', 'partial', 'interrupted']) {
    const terminal = { id:'test-only', status, updated_at:'2026-01-01T02:00:00Z' };
    assert.equal(acceptJobUpdate(terminal, { id:'test-only', status:'running', updated_at:'2026-01-01T03:00:00Z' }), terminal);
  }
  const current = { id:'test-only', status:'running', updated_at:'2026-01-01T02:00:00Z' };
  assert.equal(acceptJobUpdate(current, { ...current, updated_at:'2026-01-01T01:00:00Z' }), current);
  assert.equal(acceptJobUpdate(current, { ...current, status:'complete' }).status, 'complete');
});
