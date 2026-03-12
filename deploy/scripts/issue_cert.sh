#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <domain> <org_name> <happytrust|sadtrust>"
  exit 1
fi

DOMAIN="$1"
ORG_NAME="$2"
CA_NAME="$3"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ISSUED_DIR="$ROOT_DIR/certs/issued/$DOMAIN"
CA_CERT="$ROOT_DIR/certs/root/$CA_NAME/certs/${CA_NAME}-root.crt"
CA_KEY="$ROOT_DIR/certs/root/$CA_NAME/private/${CA_NAME}-root.key"

mkdir -p "$ISSUED_DIR"

openssl genrsa -out "$ISSUED_DIR/$DOMAIN.key" 2048

openssl req -new \
  -key "$ISSUED_DIR/$DOMAIN.key" \
  -out "$ISSUED_DIR/$DOMAIN.csr" \
  -subj "/C=US/ST=CT/L=Hartford/O=$ORG_NAME/CN=$DOMAIN"

cat > "$ISSUED_DIR/$DOMAIN.ext" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=$DOMAIN
EOF

openssl x509 -req \
  -in "$ISSUED_DIR/$DOMAIN.csr" \
  -CA "$CA_CERT" \
  -CAkey "$CA_KEY" \
  -CAcreateserial \
  -out "$ISSUED_DIR/$DOMAIN.crt" \
  -days 825 -sha256 \
  -extfile "$ISSUED_DIR/$DOMAIN.ext"

echo "Issued certificate for $DOMAIN using $CA_NAME"
