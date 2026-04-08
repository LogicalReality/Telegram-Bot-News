import telebot
import schedule
import time
import feedparser
from datetime import datetime, timedelta
import threading
import os
import json
import pytz
from dotenv import load_dotenv

# ==========================================
# 1. CONFIGURACIÓN Y PERSISTENCIA
# ==========================================
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("¡Error! No se encontró el TOKEN en el archivo .env")

bot = telebot.TeleBot(TOKEN)
noticias_enviadas = set()

# Cargar usuarios desde un archivo para no perderlos al reiniciar
ARCHIVO_USUARIOS = "usuarios.json"
try:
    with open(ARCHIVO_USUARIOS, "r") as f:
        usuarios_activos = set(json.load(f))
except FileNotFoundError:
    usuarios_activos = set()

def guardar_usuarios():
    with open(ARCHIVO_USUARIOS, "w") as f:
        json.dump(list(usuarios_activos), f)

# ==========================================
# 2. KEYWORDS + SCORING
# ==========================================
KEYWORDS = {
    'hormuz': 5, 'trump': 4, 'iran': 4, 'ataque': 5,
    'militar': 4, 'fed': 5, 'inflación': 5, 'inflation': 5,
    'binance': 3, 'bnb': 3, 'crypto': 2, 'bitcoin': 2, 'btc': 2,
    'launchpool': 4, 'burn': 4
}

def calcular_score(texto):
    return sum(peso for palabra, peso in KEYWORDS.items() if palabra in texto.lower())

def clasificar_nivel(score):
    if score >= 8:
        return "🔴 ALTO IMPACTO"
    elif score >= 4:
        return "🟡 IMPACTO MEDIO"
    return None

# ==========================================
# 3. FUENTES RSS
# ==========================================
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=crypto&hl=es-419&gl=US&ceid=US:es-419",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.investing.com/rss/news_25.rss"
]

# ==========================================
# 4. ENVÍO GLOBAL SEGURO
# ==========================================
def enviar_a_todos(mensaje):
    if not usuarios_activos:
        print("⚠️ No hay usuarios suscritos para enviar el mensaje.")
        return

    # No enviar alertas de apertura/cierre en fines de semana
    if datetime.utcnow().weekday() >= 5 and "APERTURA" in mensaje:
        print("💤 Fin de semana detectado, alerta de mercado omitida.")
        return

    enviados = 0
    for user_id in usuarios_activos:
        try:
            bot.send_message(user_id, mensaje, parse_mode='Markdown', disable_web_page_preview=False)
            enviados += 1
        except Exception as e:
            print(f"❌ Error enviando a {user_id}: {e}")
    
    print(f"✅ Mensaje enviado a {enviados} usuario(s).")

# ==========================================
# 5. LÓGICA DE NOTICIAS
# ==========================================
def buscar_noticias(manual=False, chat_id=None):
    if not manual:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 Ejecutando búsqueda automática de noticias...")
        
    global noticias_enviadas
    encontradas = 0

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                titulo = entry.title.lower()
                noticia_id = titulo[:80] # Usamos los primeros 80 caracteres como ID único

                if noticia_id in noticias_enviadas:
                    continue

                score = calcular_score(titulo)
                nivel = clasificar_nivel(score)

                if nivel:
                    mensaje = f"{nivel}\n\n📰 *{entry.title}*\n\n📊 Score: {score}\n🔗 [Leer noticia]({entry.link})"

                    if manual and chat_id:
                        bot.send_message(chat_id, mensaje, parse_mode='Markdown')
                    else:
                        enviar_a_todos(mensaje)

                    noticias_enviadas.add(noticia_id)
                    encontradas += 1

                    if manual and encontradas >= 5:
                        return
        except Exception as e:
            print(f"❌ Error leyendo RSS {url}: {e}")

# ==========================================
# 6. ESTADO DE MERCADOS
# ==========================================
HORARIOS_MERCADOS = {
    "Asia (Tokio)": ("00:00", "09:00"),
    "Europa (Londres)": ("08:00", "16:00"),
    "EE.UU. (NY)": ("13:00", "21:00"),
    "Pacífico (Sídney)": ("22:00", "07:00")
}

