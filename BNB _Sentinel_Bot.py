import time, requests, feedparser, threading, os, json,pytz, schedule, telebot
from datetime import datetime, timedelta
from dotenv import load_dotenv


# ==========================================
# 1. CONFIGURACIÓN Y PERSISTENCIA (CORREGIDO)
# ==========================================
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("¡Error! No se encontró el TOKEN en el archivo .env")

bot = telebot.TeleBot(TOKEN)
noticias_enviadas = set()

# Cargar usuarios asegurando que el archivo existe y es legible
ARCHIVO_USUARIOS = "usuarios.json"

def cargar_usuarios():
    if not os.path.exists(ARCHIVO_USUARIOS):
        with open(ARCHIVO_USUARIOS, "w") as f:
            json.dump([], f)
        return set()
    try:
        with open(ARCHIVO_USUARIOS, "r") as f:
            data = json.load(f)
            return set(data) if data else set()
    except (json.JSONDecodeError, IOError):
        print("⚠️ Error leyendo usuarios.json, iniciando lista vacía.")
        return set()

usuarios_activos = cargar_usuarios()

def guardar_usuarios():
    try:
        with open(ARCHIVO_USUARIOS, "w") as f:
            json.dump(list(usuarios_activos), f)
        # Forzar que el sistema operativo escriba el archivo ahora mismo
        os.sync() if hasattr(os, 'sync') else f.flush()
    except IOError as e:
        print(f"❌ Error crítico escribiendo usuarios: {e}")

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
    if score >= 8: return "🔴 ALTO IMPACTO"
    elif score >= 4: return "🟡 IMPACTO MEDIO"
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
# 4. ENVÍO GLOBAL SEGURO (CON FILTRO FIN DE SEMANA)
# ==========================================
def enviar_a_todos(mensaje):
    if not usuarios_activos:
        return

    # Bloqueo de alertas de mercado en fin de semana (Sábado=5, Domingo=6)
    ahora_utc = datetime.utcnow()
    es_finde = ahora_utc.weekday() >= 5
    palabras_mercado = ["APERTURA", "CIERRE", "ASIA", "LONDRES", "NEW YORK"]
    
    if es_finde and any(x in mensaje for x in palabras_mercado):
        print(f"💤 Omitiendo alerta de mercado en finde: {mensaje[:30]}...")
        return

    for user_id in usuarios_activos:
        try:
            bot.send_message(user_id, mensaje, parse_mode='Markdown')
        except Exception as e:
            print(f"❌ Error enviando a {user_id}: {e}")

# ==========================================
# 5. LÓGICA DE NOTICIAS
# ==========================================
def buscar_noticias(manual=False, chat_id=None):
    if not manual:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 Búsqueda automática...")
    
    global noticias_enviadas
    encontradas = 0

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                titulo = entry.title.lower()
                noticia_id = titulo[:80]

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
                    if manual and encontradas >= 5: return
        except Exception as e:
            print(f"❌ Error RSS {url}: {e}")

