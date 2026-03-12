#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$ROOT_DIR/certs/root/happytrust/private" "$ROOT_DIR/certs/root/happytrust/certs"
mkdir -p "$ROOT_DIR/certs/root/sadtrust/private" "$ROOT_DIR/certs/root/sadtrust/certs"
chmod 700 "$ROOT_DIR/certs/root/happytrust/private" "$ROOT_DIR/certs/root/sadtrust/private"

openssl genrsa -out "$ROOT_DIR/certs/root/happytrust/private/happytrust-root.key" 4096
openssl req -x509 -new -nodes \
  -key "$ROOT_DIR/certs/root/happytrust/private/happytrust-root.key" \
  -sha256 -days 3650 \
  -out "$ROOT_DIR/certs/root/happytrust/certs/happytrust-root.crt" \
  -subj "/C=US/ST=CT/L=Hartford/O=HappyTrust/CN=HappyTrust Root CA"

openssl genrsa -out "$ROOT_DIR/certs/root/sadtrust/private/sadtrust-root.key" 4096
openssl req -x509 -new -nodes \
  -key "$ROOT_DIR/certs/root/sadtrust/private/sadtrust-root.key" \
  -sha256 -days 3650 \
  -out "$ROOT_DIR/certs/root/sadtrust/certs/sadtrust-root.crt" \
  -subj "/C=US/ST=CT/L=Hartford/O=SadTrust/CN=SadTrust Root CA"

echo "Created HappyTrust and SadTrust root CAs"
