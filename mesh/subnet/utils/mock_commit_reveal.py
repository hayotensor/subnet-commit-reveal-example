from collections import defaultdict
from typing import Optional

from mesh import get_dht_time, get_logger
from mesh.dht.routing import DHTID
from mesh.dht.validation import DHTRecord, DHTRecordRequestType
from mesh.substrate.chain_functions import EpochData, Hypertensor
from mesh.substrate.config import BLOCK_SECS, EPOCH_LENGTH
from mesh.utils.key import extract_peer_id_from_record_validator

logger = get_logger(__name__)

"""
Commit-Reveal Schema using the HypertensorPredicateValidator
"""

"""
Hypertensor predicate validator

Verified allowable keys, schemas, epoch relationships, and commit-reveal schemes.
"""

def get_verifier_commit_key(epoch: int) -> str:
    return f"verifier_commit_epoch_{epoch}"

def get_verifier_reveal_key(epoch: int) -> str:
    return f"verifier_reveal_epoch_{epoch}"

def get_prover_commit_key(epoch: int) -> str:
    return f"prover_commit_epoch_{epoch}"

def get_prover_reveal_key(epoch: int) -> str:
    return f"prover_reveal_epoch_{epoch}"

def get_scores_commit_key(epoch: int) -> str:
    return f"scores_commit_epoch_{epoch}"

def get_scores_reveal_key(epoch: int) -> str:
    return f"scores_reveal_epoch_{epoch}"

def get_mock_commit_key(epoch: int) -> str:
    return f"commit_epoch_{epoch}"

def get_mock_reveal_key(epoch: int) -> str:
    return f"reveal_epoch_{epoch}"

def get_mock_consensus_key(epoch: int) -> str:
    return f"consensus_epoch_{epoch}"

# peer commit-reveal epoch percentage elapsed deadlines
COMMIT_DEADLINE = 0.5
REVEAL_DEADLINE = 0.80

"""
Expiration validations

Add expirations for each key stored
"""
MAX_HEART_BEAT_TIME = BLOCK_SECS * EPOCH_LENGTH * 1.1   # Max 1.1 epochs
MAX_CONSENSUS_TIME = BLOCK_SECS * EPOCH_LENGTH * 5      # Max 5 epochs
MAX_COMMIT_TIME = BLOCK_SECS * EPOCH_LENGTH * 5         # Max 5 epochs
MAX_REVEAL_TIME = BLOCK_SECS * EPOCH_LENGTH * 5         # Max 5 epochs

VERIFIER_COMMIT_DEADLINE = 0.5
VERIFIER_REVEAL_DEADLINE = 0.6
SCORES_REVEAL_DEADLINE = 0.6

