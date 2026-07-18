"""Fixed exchange-rate adapter."""

from shop.ports.statements.create_monthly_statement import StatementExchangeRates


class FixedExchangeRates(StatementExchangeRates):
    """Convert GBP with deterministic rates suitable for the runnable example."""

    _per_gbp = {"GBP": 1.0, "EUR": 1.17, "USD": 1.35}

    async def convert_from_gbp(self, amount_pence: int, currency: str) -> int:
        try:
            rate = self._per_gbp[currency.upper()]
        except KeyError as error:
            raise ValueError(f"unsupported statement currency: {currency}") from error
        return round(amount_pence * rate)
