import asyncio
from dataclasses import asdict
import multiprocessing as mp
from typing import Any, Dict, List, Optional, Tuple

from mesh import DHT
from mesh.dht.validation import RecordValidatorBase
from mesh.subnet.consensus.task import TaskCommitReveal
from mesh.subnet.consensus.utils import compare_consensus_data, did_node_attest
from mesh.subnet.utils.consensus import ConsensusScores
from mesh.subnet.utils.mock_commit_reveal import SCORES_REVEAL_DEADLINE, VERIFIER_COMMIT_DEADLINE, VERIFIER_REVEAL_DEADLINE
from mesh.substrate.chain_data import ConsensusData, SubnetNodeConsensusData
from mesh.substrate.chain_functions import Hypertensor, SubnetNodeClass
from mesh.substrate.config import BLOCK_SECS
from mesh.substrate.mock.chain_functions import MockHypertensor
from mesh.substrate.mock.local_chain_functions import LocalMockHypertensor
from mesh.utils import get_logger
from mesh.utils.asyncio import switch_to_uvloop

logger = get_logger(__name__)

class Consensus(mp.Process):
    def __init__(
        self,
        dht: DHT,
        subnet_id: int,
        subnet_node_id: int,
        record_validator: RecordValidatorBase,
        hypertensor: Hypertensor,
        task_commit_reveal: TaskCommitReveal,
        skip_activate_subnet: bool = False,
        start: bool = True
    ):
        super().__init__()
        self.dht = dht
        self.peer_id = self.dht.peer_id
        self.subnet_id = subnet_id
        self.subnet_node_id = subnet_node_id
        self.hypertensor = hypertensor
        self.task_commit_reveal = task_commit_reveal
        self.record_validator = record_validator
        self.previous_epoch_data: int | None = None
        self.is_subnet_active: bool = False
        self.skip_activate_subnet = skip_activate_subnet
        self.slot: int | None = None # subnet epoch slot, set in `run_activate_subnet`
        self.epoch_scores: Dict[int, List[Dict]] = dict() # Scores
        self.stop = mp.Event()
        self._inner_pipe, self._outer_pipe = mp.Pipe(duplex=True)

        if start:
            self.start()

    def run(self):
        loop = switch_to_uvloop()
        stop = asyncio.Event()
        loop.add_reader(self._inner_pipe.fileno(), stop.set)

        try:
            loop.run_until_complete(self._main_loop())
        except KeyboardInterrupt:
            logger.debug("Caught KeyboardInterrupt, shutting down")

    async def _main_loop(self):
        if not await self.run_activate_subnet():
            return
        if not await self.run_is_node_validator():
            return
        await self.run_forever()

    def get_validator(self, epoch: int):
        validator = self.hypertensor.get_rewards_validator(self.subnet_id, epoch)
        return validator

    def get_scores(self, target_epoch: int) -> Optional[List[Any]]:
        if (target_epoch - 1) in self.epoch_scores:
            del self.epoch_scores[target_epoch - 1]
        return self.epoch_scores.get(target_epoch, None)

    def _get_attestation_ratio(self, consensus_data: ConsensusData):
        return len(consensus_data.attests) / len(consensus_data.subnet_nodes)

    async def run_activate_subnet(self):
        """
        Verify subnet is active on-chain before starting consensus

        For initial coldkeys this will sleep until the enactment period, then proceed
        to check once per epoch after enactment starts if the owner activated the subnet
        """
        # Useful if subnet is already active and for testing
        if self.skip_activate_subnet:
            logger.info("Skipping subnet activation and attempting to start consensus")
            return True

        last_epoch = None
        subnet_active = False
        max_errors = 3
        errors_count = 0
        while not self.stop.is_set():
            if self.slot is None or self.slot == 'None':  # noqa: E711
                try:
                    slot = self.hypertensor.get_subnet_slot(self.subnet_id)
                    if slot == None or slot == 'None':  # noqa: E711
                        await asyncio.sleep(
                            BLOCK_SECS
                        )
                        continue
                    self.slot = int(str(slot))
                    logger.info(f"Subnet running in slot {self.slot}")
                except Exception as e:
                    logger.warning(f"Consensus get_subnet_slot={e}", exc_info=True)

            epoch_data = self.hypertensor.get_epoch_data()
            current_epoch = epoch_data.epoch

            if current_epoch != last_epoch:
                # offset_sleep = 0
                subnet_info = self.hypertensor.get_formatted_subnet_info(self.subnet_id)
                if subnet_info is None or subnet_info == None:  # noqa: E711
                    # None means the subnet is likely deactivated
                    if errors_count > max_errors:
                        logger.warning("Cannot find subnet ID: %s, shutting down", self.subnet_id)
                        self.shutdown()
                        subnet_active = False
                        break
                    else:
                        logger.warning(f"Cannot find subnet ID: {self.subnet_id}, trying {max_errors - errors_count} more times")
                        errors_count = errors_count + 1
                else:
                    if subnet_info.state == "Active":
                        logger.info(f"Subnet ID {self.subnet_id} is active, starting consensus")
                        subnet_active = True
                        break

                last_epoch = current_epoch

            logger.info("Waiting for subnet to be activated. Sleeping until next epoch")
            await asyncio.sleep(
                max(0.0, epoch_data.seconds_remaining)
            )

        return subnet_active

    async def run_is_node_validator(self):
        """
        Verify node is active on-chain before starting consensus

        Node must be classed as Idle on-chain to to start consensus

        Included nodes cannot be the elected validator or attest but must take part in consensus
        and be included in the consensus data to graduate to a Validator classed node
        """
        last_epoch = None
        while not self.stop.is_set():
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            current_epoch = epoch_data.epoch

            if current_epoch != last_epoch:
                nodes = self.hypertensor.get_min_class_subnet_nodes_formatted(self.subnet_id, current_epoch, SubnetNodeClass.Idle)
                node_found = False
                for node in nodes:
                    if node.subnet_node_id == self.subnet_node_id:
                        node_found = True
                        break

                if not node_found:
                    logger.info(
                        "Subnet Node ID %s is not Validator class on epoch %s. Trying again next epoch", self.subnet_node_id, current_epoch
                    )
                else:
                    logger.info(
                        "Subnet Node ID %s is classified as a Validator class on epoch %s. Starting consensus.", self.subnet_node_id, current_epoch
                    )
                    break

                last_epoch = current_epoch

            await asyncio.sleep(epoch_data.seconds_remaining)

        return True

    async def run_forever(self):
        """
        Loop until a new epoch to found, then run consensus logic
        """
        self._async_stop_event = asyncio.Event()
        last_epoch = None
        started = False

        logger.info("✅ Starting consensus")

        while not self.stop.is_set() and not self._async_stop_event.is_set():
            try:
                epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)

                # Start on fresh epoch
                if started is False:
                    started = True
                    try:
                        await asyncio.wait_for(
                            self._async_stop_event.wait(),
                            timeout=epoch_data.seconds_remaining
                        )
                        break  # Stop event was set
                    except asyncio.TimeoutError:
                        continue  # Timeout reached, continue to next iteration

                current_epoch = epoch_data.epoch
                if current_epoch != last_epoch:
                    """
                    Add validation logic before and/or after `await run_consensus(current_epoch)`

                    The logic here should be for qualifying nodes (proving work), generating scores, etc.
                    """
                    # Attest/Validate prev epochs data      ⸺ 0-15%
                    await self.run_consensus(current_epoch)

                    # Run tasks and commit scores           ⸺ 0-50%
                    await self.run_task_commit(current_epoch)

                    # Reveal commit                         ⸺ 51-60%
                    await self.run_task_reveal(current_epoch)

                    # Reveal prev commit scores             ⸺ 51-60%
                    await self.run_reveal_scores(current_epoch)

                    # Get scores for next epoch             ⸺ 60-100%
                    _, consensus_formatted_scores = await self.run_verify_and_score_peers(current_epoch)

                    if consensus_formatted_scores:
                        self.epoch_scores[current_epoch] = consensus_formatted_scores
                        # Commit scores
                        await self.run_commit_scores(current_epoch)

                    # Have peers commit scores on this epoch, and reveal on the following
                    # This ensures we know the peers did the work to get the scores and know them
                    # Later this data can be used to check against its data (if validator) or if
                    # it attested the same validator scores they had

                    last_epoch = current_epoch

                    # Get fresh epoch data after processing
                    epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)

                # Wait for either stop event or timeout based on remaining time
                try:
                    await asyncio.wait_for(
                        self._async_stop_event.wait(),
                        timeout=epoch_data.seconds_remaining
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Timeout reached, continue to next iteration
            except Exception as e:
                logger.warning(e, exc_info=True)
                await asyncio.sleep(BLOCK_SECS)

    async def run_task_commit(self, current_epoch: int):        
        while not self.stop.is_set():
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            _current_epoch = epoch_data.epoch

            # If next epoch or validator took too long, move onto next steps
            if _current_epoch != current_epoch or epoch_data.percent_complete > VERIFIER_COMMIT_DEADLINE:
                break

            await self.task_commit_reveal.call_and_commit_all_tasks(current_epoch)
            break

    async def run_task_reveal(self, current_epoch: int):        
        while not self.stop.is_set():
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            _current_epoch = epoch_data.epoch

            # If next epoch or validator took too long, move onto next steps
            if _current_epoch != current_epoch or epoch_data.percent_complete > VERIFIER_REVEAL_DEADLINE:
                break

            if epoch_data.percent_complete <= VERIFIER_COMMIT_DEADLINE:
                await asyncio.sleep(BLOCK_SECS)
                continue

            await self.task_commit_reveal.reveal_tasks(current_epoch)
            break

    async def run_commit_scores(self, current_epoch: int):
        if not self.epoch_scores[current_epoch]:
            return

        while not self.stop.is_set():
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            _current_epoch = epoch_data.epoch

            # If next epoch or validator took too long, move onto next steps
            if _current_epoch != current_epoch:
                break
            
            # Commit scores after reveals
            if epoch_data.percent_complete <= SCORES_REVEAL_DEADLINE:
                await asyncio.sleep(BLOCK_SECS)
                continue

            await self.task_commit_reveal.commit_scores(current_epoch, self.epoch_scores[current_epoch])
            break

    async def run_reveal_scores(self, current_epoch: int):
        while not self.stop.is_set():
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            _current_epoch = epoch_data.epoch

            # If next epoch or validator took too long, move onto next steps
            if _current_epoch != current_epoch or epoch_data.percent_complete > SCORES_REVEAL_DEADLINE:
                break

            if epoch_data.percent_complete <= VERIFIER_COMMIT_DEADLINE:
                await asyncio.sleep(BLOCK_SECS)
                continue

            await self.task_commit_reveal.reveal_scores(current_epoch)
            break

    async def run_verify_and_score_peers(self, current_epoch: int) -> Tuple[Optional[List[ConsensusScores]], Optional[List[SubnetNodeConsensusData]]]:
        while not self.stop.is_set():
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            _current_epoch = epoch_data.epoch

            # If next epoch or validator took too long, move onto next steps
            if _current_epoch != current_epoch:
                return None, None

            if epoch_data.percent_complete <= VERIFIER_REVEAL_DEADLINE:
                await asyncio.sleep(BLOCK_SECS)
                continue

            return self.task_commit_reveal.verify_and_score_peers(current_epoch)

    async def run_consensus(self, current_epoch: int):
        """
        At the start of each epoch, we check if we are validator

        Scores are likely generated and rooted from the `run_forever` function, although, anything use cases are possible

        We start by:
            - Getting scores
                - Can generate scores in real-time or get from the DHT database

        If elected on-chain validator:
            - Submit scores to Hypertensor

        If attestor (non-elected on-chain validator):
            - Retrieve validators score submission from Hypertensor
            - Compare to our own
            - Attest if 100% accuracy, else do nothing
        """
        logger.info(f"[Consensus] epoch: {current_epoch}")

        scores = self.get_scores(current_epoch - 1)
        if scores is None:
            return

        validator = None
        # Wait until validator is chosen
        while not self.stop.is_set():
            validator = self.get_validator(current_epoch)
            epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
            _current_epoch = epoch_data.epoch
            if _current_epoch != current_epoch:
                validator = None
                break

            if validator is not None or validator != 'None':
                break

            # Wait until next block to try again
            await asyncio.sleep(BLOCK_SECS)

        if validator is None or validator == None:  # noqa: E711
            return

        if validator == self.subnet_node_id:
            logger.info(f"🎖️ Acting as elected validator for epoch {current_epoch} and proposing an attestation to the blockchain")

            # See if attestation proposal submitted
            consensus_data = self.hypertensor.get_consensus_data_formatted(self.subnet_id, current_epoch)
            if consensus_data is not None: # noqa: E711
                logger.info("Already submitted data, moving to next epoch")
                return

            if len(scores) == 0:
                """
                Add any logic here for when no scores are present.

                The blockchain allows the validator to submit an empty score. This can mean
                the mesh is in a broken state or not synced.

                If other peers also come up with the same "zero" scores, they can attest the validator
                and the validator will not accrue penalties or be slashed. The subnet itself will accrue
                penalties until it recovers (penalties decrease for every successful epoch).

                No scores are generated, likely subnet in broken state and all other nodes
                should be too, so we submit consensus with no scores.

                This will increase subnet penalties, but avoid validator penalties.

                Any successful epoch following will remove these penalties on the subnet
                """
                self.hypertensor.propose_attestation(self.subnet_id, data=[asdict(s) for s in scores])
            else:
                self.hypertensor.propose_attestation(self.subnet_id, data=[asdict(s) for s in scores])

        elif validator is not None:
            logger.info(f"🗳️ Acting as attestor/voter for epoch {current_epoch}")
            consensus_data = None
            while not self.stop.is_set():
                # Check consensus data exists in case attest fails
                if consensus_data is None or consensus_data == None:  # noqa: E711
                    consensus_data = self.hypertensor.get_consensus_data_formatted(self.subnet_id, current_epoch)

                epoch_data = self.hypertensor.get_subnet_epoch_data(self.slot)
                _current_epoch = epoch_data.epoch

                # If next epoch or validator took too long, move onto next steps
                if _current_epoch != current_epoch or epoch_data.percent_complete > 0.15:
                    break

                if consensus_data is None or consensus_data == None:  # noqa: E711
                    await asyncio.sleep(BLOCK_SECS)
                    continue

                validator_data = consensus_data.data

                """
                Get all of the hosters inference outputs they stored to the DHT
                """

                self.previous_epoch_data = None
                if 1.0 == compare_consensus_data(my_data=scores, validator_data=validator_data):
                    # Update previous epoch to current epoch data
                    self.previous_epoch_data = scores

                    # Check if we already attested
                    if did_node_attest(self.subnet_node_id, consensus_data):
                        logger.info("Already attested, moving to next epoch")
                        break

                    logger.info(f"✅ Elected validator's data matches for epoch {current_epoch}, attesting their data")
                    receipt = self.hypertensor.attest(self.subnet_id)
                    if isinstance(self.hypertensor, MockHypertensor) or isinstance(self.hypertensor, LocalMockHypertensor): # don't check receipt if using mock
                        return

                    if receipt.is_success:
                        break
                    else:
                        await asyncio.sleep(BLOCK_SECS)
                else:
                    logger.info(f"❌ Data doesn't match validator's for epoch {current_epoch}, moving forward with no attetation")
                    break

    def shutdown(self):
        if not self.stop.is_set():
            self.stop.set()

        if self.is_alive():
            self.join(3)
            if self.is_alive():
                logger.warning(
                    "Consensus did not shut down within the grace period; terminating it the hard way"
                )
                self.terminate()
        else:
            logger.warning("Consensus shutdown had no effect, the process is already dead")
