"""
Utilities for declaring and retrieving active model layers using a shared DHT.
"""
from __future__ import annotations

import math
from functools import partial
from typing import Any, Dict, List, Optional, Union

from mesh.dht import DHT, DHTNode, DHTValue
from mesh.dht.crypto import SignatureValidator
from mesh.dht.routing import DHTKey
from mesh.dht.validation import RecordValidatorBase
from mesh.p2p import PeerID
from mesh.utils import DHTExpiration, MPFuture, get_dht_time, get_logger
from mesh.utils.data_structures import NodeHeartbeat, RemoteInfo, RemoteModuleInfo, ServerInfo, ServerState
from mesh.utils.key import (
    extract_peer_id_from_record_validator,
)

logger = get_logger(__name__)

def declare_node(
    dht: DHT,
    key: DHTKey,
    server_info: ServerInfo,
    expiration_time: DHTExpiration,
    wait: bool = True,
    record_validator: Optional[RecordValidatorBase] = None,
):
    """
    Declare your node; update timestamps if declared previously

    :param key: key to store under
    :param wait: if True, awaits for declaration to finish, otherwise runs in background
    :param throughput: specify your performance in terms of compute throughput
    :param expiration_time: declared modules will be visible for this many seconds
    :returns: if wait, returns store status for every key (True = store succeeded, False = store rejected)
    """
    subkey = dht.peer_id.to_base58().encode() + record_validator.local_public_key
    return dht.run_coroutine(
        partial(
            _store_node,
            key=key,
            subkey=dht.peer_id.to_base58(),
            server_info=server_info,
            expiration_time=expiration_time
        ),
        return_future=not wait,
    )

async def _store_node(
    dht: DHT,
    node: DHTNode,
    key: DHTKey,
    subkey: Any,
    server_info: ServerInfo,
    expiration_time: DHTExpiration,
) -> Dict[DHTKey, bool]:
    return await node.store(
        key=key,
        subkey=subkey,
        value=server_info.to_tuple(),
        expiration_time=expiration_time,
        num_workers=32,
    )

def get_node_infos(
    dht: DHT,
    uid: Any, # type: ignore
    expiration_time: Optional[DHTExpiration] = None,
    *,
    latest: bool = False,
    return_future: bool = False,
) -> Union[List[RemoteModuleInfo], MPFuture]:
    return dht.run_coroutine(
        partial(
            _get_node_infos,
            uid=uid,
            expiration_time=expiration_time,
            latest=latest,
        ),
        return_future=return_future,
    )

async def _get_node_infos(
    dht: DHT,
    node: DHTNode,
    uid: Any, # type: ignore
    expiration_time: Optional[DHTExpiration],
    latest: bool,
) -> List[RemoteModuleInfo]:
    if latest:
        assert expiration_time is None, "You should define either `expiration_time` or `latest`, not both"
        expiration_time = math.inf
    elif expiration_time is None:
        expiration_time = get_dht_time()
    num_workers = 1 if dht.num_workers is None else 1
    found: Dict[Any, DHTValue] = await node.get_many([uid], expiration_time, num_workers=num_workers) # type: ignore

    if found[uid] is None:
        return []
    peers = []
    inner_dict = found[uid].value

    modules: List[RemoteModuleInfo] = []
    for subkey, values in inner_dict.items():
        # If using record validator
        # caller_peer_id = extract_rsa_peer_id_from_ssh(subkey)

        peers.append(PeerID.from_base58(subkey))
        server_info = ServerInfo.from_tuple(values.value)

        modules.append(
            RemoteModuleInfo(
                peer_id=PeerID.from_base58(subkey),
                server=server_info
            )
        )
    return modules

def store_data(
    dht: DHT,
    key: DHTKey,
    subkey: Optional[Any],
    data: Any,
    expiration_time: DHTExpiration,
    wait: bool = True,
):
    return dht.run_coroutine(
        partial(_store_data, key=key, subkey=subkey, value=data, expiration_time=expiration_time),
        return_future=False,
    )

async def _store_data(
    dht: DHT,
    node: DHTNode,
    key: Any,
    subkey: Optional[Any],
    value: Any,
    expiration_time: DHTExpiration,
) -> Dict[DHTKey, bool]:
    return await node.store(
        key=key,
        subkey=subkey,
        value=value,
        expiration_time=expiration_time,
        num_workers=32,
    )

def get_many_data(
    dht: DHT,
    uid: Any,
    expiration_time: Optional[DHTExpiration] = None,
    *,
    latest: bool = False,
    return_future: bool = False,
):
    return dht.run_coroutine(
        partial(
            _get_data,
            key=uid,
            expiration_time=expiration_time,
            latest=latest,
        ),
        return_future=return_future,
    )

async def _get_data(
    dht: DHT,
    node: DHTNode,
    key: Any,
    expiration_time: Optional[DHTExpiration],
    latest: bool,
) -> Any:
    found = await node.get_many([key], expiration_time)
    return found


"""
Validated entries requiring signing and ownership
If using this, ensure to use a predicate validator that
only allows max expiration entries so the records don't
last forever
"""