# ==========================================
# 6. ALERTAS DE PRECIOS Y MERCADOS
# ==========================================
def alerta_precios_top(symbol_to_check=None):
    url = "https://api.binance.com/api/v3/ticker/price"
    symbols_map = {"BTCUSDT": "₿ BTC", "ETHUSDT": "Ξ ETH", "BNBUSDT": "🔶 BNB"}
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        precios = {item['symbol']: float(item['price']) for item in data if item['symbol'] in symbols_map}
        
        # SI LA FUNCIÓN SE LLAMA DESDE UN COMANDO (ej: para obtener un solo precio)
        if symbol_to_check:
            # Limpiamos el símbolo por si viene como BTC/USDT
            clean_symbol = symbol_to_check.replace("/", "")
            price = precios.get(clean_symbol, "N/A")
            return f"${price:,.2f}" if price != "N/A" else "Error"

        # SI LA FUNCIÓN SE EJECUTA AUTOMÁTICAMENTE (Alerta global)
        mensaje = "💰 *ACTUALIZACIÓN DE PRECIOS*\n\n"
        for sym in symbols_map:
            if sym in precios:
                mensaje += f"• *{symbols_map[sym]}:* `${precios[sym]:,.2f}`\n"
        
        enviar_a_todos(mensaje)

    except Exception as e:
        print(f"❌ Error en alerta_precios: {e}")
        return "Error"

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
    es_finde = dia_semana >= 4 

    for mercado, (abre_str, cierra_str) in HORARIOS_MERCADOS.items():
        h_abre = int(abre_str.split(':')[0])
        h_cierra = int(cierra_str.split(':')[0])
        
        # Crear objetos de hora para hoy
        inicio = ahora_utc.replace(hour=h_abre, minute=0, second=0, microsecond=0)
        fin = ahora_utc.replace(hour=h_cierra, minute=0, second=0, microsecond=0)

        # Ajuste para mercados que cierran al día siguiente (como Sídney o EE.UU.)
        if h_abre > h_cierra:
            if ahora_utc.hour >= h_abre:
                fin += timedelta(days=1)
            else:
                inicio -= timedelta(days=1)

        # REGLA DE ORO: Si es fin de semana, nada está abierto
        if es_finde:
            estado = "💤 FIN DE SEMANA"
            # Calcular cuánto falta para el lunes a la hora de apertura
            dias_para_lunes = (7 - dia_semana)
            proxima_apertura = inicio.replace(day=ahora_utc.day) + timedelta(days=dias_para_lunes)
            diff = proxima_apertura - ahora_utc
            texto += f"• *{mercado}:* {estado}\n  └ ⏳ Abre en: {diff.days}d {diff.seconds//3600}h\n\n"
        else:
            # Lógica normal de lunes a viernes
            abierto = inicio <= ahora_utc < fin
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
    if message.chat.id not in usuarios_activos:
        usuarios_activos.add(message.chat.id)
        guardar_usuarios()
        bot.send_message(message.chat.id, "✅ Suscripción activada. Recibirás alertas de precios y noticias.")
    else:
        bot.send_message(message.chat.id, "ℹ️ Ya estás en la lista de usuarios activos.")

@bot.message_handler(commands=['noticias'])
def noticias(message):
    bot.send_message(message.chat.id, "🔎 Buscando noticias de alto impacto...")
    buscar_noticias(manual=True, chat_id=message.chat.id)

@bot.message_handler(commands=['mercados'])
def mercados(message):
    bot.send_message(message.chat.id, obtener_estado_mercados(), parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status(message):
    bot.send_message(message.chat.id, f"📊 *Estado del Bot*\n\n"
                                      f"👥 Usuarios activos: {len(usuarios_activos)}\n"
                                      f"⏰ Alertas programadas: {len(schedule.jobs)}"
                                      , parse_mode='Markdown')

@bot.message_handler(commands=['prices']) # O el comando que tengas
def prices(message):
    try:
        btc_p = alerta_precios_top('BTCUSDT')
        eth_p = alerta_precios_top('ETHUSDT')
        bnb_p = alerta_precios_top('BNBUSDT')
        
        texto = f"📊 *PRECIOS ACTUALES*\n\n"
        texto += f"🔶 BTC: `{btc_p}`\n"
        texto += f"🔶 ETH: `{eth_p}`\n"
        texto += f"🔶 BNB: `{bnb_p}`"
        
        bot.reply_to(message, texto, parse_mode='Markdown')
    except Exception as e:
        print(f"Error en comando prices: {e}")
# ==========================================
# 8. PLANIFICADOR
# ==========================================
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

schedule.every(3).minutes.do(buscar_noticias)
schedule.every(1).hours.do(alerta_precios_top)

alertas_config = {
    "00:00": "🌏 *APERTURA ASIA*",
    "08:00": "🇪🇺 *APERTURA LONDRES*",
    "13:00": "🇺🇸 *APERTURA NEW YORK*",
    "21:00": "🔒 *CIERRE NEW YORK*"
}

for hora, msj in alertas_config.items():
    schedule.every().day.at(hora).do(enviar_a_todos, f"⏰ {msj}")

# ==========================================
# 9. EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    print(f"🚀 Bot iniciado. Usuarios registrados: {len(usuarios_activos)}")
    threading.Thread(target=run_schedule, daemon=True).start()
    bot.infinity_polling()