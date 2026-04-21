#!/usr/bin/env python3
"""
Script tao JWT RSA key pair cho authentication.
Chay mot lan: python infrastructure/scripts/gen_jwt_keys.py

Su dung thu vien 'cryptography' (khong can openssl CLI).
"""

import os
import sys

def main():
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("[ERROR] Can cai cryptography: pip install cryptography")
        sys.exit(1)

    keys_dir = "keys"
    os.makedirs(keys_dir, exist_ok=True)

    private_key_path = os.path.join(keys_dir, "private.pem")
    public_key_path = os.path.join(keys_dir, "public.pem")

    if os.path.exists(private_key_path):
        print(f"[WARN] Key da ton tai tai {private_key_path}")
        print("       Xoa thu cong neu muon tao lai.")
        return

    print("[INFO] Tao RSA private key (2048-bit)...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write files
    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    with open(public_key_path, "wb") as f:
        f.write(public_pem)

    # Set permissions (Unix only)
    if sys.platform != "win32":
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)

    print(f"[OK] Tao xong!")
    print(f"     Private key: {private_key_path}")
    print(f"     Public key:  {public_key_path}")
    print(f"")
    print(f"[WARN] KHONG commit keys/ len Git")

if __name__ == "__main__":
    main()
