# base_blueprint.py
from flask import Blueprint, Response, abort
import os
import sys
import importlib


class BaseBlueprint(Blueprint):
    def __init__(
        self,
        name,
        import_name,  # <-- viene de la feature, suele ser __name__
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

        # En lugar de peinar /workspace/<app>/features..., resolvemos por el módulo Python:
        try:
            module = sys.modules.get(import_name) or importlib.import_module(
                import_name
            )
            pkg_dir = os.path.dirname(module.__file__)
        except Exception as e:
            raise RuntimeError(
                f"No puedo resolver la ruta de paquete para {import_name}: {e}"
            )

        # Aquí vive tu feature (src/splent_io/splent_feature_xxx)
        self.feature_code_path = pkg_dir

        # Si no te pasan template_folder, usa el de la feature
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

    def send_file(self, subfolder, filename):
        file_path = os.path.join(self.feature_code_path, "assets", subfolder, filename)

        if filename == "webpack.config.js":
            abort(403, description="Access to this file is forbidden")

        if os.path.exists(file_path) and subfolder in ["js", "css", "dist"]:
            try:
                if filename.endswith(".js"):
                    mimetype = "application/javascript"
                elif filename.endswith(".css"):
                    mimetype = "text/css"
                else:
                    mimetype = "text/plain"
                with open(file_path, "r") as f:
                    return Response(f.read(), mimetype=mimetype)
            except FileNotFoundError:
                abort(404, description=f"File not found: {file_path}")
        abort(404, description=f"Invalid path or file: {subfolder}/{filename}")
