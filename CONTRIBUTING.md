# Contributing

Contributions are welcome through pull requests.

- `main` is the protected release branch; do not push directly to it.
- Create a focused branch from `main` and explain the behavior change.
- Run `python -m unittest discover -s tests -v` and
  `python -B scripts/check_release.py` before opening a pull request.
- Do not commit credentials, browser cookies, private files, `.env` files, or
  generated caches.
- Changes that expand browser, Figma, download, or write access must document
  their permission boundary and add a regression test.

The maintainer reviews and merges changes after the checks and security impact
are understood.
