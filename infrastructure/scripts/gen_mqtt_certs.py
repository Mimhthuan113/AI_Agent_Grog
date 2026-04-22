"""
Script tao certificate cho MQTT TLS
=====================================
Tao CA, server cert, va client cert cho Mosquitto + ESP32.

Chay:
    python infrastructure/scripts/gen_mqtt_certs.py

Output:
    infrastructure/mosquitto/certs/
    ├── ca.crt          ← CA certificate
    ├── ca.key          ← CA private key (GIU BI MAT)
    ├── server.crt      ← Server certificate
    ├── server.key      ← Server private key
    ├── client.crt      ← Client certificate (cho ESP32)
    └── client.key      ← Client private key (cho ESP32)
"""

import os
import datetime
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


CERTS_DIR = Path(__file__).parent.parent / "mosquitto" / "certs"
VALIDITY_DAYS = 365 * 3  # 3 nam


def gen_key():
    """Tao RSA 2048-bit key."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def save_key(key, path):
    """Luu private key ra file PEM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    print(f"  [KEY] {path}")


def save_cert(cert, path):
    """Luu certificate ra file PEM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"  [CRT] {path}")


def create_ca():
    """Tao self-signed CA certificate."""
    key = gen_key()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "VN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Smart Home Hub"),
        x509.NameAttribute(NameOID.COMMON_NAME, "SmartHome CA"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def create_cert(ca_key, ca_cert, common_name, san_dns=None):
    """Tao certificate duoc ky boi CA."""
    key = gen_key()
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "VN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Smart Home Hub"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=VALIDITY_DAYS))
    )
    if san_dns:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(dns) for dns in san_dns
            ]),
            critical=False,
        )
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert


def main():
    print("=" * 50)
    print("MQTT TLS Certificate Generator")
    print("=" * 50)

    # 1. CA
    print("\n[1] Tao CA certificate...")
    ca_key, ca_cert = create_ca()
    save_key(ca_key, CERTS_DIR / "ca.key")
    save_cert(ca_cert, CERTS_DIR / "ca.crt")

    # 2. Server cert
    print("\n[2] Tao Server certificate...")
    srv_key, srv_cert = create_cert(
        ca_key, ca_cert,
        common_name="mqtt-broker",
        san_dns=["localhost", "mosquitto", "smarthome-mqtt"],
    )
    save_key(srv_key, CERTS_DIR / "server.key")
    save_cert(srv_cert, CERTS_DIR / "server.crt")

    # 3. Client cert (cho ESP32 / backend)
    print("\n[3] Tao Client certificate...")
    cli_key, cli_cert = create_cert(
        ca_key, ca_cert,
        common_name="smarthome-client",
    )
    save_key(cli_key, CERTS_DIR / "client.key")
    save_cert(cli_cert, CERTS_DIR / "client.crt")

    print("\n" + "=" * 50)
    print(f"Done! Certs saved to: {CERTS_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
