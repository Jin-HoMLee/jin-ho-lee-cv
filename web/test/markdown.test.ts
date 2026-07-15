import { describe, expect, it } from "vitest";
import { escapeHtml, renderMarkdown } from "../src/lib/markdown";

// The complete set of tags the renderer is allowed to emit. Stripping exactly
// these from the output must leave no angle bracket behind - anything else
// would be unescaped model-controlled HTML reaching innerHTML.
const ALLOWED_TAGS = /<\/?(strong|em|ul|li|code)>/g;
function expectOnlySafeTags(html: string): void {
  expect(html.replace(ALLOWED_TAGS, "")).not.toMatch(/[<>]/);
}

describe("escapeHtml", () => {
  it("escapes every HTML metacharacter", () => {
    expect(escapeHtml(`&<>"'`)).toBe("&amp;&lt;&gt;&quot;&#39;");
  });

  it("leaves plain text untouched", () => {
    expect(escapeHtml("splice neoepitope pipeline")).toBe("splice neoepitope pipeline");
  });
});

describe("renderMarkdown: supported constructs", () => {
  it("renders **bold** as <strong>", () => {
    expect(renderMarkdown("I built **pipelines** at scale")).toBe(
      "I built <strong>pipelines</strong> at scale",
    );
  });

  it("renders *italic* as <em>", () => {
    expect(renderMarkdown("a *subtle* point")).toBe("a <em>subtle</em> point");
  });

  it("renders `inline code` as <code>", () => {
    expect(renderMarkdown("run `just validate` first")).toBe(
      "run <code>just validate</code> first",
    );
  });

  it("renders * bullets as a <ul> (the exact shape from issue #120)", () => {
    expect(renderMarkdown("* **Fintech & Consulting:** BI work\n* **Research:** RNA-seq")).toBe(
      "<ul><li><strong>Fintech &amp; Consulting:</strong> BI work</li>" +
        "<li><strong>Research:</strong> RNA-seq</li></ul>",
    );
  });

  it("renders - bullets as a <ul> too", () => {
    expect(renderMarkdown("- one\n- two")).toBe("<ul><li>one</li><li>two</li></ul>");
  });

  it("renders # headings as <strong> lines (no raw # artifacts)", () => {
    const out = renderMarkdown("## Experience\nI led the team");
    expect(out).toBe("<strong>Experience</strong>\nI led the team");
    expect(out).not.toContain("#");
  });

  it("keeps plain newlines literal (bubble uses white-space: pre-wrap)", () => {
    expect(renderMarkdown("first line\nsecond line")).toBe("first line\nsecond line");
  });

  it("does not leave stray newlines around a <ul> (pre-wrap would double-space)", () => {
    expect(renderMarkdown("Two areas:\n* one\n* two\nThat's it")).toBe(
      "Two areas:<ul><li>one</li><li>two</li></ul>That&#39;s it",
    );
    expect(renderMarkdown("Two areas:\n\n* one\n* two")).toBe(
      "Two areas:<ul><li>one</li><li>two</li></ul>",
    );
  });

  it("leaves free-standing asterisks (math, footnotes) alone", () => {
    expect(renderMarkdown("3 * 4 * 5")).toBe("3 * 4 * 5");
  });
});

describe("renderMarkdown: streaming fragments", () => {
  it("renders an unclosed **bold literally instead of crashing or mangling", () => {
    expect(renderMarkdown("**Fin")).toBe("**Fin");
  });

  it("resolves once the closing marker arrives in a later chunk (re-render of the buffer)", () => {
    const partial = renderMarkdown("* **Fin");
    expect(partial).toBe("<ul><li>**Fin</li></ul>");
    const complete = renderMarkdown("* **Fintech:** consulting");
    expect(complete).toBe("<ul><li><strong>Fintech:</strong> consulting</li></ul>");
  });
});

describe("renderMarkdown: XSS safety against hostile model output", () => {
  const payloads = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "</script><script>alert(1)</script>",
    "<ScRiPt>alert(1)</ScRiPt>",
    '<a href="javascript:alert(1)">click</a>',
    "**<script>alert(1)</script>**",
    "*<img src=x onerror=alert(1)>*",
    "`<script>alert(1)</script>`",
    "* <script>alert(1)</script>",
    "# <svg onload=alert(1)>",
    '" onmouseover="alert(1)',
  ];

  for (const payload of payloads) {
    it(`neutralizes: ${payload}`, () => {
      const out = renderMarkdown(payload);
      expectOnlySafeTags(out);
      expect(out.toLowerCase()).not.toContain("<script");
      expect(out.toLowerCase()).not.toContain("<img");
      expect(out.toLowerCase()).not.toContain("<svg");
      expect(out.toLowerCase()).not.toContain("<a ");
    });
  }

  it("keeps the hostile payload visible as escaped text inside the styling tags", () => {
    expect(renderMarkdown("**<script>alert(1)</script>**")).toBe(
      "<strong>&lt;script&gt;alert(1)&lt;/script&gt;</strong>",
    );
  });

  it("never emits attributes, so quote injection has nowhere to land", () => {
    const out = renderMarkdown('*a" onmouseover="alert(1)*');
    expect(out).not.toContain('"');
    expectOnlySafeTags(out);
  });
});
