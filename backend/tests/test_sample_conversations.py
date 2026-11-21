from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agents.chat.charts import ChartSpec
from app.storage.conversations import ConversationRepository
from app.storage.sample_conversations import (
    SAMPLE_CONVERSATIONS,
    build_sample_drafts,
    seed_sample_conversations,
)


@pytest.fixture
def repository(tmp_path: Path) -> ConversationRepository:
    return ConversationRepository(tmp_path / "samples.sqlite3")


def test_every_sample_chart_is_a_valid_chart_spec() -> None:
    charts = [
        exchange.chart
        for samples in SAMPLE_CONVERSATIONS.values()
        for sample in samples
        for exchange in sample.exchanges
        if exchange.chart is not None
    ]

    assert charts
    for chart in charts:
        # Revalidating must not change anything: the stored chart is exactly what the frontend gets.
        assert ChartSpec.model_validate(chart.model_dump()) == chart


def test_seeding_inserts_samples_newest_first_in_the_defined_order(
    repository: ConversationRepository,
) -> None:
    assert seed_sample_conversations(repository) == ["amalfi"]

    summaries = repository.list_conversations("amalfi")
    assert [summary.title for summary in summaries] == [
        sample.title for sample in SAMPLE_CONVERSATIONS["amalfi"]
    ]
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    assert all(summary.created_at < summary.updated_at < now for summary in summaries)
    first = repository.get_conversation("amalfi", summaries[0].id)
    assert first is not None
    assert [message.role for message in first.messages][:2] == ["user", "assistant"]
    assert first.messages[1].chart is not None
    assert repository.list_conversations("other-account") == []


def test_seeding_is_idempotent_and_respects_deletions(tmp_path: Path) -> None:
    database_path = tmp_path / "samples.sqlite3"
    repository = ConversationRepository(database_path)
    seed_sample_conversations(repository)
    deleted = repository.list_conversations("amalfi")[0]
    assert repository.delete_conversation("amalfi", deleted.id)

    restarted = ConversationRepository(database_path)
    assert seed_sample_conversations(restarted) == []

    titles = [summary.title for summary in restarted.list_conversations("amalfi")]
    assert deleted.title not in titles
    assert len(titles) == len(SAMPLE_CONVERSATIONS["amalfi"]) - 1


def test_reset_replaces_the_accounts_conversations(repository: ConversationRepository) -> None:
    own = repository.create_conversation("amalfi", "Test chat")
    repository.append_exchange(own.id, "Hi", "Ciao!")
    other = repository.create_conversation("other-account", "Someone else's chat")

    repository.reset_conversations("amalfi", build_sample_drafts("amalfi", datetime.now(UTC)))

    titles = [summary.title for summary in repository.list_conversations("amalfi")]
    assert titles == [sample.title for sample in SAMPLE_CONVERSATIONS["amalfi"]]
    assert repository.get_conversation("amalfi", own.id) is None
    assert repository.get_conversation("other-account", other.id) is not None
    assert seed_sample_conversations(repository) == []
