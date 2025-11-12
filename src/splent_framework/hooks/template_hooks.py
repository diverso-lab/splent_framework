# splent_framework/template_hooks.py

_hooks = {}


def register_template_hook(name, func):
    _hooks.setdefault(name, []).append(func)


def get_template_hooks(name):
    return _hooks.get(name, [])
