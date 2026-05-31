# Releasing

This is the maintainer runbook for cutting a pyssg release. pyssg is **not**
published to PyPI: a release is a git tag whose built wheel and sdist are
attached to a GitHub Release, so users can pin or download a specific version
and install via git.

pyssg follows [Semantic Versioning](https://semver.org). The version lives in a
single place, `pyproject.toml` (`[project].version`); `pyssg --version` reads it
back from the installed distribution metadata.

## 1. Prepare the release PR

Open a branch (e.g. `release/vX.Y.Z`) and:

1. Bump `[project].version` in `pyproject.toml`.
2. Move the `CHANGELOG.md` entries from `[Unreleased]` into a new
   `[X.Y.Z] - YYYY-MM-DD` section and refresh the compare links at the bottom.
3. Run the same checks CI runs, locally:

   ```sh
   source .venv/bin/activate
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy
   uv run python -m unittest discover -s tests
   ```

4. Open the PR, wait for CI to pass, and merge to `main`.

## 2. Tag and push

On the merge commit on `main`:

```sh
git checkout main && git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```

The tag must match the `pyproject.toml` version (without the leading `v`); the
release workflow fails fast if they disagree.

Pre-releases use a suffix, e.g. `vX.Y.Z-rc1` (or `-alpha`/`-beta`), and are
automatically marked as pre-releases on GitHub.

## 3. What the workflow does

Pushing the tag triggers `.github/workflows/release.yml`, which:

1. Verifies the tag matches the `pyproject.toml` version.
2. Builds the wheel and sdist (`uv build`).
3. Smoke tests the built wheel in a clean venv: `pyssg --version`, scaffolds a
   `docs` site and builds it offline.
4. Creates a GitHub Release with auto-generated notes and the artifacts attached
   (marked pre-release for `-rc`/`-alpha`/`-beta` tags).

## 4. Verify the release

After the workflow finishes:

```sh
uv venv /tmp/verify
uv pip install --python /tmp/verify "pyssg[plugins] @ git+https://github.com/magiskboy/pyssg@vX.Y.Z"
/tmp/verify/bin/pyssg --version   # should print X.Y.Z
```

Confirm the Release page lists the `.whl` and `.tar.gz` artifacts and the notes
read correctly.
