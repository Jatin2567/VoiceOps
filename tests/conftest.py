"""Keep provider credentials out of unit tests."""
import pytest

@pytest.fixture(autouse=True)
def isolated_provider_environment(monkeypatch):
    for name in ("GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "REDIS_URL"):
        monkeypatch.setenv(name, "")
