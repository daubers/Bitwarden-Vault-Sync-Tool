#!/bin/sh
set -eu

if [ -f /ssl/cert.pem ] && [ -f /ssl/key.pem ]; then
    echo "TLS cert already present, skipping generation"
    exit 0
fi

openssl req -x509 -newkey rsa:2048 -keyout /ssl/key.pem -out /ssl/cert.pem -days 3650 -nodes \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:vaultwarden,IP:127.0.0.1"

chmod 644 /ssl/cert.pem /ssl/key.pem
echo "Generated self-signed TLS cert for local dev"
