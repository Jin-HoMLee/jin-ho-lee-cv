export interface SystemBlock {
  type: "text";
  text: string;
  cache_control?: { type: "ephemeral" };
}

export function wrapContext(cv: string): string {
  return `<cv_context>\n${cv}\n</cv_context>`;
}

// system = [persona, cached context]. Marking the large, static context block as
// ephemeral-cacheable means it's paid in full once then read at ~10% on cache hits.
export function buildSystemPrompt(persona: string, cv: string): SystemBlock[] {
  return [
    { type: "text", text: persona },
    { type: "text", text: wrapContext(cv), cache_control: { type: "ephemeral" } },
  ];
}
