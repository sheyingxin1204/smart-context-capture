# Public submission packet

This directory contains material to copy into the official Codex/ChatGPT
Plugin submission form. The plugin is intentionally a **skills-only** plugin:
the Python gateway is a bundled deterministic resource, while Chrome/Figma
connectors remain optional user-configured providers.

## Required publisher values

The following values must be supplied by the real publisher in the portal:

- Verified individual or business developer identity.
- Public HTTPS website and support URL.
- Public HTTPS privacy-policy URL and terms-of-service URL.
- Recommended: public repository URL that matches the verified publisher, for
  transparency and reproducible releases. (The portal's required public links
  are the website, support, privacy-policy, and terms URLs.)
- Production logo/brand assets.
- Countries/regions where support and legal terms are ready.

Do not put invented URLs or credentials into the manifest or submission form.

## Submission type

Choose **Skills only**. No MCP server is bundled in this release, and the
submission should not reference an existing third-party integration ID.

## Files

- `listing-draft.md`: customer-facing listing copy and capability boundaries.
- `test-cases.json`: five positive and three negative reviewer-run cases.
- `release-notes.md`: release notes for version 0.3.2.
- `privacy-policy-draft.md`: data-handling disclosure to host at a real HTTPS URL
  after legal/publisher review.
- `terms-draft.md`: terms draft to host at a real HTTPS URL after review.

The final upload should preserve the tested plugin tree: `.codex-plugin/`,
`skills/`, `src/`, the launcher under `skills/.../scripts/`, and the package
metadata required by the launcher.

Build the current upload artifact with `python scripts/build_release.py`:
`dist/smart-context-capture-0.3.2-release.zip`. The script writes a matching
`.sha256` file and uses an explicit allow-list so tests, drafts, caches, and
credentials cannot enter the upload.
