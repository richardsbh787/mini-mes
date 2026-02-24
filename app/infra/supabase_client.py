import os
from functools import lru_cache
from supabase import create_client, Client

SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_SCHEMA_ENV = "SUPABASE_SCHEMA"

@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.getenv(SUPABASE_URL_ENV)
    key = os.getenv(SUPABASE_KEY_ENV)
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)

def sb_table(table_name: str):
    schema = os.getenv(SUPABASE_SCHEMA_ENV, "public")
    return get_supabase().schema(schema).table(table_name)