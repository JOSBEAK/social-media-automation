from src.core.registry import PlatformBundle, Registry
from src.handlers.actions.instagram_comment import InstagramCommentHandler
from src.handlers.actions.instagram_like import InstagramLikeHandler
from src.handlers.actions.instagram_repost import InstagramRepostHandler
from src.handlers.actions.twitter_comment import TwitterCommentHandler
from src.handlers.actions.twitter_like import TwitterLikeHandler
from src.handlers.actions.twitter_repost import TwitterRepostHandler
from src.handlers.platforms.instagram_handler import InstagramHandler
from src.handlers.platforms.twitter_handler import TwitterHandler


def create_default_registry() -> Registry:
    registry = Registry()
    registry.register_bundle(
        PlatformBundle(
            InstagramHandler(),
            (InstagramLikeHandler(), InstagramCommentHandler(), InstagramRepostHandler()),
        )
    )
    registry.register_bundle(
        PlatformBundle(
            TwitterHandler(),
            (TwitterLikeHandler(), TwitterCommentHandler(), TwitterRepostHandler()),
        )
    )
    return registry
