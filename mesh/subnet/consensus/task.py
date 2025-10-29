

import asyncio
import hashlib
import os
import pickle
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from mesh import DHT, PeerID, get_dht_time
from mesh.dht.validation import RecordValidatorBase
from mesh.proto import math_pb2
from mesh.subnet.consensus.utils import compare_consensus_data, did_node_attest, get_attestation_ratio, get_peers_node_id
from mesh.subnet.protocols.math_protocol import MathProtocol
from mesh.subnet.utils.consensus import BASE_VALIDATOR_SCORE, EPSILON, ConsensusScores
from mesh.subnet.utils.mock_commit_reveal import (
  MAX_COMMIT_TIME,
  MAX_REVEAL_TIME,
  get_scores_commit_key,
  get_scores_reveal_key,
  get_verifier_commit_key,
  get_verifier_reveal_key,
)
from mesh.substrate.chain_data import SubnetNodeConsensusData, SubnetNodeInfo
from mesh.substrate.chain_functions import Hypertensor, SubnetNodeClass
from mesh.utils.authorizers.auth import AuthorizerBase
from mesh.utils.dht import get_node_infos_sig
from mesh.utils.key import extract_peer_id_from_record_validator
from mesh.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MathData:
  peer_id: str
  equation: str
  answer: str
  peer_answer: str
  score: int

