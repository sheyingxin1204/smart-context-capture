---
name: smart-context-capture
description: Route user-selected local files, public webpages, authorized Chrome tabs, or Figma nodes into one normalized context packet. Use for requests to read, inspect, summarize, compare, or extract content from local files, a browser page, or a Figma design.
---

# Smart Context Capture

This plugin uses the project Python gateway for deterministic local parsing and
keeps browser/Figma access behind explicit, user-installed providers.

## Workflow

1. Identify the source before reading anything: local path, existing Chrome
   tab, or Figma URL/node.
2. Check the capability registry only for that source. Report a missing
   extension, MCP server, CLI, login, or permission instead of retrying
   unrelated providers.
3. Prefer structured extraction, then DOM/API/CLI extraction, and use
   screenshot/OCR only as an explicitly labeled fallback.
   For an ordinary public `http(s)` URL, try the low-permission public HTTP
   adapter before requesting browser or Computer Use access.
4. For a local file, use `smart-context` or the bundled
   `scripts/run_capture.py` launcher and return its JSON `ContextPacket`. The
   launcher is self-contained for the dependency-free core, so a standalone
   Skill install does not require a separate editable package install. The
   bundled core currently supports text/code, Markdown, HTML, CSV/TSV, and
   JSON. PDF, Office, and image parsing require an optional adapter. The
   optional MarkItDown provider can be installed for rich documents.
   For a public URL, use `smart-context "<url>" --source chrome_tab --pretty`
   before invoking desktop/browser control. This route is public HTTP first,
   even when a CDP endpoint is available.
   The launcher requires Python 3.10+; if the runtime is unavailable, report
   that prerequisite instead of silently escalating a read to Computer Use.
5. For an existing Chrome tab or a page whose login/JavaScript state matters,
   use the Codex Chrome connector/relay first. The connector is a separate
   transport from the Python gateway's raw CDP endpoint: a working connector
   does not imply that `http://127.0.0.1:9222` is listening. When the connector
   is available, have the agent read the authorized tab through that connector
   and normalize the returned result; do not invoke Computer Use merely because
   the raw CDP probe is unavailable. Use `--browser-session` only when the user
   explicitly configured a compatible CDP/relay URL (pass `--cdp-url` or set
   `SMART_CONTEXT_CDP_URL`). For Figma, use the official Figma MCP when its
   tools are present; use the REST adapter only as an explicit fallback with
   `FIGMA_ACCESS_TOKEN`.
6. Preserve source identity, adapter, encoding/format metadata, confidence,
   warnings, and whether a fallback was used.
7. Use persistent caching only when the user explicitly chooses a cache
   directory; cached packets contain source content and must be treated as
   sensitive local data.
8. Ask for confirmation before downloads, uploads, writes, form submissions,
   clipboard access, or any other externally visible action.

## Provider order

- Local files: built-in parser, then optional MarkItDown, then a user-approved
  OCR/export adapter.
- Chrome: an available Codex Chrome connector/MCP or relay first, then the
  bundled CDP adapter, then a clearly labeled screenshot fallback. The
  built-in connector can read the user's authorized existing tabs; the raw
  CDP adapter normally uses an isolated Chrome profile and must not be
  presented as the same session.
- Figma: official Figma MCP first, then the bundled REST adapter, then a
  clearly labeled export/screenshot fallback. The remote Figma MCP uses an
  OAuth connection in Codex and does not require exposing a token to Python;
  the desktop MCP uses the local Streamable HTTP endpoint configured by the
  user. Only the REST fallback reads `FIGMA_ACCESS_TOKEN`.

Permission rule: public HTTP and local parsing do not replace browser login
state, JavaScript execution, or visual interaction. If those are required,
explain why the request must be upgraded to a connector, CDP, or Computer Use;
never claim that a low-permission fetch is equivalent.

For an ordinary `http(s)` URL, do not invoke Computer Use or desktop/browser
control before attempting the bundled public HTTP command. Upgrade only when
the result reports a JavaScript shell, login/HTTP authorization failure, an
explicit current-tab request, or a user-approved visual interaction.

Do not silently read cookies, passwords, browser session stores, unrelated
tabs, unrelated files, or hidden application data. A provider failure must be
reported as a provider failure; never present a screenshot/OCR approximation
as if it were a complete structured read.
