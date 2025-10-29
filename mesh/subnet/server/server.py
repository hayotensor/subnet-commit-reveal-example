from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

import mesh
from mesh import DHT, get_dht_time
from mesh.dht.crypto import SignatureValidator
from mesh.dht.validation import HypertensorPredicateValidator, RecordValidatorBase
from mesh.subnet.consensus.consensus import Consensus
from mesh.subnet.consensus.task import TaskCommitReveal
from mesh.subnet.protocols.math_protocol import MathProtocol
from mesh.subnet.utils.mock_commit_reveal import MockHypertensorCommitReveal
from mesh.substrate.chain_functions import Hypertensor
from mesh.substrate.mock.chain_functions import MockHypertensor
from mesh.utils.authorizers.auth import AuthorizerBase, SignatureAuthorizer
from mesh.utils.authorizers.pos_auth import ProofOfStakeAuthorizer
from mesh.utils.data_structures import ServerClass, ServerInfo, ServerState
from mesh.utils.dht import declare_node_sig, get_node_infos_sig
from mesh.utils.key import get_private_key
from mesh.utils.logging import get_logger
from mesh.utils.ping import PingAggregator
from mesh.utils.proof_of_stake import ProofOfStake
from mesh.utils.random import sample_up_to
from mesh.utils.reachability import ReachabilityProtocol, check_direct_reachability
from mesh.utils.timed_storage import MAX_DHT_TIME_DISCREPANCY_SECONDS

logger = get_logger(__name__)

DEFAULT_NUM_WORKERS = 8

