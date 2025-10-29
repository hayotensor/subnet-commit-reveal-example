import json
import os
from pathlib import Path

import torch
from dotenv import load_dotenv

load_dotenv(os.path.join(Path.cwd(), '.env'))

"""
NOTE: In production, we get the bootnodes from the blockchain

Default bootstrap nodes

# How to use:
    Add PUBLIC_INITIAL_PEERS in the .env file as:

    PUBLIC_INITIAL_PEERS = ['/ip4/{IP}/tcp/{PORT}/p2p/{PeerID}']
"""
raw_peers = os.getenv('PUBLIC_INITIAL_PEERS')
if raw_peers is None:
    raise ValueError("PUBLIC_INITIAL_PEERS not set in .env")

# If the string is quoted (single or double), strip those quotes
if (raw_peers.startswith('"') and raw_peers.endswith('"')) or \
   (raw_peers.startswith("'") and raw_peers.endswith("'")):
    raw_peers = raw_peers[1:-1]

try:
    PUBLIC_INITIAL_PEERS = json.loads(raw_peers)
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to parse PUBLIC_INITIAL_PEERS as JSON: {e}")

# The reachability API is currently used only when connecting to the public swarm
# ** This is NOT required **
# If the subnet has a centralized dashboard, this can be used to ensure the dashboard
# can reach the node
REACHABILITY_API_URL = "https://dashboard.subnet-name.com"

DTYPE_MAP = dict(bfloat16=torch.bfloat16, float16=torch.float16, float32=torch.float32, auto="auto")