def obtener_estado_mercados():
    ahora_utc = datetime.utcnow()
    dia_semana = ahora_utc.weekday()
    texto = "📅 *ESTADO DE LOS MERCADOS (UTC)*\n\n"
    es_finde = dia_semana >= 5 

    for mercado, (abre_str, cierra_str) in HORARIOS_MERCADOS.items():
        h_abre = int(abre_str.split(':')[0])
        h_cierra = int(cierra_str.split(':')[0])
        
        inicio = ahora_utc.replace(hour=h_abre, minute=0, second=0, microsecond=0)
        fin = ahora_utc.replace(hour=h_cierra, minute=0, second=0, microsecond=0)

        if h_abre > h_cierra:
            if ahora_utc.hour >= h_abre:
                fin += timedelta(days=1)
            else:
                inicio -= timedelta(days=1)

        abierto = inicio <= ahora_utc < fin

        if es_finde:
            estado = "💤 FIN DE SEMANA"
            dias_para_lunes = (7 - dia_semana)
            proxima_apertura = inicio + timedelta(days=dias_para_lunes)
            diff = proxima_apertura - ahora_utc
            texto += f"• *{mercado}:* {estado}\n  └ ⏳ Abre en: {diff.days}d {diff.seconds//3600}h {(diff.seconds//60)%60}m\n\n"
        else:
            if abierto:
                estado = "🟢 ABIERTO"
                diff = fin - ahora_utc
                texto += f"• *{mercado}:* {estado}\n  └ ⏳ Cierra en: {diff.seconds//3600}h {(diff.seconds//60)%60}m\n\n"
            else:
                estado = "🔴 CERRADO"
                if ahora_utc >= fin: inicio += timedelta(days=1)
                diff = inicio - ahora_utc
                texto += f"• *{mercado}:* {estado}\n  └ ⏳ Abre en: {diff.seconds//3600}h {(diff.seconds//60)%60}m\n\n"
    return texto

# ==========================================
# 7. COMANDOS TELEGRAM
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    usuarios_activos.add(message.chat.id)
    guardar_usuarios() # Guardamos en el JSON
    bot.send_message(message.chat.id, "✅ Te has suscrito a las alertas automáticas. ¡No te perderás nada!")
    print(f"Nuevo usuario suscrito: {message.chat.id}")

@bot.message_handler(commands=['noticias'])
def noticias(message):
    bot.send_message(message.chat.id, "🔎 Buscando noticias de alto impacto...")
    buscar_noticias(manual=True, chat_id=message.chat.id)

@bot.message_handler(commands=['mercados'])
def mercados(message):
    bot.send_message(message.chat.id, obtener_estado_mercados(), parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status(message):
    ahora_utc = datetime.utcnow()
    tz_local = pytz.timezone('Europe/Madrid')
    ahora_local = datetime.now(tz_local)

    texto = f"""
✅ *SISTEMA OPERATIVO*

👥 Usuarios: {len(usuarios_activos)}
📡 Fuentes RSS: {len(RSS_FEEDS)}

🕒 *RELOJES:*
🌐 UTC: `{ahora_utc.strftime('%H:%M:%S')}`
🏠 España: `{ahora_local.strftime('%H:%M:%S')}`
"""
    bot.send_message(message.chat.id, texto, parse_mode='Markdown')

# ==========================================
# 8. PLANIFICADOR (SCHEDULE)
# ==========================================
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Buscar noticias cada 3 minutos
schedule.every(3).minutes.do(buscar_noticias)

# Alertas de mercados (Horas en UTC)
alertas_config = {
    "00:00": "🌏 *APERTURA ASIA*\n⚠️ Posibles movimientos en crypto",
    "08:00": "🇪🇺 *APERTURA LONDRES*\n📊 Entra volumen institucional",
    "13:00": "🇺🇸 *APERTURA NEW YORK*\n🔥 Alta volatilidad esperada",
    "21:00": "🔒 *CIERRE NEW YORK*\n📉 Baja liquidez"
}

for hora, msj in alertas_config.items():
    schedule.every().day.at(hora).do(enviar_a_todos, f"⏰ {msj}")

# ==========================================
# 9. EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    print("===================================")
    print("🚀 BOT CRIPTO INICIADO CORRECTAMENTE")
    print("===================================")
    print(f"Usuarios cargados de disco: {len(usuarios_activos)}")
    
    # Hilo para que el schedule no bloquee a Telegram
    threading.Thread(target=run_schedule, daemon=True).start()
    
    # Bucle principal de Telegram
    bot.infinity_polling()