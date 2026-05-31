# Security Policy

## Supported versions

pyssg is pre-1.0. Security fixes are applied to the latest `main` and released as
a new tag. There are no long-term support branches yet.

## Reporting a vulnerability

Please do not open a public issue for security problems.

Instead, use GitHub's private vulnerability reporting:
[Report a vulnerability](https://github.com/magiskboy/pyssg/security/advisories/new).

Include a description, reproduction steps, and the affected version or commit. You
can expect an initial acknowledgement within a few days. Once a fix is ready, a
patched release is tagged and the advisory is published.

## Scope

pyssg is a build-time static site generator: it reads local content and templates
and writes HTML. The most relevant risks are template injection via untrusted
content and fetching community themes from GitHub. Theme manifests (`theme.toml`)
are parsed with `tomllib` and never executed. Reports about these areas are
especially welcome.
