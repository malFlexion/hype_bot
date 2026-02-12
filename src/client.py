"""Bluesky API client wrapper using atproto SDK."""

import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from atproto import Client as AtProtoClient, models


logger = logging.getLogger(__name__)


class BlueskyClient:
    """Wrapper around atproto Client with error handling and convenience methods."""

    def __init__(self, handle: str, app_password: str):
        """
        Initialize the Bluesky client.

        Args:
            handle: Bot's Bluesky handle (e.g., bot.bsky.social)
            app_password: App password from Bluesky settings
        """
        self.handle = handle
        self.app_password = app_password
        self.client = AtProtoClient()
        self._last_seen_at: Optional[str] = None

    def login(self) -> None:
        """Authenticate with Bluesky."""
        try:
            self.client.login(self.handle, self.app_password)
            logger.info(f"✓ Successfully authenticated as {self.handle}")
        except Exception as e:
            logger.error(f"✗ Authentication failed: {e}")
            raise

    def get_notifications(self, seen_at: Optional[str] = None) -> List[Any]:
        """
        Fetch new notifications since the given timestamp.

        Args:
            seen_at: ISO timestamp of last seen notification (optional)

        Returns:
            List of notification objects
        """
        try:
            params = {}
            if seen_at:
                params['seen_at'] = seen_at

            response = self.client.app.bsky.notification.list_notifications(params=params)

            notifications = response.notifications if hasattr(response, 'notifications') else []
            logger.info(f"Fetched {len(notifications)} notifications")
            return notifications

        except Exception as e:
            logger.error(f"Error fetching notifications: {e}")
            return []

    def get_mentions(self, seen_at: Optional[str] = None) -> List[Any]:
        """
        Fetch new mentions since the given timestamp.

        Args:
            seen_at: ISO timestamp of last seen notification (optional)

        Returns:
            List of mention notifications
        """
        notifications = self.get_notifications(seen_at)
        mentions = [n for n in notifications if n.reason == 'mention']
        logger.info(f"Found {len(mentions)} new mentions")
        return mentions

    def get_author_feed(
        self,
        actor: str,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch posts from a user's feed.

        Args:
            actor: User's DID or handle
            limit: Number of posts to fetch (max 100 per request)
            cursor: Pagination cursor for next page

        Returns:
            Dict with 'feed' (list of posts) and 'cursor' (for pagination)
        """
        try:
            params = {
                'actor': actor,
                'limit': min(limit, 100)
            }
            if cursor:
                params['cursor'] = cursor

            response = self.client.app.bsky.feed.get_author_feed(params=params)

            feed = response.feed if hasattr(response, 'feed') else []
            next_cursor = response.cursor if hasattr(response, 'cursor') else None

            return {
                'feed': feed,
                'cursor': next_cursor
            }

        except Exception as e:
            logger.error(f"Error fetching feed for {actor}: {e}")
            return {'feed': [], 'cursor': None}

    def fetch_all_posts(self, actor: str, max_posts: int = 1000) -> List[Any]:
        """
        Fetch all posts from a user with pagination.

        Args:
            actor: User's DID or handle
            max_posts: Maximum number of posts to fetch

        Returns:
            List of post objects (only original posts, not reposts)
        """
        all_posts = []
        cursor = None

        logger.info(f"Fetching posts for {actor} (max {max_posts})...")

        while len(all_posts) < max_posts:
            result = self.get_author_feed(actor, limit=100, cursor=cursor)
            feed_items = result['feed']

            if not feed_items:
                break

            # Filter out reposts, only keep original posts
            for item in feed_items:
                if hasattr(item, 'post') and hasattr(item.post, 'record'):
                    # Check if it's a repost
                    if not hasattr(item, 'reason') or item.reason is None:
                        all_posts.append(item.post)

                if len(all_posts) >= max_posts:
                    break

            cursor = result['cursor']
            if not cursor:
                break

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        logger.info(f"Fetched {len(all_posts)} posts for {actor}")
        return all_posts

    def send_post(self, text: str) -> Optional[str]:
        """
        Send a standalone post.

        Args:
            text: Post content (max 300 chars)

        Returns:
            URI of created post, or None if failed
        """
        try:
            response = self.client.send_post(text=text)
            uri = response.uri if hasattr(response, 'uri') else None
            logger.info(f"Posted: {text[:50]}...")
            return uri
        except Exception as e:
            logger.error(f"Error posting: {e}")
            return None

    def send_reply(
        self,
        text: str,
        parent_uri: str,
        parent_cid: str,
        root_uri: Optional[str] = None,
        root_cid: Optional[str] = None
    ) -> Optional[str]:
        """
        Reply to a post.

        Args:
            text: Reply content (max 300 chars)
            parent_uri: URI of the post being replied to
            parent_cid: CID of the post being replied to
            root_uri: URI of the root post in thread (for threading)
            root_cid: CID of the root post in thread (for threading)

        Returns:
            URI of created reply, or None if failed
        """
        try:
            # Create reply reference
            parent_ref = models.create_strong_ref(
                models.ComAtprotoRepoStrongRef.Main(
                    uri=parent_uri,
                    cid=parent_cid
                )
            )

            # If no root specified, parent is the root
            if root_uri and root_cid:
                root_ref = models.create_strong_ref(
                    models.ComAtprotoRepoStrongRef.Main(
                        uri=root_uri,
                        cid=root_cid
                    )
                )
            else:
                root_ref = parent_ref

            # Create reply object
            reply = models.AppBskyFeedPost.ReplyRef(
                parent=parent_ref,
                root=root_ref
            )

            # Send the reply
            response = self.client.send_post(text=text, reply_to=reply)
            uri = response.uri if hasattr(response, 'uri') else None
            cid = response.cid if hasattr(response, 'cid') else None

            logger.info(f"Replied: {text[:50]}...")
            return uri, cid

        except Exception as e:
            logger.error(f"Error sending reply: {e}")
            return None, None

    def update_seen_notifications(self, seen_at: str) -> bool:
        """
        Mark notifications as seen.

        Args:
            seen_at: ISO timestamp to mark as seen

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.app.bsky.notification.update_seen({'seen_at': seen_at})
            self._last_seen_at = seen_at
            logger.debug(f"Updated seen notifications to {seen_at}")
            return True
        except Exception as e:
            logger.error(f"Error updating seen notifications: {e}")
            return False

    def get_profile(self, actor: str) -> Optional[Any]:
        """
        Get profile information for a user.

        Args:
            actor: User's DID or handle

        Returns:
            Profile object or None if failed
        """
        try:
            response = self.client.app.bsky.actor.get_profile({'actor': actor})
            return response
        except Exception as e:
            logger.error(f"Error fetching profile for {actor}: {e}")
            return None
