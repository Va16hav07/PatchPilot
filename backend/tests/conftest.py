import os

# Tests drop and recreate collections: never point them at the real database.
os.environ["MONGO_URI"] = os.environ.get("TEST_MONGO_URI", "mongodb://127.0.0.1:27017")
os.environ["MONGO_DB"] = "thali_test"
os.environ["GOOGLE_CLIENT_ID"] = "test-client"
os.environ["SESSION_SECRET"] = "test-secret-at-least-32-bytes-long!!"
