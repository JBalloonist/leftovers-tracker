import os

# Allow the app's dev-only default password and secret key during tests.
os.environ.setdefault("LEFTOVERS_DEV", "1")
