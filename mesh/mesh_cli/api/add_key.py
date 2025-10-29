from argparse import ArgumentParser

from mesh.mesh_cli.api.api_utils import add_api_key
from mesh.utils import get_logger

logger = get_logger(__name__)

"""
mesh-add-api-key --owner <owner_name>
"""
def main():
    parser = ArgumentParser(description="Manage bootnode API keys")
    parser.add_argument("--owner", required=True, help="Owner name to add a new API key")
    parser.add_argument("--key", help="Optional: custom key value")
    parser.add_argument("--inactive", action="store_true", help="Create key as inactive")
    args = parser.parse_args()

    if args.owner:
        add_api_key(args.owner, key=args.key, active=not args.inactive)
    else:
        logger.info("No action specified. Use --owner OWNER")

if __name__ == "__main__":
    main()
