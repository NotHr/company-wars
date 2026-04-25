import sys
import importlib

# pytest's Package.setup() calls importlib.import_module("__init__") for the
# project root because the directory name "company-wars" contains a hyphen and
# is therefore not a valid Python identifier — pytest cannot derive the package
# name and falls back to module_name = "__init__". Pre-registering the editable
# install's module makes sys.modules lookup short-circuit before any re-import
# attempt, letting the relative imports in __init__.py succeed.
if "__init__" not in sys.modules:
    importlib.import_module("comany_fights")
    sys.modules["__init__"] = sys.modules["comany_fights"]
