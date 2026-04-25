# 🤖 BNB Sentinel Bot (Serverless Edition)

Un bot financiero para Telegram diseñado para ejecutarse 100% de manera gratuita en la nube usando una arquitectura orientada a eventos (Serverless). Monitorea precios de criptomonedas, aperturas de mercados globales y filtra noticias RSS de alto impacto.

## 🏗 Arquitectura

El bot ha sido refactorizado para abandonar el polling tradicional y operar bajo:

- **Vercel (Compute):** Funciones Serverless en Python para manejar los comandos de los usuarios vía Webhooks y un Cron Job automático.
- **Supabase (PostgreSQL):** Base de datos en la nube para persistir los usuarios suscritos y mantener un caché de las noticias enviadas, evitando mensajes duplicados.

## 🚀 Guía de Configuración Rápida

Para desplegar tu propio bot gratis, sigue estos pasos:

### 1. Configurar Supabase (Base de Datos)

1. Crea un proyecto gratuito en [Supabase](https://supabase.com/).
2. Ve a la sección **SQL Editor** y ejecuta este snippet para crear las tablas necesarias:

```sql
CREATE TABLE users (
    chat_id BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sent_news (
    news_hash TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

3. Ve a `Project Settings -> API` y guarda tu **URL** y tu **anon/public KEY**.

### 2. Configurar Variables de Entorno (Local y Vercel)

Crea un archivo `.env` en la raíz de este proyecto (solo para desarrollo local) y asegúrate de agregar estas mismas variables en el panel de **Vercel** (`Settings -> Environment Variables`):

```env
TELEGRAM_TOKEN=tu_token_de_botfather
SUPABASE_URL=tu_url_de_supabase
SUPABASE_KEY=tu_key_anon_de_supabase
```

### 3. Despliegue en Vercel

1. Sube este repositorio a tu cuenta de GitHub.
2. Inicia sesión en [Vercel](https://vercel.com/), haz clic en "Add New Project" e importa tu repositorio.
3. Asegúrate de añadir las 3 variables de entorno antes de darle a "Deploy".
4. Vercel te dará una URL (ej. `https://mi-bot-financiero.vercel.app`).

### 4. Conectar Telegram (Webhook)

Telegram necesita saber a dónde enviar los mensajes. Abre tu navegador y pega esta URL (reemplazando con tus datos reales):

```
https://api.telegram.org/bot<TU_TELEGRAM_TOKEN>/setWebhook?url=https://<TU_DOMINIO_VERCEL>/api/webhook
```

Si todo sale bien, verás un JSON diciendo `"Webhook was set"`.

## 📂 Estructura del Proyecto

- `api/webhook.py`: El punto de entrada que Telegram llama cuando alguien escribe un comando.
- `api/cron.py`: El script que Vercel llama automáticamente cada 15 minutos (configurado en `vercel.json`) para buscar noticias.
- `bot/services.py`: Contiene la lógica pura (cálculos, APIs externas, RSS).
- `bot/db.py`: Funciones auxiliares para interactuar con Supabase.

## ⏰ Configuración del Monitor (Cada 15 min)

Debido a que Vercel Hobby limita los Crons nativos a una vez al día, hemos implementado un **Trigger Externo** usando GitHub Actions:

1. El archivo `.github/workflows/cron.yml` ya está configurado.
2. Cada 15 minutos, GitHub lanzará un pequeño proceso que llamará a tu URL de Vercel para activar la búsqueda de noticias.
3. Asegúrate de que tu URL en `.github/workflows/cron.yml` sea la correcta (reemplaza `telegram-bot-news.vercel.app` por tu dominio real si es diferente).

## 🛠 Comandos Disponibles en Telegram

- `/start` - Suscribe al usuario a las alertas de noticias automáticas.
- `/prices` - Devuelve el precio actual de BTC, ETH y BNB.
- `/mercados` - Informa qué bolsas mundiales están abiertas en este momento.
- `/noticias` - Información sobre el estado del monitor de noticias.