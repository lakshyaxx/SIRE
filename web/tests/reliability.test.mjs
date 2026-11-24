import test from "node:test";
import assert from "node:assert/strict";
import { actualSource } from "./source.mjs";

test("partial findings retain a partial title and the actual failed stage", () => {
  const { investigationNoticeTitle } = actualSource(
    "../src/pages/InvestigationWorkspace.tsx",
  );
  assert.equal(
    investigationNoticeTitle("partial", "hypotheses.quality"),
    "Partial investigation · hypotheses.quality",
  );
  assert.equal(
    investigationNoticeTitle("error", "vision.inspect"),
    "Investigation failed · vision.inspect",
  );
});

test("assumptions and expected signs are not presented as observed or missing facts", () => {
  const { presentInvestigation } = actualSource("../src/services/api.ts");
  const detail = presentInvestigation({
    id: "test-only",
    kind: "case",
    conversation_id: "test-only",
    status: "partial",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    question: "Test-only",
    evidence_count: 0,
    report: {
      case: { question: "Test-only", evidence: [] },
      hypotheses: [
        {
          id: "test-only",
          mechanism: "Test-only tentative possibility.",
          status: "tentative",
          evidence_support: "low",
          supporting_evidence_ids: [],
          contradicting_evidence_ids: [],
          assumptions: ["Test-only unverified condition"],
          expected_signs: [
            { predicate: "test-only expected signal", expected_value: true },
          ],
          missing_tests: ["Test-only independent check"],
        },
      ],
      limitations: ["Test-only limitation"],
      unresolved: ["Test-only missing input", "Test-only missing input"],
    },
  });
  assert.deepEqual(detail.hypotheses[0].missingInformation, []);
  assert.deepEqual(detail.followUps, ["Test-only missing input"]);
  assert.deepEqual(detail.hypotheses[0].assumptions, [
    "Test-only unverified condition",
  ]);
  assert.ok(
    detail.hypotheses[0].expectedSigns[0].includes("not an observed result"),
  );
});
