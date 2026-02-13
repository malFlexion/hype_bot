"""Shared test fixtures for hype_bot tests."""

import pytest
from datetime import datetime, timezone
from types import SimpleNamespace


def make_post(
    likes=0,
    reposts=0,
    replies=0,
    text="Test post",
    uri="at://did:plc:abc123/app.bsky.feed.post/xyz789",
    indexed_at=None,
    created_at=None,
):
    """Factory for creating mock post objects."""
    record = SimpleNamespace(
        text=text,
        created_at=created_at or "2025-01-15T12:00:00.000Z",
    )
    return SimpleNamespace(
        like_count=likes,
        repost_count=reposts,
        reply_count=replies,
        record=record,
        uri=uri,
        indexed_at=indexed_at or "2025-01-15T12:00:00.000Z",
    )


def make_mention(
    uri="at://did:plc:author/app.bsky.feed.post/mention1",
    cid="bafyreimention1",
    author_did="did:plc:author123",
    author_handle="testuser.bsky.social",
    indexed_at="2025-01-15T12:00:00.000Z",
):
    """Factory for creating mock mention objects."""
    author = SimpleNamespace(did=author_did, handle=author_handle)
    return SimpleNamespace(
        uri=uri,
        cid=cid,
        author=author,
        indexed_at=indexed_at,
    )


@pytest.fixture
def sample_posts():
    """A list of sample posts with varying engagement."""
    return [
        make_post(likes=100, reposts=50, replies=20, text="Popular post"),
        make_post(likes=10, reposts=5, replies=2, text="Average post"),
        make_post(likes=1, reposts=0, replies=0, text="Low engagement post"),
        make_post(likes=5, reposts=1, replies=30, text="Ratioed post"),
    ]


@pytest.fixture
def formatter():
    """ResponseFormatter instance."""
    from src.formatter import ResponseFormatter
    return ResponseFormatter()


@pytest.fixture
def analytics():
    """PostAnalytics instance with default settings."""
    from src.analytics import PostAnalytics
    return PostAnalytics()
