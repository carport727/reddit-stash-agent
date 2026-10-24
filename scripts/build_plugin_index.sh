#!/bin/bash
# Build a Stash plugin source (index.yml + one zip per plugin) into $1 (default _site).
# Same layout as stashapp/CommunityScripts; add the published index.yml URL in
# Stash > Settings > Plugins > Available Plugins > Add Source.
set -euo pipefail

outdir="${1:-_site}"
rm -rf "$outdir"
mkdir -p "$outdir"
outdir=$(realpath "$outdir")

for yml in plugins/*/*.yml; do
    dir=$(dirname "$yml")
    plugin_id=$(basename "$yml" .yml)
    field() { grep "^$1:" "$yml" | head -n 1 | cut -d' ' -f2- | sed -e 's/\r//' -e 's/^"\(.*\)"$/\1/'; }

    commit=$(git log -n 1 --pretty=format:%h -- "$dir")
    updated=$(TZ=UTC0 git log -n 1 --date="format-local:%F %T" --pretty=format:%ad -- "$dir")
    zipfile="$outdir/$plugin_id.zip"

    (cd "$dir" && zip -r -X "$zipfile" . -x '*__pycache__*' > /dev/null)

    cat >> "$outdir/index.yml" <<YML
- id: $plugin_id
  name: $(field name)
  metadata:
    description: $(field description)
  version: $(field version)-$commit
  date: $updated
  path: $plugin_id.zip
  sha256: $(sha256sum "$zipfile" | cut -d' ' -f1)

YML
    echo "Packaged $plugin_id"
done
