"""
utils/compat.py - Keep pandas behaving the same on every Python version.

pandas 3 (installed automatically on Python 3.13/3.14) keeps empty cells as NaN after
.astype(str), where pandas 2 gives the text "nan"/"None". The app relies on the
pandas 2 behaviour, so switch the new text mode off when it exists.
"""
import pandas as pd

try:
    pd.set_option("future.infer_string", False)
except Exception:  # very old pandas without the option: nothing to do
    pass
