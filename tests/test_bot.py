"""Tests for the BlueskyBot and MentionTracker."""

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from src.bot import BlueskyBot, MentionTracker
from tests.conftest import make_post, make_mention


class TestMentionTracker:
    def test_new_mention_not_processed(self, tmp_path):
        tracker = MentionTracker(data_dir=str(tmp_path))
        assert tracker.is_processed("at://some/uri") is False

    def test_mark_and_check_processed(self, tmp_path):
        tracker = MentionTracker(data_dir=str(tmp_path))
        tracker.mark_processed("at://some/uri")
        assert tracker.is_processed("at://some/uri") is True

    def test_different_uri_not_processed(self, tmp_path):
        tracker = MentionTracker(data_dir=str(tmp_path))
        tracker.mark_processed("at://uri1")
        assert tracker.is_processed("at://uri2") is False

    def test_update_last_seen(self, tmp_path):
        tracker = MentionTracker(data_dir=str(tmp_path))
        assert tracker.last_seen_at is None
        tracker.update_last_seen("2025-01-15T12:00:00.000Z")
        assert tracker.last_seen_at == "2025-01-15T12:00:00.000Z"

    def test_persists_across_instances(self, tmp_path):
        tracker = MentionTracker(data_dir=str(tmp_path))
        tracker.mark_processed("at://some/uri")
        tracker.update_last_seen("2025-01-15T12:00:00.000Z")

        tracker2 = MentionTracker(data_dir=str(tmp_path))
        assert tracker2.is_processed("at://some/uri") is True
        assert tracker2.last_seen_at == "2025-01-15T12:00:00.000Z"

    def test_handles_missing_file(self, tmp_path):
        tracker = MentionTracker(data_dir=str(tmp_path))
        assert tracker.processed_uris == set()
        assert tracker.last_seen_at is None


class TestBlueskyBotProcessMention:
    def _make_bot(self, tmp_path):
        """Create a bot with mocked dependencies."""
        client = MagicMock()
        config = SimpleNamespace(
            MAX_POSTS=10000,
            RECENT_DAYS=30,
            MIN_ENGAGEMENT_FOR_RATIO=5,
        )
        bot = BlueskyBot(client=client, config=config)
        bot.tracker = MentionTracker(data_dir=str(tmp_path))
        return bot, client

    def test_skips_already_processed(self, tmp_path):
        bot, client = self._make_bot(tmp_path)
        mention = make_mention()
        bot.tracker.mark_processed(mention.uri)

        result = bot.process_mention(mention)
        assert result is True
        client.fetch_all_posts.assert_not_called()

    def test_non_follower_gets_follow_prompt(self, tmp_path):
        bot, client = self._make_bot(tmp_path)
        client.is_following_bot.return_value = False
        client.send_reply.return_value = ("uri", "cid")
        mention = make_mention()

        result = bot.process_mention(mention)
        assert result is True
        client.send_reply.assert_called_once()
        reply_text = client.send_reply.call_args[1]["text"]
        assert "Follow me first" in reply_text
        assert bot.tracker.is_processed(mention.uri)

    def test_follower_with_posts_gets_analytics(self, tmp_path):
        bot, client = self._make_bot(tmp_path)
        client.is_following_bot.return_value = True
        client.fetch_all_posts.return_value = [
            make_post(likes=100, reposts=50, replies=20),
        ]
        client.send_reply.return_value = ("at://reply/uri", "replycid")
        mention = make_mention()

        result = bot.process_mention(mention)
        assert result is True
        # Should send 2 thread posts (first reply + 1 continuation)
        assert client.send_reply.call_count == 2
        assert bot.tracker.is_processed(mention.uri)

    def test_follower_with_no_posts(self, tmp_path):
        bot, client = self._make_bot(tmp_path)
        client.is_following_bot.return_value = True
        client.fetch_all_posts.return_value = []
        client.send_reply.return_value = ("uri", "cid")
        mention = make_mention()

        result = bot.process_mention(mention)
        assert result is True
        client.send_reply.assert_called_once()
        reply_text = client.send_reply.call_args[1]["text"]
        assert "doesn't have any posts" in reply_text

    def test_error_handling(self, tmp_path):
        bot, client = self._make_bot(tmp_path)
        client.is_following_bot.side_effect = Exception("API error")
        client.send_reply.return_value = ("uri", "cid")
        mention = make_mention()

        result = bot.process_mention(mention)
        assert result is False
