#!/usr/bin/env bash
set -euo pipefail

MANIFEST="$(dirname "$0")/../build/binaries-list.txt"

if [ ! -f "$MANIFEST" ]; then
  echo "Manifest not found: $MANIFEST"
  exit 1
fi

download() {
  local url="$1"; local out="$2"; local sha="$3"
  mkdir -p "$(dirname "$out")"

  if [ -f "$out" ] && [ -n "$sha" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
      cursha=$(sha256sum "$out" | awk '{print $1}')
      if [ "$cursha" = "$sha" ]; then
        echo "OK: $out (matches sha256)"
        return 0
      else
        echo "Mismatch sha256 for $out, re-downloading"
      fi
    fi
  elif [ -f "$out" ]; then
    echo "Exists: $out (no sha provided)"
    return 0
  fi

  if command -v curl >/dev/null 2>&1; then
    curl -L --fail -o "$out" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$out" "$url"
  else
    echo "Neither curl nor wget available; please install one." >&2
    return 2
  fi

  if [ -n "$sha" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
      cursha=$(sha256sum "$out" | awk '{print $1}')
      if [ "$cursha" != "$sha" ]; then
        echo "ERROR: SHA256 mismatch for $out" >&2
        return 3
      fi
    else
      echo "Warning: sha256sum not found; cannot verify $out"
    fi
  fi

  echo "Downloaded: $out"
}

while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"
  line="$(echo -n "$line" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  if [ -z "$line" ]; then
    continue
  fi
  IFS='|' read -r url out sha <<< "$line"
  if [ -z "$url" ] || [ -z "$out" ]; then
    echo "Skipping malformed line: $line"
    continue
  fi
  download "$url" "$out" "$sha"
done < "$MANIFEST"

echo "All done."
