from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from mesh.proto import dht_pb2
from mesh.proto.auth_pb2 import AccessToken
from mesh.utils.authorizers.auth import AuthRole, AuthRPCWrapper, SignatureAuthorizer
from mesh.utils.crypto import Ed25519PrivateKey, RSAPrivateKey
from mesh.utils.logging import get_logger

logger = get_logger(__name__)

# pytest tests/test_auth_rsa.py -rP

class MockAuthorizer(SignatureAuthorizer):
    _authority_private_key = None
    _authority_public_key = None

    def __init__(self, local_private_key: Optional[RSAPrivateKey], username: str = "mock"):
        super().__init__(local_private_key)

        self._username = username
        self._authority_public_key = None

    async def get_token(self) -> AccessToken:
        if MockAuthorizer._authority_private_key is None:
            MockAuthorizer._authority_private_key = RSAPrivateKey()

        self._authority_public_key = MockAuthorizer._authority_private_key.get_public_key()

        now = datetime.now(timezone.utc)
        expiration = now + timedelta(minutes=1)

        token = AccessToken(
            username=self._username,
            public_key=self.local_public_key.to_bytes(),
            expiration_time=str(expiration),
        )
        token.signature = MockAuthorizer._authority_private_key.sign(self._token_to_bytes(token))
        return token

    def is_token_valid(self, access_token: AccessToken) -> bool:
        data = self._token_to_bytes(access_token)

        if not self._authority_public_key.verify(data, access_token.signature):
            logger.exception("Access token has invalid signature")
            return False

        try:
            expiration_time = datetime.fromisoformat(access_token.expiration_time)
        except ValueError:
            logger.exception(
                f"datetime.fromisoformat() failed to parse expiration time: {access_token.expiration_time}"
            )
            return False

        if expiration_time.tzinfo is None:
            logger.warning("Expiration time was naive; assuming UTC")
            expiration_time = expiration_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if expiration_time < now:
            logger.exception("Access token has expired")
            return False

        return True

    _MAX_LATENCY = timedelta(minutes=1)

    def does_token_need_refreshing(self, access_token: AccessToken) -> bool:
        try:
            expiration_time = datetime.fromisoformat(access_token.expiration_time)
        except ValueError:
            return True

        if expiration_time.tzinfo is None:
            expiration_time = expiration_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        return expiration_time < now + self._MAX_LATENCY

    @staticmethod
    def _token_to_bytes(access_token: AccessToken) -> bytes:
        return f"{access_token.username} {access_token.public_key} {access_token.expiration_time}".encode()

# pytest tests/test_auth.py::test_valid_request_and_response -rP

@pytest.mark.asyncio
async def test_valid_request_and_response():
    client_authorizer = MockAuthorizer(RSAPrivateKey())
    service_authorizer = MockAuthorizer(Ed25519PrivateKey())

    request = dht_pb2.PingRequest()
    request.peer.node_id = b"ping"
    await client_authorizer.sign_request(request, service_authorizer.local_public_key)
    assert await service_authorizer.validate_request(request)

    response = dht_pb2.PingResponse()
    response.peer.node_id = b"pong"
    await service_authorizer.sign_response(response, request)
    assert await client_authorizer.validate_response(response, request)

# pytest tests/test_auth.py::test_invalid_access_token -rP

@pytest.mark.asyncio
async def test_invalid_access_token():
    client_authorizer = MockAuthorizer(RSAPrivateKey())
    service_authorizer = MockAuthorizer(Ed25519PrivateKey())

    request = dht_pb2.PingRequest()
    request.peer.node_id = b"ping"
    await client_authorizer.sign_request(request, service_authorizer.local_public_key)

    # Break the access token signature
    request.auth.client_access_token.signature = b"broken"

    assert not await service_authorizer.validate_request(request)

    response = dht_pb2.PingResponse()
    response.peer.node_id = b"pong"
    await service_authorizer.sign_response(response, request)

    # Break the access token signature
    response.auth.service_access_token.signature = b"broken"

    assert not await client_authorizer.validate_response(response, request)

# pytest tests/test_auth.py::test_invalid_signatures -rP

@pytest.mark.asyncio
async def test_invalid_signatures():
    client_authorizer = MockAuthorizer(RSAPrivateKey())
    service_authorizer = MockAuthorizer(Ed25519PrivateKey())

    request = dht_pb2.PingRequest()
    request.peer.node_id = b"true-ping"
    await client_authorizer.sign_request(request, service_authorizer.local_public_key)

    # A man-in-the-middle attacker changes the request content
    request.peer.node_id = b"fake-ping"

    assert not await service_authorizer.validate_request(request)

    response = dht_pb2.PingResponse()
    response.peer.node_id = b"true-pong"
    await service_authorizer.sign_response(response, request)

    # A man-in-the-middle attacker changes the response content
    response.peer.node_id = b"fake-pong"

    assert not await client_authorizer.validate_response(response, request)

# pytest tests/test_auth.py::test_auth_rpc_wrapper -rP

@pytest.mark.asyncio
async def test_auth_rpc_wrapper():
    class Servicer:
        async def rpc_increment(self, request: dht_pb2.PingRequest) -> dht_pb2.PingResponse:
            assert request.peer.node_id == b"ping"
            assert request.auth.client_access_token.username == "alice"

            response = dht_pb2.PingResponse()
            response.peer.node_id = b"pong"
            return response

    class Client:
        def __init__(self, servicer: Servicer):
            self._servicer = servicer

        async def rpc_increment(self, request: dht_pb2.PingRequest) -> dht_pb2.PingResponse:
            return await self._servicer.rpc_increment(request)

    servicer = AuthRPCWrapper(Servicer(), AuthRole.SERVICER, MockAuthorizer(Ed25519PrivateKey(), "bob"))
    client = AuthRPCWrapper(Client(servicer), AuthRole.CLIENT, MockAuthorizer(RSAPrivateKey(), "alice"))

    request = dht_pb2.PingRequest()
    request.peer.node_id = b"ping"

    response = await client.rpc_increment(request)

    assert response.peer.node_id == b"pong"
    assert response.auth.service_access_token.username == "bob"
