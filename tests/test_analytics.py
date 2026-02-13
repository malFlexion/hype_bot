"""Tests for the PostAnalytics engine."""

import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from src.analytics import PostAnalytics
from tests.conftest import make_post


class TestCalculateEngagement:
    def test_normal_values(self):
        post = make_post(likes=100, reposts=50, replies=20)
        assert PostAnalytics.calculate_engagement(post) == 170

    def test_all_zeros(self):
        post = make_post(likes=0, reposts=0, replies=0)
        assert PostAnalytics.calculate_engagement(post) == 0

    def test_missing_attributes(self):
        post = SimpleNamespace()  # no like_count, etc.
        assert PostAnalytics.calculate_engagement(post) == 0


class TestCalculateRatio:
    def test_normal_ratio(self):
        post = make_post(likes=10, replies=30)
        assert PostAnalytics.calculate_ratio(post) == 3.0

    def test_zero_likes(self):
        post = make_post(likes=0, replies=10)
        # Should use max(likes, 1) = 1
        assert PostAnalytics.calculate_ratio(post) == 10.0

    def test_no_replies(self):
        post = make_post(likes=50, replies=0)
        assert PostAnalytics.calculate_ratio(post) == 0.0

    def test_high_ratio(self):
        post = make_post(likes=2, replies=100)
        assert PostAnalytics.calculate_ratio(post) == 50.0


class TestGetPostDate:
    def test_indexed_at(self):
        post = make_post(indexed_at="2025-06-15T12:00:00.000Z")
        result = PostAnalytics.get_post_date(post)
        assert result is not None
        assert result.year == 2025
        assert result.month == 6

    def test_created_at_fallback(self):
        post = SimpleNamespace(
            record=SimpleNamespace(created_at="2025-03-01T08:00:00.000Z")
        )
        result = PostAnalytics.get_post_date(post)
        assert result is not None
        assert result.month == 3

    def test_no_date(self):
        post = SimpleNamespace()
        result = PostAnalytics.get_post_date(post)
        assert result is None


class TestFindTopRecentPost:
    def test_finds_top_within_window(self, analytics):
        now = datetime.now(timezone.utc).isoformat()
        posts = [
            make_post(likes=10, reposts=5, replies=2, indexed_at=now),
            make_post(likes=50, reposts=20, replies=10, indexed_at=now),
        ]
        result = analytics.find_top_recent_post(posts, days=30)
        assert result is not None
        post, engagement = result
        assert engagement == 80  # 50+20+10

    def test_excludes_old_posts(self, analytics):
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        posts = [make_post(likes=100, reposts=50, replies=20, indexed_at=old_date)]
        result = analytics.find_top_recent_post(posts, days=30)
        assert result is None

    def test_empty_list(self, analytics):
        result = analytics.find_top_recent_post([], days=30)
        assert result is None


class TestFindTopAllTimePost:
    def test_finds_highest_engagement(self, analytics):
        posts = [
            make_post(likes=10, reposts=5, replies=2),
            make_post(likes=200, reposts=100, replies=50),
            make_post(likes=50, reposts=20, replies=10),
        ]
        result = analytics.find_top_all_time_post(posts)
        assert result is not None
        post, engagement = result
        assert engagement == 350  # 200+100+50

    def test_empty_list(self, analytics):
        result = analytics.find_top_all_time_post([])
        assert result is None

    def test_single_post(self, analytics):
        posts = [make_post(likes=5, reposts=1, replies=1)]
        result = analytics.find_top_all_time_post(posts)
        assert result is not None
        _, engagement = result
        assert engagement == 7


class TestFindMostRatioedPost:
    def test_finds_highest_ratio(self, analytics):
        posts = [
            make_post(likes=10, replies=5),   # ratio 0.5
            make_post(likes=10, replies=50),  # ratio 5.0
            make_post(likes=10, replies=20),  # ratio 2.0
        ]
        result = analytics.find_most_ratioed_post(posts)
        assert result is not None
        _, ratio = result
        assert ratio == 5.0

    def test_filters_below_min_engagement(self):
        analytics = PostAnalytics(min_engagement_for_ratio=10)
        posts = [
            make_post(likes=3, replies=100),  # below threshold
            make_post(likes=15, replies=30),  # above threshold, ratio 2.0
        ]
        result = analytics.find_most_ratioed_post(posts)
        assert result is not None
        _, ratio = result
        assert ratio == 2.0

    def test_no_qualifying_posts(self):
        analytics = PostAnalytics(min_engagement_for_ratio=100)
        posts = [make_post(likes=5, replies=50)]
        result = analytics.find_most_ratioed_post(posts)
        assert result is None


class TestAnalyzeUserPosts:
    def test_returns_all_categories(self, analytics):
        now = datetime.now(timezone.utc).isoformat()
        posts = [
            make_post(likes=100, reposts=50, replies=20, indexed_at=now),
            make_post(likes=10, replies=40, indexed_at=now),
        ]
        result = analytics.analyze_user_posts(posts)
        assert 'top_recent' in result
        assert 'top_all_time' in result
        assert 'most_ratioed' in result

    def test_empty_posts(self, analytics):
        result = analytics.analyze_user_posts([])
        assert result['top_recent'] is None
        assert result['top_all_time'] is None
        assert result['most_ratioed'] is None
