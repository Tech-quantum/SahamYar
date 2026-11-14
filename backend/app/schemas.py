from pydantic import BaseModel, Field


class StockSearchItem(BaseModel):
    ins_code: str | None = None
    symbol: str | None = None
    name: str | None = None
    isin: str | None = None
    market_flow: int | None = None
    market: str | None = None
    raw: dict = Field(default_factory=dict)


class StockSearchResponse(BaseModel):
    source: str = "TSETMC"
    query: str
    count: int
    items: list[StockSearchItem]
    retrieved_at: str
