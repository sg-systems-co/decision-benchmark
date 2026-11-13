#!/usr/bin/env bash
# Install gitleaks at a pinned version, checked against its published sha256.
# Linux x64 only (GitHub-hosted ubuntu runners).
set -euo pipefail

VERSION="8.30.1"
SHA256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
ARCHIVE="gitleaks_${VERSION}_linux_x64.tar.gz"

tmp="$(mktemp -d)"
curl -fsSL -o "${tmp}/${ARCHIVE}" "https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/${ARCHIVE}"
echo "${SHA256}  ${tmp}/${ARCHIVE}" | sha256sum --check --strict
tar -xzf "${tmp}/${ARCHIVE}" -C "${tmp}" gitleaks
mkdir -p "${HOME}/.local/bin"
install -m 0755 "${tmp}/gitleaks" "${HOME}/.local/bin/gitleaks"
echo "${HOME}/.local/bin" >> "${GITHUB_PATH:-/dev/null}"
"${HOME}/.local/bin/gitleaks" version
