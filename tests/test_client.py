"""Tests for the BlueskyClient wrapper."""

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from src.client import BlueskyClient


@pytest.fixture
def client():
    """Create a BlueskyClient with a mocked atproto client."""
    with patch("src.client.AtProtoClient") as MockClient:
        mock_atproto = MagicMock()
        MockClient.return_value = mock_atproto
        bsky_client = BlueskyClient(
            handle="bot.bsky.social", app_password="test-password"
        )
        yield bsky_client, mock_atproto


class TestLogin:
    def test_successful_login(self, client):
        bsky_client, mock_atproto = client
        bsky_client.login()
        mock_atproto.login.assert_called_once_with(
            "bot.bsky.social", "test-password"
        )

    def test_failed_login(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.login.side_effect = Exception("Invalid credentials")
        with pytest.raises(Exception, match="Invalid credentials"):
            bsky_client.login()


class TestGetMentions:
    def test_filters_mentions(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.notification.list_notifications.return_value = (
            SimpleNamespace(
                notifications=[
                    SimpleNamespace(reason="mention", uri="at://1"),
                    SimpleNamespace(reason="like", uri="at://2"),
                    SimpleNamespace(reason="mention", uri="at://3"),
                    SimpleNamespace(reason="follow", uri="at://4"),
                ]
            )
        )
        mentions = bsky_client.get_mentions()
        assert len(mentions) == 2
        assert all(m.reason == "mention" for m in mentions)

    def test_no_notifications(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.notification.list_notifications.return_value = (
            SimpleNamespace(notifications=[])
        )
        mentions = bsky_client.get_mentions()
        assert mentions == []


class TestFetchAllPosts:
    def test_single_page(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.feed.get_author_feed.return_value = SimpleNamespace(
            feed=[
                SimpleNamespace(
                    post=SimpleNamespace(record=SimpleNamespace(text="post1")),
                    reason=None,
                ),
            ],
            cursor=None,
        )
        posts = bsky_client.fetch_all_posts("did:plc:user1", max_posts=100)
        assert len(posts) == 1

    def test_filters_reposts(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.feed.get_author_feed.return_value = SimpleNamespace(
            feed=[
                SimpleNamespace(
                    post=SimpleNamespace(record=SimpleNamespace(text="original")),
                    reason=None,
                ),
                SimpleNamespace(
                    post=SimpleNamespace(record=SimpleNamespace(text="repost")),
                    reason=SimpleNamespace(type="repost"),
                ),
            ],
            cursor=None,
        )
        posts = bsky_client.fetch_all_posts("did:plc:user1")
        assert len(posts) == 1
        assert posts[0].record.text == "original"

    def test_pagination(self, client):
        bsky_client, mock_atproto = client
        # First page returns cursor, second page returns None
        mock_atproto.app.bsky.feed.get_author_feed.side_effect = [
            SimpleNamespace(
                feed=[
                    SimpleNamespace(
                        post=SimpleNamespace(record=SimpleNamespace(text="p1")),
                        reason=None,
                    ),
                ],
                cursor="next_page",
            ),
            SimpleNamespace(
                feed=[
                    SimpleNamespace(
                        post=SimpleNamespace(record=SimpleNamespace(text="p2")),
                        reason=None,
                    ),
                ],
                cursor=None,
            ),
        ]
        posts = bsky_client.fetch_all_posts("did:plc:user1")
        assert len(posts) == 2


class TestIsFollowingBot:
    def test_user_follows_bot(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.actor.get_profile.return_value = SimpleNamespace(
            viewer=SimpleNamespace(followed_by="at://did:plc:user/follow/123")
        )
        assert bsky_client.is_following_bot("did:plc:user1") is True

    def test_user_does_not_follow(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.actor.get_profile.return_value = SimpleNamespace(
            viewer=SimpleNamespace(followed_by=None)
        )
        assert bsky_client.is_following_bot("did:plc:user1") is False

    def test_no_viewer(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.actor.get_profile.return_value = SimpleNamespace(
            viewer=None
        )
        assert bsky_client.is_following_bot("did:plc:user1") is False

    def test_api_error(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.app.bsky.actor.get_profile.side_effect = Exception("API error")
        assert bsky_client.is_following_bot("did:plc:user1") is False


class TestSendReply:
    def test_successful_reply(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.send_post.return_value = SimpleNamespace(
            uri="at://reply/uri", cid="replycid"
        )
        uri, cid = bsky_client.send_reply(
            text="Hello!",
            parent_uri="at://parent/uri",
            parent_cid="parentcid",
        )
        assert uri == "at://reply/uri"
        assert cid == "replycid"

    def test_failed_reply(self, client):
        bsky_client, mock_atproto = client
        mock_atproto.send_post.side_effect = Exception("Post failed")
        uri, cid = bsky_client.send_reply(
            text="Hello!",
            parent_uri="at://parent/uri",
            parent_cid="parentcid",
        )
        assert uri is None
        assert cid is None
