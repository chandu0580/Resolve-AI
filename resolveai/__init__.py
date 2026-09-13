"""ResolveAI: an AppleSupport AI support agent built on the Customer Support on Twitter dataset."""
import os as _os

# Must run before anything imports transformers: a broken TensorFlow install on the dev machine otherwise gets imported.
_os.environ.setdefault("USE_TF", "0")
_os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
_os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

__version__ = "1.0.0"
