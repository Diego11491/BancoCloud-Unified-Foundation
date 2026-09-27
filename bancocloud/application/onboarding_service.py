from bancocloud.domain.onboarding import normalize_region


class OnboardingService:
    def __init__(self, repository): self.repository = repository
    def onboard(self, region: str) -> dict:
        return self.repository.create(normalize_region(region))
