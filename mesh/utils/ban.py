import subprocess
from typing import List

from mesh.dht import DHT
from mesh.p2p import PeerID
from mesh.utils.logging import get_logger
from mesh.utils.p2p_utils import get_peers_ips

logger = get_logger(__name__)


def ban_peers(dht: DHT, peer_ids: List[PeerID]):
    peers_info = {
        str(peer.peer_id): {
            "multiaddrs": [str(multiaddr) for multiaddr in peer.addrs],
        }
        for peer in dht.run_coroutine(get_peers_ips)
    }

    # Extract IPs for the specified peer IDs and ban them
    for peer_id in peer_ids:
        peer_id_str = peer_id.to_string()

        # Check if peer_id exists in the peers_info
        if peer_id_str in peers_info:
            multiaddrs = peers_info[peer_id_str]['multiaddrs']

            # Extract all IPv4 addresses from multiaddrs
            ips = [addr.split('/')[2] for addr in multiaddrs if '/ip4/' in addr]

            # Ban each IP
            for ip in ips:
                logger.info(f"Banning IP {ip} for peer {peer_id_str}")
                block_ip(ip)

def unban_peers(dht: DHT, peer_ids: List[PeerID]):
    peers_info = {
        str(peer.peer_id): {
            "multiaddrs": [str(multiaddr) for multiaddr in peer.addrs],
        }
        for peer in dht.run_coroutine(get_peers_ips)
    }

    # Extract IPs for the specified peer IDs and ban them
    for peer_id in peer_ids:
        peer_id_str = peer_id.to_string()

        # Check if peer_id exists in the peers_info
        if peer_id_str in peers_info:
            multiaddrs = peers_info[peer_id_str]['multiaddrs']

            # Extract all IPv4 addresses from multiaddrs
            ips = [addr.split('/')[2] for addr in multiaddrs if '/ip4/' in addr]

            # Ban each IP
            for ip in ips:
                logger.info(f"Banning IP {ip} for peer {peer_id_str}")
                unblock_ip(ip)

def block_ip(ip_address):
    """Block an IP address using UFW firewall"""
    try:
        # Run the ufw command with sudo
        result = subprocess.run(
            ['sudo', 'ufw', 'deny', 'from', ip_address],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully blocked {ip_address}")
        logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to block {ip_address}: {e}")
        logger.error(e.stderr)
        return False

def unblock_ip(ip_address):
    """Unblock an IP address using UFW firewall"""
    try:
        # Check if rule exists first
        check_result = subprocess.run(
            ['sudo', 'ufw', 'status', 'numbered'],
            capture_output=True,
            text=True,
            check=True
        )

        if ip_address not in check_result.stdout:
            logger.info(f"No block rule found for {ip_address}")
            return False

        # Delete the rule
        result = subprocess.run(
            ['sudo', 'ufw', 'delete', 'deny', 'from', ip_address],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully unblocked {ip_address}")
        logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to unblock {ip_address}: {e}")
        logger.error(e.stderr)
        return False
