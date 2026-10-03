"""RePEc identifiers remain actionable when API access is not provisioned."""
from .base import ProviderFailure
from ..models import AttemptOutcome


class Repec:
    name = "repec"

    async def discover(self, paper, context):
        if paper.identifier_kind == "repec":
            raise ProviderFailure(AttemptOutcome("needs_credentials", self.name, "repec_api_access_not_provisioned"))
        return []
