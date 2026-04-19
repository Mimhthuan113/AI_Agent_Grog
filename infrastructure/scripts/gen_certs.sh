#!/bin/bash
# ============================================================
# Script tạo TLS certificates cho MQTT
# Chạy một lần: bash infrastructure/scripts/gen_certs.sh
# ============================================================

set -e  # Dừng khi có lỗi

CERTS_DIR="infrastructure/certs"
mkdir -p "$CERTS_DIR"

echo "📜 Bước 1: Tạo CA (Certificate Authority)..."
openssl genrsa -out "$CERTS_DIR/ca.key" 4096
openssl req -new -x509 -days 3650 \
    -key "$CERTS_DIR/ca.key" \
    -out "$CERTS_DIR/ca.crt" \
    -subj "/CN=SmartHomeCA/O=SmartHub/C=VN"

echo "🖥️  Bước 2: Tạo Server Certificate (cho Mosquitto)..."
openssl genrsa -out "$CERTS_DIR/server.key" 2048
openssl req -new \
    -key "$CERTS_DIR/server.key" \
    -out "$CERTS_DIR/server.csr" \
    -subj "/CN=mosquitto/O=SmartHub/C=VN"
openssl x509 -req -days 3650 \
    -in "$CERTS_DIR/server.csr" \
    -CA "$CERTS_DIR/ca.crt" \
    -CAkey "$CERTS_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERTS_DIR/server.crt"

echo "📱 Bước 3: Tạo Client Certificate (cho ESP32 node1)..."
openssl genrsa -out "$CERTS_DIR/esp32_node1.key" 2048
openssl req -new \
    -key "$CERTS_DIR/esp32_node1.key" \
    -out "$CERTS_DIR/esp32_node1.csr" \
    -subj "/CN=esp32_node1/O=SmartHub/C=VN"
openssl x509 -req -days 3650 \
    -in "$CERTS_DIR/esp32_node1.csr" \
    -CA "$CERTS_DIR/ca.crt" \
    -CAkey "$CERTS_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERTS_DIR/esp32_node1.crt"

echo "🔑 Bước 4: Tạo Client Certificate (cho Backend service)..."
openssl genrsa -out "$CERTS_DIR/client.key" 2048
openssl req -new \
    -key "$CERTS_DIR/client.key" \
    -out "$CERTS_DIR/client.csr" \
    -subj "/CN=smarthub_backend/O=SmartHub/C=VN"
openssl x509 -req -days 3650 \
    -in "$CERTS_DIR/client.csr" \
    -CA "$CERTS_DIR/ca.crt" \
    -CAkey "$CERTS_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERTS_DIR/client.crt"

echo ""
echo "✅ Tạo certs xong! Files:"
ls -la "$CERTS_DIR/"
echo ""
echo "⚠️  LƯU Ý: ca.key là file nhạy cảm — đã có trong .gitignore"
echo "⚠️  Copy esp32_node1.crt + esp32_node1.key + ca.crt vào firmware"
