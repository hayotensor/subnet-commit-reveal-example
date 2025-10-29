import asyncio
import functools
import inspect
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Tuple, Union

from mesh.proto.auth_pb2 import AccessToken, RequestAuthInfo, ResponseAuthInfo
from mesh.utils.asyncio import anext, peek_first
from mesh.utils.crypto import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
    KeyType,
    RSAPrivateKey,
    RSAPublicKey,
    load_public_key_from_bytes,
)
from mesh.utils.logging import get_logger
from mesh.utils.timed_storage import TimedStorage, get_dht_time

logger = get_logger(__name__)


class AuthorizedRequestBase:
    """
    Interface for protobufs with the ``RequestAuthInfo auth`` field. Used for type annotations only.
    """

    auth: RequestAuthInfo


class AuthorizedResponseBase:
    """
    Interface for protobufs with the ``ResponseAuthInfo auth`` field. Used for type annotations only.
    """

    auth: ResponseAuthInfo


class AuthorizerBase(ABC):
    @abstractmethod
    async def sign_request(
        self, request: AuthorizedRequestBase, service_public_key: Optional[Ed25519PublicKey | RSAPublicKey]
    ) -> None: ...

    @abstractmethod
    async def validate_request(self, request: AuthorizedRequestBase) -> bool: ...

    @abstractmethod
    async def sign_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> None: ...

    @abstractmethod
    async def validate_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> bool: ...

class SignatureAuthorizer(AuthorizerBase):
    def __init__(self, local_private_key: Ed25519PrivateKey | RSAPrivateKey):
        self._key_type = KeyType.RSA if isinstance(local_private_key, RSAPrivateKey) else KeyType.Ed25519
        self._local_private_key = local_private_key
        self._local_public_key = local_private_key.get_public_key()

        self._local_access_token = None
        self._refresh_lock = asyncio.Lock()

        self._recent_nonces = TimedStorage()

    async def get_token(self) -> AccessToken:
        # Uses the built in template ``AccessToken`` format
        token = AccessToken(
            username='',
            public_key=self._local_public_key.to_bytes(),
            expiration_time=str(datetime.now(timezone.utc) + timedelta(minutes=1)),
        )
        token.signature = self._local_private_key.sign(self._token_to_bytes(token))
        return token

    @staticmethod
    def _token_to_bytes(access_token: AccessToken) -> bytes:
        return f"{access_token.username} {access_token.public_key} {access_token.expiration_time}".encode()

    @property
    def local_public_key(self) -> Ed25519PublicKey | RSAPublicKey:
        return self._local_public_key

    async def sign_request(self, request: AuthorizedRequestBase, service_public_key: Optional[Ed25519PublicKey | RSAPublicKey]) -> None:
        auth = request.auth

        local_access_token = await self.get_token()
        auth.client_access_token.CopyFrom(local_access_token)

        if service_public_key is not None:
            auth.service_public_key = service_public_key.to_bytes()
        auth.time = get_dht_time()

        auth.nonce = secrets.token_bytes(8)

        assert auth.signature == b""
        auth.signature = self._local_private_key.sign(request.SerializeToString())

    _MAX_CLIENT_SERVICER_TIME_DIFF = timedelta(minutes=1)

    async def do_validate_request(self, request: AuthorizedRequestBase) -> Tuple[RSAPublicKey | Ed25519PublicKey, float, bytes, bool]:
        """
        Returns:
            public key, current time, nonce, verified
        """
        auth = request.auth

        client_public_key = load_public_key_from_bytes(auth.client_access_token.public_key)

        signature = auth.signature
        auth.signature = b""
        if not client_public_key.verify(request.SerializeToString(), signature):
            logger.debug("Request has invalid signature")
            return client_public_key, 0.0, auth.nonce, False

        if auth.service_public_key and auth.service_public_key != self._local_public_key.to_bytes():
            logger.debug("Request is generated for a peer with another public key")
            return client_public_key, 0.0, auth.nonce, False

        with self._recent_nonces.freeze():
            current_time = get_dht_time()
            if abs(auth.time - current_time) > self._MAX_CLIENT_SERVICER_TIME_DIFF.total_seconds():
                logger.debug("Clocks are not synchronized or a previous request is replayed again")
                return client_public_key, current_time, auth.nonce, False
            if auth.nonce in self._recent_nonces:
                logger.debug("Previous request is replayed again")
                return client_public_key, current_time, auth.nonce, False

        if auth.nonce in self._recent_nonces:
            logger.debug("Previous request is replayed again")
            return client_public_key, current_time, auth.nonce, False

        return client_public_key, current_time, auth.nonce, True

    async def validate_request(self, request: AuthorizedRequestBase) -> bool:
        _, current_time, nonce, valid = await self.do_validate_request(request)
        if not valid:
            return False

        self._recent_nonces.store(
            nonce, None, current_time + self._MAX_CLIENT_SERVICER_TIME_DIFF.total_seconds() * 3
        )

        return True

    async def sign_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> None:
        auth = response.auth

        # auth.service_access_token.CopyFrom(self._local_access_token)
        local_access_token = await self.get_token()
        auth.service_access_token.CopyFrom(local_access_token)
        auth.nonce = request.auth.nonce

        assert auth.signature == b""
        auth.signature = self._local_private_key.sign(response.SerializeToString())

    async def do_validate_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> Tuple[RSAPublicKey | Ed25519PublicKey, bool]:
        auth = response.auth

        service_public_key = load_public_key_from_bytes(auth.service_access_token.public_key)

        signature = auth.signature
        auth.signature = b""
        if not service_public_key.verify(response.SerializeToString(), signature):
            logger.debug("Response has invalid signature")
            return service_public_key, False

        if auth.nonce != request.auth.nonce:
            logger.debug("Response is generated for another request")
            return service_public_key, False

        return service_public_key, True

    async def validate_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> bool:
        _, valid = await self.do_validate_response(response, request)
        return valid


