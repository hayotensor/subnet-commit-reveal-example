import json
import time
from typing import Any, Optional, List
from mesh.substrate.chain_data import ConsensusData, SubnetInfo, SubnetNode, SubnetNodeConsensusData, SubnetNodeInfo
from mesh.substrate.chain_functions import EpochData, SubnetNodeClass, subnet_node_class_to_enum
from mesh.substrate.config import BLOCK_SECS
from mesh.substrate.mock.mock_db import MockDatabase  # assume separate file
from mesh import PeerID
from mesh.utils import get_logger

logger = get_logger(__name__)

class LocalMockHypertensor:
    def __init__(
        self,
        subnet_id: int,
        peer_id: PeerID,
        subnet_node_id: int,
        coldkey: str,
        hotkey: str,
        bootnode_peer_id: str,
        client_peer_id: str,
        reset_db: bool = False,
    ):

        self.subnet_id = subnet_id
        self.peer_id = peer_id
        self.subnet_node_id = subnet_node_id
        self.coldkey = coldkey
        self.hotkey = hotkey
        self.bootnode_peer_id = bootnode_peer_id
        self.client_peer_id = client_peer_id
        self.BLOCK_SECS = 6

        # Initialize database
        self.db = MockDatabase()
        if reset_db:
            self.db.reset_database()

        # Only store if not bootnode, use `subnet_node_id=0` if bootnode
        if subnet_node_id != 0:
            # Register this node
            self.db.insert_subnet_node(
                subnet_id=self.subnet_id,
                node_info=dict(
                    subnet_node_id=self.subnet_node_id,
                    peer_id=self.peer_id.to_base58(),
                    coldkey=self.coldkey,
                    hotkey=self.hotkey,
                    bootnode_peer_id=self.bootnode_peer_id,
                    client_peer_id=self.client_peer_id,
                    bootnode="",
                    identity="",
                    classification={
                        "node_class": "Validator",
                        "start_epoch": self.get_epoch()
                    },
                    delegate_reward_rate=0,
                    last_delegate_reward_rate_update=0,
                    unique="",
                    non_unique="",
                    stake_balance=int(1e18),
                    node_delegate_stake_balance=0,
                    penalties=0,
                    reputation=int(1e18)
                ),
            )

    def propose_attestation(
        self,
        subnet_id: int,
        data,
        args: Optional[Any] = None,
        attest_data: Optional[Any] = None,
    ):
        epoch = self.get_epoch()
        subnet_nodes = self.db.get_all_subnet_nodes(subnet_id)
        proposal = {
            "validator_id": self.subnet_node_id,
            "validator_epoch_progress": 0,
            "attests": [
                {node["subnet_node_id"]: {
                    "block": 0,
                    "attestor_progress": 0,
                    "reward_factor": int(1e18),
                    "data": attest_data
                }} for node in subnet_nodes
            ],
            "subnet_nodes": subnet_nodes,
            "prioritize_queue_node_id": None,
            "remove_queue_node_id": None,
            "data": data,
            "args": args,
        }
        self.db.insert_consensus_data(subnet_id, epoch, proposal)
        return proposal

    def attest(self, subnet_id: int, data: Optional[List[Any]] = None):
        """
        Append this peer's attestation data to the existing consensus record
        for the current epoch.
        """
        epoch = self.get_epoch()

        # Load existing consensus data for this subnet and epoch
        consensus = self.db.get_consensus_data(subnet_id, epoch)
        if consensus is None:
            raise ValueError(f"No consensus proposal found for subnet {subnet_id} epoch {epoch}")

        # Build this peer's attestation record
        attestation_entry = {
            self.subnet_node_id: {
                "block": self.get_block_number(),
                "attestor_progress": 0,
                "reward_factor": int(1e18),
                "data": data or "",
            }
        }

        # Append or update attestation
        updated_attests = consensus.get("attests", [])
        # Remove any existing entry for this same peer
        updated_attests = [
            a for a in updated_attests if str(self.subnet_node_id) not in map(str, a.keys())
        ]
        updated_attests.append(attestation_entry)

        # Save updated record back to database
        consensus["attests"] = updated_attests
        self.db.insert_consensus_data(subnet_id, epoch, consensus)

    def get_consensus_data_formatted(self, subnet_id: int, epoch: int) -> Optional["ConsensusData"]:
        record = self.db.get_consensus_data(subnet_id, epoch)
        if record is None:
            return None

        # Convert subnet_nodes into SubnetNode dataclasses if available
        subnet_nodes_data = record.get("subnet_nodes", [])
        subnet_nodes: List[SubnetNode] = []

        # Handle if stored as JSON string
        if isinstance(subnet_nodes_data, str):
            import json
            try:
                subnet_nodes_data = json.loads(subnet_nodes_data)
            except Exception:
                return []

        # Map to dataclasses
        for node_dict in subnet_nodes_data:
            try:
                classification_data = node_dict.get("classification", {})

                if isinstance(classification_data, str):
                    try:
                        classification = json.loads(classification_data)
                    except json.JSONDecodeError:
                        classification = {}
                else:
                    classification = classification_data

                subnet_nodes.append(
                    SubnetNode(
                        id=node_dict.get("id"),
                        hotkey=node_dict.get("hotkey", ""),
                        peer_id=node_dict.get("peer_id", ""),
                        bootnode_peer_id=node_dict.get("bootnode_peer_id", ""),
                        bootnode=node_dict.get("bootnode", ""),
                        client_peer_id=node_dict.get("client_peer_id", ""),
                        classification=classification,
                        delegate_reward_rate=node_dict.get("delegate_reward_rate", 0),
                        last_delegate_reward_rate_update=node_dict.get("last_delegate_reward_rate_update", 0),
                        unique=node_dict.get("unique", ""),
                        non_unique=node_dict.get("non_unique", "")
                    )
                )
            except Exception as e:
                print(f"[WARN] Failed to parse subnet node: {e}")

        raw_data = record.get("data", [])
        consensus_scores: List[SubnetNodeConsensusData] = [
            SubnetNodeConsensusData(
                subnet_node_id=item["subnet_node_id"],
                score=item["score"]
            )
            for item in raw_data
        ]

        # Return final ConsensusData object
        return ConsensusData(
            validator_id=record["validator_id"],
            validator_epoch_progress=record["validator_epoch_progress"],
            attests=record.get("attests", []),
            subnet_nodes=subnet_nodes,
            prioritize_queue_node_id=record.get("prioritize_queue_node_id"),
            remove_queue_node_id=record.get("remove_queue_node_id"),
            data=consensus_scores,
            args=record.get("args"),
        )

    def get_block_number(self) -> int:
        now = time.time()
        return int(now // self.BLOCK_SECS)

    def get_epoch_length(self):
        return 20

    def get_epoch(self):
        current_block = self.get_block_number()
        epoch_length = self.get_epoch_length()
        return current_block // epoch_length

    def proof_of_stake(
        self,
        subnet_id: int,
        peer_id: str,
        min_class: int
    ):
        return {
            "result": True
        }

    def get_subnet_slot(self, subnet_id: int):
        return 3

    def get_epoch_data(self) -> EpochData:
        current_block = self.get_block_number()
        epoch_length = self.get_epoch_length()
        epoch = current_block // epoch_length
        blocks_elapsed = current_block % epoch_length
        percent_complete = blocks_elapsed / epoch_length
        blocks_remaining = epoch_length - blocks_elapsed
        seconds_elapsed = blocks_elapsed * BLOCK_SECS
        seconds_remaining = blocks_remaining * BLOCK_SECS

        return EpochData(
            block=current_block,
            epoch=epoch,
            block_per_epoch=epoch_length,
            seconds_per_epoch=epoch_length * BLOCK_SECS,
            percent_complete=percent_complete,
            blocks_elapsed=blocks_elapsed,
            blocks_remaining=blocks_remaining,
            seconds_elapsed=seconds_elapsed,
            seconds_remaining=seconds_remaining
        )

    def get_subnet_epoch_data(self, slot: int) -> EpochData:
        current_block = self.get_block_number()
        epoch_length = self.get_epoch_length()

        blocks_since_start = current_block - slot
        epoch = blocks_since_start // epoch_length
        blocks_elapsed = blocks_since_start % epoch_length
        percent_complete = blocks_elapsed / epoch_length
        blocks_remaining = epoch_length - blocks_elapsed
        seconds_elapsed = blocks_elapsed * BLOCK_SECS
        seconds_remaining = blocks_remaining * BLOCK_SECS

        return EpochData(
            block=current_block,
            epoch=epoch,
            block_per_epoch=epoch_length,
            seconds_per_epoch=epoch_length * BLOCK_SECS,
            percent_complete=percent_complete,
            blocks_elapsed=blocks_elapsed,
            blocks_remaining=blocks_remaining,
            seconds_elapsed=seconds_elapsed,
            seconds_remaining=seconds_remaining
        )

    def get_rewards_validator(self, subnet_id: int, epoch: int):
        return 6

    def get_min_class_subnet_nodes_formatted(
        self,
        subnet_id: int,
        subnet_epoch: int,
        min_class: SubnetNodeClass
    ) -> List["SubnetNodeInfo"]:
        """
        Return all subnet nodes that meet or exceed the minimum classification
        requirement and have started on or before the given subnet_epoch.
        """
        try:
            subnet_nodes = self.db.get_all_subnet_nodes(subnet_id)
            qualified_nodes = []

            for node_dict in subnet_nodes:
                classification_data = node_dict.get("classification", {})

                if isinstance(classification_data, str):
                    try:
                        classification = json.loads(classification_data)
                    except json.JSONDecodeError:
                        classification = {}
                else:
                    classification = classification_data

                node_class_name = classification.get("node_class", "Validator")
                start_epoch = classification.get("start_epoch", 0)

                node_class_enum = subnet_node_class_to_enum(node_class_name)

                if (
                    node_class_enum.value >= min_class.value
                    and start_epoch <= subnet_epoch
                ):
                    qualified_nodes.append(
                        SubnetNodeInfo(
                            subnet_id=self.subnet_id,
                            subnet_node_id=node_dict["subnet_node_id"],
                            coldkey=node_dict["coldkey"],
                            hotkey=node_dict["hotkey"],
                            peer_id=node_dict["peer_id"],
                            bootnode_peer_id=node_dict["bootnode_peer_id"],
                            client_peer_id=node_dict["client_peer_id"],
                            bootnode=node_dict["bootnode"],
                            identity=node_dict["identity"],
                            classification=classification,
                            delegate_reward_rate=0,
                            last_delegate_reward_rate_update=0,
                            unique=node_dict["unique"],
                            non_unique=node_dict["non_unique"],
                            stake_balance=int(node_dict.get("stake_balance", 0)),
                            node_delegate_stake_balance=0,
                            penalties=int(node_dict.get("penalties", 0)),
                            reputation=int(node_dict.get("reputation", 0)),
                        )
                    )

            return qualified_nodes
        except Exception as e:
            logger.warning(f"[WARN] get_min_class_subnet_nodes_formatted error: {e}", exc_info=True)
            return []

    def get_formatted_subnet_info(self, subnet_id: int) -> Optional["SubnetInfo"]:
        return SubnetInfo(
            id=self.subnet_id,
            name="subnet-name",
            repo="subnet-repo",
            description="subnet-description",
            misc="subnet-misc",
            state="Active",
            start_epoch=0,
            churn_limit=10,
            min_stake=0,
            max_stake=0,
            queue_immunity_epochs=0,
            target_node_registrations_per_epoch=0,
            subnet_node_queue_epochs=0,
            idle_classification_epochs=0,
            included_classification_epochs=0,
            delegate_stake_percentage=0,
            node_burn_rate_alpha=0,
            max_node_penalties=0,
            initial_coldkeys=0,
            max_registered_nodes=0,
            owner="000000000000000000000000000000000000000000000000",
            pending_owner="000000000000000000000000000000000000000000000000",
            registration_epoch=0,
            key_types=0,
            slot_index=3,
            penalty_count=0,
            bootnode_access=0,
            bootnodes=0,
            total_nodes=0,
            total_active_nodes=0,
            total_electable_nodes=0,
            current_min_delegate_stake=0
        )