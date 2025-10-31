"""
!See README.md
"""

import os
from argparse import ArgumentParser
from pathlib import Path
from secrets import token_hex
from signal import SIGINT, SIGTERM, signal, strsignal
from threading import Event, Thread

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.status import HTTP_403_FORBIDDEN

from mesh.dht import DHT, DHTNode
from mesh.dht.crypto import SignatureValidator
from mesh.mesh_cli.api.api_utils import get_active_keys, load_api_keys
from mesh.substrate.chain_functions import Hypertensor, KeypairFrom
from mesh.substrate.mock.chain_functions import MockHypertensor
from mesh.substrate.mock.local_chain_functions import LocalMockHypertensor
from mesh.utils.authorizers.auth import SignatureAuthorizer
from mesh.utils.authorizers.pos_auth import ProofOfStakeAuthorizer
from mesh.utils.dht import get_node_heartbeats
from mesh.utils.key import get_peer_id_from_identity_path, get_private_key
from mesh.utils.logging import get_logger, use_mesh_log_handler
from mesh.utils.networking import log_visible_maddrs
from mesh.utils.p2p_utils import extract_peer_ip_info, get_peers_ips
from mesh.utils.proof_of_stake import ProofOfStake

use_mesh_log_handler("in_root_logger")
logger = get_logger(__name__)

load_dotenv(os.path.join(Path.cwd(), '.env'))

PHRASE = os.getenv('PHRASE')

dht: DHT = None

"""
Bootnode API

Example:
    curl -H "X-API-Key: key-party1-abc123" http://localhost:8000/get_bootnodes
        returns:
            {
                "value":[
                    "/ip4/127.0.0.1/tcp/31330/p2p/123D",
                    "/ip4/127.0.0.1/udp/31330/quic/p2p/123D"
                ]
            }
    curl -H "X-API-Key: key-party1-abc123" http://localhost:8000/get_heartbeat
    (This returns data based on the unique variables for the subnet nodes that are sent in during the heartbeat submissions)
        returns:
            [
                {
                    "peer_id":"QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                    "server":{
                        "state":2,
                        "role":"validator",
                        "throughput":1.0,
                        "public_name":null,
                        "version":"1.0.0",
                        "using_relay":false,
                        "next_pings":{}},
                        "expiration_time":1759202593.575971
                    }
                ]
    curl -H "X-API-Key: key-party1-abc123" http://localhost:8000/get_peers_info
        returns:
             {
                'QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG': {
                    'location': {
                        'status': 'fail',
                        'message': 'private range',
                        'query': '127.0.0.1'
                    },
                    'multiaddrs': ['/ip4/127.0.0.1/tcp/31332']
                },
                '12D3KooWMUcE668wDF6aTiMmsKFwSV2wJNZ4tNvphVhMziPgg7mN': {
                    'location': {
                        'status': 'fail',
                        'message': 'private range',
                        'query': '127.0.0.1'
                    },
                    'multiaddrs': ['/ip4/127.0.0.1/tcp/41500']
                }
             }

Create endpoint with NGINX for HTTPS encryption

Docs: https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-22-04#step-5-configuring-nginx-to-proxy-requests

server {
    listen 443 ssl;
    server_name bootnode.example.com;

    ssl_certificate /etc/letsencrypt/live/bootnode.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bootnode.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
"""
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    api_keys: set[str] = load_api_keys()
    active_keys = get_active_keys(api_keys)
    if api_key_header in active_keys:
        return api_key_header
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid or missing API Key")

app = FastAPI()
# Limiter for API key
key_limiter = Limiter(key_func=lambda request: request.state.api_key)
# Limiter for IP
ip_limiter = Limiter(key_func=lambda request: request.client.host)
app.state.limiter = key_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware to attach api_key to request.state
@app.middleware("http")
async def attach_api_key(request: Request, call_next):
    api_key = request.query_params.get("api_key") or request.headers.get("x-api-key")
    request.state.api_key = api_key
    return await call_next(request)

