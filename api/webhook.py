import os
import sys
from http.server import BaseHTTPRequestHandler
import telebot

# Añadir el root del proyecto al path para importar bot.services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services import obtener_precios, obtener_estado_mercados, buscar_noticias
from bot.db import add_user

token = os.getenv('TELEGRAM_TOKEN', '')
bot = telebot.TeleBot(token, threaded=False)

# ===== MANEJADORES DE COMANDOS =====

@bot.message_handler(commands=['start'])
def cmd_start(m):
    chat_id = m.chat.id
    if add_user(chat_id):
        bot.reply_to(m, "🚀 **Bot Serverless Activo**\n• Te has suscrito a las noticias de alto impacto.\n• /prices : Precios Cripto\n• /mercados : Estado de bolsas\n• /noticias : Top noticias actuales")
    else:
        bot.reply_to(m, "⚠️ Hubo un error al suscribirte o la base de datos no está conectada.")

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
