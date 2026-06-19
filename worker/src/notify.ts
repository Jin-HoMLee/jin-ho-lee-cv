// Phase 12c lead notification. Best-effort, behind a tiny swappable interface
// (LeadNotifier). Default backend = Telegram Bot API (free, no DNS / domain
// reputation). Graceful default: if the bot token / chat id are unset, this
// logs and no-ops — the lead is still stored (the dashboard is the backstop).
// fetchImpl is injectable for unit tests (same pattern as turnstile.ts).

export interface NotifyLead {
  email: string;
  name: string | null;
  message: string | null;
  country: string | null;
  msg_count: number | null;
  ts: number;
}

export interface NotifyEnv {
  TELEGRAM_BOT_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
}

export type LeadNotifier = (lead: NotifyLead, env: NotifyEnv, fetchImpl?: typeof fetch) => Promise<void>;

export function formatLead(lead: NotifyLead): string {
  return [
    "📇 New lead from your digital twin",
    `Email: ${lead.email}`,
    lead.name ? `Name: ${lead.name}` : null,
    lead.message ? `Message: ${lead.message}` : null,
    lead.country ? `Country: ${lead.country}` : null,
  ]
    .filter(Boolean)
    .join("\n");
}

export const notifyLead: LeadNotifier = async (lead, env, fetchImpl = fetch) => {
  const token = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) {
    console.log("notifyLead: Telegram not configured — lead stored, notification skipped");
    return;
  }
  try {
    await fetchImpl(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: formatLead(lead), disable_web_page_preview: true }),
    });
  } catch {
    // Best-effort: the lead is already in D1 and visible on the dashboard.
    console.log("notifyLead: Telegram delivery failed — lead is stored, view it on the dashboard");
  }
};
