# MathRelaxing — Context Handoff

> Generado el 2026-05-18. Úsalo como contexto de arranque para una nueva sesión de IA agéntica.

---

## El proyecto

**mathrelaxing.store** — tienda de arte matemático digital.
- **Stack:** FastAPI + SQLAlchemy + SQLite + Jinja2 + Resend (email) + Telegram bot
- **Servidor:** `/var/www/mathrelaxing.store/` en Ubuntu, systemd service `mathrelaxing`, uvicorn en `127.0.0.1:8000`
- **Python env:** `/var/www/mathrelaxing.store/.venv`
- **Restart:** `systemctl restart mathrelaxing`
- **Logs:** `journalctl -u mathrelaxing -n 50 --no-pager`

---

## Estructura de archivos clave

```
/var/www/mathrelaxing.store/
├── main.py                          # App FastAPI, rutas HTML principales
├── .env                             # Variables de entorno (ver sección)
├── database.py                      # SQLAlchemy engine + get_db()
├── models/
│   └── product.py                   # Todos los modelos SQLAlchemy
├── routers/
│   ├── webhooks.py                  # Webhooks PayPal, Printful, Whop
│   ├── lowpoly.py                   # Generador Low Poly + rutas de crédito
│   ├── products.py
│   ├── orders.py
│   └── ...
├── services/
│   ├── email.py                     # Envío de emails con Resend
│   ├── telegram.py                  # Notificaciones Telegram
│   ├── whop.py                      # Cliente Whop (verify, get_plans, etc.)
│   └── ...
├── templates/
│   ├── lowpoly.html                 # Página principal /lowpoly
│   ├── lowpoly_credit.html          # Página de canje de crédito
│   └── lowpoly_access.html          # Página de reenvío de link por email
└── static/
    ├── examples/web/                # 32 imágenes de ejemplo (parámetros de demo)
    ├── previews/lowpoly/            # Previews watermarked de jobs
    ├── purchases/lowpoly/           # Archivos finales de jobs pagados
    └── img/
        ├── logo-whop.png            # Logo 512×512 para Whop
        └── banner-whop.jpg          # Banner 1920×1080 para Whop
```

---

## Variables de entorno (`.env`)

```env
APP_ENV=production
DATABASE_URL=sqlite:////var/www/mathrelaxing.store/mathrelaxing.db

RESEND_API_KEY=re_cgoAPWP8_B6vhG7Uzjp54rZZEoxSsJUJg
TELEGRAM_BOT_TOKEN=8779385667:AAGd2nJqcmjvndvyY0GHyFcsLKOJCkayasI
TELEGRAM_CHAT_ID=5774052858

PAYPAL_CLIENT_ID=AT6BclVGpxxOZF_...
PAYPAL_SECRET=EMHPH_vua9jAFy...
PAYPAL_MODE=live
PAYPAL_WEBHOOK_ID=20E90518TH089473Y

WHOP_API_KEY=apik_QhK142oAoT309_...   # ⚠️ COMPROMETIDA — regenerar en Whop dashboard
WHOP_COMPANY_ID=biz_K21tvFR0jxGtVz
WHOP_WEBHOOK_SECRET=ws_3f282df576...
WHOP_LOWPOLY_PLAN_1=                   # Vacío — productos Low Poly eliminados de Whop
WHOP_LOWPOLY_PLAN_5=                   # Vacío — se recrearán cuando se retome

LEMON_SQUEEZY_API_KEY=eyJ0eXAi...
LEMON_SQUEEZY_STORE_ID=351960
LEMON_SQUEEZY_WEBHOOK_SECRET=mr-whsec-mathrelaxing-2024
```

---

## Modelos de base de datos (models/product.py)

### LowPolyJob
```python
class LowPolyJob(Base):
    __tablename__ = "lowpoly_jobs"
    id             # INT PK
    token          # UUID único — identifica el job
    lemon_order_id # STRING nullable
    customer_email
    customer_name
    params_json    # JSON con parámetros de generación
    coloring_url   # URL del PNG de colorear
    colored_url    # URL del PNG de referencia de colores
    extra_files_json
    pack_size      # INT, cantidad de imágenes del job
    status         # "pending" | "paid" | "expired"
    created_at
```

