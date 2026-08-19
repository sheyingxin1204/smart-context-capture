# Smart Context Capture — listing draft

## Short description

Read local files and public webpages with least privilege, then explicitly
upgrade to authorized browser or Figma providers when necessary.

## Long description

Smart Context Capture gives Codex one auditable read path for local files,
public webpages, existing Chrome tabs, and Figma nodes. It uses dependency-free
Python parsing for local data and public HTTP first, records the adapter,
access mode, confidence, provenance, truncation, and fallback warnings, and
only uses browser session state or Figma tokens when the user has configured
and authorized those providers. It never silently reads cookies, passwords,
unrelated tabs, or hidden files. Downloads and other external writes require
explicit confirmation.

## Capability boundary

- Read-only by default.
- Public HTTP does not execute JavaScript or reuse browser login state.
- Chrome current-tab reads require a user-configured Connector, Relay, or CDP.
- Figma REST fallback requires an explicit user-provided access token; official
  Figma MCP can be used separately when installed.
- Rich PDF/Office/OCR support is optional and reports unavailable rather than
  pretending to parse unsupported formats.
