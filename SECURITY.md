# Security Policy

## Scope

This project is a local image-processing Skill. It does not upload images, call cloud APIs, read API keys, or delete source files.

## Safe defaults

- Source files are not overwritten by default.
- Output is written to a separate directory.
- API keys, environment files, user images, and generated manifests are excluded from the release template.
- External uploads remain the user's explicit responsibility.

## Reporting a vulnerability

Do not include private images, credentials, API keys, or personal paths in a public issue. Report suspected security problems privately to the repository maintainer after the repository owner has been configured.
