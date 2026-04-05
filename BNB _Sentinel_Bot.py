import telebot
import schedule
import time
import feedparser
from datetime import datetime, timedelta
import threading
import os
from dotenv import load_dotenv

# ==========================================
# 1. CONFIG
# ==========================================
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("¡Error! No se encontró el TOKEN en el archivo .env")
bot = telebot.TeleBot(TOKEN)

usuarios_activos = set()
noticias_enviadas = set()

# ==========================================
# 2. KEYWORDS + SCORING
# ==========================================
KEYWORDS = {
    'hormuz': 5, 'trump': 4, 'iran': 4, 'ataque': 5,
    'militar': 4, 'fed': 5, 'inflación': 5,
    'binance': 3, 'bnb': 3, 'crypto': 2,
    'launchpool': 4, 'burn': 4
}

def calcular_score(texto):
    return sum(peso for palabra, peso in KEYWORDS.items() if palabra in texto)

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
# 4. ENVÍO GLOBAL
# ==========================================
def enviar_a_todos(mensaje):
    for user_id in usuarios_activos:
        try:
            bot.send_message(user_id, mensaje, parse_mode='Markdown')
        except:
            pass

# ==========================================
# 5. NOTICIAS
# ==========================================
def buscar_noticias(manual=False, chat_id=None):
    global noticias_enviadas
    encontradas = 0

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries[:10]:
            titulo = entry.title.lower()
            noticia_id = titulo[:80]

            if noticia_id in noticias_enviadas and not manual:
                continue

            score = calcular_score(titulo)
            nivel = clasificar_nivel(score)

            if nivel:
                mensaje = f"""{nivel}

📰 *{entry.title}*

📊 Score: {score}
🔗 [Leer noticia]({entry.link})
"""

                if manual and chat_id:
                    bot.send_message(chat_id, mensaje, parse_mode='Markdown')
                else:
                    enviar_a_todos(mensaje)

                noticias_enviadas.add(noticia_id)
                encontradas += 1

                if manual and encontradas >= 5:
                    return

# ==========================================
# 6. MERCADOS GLOBALES
# ==========================================
HORARIOS_MERCADOS = {
    "Asia (Tokio)": ("00:00", "09:00"),
    "Europa (Londres)": ("08:00", "16:00"),
    "EE.UU. (NY)": ("13:00", "21:00"),
    "Pacífico (Sídney)": ("22:00", "07:00")
}

def obtener_estado_mercados():
    ahora_utc = datetime.utcnow()
    dia_semana = ahora_utc.weekday()  # 0=Lunes, 5=Sábado, 6=Domingo
    texto = "📅 *ESTADO DE LOS MERCADOS (UTC)*\n\n"

    # Verificación de Fin de Semana
    es_finde = dia_semana >= 5 

    for mercado, (abre_str, cierra_str) in HORARIOS_MERCADOS.items():
        h_abre = int(abre_str.split(':')[0])
        h_cierra = int(cierra_str.split(':')[0])
        
        # Crear objetos datetime para hoy para calcular diferencias
        inicio = ahora_utc.replace(hour=h_abre, minute=0, second=0, microsecond=0)
        fin = ahora_utc.replace(hour=h_cierra, minute=0, second=0, microsecond=0)

        # Manejo de mercados que cruzan la medianoche (Sídney)
        if h_abre > h_cierra:
            if ahora_utc.hour >= h_abre:
                fin += timedelta(days=1)
            else:
                inicio -= timedelta(days=1)

        abierto = inicio <= ahora_utc < fin

        # Lógica de Estado y Tiempo
        if es_finde:
            estado = "💤 FIN DE SEMANA"
            # Calculamos para el lunes (dia 0)
            dias_para_lunes = (7 - dia_semana)
            proxima_apertura = inicio.replace(hour=h_abre) + timedelta(days=dias_para_lunes)
            diff = proxima_apertura - ahora_utc
            horas, rem = divmod(diff.seconds, 3600)
            minutos, _ = divmod(rem, 60)
            info_tiempo = f"⏳ Abre en: {diff.days}d {horas}h {minutos}m"
        else:
            if abierto:
                estado = "🟢 ABIERTO"
                diff = fin - ahora_utc
                horas, rem = divmod(diff.seconds, 3600)
                minutos, _ = divmod(rem, 60)
                info_tiempo = f"⏳ Cierra en: {horas}h {minutos}m"
            else:
                estado = "🔴 CERRADO"
                # Si ya cerró hoy, la apertura es mañana
                if ahora_utc >= fin:
                    inicio += timedelta(days=1)
                diff = inicio - ahora_utc
                horas, rem = divmod(diff.seconds, 3600)
                minutos, _ = divmod(rem, 60)
                info_tiempo = f"⏳ Abre en: {horas}h {minutos}m"

        texto += f"• *{mercado}:* {estado}\n  └ {info_tiempo}\n\n"

    return texto

def alerta_mercados():
    ahora_dt = datetime.utcnow()
    # No enviar alertas de apertura/cierre en fin de semana
    if ahora_dt.weekday() >= 5:
        return

    ahora = ahora_dt.strftime('%H:%M')
    alertas = {
        "00:00": "🌏 *APERTURA ASIA*\n⚠️ Posibles movimientos en crypto",
        "08:00": "🇪🇺 *APERTURA LONDRES*\n📊 Entra volumen institucional",
        "13:00": "🇺🇸 *APERTURA NEW YORK*\n🔥 Alta volatilidad esperada",
        "21:00": "🔒 *CIERRE NEW YORK*\n📉 Baja liquidez"
    }

    if ahora in alertas:
        enviar_a_todos(f"⏰ {alertas[ahora]}")

# ==========================================
# 7. COMANDOS
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    usuarios_activos.add(message.chat.id)
    bot.send_message(message.chat.id, "✅ Te has suscrito a las alertas.")

@bot.message_handler(commands=['noticias'])
def noticias(message):
    bot.send_message(message.chat.id, "🔎 Buscando noticias...")
    buscar_noticias(manual=True, chat_id=message.chat.id)

@bot.message_handler(commands=['mercados'])
def mercados(message):
    texto = obtener_estado_mercados()
    bot.send_message(message.chat.id, texto, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status(message):
    texto = f"""
✅ BOT ACTIVO

👥 Usuarios: {len(usuarios_activos)}
📡 Fuentes: {len(RSS_FEEDS)}
🧠 Keywords: {len(KEYWORDS)}
⏰ Hora: {datetime.now().strftime('%H:%M')}
"""
    bot.send_message(message.chat.id, texto)

# ==========================================
# 8. SCHEDULE
# ==========================================
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

schedule.every(3).minutes.do(buscar_noticias)
schedule.every().minute.do(alerta_mercados)

threading.Thread(target=run_schedule).start()

# ==========================================
# 9. RUN
# ==========================================
print("BOT PRO MULTIUSUARIO ACTIVO 🚀")
bot.infinity_polling()