import type { DigestRow, QuestionRow } from "./insights";
import type { LeadRow } from "./leads";

// Visitor question text is untrusted — escape before rendering into the page.
export function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

// Self-contained, server-rendered dashboard. No Astro, no markdown dependency:
// the digest markdown is shown verbatim in a <pre> (honest, zero new dep). This
// route is private (Cloudflare Access) and intentionally off the public site
// surface — never in the sitemap / llms.txt / CNAME.
export function renderDashboard(data: {
  digest: DigestRow | null;
  monthCount: number;
  ceiling: number;
  questions: QuestionRow[];
  leads: LeadRow[];
}): string {
  const { digest, monthCount, ceiling, questions, leads } = data;

  const digestBlock = digest
    ? `<pre style="white-space:pre-wrap;background:#11151d;border:1px solid #272d39;border-radius:10px;padding:1rem;color:#e8eaed">${escapeHtml(
        digest.markdown,
      )}</pre><p style="color:#99a0ac;font-size:.85rem">covering ${String(
        digest.n_questions,
      )} question(s), generated ${fmtTime(
        digest.ts,
      )}</p>`
    : `<p style="color:#99a0ac">No digest yet — the cron will write the first one on its next run.</p>`;

  const leadRows = leads
    .map(
      (l) =>
        `<tr><td style="padding:6px 10px;border-bottom:1px solid #272d39"><a style="color:#7aa2f7" href="mailto:${escapeHtml(
          l.email,
        )}">${escapeHtml(l.email)}</a></td><td style="padding:6px 10px;border-bottom:1px solid #272d39">${escapeHtml(
          l.name ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${escapeHtml(
          l.message ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${escapeHtml(
          l.country ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${fmtTime(
          l.ts,
        )}</td></tr>`,
    )
    .join("");

  const leadsBlock = leads.length
    ? `<table><thead><tr><th>Email</th><th>Name</th><th>Message</th><th>Country</th><th>Time</th></tr></thead><tbody>${leadRows}</tbody></table>`
    : `<p style="color:#99a0ac">No leads yet — opted-in contact details will appear here.</p>`;

  const rows = questions
    .map(
      (q) =>
        `<tr><td style="padding:6px 10px;border-bottom:1px solid #272d39">${escapeHtml(
          q.text,
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${escapeHtml(
          q.country ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${fmtTime(
          q.ts,
        )}</td></tr>`,
    )
    .join("");

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<title>Twin insights</title>
<style>body{margin:0;background:#0c0e13;color:#e8eaed;font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;padding:2rem;max-width:900px;margin:0 auto}h1{font-size:1.3rem}table{width:100%;border-collapse:collapse;font-size:.9rem}th{text-align:left;padding:6px 10px;color:#99a0ac;border-bottom:1px solid #272d39}</style>
</head><body>
<h1>🤖 Twin insights</h1>
<p>Usage this <strong>current window</strong> (rolling ~31-day): <strong>${monthCount}</strong> / ${ceiling}</p>
<h2>Latest digest</h2>
${digestBlock}
<h2>📇 Leads (${leads.length})</h2>
${leadsBlock}
<h2>Recent questions (${questions.length})</h2>
<table><thead><tr><th>Question</th><th>Country</th><th>Time</th></tr></thead><tbody>${rows}</tbody></table>
</body></html>`;
}
