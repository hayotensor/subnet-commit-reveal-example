import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from mesh.substrate.chain_functions import Hypertensor, KeypairFrom
from mesh.utils.logging import get_logger

load_dotenv(os.path.join(Path.cwd(), '.env'))

PHRASE = os.getenv('PHRASE')

logger = get_logger(__name__)

"""
register-subnet \
--max_cost 100.00 \
--name subnet-1 \
--repo github.com/subnet-1 \
--description "artificial intelligence" \
--misc "cool subnet" \
--churn_limit 64 \
--min_stake 100.00 \
--max_stake  1000.00 \
--delegate_stake_percentage 0.1 \
--subnet_node_queue_epochs 10 \
--idle_classification_epochs 10 \
--included_classification_epochs 10 \
--max_node_penalties 10 \
--initial_coldkeys ["0x0123456789abcdef0123456789abcdef01234567"] \
--max_registered_nodes 10 \
--key_types ["Rsa"] \
--bootnodes "p2p/12.0.1/tpc" \
--phrase "craft squirrel soap letter garment unfair meat slide swift miss forest wide" \
--local_rpc

[Local]

Alith

register-subnet \
--max_cost 100.00 \
--name subnet-1 \
--repo github.com/subnet-1 \
--description "artificial intelligence" \
--misc "cool subnet" \
--churn_limit 64 \
--min_stake 100.00 \
--max_stake  1000.00 \
--delegate_stake_percentage 0.1 \
--subnet_node_queue_epochs 10 \
--idle_classification_epochs 10 \
--included_classification_epochs 10 \
--max_node_penalties 10 \
--initial_coldkeys "0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac" "0x3Cd0A705a2DC65e5b1E1205896BaA2be8A07c6e0" "0x798d4Ba9baf0064Ec19eB4F0a1a45785ae9D6DFc" "0x773539d4Ac0e786233D90A233654ccEE26a613D9" \
--max_registered_nodes 10 \
--key_types "Rsa" \
--bootnodes "p2p/12.0.1/tpc" \
--private_key "0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133" \
--local_rpc

"""

def main():
    # fmt:off
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--max_cost", type=float, required=True, help="Max cost you want to pay to register the subnet")
    parser.add_argument("--name", type=str, required=True, help="Subnet name (unique)")
    parser.add_argument("--repo", type=str, required=True, help="Subnet repository (unique)")
    parser.add_argument("--description", type=str, required=True, help="A short description of what the subnet does")
    parser.add_argument("--misc", type=str, required=True, help="Misc information about the subnet")
    parser.add_argument("--churn_limit", type=int, required=True, help="Number of subnet activations per epoch")
    parser.add_argument("--min_stake", type=float, required=True, help="Minimum stake balance to register a Subnet Node in the subnet")
    parser.add_argument("--max_stake", type=float, required=True, help="Maximum stake balance to register a Subnet Node in the subnet")
    parser.add_argument("--delegate_stake_percentage", type=float, required=True, help="Percentage of emissions that are allocated to delegate stakers as decimal (100% == 1.0)")
    parser.add_argument("--subnet_node_queue_epochs", type=int, required=True, help="Number of epochs for registered nodes to be in queue before activation")
    parser.add_argument("--idle_classification_epochs", type=int, required=True, help="Number of epochs in Idle classification (See SubnetNodeClass)")
    parser.add_argument("--included_classification_epochs", type=int, required=True, help="Number of epochs in Included classification (See SubnetNodeClass)")
    parser.add_argument("--max_node_penalties", type=int, required=True, help="Number of penalties to be removed")
    parser.add_argument("--max_registered_nodes", type=int, required=True, help="Maximum number of nodes that can be registered at any time")
    parser.add_argument("--initial_coldkeys", type=str, nargs='+', required=True, help="List of initial coldkeys that can register while subnet is in registration")
    parser.add_argument("--key_types", type=str, nargs='+', required=True, help="Key type of subnet signature system")
    parser.add_argument("--bootnodes", type=str, nargs='+', required=True, help="Key type of subnet signature system")
    parser.add_argument("--local_rpc", action="store_true", help="[Testing] Run in local RPC mode, uses LOCAL_RPC")
    parser.add_argument("--phrase", type=str, required=False, help="[Testing] Coldkey phrase that controls actions which include funds, such as registering, and staking")
    parser.add_argument("--private_key", type=str, required=False, help="[Testing] Hypertensor blockchain private key")

    args = parser.parse_args()
    local_rpc = args.local_rpc
    phrase = args.phrase
    private_key = args.private_key

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

    hotkey = hypertensor.keypair.ss58_address
    max_cost = int(args.max_cost * 1e18)
    assert max_cost > 0, "Max cost must be greater than zero"
    name = args.name
    repo = args.repo
    description = args.description
    misc = args.misc
    churn_limit = args.churn_limit
    min_stake = int(args.min_stake * 1e18)
    max_stake = int(args.max_stake * 1e18)
    assert min_stake <= max_stake, "min_stake must be less than or equal to max_stake"
    delegate_stake_percentage = 1e18 if args.delegate_stake_percentage > 1.0 else int(args.delegate_stake_percentage * 1e18)
    assert delegate_stake_percentage <= 0.95e18, "delegate_stake_percentage must be less than or equal to 95%"
    subnet_node_queue_epochs = args.subnet_node_queue_epochs
    idle_classification_epochs = args.idle_classification_epochs
    included_classification_epochs = args.included_classification_epochs
    max_node_penalties = args.max_node_penalties
    initial_coldkeys = args.initial_coldkeys
    max_registered_nodes = args.max_registered_nodes
    key_types = args.key_types
    bootnodes = args.bootnodes

    try:
        receipt = hypertensor.register_subnet(
            hotkey,
            max_cost,
            name,
            repo,
            description,
            misc,
            churn_limit,
            min_stake,
            max_stake,
            delegate_stake_percentage,
            subnet_node_queue_epochs,
            idle_classification_epochs,
            included_classification_epochs,
            max_node_penalties,
            max_registered_nodes,
            initial_coldkeys,
            key_types,
            bootnodes,
        )
        if receipt.is_success:
            logger.info('✅ Success, triggered events:')
            for event in receipt.triggered_events:
                print(f'* {event.value}')
        else:
            logger.error(f'⚠️ Extrinsic Failed: {receipt.error_message}')
    except Exception as e:
        logger.error("Error: ", e, exc_info=True)

if __name__ == "__main__":
    main()
