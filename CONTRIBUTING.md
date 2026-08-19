# Contributing

Contributions are welcome through pull requests.

- `main` is the protected release branch; do not push directly to it.
- Create a focused branch from `main` and explain the behavior change.
- Run `python -m unittest discover -s tests -v`,
  `python -B scripts/sync_skill_runtime.py --check`, and
  `python -B scripts/check_release.py` before opening a pull request.
- Run `python -B scripts/build_release.py` when changing the Skill bundle; the
  allow-list builder is the only supported way to create a public upload.
- Do not commit credentials, browser cookies, private files, `.env` files, or
  generated caches.
- Changes that expand browser, Figma, download, or write access must document
  their permission boundary and add a regression test.

The maintainer reviews and merges changes after the checks and security impact
are understood.
