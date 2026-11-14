class MarketDataError(Exception):
    """Base class for upstream market-data errors."""


class ProviderUnavailable(MarketDataError):
    """The upstream provider could not be reached or returned an error."""


class ProviderSchemaError(MarketDataError):
    """The provider response did not match the expected contract."""