class Server:
    def __init__(
        self,
        *,
        initial_peers: List[str],
        public_name: Optional[str] = None,
        role: ServerClass,
        update_period: float = 60,
        expiration: Optional[float] = None,
        reachable_via_relay: Optional[bool] = None,
        use_relay: bool = True,
        use_auto_relay: bool = True,
        subnet_id: Optional[int] = None,
        subnet_node_id: Optional[int] = None,
        hypertensor: Optional[Hypertensor] = None,
        **kwargs,
    ):
        """
        Create a server
        """
        self.reachability_protocol = None
        self.update_period = update_period
        if expiration is None:
            expiration = max(2 * update_period, MAX_DHT_TIME_DISCREPANCY_SECONDS)
        self.expiration = expiration

        self.initial_peers = initial_peers
        self.announce_maddrs = kwargs.get('announce_maddrs')  # Returns None if 'my_key' not present

        self.subnet_id = subnet_id
        self.subnet_node_id = subnet_node_id
        self.hypertensor = hypertensor

        identity_path = kwargs.get('identity_path', None)
        pk = get_private_key(identity_path)

        """
        Initialize record validators

        See https://docs.hypertensor.org/mesh-template/dht-records/record-validator
        """
        # Initialize signature record validator. See https://docs.hypertensor.org/mesh-template/dht-records/record-validator/signature-validators
        self.signature_validator = SignatureValidator(pk)
        self.record_validators=[self.signature_validator]

        # Initialize predicate validator here. See https://docs.hypertensor.org/mesh-template/dht-records/record-validator/predicate-validators
        if self.hypertensor is not None:
            # consensus_predicate = HypertensorPredicateValidator.from_predicate_class(
            #     MockHypertensorCommitReveal, hypertensor=self.hypertensor, subnet_id=subnet_id
            # )
            consensus_predicate = HypertensorPredicateValidator.from_predicate_class(
                MockHypertensorCommitReveal, hypertensor=self.hypertensor, subnet_id=subnet_id
            )

        else:
            # consensus_predicate = HypertensorPredicateValidator.from_predicate_class(
            #     MockHypertensorCommitReveal, hypertensor=MockHypertensor(), subnet_id=subnet_id
            # )
            consensus_predicate = HypertensorPredicateValidator.from_predicate_class(
                MockHypertensorCommitReveal, hypertensor=MockHypertensor(), subnet_id=subnet_id
            )

        self.record_validators.append(consensus_predicate)

        """
        Initialize authorizers

        See https://docs.hypertensor.org/mesh-template/authorizers
        """
        # Initialize signature authorizer. See https://docs.hypertensor.org/mesh-template/authorizers/signature-authorizer
        self.signature_authorizer = SignatureAuthorizer(pk)

        # Initialize PoS authorizer. See https://docs.hypertensor.org/mesh-template/authorizers/pos
        if self.hypertensor is not None:
            logger.info("Initializing PoS - proof-of-stake")
            pos = ProofOfStake(
                self.subnet_id,
                self.hypertensor,
                min_class=1,
            )
            self.pos_authorizer = ProofOfStakeAuthorizer(self.signature_authorizer, pos)
        else:
            logger.info("Skipping PoS - proof-of-stake, using signature authorization only. If starting in production, make sure to use PoS")
            # For testing purposes, at minimum require signatures
            self.pos_authorizer = self.signature_authorizer

        # Test connecting to the DHT as a direct peer
        if reachable_via_relay is None:
            is_reachable = check_direct_reachability(initial_peers=initial_peers, authorizer=self.pos_authorizer, use_relay=False, **kwargs)
            reachable_via_relay = is_reachable is False  # if can't check reachability (returns None), run a full peer
            logger.info(f"This server is accessible {'via relays' if reachable_via_relay else 'directly'}")

        logger.info("About to run DHT")

        self.dht = DHT(
            initial_peers=initial_peers,
            start=True,
            num_workers=DEFAULT_NUM_WORKERS,
            use_relay=use_relay,
            use_auto_relay=use_auto_relay,
            client_mode=reachable_via_relay,
            record_validators=self.record_validators,
            **dict(kwargs, authorizer=self.pos_authorizer)
        )
        self.reachability_protocol = ReachabilityProtocol.attach_to_dht(self.dht, identity_path) if not reachable_via_relay else None

        visible_maddrs_str = [str(a) for a in self.dht.get_visible_maddrs()]

        logger.info(f"Running a server on {visible_maddrs_str}")

        throughput_info = {"throughput": 1.0}
        self.server_info = ServerInfo(
            state=ServerState.JOINING,
            role=role,
            public_name=public_name,
            version="1.0.0",
            using_relay=reachable_via_relay,
            **throughput_info,
        )

        self.protocol = None
        self.module_container = None
        self.consensus = None
        self.stop = threading.Event()

    def run(self):
        self.protocol = MathProtocol(
            dht=self.dht,
            subnet_id=self.subnet_id,
            hypertensor=self.hypertensor,
            authorizer=self.signature_authorizer,
            start=True
        )

        self.module_container = ModuleAnnouncerThread(
            dht=self.dht,
            server_info=self.server_info,
            record_validator=self.signature_validator,
            update_period=self.update_period,
            expiration=self.expiration,
            start=True
        )

        self.consensus = ConsensusThread(
            dht=self.dht,
            server_info=self.server_info,
            subnet_id=self.subnet_id,
            subnet_node_id=self.subnet_node_id,
            record_validator=self.signature_validator,
            authorizer=self.signature_authorizer,
            hypertensor=self.hypertensor,
            start=True
        )

        """
        Keep server running forever
        """
        self.stop.wait()

    def shutdown(self, timeout: Optional[float] = 5):
        logger.info("Shutting down Server, wait to shutdown properly")
        self.stop.set()

        if self.protocol is not None:
            self.protocol.shutdown()

        if self.reachability_protocol is not None:
            self.reachability_protocol.shutdown()

        if self.consensus is not None:
            self.consensus.shutdown()

        self.dht.shutdown()
        self.dht.join()

class ModuleAnnouncerThread(threading.Thread):
    def __init__(
        self,
        dht: DHT,
        server_info: ServerInfo,
        record_validator: RecordValidatorBase,
        update_period: float,
        expiration: Optional[float] = None,
        start: bool = True,
    ):
        super().__init__()
        self.dht = dht

        server_info.state = ServerState.JOINING
        self.dht_announcer = ModuleHeartbeatThread(
            dht,
            server_info,
            record_validator,
            update_period=update_period,
            expiration=expiration,
            daemon=True,
        )
        self.role = server_info.role
        self.dht_announcer.start()
        logger.info("Announced to the DHT that we are joining")

        if start:
            self.start()

    def run(self):
        logger.info("Announcing that node is online")
        self.dht_announcer.announce(ServerState.ONLINE)

    def shutdown(self):
        """
        Gracefully terminate the container, process-safe.
        """
        self.dht_announcer.announce(ServerState.OFFLINE)
        logger.info("Announced to the DHT that we are exiting")

        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=5)
        logger.info("Module shut down successfully")