### LowPolyCredit
```python
class LowPolyCredit(Base):
    __tablename__ = "lowpoly_credits"
    id             # INT PK
    token          # UUID único — es la llave de la URL de canje
    whop_id        # STRING — ID del pago en Whop (idempotencia)
    customer_email
    customer_name
    pack_size      # INT: 1 o 5
    used_count     # INT: empieza en 0
    status         # "unused" | "partial" | "exhausted"
    created_at
    used_at        # DATETIME nullable
```

### Purchase (productos digitales)
```python
class Purchase(Base):
    __tablename__ = "purchases"
    id, lemon_order_id, product_id, customer_email, customer_name
    download_token  # UUID para descargar
    download_count, max_downloads
    status         # "pending" | "paid" | "delivered" | "expired"
    ref_source, item_index
    paypal_order_id  # también usado como "whop:{whop_id}" para compras Whop
    expires_at, created_at
```

---

## Rutas HTTP relevantes

### main.py (rutas sin prefijo /api)
```
GET  /lowpoly                        → lowpoly.html (página principal del generador)
GET  /lowpoly/access                 → lowpoly_access.html (reenvío de link por email)
POST /lowpoly/access                 → busca créditos por email y reenvía link
GET  /lowpoly/credit/{token}         → lowpoly_credit.html (canje de crédito)
POST /lowpoly/credit/{token}/generate → genera imagen y consume un crédito
GET  /experiences/{experience_id}    → lowpoly_access.html (entry point desde Whop, iframe-safe)
```

### routers/lowpoly.py (prefijo /api)
```
GET  /api/lowpoly/upload             → página de upload (flujo directo sin crédito)
POST /api/lowpoly/upload             → genera watermarked preview
POST /api/gpt/lowpoly/checkout-pack  → crea LowPolyJob + PayPal order
GET  /api/lowpoly/paypal-return      → captura pago PayPal y envía archivos
GET  /api/lowpoly/result/{token}     → estado del job
GET  /api/lowpoly/credit/{token}     → (duplicado, usar ruta sin /api)
POST /api/lowpoly/credit/{token}/generate → (duplicado, usar ruta sin /api)
```

### routers/webhooks.py (prefijo /api)
```
POST /api/webhooks/whop              → webhook Whop (Standard Webhooks)
POST /api/webhooks/paypal            → webhook PayPal (legacy)
POST /api/webhooks/printful          → webhook Printful
POST /api/webhooks/lemonsqueezy      → webhook LemonSqueezy (legacy)
```

---

## Webhook de Whop — implementación correcta

**Protocolo:** Standard Webhooks (NO es HMAC simple sobre el body)

**Headers que envía Whop:**
- `webhook-id` — ID único del evento
- `webhook-timestamp` — Unix timestamp en segundos
- `webhook-signature` — `v1,<base64(HMAC-SHA256)>`

**Contenido firmado:** `{webhook-id}.{webhook-timestamp}.{body}`

**Verificación en código:**
```python
import base64, whop_sdk

def _whop_client():
    secret = os.getenv("WHOP_WEBHOOK_SECRET", "")
    webhook_key = base64.b64encode(secret.encode()).decode() if secret else None
    return whop_sdk.Whop(
        api_key=os.getenv("WHOP_API_KEY", ""),
        webhook_key=webhook_key,
    )

# En el handler:
event = _whop_client().webhooks.unwrap(body_str, headers=dict(request.headers))
```

**Dependencia necesaria:** `whop-sdk[webhooks]` (instala `standardwebhooks`)

**Nombres de eventos correctos (con punto, no guión bajo):**
- `payment.succeeded` → compra one-time
- `membership.activated` → membresía activada
- `refund.created` → reembolso
- `dispute.created` / `dispute.updated` → disputa

**Webhook registrado en Whop:**
- ID: `hook_TdG6sInvS1Jum`
- URL: `https://mathrelaxing.store/api/webhooks/whop`
- Eventos: `payment.succeeded`, `membership.activated`, `refund.created`, `dispute.created`, `dispute.updated`

---

## Flujo Low Poly Credit (implementado, Whop desconectado)

El backend está 100% implementado y funcional. Los productos de Whop fueron eliminados temporalmente. Para reactivar:

1. Recrear productos en Whop (1 credit $2.99, 5 credits $9.99)
2. Obtener los plan IDs y llenar `WHOP_LOWPOLY_PLAN_1` y `WHOP_LOWPOLY_PLAN_5` en `.env`
3. El webhook ya maneja el resto automáticamente

