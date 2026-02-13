"""Response formatting for Bluesky posts."""

import logging
from typing import Any, Optional, List, Tuple


logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Format analytics results into Bluesky posts."""

    MAX_POST_LENGTH = 300
    MAX_TEXT_PREVIEW = 80

    @staticmethod
    def uri_to_url(uri: str, handle: Optional[str] = None) -> str:
        """
        Convert AT-URI to web URL.

        Args:
            uri: AT-URI (e.g., at://did:plc:xxx/app.bsky.feed.post/yyy)
            handle: Optional user handle for cleaner URL

        Returns:
            Web URL (e.g., https://bsky.app/profile/handle/post/rkey)
        """
        try:
            # Parse AT-URI: at://did/collection/rkey
            parts = uri.replace('at://', '').split('/')
            if len(parts) >= 3:
                did = parts[0]
                rkey = parts[2]

                # Use handle if available, otherwise DID
                actor = handle if handle else did

                return f"https://bsky.app/profile/{actor}/post/{rkey}"
        except Exception as e:
            logger.warning(f"Error converting URI to URL: {e}")

        return uri

    @staticmethod
    def format_engagement_stats(likes: int, reposts: int, replies: int) -> str:
        """
        Format engagement stats with emojis.

        Args:
            likes: Number of likes
            reposts: Number of reposts
            replies: Number of replies

        Returns:
            Formatted string (e.g., "❤️ 234 | 🔄 56 | 💬 89")
        """
        return f"❤️ {likes} | 🔄 {reposts} | 💬 {replies}"

    @staticmethod
    def truncate_text(text: str, max_length: int) -> str:
        """
        Truncate text with ellipsis if too long.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def get_post_preview(self, post: Any) -> str:
        """
        Extract and truncate post text for preview.

        Args:
            post: Post object

        Returns:
            Truncated post text
        """
        try:
            if isinstance(post, dict):
                text = post.get('record_text')
            else:
                record = getattr(post, 'record', None)
                text = record.get('text') if isinstance(record, dict) else getattr(record, 'text', None) if record else None
            if text:
                text = ' '.join(text.split())
                return f'"{self.truncate_text(text, self.MAX_TEXT_PREVIEW)}"'
        except Exception as e:
            logger.warning(f"Error extracting post text: {e}")

        return "[Post content unavailable]"

    def get_post_stats(self, post: Any) -> Tuple[int, int, int]:
        """
        Extract engagement stats from post.

        Args:
            post: Post object

        Returns:
            Tuple of (likes, reposts, replies)
        """
        if isinstance(post, dict):
            likes = post.get('like_count', 0)
            reposts = post.get('repost_count', 0)
            replies = post.get('reply_count', 0)
        else:
            likes = getattr(post, 'like_count', 0)
            reposts = getattr(post, 'repost_count', 0)
            replies = getattr(post, 'reply_count', 0)
        return likes, reposts, replies

    def format_thread_post(
        self,
        emoji: str,
        title: str,
        post: Any,
        score_text: Optional[str] = None,
        handle: Optional[str] = None
    ) -> str:
        """
        Format a single post in the thread.

        Args:
            emoji: Category emoji (🔥, 👑, 🌶️)
            title: Category title
            post: Post object
            score_text: Optional additional score text (e.g., "Ratio: 2.3")
            handle: User handle for URL

        Returns:
            Formatted post text
        """
        # Get post stats
        likes, reposts, replies = self.get_post_stats(post)
        stats = self.format_engagement_stats(likes, reposts, replies)

        # Get post preview
        preview = self.get_post_preview(post)
        
        # Get URL
        if isinstance(post, dict):
            uri = post.get('uri')
        else:
            uri = getattr(post, 'uri', None)
        url = self.uri_to_url(uri, handle)

        # Build the post
        parts = [
            f"{emoji} {title}",
            stats
        ]

        if score_text:
            parts.append(score_text)

        parts.append(preview)
        parts.append(url)

        # Join with newlines
        text = '\n\n'.join(parts)

        # Ensure it fits (truncate preview if needed)
        if len(text) > self.MAX_POST_LENGTH:
            # Recalculate with shorter preview
            available_for_preview = self.MAX_POST_LENGTH - (len('\n\n'.join(parts)) - len(preview))
            short_preview = self.truncate_text(
                preview,
                max(20, available_for_preview)
            )
            parts[-2] = short_preview
            text = '\n\n'.join(parts)

        return text

    def format_error_response(self, error_message: str, handle: Optional[str] = None) -> str:
        """
        Format an error message response.

        Args:
            error_message: Error description
            handle: User handle to mention

        Returns:
            Formatted error message
        """
        if handle:
            return f"Sorry @{handle}, I couldn't analyze your posts: {error_message}"
        return f"Sorry, I couldn't complete the analysis: {error_message}"

    def format_no_posts_response(self, handle: Optional[str] = None) -> str:
        """
        Format a response for users with no posts.

        Args:
            handle: User handle to mention

        Returns:
            Formatted message
        """
        if handle:
            return f"@{handle} doesn't have any posts yet! Start posting to build your engagement history. 🚀"
        return "No posts found to analyze. Start posting to build your engagement history! 🚀"

    def create_thread_responses(
        self,
        top_recent: Optional[Tuple[Any, int]],
        top_all_time: Optional[Tuple[Any, int]],
        most_ratioed: Optional[Tuple[Any, float]],
        handle: Optional[str] = None,
        recent_days: int = 30
    ) -> List[str]:
        """
        Create a thread of responses for the analytics.

        Args:
            top_recent: Tuple of (post, engagement) for top recent post
            top_all_time: Tuple of (post, engagement) for top all-time post
            most_ratioed: Tuple of (post, ratio) for most ratioed post
            handle: User handle
            recent_days: Number of days for "recent"

        Returns:
            List of post texts for the thread (3 posts)
        """
        thread = []

        # Post 1: Top recent
        if top_recent:
            post, engagement = top_recent
            text = self.format_thread_post(
                emoji="🔥",
                title=f"Recent ({recent_days}d) - {engagement} total engagement",
                post=post,
                handle=handle
            )
            thread.append(text)
        else:
            thread.append(f"🔥 No posts found in the last {recent_days} days")

        # Post 2: Top all-time
        if top_all_time:
            post, engagement = top_all_time
            text = self.format_thread_post(
                emoji="👑",
                title=f"All-Time - {engagement} total engagement",
                post=post,
                handle=handle
            )
            thread.append(text)
        else:
            thread.append("👑 No all-time posts found")

        # Post 3: Most ratioed (only if ratio is 3:1 or worse)
        if most_ratioed:
            post, ratio = most_ratioed
            if ratio >= 3.0:
                text = self.format_thread_post(
                    emoji="🌶️",
                    title="Most Ratioed",
                    post=post,
                    score_text=f"Ratio: {ratio:.1f}",
                    handle=handle
                )
                thread.append(text)
            else:
                thread.append(f"No ratio here! Keep posting those bangers 🔥")
        else:
            thread.append(f"No ratio here! Keep posting those bangers 🔥")

        return thread