class ConsensusThread():
    def __init__(
        self,
        dht: DHT,
        server_info: ServerInfo,
        subnet_id: int,
        subnet_node_id: int,
        record_validator: RecordValidatorBase,
        authorizer: AuthorizerBase,
        hypertensor: Hypertensor,
        start: bool = True,
    ):
        super().__init__()
        self.dht = dht
        self.server_info = server_info
        self.subnet_id = subnet_id
        self.subnet_node_id = subnet_node_id
        self.signature_validator = record_validator
        self.authorizer = authorizer
        self.hypertensor = hypertensor
        self.consensus = None
        self.validator = None

        if start:
            self.run()

    def run(self) -> None:
        """
        Add any other logic the Consensus class requires to run,
        such as differ node role classes, etc.

        See template implementation
        """
        task_commit_reveal = TaskCommitReveal(
            dht=self.dht,
            authorizer=self.authorizer,
            record_validator=self.signature_validator,
            subnet_id=self.subnet_id,
            hypertensor=self.hypertensor,
        )

        self.consensus = Consensus(
            dht=self.dht,
            subnet_id=self.subnet_id,
            subnet_node_id=self.subnet_node_id,
            record_validator=self.signature_validator,
            hypertensor=self.hypertensor,
            task_commit_reveal=task_commit_reveal,
            skip_activate_subnet=False,
            start=True,
        )

        logger.info("Starting consensus")

    def shutdown(self):
        if self.consensus is not None:
            self.consensus.shutdown()

        if self.validator is not None:
            self.validator.shutdown()

class ModuleHeartbeatThread(threading.Thread):
    """Periodically announces server is live before expiration of storage, visible to all DHT peers"""

    def __init__(
        self,
        dht: DHT,
        server_info: ServerInfo,
        record_validator: RecordValidatorBase,
        *,
        update_period: float,
        expiration: float,
        max_pinged: int = 5,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.dht = dht
        self.server_info = server_info
        self.record_validator = record_validator

        self.update_period = update_period
        self.expiration = expiration
        self.trigger = threading.Event()

        self.max_pinged = max_pinged
        self.ping_aggregator = PingAggregator(self.dht)

    def run(self) -> None:
        """
        Start heartbeat

        - Tell the network you're still hear
        - Ping other nodes
        """
        while True:
            start_time = time.perf_counter()

            if self.server_info.state != ServerState.OFFLINE:
                self._ping_next_servers()
                self.server_info.next_pings = {
                    peer_id.to_base58(): rtt for peer_id, rtt in self.ping_aggregator.to_dict().items()
                }
            else:
                self.server_info.next_pings = None  # No need to ping if we're disconnecting

            logger.info("Declaring node [Heartbeat]...")

            """
            Do not change the "node" key

            See https://docs.hypertensor.org/build-a-subnet/requirements#node-key-public-key-subkey
            """
            declare_node_sig(
                dht=self.dht,
                key="node",
                server_info=self.server_info,
                expiration_time=get_dht_time() + self.expiration,
                record_validator=self.record_validator
            )

            if self.server_info.state == ServerState.OFFLINE:
                break

            """
            If you want to host multiple applications in one DHT or run a bootstrap node that acts as an entry 
            point to multiple subnets, you can do so in the DHTStorage mechanism.

            Without a clear understanding of how DHTs or DHTStorage, we suggest isolating subnets and not using this.

            if not self.dht_prefix.startswith("_"):
                self.dht.store(
                    key="_team_name_here.subnets",
                    subkey=self.dht_prefix,
                    value=self.model_info.to_dict(),
                    expiration_time=get_dht_time() + self.expiration,
                )
            """

            delay = self.update_period - (time.perf_counter() - start_time)
            if delay < 0:
                logger.warning(
                    f"Declaring node to DHT takes more than --update_period, consider increasing it (currently {self.update_period})"
                )
            self.trigger.wait(max(delay, 0))
            self.trigger.clear()

    def announce(self, state: ServerState) -> None:
        self.server_info.state = state
        self.trigger.set()
        if state == ServerState.OFFLINE:
            if self.is_alive():
                self.join(timeout=5)


    def _ping_next_servers(self) -> Dict[mesh.PeerID, float]:
        module_infos = get_node_infos_sig(
            self.dht,
            uid="node",
            latest=True
        )
        if len(module_infos) == 0:
            return
        print("module_infos", module_infos)
        middle_servers = {info.peer_id for info in module_infos}
        pinged_servers = set(sample_up_to(middle_servers, self.max_pinged))
        # discard self
        pinged_servers.discard(self.dht.peer_id)
        self.ping_aggregator.ping(list(pinged_servers))
