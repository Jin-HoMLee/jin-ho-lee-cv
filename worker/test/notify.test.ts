import { describe, expect, it, vi } from "vitest";
import { notifyLead, formatLead, type NotifyLead } from "../src/notify";

const lead: NotifyLead = {
  email: "a@b.co", name: "Ada", message: "let's talk", country: "DE", msg_count: 5, ts: 100,
};

describe("formatLead", () => {
  it("includes the email and omits absent optional fields", () => {
    const text = formatLead({ ...lead, name: null, message: null });
    expect(text).toContain("a@b.co");
    expect(text).not.toContain("Name:");
    expect(text).not.toContain("Message:");
  });
});

describe("notifyLead", () => {
  it("no-ops (no fetch) when Telegram is not configured", async () => {
    const fetchMock = vi.fn();
    await notifyLead(lead, {}, fetchMock as unknown as typeof fetch);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("POSTs to the Telegram sendMessage API when configured", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true }) as unknown as Response);
    await notifyLead(lead, { TELEGRAM_BOT_TOKEN: "T", TELEGRAM_CHAT_ID: "42" }, fetchMock as unknown as typeof fetch);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.telegram.org/botT/sendMessage");
    const body = JSON.parse(String(init.body));
    expect(body.chat_id).toBe("42");
    expect(body.text).toContain("a@b.co");
  });

  it("swallows a thrown fetch (best-effort — never rejects)", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("network down");
    });
    await expect(
      notifyLead(lead, { TELEGRAM_BOT_TOKEN: "T", TELEGRAM_CHAT_ID: "42" }, fetchMock as unknown as typeof fetch),
    ).resolves.toBeUndefined();
  });

  it("handles a Telegram API-level error (resp.ok false) without throwing", async () => {
    // A bad token / chat id returns HTTP 200-or-4xx with {ok:false}; the fetch resolves,
    // so this is observability only — notifyLead must still resolve, never reject.
    const fetchMock = vi.fn(async () => ({ ok: false, status: 401 }) as unknown as Response);
    await expect(
      notifyLead(lead, { TELEGRAM_BOT_TOKEN: "T", TELEGRAM_CHAT_ID: "42" }, fetchMock as unknown as typeof fetch),
    ).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
