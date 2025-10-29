from typing import Optional

from mesh.utils.authorizers.auth import (
    AuthorizedRequestBase,
    AuthorizedResponseBase,
    AuthorizerBase,
    SignatureAuthorizer,
)
from mesh.utils.crypto import (
    Ed25519PublicKey,
    RSAPublicKey,
)
from mesh.utils.logging import get_logger
from mesh.utils.proof_of_stake import ProofOfStake

logger = get_logger(__name__)

class ProofOfStakeAuthorizer(AuthorizerBase):
    def __init__(
        self,
        signature_authorizer: SignatureAuthorizer,
        pos: ProofOfStake
    ):
        super().__init__()
        self.signature_authorizer = signature_authorizer
        self.pos = pos

    async def sign_request(
        self,
        request: AuthorizedRequestBase,
        service_public_key: Optional[Ed25519PublicKey | RSAPublicKey]
    ) -> None:
        await self.signature_authorizer.sign_request(request, service_public_key)

    async def validate_request(self, request: AuthorizedRequestBase) -> bool:
        client_public_key, current_time, nonce, valid = await self.signature_authorizer.do_validate_request(request)
        if not valid:
            return False

        # Verify proof of stake
        try:
            proof_of_stake = self.pos.proof_of_stake(client_public_key)
            if not proof_of_stake:
                return False
        except Exception as e:
            logger.debug(f"Proof of stake failed, validate_request={e}", exc_info=True)
            return False

        self.signature_authorizer._recent_nonces.store(
            nonce, None, current_time + self.signature_authorizer._MAX_CLIENT_SERVICER_TIME_DIFF.total_seconds() * 3
        )

        return True

    async def sign_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> None:
        await self.signature_authorizer.sign_response(response, request)

    async def validate_response(self, response: AuthorizedResponseBase, request: AuthorizedRequestBase) -> bool:
        service_public_key, valid = await self.signature_authorizer.do_validate_response(response, request)
        if not valid:
            return False

        # Verify proof of stake
        try:
            proof_of_stake = self.pos.proof_of_stake(service_public_key)
            if not proof_of_stake:
                return False
        except Exception as e:
            logger.debug(f"Proof of stake failed, validate_response={e}", exc_info=True)
            return False

        return True
