import json
import logging
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

ChartMetric = Literal[
    "balance",
    "money_in",
    "money_out",
    "net_result",
    "payroll",
    "spending_by_category",
    "takings_by_weekday",
    "payroll_by_employee",
]
ChartType = Literal["line", "bar", "area"]
ChartGranularity = Literal["day", "week", "month"]

# These metrics are a breakdown, not a time series: shown alone, as horizontal bars, one bar per item.
CATEGORY_METRICS: tuple[ChartMetric, ...] = (
    "spending_by_category",
    "takings_by_weekday",
    "payroll_by_employee",
)

# Breakdowns computed for the chosen months; the others always cover the whole statement.
PERIOD_CATEGORY_METRICS: tuple[ChartMetric, ...] = ("payroll_by_employee",)

METRIC_NAMES: dict[str, str] = {
    "balance": "balance",
    "money_in": "money in",
    "money_out": "money out",
    "net_result": "net result",
    "payroll": "net payroll",
    "spending_by_category": "money out by category",
    "takings_by_weekday": "average card takings by weekday",
    "payroll_by_employee": "total net pay per employee",
}

CHART_TOOL_NAME = "create_chart"

CHART_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": CHART_TOOL_NAME,
        "description": (
            "Show the owner an interactive chart of their bank account, including staff payroll. The app "
            "computes all figures from the bank statement; you only choose what to show. Use it whenever "
            "the owner asks for a chart, graph, plot or visual comparison."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short chart title, at most 8 words."},
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": list(ChartMetric.__args__),  # type: ignore[attr-defined]
                    },
                    "description": (
                        "1 to 3 values over time: balance (account balance at the end of each period), "
                        "money_in, money_out, net_result (money in minus money out), payroll (all net "
                        "salaries paid in each period; use it for payroll or staff costs per month or over "
                        "time). Or exactly one breakdown: spending_by_category (money out by category), "
                        "takings_by_weekday (average card takings per weekday), payroll_by_employee (one "
                        "bar per staff member: total net pay over the chosen months; only when the owner "
                        "asks per person, per employee or who earns what)."
                    ),
                },
                "chart_type": {"type": "string", "enum": list(ChartType.__args__)},  # type: ignore[attr-defined]
                "granularity": {
                    "type": "string",
                    "enum": list(ChartGranularity.__args__),  # type: ignore[attr-defined]
                    "description": "One point or bar per day, week or month.",
                },
                "start_month": {"type": "string", "description": "First month shown, YYYY-MM. Omit for all."},
                "end_month": {"type": "string", "description": "Last month shown, YYYY-MM. Omit for all."},
            },
            "required": ["title", "metrics"],
        },
    },
}

CHART_PROMPT = (
    f"When the owner asks for a chart, graph or plot, call the {CHART_TOOL_NAME} tool. "
    "Never draw charts with text, tables of made-up numbers or code."
)

STATEMENT_PERIOD_PROMPT = (
    "The bank statement covers {first_day} to {last_day}; chart months must lie in that period. "
    "Unless the owner names a year, months like 'June' mean the one in this period."
)


class StatementPeriod(BaseModel):
    """First and last day of the bank statement the charts are computed from."""

    first_day: date
    last_day: date


