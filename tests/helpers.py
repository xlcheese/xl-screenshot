"""Set-up shared by every test: import this first.

- the app's code is imported from this checkout (usr/lib/xl-screenshot), not
  from an installed copy
- HOME is a new empty folder, so tests never touch your real settings
- text is in English, whatever your desktop language (test_i18n changes it)
"""
import os
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
LIB = os.path.join(ROOT, "usr", "lib", "xl-screenshot")
BIN = os.path.join(ROOT, "usr", "bin")

sys.path.insert(0, LIB)
os.environ["HOME"] = tempfile.mkdtemp(prefix="xl-test-home-")
os.environ["LANGUAGE"] = "en"
os.environ.pop("GDK_SCALE", None)

# Pictures the tests save of the windows they check (handy for a look by eye).
# They go in the temporary home folder, or wherever XL_TEST_PICTURES says.
PICTURES = os.environ.get("XL_TEST_PICTURES") or os.environ["HOME"]
os.makedirs(PICTURES, exist_ok=True)