class TaskCommitReveal():
    def __init__(
        self,
        dht: DHT,
        authorizer: AuthorizerBase,
        record_validator: RecordValidatorBase,
        subnet_id: int,
        hypertensor: Hypertensor,
    ):
        self.dht = dht
        self.peer_id = dht.peer_id
        self.authorizer = authorizer
        self.record_validator = record_validator
        self.subnet_id = subnet_id
        self.hypertensor = hypertensor
        self.commits: Dict[int, PeerID] = dict() # Epoch -> Peer ID
        self.latest_task_commit = None
        self.latest_scores_commit = {}


    async def call_and_commit_all_tasks(self, current_epoch: int):
        nodes = get_node_infos_sig(
            self.dht,
            uid="node",
            latest=True,
            record_validator=self.record_validator
        )

        p2p = await self.dht.replicate_p2p()

        node_peer_ids = {n.peer_id for n in nodes}

        # Give each peer/prover a unique equation to solve, verify it, and score them
        #
        # NOTE: We can go further with this and require the responding peer to commit
        #       In practice we should:
        #       - Have verifier send equation to prover and commit the equation to the DHT Records
        #       - Have prover commit his response alongside the verifiers commit hash
        #       - Later both parties reveal their commits
        #           - Verify the hashes are the same to ensure neither party changed the data
        #
        # In this example the verifier sends an equation to the prover and submits the right answer
        # with the provers answer, and scores them a 1.0 if correct.
        evals_data: List[MathData] = []
        for peer_id in node_peer_ids:
            if peer_id.__eq__(self.peer_id):
                continue
            stub = MathProtocol.get_server_stub(
                p2p,
                peer_id,
                self.authorizer
            )
            equation = self.generate_task()
            my_eval = float(eval(equation))

            input = math_pb2.MathRequest(input=equation)

            # Call the peer to commit the answer
            async with asyncio.Semaphore(float("inf")):
                peer_eval = await stub.rpc_math(input)

            evals_data.append(MathData(
                peer_id=peer_id,
                equation=equation,
                answer=my_eval,
                peer_answer=peer_eval.output,
                score=1.0 if my_eval == peer_eval.output else 0.0
            ))
        
        if not evals_data:
            return
        
        evals_bytes = pickle.dumps(evals_data)
        salt = os.urandom(16)
        digest = hashlib.sha256(salt + evals_bytes).digest()

        verifier_commit_key = get_verifier_commit_key(current_epoch)

        store_ok = self.dht.store(
            verifier_commit_key,
            digest,
            get_dht_time() + MAX_COMMIT_TIME * .9,
            self.record_validator.local_public_key
        )

        self.latest_task_commit = {
            "target_epoch": current_epoch,
            "salt": salt,
            "bytes": evals_bytes,
        }

        if store_ok:
            logger.info(f"[TaskCommitReveal] Committed tasks data for epoch {current_epoch}")
        else:
            logger.warning(f"[TaskCommitReveal] Commit tasks data failed for epoch {current_epoch}")

    async def reveal_tasks(self, current_epoch: int):
        if (
            not self.latest_task_commit
            or self.latest_task_commit["target_epoch"] != current_epoch
        ):
            return

        reveal_key = get_verifier_reveal_key(current_epoch)

        reveal_payload = {
            "salt": self.latest_task_commit["salt"],
            "bytes": self.latest_task_commit["bytes"],
        }

        if reveal_payload is None:
            return

        store_ok = self.dht.store(
            reveal_key,
            reveal_payload,
            get_dht_time() + MAX_REVEAL_TIME * .9,
            self.record_validator.local_public_key
        )

        if store_ok:
            logger.info(f"[TaskCommitReveal] Revealed tasks data for epoch {current_epoch}")
        else:
            logger.warning(f"[TaskCommitReveal] Revealing tasks data failed for epoch {current_epoch}")

    async def commit_scores(self, current_epoch: int, scores: Dict):
        scores_bytes = pickle.dumps(scores)
        salt = os.urandom(16)
        digest = hashlib.sha256(salt + scores_bytes).digest()

        scores_commit_key = get_scores_commit_key(current_epoch)

        store_ok = self.dht.store(
            scores_commit_key,
            digest,
            get_dht_time() + MAX_COMMIT_TIME * .9,
            self.record_validator.local_public_key
        )

        self.latest_scores_commit[current_epoch] = {
            "target_epoch": current_epoch,
            "salt": salt,
            "bytes": scores_bytes,
        }

        if store_ok:
            logger.info(f"[TaskCommitReveal] Committed score data for epoch {current_epoch}")
        else:
            logger.warning(f"[TaskCommitReveal] Commit score data failed for epoch {current_epoch}")

    async def reveal_scores(self, current_epoch: int):
        if (
            not self.latest_scores_commit
            or self.latest_scores_commit.get(current_epoch - 2, None) is None
        ):
            return

        logger.info(f"Revealing commit from epoch {current_epoch - 2}, in epoch current_epoch")

        reveal_key = get_scores_reveal_key(current_epoch)

        reveal_payload = {
            "salt": self.latest_scores_commit.get(current_epoch - 2, None)["salt"],
            "bytes": self.latest_scores_commit.get(current_epoch - 2, None)["bytes"],
        }

        if reveal_payload is None:
            return
        store_ok = self.dht.store(
            reveal_key,
            reveal_payload,
            get_dht_time() + MAX_REVEAL_TIME * .9,
            self.record_validator.local_public_key
        )

        if store_ok:
            logger.info(f"[TaskCommitReveal] Revealed score data for epoch {current_epoch}")
        else:
            logger.warning(f"[TaskCommitReveal] Revealing score data failed for epoch {current_epoch}")

    def verify_score_reveals(self, target_epoch: int, included_nodes: List[SubnetNodeInfo]) -> Optional[List[ConsensusScores]]:
        """
        params:
            target_epoch: The target epoch, which is the current epoch
            consensus_scores: The scores
        """

        scores_commit_key = get_scores_commit_key(target_epoch - 2)   # commit from 2 epochs previous
        scores_reveal_key = get_scores_reveal_key(target_epoch)       # reveal from current epoch

        commit_records = self.dht.get(scores_commit_key, latest=True) or {}
        reveal_records = self.dht.get(scores_reveal_key, latest=True) or {}

        if not reveal_records and not commit_records:
            logger.warning(f"[TaskCommitReveal] No validator reveals found for epoch {target_epoch}")
            return None
        
        # Get scores from 2 epochs previous
        consensus_data = self.hypertensor.get_consensus_data_formatted(self.subnet_id, target_epoch - 2)

        if consensus_data is None:
            return None

        attestation_ratio = get_attestation_ratio(consensus_data)
        if attestation_ratio < 0.66:
            return None
        
        consensus_scores = consensus_data.data

        # Score each peer based on accuracy of data from the consensus
        results: Dict[str, List[Dict]] = {}

        # Get all reveal data
        for public_key, reveal_data in reveal_records.value.items():
            try:
                peer_id = extract_peer_id_from_record_validator(public_key)

                # Get peer_id's subnet_node_id
                subnet_node_id = get_peers_node_id(peer_id, included_nodes)

                # Did node attest
                attested = did_node_attest(subnet_node_id, consensus_data)

                # If didn't attest, skip
                # Only if subnet is in consensus and node attested do we score based on this
                if attested is False:
                    continue

                payload = reveal_data.value
                salt = payload["salt"]
                bytes = payload["bytes"]

                # 1) Verify the commit hash
                recomputed_digest = hashlib.sha256(salt + bytes).digest()
                committed_digest = commit_records.value[public_key].value

                if committed_digest != recomputed_digest:
                    # Disclude node from consensus
                    logger.warning(f"[TaskCommitReveal] Hash mismatch from validator {peer_id}, skipping verify_score_reveals")
                    continue

                # 2) Deserialize the scores
                raw_data = pickle.loads(bytes)
                results[peer_id.to_base58()] = raw_data

            except Exception as e:
                logger.warning(f"[TaskCommitReveal] Failed to verify or parse scores from {peer_id}, verify_score_reveals: {e}")


        # Convert validator_data to a set

        final_consensus_scores: List[ConsensusScores] = []
        for peer_id, scores in results.items():

            score = compare_consensus_data(
                my_data=scores,
                validator_data=consensus_scores,
            )

            final_consensus_scores.append(ConsensusScores(
                peer_id=peer_id,
                score=int(score * 1e18)
            ))

        return final_consensus_scores

    def verify_and_score_peers(self, target_epoch: int) -> Tuple[Optional[List[ConsensusScores]], Optional[List[SubnetNodeConsensusData]]]:
        """
        Get the validator submitted data from the DHT Record

        We ensure the validator is submitting scores to the DHT

        - We get each Record entry by each hoster node
        - We iterate to validate and score this data and store it in the Consensus class

        Note:
            Validators with no reveal (1 epoch old validators)are not submitted as the
            reveal is the next epoch from the commit.
        """

        mock_commit_key = get_verifier_commit_key(target_epoch)
        mock_reveal_key = get_verifier_reveal_key(target_epoch)

        commit_records = self.dht.get(mock_commit_key, latest=True) or {}
        reveal_records = self.dht.get(mock_reveal_key, latest=True) or {}

        if not reveal_records and not commit_records:
            logger.warning(f"[TaskCommitReveal] No validator reveals found for epoch {target_epoch}")
            return None, None

        results: Dict[str, List[MathData]] = {}

        # Get all reveal data
        for public_key, reveal_data in reveal_records.value.items():
            try:
                peer_id = extract_peer_id_from_record_validator(public_key)
                logger.debug(f"[TaskCommitReveal] peer_id={peer_id}")

                payload = reveal_data.value
                salt = payload["salt"]
                bytes = payload["bytes"]

                # 1) Verify the commit hash
                recomputed_digest = hashlib.sha256(salt + bytes).digest()
                committed_digest = commit_records.value[public_key].value

                if committed_digest != recomputed_digest:
                    # Disclude node from consensus
                    logger.warning(f"[TaskCommitReveal] Hash mismatch from validator {peer_id}, skipping verify_and_score_peers")
                    continue

                # 2) Deserialize the scores
                raw_data = pickle.loads(bytes)
                # Each peers scores
                math_data: List[MathData] = [
                    MathData(
                        peer_id=data.peer_id.to_base58(),
                        equation=data.equation,
                        answer=data.answer,
                        peer_answer=data.peer_answer,
                        score=data.score
                    )
                    for data in raw_data
                ]
                results[peer_id.to_base58()] = math_data

            except Exception as e:
                logger.warning(f"[TaskCommitReveal] Failed to verify or parse scores from {peer_id}, verify_and_score_peers: {e}")

        # Step 1: Get scores per peer_id
        peer_scores = defaultdict(list)  # peer_id -> list of scores
        for round_scores in results.values():
            for score_obj in round_scores:
                peer_scores[score_obj.peer_id].append(score_obj.score)

        # Step 2: Compute the mean score per peer
        peer_means = {
            peer_id: statistics.mean(scores)
            for peer_id, scores in peer_scores.items()
        }

        # Step 3: Compute squared error per peer
        validator_errors: Dict[str, float] = {}
        for validator_peer_id, round_scores in results.items():
            error_sum = 0.0
            for score_obj in round_scores:
                mean = peer_means.get(score_obj.peer_id)
                if mean is not None:
                    error_sum += (score_obj.score - mean) ** 2
            validator_errors[validator_peer_id] = error_sum

        # Step 4: Normalize errors and subtract from base score
        max_error = max(validator_errors.values(), default=1.0)

        validator_scores = {
            peer_id: max(BASE_VALIDATOR_SCORE - (error / (max_error + EPSILON)), 0.0)
            for peer_id, error in validator_errors.items()
        }

        consensus_scores = [
            ConsensusScores(peer_id=peer_id, score=int(score * 1e18))
            for peer_id, score in validator_scores.items()
        ]

        included_nodes = self.hypertensor.get_min_class_subnet_nodes_formatted(self.subnet_id, target_epoch, SubnetNodeClass.Included)

        # Filter math scores to only `included_nodes` and swap `peer_id` for `subnet_node_id`
        scores, consensus_formatted_scores = self.filter_and_format_scores_from_peer_id(target_epoch, consensus_scores, included_nodes)

        score_reveal_scores = self.verify_score_reveals(target_epoch, included_nodes)

        if score_reveal_scores:
            # Filter reveal scores to only `included_nodes` and swap `peer_id` for `subnet_node_id`
            _, scores_consensus_formatted_scores = self.filter_and_format_scores_from_peer_id(target_epoch, score_reveal_scores, included_nodes)
            final_scores = self.average_consensus_scores(consensus_formatted_scores, scores_consensus_formatted_scores)
            scores, consensus_formatted_scores = self.filter_and_format_scores_from_subnet_node_id(final_scores, included_nodes)

        return scores, consensus_formatted_scores

    def average_consensus_scores(
        self,
        *score_lists: List[SubnetNodeConsensusData],
    ) -> List[SubnetNodeConsensusData]:
        """Average scores across multiple lists of SubnetNodeConsensusData."""
        aggregated = {}

        # Collect all scores per subnet_node_id
        for score_list in score_lists:
            for entry in score_list:
                aggregated.setdefault(entry.subnet_node_id, []).append(entry.score)

        # Compute averages
        averaged = [
            SubnetNodeConsensusData(
                subnet_node_id=node_id,
                score=sum(scores) // len(scores)  # integer average
            )
            for node_id, scores in aggregated.items()
        ]

        return averaged

    def filter_and_format_scores_from_peer_id(self, current_epoch: int, scores: List[ConsensusScores], included_nodes: List[SubnetNodeInfo]) -> Tuple[List[ConsensusScores], List[SubnetNodeConsensusData]]:
        """
        Filter scores against the blockchain included subnet nodes
        """
        # Step 1: Get set of included peer_ids
        included_peer_ids = {node.peer_id for node in included_nodes}
        scores_peer_ids = {peer.peer_id for peer in scores}

        filtered_scores = [
            score_obj
            for score_obj in scores
            if score_obj.peer_id in included_peer_ids
        ]

        score_map = {s.peer_id: s.score for s in filtered_scores}

        consensus_formatted_scores = [
            SubnetNodeConsensusData(
                subnet_node_id=node.subnet_node_id,
                score=score_map[node.peer_id]
            )
            for node in included_nodes
            if node.peer_id in scores_peer_ids
        ]

        return filtered_scores, consensus_formatted_scores

    def filter_and_format_scores_from_subnet_node_id(self, scores: List[SubnetNodeConsensusData], included_nodes: List[SubnetNodeInfo]) -> Tuple[List[ConsensusScores], List[SubnetNodeConsensusData]]:
        """
        Filter scores against the blockchain included subnet nodes
        """        
        # Step 1: Get set of included subnet_node_ids
        included_subnet_node_ids = {node.subnet_node_id for node in included_nodes}
        scores_subnet_node_ids = {peer.subnet_node_id for peer in scores}

        filtered_scores = [
            score_obj
            for score_obj in scores
            if score_obj.subnet_node_id in included_subnet_node_ids
        ]

        score_map = {s.subnet_node_id: s.score for s in filtered_scores}

        consensus_formatted_scores = [
            ConsensusScores(
                peer_id=node.peer_id,
                score=score_map[node.subnet_node_id]
            )
            for node in included_nodes
            if node.subnet_node_id in scores_subnet_node_ids
        ]

        return consensus_formatted_scores, filtered_scores

    def filter_scores_and_extend_format(self, current_epoch: int, scores: List[ConsensusScores]) -> Tuple[List[ConsensusScores], List[SubnetNodeConsensusData]]:
        """
        Filter scores against the blockchain included subnet nodes
        """
        included_nodes = self.hypertensor.get_min_class_subnet_nodes_formatted(self.subnet_id, current_epoch, SubnetNodeClass.Included)

        # Step 1: Get set of included peer_ids
        included_peer_ids = {node.peer_id for node in included_nodes}
        scores_peer_ids = {peer.peer_id for peer in scores}

        filtered_scores = [
            score_obj
            for score_obj in scores
            if score_obj.peer_id in included_peer_ids
        ]

        score_map = {s.peer_id: s.score for s in filtered_scores}

        consensus_formatted_scores = [
            SubnetNodeConsensusData(
                subnet_node_id=node.subnet_node_id,
                score=score_map[node.peer_id]
            )
            for node in included_nodes
            if node.peer_id in scores_peer_ids
        ]

        return filtered_scores, consensus_formatted_scores

    def generate_task(self):
        """Generates a random arithmetic equation as a string."""
        operators = ['+', '-', '*', '/']
        operator = random.choice(operators)

        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)

        if operator == '/':
            while num1 % num2 != 0 or num2 == 0:
                num1 = random.randint(1, 20)
                num2 = random.randint(1, 20)

        equation = f"{num1} {operator} {num2}"
        return equation

    def eval_task(self, equation: str):
        return eval(equation)
