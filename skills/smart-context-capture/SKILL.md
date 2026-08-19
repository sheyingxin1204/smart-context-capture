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
   `scripts/run_capture.py` launcher and return its JSON `ContextPacket`. The bundled core currently supports
   text/code, Markdown, HTML, CSV/TSV, and JSON. PDF, Office, and image
   parsing require an optional adapter. The optional MarkItDown provider can
   be installed for rich documents.
   For a public URL, use `smart-context "<url>" --source chrome_tab --pretty`
   before invoking desktop/browser control. This route is public HTTP first,
   even when a CDP endpoint is available.
   The launcher requires Python 3.10+; if the runtime is unavailable, report
   that prerequisite instead of silently escalating a read to Computer Use.
5. For an existing Chrome tab or a page whose login/JavaScript state matters,
   require a user-configured CDP/relay provider and pass
   `--browser-session`; for Figma REST fallback, require an explicit
   `FIGMA_ACCESS_TOKEN`. An
   official Chrome/Figma MCP may replace either transport when registered.
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
  bundled CDP adapter, then a clearly labeled screenshot fallback.
- Figma: official Figma MCP first, then the bundled REST adapter, then a
  clearly labeled export/screenshot fallback.

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
