// pi-inject-memory-index.ts - pi adapter: inject the always-loaded memory
// INDEX into the session as one persistent custom message, mirroring Claude
// Code's native auto-load (and the Codex SessionStart inject hooks).
//
// pi natively loads AGENTS.md/CLAUDE.md and discovers .agents/skills, so this
// extension is the ONLY adapter code pi needs (claude-personas#104). It lands
// at .agents/hooks/lib/pi-inject-memory-index.ts via install.sh; the instance
// wires it with a one-line re-export shim in .pi/extensions/ (pi's trust-gated
// auto-discovery dir - see the pi section of docs/vendor-caveats.md).
//
// Index resolution walks up from cwd: .agents/memory/MEMORY.md (embedded and
// role clones both mount this) first, then the .claude/memory hop as a
// fallback. Role-clone parity with inject-role-index.sh: the payload carries
// the role index only, plus one-line on-demand pointers to shared/ and user/
// indexes when present.
//
// CAP - adopts Claude Code's native MEMORY.md size guard rather than an
// invented figure (~200 lines / ~25 KB, whichever first; see
// claude-personas#48/#52). Whole-line truncation with an explicit
// [TRUNCATED ...] trailer; PERSONAS_INJECT_BYTE_CAP / PERSONAS_INJECT_LINE_CAP
// override, non-numeric overrides fall back to the defaults rather than
// suppressing the index.
//
// Injection fires on before_agent_start (works in TUI, RPC, and -p print
// mode alike) and dedups against the session's existing entries, so /resume
// and later prompts never double-inject. Defensive by design: any error is
// swallowed - the extension must never break a session start.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const CUSTOM_TYPE = "personas-memory-index";
const DEFAULT_BYTE_CAP = 25000;
const DEFAULT_LINE_CAP = 200;

function capFromEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw === undefined || !/^[0-9]+$/.test(raw)) return fallback;
  return parseInt(raw, 10);
}

// Walk up from cwd to the filesystem root; first dir carrying a memory mount
// wins. .agents/memory is the vendor-neutral mount (embedded repos and role
// clones both have it); .claude/memory covers a clone wired before the
// .agents hop existed.
function findMemoryDir(startCwd: string): string | null {
  let dir = resolve(startCwd);
  for (;;) {
    for (const mount of [join(".agents", "memory"), join(".claude", "memory")]) {
      const candidate = join(dir, mount);
      if (existsSync(join(candidate, "MEMORY.md"))) return candidate;
    }
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

// Keep whole lines while BOTH the byte budget and the line cap hold - the
// same rule as the Codex inject hooks, so every adapter truncates where
// Claude Code natively would.
function boundIndex(
  text: string,
  byteCap: number,
  lineCap: number,
): { body: string; truncated: boolean } {
  const lines = text.split("\n");
  // A trailing newline yields one empty trailing element; dropping it keeps
  // line counting aligned with awk's NR in the shell siblings.
  if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
  const kept: string[] = [];
  let bytes = 0;
  for (const line of lines) {
    bytes += Buffer.byteLength(line, "utf8") + 1;
    if (bytes > byteCap || kept.length + 1 > lineCap) {
      return { body: kept.join("\n"), truncated: true };
    }
    kept.push(line);
  }
  return { body: kept.join("\n"), truncated: false };
}

function buildPayload(cwd: string): string | null {
  const memoryDir = findMemoryDir(cwd);
  if (memoryDir === null) return null;
  const indexPath = join(memoryDir, "MEMORY.md");

  const byteCap = capFromEnv("PERSONAS_INJECT_BYTE_CAP", DEFAULT_BYTE_CAP);
  const lineCap = capFromEnv("PERSONAS_INJECT_LINE_CAP", DEFAULT_LINE_CAP);

  const header = "# Memory index (auto-injected by the personas pi adapter)\n\n";
  const remaining = byteCap - Buffer.byteLength(header, "utf8");
  if (remaining <= 0) return null;

  const raw = readFileSync(indexPath, "utf8");
  const { body, truncated } = boundIndex(raw, remaining, lineCap);

  let payload = header + body + "\n";
  // Parity with inject-role-index.sh: shared and role@user indexes are loaded
  // on demand, so the payload points at them instead of inlining them, in
  // precedence order (role > shared > role@user).
  const sharedIndex = join(memoryDir, "shared", "MEMORY.md");
  if (existsSync(sharedIndex)) {
    payload += `\n# Shared memory index (loaded on demand): read ${sharedIndex}`;
  }
  const userIndex = join(memoryDir, "user", "MEMORY.md");
  if (existsSync(userIndex)) {
    payload += `\n# Role user-tier memory index (loaded on demand): read ${userIndex}`;
  }
  if (truncated) {
    payload += `\n[TRUNCATED by the pi adapter at the Claude Code native cap - read ${indexPath} for the full index]`;
  }
  return payload;
}

export default function (pi: ExtensionAPI) {
  pi.on("before_agent_start", async (_event, ctx) => {
    try {
      const alreadyInjected = ctx.sessionManager
        .getEntries()
        .some(
          (entry: { type?: string; customType?: string }) =>
            entry.type === "custom_message" && entry.customType === CUSTOM_TYPE,
        );
      if (alreadyInjected) return;

      const payload = buildPayload(ctx.cwd);
      if (payload === null) return;

      return {
        message: {
          customType: CUSTOM_TYPE,
          content: payload,
          display: false,
        },
      };
    } catch {
      // Never break a session start over a memory index.
      return;
    }
  });
}
