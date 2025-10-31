import glob
import time
from typing import Any, List, Optional

from mesh.substrate.chain_data import ConsensusData, SubnetInfo, SubnetNode, SubnetNodeConsensusData, SubnetNodeInfo
from mesh.substrate.chain_functions import EpochData, SubnetNodeClass
from mesh.substrate.config import BLOCK_SECS
from mesh.utils.key import generate_rsa_private_key_file


class MockHypertensor:
    def __init__(self):
        # self.start_time = time.time()
        self.BLOCK_TIME = 6

    def get_epoch_length(self):
        return 20

    def get_block_number(self) -> int:
        """Simulate block height based on elapsed time."""
        now = time.time()
        return int(now // BLOCK_SECS)

    def proof_of_stake(
        self,
        subnet_id: int,
        peer_id: str,
        min_class: int
    ):
        return {
            "result": True
        }

    def get_epoch(self):
        current_block = self.get_block_number()
        epoch_length = self.get_epoch_length()
        return current_block // epoch_length

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

    def propose_attestation(
        self,
        subnet_id: int,
        data,
        args: Optional[Any] = None,
        attest_data: Optional[Any] = None,
    ):
        return

    def attest(
        self,
        subnet_id: int,
        data: Optional[List[Any]] = None
    ):
        return

    def get_subnet_included_nodes(self, subnet_id: int) -> List:
        return [
            SubnetNode(
                id=1,
                hotkey="0x1234567890abcdef1234567890abcdef12345678",
                peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
                bootnode_peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
                bootnode="",
                client_peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
                classification="Validator",
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique=None,
                non_unique=None,
            )
        ]

    def get_formatted_subnet_info(self, subnet_id: int) -> Optional["SubnetInfo"]:
        return SubnetInfo(
            id=subnet_id,
            name=f"subnet-{subnet_id}",
            repo=f"github.com/subnet-{subnet_id}",
            description="artificial intelligence",
            misc="artificial intelligence misc",
            state="Active",
            start_epoch=0,
            churn_limit=0,
            min_stake=0,
            max_stake=0,
            queue_immunity_epochs=10,
            target_node_registrations_per_epoch=10,
            subnet_node_queue_epochs=0,
            idle_classification_epochs=10,
            included_classification_epochs=10,
            delegate_stake_percentage=0.1e18,
            node_burn_rate_alpha=0,
            max_node_penalties=0,
            initial_coldkeys=0,
            max_registered_nodes=0,
            owner="0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac",
            pending_owner="000000000000000000000000000000000000000000000000",
            registration_epoch=0,
            key_types=sorted(set("Rsa")),
            slot_index=3,
            penalty_count=0,
            bootnode_access=["000000000000000000000000000000000000000000000000"],
            bootnodes=["000000000000000000000000000000000000000000000000"],
            total_nodes=4,
            total_active_nodes=4,
            total_electable_nodes=4,
            current_min_delegate_stake=0,
        )

    def get_elected_validator_node_formatted(self, subnet_id: int, epoch: int) -> Optional["SubnetNode"]:
        return SubnetNode(
            id=1,
            hotkey="0x1234567890abcdef1234567890abcdef12345678",
            peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
            bootnode_peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
            bootnode="",
            client_peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
            classification="Validator",
            delegate_reward_rate=0,
            last_delegate_reward_rate_update=0,
            unique=None,
            non_unique=None,
        )

    def get_min_class_subnet_nodes_formatted(self, subnet_id: int, subnet_epoch: int, min_class: SubnetNodeClass) -> List["SubnetNodeInfo"]:
        return [
            # alith.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=1,
                coldkey="0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac",
                hotkey="0x317D7a5a2ba5787A99BE4693Eb340a10C71d680b",
                peer_id="QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB",
                bootnode_peer_id="QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB",
                client_peer_id="QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            ),
            # baltathar.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=2,
                coldkey="0x3Cd0A705a2DC65e5b1E1205896BaA2be8A07c6e0",
                hotkey="0xc30fE91DE91a3FA79E42Dfe7a01917d0D92D99D7",
                peer_id="QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                bootnode_peer_id="QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                client_peer_id="QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            ),
            # charleth.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=3,
                coldkey="0x798d4Ba9baf0064Ec19eB4F0a1a45785ae9D6DFc",
                hotkey="0x2f7703Ba9953d422294079A1CB32f5d2B60E38EB",
                peer_id="QmTJ8uyLJBwVprejUQfYFAywdXWfdnUQbC1Xif6QiTNta9",
                bootnode_peer_id="QmTJ8uyLJBwVprejUQfYFAywdXWfdnUQbC1Xif6QiTNta9",
                client_peer_id="QmTJ8uyLJBwVprejUQfYFAywdXWfdnUQbC1Xif6QiTNta9",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            ),
            # dorothy.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=4,
                coldkey="0x773539d4Ac0e786233D90A233654ccEE26a613D9",
                hotkey="0x294BFfC18b5321264f55c517Aca2963bEF9D29EA",
                peer_id="QmPpeHpL6R4aXeBxRqqvA78mNW9QjM1ZiFrS3n2MdMtPKJ",
                bootnode_peer_id="QmPpeHpL6R4aXeBxRqqvA78mNW9QjM1ZiFrS3n2MdMtPKJ",
                client_peer_id="QmPpeHpL6R4aXeBxRqqvA78mNW9QjM1ZiFrS3n2MdMtPKJ",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            ),
            # ethan.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=5,
                coldkey="0xFf64d3F6efE2317EE2807d223a0Bdc4c0c49dfDB",
                hotkey="0x919a696741e5bEe48538D43CB8A34a95261E62fc",
                peer_id="Qma2JzgMccgNvrFwMRccjRVzQtJBQT8Qrz7rcfR7RAkHJf",
                bootnode_peer_id="Qma2JzgMccgNvrFwMRccjRVzQtJBQT8Qrz7rcfR7RAkHJf",
                client_peer_id="Qma2JzgMccgNvrFwMRccjRVzQtJBQT8Qrz7rcfR7RAkHJf",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            ),
            # faith.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=6,
                coldkey="0xC0F0f4ab324C46e55D02D0033343B4Be8A55532d",
                hotkey="0xD4eb2503fA9F447CCa7b78D9a86F2fdbc964401e",
                peer_id="Qmd9kjDLqM9isDgU5rCW6H9mpmfeLVtgsSHC5bqdDJtXmM",
                bootnode_peer_id="Qmd9kjDLqM9isDgU5rCW6H9mpmfeLVtgsSHC5bqdDJtXmM",
                client_peer_id="Qmd9kjDLqM9isDgU5rCW6H9mpmfeLVtgsSHC5bqdDJtXmM",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            ),
            # bootnode.id
            SubnetNodeInfo(
                subnet_id=1,
                subnet_node_id=6,
                coldkey="0xD4eb2503fA9F447CCa7b78D9a86F2fdbc964401e",
                hotkey="0xD4eb2503fA9F447CCa7b78D9a86F2fdbc964401e",
                peer_id="QmSjcNmhbRvek3YDQAAQ3rV8GKR8WByfW8LC4aMxk6gj7v",
                bootnode_peer_id="QmSjcNmhbRvek3YDQAAQ3rV8GKR8WByfW8LC4aMxk6gj7v",
                client_peer_id="QmSjcNmhbRvek3YDQAAQ3rV8GKR8WByfW8LC4aMxk6gj7v",
                bootnode="",
                identity=dict(),
                classification=dict(),
                delegate_reward_rate=0,
                last_delegate_reward_rate_update=0,
                unique="",
                non_unique="",
                stake_balance=0,
                node_delegate_stake_balance=0,
                penalties=0,
                reputation=dict()
            )
        ]

    def get_formatted_rewards_validator_info(self, subnet_id, epoch: int) -> Optional["SubnetNodeInfo"]:
        return SubnetNodeInfo(
            subnet_id=1,
            subnet_node_id=1,
            coldkey="0x1234567890abcdef1234567890abcdef12345678",
            hotkey="0x1234567890abcdef1234567890abcdef12345678",
            peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
            bootnode_peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
            client_peer_id="QmNV5G3hq2UmAck2htEgsqrmPFBff5goFZAdmKDcZLBZLX",
            bootnode="",
            identity=dict(),
            classification=dict(),
            delegate_reward_rate=0,
            last_delegate_reward_rate_update=0,
            unique="",
            non_unique="",
            stake_balance=0,
            node_delegate_stake_balance=0,
            penalties=0,
            reputation=dict()
        )

    def get_consensus_data_formatted(self, subnet_id: int, epoch: int) -> Optional[ConsensusData]:
        """
        Get formatted list of subnet nodes classified as Validator

        :param subnet_id: subnet ID

        :returns: List of subnet node IDs
        """
        return ConsensusData(
            validator_id=1,
            validator_epoch_progress=0,
            attests=[
                {1: {
                    "block": 0,
                    "attestor_progress": 0,
                    "reward_factor": int(1e18),
                    "data": ""
                }},
                # {2: {
                #     "block": 0,
                #     "attestor_progress": 0,
                #     "reward_factor": int(1e18),
                #     "data": ""
                # }},
                # {3: {
                #     "block": 0,
                #     "attestor_progress": 0,
                #     "reward_factor": int(1e18),
                #     "data": ""
                # }},
                # {4: {
                #     "block": 0,
                #     "attestor_progress": 0,
                #     "reward_factor": int(1e18),
                #     "data": ""
                # }},
                # {5: {
                #     "block": 0,
                #     "attestor_progress": 0,
                #     "reward_factor": int(1e18),
                #     "data": ""
                # }},
                {6: {
                    "block": 0,
                    "attestor_progress": 0,
                    "reward_factor": int(1e18),
                    "data": ""
                }},
            ],
            subnet_nodes=[
                SubnetNode(
                    id=1,
                    hotkey="0x317D7a5a2ba5787A99BE4693Eb340a10C71d680b",
                    peer_id="QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB",
                    bootnode_peer_id="QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB",
                    client_peer_id="QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB",
                    bootnode="",
                    classification=dict(),
                    delegate_reward_rate=0,
                    last_delegate_reward_rate_update=0,
                    unique="",
                    non_unique="",
                ),
                # # baltathar.id
                # SubnetNode(
                #     id=2,
                #     hotkey="0xc30fE91DE91a3FA79E42Dfe7a01917d0D92D99D7",
                #     peer_id="QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                #     bootnode_peer_id="QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                #     client_peer_id="QmbRz8Bt1pMcVnUzVQpL2icveZz2MF7VtELC44v8kVNwiG",
                #     bootnode="",
                #     classification=dict(),
                #     delegate_reward_rate=0,
                #     last_delegate_reward_rate_update=0,
                #     unique="",
                #     non_unique="",
                # ),
                # # charleth.id
                # SubnetNode(
                #     id=3,
                #     hotkey="0x2f7703Ba9953d422294079A1CB32f5d2B60E38EB",
                #     peer_id="QmTJ8uyLJBwVprejUQfYFAywdXWfdnUQbC1Xif6QiTNta9",
                #     bootnode_peer_id="QmTJ8uyLJBwVprejUQfYFAywdXWfdnUQbC1Xif6QiTNta9",
                #     client_peer_id="QmTJ8uyLJBwVprejUQfYFAywdXWfdnUQbC1Xif6QiTNta9",
                #     bootnode="",
                #     classification=dict(),
                #     delegate_reward_rate=0,
                #     last_delegate_reward_rate_update=0,
                #     unique="",
                #     non_unique="",
                # ),
                # # dorothy.id
                # SubnetNode(
                #     id=4,
                #     hotkey="0x294BFfC18b5321264f55c517Aca2963bEF9D29EA",
                #     peer_id="QmPpeHpL6R4aXeBxRqqvA78mNW9QjM1ZiFrS3n2MdMtPKJ",
                #     bootnode_peer_id="QmPpeHpL6R4aXeBxRqqvA78mNW9QjM1ZiFrS3n2MdMtPKJ",
                #     client_peer_id="QmPpeHpL6R4aXeBxRqqvA78mNW9QjM1ZiFrS3n2MdMtPKJ",
                #     bootnode="",
                #     classification=dict(),
                #     delegate_reward_rate=0,
                #     last_delegate_reward_rate_update=0,
                #     unique="",
                #     non_unique="",
                # ),
                # # ethan.id
                # SubnetNode(
                #     id=5,
                #     hotkey="0x919a696741e5bEe48538D43CB8A34a95261E62fc",
                #     peer_id="Qma2JzgMccgNvrFwMRccjRVzQtJBQT8Qrz7rcfR7RAkHJf",
                #     bootnode_peer_id="Qma2JzgMccgNvrFwMRccjRVzQtJBQT8Qrz7rcfR7RAkHJf",
                #     client_peer_id="Qma2JzgMccgNvrFwMRccjRVzQtJBQT8Qrz7rcfR7RAkHJf",
                #     bootnode="",
                #     classification=dict(),
                #     delegate_reward_rate=0,
                #     last_delegate_reward_rate_update=0,
                #     unique="",
                #     non_unique="",
                # ),
                # # faith.id
                # SubnetNode(
                #     id=6,
                #     hotkey="0xD4eb2503fA9F447CCa7b78D9a86F2fdbc964401e",
                #     peer_id="Qmd9kjDLqM9isDgU5rCW6H9mpmfeLVtgsSHC5bqdDJtXmM",
                #     bootnode_peer_id="Qmd9kjDLqM9isDgU5rCW6H9mpmfeLVtgsSHC5bqdDJtXmM",
                #     client_peer_id="Qmd9kjDLqM9isDgU5rCW6H9mpmfeLVtgsSHC5bqdDJtXmM",
                #     bootnode="",
                #     classification=dict(),
                #     delegate_reward_rate=0,
                #     last_delegate_reward_rate_update=0,
                #     unique="",
                #     non_unique="",
                # ),
                # bootnode.id
                SubnetNode(
                    id=6,
                    hotkey="0xD4eb2503fA9F447CCa7b78D9a86F2fdbc964401e",
                    peer_id="QmSjcNmhbRvek3YDQAAQ3rV8GKR8WByfW8LC4aMxk6gj7v",
                    bootnode_peer_id="QmSjcNmhbRvek3YDQAAQ3rV8GKR8WByfW8LC4aMxk6gj7v",
                    client_peer_id="QmSjcNmhbRvek3YDQAAQ3rV8GKR8WByfW8LC4aMxk6gj7v",
                    bootnode="",
                    classification=dict(),
                    delegate_reward_rate=0,
                    last_delegate_reward_rate_update=0,
                    unique="",
                    non_unique="",
                )
            ],
            prioritize_queue_node_id=None,
            remove_queue_node_id=None,
            data=[
                SubnetNodeConsensusData(
                    subnet_node_id=1,
                    score=int(1e18)
                ),
                # SubnetNodeConsensusData(
                #     subnet_node_id=2,
                #     score=int(1e18)
                # ),
                # SubnetNodeConsensusData(
                #     subnet_node_id=3,
                #     score=int(1e18)
                # ),
                # SubnetNodeConsensusData(
                #     subnet_node_id=4,
                #     score=int(1e18)
                # ),
                # SubnetNodeConsensusData(
                #     subnet_node_id=5,
                #     score=int(1e18)
                # ),
                SubnetNodeConsensusData(
                    subnet_node_id=6,
                    score=int(1e18)
                ),
            ],
            args=None,
        )

    def get_consensus_data(self, subnet_id: int, epoch: int):
        consensus_data = []
        for filepath in glob.glob("server*.id"):
            _, _, public_bytes, _, _, peer_id = generate_rsa_private_key_file(filepath)
            node = {
                'peer_id': peer_id,
                'score': int(1e18)
            }
            consensus_data.append(node)
    
    def get_subnet_registration_epochs(self, subnet_id: int):
        return 10

    def get_reward_result_event(
        self,
        target_subnet_id: int,
        epoch: int
    ):
        return target_subnet_id, int(1e18)
