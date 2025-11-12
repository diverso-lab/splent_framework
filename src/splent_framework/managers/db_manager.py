from flask_migrate import Migrate
from splent_cli.utils.path_utils import PathUtils
from splent_framework.db import db


class MigrateManager:
    def __init__(self, app):
        self.app = app
        self.migrate = Migrate(directory=PathUtils.get_migrations_dir())
        self.init()

    def init(self):
        db.init_app(self.app)
        self.migrate.init_app(self.app, db)
