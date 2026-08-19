# Privacy policy draft — Smart Context Capture

_This is a draft for the verified publisher to review and host at a public
HTTPS URL. It is not legal advice._

Smart Context Capture is a local Codex Skill and Python package. Its default
local-file and public-HTTP readers process the selected input in the local
runtime. Public HTTP requests send only the requested URL and a generic
read-only request header; they do not send browser cookies, passwords, browser
profiles, or Figma login state.

If the user explicitly configures Chrome CDP/Connector or a Figma access token,
the selected provider may read the selected page/node under that provider's
permissions. The Skill does not discover or extract browser session stores or
tokens. Figma tokens are read from the explicit process configuration and are
not written to project files or returned in packets.

Persistent packet caching is disabled by default. If the user opts into a
cache directory, captured content and provenance are stored there as local
files and inherit the user's filesystem permissions. Users should not enable
the cache for sensitive material without securing that directory.

Downloads, uploads, writes, form submissions, and clipboard operations require
explicit confirmation. The project does not sell personal data or transmit
captured content to a Smart Context Capture service.

For privacy requests or security reports, the verified publisher must replace
this paragraph with a real support contact and retention/deletion process.
