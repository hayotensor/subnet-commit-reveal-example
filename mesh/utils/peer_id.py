import hashlib
from typing import Optional

from cryptography.hazmat.primitives import serialization

from mesh import PeerID
from mesh.dht.crypto import SignatureValidator
from mesh.dht.validation import RecordValidatorBase
from mesh.proto import crypto_pb2
from mesh.utils import get_logger, multihash
from mesh.utils.crypto import Ed25519PublicKey, RSAPublicKey

logger = get_logger(__name__)

"""
Extract Ed25519 peer ID from public key
"""
def extract_ed25519_peer_id(record_validator: RecordValidatorBase, key)-> Optional[PeerID]:
  public_keys = SignatureValidator._PUBLIC_KEY_RE.findall(key)
  public_keys = record_validator._PUBLIC_KEY_RE.findall(key)
  pubkey = Ed25519PublicKey.from_bytes(public_keys[0])

  peer_id = get_ed25519_peer_id(pubkey)
  return peer_id

def get_ed25519_peer_id(public_key: Ed25519PublicKey) -> Optional[PeerID]:
  try:
    encoded_public_key = crypto_pb2.PublicKey(
      key_type=crypto_pb2.Ed25519,
      data=public_key.to_raw_bytes(),
    ).SerializeToString()

    encoded_public_key = b"\x00$" + encoded_public_key

    peer_id = PeerID(encoded_public_key)

    return peer_id
  except Exception as e:
    logger.error(e)
    return None

def get_peer_id_from_pubkey(public_key: RSAPublicKey | Ed25519PublicKey) -> Optional[PeerID]:
  if isinstance(public_key, RSAPublicKey):
    return get_rsa_peer_id(public_key)
  elif isinstance(public_key, Ed25519PublicKey):
    return get_ed25519_peer_id(public_key)
  else:
    return None

"""
Extract RSA peer ID from public key
"""
def extract_rsa_peer_id(record_validator: RecordValidatorBase, key)-> Optional[PeerID]:
  public_keys = SignatureValidator._PUBLIC_KEY_RE.findall(key)
  public_keys = record_validator._PUBLIC_KEY_RE.findall(key)
  pubkey = RSAPublicKey.from_bytes(public_keys[0])

  peer_id = get_rsa_peer_id(pubkey)
  return peer_id

def get_rsa_peer_id(public_key: RSAPublicKey) -> Optional[PeerID]:
  try:
    encoded_public_key = public_key._public_key.public_bytes(
      encoding=serialization.Encoding.DER,
      format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    encoded_public_key = crypto_pb2.PublicKey(
      key_type=crypto_pb2.RSA,
      data=encoded_public_key,
    ).SerializeToString()

    encoded_digest = multihash.encode(
      hashlib.sha256(encoded_public_key).digest(),
      multihash.coerce_code("sha2-256"),
    )

    encoded_public_key = encoded_digest

    peer_id = PeerID(encoded_public_key)

    return peer_id
  except Exception as e:
    logger.error(e)
    return None
