# Answer-Engine Optimization (AEO) for the CV site + digital twin

Deep-research report - generated 2026-07-01 (Claude Code `deep-research` workflow).

Scope: AEO for a public personal CV website + CV-grounded digital-twin chatbot, for an academic-to-industry bioinformatics / data-science job seeker (Mannheim, DE), 2026.

Method: fan-out web search across 5 angles, then fetch + claim-extraction, then 3-vote adversarial verification (2 of 3 refutes kills a claim), then synthesis.
The Verify phase required 3 resumes to clear a transient rate-limit; the load-bearing crawler and llms.txt claims were additionally hand-verified against primary sources.

## Executive summary

In 2026 the major AI answer engines discover and cite personal sites through documented, robots.txt-controllable crawlers that split cleanly into three functional roles: training crawlers (GPTBot, ClaudeBot, Google-Extended token, CCBot), search-indexing/citation crawlers (OAI-SearchBot, PerplexityBot, Googlebot for AI Overviews, Claude-SearchBot), and real-time user-initiated fetchers (ChatGPT-User, Perplexity-User, Claude-User).
The single highest-leverage, lowest-effort move is to ensure the search/citation and user-fetch crawlers are explicitly allowed in robots.txt while blocking training crawlers is optional and harmless to citation traffic; blocking a training bot does NOT remove you from ChatGPT/Perplexity/Gemini answers because those use different user-agents. llms.txt is verifiably NOT consumed by any major answer engine as of April-May 2026 (John Mueller: "no AI system currently uses llms.txt"; 97% of domains with valid llms.txt got zero requests) - it is a symbolic gesture whose only real use is developer tooling, so it should be kept as cheap insurance but never relied upon.
Because these AI crawlers do not execute JavaScript (a 500M-fetch Vercel/MERJ study found zero JS execution), server-rendered HTML is mandatory - the site's Astro SSG output is already the correct mitigation, and schema.org/entity signals plus a JS-free content layer for the twin's underlying facts are what actually get captured.
For a Germany-based bilingual job seeker the practical priorities are: keep content in initial HTML, allow the citation/user crawlers, strengthen entity disambiguation (sameAs to ORCID/Google Scholar/GitHub/LinkedIn), and treat llms.txt as optional.

## Verified findings

### 1. OpenAI runs three functionally distinct, independently robots.txt-controllable crawlers: GPTBot (training, token GPTBot/1.3, safely blockable), OAI-SearchBot (surfaces/cites sites in ChatGPT search, token OAI-SearchBot/1.3 - must be ALLOWED to appear in ChatGPT search answers), and ChatGPT-User (real-time user-initiated fetch, token ChatGPT-User/1.0, highest-intent; robots.txt 'may not apply' because user-initiated). OpenAI publishes per-crawler IP allowlists (gptbot.json, searchbot.json, chatgpt-user.json, adsbot.json).

- **Confidence:** high  |  **Vote:** 3-0 (merged claims 0,1,2,7,11,14)
- **Evidence:**
  OpenAI primary docs give exact UA strings and state sites opted out of OAI-SearchBot 'will not be shown in ChatGPT search answers,' while GPTBot governs only training and ChatGPT-User is user-initiated ('robots.txt rules may not apply').
  Four IP JSON allowlists return HTTP 200 live.
  Actionable: allow OAI-SearchBot + ChatGPT-User; blocking GPTBot is optional and does not harm citations.
- **Sources:** <https://developers.openai.com/api/docs/bots>, <https://momenticmarketing.com/blog/ai-search-crawlers-bots>, <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>

### 2. Anthropic runs three parallel crawlers: ClaudeBot (training, blockable via User-agent: ClaudeBot / Disallow: / placed top-level and repeated per subdomain), Claude-SearchBot (search-result quality/retrieval), and Claude-User (real-time answers to individual Claude users). All honor robots.txt industry-standard directives (and the non-standard Crawl-delay); Anthropic publishes verification IPs at claude.com/crawling/bots.json but warns IP-blocking is an unreliable opt-out.

- **Confidence:** high  |  **Vote:** 3-0 (merged claims 3,4,15,16)
- **Evidence:**
  Anthropic's official Help Center article #8896518 confirms all three bots verbatim, the exact block directive, per-subdomain placement, robots.txt+Crawl-delay honoring, and the bots.json IP list with the IP-blocking-unreliable warning.
  Mirror of OpenAI's training/search/user split - same actionable pattern: allow the search + user bots, optionally block ClaudeBot.
- **Sources:** <https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler>, <https://nohacks.co/blog/ai-user-agents-landscape-2026>

