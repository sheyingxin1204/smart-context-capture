# Official submission steps

This release is a **skills-only** plugin. It does not bundle an MCP server or
claim an existing third-party integration.

## 0. Read the official requirements

- [Build skills](https://developers.openai.com/plugins/build/skills)
- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Submit plugins](https://developers.openai.com/plugins/deploy/submission)

The submission guide is the source of truth if the portal UI changes.

## 1. Run the final local checks

From `C:\tmp\codex-smart-context-skill`:

```powershell
python -B scripts/check_release.py
python -m unittest discover -s tests -v
Get-FileHash .\dist\smart-context-capture-0.3.1-release.zip -Algorithm SHA256
```

Expected release hash:
`88B99AC62DB4EC278059761362E13F53ED60E33EED2479EA275ABC218147BFF8`.

Upload only:
`dist/smart-context-capture-0.3.1-release.zip`.

Do not upload `tests/`, `submission/`, caches, `__pycache__/`, or credentials.

## 2. Prepare the publisher identity and permission

1. Open [organization settings](https://platform.openai.com/settings/organization/general)
   and complete individual or business verification.
2. Open [organization roles](https://platform.openai.com/settings/organization/people/roles)
   and give the submitting role **Apps Management: Write**.
3. Use the same organization for verification, role access, and submission.

## 3. Prepare public listing pages

Host real HTTPS pages for the website, support, privacy policy, and terms of
service. Drafts are in `privacy-policy-draft.md` and `terms-draft.md`; review
them before publishing. A public repository matching the publisher is strongly
recommended for transparency, but do not invent URLs.

Also prepare a production logo and choose a category. Replace the generic
`author`/`developerName` values in `.codex-plugin/plugin.json` with the real
publisher values before making a new release package.

## 4. Create the draft

Open the [Plugin submission portal](https://platform.openai.com/plugins), select
**Create plugin**, then choose **Skills only**. The portal saves a draft while
you work. Do not select **With MCP** for this release.

## 5. Fill the Info tab

Copy the customer-facing text from `listing-draft.md`, then enter:

- the verified developer identity;
- production logo and `Productivity` (or the closest accurate category);
- website, support, privacy-policy, and terms URLs;
- the real publisher/developer name.

## 6. Upload the skill bundle

In the Skills tab upload the final ZIP from step 1. Keep the tested tree intact:
`.codex-plugin/`, `skills/`, `src/`, `scripts/`, `README.md`, `LICENSE`, and
`pyproject.toml`. The skill contains the Python launcher; Chrome, Figma,
MarkItDown, and OCR remain optional user-configured providers.

## 7. Add prompts and reviewer tests

- Copy starter prompts from the manifest or `listing-draft.md`.
- Enter all five positive and three negative cases from `test-cases.json`.
- Use reviewer-accessible fixtures only; do not require MFA, private networks,
  personal accounts, cookies, or unpublished files.

The official requirement is [five positive and three negative tests](https://developers.openai.com/plugins/deploy/submission#testing).

## 8. Choose availability and submit

Select only countries/regions where the publisher, support process, and legal
pages are ready. Copy `release-notes.md` into the release-notes field, review
the attestations, and select **Submit for Review**.

## 9. Approval and publication

Submitting starts review; it does **not** publish immediately. After approval,
return to the portal and select **Publish**. The approved skills-only plugin
then appears in the universal Plugins Directory shared by ChatGPT and Codex.

For portal errors, use the [submission error reference](https://developers.openai.com/plugins/deploy/submission-errors).

## 10. Future updates

Bump the version, update the real metadata, rerun the checks, generate a new ZIP
and SHA-256, and submit a new version for review. Never silently add a browser
connector, token, cookie access, or destructive download capability to an
existing published version.
