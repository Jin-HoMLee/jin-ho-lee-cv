// Minimal, escape-first markdown renderer for the twin chat bubbles (#120).
//
// Gemini answers often arrive as markdown (bold labels, bullet lists); the widget
// used to insert them as textContent, so visitors saw literal ** and * artifacts.
// This renders just the handful of constructs models actually emit - bold, italic,
// inline code, bullet lists, #-headings - and nothing else. No library, no options.
//
// XSS: the answer text is model output, i.e. untrusted (same class of care as the
// #113 </script> breakout). The pipeline is escape-FIRST: every HTML metacharacter
// is neutralized before any transform runs, and the transforms only ever wrap
// already-escaped text in a fixed set of literal tags (<strong>, <em>, <code>,
// <ul>, <li>) with no attributes. Hostile input can therefore only ever appear as
// visible text.
//
// Streaming: the widget re-renders the accumulated buffer on every SSE chunk, so
// this function must be safe on fragments. An unclosed marker (e.g. "**Fin")
// simply doesn't match and stays literal until the closing chunk arrives.
//
// Newlines: the bubble uses `white-space: pre-wrap`, so plain newlines are kept
// literal instead of becoming <br>. List blocks swallow their surrounding
// newlines - <ul> is block-level and provides its own separation, and a leftover
// "\n" next to it would double-space under pre-wrap.

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}

// Inline transforms over already-escaped text. Order matters: code first (so its
// content is captured whole), then bold before italic (so ** isn't eaten as two
// italics). Bold/italic require non-space content edges, which keeps free-standing
// asterisks ("3 * 4") literal - same rule real markdown uses.
function inline(escaped: string): string {
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(\S(?:[^*]*\S)?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(\S(?:[^*]*\S)?)\*/g, "<em>$1</em>");
}

const LIST_ITEM = /^ {0,3}[-*] +(.*)$/;
const HEADING = /^ {0,3}#{1,6} +(.*)$/;

export function renderMarkdown(source: string): string {
  const lines = escapeHtml(source).split("\n");
  let html = "";
  let pendingNewline = false; // separator owed to the previous plain line
  let items: string[] = [];

  const flushList = (): void => {
    if (items.length === 0) return;
    html = html.replace(/\n+$/, ""); // the <ul> block replaces adjacent newlines
    html += `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;
    items = [];
    pendingNewline = false;
  };

  for (const line of lines) {
    const item = LIST_ITEM.exec(line);
    if (item) {
      items.push(inline(item[1]));
      continue;
    }
    flushList();
    const heading = HEADING.exec(line);
    const rendered = heading ? `<strong>${inline(heading[1])}</strong>` : inline(line);
    if (pendingNewline) html += "\n";
    html += rendered;
    pendingNewline = true;
  }
  flushList();
  return html.replace(/\n+$/, "");
}
