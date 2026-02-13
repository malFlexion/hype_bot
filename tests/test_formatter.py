"""Tests for the ResponseFormatter."""

import pytest
from src.formatter import ResponseFormatter
from tests.conftest import make_post


class TestUriToUrl:
    def test_valid_uri_with_handle(self):
        uri = "at://did:plc:abc123/app.bsky.feed.post/xyz789"
        result = ResponseFormatter.uri_to_url(uri, handle="user.bsky.social")
        assert result == "https://bsky.app/profile/user.bsky.social/post/xyz789"

    def test_valid_uri_without_handle(self):
        uri = "at://did:plc:abc123/app.bsky.feed.post/xyz789"
        result = ResponseFormatter.uri_to_url(uri)
        assert result == "https://bsky.app/profile/did:plc:abc123/post/xyz789"

    def test_malformed_uri(self):
        uri = "not-a-valid-uri"
        result = ResponseFormatter.uri_to_url(uri)
        assert result == uri  # returns original on failure


class TestFormatEngagementStats:
    def test_normal_values(self):
        result = ResponseFormatter.format_engagement_stats(100, 50, 20)
        assert "100" in result
        assert "50" in result
        assert "20" in result

    def test_zeros(self):
        result = ResponseFormatter.format_engagement_stats(0, 0, 0)
        assert "0" in result


class TestTruncateText:
    def test_under_limit(self):
        result = ResponseFormatter.truncate_text("short", 10)
        assert result == "short"

    def test_at_limit(self):
        result = ResponseFormatter.truncate_text("12345", 5)
        assert result == "12345"

    def test_over_limit(self):
        result = ResponseFormatter.truncate_text("this is a long string", 10)
        assert len(result) == 10
        assert result.endswith("...")


class TestGetPostPreview:
    def test_normal_text(self, formatter):
        post = make_post(text="Hello world")
        result = formatter.get_post_preview(post)
        assert "Hello world" in result
        assert result.startswith('"')

    def test_missing_text(self, formatter):
        from types import SimpleNamespace
        post = SimpleNamespace()
        result = formatter.get_post_preview(post)
        assert result == "[Post content unavailable]"

    def test_whitespace_cleanup(self, formatter):
        post = make_post(text="hello   world\n\nnewlines")
        result = formatter.get_post_preview(post)
        assert "hello world newlines" in result


class TestFormatThreadPost:
    def test_within_char_limit(self, formatter):
        post = make_post(likes=10, reposts=5, replies=2, text="Short post")
        result = formatter.format_thread_post(
            emoji="🔥", title="Test Title", post=post
        )
        assert len(result) <= 300

    def test_contains_required_elements(self, formatter):
        post = make_post(likes=10, reposts=5, replies=2, text="My post")
        result = formatter.format_thread_post(
            emoji="🔥", title="Test", post=post, handle="user.bsky.social"
        )
        assert "🔥" in result
        assert "Test" in result
        assert "bsky.app" in result


class TestCreateThreadResponses:
    def test_all_categories_present(self, formatter):
        post1 = make_post(likes=100, reposts=50, replies=20)
        post2 = make_post(likes=200, reposts=100, replies=50)
        post3 = make_post(likes=5, replies=30)

        thread = formatter.create_thread_responses(
            top_recent=(post1, 170),
            top_all_time=(post2, 350),
            most_ratioed=(post3, 6.0),  # ratio >= 3.0
            handle="user.bsky.social",
        )
        assert len(thread) == 3
        assert "🔥" in thread[0]
        assert "👑" in thread[1]
        assert "🌶️" in thread[2]

    def test_ratio_below_threshold_shows_fun_message(self, formatter):
        post = make_post(likes=10, replies=5)
        thread = formatter.create_thread_responses(
            top_recent=None,
            top_all_time=None,
            most_ratioed=(post, 0.5),  # ratio < 3.0
            handle="user.bsky.social",
        )
        assert "No ratio here" in thread[2]
        assert "bangers" in thread[2]

    def test_no_ratioed_post(self, formatter):
        thread = formatter.create_thread_responses(
            top_recent=None,
            top_all_time=None,
            most_ratioed=None,
            handle="user.bsky.social",
        )
        assert "No ratio here" in thread[2]

    def test_missing_recent_and_alltime(self, formatter):
        thread = formatter.create_thread_responses(
            top_recent=None,
            top_all_time=None,
            most_ratioed=None,
        )
        assert len(thread) == 3
        assert "No posts found" in thread[0]
        assert "No all-time" in thread[1]

    def test_all_posts_under_300_chars(self, formatter):
        post = make_post(likes=100, reposts=50, replies=20, text="A" * 200)
        thread = formatter.create_thread_responses(
            top_recent=(post, 170),
            top_all_time=(post, 170),
            most_ratioed=(post, 5.0),
            handle="user.bsky.social",
        )
        for post_text in thread:
            assert len(post_text) <= 300
