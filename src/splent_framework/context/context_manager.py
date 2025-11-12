def build_jinja_context(app, base_context: dict) -> dict:
    """
    It combines the base context of the core with the variables injected by the features.
    """
    ctx = dict(base_context)  # copia defensiva

    for fn in getattr(app, "context_processors", []):
        try:
            result = fn(app)
            if isinstance(result, dict):
                ctx.update(result)
            else:
                print(f"⚠️ Feature context processor {fn} returned {type(result)}")
        except Exception as e:
            print(f"⚠️ Error in feature context processor {fn}: {e}")

    return ctx
