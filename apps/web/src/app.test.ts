// @vitest-environment jsdom
import { act } from "react";
import { expect, it, vi } from "vitest";

it("polls a paper run and opens a citation from the published version", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  document.body.innerHTML = '<div id="root"></div>';
  const base = "/api/v1/reviews";
  const run = { id: "test-run", status: "queued", mode: "paper", question: "Dataset coverage" };
  const citation = { passage_id: "passage-1", locator: "Paragraph 2", quote: "Exact text", char_start: 2, char_end: 12 };
  let polls = 0;
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    if (path === base && options?.method === "POST") {
      expect(new Headers(options.headers).get("Idempotency-Key")).toBeTruthy();
      expect((options.body as FormData).get("text")).toBe("Submitted fixture text.");
      return Response.json(run);
    }
    if (path === base) return Response.json([]);
    if (path === `${base}/test-run`) return Response.json(++polls === 1
      ? { ...run, status: "reviewing", stage: "methodology", activity: "Retrying in 45 seconds." }
      : { ...run, status: "completed", report_version: 1 });
    const final = { id: "finding-1", role: "Dataset & Evidence", category: "strength", assessment: "Two datasets were evaluated.", status: "supported", citations: [citation] };
    if (path.endsWith("/report?version=1")) return Response.json({
      version: 1, summary: "Three reviews saved.", coverage: "no_results", prioritized_revisions: [],
      findings: [final],
      critique: [{
        original: { ...final, assessment: "The results generalize across datasets." }, final,
        challenge: "The study only covers two datasets.", reply_action: "revise",
        reply_reason: "Narrowed the assessment to the observed scope.", disposition: "revised",
      }],
    });
    if (path.endsWith("/passages/passage-1?version=1")) return Response.json({
      passage: { title: "Submission", locator: "Paragraph 2", text: "Exact text follows.", char_start: 2, url: "" },
    });
    throw new Error(`Unexpected fixture request ${path}`);
  }));
  try {
    await act(async () => { await import("./main"); });
    const form = document.querySelector("form")!;
    form.querySelector("textarea")!.value = "Submitted fixture text.";
    await act(async () => { form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    expect(document.querySelector('header [role="status"]')?.textContent).toBe("Queued");
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(document.querySelector('[aria-current="step"]')?.textContent).toContain("Review methodology");
    expect(document.querySelector('.review-progress [role="status"]')?.textContent).toBe("Retrying in 45 seconds.");
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(document.querySelector('header [role="status"]')?.textContent).toBe("Completed");
    expect(document.querySelector('a[href$="/report.json?version=1"]')).not.toBeNull();
    expect(document.querySelector('a[href$="/report.md?version=1"]')).not.toBeNull();
    const critique = document.querySelector('[aria-label="Finding before and after critique"]');
    expect(critique?.textContent).toContain("The results generalize across datasets.");
    expect(critique?.textContent).toContain("Two datasets were evaluated.");
    expect(critique?.textContent).toContain("revised");
    await act(async () => { document.querySelector<HTMLButtonElement>(".citation")!.click(); });
    expect(document.querySelector("mark")?.textContent).toBe("Exact text");
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Cited passage");
  } finally {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  }
});

