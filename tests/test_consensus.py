from typing import List
from mesh.substrate.chain_data import SubnetNodeConsensusData


def compare_consensus_data(
    my_data: List[SubnetNodeConsensusData],
    validator_data: List[SubnetNodeConsensusData],
) -> float:
    validator_data_set = set(frozenset(validator_data))
    my_data_set = set(frozenset(my_data))

    intersection = my_data_set & validator_data_set
    union = my_data_set | validator_data_set

    if not union:
        return 100.0

    # Accuracy as a percentage of overlap
    accuracy = (len(intersection) / len(union)) * 100
    return accuracy

# pytest tests/test_consensus.py::test_compare_consensus_data_100 -rP

def test_compare_consensus_data_100():
    my_data=[
        SubnetNodeConsensusData(
            subnet_node_id=1,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=2,
            score=int(1e18)
        ),
    ]
    validator_data=[
        SubnetNodeConsensusData(
            subnet_node_id=1,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=2,
            score=int(1e18)
        ),
    ]
    assert 100.0 == compare_consensus_data(my_data, validator_data)

# pytest tests/test_consensus.py::test_compare_consensus_data_50 -rP

def test_compare_consensus_data_50():
    my_data=[
        SubnetNodeConsensusData(
            subnet_node_id=1,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=2,
            score=int(1e18)
        ),
    ]
    validator_data=[
        SubnetNodeConsensusData(
            subnet_node_id=1,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=2,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=3,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=4,
            score=int(1e18)
        ),
    ]
    assert 50.0 == compare_consensus_data(my_data, validator_data)

    validator_data=[
        SubnetNodeConsensusData(
            subnet_node_id=1,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=2,
            score=int(1e18)
        ),
    ]
    my_data=[
        SubnetNodeConsensusData(
            subnet_node_id=1,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=2,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=3,
            score=int(1e18)
        ),
        SubnetNodeConsensusData(
            subnet_node_id=4,
            score=int(1e18)
        ),
    ]
    assert 50.0 == compare_consensus_data(my_data, validator_data)
