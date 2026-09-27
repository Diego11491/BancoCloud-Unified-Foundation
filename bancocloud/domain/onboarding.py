class OnboardingError(ValueError):
    pass


def normalize_region(region: str) -> str:
    value = region.strip()
    if not 2 <= len(value) <= 50:
        raise OnboardingError("Region must be between 2 and 50 characters")
    return value
