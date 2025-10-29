import asyncio
import time
from abc import ABC
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from mesh import PeerID
from mesh.utils.authorizers.auth import AuthorizedRequestBase, AuthorizedResponseBase, AuthorizerBase
from mesh.utils.crypto import Ed25519PrivateKey, RSAPrivateKey, load_public_key_from_bytes
from mesh.utils.logging import get_logger

logger = get_logger(__name__)


class ThreatLevel(Enum):
    """Threat levels for progressive response"""
    NORMAL = 0
    SUSPICIOUS = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_requests_per_second: int = 10
    max_requests_per_minute: int = 100
    max_requests_per_hour: int = 1000
    max_burst: int = 20

    suspicious_threshold: float = 1.5
    blocking_threshold: float = 3.0
    ip_ban_threshold: float = 5.0

    short_window: int = 1
    medium_window: int = 60
    long_window: int = 3600

    temp_block_duration: int = 300
    extended_block_duration: int = 3600

    enable_ip_banning: bool = False  # Disabled by default, requires external DHT integration
    ip_ban_violation_count: int = 10


class RateLimitAuthorizer(AuthorizerBase):
    """
    Rate-limiting authorizer that wraps another authorizer (like SignatureAuthorizer).

    This implements the same AuthorizerBase interface and adds rate limiting on top
    of the underlying authentication mechanism.

    Usage:
        signature_auth = SignatureAuthorizer(private_key)
        rate_limited_auth = RateLimitAuthorizer(
            inner_authorizer=signature_auth,
            config=RateLimitConfig(max_requests_per_second=5)
        )
    """

    def __init__(
        self,
        inner_authorizer: AuthorizerBase,
        config: Optional[RateLimitConfig] = None,
        ip_ban_callback: Optional[callable] = None
    ):
        """
        Args:
            inner_authorizer: The underlying authorizer (e.g., SignatureAuthorizer)
            config: Rate limiting configuration
            ip_ban_callback: Optional callback function to ban IPs, signature: callback(peer_id: PeerID, reason: str)
        """
        self.inner_authorizer = inner_authorizer
        self.config = config or RateLimitConfig()
        self.ip_ban_callback = ip_ban_callback

        # Track requests per peer
        self.peer_requests: Dict[PeerID, deque] = defaultdict(lambda: deque())

        # Threat tracking
        self.peer_threat_levels: Dict[PeerID, ThreatLevel] = defaultdict(lambda: ThreatLevel.NORMAL)
        self.blocked_peers: Dict[PeerID, float] = {}  # peer_id -> unblock_time
        self.violation_counts: Dict[PeerID, int] = defaultdict(int)
        self.ip_banned_peers: set[PeerID] = set()

        # Statistics
        self.total_requests: Dict[PeerID, int] = defaultdict(int)
        self.blocked_requests: Dict[PeerID, int] = defaultdict(int)
        self.threat_escalations: Dict[PeerID, list] = defaultdict(list)

        self._lock = asyncio.Lock()

    @property
    def local_public_key(self):
        """Delegate to inner authorizer if it has this property."""
        if hasattr(self.inner_authorizer, 'local_public_key'):
            return self.inner_authorizer.local_public_key
        return None

    async def sign_request(
        self,
        request: AuthorizedRequestBase,
        service_public_key: Optional[Ed25519PrivateKey | RSAPrivateKey]
    ) -> None:
        """
        Sign a request using the inner authorizer.
        No rate limiting on outgoing requests (we're the client).
        """
        await self.inner_authorizer.sign_request(request, service_public_key)

    async def validate_request(self, request: AuthorizedRequestBase) -> bool:
        """
        Validate an incoming request with rate limiting.

        This is called on the SERVICER side to check if we should accept
        a request from a peer.
        """
        # Extract peer ID from the request's auth info
        try:
            peer_public_key_bytes = request.auth.client_access_token.public_key
            client_public_key = load_public_key_from_bytes(peer_public_key_bytes)
            # Create a pseudo peer_id from public key (you may need to adjust this)
            peer_id = self._public_key_to_peer_id(client_public_key)
        except Exception as e:
            logger.warning(f"Failed to extract peer ID from request: {e}")
            return False

        # Check rate limits FIRST
        is_allowed, reason = await self._check_rate_limit(peer_id)
        if not is_allowed:
            logger.warning(f"Rate limit blocked request from peer: {reason}")
            await self._record_violation(peer_id, reason)
            return False

        # Then validate with inner authorizer
        is_valid = await self.inner_authorizer.validate_request(request)

        if not is_valid:
            # Auth failed - record as suspicious
            await self._record_violation(peer_id, "Authentication failed")
            return False

        return True

    async def sign_response(
        self,
        response: AuthorizedResponseBase,
        request: AuthorizedRequestBase
    ) -> None:
        """
        Sign a response using the inner authorizer.
        No rate limiting on outgoing responses.
        """
        await self.inner_authorizer.sign_response(response, request)

    async def validate_response(
        self,
        response: AuthorizedResponseBase,
        request: AuthorizedRequestBase
    ) -> bool:
        """
        Validate a response using the inner authorizer.
        No rate limiting on incoming responses (we're the client).
        """
        return await self.inner_authorizer.validate_response(response, request)

    # ========================================================================
    # Rate Limiting Implementation
    # ========================================================================

    async def _check_rate_limit(self, peer_id: PeerID) -> tuple[bool, Optional[str]]:
        """Check if request from peer should be allowed based on rate limits."""
        async with self._lock:
            current_time = time.time()

            # Check if IP banned
            if peer_id in self.ip_banned_peers:
                self.blocked_requests[peer_id] += 1
                return False, "Peer is banned at IP level"

            # Check if temporarily blocked
            if peer_id in self.blocked_peers:
                unblock_time = self.blocked_peers[peer_id]
                if current_time < unblock_time:
                    self.blocked_requests[peer_id] += 1
                    remaining = int(unblock_time - current_time)
                    return False, f"Peer blocked for {remaining} more seconds"
                else:
                    del self.blocked_peers[peer_id]
                    logger.info(f"Unblocked peer {peer_id}")

            # Get request history
            requests = self.peer_requests[peer_id]

            # Clean old requests
            cutoff_time = current_time - self.config.long_window
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            # Count requests in time windows
            short_count = sum(1 for t in requests if t > current_time - self.config.short_window)
            medium_count = sum(1 for t in requests if t > current_time - self.config.medium_window)
            long_count = len(requests)

            # Detect threats
            is_threat, reason, threat_level = self._detect_threat(
                peer_id, short_count, medium_count, long_count
            )

            if is_threat:
                await self._handle_threat(peer_id, threat_level, reason)
                return False, reason

            # Record request
            requests.append(current_time)
            self.total_requests[peer_id] += 1

            return True, None

    def _detect_threat(
        self,
        peer_id: PeerID,
        short_count: int,
        medium_count: int,
        long_count: int
    ) -> tuple[bool, Optional[str], ThreatLevel]:
        """Detect threat level based on request patterns."""
        max_rate = self.config.max_requests_per_second

        # CRITICAL: Extreme violation
        if (short_count > max_rate * self.config.ip_ban_threshold or
            self.violation_counts[peer_id] >= self.config.ip_ban_violation_count):
            return True, f"Critical: {short_count} req/s", ThreatLevel.CRITICAL

        # HIGH: Severe violation
        if short_count > max_rate * self.config.blocking_threshold:
            return True, f"Severe: {short_count} req/s", ThreatLevel.HIGH

        # MODERATE: Sustained high rate
        if medium_count >= self.config.max_requests_per_minute:
            return True, f"Exceeded: {medium_count} req/min", ThreatLevel.MODERATE

        if long_count >= self.config.max_requests_per_hour:
            return True, f"Exceeded: {long_count} req/hour", ThreatLevel.MODERATE

        # SUSPICIOUS: Burst
        if short_count >= self.config.max_burst:
            return True, f"Burst: {short_count} req/s", ThreatLevel.SUSPICIOUS

        # SUSPICIOUS: Unusual pattern
        if short_count > max_rate * self.config.suspicious_threshold:
            return True, "Suspicious pattern", ThreatLevel.SUSPICIOUS

        return False, None, ThreatLevel.NORMAL

    async def _handle_threat(self, peer_id: PeerID, threat_level: ThreatLevel, reason: str):
        """Handle detected threat based on severity."""
        current_level = self.peer_threat_levels[peer_id]

        # Escalate if needed
        if threat_level.value > current_level.value:
            self.threat_escalations[peer_id].append((time.time(), current_level, threat_level))
            self.peer_threat_levels[peer_id] = threat_level
            logger.warning(f"Threat escalated for {peer_id}: {current_level.name} -> {threat_level.name}")

        self.violation_counts[peer_id] += 1

        if threat_level == ThreatLevel.SUSPICIOUS:
            logger.warning(f"Suspicious: {peer_id} - {reason}")

        elif threat_level == ThreatLevel.MODERATE:
            self._block_peer(peer_id, self.config.temp_block_duration)
            logger.warning(f"Blocking {peer_id} for {self.config.temp_block_duration}s: {reason}")

        elif threat_level == ThreatLevel.HIGH:
            self._block_peer(peer_id, self.config.extended_block_duration)
            logger.error(f"Extended block {peer_id} for {self.config.extended_block_duration}s: {reason}")

        elif threat_level == ThreatLevel.CRITICAL:
            if self.config.enable_ip_banning and self.ip_ban_callback:
                await self._ban_peer_ip(peer_id, reason)
            else:
                self._block_peer(peer_id, 86400)  # 24 hours
                logger.critical(f"Critical threat {peer_id}: {reason}")

    def _block_peer(self, peer_id: PeerID, duration: int):
        """Block peer temporarily."""
        unblock_time = time.time() + duration
        self.blocked_peers[peer_id] = unblock_time
        logger.warning(f"Blocked {peer_id} for {duration}s")

    async def _ban_peer_ip(self, peer_id: PeerID, reason: str):
        """Ban peer at IP level."""
        if peer_id in self.ip_banned_peers:
            return

        logger.critical(f"IP BANNING {peer_id}: {reason}")
        self.ip_banned_peers.add(peer_id)

        if self.ip_ban_callback:
            try:
                await self.ip_ban_callback(peer_id, reason)
            except Exception as e:
                logger.error(f"IP ban callback failed for {peer_id}: {e}")

    async def _record_violation(self, peer_id: PeerID, reason: str):
        """Record a violation (auth failure, rate limit, etc.)."""
        async with self._lock:
            self.violation_counts[peer_id] += 1

            if self.violation_counts[peer_id] >= 5:
                await self._handle_threat(peer_id, ThreatLevel.SUSPICIOUS, f"Repeated violations: {reason}")

    def _public_key_to_peer_id(self, public_key) -> PeerID:
        """
        Convert public key to PeerID for tracking.
        You may need to adjust this based on how your system identifies peers.
        """
        # Simple approach: use hash of public key bytes as peer identifier
        key_bytes = public_key.to_bytes()
        # You might want to use PeerID.from_base58() or another method
        # This is a placeholder - adjust based on your PeerID implementation
        return PeerID(key_bytes[:20])  # Use first 20 bytes as ID

    # ========================================================================
    # Statistics & Monitoring
    # ========================================================================

    def get_peer_stats(self, peer_id: PeerID) -> dict:
        """Get statistics for a specific peer."""
        requests = self.peer_requests[peer_id]
        current_time = time.time()

        return {
            "peer_id": str(peer_id),
            "threat_level": self.peer_threat_levels[peer_id].name,
            "total_requests": self.total_requests[peer_id],
            "blocked_requests": self.blocked_requests[peer_id],
            "violations": self.violation_counts[peer_id],
            "is_blocked": peer_id in self.blocked_peers,
            "is_ip_banned": peer_id in self.ip_banned_peers,
            "recent_1s": sum(1 for t in requests if t > current_time - 1),
            "recent_1m": sum(1 for t in requests if t > current_time - 60),
            "recent_1h": len(requests),
        }

    def get_all_stats(self) -> dict:
        """Get overall statistics."""
        return {
            "total_peers": len(self.peer_requests),
            "blocked_peers": len(self.blocked_peers),
            "ip_banned_peers": len(self.ip_banned_peers),
            "total_requests": sum(self.total_requests.values()),
            "total_blocked": sum(self.blocked_requests.values()),
            "threat_distribution": {
                level.name: sum(1 for l in self.peer_threat_levels.values() if l == level)  # noqa: E741
                for level in ThreatLevel
            }
        }
