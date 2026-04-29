import os
from dotenv import load_dotenv
from supabase import create_client, Client

"""
=== SQL SNIPPETS PARA SUPABASE ===
Ejecuta esto en el SQL Editor de Supabase para crear las tablas:

CREATE TABLE users (
    chat_id BIGINT PRIMARY KEY,
    news_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sent_news (
    news_hash TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Si ya tenés la tabla users, agregá la columna nueva:
-- ALTER TABLE users ADD COLUMN news_enabled BOOLEAN DEFAULT TRUE;
===================================
"""

load_dotenv()

# Inicialización del cliente Supabase
url: str = os.getenv("SUPABASE_URL", "").strip()
key: str = os.getenv("SUPABASE_KEY", "").strip()

# Limpieza de URL para evitar el error "double rest/v1"
if url.endswith("/rest/v1/"):
    url = url[:-9]
elif url.endswith("/rest/v1"):
    url = url[:-8]

if not url or not key:
    print("⚠️ ADVERTENCIA: SUPABASE_URL o SUPABASE_KEY no están configurados.")

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    supabase = None
    print(f"Error inicializando Supabase: {e}")


def get_all_users() -> list:
    """Devuelve una lista con todos los chat_id de los usuarios."""
    if not supabase: return []
    try:
        response = supabase.table("users").select("chat_id").execute()
        return [user["chat_id"] for user in response.data]
    except Exception as e:
        print(f"Error en get_all_users: {e}")
        return []

def add_user(chat_id: int) -> dict:
    """Añade un usuario. Devuelve dict con status y news_enabled."""
    if not supabase: return {"status": "error"}
    try:
        response = supabase.table("users").select("chat_id, news_enabled").eq("chat_id", chat_id).execute()
        if response.data:
            return {"status": "existing", "news_enabled": response.data[0]["news_enabled"]}
        supabase.table("users").insert({"chat_id": chat_id, "news_enabled": True}).execute()
        return {"status": "new", "news_enabled": True}
    except Exception as e:
        print(f"Error en add_user: {e}")
        return {"status": "error"}


def set_news_enabled(chat_id: int, enabled: bool) -> str:
    """Activa o desactiva las noticias automáticas para un usuario. Crea el usuario si no existe. Devuelve 'ok' o 'error'."""
    if not supabase: return "error"
    try:
        supabase.table("users").upsert({"chat_id": chat_id, "news_enabled": enabled}).execute()
        return "ok"
    except Exception as e:
        print(f"Error en set_news_enabled: {e}")
        return "error"


def get_news_subscribers() -> list:
    """Devuelve los chat_id de usuarios con news_enabled=True."""
    if not supabase: return []
    try:
        response = supabase.table("users").select("chat_id").eq("news_enabled", True).execute()
        return [user["chat_id"] for user in response.data]
    except Exception as e:
        print(f"Error en get_news_subscribers: {e}")
        return []

def is_news_sent(news_hash: str) -> bool:
    """Comprueba si una noticia ya fue enviada buscando su hash."""
    if not supabase: return False
    try:
        response = supabase.table("sent_news").select("news_hash").eq("news_hash", news_hash).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error en is_news_sent: {e}")
        return False

def mark_news_sent(news_hash: str) -> bool:
    """Guarda el hash de la noticia en la base de datos para marcarla como enviada."""
    if not supabase: return False
    try:
        supabase.table("sent_news").upsert({"news_hash": news_hash}).execute()
        return True
    except Exception as e:
        print(f"Error en mark_news_sent: {e}")
        return False
