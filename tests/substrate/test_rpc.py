


from dataclasses import dataclass
from typing import Any

import pytest
import scalecodec
from scalecodec.base import RuntimeConfiguration, ScaleBytes
from scalecodec.type_registry import load_type_registry_preset

from mesh.substrate.chain_functions import Hypertensor, KeypairFrom

# custom_rpc_type_registry = {
#   "types": {
#     "SubnetData": {
#       "type": "struct",
#       "type_mapping": [
#         ["id", "u32"],
#         ["name", "Vec<u8>"],
#         ["repo", "Vec<u8>"],
#         ["description", "Vec<u8>"],
#         ["misc", "Vec<u8>"],
#         ["state", "SubnetState"],
#         ["start_epoch", "u32"],
#       ],
#     },
#     "SubnetInfo": {
#       "type": "struct",
#       "type_mapping": [
#         ["id", "u32"],
#         ["name", "Vec<u8>"],
#         ["repo", "Vec<u8>"],
#         ["description", "Vec<u8>"],
#         ["misc", "Vec<u8>"],
#         ["state", "SubnetState"],
#         ["start_epoch", "u32"],
#         ["churn_limit", "u32"],
#         ["min_stake", "u128"],
#         ["max_stake", "u128"],
#         ["queue_immunity_epochs", "u32"],
#         ["target_node_registrations_per_epoch", "u32"],
#         ["subnet_node_queue_epochs", "u32"],
#         ["idle_classification_epochs", "u32"],
#         ["included_classification_epochs", "u32"],
#         ["delegate_stake_percentage", "u128"],
#         ["node_burn_rate_alpha", "u128"],
#         ["max_node_penalties", "u32"],
#         ["initial_coldkeys", "Option<Vec<[u8; 20]>>"],
#         ["max_registered_nodes", "u32"],
#         ["owner", "Option<[u8; 20]>"],
#         ["pending_owner", "Option<[u8; 20]>"],
#         ["registration_epoch", "Option<u32>"],
#         ["key_types", "BTreeSet<KeyType>"],
#         ["slot_index", "Option<u32>"],
#         ["penalty_count", "u32"],
#         ["bootnode_access", "BTreeSet<[u8; 20]>"],
#         ["bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["total_nodes", "u32"],
#         ["total_active_nodes", "u32"],
#         ["total_electable_nodes", "u32"],
#         ["current_min_delegate_stake", "u128"]
#       ],
#     },
#     "SubnetState": {
#       "type": "enum",
#       "value_list": [
#         "Registered",
#         "Active",
#         "Paused",
#       ],
#     },
#     "KeyType": {
#       "type": "enum",
#       "value_list": [
#         "Rsa",
#         "Ed25519",
#         "Secp256k1",
#         "Ecdsa",
#       ],
#     },
#     "SubnetNode": {
#       "type": "struct",
#       "type_mapping": [
#         ["id", "u32"],
#         ["hotkey", "[u8; 20]"],
#         ["peer_id", "OpaquePeerId"],
#         ["bootnode_peer_id", "OpaquePeerId"],
#         ["bootnode", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["client_peer_id", "OpaquePeerId"],
#         ["classification", "SubnetNodeClassification"],
#         ["delegate_reward_rate", "u128"],
#         ["last_delegate_reward_rate_update", "u32"],
#         ["unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["non_unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
#       ],
#     },
#     "SubnetNodeClassification": {
#       "type": "struct",
#       "type_mapping": [
#         ["node_class", "SubnetNodeClass"],
#         ["start_epoch", "u32"],
#       ],
#     },
#     "SubnetNodeClass": {
#       "type": "enum",
#       "value_list": [
#         "Registered",
#         "Idle",
#         "Included",
#         "Validator",
#       ],
#     },
#     "SubnetNodeConsensusData": {
#       "type": "struct",
#       "type_mapping": [
#         ["subnet_node_id", "u32"],
#         ["score", "u128"],
#       ],
#     },
#     "RewardsData": {
#       "type": "struct",
#       "type_mapping": [
#         ["overall_subnet_reward", "u128"],
#         ["subnet_owner_reward", "u128"],
#         ["subnet_rewards", "u128"],
#         ["delegate_stake_rewards", "u128"],
#         ["subnet_node_rewards", "u128"],
#       ],
#     },
#     "SubnetNodeInfo": {
#       "type": "struct",
#       "type_mapping": [
#         ["subnet_id", "u32"],
#         ["subnet_node_id", "u32"],
#         ["coldkey", "[u8; 20]"],
#         ["hotkey", "[u8; 20]"],
#         ["peer_id", "PeerId"],
#         ["bootnode_peer_id", "PeerId"],
#         ["client_peer_id", "PeerId"],
#         ["bootnode", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["identity", "ColdkeyIdentityData"],
#         ["classification", "SubnetNodeClassification"],
#         ["delegate_reward_rate", "u128"],
#         ["last_delegate_reward_rate_update", "u32"],
#         ["unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["non_unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["stake_balance", "u128"],
#         ["node_delegate_stake_balance", "u128"],
#         ["penalties", "u32"],
#         ["reputation", "Reputation"],
#       ],
#     },
#     "Reputation": {
#       "type": "struct",
#       "type_mapping": [
#         ["start_epoch", "u32"],
#         ["score", "u128"],
#         ["lifetime_node_count", "u32"],
#         ["total_active_nodes", "u32"],
#         ["total_increases", "u32"],
#         ["total_decreases", "u32"],
#         ["average_attestation", "u128"],
#         ["last_validator_epoch", "u32"],
#         ["ow_score", "u128"],
#       ],
#     },
#     "ColdkeyIdentityData": {
#       "type": "struct",
#       "type_mapping": [
#         ["name", "BoundedVec<u8, DefaultMaxVectorLength>"],
#         ["url", "BoundedVec<u8, DefaultMaxUrlLength>"],
#         ["image", "BoundedVec<u8, DefaultMaxUrlLength>"],
#         ["discord", "BoundedVec<u8, DefaultMaxSocialIdLength>"],
#         ["x", "BoundedVec<u8, DefaultMaxSocialIdLength>"],
#         ["telegram", "BoundedVec<u8, DefaultMaxSocialIdLength>"],
#         ["github", "BoundedVec<u8, DefaultMaxUrlLength>"],
#         ["hugging_face", "BoundedVec<u8, DefaultMaxUrlLength>"],
#         ["description", "BoundedVec<u8, DefaultMaxVectorLength>"],
#         ["misc", "BoundedVec<u8, DefaultMaxVectorLength>"],
#       ],
#     },
#     "AttestEntry": {
#       "type": "struct",
#       "type_mapping": [
#         ["block", "u32"],
#         ["data", "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>"]
#       ]
#     },
#     "ConsensusData": {
#       "type": "struct",
#       "type_mapping": [
#         ["validator_id", "u32"],
#         ["validator_epoch_progress", "u128"],
#         ["attests", "BTreeMap<u32, AttestEntry>"],
#         ["subnet_nodes", "Vec<SubnetNode<[u8; 20]>>"],
#         ["prioritize_queue_node_id", "Option<u32>"],
#         ["remove_queue_node_id", "Option<u32>"],
#         ["data", "Vec<SubnetNodeConsensusData>"],
#         ["args", "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>"],
#       ],
#     },
#     "ConsensusSubmissionData": {
#       "type": "struct",
#       "type_mapping": [
#         ["validator_subnet_node_id", "u32"],
#         ["attestation_ratio", "u128"],
#         ["weight_sum", "u128"],
#         ["data_length", "u32"],
#         ["data", "Vec<SubnetNodeConsensusData>"],
#         ["attests", "BTreeMap<u32, AttestEntry>"],
#         ["subnet_nodes", "Vec<SubnetNode<[u8; 20]>>"],
#         ["prioritize_queue_node_id", "Option<u32>"],
#         ["remove_queue_node_id", "Option<u32>"],
#       ],
#     },
#     "AllSubnetBootnodes": {
#       "type": "struct",
#       "type_mapping": [
#         ["bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
#         ["node_bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
#       ],
#     },
#     "SubnetNodeStakeInfo": {
#       "type": "struct",
#       "type_mapping": [
#         ["subnet_id", "Option<u32>"],
#         ["subnet_node_id", "Option<u32>"],
#         ["hotkey", "[u8; 20]"],
#         ["balance", "u128"],
#       ],
#     },
#     "DelegateStakeInfo": {
#       "type": "struct",
#       "type_mapping": [
#         ["subnet_id", "u32"],
#         ["shares", "u128"],
#         ["balance", "u128"],
#       ],
#     },
#     "NodeDelegateStakeInfo": {
#       "type": "struct",
#       "type_mapping": [
#         ["subnet_id", "u32"],
#         ["subnet_node_id", "u32"],
#         ["shares", "u128"],
#         ["balance", "u128"],
#       ],
#     },
#     "PeerId": "Vec<u8>",
#     "BoundedVec<u8, DefaultMaxVectorLength>": "Vec<u8>",
#     "BoundedVec<u8, DefaultMaxUrlLength>": "Vec<u8>",
#     "BoundedVec<u8, DefaultMaxSocialIdLength>": "Vec<u8>",
#     "BoundedVec<u8, DefaultValidatorArgsLimit>": "Vec<u8>",
#     "Option<BoundedVec<u8, DefaultMaxVectorLength>>": "Option<Vec<u8>>",
#     "Option<BoundedVec<u8, DefaultMaxUrlLength>>": "Option<Vec<u8>>",
#     "Option<BoundedVec<u8, DefaultMaxSocialIdLength>>": "Option<Vec<u8>>",
#     "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>": "Option<Vec<u8>>",
#     "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>": "Vec<u8>",
#   }
# }
custom_rpc_type_registry = {
  "types": {
    "SubnetData": {
      "type": "struct",
      "type_mapping": [
        ["id", "u32"],
        ["name", "Vec<u8>"],
        ["repo", "Vec<u8>"],
        ["description", "Vec<u8>"],
        ["misc", "Vec<u8>"],
        ["state", "SubnetState"],
        ["start_epoch", "u32"],
      ],
    },
    "SubnetInfo": {
      "type": "struct",
      "type_mapping": [
        ["id", "u32"],
        ["name", "Vec<u8>"],
        ["repo", "Vec<u8>"],
        ["description", "Vec<u8>"],
        ["misc", "Vec<u8>"],
        ["state", "SubnetState"],
        ["start_epoch", "u32"],
        ["churn_limit", "u32"],
        ["min_stake", "u128"],
        ["max_stake", "u128"],
        ["queue_immunity_epochs", "u32"],
        ["target_node_registrations_per_epoch", "u32"],
        ["subnet_node_queue_epochs", "u32"],
        ["idle_classification_epochs", "u32"],
        ["included_classification_epochs", "u32"],
        ["delegate_stake_percentage", "u128"],
        ["node_burn_rate_alpha", "u128"],
        ["max_node_penalties", "u32"],
        ["initial_coldkeys", "Option<Vec<[u8; 20]>>"],
        ["max_registered_nodes", "u32"],
        ["owner", "Option<[u8; 20]>"],
        ["pending_owner", "Option<[u8; 20]>"],
        ["registration_epoch", "Option<u32>"],
        ["key_types", "BTreeSet<KeyType>"],
        ["slot_index", "Option<u32>"],
        ["penalty_count", "u32"],
        ["bootnode_access", "BTreeSet<[u8; 20]>"],
        ["bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["total_nodes", "u32"],
        ["total_active_nodes", "u32"],
        ["total_electable_nodes", "u32"],
        ["current_min_delegate_stake", "u128"]
      ],
    },
    "SubnetState": {
      "type": "enum",
      "value_list": [
        "Registered",
        "Active",
        "Paused",
      ],
    },
    "KeyType": {
      "type": "enum",
      "value_list": [
        "Rsa",
        "Ed25519",
        "Secp256k1",
        "Ecdsa",
      ],
    },
    "SubnetNode": {
      "type": "struct",
      "type_mapping": [
        ["id", "u32"],
        ["hotkey", "[u8; 20]"],
        ["peer_id", "OpaquePeerId"],
        ["bootnode_peer_id", "OpaquePeerId"],
        ["bootnode", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["client_peer_id", "OpaquePeerId"],
        ["classification", "SubnetNodeClassification"],
        ["delegate_reward_rate", "u128"],
        ["last_delegate_reward_rate_update", "u32"],
        ["unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["non_unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
      ],
    },
    "SubnetNodeClassification": {
      "type": "struct",
      "type_mapping": [
        ["node_class", "SubnetNodeClass"],
        ["start_epoch", "u32"],
      ],
    },
    "SubnetNodeClass": {
      "type": "enum",
      "value_list": [
        "Registered",
        "Idle",
        "Included",
        "Validator",
      ],
    },
    "SubnetNodeConsensusData": {
      "type": "struct",
      "type_mapping": [
        ["subnet_node_id", "u32"],
        ["score", "u128"],
      ],
    },
    "RewardsData": {
      "type": "struct",
      "type_mapping": [
        ["overall_subnet_reward", "u128"],
        ["subnet_owner_reward", "u128"],
        ["subnet_rewards", "u128"],
        ["delegate_stake_rewards", "u128"],
        ["subnet_node_rewards", "u128"],
      ],
    },
    "SubnetNodeInfo": {
      "type": "struct",
      "type_mapping": [
        ["subnet_id", "u32"],
        ["subnet_node_id", "u32"],
        ["coldkey", "[u8; 20]"],
        ["hotkey", "[u8; 20]"],
        ["peer_id", "PeerId"],
        ["bootnode_peer_id", "PeerId"],
        ["client_peer_id", "PeerId"],
        ["bootnode", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["identity", "ColdkeyIdentityData"],
        ["classification", "SubnetNodeClassification"],
        ["delegate_reward_rate", "u128"],
        ["last_delegate_reward_rate_update", "u32"],
        ["unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["non_unique", "Option<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["stake_balance", "u128"],
        ["node_delegate_stake_balance", "u128"],
        ["penalties", "u32"],
        ["reputation", "Reputation"],
      ],
    },
    "Reputation": {
      "type": "struct",
      "type_mapping": [
        ["start_epoch", "u32"],
        ["score", "u128"],
        ["lifetime_node_count", "u32"],
        ["total_active_nodes", "u32"],
        ["total_increases", "u32"],
        ["total_decreases", "u32"],
        ["average_attestation", "u128"],
        ["last_validator_epoch", "u32"],
        ["ow_score", "u128"],
      ],
    },
    "ColdkeyIdentityData": {
      "type": "struct",
      "type_mapping": [
        ["name", "BoundedVec<u8, DefaultMaxVectorLength>"],
        ["url", "BoundedVec<u8, DefaultMaxUrlLength>"],
        ["image", "BoundedVec<u8, DefaultMaxUrlLength>"],
        ["discord", "BoundedVec<u8, DefaultMaxSocialIdLength>"],
        ["x", "BoundedVec<u8, DefaultMaxSocialIdLength>"],
        ["telegram", "BoundedVec<u8, DefaultMaxSocialIdLength>"],
        ["github", "BoundedVec<u8, DefaultMaxUrlLength>"],
        ["hugging_face", "BoundedVec<u8, DefaultMaxUrlLength>"],
        ["description", "BoundedVec<u8, DefaultMaxVectorLength>"],
        ["misc", "BoundedVec<u8, DefaultMaxVectorLength>"],
      ],
    },
    "AttestEntry": {
      "type": "struct",
      "type_mapping": [
        ["block", "u32"],
        ["attestor_progress", "u128"],
        ["reward_factor", "u128"],
        ["data", "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>"]
      ]
    },
    "ConsensusData": {
      "type": "struct",
      "type_mapping": [
        ["validator_id", "u32"],
        ["block", "u32"],
        ["validator_epoch_progress", "u128"],
        ["validator_reward_factor", "u128"],
        ["attests", "BTreeMap<u32, AttestEntry>"],
        ["subnet_nodes", "Vec<SubnetNode<[u8; 20]>>"],
        ["prioritize_queue_node_id", "Option<u32>"],
        ["remove_queue_node_id", "Option<u32>"],
        ["data", "Vec<SubnetNodeConsensusData>"],
        ["args", "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>"],
      ],
    },
    "ConsensusSubmissionData": {
      "type": "struct",
      "type_mapping": [
        ["validator_subnet_node_id", "u32"],
        ["validator_epoch_progress", "u128"],
        ["validator_reward_factor", "u128"],
        ["attestation_ratio", "u128"],
        ["weight_sum", "u128"],
        ["data_length", "u32"],
        ["data", "Vec<SubnetNodeConsensusData>"],
        ["attests", "BTreeMap<u32, AttestEntry>"],
        ["subnet_nodes", "Vec<SubnetNode<[u8; 20]>>"],
        ["prioritize_queue_node_id", "Option<u32>"],
        ["remove_queue_node_id", "Option<u32>"],
      ],
    },
    "AllSubnetBootnodes": {
      "type": "struct",
      "type_mapping": [
        ["bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
        ["node_bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
      ],
    },
    "SubnetNodeStakeInfo": {
      "type": "struct",
      "type_mapping": [
        ["subnet_id", "Option<u32>"],
        ["subnet_node_id", "Option<u32>"],
        ["hotkey", "[u8; 20]"],
        ["balance", "u128"],
      ],
    },
    "DelegateStakeInfo": {
      "type": "struct",
      "type_mapping": [
        ["subnet_id", "u32"],
        ["shares", "u128"],
        ["balance", "u128"],
      ],
    },
    "NodeDelegateStakeInfo": {
      "type": "struct",
      "type_mapping": [
        ["subnet_id", "u32"],
        ["subnet_node_id", "u32"],
        ["shares", "u128"],
        ["balance", "u128"],
      ],
    },
    "PeerId": "Vec<u8>",
    "BTreeSet<KeyType>": "Vec<KeyType>",
    "BTreeSet<[u8; 20]>": "Vec<[u8; 20]>",
    "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>": "Vec<BoundedVec<u8, DefaultMaxVectorLength>>",  # Not just Vec<u8>
    "BoundedVec<u8, DefaultMaxVectorLength>": "Vec<u8>",
    "BoundedVec<u8, DefaultMaxUrlLength>": "Vec<u8>",
    "BoundedVec<u8, DefaultMaxSocialIdLength>": "Vec<u8>",
    "BoundedVec<u8, DefaultValidatorArgsLimit>": "Vec<u8>",
    "Option<BoundedVec<u8, DefaultMaxVectorLength>>": "Option<Vec<u8>>",
    "Option<BoundedVec<u8, DefaultMaxUrlLength>>": "Option<Vec<u8>>",
    "Option<BoundedVec<u8, DefaultMaxSocialIdLength>>": "Option<Vec<u8>>",
    "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>": "Option<Vec<u8>>",
  }
}

LOCAL_RPC="ws://127.0.0.1:9944"

# pytest tests/substrate/test_rpc.py -rP

hypertensor = Hypertensor(LOCAL_RPC, "0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133", KeypairFrom.PRIVATE_KEY)

# pytest tests/substrate/test_rpc.py::test_get_subnet_info -rP

def test_get_subnet_info():
    # debug_custom_rpc_type_registry = {
    #   "types": {
    #     "SubnetInfo": {
    #       "type": "struct",
    #       "type_mapping": [
    #         ["id", "u32"],
    #         ["name", "Vec<u8>"],
    #         ["repo", "Vec<u8>"],
    #         ["description", "Vec<u8>"],
    #         ["misc", "Vec<u8>"],
    #         ["state", "SubnetState"],
    #         ["start_epoch", "u32"],
    #         ["churn_limit", "u32"],
    #         ["min_stake", "u128"],
    #         ["max_stake", "u128"],
    #         ["queue_immunity_epochs", "u32"],
    #         ["target_node_registrations_per_epoch", "u32"],
    #         ["subnet_node_queue_epochs", "u32"],
    #         ["idle_classification_epochs", "u32"],
    #         ["included_classification_epochs", "u32"],
    #         ["delegate_stake_percentage", "u128"],
    #         ["node_burn_rate_alpha", "u128"],
    #         ["max_node_penalties", "u32"],
    #         ["initial_coldkeys", "Option<Vec<[u8; 20]>>"],
    #         ["max_registered_nodes", "u32"],
    #         ["owner", "Option<[u8; 20]>"],
    #         ["pending_owner", "Option<[u8; 20]>"],
    #         ["registration_epoch", "Option<u32>"],
    #         ["key_types", "BTreeSet<KeyType>"],
    #         ["slot_index", "Option<u32>"],
    #         ["penalty_count", "u32"],
    #         ["bootnode_access", "BTreeSet<[u8; 20]>"],
    #         ["bootnodes", "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>"],
    #         ["total_nodes", "u32"],
    #         ["total_active_nodes", "u32"],
    #         ["total_electable_nodes", "u32"],
    #         ["current_min_delegate_stake", "u128"]
    #       ],
    #     },
    #     "SubnetState": {
    #       "type": "enum",
    #       "value_list": [
    #         "Registered",
    #         "Active",
    #         "Paused",
    #       ],
    #     },
    #     "KeyType": {
    #       "type": "enum",
    #       "value_list": [
    #         "Rsa",
    #         "Ed25519",
    #         "Secp256k1",
    #         "Ecdsa",
    #       ],
    #     },
    #     "BTreeSet<KeyType>": "Vec<KeyType>",
    #     "BTreeSet<[u8; 20]>": "Vec<[u8; 20]>",
    #     "BTreeSet<BoundedVec<u8, DefaultMaxVectorLength>>": "Vec<BoundedVec<u8, DefaultMaxVectorLength>>",  # Not just Vec<u8>
    #     "BoundedVec<u8, DefaultMaxVectorLength>": "Vec<u8>",
    #     "BoundedVec<u8, DefaultMaxUrlLength>": "Vec<u8>",
    #     "BoundedVec<u8, DefaultMaxSocialIdLength>": "Vec<u8>",
    #     "BoundedVec<u8, DefaultValidatorArgsLimit>": "Vec<u8>",
    #     "Option<BoundedVec<u8, DefaultMaxVectorLength>>": "Option<Vec<u8>>",
    #     "Option<BoundedVec<u8, DefaultMaxUrlLength>>": "Option<Vec<u8>>",
    #     "Option<BoundedVec<u8, DefaultMaxSocialIdLength>>": "Option<Vec<u8>>",
    #     "Option<BoundedVec<u8, DefaultValidatorArgsLimit>>": "Option<Vec<u8>>",
    #   }
    # }

    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getSubnetInfo',
            params=[1]
        )
        scale_obj = rpc_runtime_config.create_scale_object("Option<SubnetInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Option<SubnetInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Option<SubnetInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_subnet_info_formatted -rP

def test_get_subnet_info_formatted():
  subnet_info = hypertensor.get_formatted_subnet_info(1)
  print("subnet_info", subnet_info)

# pytest tests/substrate/test_rpc.py::test_get_all_subnet_info -rP

def test_get_all_subnet_info():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getAllSubnetsInfo',
            params=[]
        )

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_all_subnet_info_formatted -rP

def test_get_all_subnet_info_formatted():
  subnet_info = hypertensor.get_formatted_all_subnet_info()
  print(subnet_info)


# pytest tests/substrate/test_rpc.py::test_get_subnet_node_info -rP

def test_get_subnet_node_info():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getSubnetNodeInfo',
            params=[1,1]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Option<SubnetNodeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Option<SubnetNodeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Option<SubnetNodeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_subnet_node_info_formatted -rP

def test_get_subnet_node_info_formatted():
  subnet_node_info = hypertensor.get_formatted_get_subnet_node_info(1, 1)
  print(subnet_node_info)

# pytest tests/substrate/test_rpc.py::test_get_min_class_subnet_nodes_formatted -rP

def test_get_min_class_subnet_nodes_formatted():
  subnet_node_info = hypertensor.get_min_class_subnet_nodes_formatted(1, 0, 1)
  print(subnet_node_info)

# pytest tests/substrate/test_rpc.py::test_get_subnet_nodes_info -rP

def test_get_subnet_nodes_info():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getSubnetNodesInfo',
            params=[1]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Vec<SubnetNodeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_subnet_nodes_info_formatted -rP

def test_get_subnet_nodes_info_formatted():
  subnet_node_info = hypertensor.get_subnet_nodes_info_formatted(1)
  print(subnet_node_info)

# pytest tests/substrate/test_rpc.py::test_get_all_subnet_nodes_info -rP

def test_get_all_subnet_nodes_info():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getAllSubnetNodesInfo',
            params=[]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Vec<SubnetNodeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_all_subnet_nodes_info_formatted -rP

def test_get_all_subnet_nodes_info_formatted():
  subnet_node_info = hypertensor.get_all_subnet_nodes_info_formatted()
  print(subnet_node_info)

# pytest tests/substrate/test_rpc.py::test_proof_of_stake -rP

def test_proof_of_stake():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    peer_id_to_vec = [ord(char) for char in "12D1KooWGFuUunX1AzAzjs3CgyqTXtPWX3AqRhJFbesGPGYHJQTP"]

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_proofOfStake',
            params=[
              1,
              peer_id_to_vec,
              1,
            ]
        )
        print("result['result']", result['result'])

# pytest tests/substrate/test_rpc.py::test_get_bootnodes -rP

def test_get_bootnodes():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getBootnodes',
            params=[1]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("AllSubnetBootnodes")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('AllSubnetBootnodes')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('AllSubnetBootnodes', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_bootnodes_formatted -rP

def test_get_bootnodes_formatted():
  bootnodes = hypertensor.get_bootnodes_formatted(1)
  print(bootnodes)

# pytest tests/substrate/test_rpc.py::test_get_coldkey_subnet_nodes_info -rP

def test_get_coldkey_subnet_nodes_info():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getColdkeySubnetNodesInfo',
            params=["0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac"]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Vec<SubnetNodeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        print("result:", result)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_coldkey_subnet_nodes_info_formatted -rP

def test_get_coldkey_subnet_nodes_info_formatted():
  data = hypertensor.get_coldkey_subnet_nodes_info_formatted("0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac")
  print(data)


# pytest tests/substrate/test_rpc.py::test_get_coldkey_stakes -rP

def test_get_coldkey_stakes():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getColdkeyStakes',
            params=["0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac"]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Vec<SubnetNodeStakeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        print("result:", result)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeStakeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<SubnetNodeStakeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_coldkey_stakes_formatted -rP

def test_get_coldkey_stakes_formatted():
  data = hypertensor.get_coldkey_stakes_formatted("0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac")
  print(data)

# pytest tests/substrate/test_rpc.py::test_get_delegate_stakes -rP

def test_get_delegate_stakes():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getDelegateStakes',
            params=["0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac"]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Vec<DelegateStakeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        print("result:", result)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<DelegateStakeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<DelegateStakeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_delegate_stakes_formatted -rP

def test_get_delegate_stakes_formatted():
  data = hypertensor.get_delegate_stakes_formatted("0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac")
  print(data)

# pytest tests/substrate/test_rpc.py::test_get_node_delegate_stakes -rP

def test_get_node_delegate_stakes():
    rpc_runtime_config = RuntimeConfiguration()
    rpc_runtime_config.update_type_registry(load_type_registry_preset("legacy"))
    rpc_runtime_config.update_type_registry(custom_rpc_type_registry)

    with hypertensor.interface as _interface:
        result = _interface.rpc_request(
            method='network_getNodeDelegateStakes',
            params=["0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac"]
        )
        # print("Raw result:", result)
        scale_obj = rpc_runtime_config.create_scale_object("Vec<NodeDelegateStakeInfo>")
        type_info = scale_obj.generate_type_decomposition()
        print("type_info", type_info)

        print("result:", result)

        if 'result' in result and result['result']:
            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<NodeDelegateStakeInfo>')

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode(ScaleBytes(bytes(result['result'])))
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

            try:
                # Create scale object for decoding
                obj = rpc_runtime_config.create_scale_object('Vec<NodeDelegateStakeInfo>', data=ScaleBytes(bytes(result['result'])))

                # Decode the hex-encoded SCALE data (don't encode!)
                decoded_data = obj.decode()
                print("Decoded data:", decoded_data)

            except Exception as e:
                print("Decode error:", str(e))

# pytest tests/substrate/test_rpc.py::test_get_node_delegate_stakes_formatted -rP

def test_get_node_delegate_stakes_formatted():
  data = hypertensor.get_node_delegate_stakes_formatted("0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac")
  print(data)


@dataclass
class ConsensusData:
  """
  Dataclass for subnet node info.
  """
  validator_id: int
  validator_epoch_progress: int
  attests: list
  subnet_nodes: list
  prioritize_queue_node_id: int | None
  remove_queue_node_id: int | None
  data: list | None
  args: list | None

  @classmethod
  def fix_decoded_values(cls, data_decoded: Any) -> "ConsensusData":
      """Converts substrate-interface SCALE object to ConsensusData dataclass."""
      return cls(**data_decoded.serialize())

  # @classmethod
  # def fix_decoded_values(cls, data_decoded: Any) -> "ConsensusData":
  #   # Try serialize method if available
  #   if hasattr(data_decoded, 'serialize'):
  #       data_dict = data_decoded.serialize()
  #       print(f"DEBUG: serialize() returned: {type(data_dict)}")
  #   else:
  #       # Manually extract all fields
  #       data_dict = {}
  #       for key in ['validator_id', 'attests', 'subnet_nodes', 'prioritize_queue_node_id',
  #                   'remove_queue_node_id', 'data', 'args']:
  #           try:
  #               data_dict[key] = data_decoded[key]
  #           except Exception as e:
  #               print(f"DEBUG: Failed to get {key}: {e}")
  #               data_dict[key] = None

  #       print(f"DEBUG: Manual extraction: {data_dict}")
  #   return cls(**data_dict)


# pytest tests/substrate/test_rpc.py::test_get_consensus_data_formatted -rP

def test_get_consensus_data_formatted():
  # subnet_info = hypertensor.get_consensus_data_formatted(1, 15)
  # print("subnet_info", subnet_info)
    result = hypertensor.get_consensus_data(1, 1)

    consensus_data = ConsensusData.fix_decoded_values(result)
    print("consensus_data", consensus_data)
