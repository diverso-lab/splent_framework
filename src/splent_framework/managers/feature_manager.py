import os
import sys
import importlib
import tomllib
from dataclasses import dataclass
from typing import List, Tuple
from flask import Blueprint
from splent_cli.utils.path_utils import PathUtils


# =========================
# Excepciones específicas
# =========================
class FeatureError(RuntimeError):
    pass


# =========================
# Modelo de referencia
# =========================
@dataclass(frozen=True)
class FeatureRef:
    org: str           # org original (p.ej. "splent-io")
    org_safe: str      # org para namespace python (p.ej. "splent_io")
    name: str          # p.ej. "splent_feature_auth"
    version: str       # p.ej. "v1.0.0"

    def import_name(self) -> str:
        return f"{self.org_safe}.{self.name}"


class FeatureManager:
    """
    Carga e integra features como paquetes Python bajo namespace org_safe (p.ej. 'splent_io').

    Estructura esperada de cada feature (symlink en el producto hacia la cache real):
      <product>/features/<org_safe>/<name>@<version> -> /workspace/.splent_cache/features/<org_safe>/<name>@<version>
        └── src/
            └── <org_safe>/
                └── <name>/
                    ├── __init__.py
                    ├── routes.py      (opcional, aquí lo tratamos como obligatorio si strict=True)
                    ├── models.py      (opcional idem)
                    ├── hooks.py       (opcional idem)
                    └── config.py      (opcional con inject_config(app))
    """

    _already_registered = False

    def __init__(self, app, *, strict: bool = True, default_version: str = "v1.0.0"):
        self.app = app
        self.strict = strict
        self.default_version = default_version

    # =========================
    # API pública
    # =========================
    def register_features(self) -> None:
        
        if FeatureManager._already_registered:
            return
        FeatureManager._already_registered = True

        splent_app = os.getenv("SPLENT_APP")
        if not splent_app:
            raise FeatureError("SPLENT_APP not set")

        product_features_dir = os.path.join(
            PathUtils.get_working_dir(), splent_app, "features"
        )

        features_raw = self._load_feature_list_from_pyproject(splent_app)
        if not features_raw:
            print("ℹ️ No features declared.")
            return

        refs = [self._parse_feature_entry(e) for e in features_raw]

        # Carga estricta de cada feature
        for ref in refs:
            self._load_one_feature(product_features_dir, ref)

    # =========================
    # Carga de configuración
    # =========================
    def _load_feature_list_from_pyproject(self, splent_app: str) -> List[str]:
        pyproject_path = os.path.join(PathUtils.get_working_dir(), splent_app, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            raise FeatureError(f"pyproject.toml not found at {pyproject_path}")

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            features = data["project"]["optional-dependencies"].get("features", [])
            if not isinstance(features, list):
                raise FeatureError("Invalid [project.optional-dependencies.features] format (expected list)")
            # normalizamos espacios o entradas vacías
            features = [x.strip() for x in features if isinstance(x, str) and x.strip()]
            return features
        except Exception as e:
            raise FeatureError(f"Failed to parse features in {pyproject_path}: {e}") from e

    def _parse_feature_entry(self, entry: str) -> FeatureRef:
        # Formatos admitidos:
        #   org/name@vX.Y.Z  |  name@vX.Y.Z  |  org/name  |  name
        if "/" in entry:
            org, rest = entry.split("/", 1)
        else:
            org, rest = "splent-io", entry

        name, sep, version = rest.partition("@")
        version = version if sep else None
        if not name:
            raise FeatureError(f"Invalid feature entry (empty name): {entry}")

        org_safe = org.replace("-", "_")
        return FeatureRef(org=org, org_safe=org_safe, name=name, version=version)

    # =========================
    # Carga de una feature
    # =========================

    def _load_one_feature(self, product_features_dir: str, ref: FeatureRef) -> None:
        """
        Valida estructura, prepara sys.path, importa el paquete y realiza integración (config, init, blueprints).
        Soporta features con o sin versión declarada.
        """

        # 1️⃣ Determinar la ruta del enlace (link_path)
        if ref.version:
            # Si hay versión explícita, buscar el enlace versionado
            link_path = os.path.join(product_features_dir, ref.org_safe, f"{ref.name}@{ref.version}")
        else:
            # Si no hay versión, buscar enlace simple
            link_path = os.path.join(product_features_dir, ref.org_safe, ref.name)

        # 2️⃣ Si no existe, aplicar fallback inteligente
        if not os.path.exists(link_path):
            import glob
            # Buscar cualquier versión disponible de esa feature
            candidates = sorted(glob.glob(os.path.join(product_features_dir, ref.org_safe, f"{ref.name}@*")))
            if candidates:
                link_path = candidates[0]
                print(f"   ⚠️ Using available version for {ref.name}: {os.path.basename(link_path)}")
            else:
                raise FeatureError(f"Feature link not found: {link_path}")

        # 3️⃣ Resolver paths internos (src/org_safe/feature_name)
        feature_dir = os.path.realpath(link_path)
        src_root, org_ns_dir, pkg_dir = self._resolve_feature_paths(feature_dir, ref)

        # 4️⃣ Añadir src_root a sys.path (para habilitar import splent_io.x)
        self._ensure_namespace_on_syspath(src_root)

        import_name = ref.import_name()

        # 5️⃣ Importar el módulo raíz
        module = self._import_strict(import_name, err=f"Cannot import {import_name}")

        # 6️⃣ Carga estricta de submódulos típicos
        self._import_submodule_strict(import_name, "routes")
        self._import_submodule_strict(import_name, "models")
        self._import_submodule_strict(import_name, "hooks")

        # 7️⃣ Configuración (si existe)
        self._inject_config_if_present(import_name)

        # 8️⃣ Inicialización personalizada (si existe)
        self._call_init_feature_if_present(module, import_name)

        # 9️⃣ Registro de blueprints
        self._register_blueprints_on_module(module, import_name)

    def _resolve_feature_paths(self, feature_dir: str, ref: FeatureRef) -> Tuple[str, str, str]:
        """
        Devuelve (src_root, org_ns_dir, pkg_dir) y valida su existencia.
        """
        src_root = os.path.join(feature_dir, "src")
        org_ns_dir = os.path.join(src_root, ref.org_safe)
        pkg_dir = os.path.join(org_ns_dir, ref.name)

        if not os.path.isdir(src_root):
            raise FeatureError(f"Missing src/ in feature: {feature_dir}")
        if not os.path.isdir(org_ns_dir):
            raise FeatureError(f"Missing namespace folder: {org_ns_dir}")
        if not os.path.isdir(pkg_dir):
            raise FeatureError(f"Feature package not found: {pkg_dir}")

        return src_root, org_ns_dir, pkg_dir

    def _ensure_namespace_on_syspath(self, src_root: str) -> None:
        """
        Inserta el directorio 'src/' en sys.path (no 'src/splent_io'),
        para habilitar 'import splent_io.splent_feature_*'.
        """
        if src_root not in sys.path:
            sys.path.insert(0, src_root)
            print(f"📚 Source path added: {src_root}")

    # =========================
    # Integraciones
    # =========================
    def _inject_config_if_present(self, import_name: str) -> None:
        try:
            config_mod = importlib.import_module(f"{import_name}.config")
        except ModuleNotFoundError:
            if self.strict:
                raise FeatureError(f"{import_name}.config not found")
            return
        except Exception as e:
            raise FeatureError(f"Error importing {import_name}.config: {e}") from e

        if hasattr(config_mod, "inject_config"):
            try:
                config_mod.inject_config(self.app)
            except Exception as e:
                raise FeatureError(f"Error in {import_name}.config.inject_config: {e}") from e
        elif self.strict:
            raise FeatureError(f"{import_name}.config lacks inject_config(app)")

    def _call_init_feature_if_present(self, module, import_name: str) -> None:
        if hasattr(module, "init_feature"):
            try:
                module.init_feature(self.app)
            except Exception as e:
                raise FeatureError(f"Error in {import_name}.init_feature(app): {e}") from e
        elif self.strict:
            raise FeatureError(f"{import_name} lacks init_feature(app)")

    def _register_blueprints_on_module(self, module, import_name: str) -> None:
        """Registra todos los blueprints definidos tanto en el módulo raíz como en submódulos (routes, etc.)."""
        registered = 0
        candidates = [module]

        # Intentar añadir submódulos comunes si ya se han importado
        for sub in ("routes", "models", "hooks"):
            fullname = f"{import_name}.{sub}"
            if fullname in sys.modules:
                candidates.append(sys.modules[fullname])

        for mod in candidates:
            for attr in dir(mod):
                try:
                    obj = getattr(mod, attr)
                except Exception as e:
                    print(f"      ⚠️ Error accessing attribute '{attr}': {e}")
                    continue

                # Mostrar todos los atributos que parezcan relevantes
                if isinstance(obj, Blueprint):
                    if obj.name in self.app.blueprints:
                        if self.strict:
                            raise FeatureError(f"Blueprint name collision: {obj.name} in {mod.__name__}")
                        continue

                    try:
                        self.app.register_blueprint(obj)
                        registered += 1
                    except Exception as e:
                        print(f"      ❌ Failed to register blueprint '{obj.name}': {e}")

        if registered == 0:
            print(f"   ⚠️ No blueprints registered for {import_name}")
            if self.strict:
                raise FeatureError(f"No blueprints found in {import_name}")

    # =========================
    # Utilidades de import
    # =========================
    def _import_strict(self, name: str, err: str):
        try:
            return importlib.import_module(name)
        except Exception as e:
            raise FeatureError(f"{err}: {e}") from e

    def _import_submodule_strict(self, base, sub):
        """
        Importa un submódulo de una feature (routes, models, hooks...).
        Si el módulo no existe, lo ignora silenciosamente.
        Si hay error real al importarlo, lanza FeatureError.
        """
        try:
            importlib.import_module(f"{base}.{sub}")
        except ModuleNotFoundError:
            pass
        except Exception as e:
            # Otros errores sí se consideran graves
            raise FeatureError(f"Cannot import {base}.{sub}: {e}") from e

    def get_features(self) -> list[str]:
        """
        Devuelve las features declaradas en el pyproject.toml del producto activo.
        No valida ni resuelve versiones; simplemente lista el contenido de
        [project.optional-dependencies.features].
        """
        splent_app = os.getenv("SPLENT_APP")
        if not splent_app:
            raise FeatureError("SPLENT_APP not set")

        features = self._load_feature_list_from_pyproject(splent_app)
        return features or []