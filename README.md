# SPLENT Framework

Core library for building modular, feature-driven Flask applications using Software Product Line principles.

## What it provides

- **Manager pattern** — Pluggable subsystem managers (features, config, migrations, sessions, Jinja, error handling)
- **Feature system** — Modular features with lifecycle tracking, UVL-based dependency ordering, and per-feature Alembic migrations
- **Base classes** — `BaseBlueprint`, `BaseRepository`, `BaseService`, `BaseSeeder`, `GenericResource`
- **App factory** — `create_app()` wires everything together with env-aware feature loading

## Quick start

```python
from splent_framework.managers.feature_manager import FeatureManager

def create_app(config_name="development"):
    app = Flask(__name__)
    # ... config, db, sessions ...
    FeatureManager(app, strict=False).register_features()
    return app
```

## Requirements

- Python 3.13+
- Flask 3.1+
- SQLAlchemy 2.0+

## Documentation

Full documentation at **[docs.splent.io](https://docs.splent.io)**

## License

Creative Commons CC BY 4.0 - SPLENT - Diverso Lab
