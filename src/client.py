"""Bluesky API client wrapper using atproto SDK."""

import logging
import re
import time
from html.parser import HTMLParser
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError
from atproto import Client as AtProtoClient, models

logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(r'https?://[^\s\)\]\}>,"\']+', re.IGNORECASE)


class _OGParser(HTMLParser):
    """Minimal OpenGraph meta tag parser."""

    def __init__(self):
        super().__init__()
        self.og = {}

    def handle_starttag(self, tag, attrs):
        if tag != 'meta':
            return
        attrs_dict = dict(attrs)
        prop = attrs_dict.get('property', '')
        if prop.startswith('og:') and 'content' in attrs_dict:
            self.og[prop[3:]] = attrs_dict['content']


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

    def get_notifications(self, since: Optional[str] = None) -> List[Any]:
        """
        Fetch notifications, optionally filtered to those after a timestamp.

        Args:
            since: ISO timestamp — only return notifications indexed after this time

        Returns:
            List of notification objects
        """
        try:
            response = self.client.app.bsky.notification.list_notifications()

            notifications = response.notifications if hasattr(response, 'notifications') else []

            # Filter client-side by timestamp since the API no longer supports seenAt
            if since and notifications:
                notifications = [
                    n for n in notifications
                    if hasattr(n, 'indexed_at') and n.indexed_at > since
                ]

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
        notifications = self.get_notifications(since=seen_at)
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

    def fetch_all_posts(self, actor: str, max_posts: int = 10000) -> List[Any]:
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
                        post = item.post
                        # Extract minimal fields
                        post_dict = {
                            'like_count': getattr(post, 'like_count', 0),
                            'repost_count': getattr(post, 'repost_count', 0),
                            'reply_count': getattr(post, 'reply_count', 0),
                            'uri': getattr(post, 'uri', None),
                            'indexed_at': getattr(post, 'indexed_at', None),
                            'record_text': None,
                            'record_created_at': None
                        }
                        record = getattr(post, 'record', None)
                        if record:
                            # Handle both object and dict for record
                            text = record.get('text') if isinstance(record, dict) else getattr(record, 'text', None)
                            created_at = record.get('created_at') if isinstance(record, dict) else getattr(record, 'created_at', None)
                            post_dict['record_text'] = text
                            post_dict['record_created_at'] = created_at
                        all_posts.append(post_dict)

                if len(all_posts) >= max_posts:
                    break

            cursor = result['cursor']
            if not cursor:
                break

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        logger.info(f"Fetched {len(all_posts)} posts for {actor}")
        return all_posts

    @staticmethod
    def _detect_facets(text: str) -> Optional[List]:
        """
        Detect URLs in text and create Bluesky facets for them.

        Bluesky requires explicit facets with UTF-8 byte offsets
        to make links clickable in posts.

        Args:
            text: Post text to scan for URLs

        Returns:
            List of facet objects, or None if no URLs found
        """
        facets = []

        for match in _URL_PATTERN.finditer(text):
            url = match.group(0)
            # Strip trailing punctuation that's likely not part of the URL
            while url and url[-1] in '.,:;!?)':
                url = url[:-1]

            # Calculate byte offsets
            start_char = match.start()
            byte_start = len(text[:start_char].encode('utf-8'))
            byte_end = byte_start + len(url.encode('utf-8'))

            facet = models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=byte_start,
                    byte_end=byte_end,
                ),
                features=[
                    models.AppBskyRichtextFacet.Link(uri=url)
                ],
            )
            facets.append(facet)

        return facets if facets else None

    @staticmethod
    def _fetch_og_metadata(url: str) -> Dict[str, str]:
        """Fetch OpenGraph metadata from a URL."""
        req = Request(url, headers={'User-Agent': 'HypeBot/1.0'})
        with urlopen(req, timeout=10) as resp:
            # Read enough to get the <head> section
            html = resp.read(32768).decode('utf-8', errors='ignore')
        parser = _OGParser()
        parser.feed(html)
        return parser.og

    def _create_external_embed(self, url: str) -> Optional[Any]:
        """
        Create an external embed (link card) for a URL by fetching
        its OpenGraph metadata and thumbnail image.

        Args:
            url: The URL to create a link card for

        Returns:
            External embed object, or None if failed
        """
        try:
            og = self._fetch_og_metadata(url)
            title = og.get('title', url)
            description = og.get('description', '')

            # Upload thumbnail if available
            thumb = None
            image_url = og.get('image')
            if image_url:
                try:
                    img_req = Request(image_url, headers={'User-Agent': 'HypeBot/1.0'})
                    with urlopen(img_req, timeout=10) as img_resp:
                        img_data = img_resp.read(1_000_000)  # 1MB max
                        content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
                    thumb = self.client.upload_blob(img_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch/upload thumbnail: {e}")

            external = models.AppBskyEmbedExternal.External(
                uri=url,
                title=title,
                description=description,
                thumb=thumb.blob if thumb else None,
            )
            return models.AppBskyEmbedExternal.Main(external=external)

        except Exception as e:
            logger.warning(f"Failed to create external embed for {url}: {e}")
            return None

    def _extract_first_url(self, text: str) -> Optional[str]:
        """Extract the first URL from text."""
        match = _URL_PATTERN.search(text)
        if match:
            url = match.group(0)
            while url and url[-1] in '.,:;!?)':
                url = url[:-1]
            return url
        return None

    def send_post(self, text: str) -> Optional[str]:
        """
        Send a standalone post.

        Args:
            text: Post content (max 300 chars)

        Returns:
            URI of created post, or None if failed
        """
        try:
            facets = self._detect_facets(text)
            url = self._extract_first_url(text)
            embed = self._create_external_embed(url) if url else None
            response = self.client.send_post(text=text, facets=facets, embed=embed)
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

            # Detect URL facets and create link card embed
            facets = self._detect_facets(text)
            url = self._extract_first_url(text)
            embed = self._create_external_embed(url) if url else None

            # Send the reply
            response = self.client.send_post(text=text, reply_to=reply, facets=facets, embed=embed)
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
            self.client.app.bsky.notification.update_seen(
                models.AppBskyNotificationUpdateSeen.Data(seen_at=seen_at)
            )
            self._last_seen_at = seen_at
            logger.debug(f"Updated seen notifications to {seen_at}")
            return True
        except Exception as e:
            logger.error(f"Error updating seen notifications: {e}")
            return False

    def is_following_bot(self, actor_did: str) -> bool:
        """
        Check if a user follows the bot.

        Args:
            actor_did: DID of the user to check

        Returns:
            True if the user follows the bot, False otherwise
        """
        try:
            profile = self.client.app.bsky.actor.get_profile({'actor': actor_did})
            viewer = getattr(profile, 'viewer', None)
            if viewer and getattr(viewer, 'followed_by', None):
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking follow status for {actor_did}: {e}")
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