def serialize_object(obj):
    """Recursively serialize objects to JSON-compatible formats"""
    # Handle None
    if obj is None:
        return None

    # Handle primitive types
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle peer_id specifically (libp2p ID objects)
    if hasattr(obj, '_b58_str'):
        return obj._b58_str  # Return the base58 string representation

    # Handle enums
    if hasattr(obj, 'value') and hasattr(obj, 'name'):
        return obj.name

    # Handle lists/tuples
    if isinstance(obj, (list, tuple)):
        return [serialize_object(item) for item in obj]

    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: serialize_object(value) for key, value in obj.items()}

    # Handle objects with __dict__ (most custom classes)
    if hasattr(obj, '__dict__'):
        result = {}
        for key, value in obj.__dict__.items():
            # Skip private/internal attributes
            if key.startswith('_'):
                continue
            result[key] = serialize_object(value)
        return result

    # Fallback to string representation
    return str(obj)

@app.get("/get_heartbeat")
@ip_limiter.limit("5/minute")
@key_limiter.limit("5/minute")
async def get_heartbeat(
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """
    Query the DHT for the subnets heartbeats.
    """
    if dht is None:
        return {"error": "DHT not initialized"}
    results = get_node_heartbeats(
        dht,
        uid="node",
        latest=True
    )
    if results:
        try:
            serialized_results = serialize_object(results)
            return {"value": serialized_results}
        except Exception as e:
            logger.warning(f"Error returning heartbeat {e}", exc_info=True)
            return {"error": str(e)}
    return {"value": None}

@app.get("/get_bootnodes")
@ip_limiter.limit("5/minute")
@key_limiter.limit("5/minute")
async def get_bootnodes(
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """
    Query the DHT bootnodes.
    """
    if dht is None:
        return {"error": "DHT not initialized"}
    visible_maddrs = dht.get_visible_maddrs()
    if visible_maddrs:
        try:
            addrs = []
            for addr in visible_maddrs:
                addrs.append(str(addr))
            return {"value": addrs}
        except Exception as e:
            logger.warning(f"Error returning heartbeat {e}", exc_info=True)

    return {"value": None}

@app.get("/get_peers_info")
@ip_limiter.limit("5/minute")
@key_limiter.limit("5/minute")
async def get_peers_info(
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """
    Query the DHT bootnodes.
    """
    if dht is None:
        return {"error": "DHT not initialized"}

    peers_info = {str(peer.peer_id): {"location": extract_peer_ip_info(str(peer.addrs[0])), "multiaddrs": [str(multiaddr) for multiaddr in peer.addrs]} for peer in dht.run_coroutine(get_peers_ips)}
    if peers_info:
        try:
            serialized_results = serialize_object(peers_info)
            return {"value": serialized_results}
        except Exception as e:
            logger.warning(f"Error returning heartbeat {e}", exc_info=True)

    return {"value": None}




def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
Bootnode
"""
async def report_status(dht: DHT, node: DHTNode):
    logger.info(
        f"{len(node.protocol.routing_table.uid_to_peer_id) + 1} DHT nodes (including this one) "
        f"are in the local routing table "
    )
    logger.debug(f"Routing table contents: {node.protocol.routing_table}")
    logger.info(f"Local storage contains {len(node.protocol.storage)} keys")
    logger.debug(f"Local storage contents: {node.protocol.storage}")

    # Contact peers and keep the routing table healthy (remove stale PeerIDs)
    await node.get(f"heartbeat_{token_hex(16)}", latest=True)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--initial_peers",
        nargs="*",
        help="Multiaddrs of the peers that will welcome you into the existing DHT. "
        "Example: /ip4/203.0.113.1/tcp/31337/p2p/XXXX /ip4/203.0.113.2/tcp/7777/p2p/YYYY",
    )
    parser.add_argument(
        "--host_maddrs",
        nargs="*",
        default=["/ip4/0.0.0.0/tcp/0"],
        help="Multiaddrs to listen for external connections from other DHT instances. "
        "Defaults to all IPv4 interfaces and the TCP protocol: /ip4/0.0.0.0/tcp/0",
    )
    parser.add_argument(
        "--announce_maddrs",
        nargs="*",
        help="Visible multiaddrs the host announces for external connections from other DHT instances",
    )
    parser.add_argument(
        "--use_ipfs",
        action="store_true",
        help='Use IPFS to find initial_peers. If enabled, you only need to provide the "/p2p/XXXX" '
        "part of the multiaddrs for the initial_peers "
        "(no need to specify a particular IPv4/IPv6 host and port)",
    )
    parser.add_argument(
        "--identity_path",
        help="Path to a private key file. If defined, makes the peer ID deterministic. "
        "If the file does not exist, writes a new private key to this file.",
    )
    parser.add_argument(
        "--use_relay",
        action="store_true",
        dest="use_relay",
        help="Disable circuit relay functionality in libp2p (see https://docs.libp2p.io/concepts/nat/circuit-relay/)",
    )
    parser.add_argument(
        "--use_auto_relay",
        action="store_true",
        help="Look for libp2p relays to become reachable if we are behind NAT/firewall",
    )
    parser.add_argument(
        "--refresh_period", type=int, default=30, help="Period (in seconds) for fetching the keys from DHT"
    )
    parser.add_argument('--subnet_id', type=int, required=False, default=None, help='Subnet ID running a node for ')
    parser.add_argument("--no_blockchain_rpc", action="store_true", help="[Testing] Run with no RPC")
    parser.add_argument("--local_rpc", action="store_true", help="[Testing] Run in local RPC mode, uses LOCAL_RPC")
    parser.add_argument("--phrase", type=str, required=False, help="[Testing] Coldkey phrase that controls actions which include funds, such as registering, and staking")
    parser.add_argument("--private_key", type=str, required=False, help="[Testing] Hypertensor blockchain private key")

    args = parser.parse_args()

    subnet_id = args.subnet_id
    no_blockchain_rpc = args.no_blockchain_rpc
    local_rpc = args.local_rpc
    phrase = args.phrase
    private_key = args.private_key

    if no_blockchain_rpc is False:
        if local_rpc:
            rpc = os.getenv('LOCAL_RPC')
        else:
            rpc = os.getenv('DEV_RPC')

        if phrase is not None:
            hypertensor = Hypertensor(rpc, phrase)
        elif private_key is not None:
            hypertensor = Hypertensor(rpc, private_key, KeypairFrom.PRIVATE_KEY)
        else:
            hypertensor = Hypertensor(rpc, PHRASE)
    else:
        # hypertensor = MockHypertensor()
        peer_id = get_peer_id_from_identity_path(args.identity_path)
        reset_db = False
        if args.initial_peers:
            # Reset when deploying a new swarm
            reset_db = True
        hypertensor = LocalMockHypertensor(
            subnet_id=subnet_id,
            peer_id=peer_id,
            subnet_node_id=0,
            coldkey="",
            hotkey="",
            bootnode_peer_id="",
            client_peer_id="",
            reset_db=reset_db,
        )

    pk = get_private_key(args.identity_path)

    signature_validator = SignatureValidator(pk)
    record_validators=[signature_validator]

    signature_authorizer = SignatureAuthorizer(pk)

    if hypertensor is not None:
        logger.info("Initializing PoS - proof-of-stake")
        pos = ProofOfStake(
            subnet_id,
            hypertensor,
            min_class=1,
        )
        pos_authorizer = ProofOfStakeAuthorizer(signature_authorizer, pos)
    else:
        # For testing purposes, at minimum require signatures
        pos_authorizer = signature_authorizer

    global dht
    # dht = DHT(
    #     start=True,
    #     initial_peers=args.initial_peers,
    #     host_maddrs=args.host_maddrs,
    #     announce_maddrs=args.announce_maddrs,
    #     use_ipfs=args.use_ipfs,
    #     identity_path=args.identity_path,
    #     use_relay=args.use_relay,
    #     use_auto_relay=args.use_auto_relay,
    # )
    dht = DHT(
        start=True,
        initial_peers=args.initial_peers,
        host_maddrs=args.host_maddrs,
        announce_maddrs=args.announce_maddrs,
        use_ipfs=args.use_ipfs,
        identity_path=args.identity_path,
        use_relay=args.use_relay,
        use_auto_relay=args.use_auto_relay,
        record_validators=record_validators,
        **dict(authorizer=pos_authorizer)
    )

    log_visible_maddrs(dht.get_visible_maddrs(), only_p2p=args.use_ipfs)

    # Run the FastAPI server in a thread
    api_thread = Thread(target=run_api, daemon=True)
    api_thread.start()

    exit_event = Event()

    def signal_handler(signal_number: int, _) -> None:
        logger.info(f"Caught signal {signal_number} ({strsignal(signal_number)}), shutting down")
        exit_event.set()

    signal(SIGTERM, signal_handler)
    signal(SIGINT, signal_handler)

    try:
        while not exit_event.is_set():
            dht.run_coroutine(report_status, return_future=False)
            exit_event.wait(args.refresh_period)
    finally:
        dht.shutdown()


if __name__ == "__main__":
    main()
