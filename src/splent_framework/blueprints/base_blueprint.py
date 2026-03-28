# base_blueprint.py
from flask import Blueprint, Response, abort
import os
import sys
import importlib


class BaseBlueprint(Blueprint):
    def __init__(
        self,
        name,
        import_name,  # typically __name__ of the feature package
        static_folder=None,
        static_url_path=None,
        template_folder=None,
        url_prefix=None,
        subdomain=None,
        url_defaults=None,
        root_path=None,
    ):
        super().__init__(
            name,
            import_name,
            static_folder=static_folder,
            static_url_path=static_url_path,
            template_folder=template_folder,
            url_prefix=url_prefix,
            subdomain=subdomain,
            url_defaults=url_defaults,
            root_path=root_path,
        )

        # Resolve feature package directory via Python's module system
        try:
            module = sys.modules.get(import_name) or importlib.import_module(
                import_name
            )
            pkg_dir = os.path.dirname(module.__file__)
        except (ImportError, AttributeError) as e:
            raise RuntimeError(f"Cannot resolve package path for {import_name}: {e}")

        # Root directory of this feature package (src/splent_io/splent_feature_xxx)
        self.feature_code_path = pkg_dir

        # Fall back to the feature's own templates/ if none was passed
        if self.template_folder is None:
            self.template_folder = os.path.join(self.feature_code_path, "templates")

        self.add_asset_routes()

    def add_asset_routes(self):
        assets_folder = os.path.join(self.feature_code_path, "assets")
        if os.path.exists(assets_folder):
            self.add_url_rule(
                f"/{self.name}/<path:subfolder>/<path:filename>",
                "assets",
                self.send_file,
            )

    def _resolve_asset_path(self, subfolder, filename):
        """Find an asset file, checking workspace root first (for compiled assets)."""
        # Primary: feature_code_path (where the module was imported from)
        primary = os.path.join(self.feature_code_path, "assets", subfolder, filename)
        if os.path.isfile(primary):
            return os.path.realpath(primary), os.path.realpath(
                os.path.join(self.feature_code_path, "assets", subfolder)
            )

        # Fallback: workspace root (editable feature may have compiled dist/ here)
        workspace = os.getenv("WORKING_DIR")
        if workspace:
            # feature_code_path looks like .../src/splent_io/splent_feature_X
            # We need just the feature package name
            feature_name = os.path.basename(self.feature_code_path)
            org_name = os.path.basename(os.path.dirname(self.feature_code_path))
            fallback = os.path.join(
                workspace, feature_name, "src", org_name, feature_name,
                "assets", subfolder, filename,
            )
            if os.path.isfile(fallback):
                return os.path.realpath(fallback), os.path.realpath(
                    os.path.join(
                        workspace, feature_name, "src", org_name, feature_name,
                        "assets", subfolder,
                    )
                )

        return None, None

    def send_file(self, subfolder, filename):
        allowed_subfolders = {"js", "css", "dist"}
        if subfolder not in allowed_subfolders:
            abort(404)

        requested_path, base_dir = self._resolve_asset_path(subfolder, filename)

        if not requested_path:
            abort(404)

        # Prevent path traversal: resolved path must stay inside base_dir
        if (
            not requested_path.startswith(base_dir + os.sep)
            and requested_path != base_dir
        ):
            abort(403)

        if filename.endswith(".js"):
            mimetype = "application/javascript"
        elif filename.endswith(".css"):
            mimetype = "text/css"
        else:
            mimetype = "text/plain"

        with open(requested_path, "r") as f:
            return Response(f.read(), mimetype=mimetype)
