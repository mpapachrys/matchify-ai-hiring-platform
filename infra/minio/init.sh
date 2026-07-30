#!/bin/sh
# Bootstrap the object store: create the bucket the API uploads into.
# Runs once at stack start; `service_completed_successfully` gates the API on it.
set -e

echo "→ waiting for MinIO..."
until mc alias set local http://minio:9000 "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY" >/dev/null 2>&1; do
  sleep 1
done

mc mb --ignore-existing "local/$STORAGE_BUCKET"

# Bucket stays private. Every read/write goes through a short-lived presigned
# URL minted by FastAPI after it has authorized the caller.
mc anonymous set none "local/$STORAGE_BUCKET" >/dev/null 2>&1 || true

echo "✓ bucket '$STORAGE_BUCKET' ready (private)"