class AuthRole(Enum):
    CLIENT = 0
    SERVICER = 1


class AuthRPCWrapper:
    """
    An authentication wrapper around peer stubs.

    This can be used as an authentication mechanism for all peer communications or different types of communication.

    Example: The AuthorizerBase can be used as a proof-of-stake mechanism connected to Hypertensor to ensure all nodes
    that communicate with each other are staked on-chain. For things such as entering the DHT or calling for inference.
    """
    def __init__(
        self,
        stub,
        role: AuthRole,
        authorizer: Optional[AuthorizerBase],
        service_public_key: Optional[RSAPublicKey | Ed25519PublicKey] = None,
    ):
        self._stub = stub
        self._role = role
        self._authorizer = authorizer
        self._service_public_key = service_public_key

    def __getattribute__(self, name: str):
        if not name.startswith("rpc_"):
            return object.__getattribute__(self, name)

        method = getattr(self._stub, name)

        @functools.wraps(method)
        async def wrapped_rpc(request: AuthorizedRequestBase, *args, **kwargs):
            if self._authorizer is not None:
                if self._role == AuthRole.CLIENT:
                    await self._authorizer.sign_request(request, self._service_public_key)
                elif self._role == AuthRole.SERVICER:
                    if not await self._authorizer.validate_request(request):
                        return None

            response = await method(request, *args, **kwargs)

            if self._authorizer is not None:
                if self._role == AuthRole.SERVICER:
                    await self._authorizer.sign_response(response, request)
                elif self._role == AuthRole.CLIENT:
                    if not await self._authorizer.validate_response(response, request):
                        return None

            return response

        return wrapped_rpc

class AuthRPCWrapperStreamer:
    def __init__(
        self,
        stub,
        role: AuthRole,
        authorizer: Optional[AuthorizerBase],
        service_public_key: Optional[RSAPublicKey | Ed25519PublicKey] = None
    ):
        self._stub = stub
        self._role = role
        self._authorizer = authorizer
        self._service_public_key = service_public_key

    def __getattribute__(self, name: str):
        if not name.startswith("rpc_"):
            return object.__getattribute__(self, name)

        stub = object.__getattribute__(self, "_stub")
        method = getattr(stub, name)
        role = object.__getattribute__(self, "_role")
        authorizer = object.__getattribute__(self, "_authorizer")
        service_public_key = object.__getattribute__(self, "_service_public_key")

        if inspect.isasyncgenfunction(method):
            @functools.wraps(method)
            async def wrapped_stream_rpc(request, *args, **kwargs):
                if authorizer:
                    if role == AuthRole.CLIENT:
                        await authorizer.sign_request(request, service_public_key)
                    elif role == AuthRole.SERVICER:
                        if not await authorizer.validate_request(request):
                            return

                async for response in method(request, *args, **kwargs):
                    if authorizer:
                        if role == AuthRole.SERVICER:
                            await authorizer.sign_response(response, request)
                        elif role == AuthRole.CLIENT:
                            if not await authorizer.validate_response(response, request):
                                continue

                    yield response

            return wrapped_stream_rpc
        else:
            @functools.wraps(method)
            async def wrapped_unary_rpc(request, *args, **kwargs):
                if authorizer:
                    if role == AuthRole.CLIENT:
                        await authorizer.sign_request(request, service_public_key)
                    elif role == AuthRole.SERVICER:
                        if not await authorizer.validate_request(request):
                            return None

                response = await method(request, *args, **kwargs)

                if authorizer:
                    if role == AuthRole.SERVICER:
                        await authorizer.sign_response(response, request)
                    elif role == AuthRole.CLIENT:
                        if inspect.isasyncgen(response):
                            # Only validate the first response in the async generator
                            # The other way to accomplish this is to use `async_tee(response)`
                            # to get a copy of the consumer but with thousands of results
                            # it will buffer the entire response into memory
                            """
                            # gen1, gen2 = async_tee(response)
                            # async for r in gen2:
                            #     if not await authorizer.validate_response(r, request):
                            #         return None
                            # return gen1
                            """
                            first, full_gen = await peek_first(response)
                            if not await authorizer.validate_response(first, request):
                                return None
                            return full_gen
                        else:
                            if not await authorizer.validate_response(response, request):
                                return None

                return response

            return wrapped_unary_rpc