class MockHypertensorCommitReveal:

    MAX_EPOCH_HISTORY = 5 # How many epochs to store peer epoch history before clean up

    def __init__(self, hypertensor: Hypertensor, subnet_id: int):
        self.hypertensor = hypertensor
        self.subnet_id = subnet_id
        # Store any data required for logic
        self.slot: int | None = None

        # Maximum number of stores per key type, see `valid_keys` in `_get_key_type`
        self.per_peer_epoch_limits = {
            "node": 100,
            "verifier_commit": 1,
            "verifier_reveal": 1,
            "scores_reveal": 1,
            "scores_commit": 1,
        }

        # Track the number of key stores per peer, per epoch
        self._peer_store_tracker = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        # Store `self.slot`
        self._ensure_slot()

    # Create any functions required for the logic
    def _ensure_slot(self):
        if self.slot is None:
            subnet_info = self.hypertensor.get_formatted_subnet_info(self.subnet_id)
            self.slot = subnet_info.slot_index
        return self.slot

    def epoch_data(self) -> EpochData:
        """Returns the current epoch data"""
        return self.hypertensor.get_subnet_epoch_data(self._ensure_slot())

    def _has_exceeded_store_limit(self, peer_id: str, key_type: str, epoch: int) -> bool:
        """Check if the peer has already hit their per-epoch limit for this key type."""
        limit = self.per_peer_epoch_limits.get(key_type, 1)
        logger.debug(f"Current peer epoch limit {limit}")
        count = self._peer_store_tracker[epoch][key_type][peer_id]
        logger.debug(f"Current node key count {count}")
        if count >= limit:
            logger.debug(
                f"Peer {peer_id} exceeded store limit for {key_type} (epoch {epoch}, "
                f"count={count}, limit={limit})"
            )
            return True
        return False

    def _record_peer_store(self, peer_id: str, key_type: str, epoch: int):
        """Increment peer store counter after a successful PUT."""
        self._peer_store_tracker[epoch][key_type][peer_id] += 1
        new_count = self._peer_store_tracker[epoch][key_type][peer_id]
        logger.debug(
            f"Recorded store for {peer_id} → {key_type} @ epoch {epoch} "
            f"(new count={new_count})"
        )

    def _cleanup_old_epochs(self, current_epoch: int):
        """Remove records older than MAX_EPOCH_HISTORY epochs."""
        old_epochs = [
            e for e in self._peer_store_tracker.keys()
            if e < current_epoch - self.MAX_EPOCH_HISTORY
        ]

        for e in old_epochs:
            del self._peer_store_tracker[e]
            logger.debug(
                f"Current epoch: {current_epoch} "
                f"Cleaned up tracking data for old epoch {e}"
            )

    def _get_key_type(self, record: DHTRecord, current_epoch: int) -> Optional[int]:
        """
        Create schemas here
        You can use libraries like Pydantic to define schemas for keys, subkeys, and values

        TODO: Persist this data in a local database for persistance on validator node restarts
        """
        valid_keys = {
            # Heartbeat
            DHTID.generate(source="node").to_bytes(): "node",

            # ⸺ 0-15%
            DHTID.generate(source=f"scores_reveal_epoch_{current_epoch}").to_bytes(): "scores_reveal",

            # ⸺ 15-50%
            DHTID.generate(source=f"verifier_commit_epoch_{current_epoch}").to_bytes(): "verifier_commit",

            # ⸺ 50-60%
            DHTID.generate(source=f"verifier_reveal_epoch_{current_epoch}").to_bytes(): "verifier_reveal",

            # ⸺ 60-90%
            DHTID.generate(source=f"scores_commit_epoch_{current_epoch}").to_bytes(): "scores_commit",
        }

        return valid_keys.get(record.key, None)

    def _store_to_db(self, record: DHTRecord, current_epoch: int) -> None:
        """Archive data"""
        ...

    def __call__(self, record: DHTRecord, type: DHTRecordRequestType) -> bool:
        """
        Callable interface

        This is the logic that will run to validate all GET/POST DHT records

        Note: If any peers change this, they will likely become out of consensus as its data will
              mismatch others. For example, if a node stores data that others will not store, they
              will be out of sync and have bad data.

              See on-chain subnet node reputations for how nodes are removed when they go below the
              subnets minimum node reputation
        """
        try:
            # Get caller peer ID
            # This also ensures the record has a public key as a subkey
            # NOTE: To use this, `SignatureValidator` must be implemented with priority=10
            caller_peer_id = extract_peer_id_from_record_validator(record.subkey)
            if caller_peer_id is None:
                return False

            logger.debug(f"caller_peer_id: {caller_peer_id}")

            if type is DHTRecordRequestType.GET:
                logger.debug(f"{caller_peer_id} requested GET")
                return True

            # Get `EpochData`
            epoch_data = self.epoch_data()
            current_epoch = epoch_data.epoch
            percent_complete = epoch_data.percent_complete # Get progress of epoch for commit-reveal phases

            logger.debug(f"{caller_peer_id} is storing data at slot={self.slot}, epoch={current_epoch}")

            # Clean up old keys
            self._cleanup_old_epochs(current_epoch)

            # Get valid key type
            key_type = self._get_key_type(record, current_epoch)
            logger.debug(f"key_type={key_type}")

            if key_type is None:
                logger.warning(f"key_type is None={key_type}")
                return False

            # Verify peer store limit condition
            if self._has_exceeded_store_limit(caller_peer_id, key_type, current_epoch):
                return False

            dht_time = get_dht_time()

            """
            Logic here can be extended to account for any conditions

            In this mock class:

            "node": The heartbeat can be stored up to 100 time per epoch
            "commit": Must be stored by the 50% elapsed of the epoch, 1 time per epoch
            "reveal": Must be stored between 50%-60% elapsed of the epoch, 1 time per epoch
            """

            # DEADLINES AND EXPIRATIONS
            if key_type == "node":
                max_expiration = dht_time + MAX_HEART_BEAT_TIME
                if record.expiration_time > max_expiration:
                    return False

            # 0-50%
            elif key_type == "verifier_commit":
                if percent_complete > VERIFIER_COMMIT_DEADLINE:
                    logger.error("verifier_commit percent_complete")
                    return False
                if record.expiration_time > dht_time + MAX_COMMIT_TIME:
                    logger.error("verifier_commit expiration_time")
                    return False

            # 51-60%
            elif key_type == "verifier_reveal":
                if percent_complete <= VERIFIER_COMMIT_DEADLINE or percent_complete > VERIFIER_REVEAL_DEADLINE:
                    logger.error("verifier_reveal percent_complete")
                    return False
                if record.expiration_time > dht_time + MAX_REVEAL_TIME:
                    logger.error("verifier_reveal expiration_time")
                    return False

            # 51-60%
            elif key_type == "scores_reveal":
                if percent_complete <= VERIFIER_COMMIT_DEADLINE or percent_complete > SCORES_REVEAL_DEADLINE:
                    logger.error("percent_complete percent_complete")
                    return False
                if record.expiration_time > dht_time + MAX_REVEAL_TIME:
                    logger.error("percent_complete expiration_time")
                    return False

            # 60-100%
            elif key_type == "scores_commit":
                if percent_complete <= SCORES_REVEAL_DEADLINE:
                    logger.error("score_commit percent_complete")
                    return False
                if record.expiration_time > dht_time + MAX_COMMIT_TIME:
                    logger.error("score_commit expiration_time")
                    return False

            self._record_peer_store(caller_peer_id, key_type, current_epoch)

            return True
        except Exception as e:
            logger.warning(f"MockHypertensorCommitReveal error: {e}")
            return False