"""
RSA
"""
def declare_node_sig(
    dht: DHT,
    key: DHTKey,
    server_info: ServerInfo,
    expiration_time: DHTExpiration,
    wait: bool = True,
    record_validator: Optional[SignatureValidator] = None,
):
    """
    Declare your node; update timestamps if declared previously

    :param key: key to store under
    :param wait: if True, awaits for declaration to finish, otherwise runs in background
    :param throughput: specify your performance in terms of compute throughput
    :param expiration_time: declared modules will be visible for this many seconds
    :returns: if wait, returns store status for every key (True = store succeeded, False = store rejected)
    """
    return dht.run_coroutine(
        partial(
            _declare_declare_node_sig,
            key=key,
            server_info=server_info,
            expiration_time=expiration_time,
            record_validator=record_validator
        ),
        return_future=not wait,
    )

async def _declare_declare_node_sig(
    dht: DHT,
    node: DHTNode,
    key: DHTKey,
    server_info: ServerInfo,
    expiration_time: DHTExpiration,
    record_validator: Optional[SignatureValidator] = None,
) -> Dict[Any, bool]:
    subkey = dht.peer_id.to_base58() if record_validator is None else dht.peer_id.to_base58().encode() + record_validator.local_public_key

    return await node.store(
        key=key,
        subkey=subkey,
        value=server_info.to_tuple(),
        expiration_time=expiration_time,
        num_workers=32,
    )

def get_node_infos_sig(
    dht: DHT,
    uid: Any,
    expiration_time: Optional[DHTExpiration] = None,
    *,
    latest: bool = False,
    return_future: bool = False,
    record_validator: Optional[SignatureValidator] = None,
) -> Union[List[RemoteModuleInfo], MPFuture]:
    return dht.run_coroutine(
        partial(
            _get_node_infos_sig,
            uid=uid,
            expiration_time=expiration_time,
            latest=latest,
        ),
        return_future=return_future,
    )

async def _get_node_infos_sig(
    dht: DHT,
    node: DHTNode,
    uid: Any,
    expiration_time: Optional[DHTExpiration],
    latest: bool,
    record_validator: Optional[SignatureValidator] = None,
) -> List[RemoteModuleInfo]:
    if latest:
        assert expiration_time is None, "You should define either `expiration_time` or `latest`, not both"
        expiration_time = math.inf
    elif expiration_time is None:
        expiration_time = get_dht_time()
    num_workers = 1 if dht.num_workers is None else 1
    found: Dict[Any, DHTValue] = await node.get_many([uid], expiration_time, num_workers=num_workers)

    if found[uid] is None:
        return []
    peers = []
    inner_dict = found[uid].value

    modules: List[RemoteModuleInfo] = []
    for subkey, values in inner_dict.items():
        caller_peer_id = extract_peer_id_from_record_validator(subkey)
        peers.append(caller_peer_id)
        server_info = ServerInfo.from_tuple(values.value)

        modules.append(
            RemoteModuleInfo(
                peer_id=caller_peer_id,
                server=server_info
            )
        )

    return modules

def get_node_heartbeats(
    dht: DHT,
    uid: Any,
    expiration_time: Optional[DHTExpiration] = None,
    *,
    latest: bool = False,
    return_future: bool = False,
    record_validator: Optional[SignatureValidator] = None,
) -> Union[List[RemoteModuleInfo], MPFuture]:
    return dht.run_coroutine(
        partial(
            _get_node_heartbeats,
            uid=uid,
            expiration_time=expiration_time,
            latest=latest,
        ),
        return_future=return_future,
    )

async def _get_node_heartbeats(
    dht: DHT,
    node: DHTNode,
    uid: Any,
    expiration_time: Optional[DHTExpiration],
    latest: bool,
    record_validator: Optional[SignatureValidator] = None,
) -> List[NodeHeartbeat]:
    if latest:
        assert expiration_time is None, "You should define either `expiration_time` or `latest`, not both"
        expiration_time = math.inf
    elif expiration_time is None:
        expiration_time = get_dht_time()
    num_workers = 1 if dht.num_workers is None else 1
    found: Dict[Any, DHTValue] = await node.get_many([uid], expiration_time, num_workers=num_workers)

    if found[uid] is None:
        return []
    peers = []
    inner_dict = found[uid].value

    modules: List[NodeHeartbeat] = []
    for subkey, values in inner_dict.items():
        caller_peer_id = extract_peer_id_from_record_validator(subkey)
        peers.append(caller_peer_id)
        server_info = ServerInfo.from_tuple(values.value)

        modules.append(
            NodeHeartbeat(
                peer_id=caller_peer_id,
                server=server_info,
                expiration_time=values.expiration_time
            )
        )

    return modules

"""
Get routing table, used for testing

If you want to force update the routing table, see how it's
done in `mesh_cli/run_dht.py`
"""
def get_routing_table(
    dht: DHT,
    *,
    return_future: bool = False,
):
    return dht.run_coroutine(
        partial(
            _get_routing_table,
        ),
        return_future=return_future,
    )

async def _get_routing_table(
    dht: DHT,
    node: DHTNode,
):
    return node.protocol.routing_table


def sort_peers(module_infos: List[RemoteModuleInfo], *, min_state: ServerState) -> Dict[PeerID, RemoteInfo]:
    spans = {}
    for _, info in enumerate(module_infos):
        if info.server.state.value < min_state.value:
            continue

    return spans
