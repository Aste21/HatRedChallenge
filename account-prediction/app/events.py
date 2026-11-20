"""Events: small, checked descriptions of how news changes future cash flow.

| type          | meaning                                                   | fields                                        |
|---------------|-----------------------------------------------------------|-----------------------------------------------|
| shift_amount  | a scheduled payment changes by x % from a date            | stream, from, change_pct                      |
| one_off       | a single extra payment or receipt                         | date, amount (negative = money out)           |
| scale         | variable cash runs at a different level, with uncertainty | flow (sales/costs), from, to?, factor_mean, factor_sd |
| closure       | the business is shut: no variable cash; scheduled payments still go out | from, to                    |

Every event has a certainty: "official" (a confirmed change with a date and a number) or "assumption"
(an estimate). "sales" is variable money in, "costs" is variable money out.

The same rules check events from the LLM and events sent to /forecast, so nothing unchecked reaches the simulation.
"""
import datetime as dt
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator, model_validator

MAX_ONE_OFF_EUR = 20_000


class _Event(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    certainty: Literal["official", "assumption"] = "assumption"
    why: str = ""

    @field_validator("certainty", mode="before")
    @classmethod
    def _only_official_is_official(cls, v):
        """Anything not clearly 'official' is treated as an assumption."""
        return "official" if v == "official" else "assumption"


class ShiftAmount(_Event):
    type: Literal["shift_amount"]
    stream: str = Field(description="name of a scheduled payment")
    from_: dt.date = Field(alias="from")
    change_pct: float = Field(ge=-50, le=100)


class OneOff(_Event):
    type: Literal["one_off"]
    date: dt.date
    amount: float = Field(ge=-MAX_ONE_OFF_EUR, le=MAX_ONE_OFF_EUR, description="EUR, negative = money out")


class Scale(_Event):
    type: Literal["scale"]
    flow: Literal["sales", "costs"]
    from_: dt.date = Field(alias="from")
    to: dt.date | None = None
    factor_mean: float = Field(ge=0.5, le=1.5)
    factor_sd: float = Field(ge=0, le=0.2)

    @model_validator(mode="after")
    def _to_after_from(self):
        if self.to is not None and self.to < self.from_:
            raise ValueError("'to' is before 'from'")
        return self


class Closure(_Event):
    type: Literal["closure"]
    from_: dt.date = Field(alias="from")
    to: dt.date

    @model_validator(mode="after")
    def _to_after_from(self):
        if self.to < self.from_:
            raise ValueError("'to' is before 'from'")
        return self


Event = Annotated[Union[ShiftAmount, OneOff, Scale, Closure], Field(discriminator="type")]
_event_adapter = TypeAdapter(Event)


def parse_event(raw: dict) -> Event:
    """Validate one raw dict (e.g. from the LLM). Raises ValueError with a short reason."""
    try:
        return _event_adapter.validate_python(raw)
    except ValidationError as exc:
        err = exc.errors()[0]
        where = ".".join(str(x) for x in err["loc"])
        raise ValueError(f"{where}: {err['msg']}" if where else err["msg"]) from None


def unknown_streams(events: list[Event], stream_names: set[str]) -> list[str]:
    """Names used by shift_amount events that are not scheduled payments of this account."""
    return [e.stream for e in events if isinstance(e, ShiftAmount) and e.stream not in stream_names]
