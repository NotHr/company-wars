import importlib
import sys

try:
    importlib.import_module("comany_fights")
    sys.modules["__init__"] = sys.modules["comany_fights"]
except ImportError:
    pass
