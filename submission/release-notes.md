# Release notes — 0.3.1

Initial skills-only submission candidate for Smart Context Capture.

- Added least-privilege public HTTP routing for ordinary webpages.
- Added explicit `--browser-session` routing for login state, JavaScript, and
  current-tab requests.
- Added ambiguous-tab refusal, JavaScript-shell detection, access-mode
  provenance, lazy provider probing, and gateway timing traces.
- Added a bundled launcher that works from any working directory.
- Added URL metadata redaction for userinfo and sensitive query parameters in
  packet serialization, provenance, links, and opt-in cache files.
- Added an explicit Python 3.10+ prerequisite and a safe missing-runtime
  failure path that never silently escalates to Computer Use.
- Kept local parsing dependency-free and rich document parsing optional.
- Kept Figma downloads confirmation-gated and collision-safe.
- Added 33 automated regression tests and plugin/skill validation.

Reviewer note: this candidate does not bundle an MCP server and must be
submitted as Skills only. Chrome, Figma, MarkItDown, and OCR providers are
optional and are not silently installed or authenticated.