### 3. Google separates the crawling bot from the AI-training control token: Googlebot serves both standard search indexing AND AI Overviews (same robots rules, live index), while Google-Extended is ONLY a robots.txt control token governing Gemini training + grounding - it has no separate HTTP user-agent string and does NOT affect Search ranking/inclusion. Applebot-Extended is analogously a training-only control token that does not affect Spotlight/Siri.

- **Confidence:** high  |  **Vote:** 3-0 (merged claims 8,12,17)
- **Evidence:**
  Google's own crawler docs: 'Google-Extended doesn't have a separate HTTP request user agent string... used in a control capacity' and 'does not impact a site's inclusion in Google Search nor is it used as a ranking signal.' AI Overviews draw from the live Googlebot-crawled index.
  Actionable: to appear in AI Overviews, keep Googlebot allowed; Google-Extended is an optional training opt-out only.
- **Sources:** <https://momenticmarketing.com/blog/ai-search-crawlers-bots>, <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>, <https://nohacks.co/blog/ai-user-agents-landscape-2026>

### 4. Perplexity distinguishes PerplexityBot (builds the search index / surfaces+links sites, not used for foundation-model training) from Perplexity-User (user-click citation fetch, treated as human-triggered and generally ignores robots.txt). However, Cloudflare de-listed Perplexity from its Verified Bots program in August 2025 for using stealth undeclared crawlers to evade robots.txt directives, so Perplexity's stated compliance is not fully trustworthy.

- **Confidence:** high  |  **Vote:** 3-0 (merged claims 18,19)
- **Evidence:**
  Perplexity's docs define the two agents and note Perplexity-User 'generally ignores robots.txt.' Cloudflare's Aug 4 2025 blog ('Perplexity is using stealth, undeclared crawlers') and independent outlets confirm de-listing for evasion.
  Implication: robots.txt is not a reliable way to control Perplexity either direction; allowing it is low-effort for citation exposure.
- **Sources:** <https://momenticmarketing.com/blog/ai-search-crawlers-bots>, <https://nohacks.co/blog/ai-user-agents-landscape-2026>

### 5. The functional taxonomy is consistent across vendors and is the core actionable insight: blocking TRAINING crawlers (GPTBot, ClaudeBot, CCBot, or setting Google-Extended/Applebot-Extended) does NOT reduce retrieval/citation traffic, which flows through separate search-index and user-fetch agents under independent robots.txt control. robots.txt itself is voluntary (REP/RFC 9309), not legally binding; reputable crawlers comply but user-initiated fetchers may not.

- **Confidence:** high  |  **Vote:** 3-0 (merged claims 6,9,10)
- **Evidence:**
  Cross-vendor primary docs confirm independent user-agent tokens per function.
  Cloudflare Jan-2026 scale data: Googlebot reaches 1.70x more unique URLs than ClaudeBot and 167x more than PerplexityBot - traditional search crawling still vastly outstrips AI crawlers, so classic SEO/indexing remains the dominant discovery path feeding AI Overviews.
- **Sources:** <https://nohacks.co/blog/ai-user-agents-landscape-2026>, <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>, <https://momenticmarketing.com/blog/ai-search-crawlers-bots>, <https://developers.openai.com/api/docs/bots>

### 6. llms.txt is NOT consumed by any major AI answer engine as of April-May 2026 - it is a symbolic gesture, not an operational control. No major LLM vendor (OpenAI, Anthropic, Google, Perplexity, Meta, Mistral) documents reading external llms.txt; they publish their own but have not committed to parsing others'. Real-world usage is confined to developer tooling (Cursor, Claude Code, Copilot fetching docs). Claims that Anthropic/Perplexity 'confirmed' llms.txt support trace to an AEO vendor with no citations.

- **Confidence:** high  |  **Vote:** 3-0 (merged claims 5,13)
- **Evidence:**
  John Mueller (Google, June 2025): 'no AI system currently uses llms.txt' (compared it to the discredited keywords meta tag).
  A 90-day study: of ~500M AI bot visits only 408 hit llms.txt; 97% of ~38,000 domains with valid llms.txt got ZERO requests in May 2026.
  The only demonstrable surfacing is Google INDEXING the files (like any page), not answer-engine consumption.
  Actionable: keep the existing llms.txt as near-zero-cost insurance, but do not invest further or rely on it.
- **Sources:** <https://nohacks.co/blog/ai-user-agents-landscape-2026>, <https://www.wix.com/studio/ai-search-lab/llms-txt-myths>

