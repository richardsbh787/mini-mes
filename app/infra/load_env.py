import os

def load_env_if_needed() -> None:
    """
    Lightweight .env loader (no extra dependency).
    Only loads if SUPABASE_URL not set.
    """
    if os.getenv("SUPABASE_URL"):
        return

    path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v