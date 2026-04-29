import os
import sys
from http.server import BaseHTTPRequestHandler
import telebot

# Añadir el root del proyecto al path para importar bot.services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services import obtener_precios, obtener_estado_mercados, buscar_noticias
from bot.db import add_user, set_news_enabled

token = os.getenv('TELEGRAM_TOKEN', '')
bot = telebot.TeleBot(token, threaded=False)

# ===== MANEJADORES DE COMANDOS =====

@bot.message_handler(commands=['start'])
def cmd_start(m):
    result = add_user(m.chat.id)
    status = result.get("status")
    news_on = result.get("news_enabled", True)
    if status == "new":
        bot.reply_to(m, "🚀 **Bot Serverless Activo**\n• Suscrito a noticias automáticas.\n• /help : Ver comandos disponibles")
    elif status == "existing":
        state = "**activadas**" if news_on else "**desactivadas**"
        toggle = "/unsubscribe para desactivar" if news_on else "/subscribe para reactivar"
        bot.reply_to(m, f"🤖 **Ya estás registrado.** Las noticias automáticas están {state}. Usá {toggle} o /help para ver comandos.")
    else:
        bot.reply_to(m, "❌ Error de conexión con la base de datos. Intentá más tarde.")

@bot.message_handler(commands=['help'])
def cmd_help(m):
    bot.reply_to(m, "📋 **Comandos disponibles:**\n\n"
                    "• /start — Suscribirse al bot\n"
                    "• /subscribe — Activar noticias automáticas\n"
                    "• /unsubscribe — Desactivar noticias automáticas\n"
                    "• /prices — Precios de BTC, ETH y BNB\n"
                    "• /mercados — Estado de bolsas mundiales\n"
                    "• /noticias — Top 3 noticias de impacto")

@bot.message_handler(commands=['subscribe'])
def cmd_subscribe(m):
    result = set_news_enabled(m.chat.id, True)
    if result == "ok":
        bot.reply_to(m, "✅ Noticias automáticas **activadas**. Recibirás noticias cada 15 min. Usá /unsubscribe para desactivar.")
    else:
        bot.reply_to(m, "❌ Primero debés usar /start para registrarte, o hay un error de conexión.")

@bot.message_handler(commands=['unsubscribe'])
def cmd_unsubscribe(m):
    result = set_news_enabled(m.chat.id, False)
    if result == "ok":
        bot.reply_to(m, "🔇 Noticias automáticas **desactivadas**. Seguís pudiendo usar /noticias para consultar a demanda. Usá /subscribe para reactivar.")
    else:
        bot.reply_to(m, "❌ Primero debés usar /start para registrarte, o hay un error de conexión.")

@bot.message_handler(commands=['prices'])
def cmd_prices(m):
    bot.send_message(m.chat.id, obtener_precios(), parse_mode='Markdown')

@bot.message_handler(commands=['mercados'])
def cmd_mercados(m):
    bot.send_message(m.chat.id, obtener_estado_mercados(), parse_mode='Markdown')

@bot.message_handler(commands=['noticias'])
def cmd_noticias(m):
    bot.send_chat_action(m.chat.id, 'typing')
    noticias = buscar_noticias()
    if not noticias:
        bot.reply_to(m, "No he encontrado noticias de alto impacto en los feeds en este momento.")
    else:
        bot.reply_to(m, "📰 **Top 3 Noticias de Impacto Actuales:**")
        for n in noticias:
            bot.send_message(m.chat.id, n['message'], parse_mode='Markdown')

# ===== HANDLER PARA VERCEL =====

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Pasar la actualización a telebot
            json_string = post_data.decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            print(f"Error procesando Webhook: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Error")
