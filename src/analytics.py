"""Analytics engine for calculating engagement metrics."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Any, Tuple
from dateutil import parser


logger = logging.getLogger(__name__)


class PostAnalytics:
    """Post engagement analytics."""

    def __init__(self, min_engagement_for_ratio: int = 5):
        """
        Initialize analytics engine.

        Args:
            min_engagement_for_ratio: Minimum likes required for ratio calculation
        """
        self.min_engagement_for_ratio = min_engagement_for_ratio

    @staticmethod
    def calculate_engagement(post: Any) -> int:
        """
        Calculate total engagement for a post.

        Engagement = likes + reposts + replies

        Args:
            post: Post object from Bluesky API

        Returns:
            Total engagement score
        """
        likes = post.like_count if hasattr(post, 'like_count') else 0
        reposts = post.repost_count if hasattr(post, 'repost_count') else 0
        replies = post.reply_count if hasattr(post, 'reply_count') else 0

        return likes + reposts + replies

    @staticmethod
    def calculate_ratio(post: Any) -> float:
        """
        Calculate reply/like ratio for a post.

        Higher ratio indicates more controversial/divisive content.

        Args:
            post: Post object from Bluesky API

        Returns:
            Ratio of replies to likes (replies / max(likes, 1))
        """
        likes = post.like_count if hasattr(post, 'like_count') else 0
        replies = post.reply_count if hasattr(post, 'reply_count') else 0

        # Avoid division by zero
        return replies / max(likes, 1)

    @staticmethod
    def get_post_date(post: Any) -> Optional[datetime]:
        """
        Extract the timestamp from a post.

        Args:
            post: Post object from Bluesky API

        Returns:
            Datetime object or None if not available
        """
        try:
            if hasattr(post, 'indexed_at'):
                return parser.parse(post.indexed_at)
            elif hasattr(post, 'record') and hasattr(post.record, 'created_at'):
                return parser.parse(post.record.created_at)
            return None
        except Exception as e:
            logger.warning(f"Error parsing post date: {e}")
            return None

    def find_top_recent_post(
        self,
        posts: List[Any],
        days: int = 30
    ) -> Optional[Tuple[Any, int]]:
        """
        Find the top post from recent days based on engagement.

        Args:
            posts: List of post objects
            days: Number of days to look back

        Returns:
            Tuple of (post, engagement_score) or None if no recent posts
        """
        cutoff_date = datetime.now(tz=None) - timedelta(days=days)
        recent_posts = []

        for post in posts:
            post_date = self.get_post_date(post)
            if post_date:
                # Make cutoff_date timezone-aware if post_date is
                if post_date.tzinfo:
                    cutoff_date = cutoff_date.replace(tzinfo=post_date.tzinfo)
                else:
                    post_date = post_date.replace(tzinfo=None)

                if post_date >= cutoff_date:
                    engagement = self.calculate_engagement(post)
                    recent_posts.append((post, engagement))

        if not recent_posts:
            logger.info(f"No posts found in the last {days} days")
            return None

        # Sort by engagement (descending)
        recent_posts.sort(key=lambda x: x[1], reverse=True)

        top_post, engagement = recent_posts[0]
        logger.info(f"Top recent post ({days}d): {engagement} engagement")
        return top_post, engagement

    def find_top_all_time_post(
        self,
        posts: List[Any]
    ) -> Optional[Tuple[Any, int]]:
        """
        Find the top post of all time based on engagement.

        Args:
            posts: List of post objects

        Returns:
            Tuple of (post, engagement_score) or None if no posts
        """
        if not posts:
            logger.info("No posts found")
            return None

        posts_with_engagement = [
            (post, self.calculate_engagement(post))
            for post in posts
        ]

        # Sort by engagement (descending)
        posts_with_engagement.sort(key=lambda x: x[1], reverse=True)

        top_post, engagement = posts_with_engagement[0]
        logger.info(f"Top all-time post: {engagement} engagement")
        return top_post, engagement

    def find_most_ratioed_post(
        self,
        posts: List[Any]
    ) -> Optional[Tuple[Any, float]]:
        """
        Find the post with the highest reply/like ratio.

        Filters out posts with low engagement to avoid noise.

        Args:
            posts: List of post objects

        Returns:
            Tuple of (post, ratio_score) or None if no qualifying posts
        """
        qualifying_posts = []

        for post in posts:
            likes = post.like_count if hasattr(post, 'like_count') else 0

            # Only consider posts with minimum engagement
            if likes >= self.min_engagement_for_ratio:
                ratio = self.calculate_ratio(post)
                qualifying_posts.append((post, ratio))

        if not qualifying_posts:
            logger.info(
                f"No posts with at least {self.min_engagement_for_ratio} likes "
                f"for ratio calculation"
            )
            return None

        # Sort by ratio (descending)
        qualifying_posts.sort(key=lambda x: x[1], reverse=True)

        top_post, ratio = qualifying_posts[0]
        logger.info(f"Most ratioed post: {ratio:.2f} ratio")
        return top_post, ratio

    def analyze_user_posts(
        self,
        posts: List[Any],
        recent_days: int = 30
    ) -> dict:
        """
        Analyze a user's posts and return top posts in each category.

        Args:
            posts: List of post objects
            recent_days: Number of days for "recent" analysis

        Returns:
            Dict with keys: 'top_recent', 'top_all_time', 'most_ratioed'
            Each value is a tuple of (post, score) or None
        """
        logger.info(f"Analyzing {len(posts)} posts...")

        result = {
            'top_recent': self.find_top_recent_post(posts, recent_days),
            'top_all_time': self.find_top_all_time_post(posts),
            'most_ratioed': self.find_most_ratioed_post(posts)
        }

        # Log summary
        for category, data in result.items():
            if data:
                logger.info(f"✓ Found {category}")
            else:
                logger.warning(f"✗ No {category} found")

        return result