**Flujo completo:**
```
Usuario compra en Whop
  → webhook POST /api/webhooks/whop (payment.succeeded)
  → backend crea LowPolyCredit en DB (token UUID, pack_size 1 o 5)
  → email con link: https://mathrelaxing.store/lowpoly/credit/{token}
  → usuario abre link → lowpoly_credit.html (demo interactivo)
  → sube foto + elige parámetros + ingresa email → POST generate
  → backend genera PNG full-res (2550×3300 px, 300 DPI)
  → archivos servidos en pantalla + email de descarga
  → used_count++ → status "partial" o "exhausted"
```

**Parámetros de generación:**
- `colors`: 8, 12, 16 o 20
- `grid`: "square" o "hex"
- `orientation`: "portrait" o "landscape"

**Demo interactivo:** 32 imágenes pre-generadas en `/static/examples/web/`
- Formato: `{colors}_{grid}_{orientation}_{coloring|colored}.jpg`
- Ejemplo: `16_square_portrait_colored.jpg`

**Semáforo de concurrencia:** `asyncio.Semaphore(2)` en `routers/lowpoly.py`

---

## Whop — estado actual

| Item | Estado |
|---|---|
| Cuenta | `whop.com/mathrelaxing` |
| Company ID | `biz_K21tvFR0jxGtVz` |
| API Key | `apik_QhK142oAoT309_...` ⚠️ comprometida, regenerar |
| Webhook | Configurado y funcional (`hook_TdG6sInvS1Jum`) |
| Productos Low Poly | ❌ Eliminados (se recrean cuando se retome) |
| App custom "Low Poly" | `app_DudsMtDuQqt1xd` (existe en Whop, no tiene delete API) |
| 27 productos digitales | ✅ Publicados con galería (8 imágenes c/u) y descripciones |
| Logo Whop (512×512) | `/static/img/logo-whop.png` — subido vía API |
| Banner Whop | `/static/img/banner-whop.jpg` — subir manualmente en "Editar marca" |

### Notas de la API de Whop
- Usa SDK: `whop_sdk` (Python), `whop_sdk.Whop(api_key=...)`
- Galería: campo `gallery_images` recibe `[{"id": file_id}]` (no strings)
- Cada `file_id` pertenece a un solo producto (no se puede compartir entre productos)
- Upload de archivos: `client.files.create(filename=..., visibility='public')` → PUT a S3 → poll `upload_status == 'ready'`
- Crear experiencias requiere permiso `app_authorization:create` (no está en la key actual)
- `experience_path` del Content app: `/customer/[experience_id]/[restPath]`
- Content app ID (built-in Whop): `app_mmjPLOxIgL1qxe`

---

## Pendientes importantes

1. **Regenerar WHOP_API_KEY** — la actual fue expuesta en el chat. Ir a Whop dashboard → Settings → API Keys → crear nueva → actualizar `.env` → `systemctl restart mathrelaxing`

2. **Banner de Whop** — subir `/static/img/banner-whop.jpg` manualmente en Whop dashboard → "Editar marca" → "Imagen del banner" (la API no tiene endpoint para esto)

3. **Reactivar Low Poly en Whop** (cuando sea el momento):
   - Recrear 2 productos + 2 planes
   - Llenar `WHOP_LOWPOLY_PLAN_1` y `WHOP_LOWPOLY_PLAN_5` en `.env`
   - Crear experiencias (Content app o Web app) y adjuntarlas
   - Agregar botones "Comprar en Whop" en `/lowpoly` de la web

4. **Botones de compra en mathrelaxing.store/lowpoly** — la página principal del generador no tiene CTA de compra. Agregar dos botones que lleven al checkout de Whop cuando se reactiven los productos.

---

## Comandos útiles de diagnóstico

```bash
# Ver logs en tiempo real
journalctl -u mathrelaxing -f

# Verificar rutas registradas
cd /var/www/mathrelaxing.store && source .venv/bin/activate && python3 -c "
import main; [print(r.path) for r in main.app.routes]
"

# Consultar créditos en DB
cd /var/www/mathrelaxing.store && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, '.')
from database import get_db
from models.product import LowPolyCredit
db = next(get_db())
for c in db.query(LowPolyCredit).all():
    print(c.id, c.customer_email, c.status, c.pack_size, c.used_count)
"

# Simular webhook Whop (para testing)
# Ver sección 'Webhook de Whop' — requiere firma Standard Webhooks correcta
```
