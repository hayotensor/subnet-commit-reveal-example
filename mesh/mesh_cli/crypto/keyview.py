import argparse

from mesh.utils.key import get_peer_id_from_identity_path
from mesh.utils.logging import get_logger

logger = get_logger(__name__)

# View peer ID by inputing path

"""
keyview --path alith.id
"""

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--path", type=str, required=False, default="private_key.key", help="The path to the private key that generates the peer ID. ")

    args = parser.parse_args()
    path = args.path

    peer_id = get_peer_id_from_identity_path(path)

    logger.info(f"Peer ID {peer_id}")

if __name__ == "__main__":
    main()
