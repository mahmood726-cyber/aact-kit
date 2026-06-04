# Releasing aact-kit to PyPI

Publishing uses **PyPI Trusted Publishing** (OIDC) via `.github/workflows/publish.yml`
— no API token is stored anywhere.

## One-time setup (PyPI side)

1. Sign in to <https://pypi.org> with the project owner account.
2. Go to **Account → Publishing → Add a pending publisher** (works before the
   project exists): <https://pypi.org/manage/account/publishing/>
   - **PyPI Project Name:** `aact-kit`
   - **Owner:** `mahmood726-cyber`
   - **Repository name:** `aact-kit`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. (Optional, recommended) In the GitHub repo: **Settings → Environments → New
   environment → `pypi`**, and add required reviewers if you want a manual gate.

## Cut a release

```bash
# from a clean main that's green on CI
git tag v0.1.0
git push origin v0.1.0
# then draft a GitHub Release for that tag (Releases → Draft new release → publish)
```

Publishing the GitHub Release (or pushing the `v*` tag) triggers `publish.yml`,
which builds, runs `twine check`, and uploads to PyPI via OIDC. Bump
`version` in `pyproject.toml` and `__version__` in `src/aact_kit/__init__.py`
for each release.

## Manual fallback (token, no Actions)

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*      # prompts for username "__token__" + a PyPI API token
```

Local artifacts are validated already: `aact_kit-0.1.0-py3-none-any.whl` and
`aact_kit-0.1.0.tar.gz` both pass `twine check`.
