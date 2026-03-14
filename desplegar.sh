#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-ferdcard-ux/SyncMaster-App}"
ASSET="${1:-}"

if [[ -z "$ASSET" ]]; then
  if ! ls ./*.AppImage >/dev/null 2>&1; then
    echo "No se encontro ningun .AppImage en el directorio actual."
    exit 1
  fi
  ASSET=$(ls -t ./*.AppImage | head -n1)
fi

if [[ ! -f "$ASSET" ]]; then
  echo "No se encontro el archivo: $ASSET"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "No se encontro 'gh' (GitHub CLI). Instalala antes de continuar."
  exit 1
fi

VERSION=""
if [[ -f CHANGELOG.md ]]; then
  VERSION=$(grep -m1 -E '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | sed -E 's/^## \[([^]]+)\].*/\1/')
fi

if [[ -z "$VERSION" ]]; then
  VERSION=$(date +%Y.%m.%d)
fi

TAG="v${VERSION}"
TITLE="SyncMaster ${VERSION}"

NOTES_ARGS=(--generate-notes)
if [[ -f release_notes.md ]]; then
  NOTES_ARGS=(--notes-file release_notes.md)
fi

echo "Creando release en $REPO con tag $TAG usando $ASSET"

gh release create "$TAG" "$ASSET" \
  --repo "$REPO" \
  --title "$TITLE" \
  "${NOTES_ARGS[@]}"

echo "Release creado: $TAG"
