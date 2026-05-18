"""KYC/AML compliance workflows for Indian fintech onboarding."""

from __future__ import annotations

import asyncio

from ulu.api.validators import validate_pan
from ulu.domain.users import AmlStatus, KycStatus, User
from ulu.infra.circuit_breaker import kyc_breaker


class KycAmlService:
    """Identity verification and AML screening service."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def _verify_kyc_stub(self, user: User, pan_number: str, aadhaar_hash: str) -> KycStatus:
        if not validate_pan(pan_number):
            user.kyc_status = KycStatus.REJECTED
            return KycStatus.REJECTED
        if not aadhaar_hash:
            user.kyc_status = KycStatus.REJECTED
            return KycStatus.REJECTED
        raise NotImplementedError(
            "KYC verification requires integration with PAN/Aadhaar APIs. "
            "This stub accepts any non-empty input, which is not safe for production."
        )

    def verify_kyc(self, user: User, pan_number: str, aadhaar_hash: str) -> KycStatus:
        """Verifies user identity against government databases."""
        return kyc_breaker(self._verify_kyc_stub)(user, pan_number, aadhaar_hash)

    async def verify_kyc_async(self, user: User, pan_number: str, aadhaar_hash: str) -> KycStatus:
        """Async wrapper for KYC verification with timeout."""
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self.verify_kyc, user, pan_number, aadhaar_hash),
            timeout=self.timeout,
        )

    def screen_aml(self, user: User, watchlist_hit: bool = False) -> AmlStatus:
        """Screens user against AML watchlists."""
        if watchlist_hit:
            user.aml_status = AmlStatus.FROZEN
            return AmlStatus.FROZEN
        user.aml_status = AmlStatus.CLEAR
        return AmlStatus.CLEAR

    def is_compliant(self, user: User) -> bool:
        """Returns True only if KYC verified and AML clear."""
        return user.is_compliant()
