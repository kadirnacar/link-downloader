#!/bin/bash
# ytdlp-studio:check v1
# go build ./... KULLANMAZ (build/ios, build/android main'siz). wails3 build kullanır.
set -euo pipefail
cd "$(dirname "$0")/.."

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-13.0}"
if [ "$(uname)" = "Darwin" ]; then
  export CGO_CFLAGS="${CGO_CFLAGS:-} -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
  export CGO_LDFLAGS="${CGO_LDFLAGS:-} -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
  export GOFLAGS="${GOFLAGS:-} -ldflags=-extldflags=-mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
fi

echo "== frontend =="
(cd frontend && npm install --no-audit --no-fund && npm run build)

echo "== wails build =="
if command -v wails3 >/dev/null; then
  wails3 build
else
  echo "wails3 yok; kök paket derleniyor"
  go build -tags production .
fi

echo "== test (internal + services) =="
go test ./internal/... ./services/...

echo "== vet (internal + services) =="
go vet ./internal/... ./services/...

echo "OK: doğrulama tamam"