class ChartSpec(BaseModel):
    """What a chart shows; the frontend computes every figure from the account's bank statement."""

    title: str = Field(min_length=1, max_length=80)
    metrics: list[ChartMetric] = Field(min_length=1, max_length=3)
    chart_type: ChartType = "bar"
    granularity: ChartGranularity = "month"
    start_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    @field_validator("title", mode="before")
    @classmethod
    def _shorten_title(cls, title: Any) -> Any:
        """Trim the title the model wrote so a slightly long one is still accepted.

        Args:
            title: Raw title value.

        Returns:
            The trimmed title, or the value unchanged when it is not a string.
        """
        return " ".join(title.split())[:80] if isinstance(title, str) else title

    @field_validator("metrics", mode="before")
    @classmethod
    def _keep_known_metrics(cls, metrics: Any) -> Any:
        """Accept a single metric given as a plain string and drop metrics the app cannot compute.

        Args:
            metrics: Raw metrics value.

        Returns:
            The known metrics without duplicates, in the given order (empty, and so rejected, if none).
        """
        if isinstance(metrics, str):
            metrics = [metrics]
        if isinstance(metrics, list):
            known = ChartMetric.__args__  # type: ignore[attr-defined]
            return list(dict.fromkeys(metric for metric in metrics if metric in known))
        return metrics

    @field_validator("chart_type", mode="before")
    @classmethod
    def _default_chart_type(cls, chart_type: Any) -> Any:
        """Draw bars when the model asks for a style the app does not offer (e.g. a pie chart).

        Args:
            chart_type: Raw chart type value.

        Returns:
            The chart type, or `"bar"` when it is not supported.
        """
        return chart_type if chart_type in ChartType.__args__ else "bar"  # type: ignore[attr-defined]

    @field_validator("granularity", mode="before")
    @classmethod
    def _default_granularity(cls, granularity: Any) -> Any:
        """Group by month when the model asks for a grouping the app does not offer.

        Args:
            granularity: Raw granularity value.

        Returns:
            The granularity, or `"month"` when it is not supported.
        """
        return granularity if granularity in ChartGranularity.__args__ else "month"  # type: ignore[attr-defined]

    @field_validator("start_month", "end_month", mode="before")
    @classmethod
    def _drop_unusable_month(cls, month: Any) -> Any:
        """Treat an empty or malformed month as "not given", so the chart covers the whole period.

        Args:
            month: Raw month value.

        Returns:
            The month in `YYYY-MM` form (a full date is cut to its month), or `None`.
        """
        if not isinstance(month, str):
            return None
        candidate = month.strip()[:7]
        return candidate if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", candidate) else None

    @model_validator(mode="after")
    def _make_consistent(self) -> "ChartSpec":
        """Keep a breakdown alone, drop months a breakdown cannot use and order the date range.

        Returns:
            The adjusted chart specification.
        """
        breakdown = next((metric for metric in self.metrics if metric in CATEGORY_METRICS), None)
        if breakdown is not None:
            self.metrics = [breakdown]
            self.chart_type = "bar"
            if breakdown not in PERIOD_CATEGORY_METRICS:
                self.start_month = self.end_month = None
        if self.start_month and self.end_month and self.start_month > self.end_month:
            self.start_month, self.end_month = self.end_month, self.start_month
        return self


def parse_chart_arguments(raw_arguments: str) -> ChartSpec | None:
    """Validate the arguments of a `create_chart` tool call.

    Args:
        raw_arguments: JSON string with the tool arguments, as returned by the model.

    Returns:
        The chart specification, or `None` if the arguments are not valid.
    """
    try:
        return ChartSpec.model_validate(json.loads(raw_arguments or "{}"))
    except (json.JSONDecodeError, ValidationError, TypeError):
        logger.warning("Invalid %s arguments from the model: %s", CHART_TOOL_NAME, raw_arguments)
        return None


def describe_chart(chart: ChartSpec) -> str:
    """One-line description of a chart for the conversation history the model sees.

    Args:
        chart: The chart specification.

    Returns:
        A short description in plain words (the model tends to repeat it to the owner), e.g.
        `"Cash 2025" (money in, money out; bar; per month; 2025-01 to 2025-06)`.
    """
    period = (
        f"; {chart.start_month or 'start'} to {chart.end_month or 'end'}"
        if chart.start_month or chart.end_month
        else ""
    )
    granularity = "" if chart.metrics[0] in CATEGORY_METRICS else f"; per {chart.granularity}"
    metrics = ", ".join(METRIC_NAMES[metric] for metric in chart.metrics)
    return f'"{chart.title}" ({metrics}; {chart.chart_type}{granularity}{period})'