### 7. AI crawlers do not execute JavaScript, so any content requiring client-side JS rendering may not be captured - server-rendered HTML is mandatory for AI visibility. This directly validates the site's Astro SSG architecture (content in initial HTML) and implies the digital-twin's underlying CV facts should be available as static HTML/structured data, not only via a JS widget or a Worker API.

- **Confidence:** high  |  **Vote:** 3-0 (claim 21)
- **Evidence:**
  A joint Vercel/MERJ analysis of 500M+ GPTBot fetches found zero evidence of JS execution; corroborated for ClaudeBot and PerplexityBot (they fetch .js files but do not run them).
  Googlebot's WRS does render JS, so AI Overviews via the search index still see rendered content, but ChatGPT/Claude/Perplexity see only raw HTML.
  Actionable: ensure all CV facts, schema.org JSON-LD, and key twin-answerable content live in server-rendered HTML.
- **Sources:** <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>

### 8. OpenAI states it does not train on data collected by ChatGPT-User or OAI-SearchBot, and Perplexity states its bot-collected data is not used for foundation-model training. This means allowing the citation/user crawlers does not expose your content to training use - reducing the perceived tradeoff of allowing them.

- **Confidence:** medium  |  **Vote:** 2-1 (claim 20)
- **Evidence:**
  OpenAI's revised docs foreground GPTBot as the sole training crawler and describe OAI-SearchBot/ChatGPT-User by function; Perplexity's Help Center states it builds no foundation models.
  The verbatim 'explicit denial' is somewhat less prominent than paraphrased (hence the split vote), but the substance holds across primary sources.
- **Sources:** <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>, <https://developers.openai.com/api/docs/bots>, <https://www.perplexity.ai/help-center/en/articles/11564572-data-collection-at-perplexity>

### 9. Structured-data and entity-disambiguation signals beyond schema.org Person that measurably help AI/recruiter representation: sameAs links to authoritative profiles (ORCID, Google Scholar, GitHub, LinkedIn, Wikidata) for entity resolution, plus keeping all facts in server-rendered HTML. (Note: the verified corpus did not directly test FAQ/QAPage schema or Knowledge Panel efficacy - see open questions.)

- **Confidence:** low  |  **Vote:** inferred from JS/HTML + crawler findings; not a directly-voted claim
- **Evidence:**
  Derived: since AI crawlers ingest raw HTML and no JS, the existing schema.org Person JSON-LD is captured only if server-rendered (Astro SSG satisfies this). sameAs/ORCID entity links are the standard disambiguation mechanism.
  This finding is low-confidence because the adversarial corpus verified crawler mechanics, not structured-data efficacy studies - treat as reasoned extrapolation, not proven.
- **Sources:** <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>, <https://developers.openai.com/api/docs/bots>

## Adversarially REFUTED (killed by the verifier - do NOT act on these)

- ~~Google's user-triggered fetchers (Google-Agent, used for Gemini/AI grounding) ignore robots.txt, unlike OpenAI, Anthropic, and Perplexity training/search bots which respect it.~~
  (vote 0-3; source <https://nohacks.co/blog/ai-user-agents-landscape-2026>)
- ~~Anthropic uses ClaudeBot to retrieve URLs for citations and real-time information during Claude chat sessions, plus anthropic-ai for training and an undocumented claude-web crawler.~~
  (vote 0-3; source <https://momenticmarketing.com/blog/ai-search-crawlers-bots>)
- ~~Google is crawling and indexing llms.txt files, with over 125,000 such files appearing in Google search results.~~
  (vote 1-2; source <https://www.wix.com/studio/ai-search-lab/llms-txt-myths>)

## Sources

- <https://developers.openai.com/api/docs/bots>  (primary, 5 claims)
- <https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler>  (primary, 5 claims)
- <https://nohacks.co/blog/ai-user-agents-landscape-2026>  (secondary, 5 claims)
- <https://momenticmarketing.com/blog/ai-search-crawlers-bots>  (blog, 5 claims)
- <https://searchengineland.com/anthropic-claude-bots-470171>  (unreliable, 0 claims)
- <https://scrunch.com/resources/guides/guide-to-ai-user-agents/>  (blog, 5 claims)
- <https://www.wix.com/studio/ai-search-lab/llms-txt-myths>  (blog, 5 claims)

## Follow-up

Actioned in PR #112 (sameAs fix + llms.txt doc, closed #111).
Higher-leverage work tracked in issue #113 (Phase 14: Wikidata item + FAQPage schema from the twin question-log + static-HTML-facts audit).
