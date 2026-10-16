"""Generate a VAPID keypair for Web Push (one-time setup).

Usage:
    cd backend
    python gen_vapid.py

Writes `vapid_private.pem` (git-ignored) next to this file and prints the
.env lines to paste. Restart the API after changing them. The public key is
derived from the private key at runtime by GET /api/push/vapid-public-key.
"""
from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    out = Path(__file__).parent / "vapid_private.pem"
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    out.write_bytes(pem)
    try:  # pragma: no cover — platform dependent
        out.chmod(0o600)
    except OSError:
        pass

    raw = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    print(f"Private key written to {out}")
    print("Add these lines to backend/.env, then restart the API:\n")
    print("WEB_PUSH_ENABLED=true")
    print(f"VAPID_PRIVATE_KEY={out.name}")
    print("VAPID_CLAIMS_EMAIL=mailto:you@example.com")
    print(f"\nPublic key (applicationServerKey): {public}")


if __name__ == "__main__":
    main()