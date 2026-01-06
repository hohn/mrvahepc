#!/usr/bin/env sh
set -eu

BASE=/mnt/common/tank/mrva-values/mrvahepc

SRC_DB="$BASE/metadata.sql"
DST_DB="$BASE/metadata-adjust.sql"

OLD_PREFIX="https://mrva.hohnlab.org/values/db//mnt/common/tank/mrva-values/values"
NEW_PREFIX="https://hohnlab.org/mrva/values"

# Safety checks
[ -f "$SRC_DB" ] || { echo "Missing $SRC_DB"; exit 1; }

# Copy original DB
cp -a "$SRC_DB" "$DST_DB"

# Rewrite URLs in-place in the copy
sqlite3 "$DST_DB" <<EOF
UPDATE metadata
SET result_url = replace(result_url,
    '$OLD_PREFIX',
    '$NEW_PREFIX'
)
WHERE result_url LIKE '$OLD_PREFIX%';
EOF

echo "Written adjusted DB to:"
echo "  $DST_DB"
