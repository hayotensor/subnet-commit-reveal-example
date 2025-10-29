from dataclasses import dataclass

from mesh import get_logger
from mesh.dht.crypto import SignatureValidator

logger = get_logger(__name__)

BASE_VALIDATOR_SCORE = 1.0  # Start from this score
EPSILON = 1e-8    # To avoid division by zero

"""
Consensus scores
"""
# In-subnet helper
@dataclass
class ConsensusScores:
  peer_id: str
  score: int

# On-chain format
@dataclass
class OnChainConsensusScore:
  subnet_node_id: int
  score: int

"""
Mock Role Scores

Fill in roles if needed here along with any required parameters, such as tensor outputs
"""
@dataclass
class MockValidatorScores:
  peer_id: str
  score: int

# RSA or Ed25519 subkey for records (protected records requiring signing/validating)
def get_consensus_subkey(record_validator: SignatureValidator) -> bytes:
  return record_validator.local_public_key
