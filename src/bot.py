"""Main bot orchestration and mention processing."""

import logging
import time
from datetime import datetime
from typing import Optional, Set
from .client import BlueskyClient
from .analytics import PostAnalytics
from .formatter import ResponseFormatter
from .config import Config


logger = logging.getLogger(__name__)


class MentionTracker:
    """Track processed mentions to avoid duplicates."""

    def __init__(self):
        """Initialize mention tracker."""
        self.processed_uris: Set[str] = set()
        self.last_seen_at: Optional[str] = None

    def is_processed(self, uri: str) -> bool:
        """Check if a mention has been processed."""
        return uri in self.processed_uris

    def mark_processed(self, uri: str) -> None:
        """Mark a mention as processed."""
        self.processed_uris.add(uri)
        logger.debug(f"Marked {uri} as processed")

    def update_last_seen(self, timestamp: str) -> None:
        """Update the last seen timestamp."""
        self.last_seen_at = timestamp


class BlueskyBot:
    """Main bot for processing mentions and responding with analytics."""

    def __init__(
        self,
        client: BlueskyClient,
        config: Config,
        analytics: Optional[PostAnalytics] = None,
        formatter: Optional[ResponseFormatter] = None
    ):
        """
        Initialize the bot.

        Args:
            client: Authenticated Bluesky client
            config: Configuration object
            analytics: Optional analytics engine (creates default if None)
            formatter: Optional response formatter (creates default if None)
        """
        self.client = client
        self.config = config
        self.analytics = analytics or PostAnalytics(
            min_engagement_for_ratio=config.MIN_ENGAGEMENT_FOR_RATIO
        )
        self.formatter = formatter or ResponseFormatter()
        self.tracker = MentionTracker()
        self.running = False

    def process_mention(self, mention: any) -> bool:
        """
        Process a single mention and respond with analytics.

        Args:
            mention: Mention notification object

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            # Extract mention details
            mention_uri = mention.uri
            mention_cid = mention.cid

            # Check if already processed
            if self.tracker.is_processed(mention_uri):
                logger.debug(f"Skipping already processed mention: {mention_uri}")
                return True

            # Get the author (person who mentioned us)
            author = mention.author
            author_did = author.did
            author_handle = author.handle if hasattr(author, 'handle') else None

            logger.info(f"Processing mention from @{author_handle} ({author_did})")

            # Fetch the author's posts
            posts = self.client.fetch_all_posts(
                actor=author_did,
                max_posts=self.config.MAX_POSTS
            )

            if not posts:
                logger.warning(f"No posts found for @{author_handle}")
                response = self.formatter.format_no_posts_response(author_handle)
                self.client.send_reply(
                    text=response,
                    parent_uri=mention_uri,
                    parent_cid=mention_cid
                )
                self.tracker.mark_processed(mention_uri)
                return True

            # Analyze the posts
            analysis = self.analytics.analyze_user_posts(
                posts=posts,
                recent_days=self.config.RECENT_DAYS
            )

            # Format the thread responses
            thread_posts = self.formatter.create_thread_responses(
                top_recent=analysis['top_recent'],
                top_all_time=analysis['top_all_time'],
                most_ratioed=analysis['most_ratioed'],
                handle=author_handle,
                recent_days=self.config.RECENT_DAYS
            )

            # Send the thread
            # First post is a reply to the mention
            logger.info(f"Sending thread with {len(thread_posts)} posts")

            first_post_uri, first_post_cid = self.client.send_reply(
                text=thread_posts[0],
                parent_uri=mention_uri,
                parent_cid=mention_cid
            )

            if not first_post_uri:
                logger.error("Failed to send first post in thread")
                return False

            # Subsequent posts are replies to the first post
            current_uri = first_post_uri
            current_cid = first_post_cid
            root_uri = first_post_uri
            root_cid = first_post_cid

            for i, post_text in enumerate(thread_posts[1:], start=2):
                logger.info(f"Sending post {i} of {len(thread_posts)}")

                reply_uri, reply_cid = self.client.send_reply(
                    text=post_text,
                    parent_uri=current_uri,
                    parent_cid=current_cid,
                    root_uri=root_uri,
                    root_cid=root_cid
                )

                if reply_uri:
                    current_uri = reply_uri
                    current_cid = reply_cid
                else:
                    logger.error(f"Failed to send post {i} in thread")
                    # Continue anyway - partial thread is better than none

                # Small delay between posts
                time.sleep(1)

            logger.info(f"✓ Successfully responded to @{author_handle}")
            self.tracker.mark_processed(mention_uri)
            return True

        except Exception as e:
            logger.error(f"Error processing mention: {e}", exc_info=True)

            # Try to send an error response
            try:
                error_response = self.formatter.format_error_response(
                    error_message=str(e),
                    handle=author_handle if 'author_handle' in locals() else None
                )
                self.client.send_reply(
                    text=error_response,
                    parent_uri=mention_uri,
                    parent_cid=mention_cid
                )
            except Exception as reply_error:
                logger.error(f"Failed to send error response: {reply_error}")

            return False

    def poll_mentions(self) -> None:
        """
        Main polling loop - check for new mentions and process them.

        This runs continuously until stopped.
        """
        logger.info("Starting mention polling loop...")
        self.running = True

        while self.running:
            try:
                # Fetch new mentions
                mentions = self.client.get_mentions(
                    seen_at=self.tracker.last_seen_at
                )

                if mentions:
                    logger.info(f"Processing {len(mentions)} new mentions")

                    for mention in mentions:
                        self.process_mention(mention)

                    # Update last seen timestamp
                    if mentions:
                        latest_mention = mentions[0]
                        if hasattr(latest_mention, 'indexed_at'):
                            self.tracker.update_last_seen(latest_mention.indexed_at)
                            self.client.update_seen_notifications(latest_mention.indexed_at)

                else:
                    logger.debug("No new mentions")

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                self.running = False
                break

            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)
                # Continue running despite errors

            # Sleep before next poll
            logger.debug(f"Sleeping for {self.config.POLL_INTERVAL}s")
            time.sleep(self.config.POLL_INTERVAL)

        logger.info("Polling loop stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        logger.info("Stopping bot...")
        self.running = False
