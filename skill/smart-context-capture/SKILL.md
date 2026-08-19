---
name: smart-context-capture
description: Route user-selected local files, public webpages, authorized Chrome tabs, or Figma nodes into one normalized context packet. Use for requests to read, inspect, summarize, compare, or extract content from local files, a browser page, or a Figma design.
---

# Smart Context Capture

This is the project skill for the unified context gateway. It is currently a
development preview: the local-file adapter is available; Chrome and Figma
adapters must be installed and authorized separately.

## Workflow

1. Identify the source before reading anything: local path, existing Chrome
   tab, or Figma URL/node.
2. Check the capability registry only for that source. Report a missing
   extension, MCP server, CLI, login, or permission instead of retrying
   unrelated providers.
3. Prefer structured extraction, then DOM/API/CLI extraction, and use
   screenshot/OCR only as an explicitly labeled fallback. For an ordinary
   public `http(s)` URL, try the low-permission public HTTP adapter before
   requesting browser or Computer Use access.
4. For a local file, use the project gateway (`smart-context` or
   `python -m smart_context`) and return its JSON `ContextPacket`. The current
   dependency-free parser supports text/code, Markdown, HTML, CSV/TSV, and
   JSON. PDF, Office, and image parsing require an optional adapter.
   For an existing Chrome tab, the bundled read adapter needs a local CDP
   endpoint (`SMART_CONTEXT_CDP_URL`, normally port 9222). For Figma REST
   fallback, require an explicit `FIGMA_ACCESS_TOKEN`; the official Figma MCP
   can be registered as the primary provider instead.
   For a public URL, use `smart-context "<url>" --source chrome_tab --pretty`
   before invoking desktop/browser control. This route is public HTTP first,
   even when a CDP endpoint is available. If login state, JavaScript, or the
   current tab matters, add `--browser-session` to prefer the configured
   browser session.
5. Preserve source identity, adapter, encoding/format metadata, confidence,
   warnings, and whether a fallback was used.
6. Use persistent caching only when the user explicitly chooses a cache
   directory; cached packets contain source content and must be treated as
   sensitive local data.
7. Ask for confirmation before downloads, uploads, writes, form submissions,
   clipboard access, or any other externally visible action.

Provider order is local parser → optional rich parser → OCR/export for local
files; public HTTP → configured Chrome connector/MCP → CDP → screenshot for
Chrome; official Figma MCP → REST → export/screenshot for Figma. Every fallback
must be labeled. Never claim public HTTP is equivalent to a logged-in or
JavaScript-rendered browser tab.

For an ordinary `http(s)` URL, do not invoke Computer Use or desktop/browser
control before attempting the public HTTP command. Upgrade only when the
result reports a JavaScript shell, login/HTTP authorization failure, an
explicit current-tab request, or a user-approved visual interaction.

Do not silently read cookies, passwords, browser session stores, unrelated
tabs, unrelated files, or hidden application data. A provider failure must be
reported as a provider failure; never present a screenshot/OCR approximation
as if it were a complete structured read.
