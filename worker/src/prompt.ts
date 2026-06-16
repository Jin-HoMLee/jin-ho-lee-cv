export function wrapContext(cv: string): string {
  return `<cv_context>\n${cv}\n</cv_context>`;
}

// Gemini takes a single system-instruction string (no per-block cache_control on
// the free tier). Persona first, then the delimited CV context.
export function buildSystemText(persona: string, cv: string): string {
  return persona + "\n\n" + wrapContext(cv);
}
