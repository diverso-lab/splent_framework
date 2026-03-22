import logging

logger = logging.getLogger(__name__)


def build_jinja_context(app, base_context: dict) -> dict:
    """
    Combines the base context with variables injected by feature context processors.
    """
    ctx = dict(base_context)  # defensive copy — do not mutate the caller's dict

    for fn in getattr(app, "context_processors", []):
        try:
            result = fn(app)
            if isinstance(result, dict):
                ctx.update(result)
            else:
                logger.warning(
                    "Feature context processor %s returned %s instead of dict",
                    fn,
                    type(result),
                )
        except Exception as e:
            logger.exception("Error in feature context processor %s: %s", fn, e)

    return ctx
