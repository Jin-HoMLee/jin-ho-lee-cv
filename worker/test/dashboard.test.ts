import { describe, expect, it } from "vitest";
import { escapeHtml, renderDashboard } from "../src/dashboard";

describe("escapeHtml", () => {
  it("escapes HTML-significant characters", () => {
    expect(escapeHtml(`<script>"&'`)).toBe("&lt;script&gt;&quot;&amp;&#39;");
  });
});

describe("renderDashboard", () => {
  const base = {
    digest: { id: 1, ts: 1_700_000_000, markdown: "## Theme A\n3 questions", n_questions: 3 },
    monthCount: 142,
    ceiling: 5000,
    questions: [
      { id: 2, ts: 1_700_000_500, text: "what is your salary?", country: "DE", msg_count: 2 },
    ],
    leads: [
      { id: 1, ts: 1_700_000_900, email: "ada@example.com", name: "Ada", message: "let's chat", country: "GB", consent: 1, msg_count: 5 },
    ],
  };

  it("shows the usage counter as N / ceiling and labels it a rolling window", () => {
    const html = renderDashboard(base);
    expect(html).toContain("142");
    expect(html).toContain("5000");
    expect(html.toLowerCase()).toContain("current window");
  });

  it("renders the latest digest markdown in a pre block", () => {
    const html = renderDashboard(base);
    expect(html).toContain("<pre");
    expect(html).toContain("Theme A");
  });

  it("escapes untrusted question text (no raw script tag survives)", () => {
    const html = renderDashboard({
      ...base,
      questions: [{ id: 3, ts: 1, text: "<script>alert(1)</script>", country: null, msg_count: 1 }],
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("handles no digest yet without throwing", () => {
    const html = renderDashboard({ ...base, digest: null });
    expect(html.toLowerCase()).toContain("no digest");
  });

  it("renders a Leads section with the email as a mailto link", () => {
    const html = renderDashboard(base);
    expect(html.toLowerCase()).toContain("leads");
    expect(html).toContain('href="mailto:ada@example.com"');
    expect(html).toContain("Ada");
    expect(html).toContain("let&#39;s chat"); // escaped apostrophe
  });

  it("escapes an untrusted lead email/name (no raw script survives)", () => {
    const html = renderDashboard({
      ...base,
      leads: [{ id: 9, ts: 1, email: "x@y.co", name: "<script>alert(1)</script>", message: null, country: null, consent: 1, msg_count: null }],
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("handles no leads yet without throwing", () => {
    const html = renderDashboard({ ...base, leads: [] });
    expect(html.toLowerCase()).toContain("no leads");
  });
});
