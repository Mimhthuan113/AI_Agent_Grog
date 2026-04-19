#!/usr/bin/env python3
"""
Script tạo JWT RSA key pair cho authentication.
Chạy một lần: python infrastructure/scripts/gen_jwt_keys.py
"""

import os
import subprocess
import sys

KEYS_DIR = "keys"

def main():
    os.makedirs(KEYS_DIR, exist_ok=True)

    private_key = os.path.join(KEYS_DIR, "private.pem")
    public_key  = os.path.join(KEYS_DIR, "public.pem")

    if os.path.exists(private_key):
        print(f"⚠️  Key đã tồn tại tại {private_key}")
        print("   Xóa thủ công nếu muốn tạo lại.")
        return

    print("🔑 Tạo RSA private key (2048-bit)...")
    subprocess.run(
        ["openssl", "genrsa", "-out", private_key, "2048"],
        check=True
    )

    print("📄 Extract public key...")
    subprocess.run(
        ["openssl", "rsa", "-in", private_key, "-pubout", "-out", public_key],
        check=True
    )

    # Set permissions (Unix)
    if sys.platform != "win32":
        os.chmod(private_key, 0o600)
        os.chmod(public_key,  0o644)

    print(f"\n✅ Tạo xong!")
    print(f"   Private key: {private_key}")
    print(f"   Public key:  {public_key}")
    print(f"\n⚠️  KHÔNG commit keys/ lên Git — đã có trong .gitignore")

if __name__ == "__main__":
    main()
