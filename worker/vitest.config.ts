import { defineConfig } from "vitest/config";

// The Worker imports the generated chat-context.md as a text module (Wrangler's
// build handles .md text imports natively). Under Vitest/Vite that file doesn't
// exist (it's produced at deploy time) and Markdown isn't valid JavaScript, so
// resolve any *.md import to a virtual module exporting a placeholder string.
// The guardrail/prompt logic under test never depends on the real CV blob.
export default defineConfig({
  plugins: [
    {
      name: "md-stub",
      enforce: "pre",
      resolveId(source) {
        if (source.endsWith(".md")) return `\0md-stub:${source}`;
        return null;
      },
      load(id) {
        if (id.startsWith("\0md-stub:")) {
          return `export default ${JSON.stringify("PLACEHOLDER CV CONTEXT")};`;
        }
        return null;
      },
    },
  ],
});
