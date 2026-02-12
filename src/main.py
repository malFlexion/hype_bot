"""Main entry point for the Bluesky bot."""

import argparse
import logging
import signal
import sys
import threading
from flask import Flask
from .config import Config
from .client import BlueskyClient
from .bot import BlueskyBot
from .analytics import PostAnalytics
from .formatter import ResponseFormatter


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Flask app for health checks
app = Flask(__name__)
bot_instance = None


@app.route('/health')
def health_check():
    """Health check endpoint for Fly.io."""
    return {
        'status': 'healthy',
        'bot_running': bot_instance.running if bot_instance else False
    }, 200


@app.route('/')
def index():
    """Root endpoint."""
    return {
        'name': 'Bluesky Engagement Analytics Bot',
        'status': 'running',
        'version': '1.0.0'
    }, 200


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}")
    if bot_instance:
        bot_instance.stop()
    sys.exit(0)


def run_bot():
    """Run the bot in a separate thread."""
    global bot_instance

    try:
        # Validate configuration
        logger.info("Loading configuration...")
        Config.validate()

        # Initialize client
        logger.info("Initializing Bluesky client...")
        client = BlueskyClient(
            handle=Config.BLUESKY_HANDLE,
            app_password=Config.BLUESKY_APP_PASSWORD
        )

        # Login
        logger.info("Authenticating with Bluesky...")
        client.login()

        # Initialize bot
        logger.info("Starting bot...")
        bot_instance = BlueskyBot(client=client, config=Config)

        # Start polling
        bot_instance.poll_mentions()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_test(handle: str):
    """Run analytics on a specific handle and print the results (no replies posted)."""
    logger.info(f"TEST MODE: Analyzing @{handle}")

    # Initialize client and login
    Config.validate()
    client = BlueskyClient(
        handle=Config.BLUESKY_HANDLE,
        app_password=Config.BLUESKY_APP_PASSWORD
    )
    client.login()

    # Check if user follows the bot
    if not client.is_following_bot(handle):
        print(f"\n@{handle} does not follow the bot. They would be asked to follow first.")
        return

    # Fetch posts
    logger.info(f"Fetching posts for @{handle}...")
    posts = client.fetch_all_posts(actor=handle, max_posts=Config.MAX_POSTS)

    if not posts:
        print(f"\nNo posts found for @{handle}")
        return

    print(f"\nFetched {len(posts)} posts for @{handle}\n")

    # Analyze
    analytics = PostAnalytics(min_engagement_for_ratio=Config.MIN_ENGAGEMENT_FOR_RATIO)
    analysis = analytics.analyze_user_posts(posts=posts, recent_days=Config.RECENT_DAYS)

    # Format and print
    formatter = ResponseFormatter()
    thread_posts = formatter.create_thread_responses(
        top_recent=analysis['top_recent'],
        top_all_time=analysis['top_all_time'],
        most_ratioed=analysis['most_ratioed'],
        handle=handle,
        recent_days=Config.RECENT_DAYS
    )

    print("=" * 60)
    for i, post_text in enumerate(thread_posts, start=1):
        print(f"--- Post {i} ---")
        print(post_text)
        print()
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Bluesky Engagement Analytics Bot")
    parser.add_argument(
        "--test",
        metavar="HANDLE",
        help="Test mode: analyze a handle and print results without posting replies"
    )
    args = parser.parse_args()

    if args.test:
        run_test(args.test)
        return

    logger.info("=" * 60)
    logger.info("Bluesky Engagement Analytics Bot")
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Run Flask server for health checks
    logger.info(f"Starting health check server on port {Config.HEALTH_CHECK_PORT}...")
    app.run(
        host='0.0.0.0',
        port=Config.HEALTH_CHECK_PORT,
        debug=False,
        use_reloader=False
    )


if __name__ == '__main__':
    main()
