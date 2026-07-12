# Low Poly Color-by-Number — Integración con Whop

## Qué es el producto

**Low Poly Color-by-Number** es una herramienta que convierte cualquier foto del usuario en una página de colorear numerada, generada con un algoritmo matemático real (triangulación Delaunay + agrupación de colores). El usuario elige:

- Número de colores: 8, 12, 16 o 20
- Tipo de cuadrícula: cuadrada o hexagonal
- Orientación: retrato o paisaje

El resultado son dos archivos:
1. **Página de colorear** — regiones en blanco con números (PNG 2550×3300 px, 300 DPI, listo para imprimir)
2. **Referencia de colores** — la misma imagen con los colores aplicados, para saber qué color va en cada región

---

## Productos en Whop

| Producto | ID | Plan | Precio |
|---|---|---|---|
| Low Poly Color-by-Number — 1 Credit | `prod_ZuA2km8tP3V7b` | `plan_qPMvUkO7rXxOW` | $2.99 |
| Low Poly Color-by-Number — 5 Credits | `prod_nXgUJppzRQLEe` | `plan_MJXmSbhMus5WY` | $9.99 |

Cada **crédito = 1 imagen procesada**. El pack de 5 permite procesar 5 fotos distintas.

---

## Flujo completo (paso a paso)

```
1. Usuario compra en Whop
        ↓
2. Whop dispara webhook → POST /api/webhooks/whop
        ↓
3. Backend crea un registro LowPolyCredit en la base de datos
   - token UUID único
   - pack_size = 1 o 5
   - status = "unused"
        ↓
4. Backend envía email al comprador con el enlace de canje:
   https://mathrelaxing.store/lowpoly/credit/{token}
        ↓
5. Usuario abre el enlace → página interactiva de generación
   - Ve un demo en vivo con sus parámetros (imagen de ejemplo actualizada al instante)
   - Sube su foto
   - Ingresa su email
   - Hace clic en "Generate"
        ↓
6. Backend genera los archivos (20–60 segundos):
   - PNG full-res de la página de colorear
   - PNG full-res de la referencia de colores
        ↓
7. Usuario recibe los links de descarga en pantalla
   + email con los archivos adjuntos
        ↓
8. Crédito consumido:
   - used_count += 1
   - Si used_count >= pack_size → status = "exhausted"
   - Si pack_size > 1 y quedan créditos → status = "partial"
```

---

## Modelo de datos: LowPolyCredit

```
tabla: lowpoly_credits

id             INT (PK)
token          UUID (único) — es la llave de la URL de canje
whop_id        STRING — ID del pago en Whop (para idempotencia)
customer_email STRING
customer_name  STRING
pack_size      INT (1 o 5)
used_count     INT (empieza en 0)
status         STRING: "unused" | "partial" | "exhausted"
created_at     DATETIME
used_at        DATETIME (nullable)
```

---

## Webhook de Whop

- **Endpoint:** `POST /api/webhooks/whop`
- **Secret:** variable de entorno `WHOP_WEBHOOK_SECRET`
- **Protocolo de firma:** [Standard Webhooks](https://www.standardwebhooks.com/)
- **Headers relevantes:**

| Header | Contenido |
|---|---|
| `webhook-id` | ID único del evento |
| `webhook-timestamp` | Unix timestamp en segundos |
| `webhook-signature` | `v1,<base64(HMAC-SHA256)>` |

- **Contenido firmado:** `{webhook-id}.{webhook-timestamp}.{body}`
- **Verificación:** se usa `whop_sdk.Whop(webhook_key=base64(secret)).webhooks.unwrap(body, headers)`
- **Eventos manejados:**
  - `payment.succeeded` → crea crédito (o fulfills digital product) y envía email
  - `membership.activated` → mismo flujo (para productos que crean membresías)
  - `refund.created` → revoca acceso a la descarga
  - `dispute.created` / `dispute.updated` → alerta en Telegram

El handler identifica si el plan pertenece a Low Poly comparando `event.data.plan.id` con las variables de entorno `WHOP_LOWPOLY_PLAN_1` y `WHOP_LOWPOLY_PLAN_5`.

---

## Endpoints de la aplicación

| Método | URL | Descripción |
|---|---|---|
| `GET` | `/lowpoly/credit/{token}` | Página de canje interactiva |
| `POST` | `/lowpoly/credit/{token}/generate` | Genera la imagen y consume un crédito |

Parámetros del POST (multipart/form-data):
- `image` — archivo de imagen (JPEG/PNG, max ~10 MB)
- `email_addr` — email del usuario para recibir los archivos
- `colors` — 8, 12, 16 o 20
- `grid` — "square" o "hex"
- `orientation` — "portrait" o "landscape"

---

## Variables de entorno relevantes

```env
WHOP_API_KEY=apik_...
WHOP_COMPANY_ID=biz_K21tvFR0jxGtVz
WHOP_WEBHOOK_SECRET=ws_...
WHOP_LOWPOLY_PLAN_1=plan_qPMvUkO7rXxOW
WHOP_LOWPOLY_PLAN_5=plan_MJXmSbhMus5WY
```

---

## Archivos modificados / creados

| Archivo | Cambio |
|---|---|
| `models/product.py` | Modelo `LowPolyCredit` + tabla SQLite |
| `routers/webhooks.py` | Handler `_handle_whop_lowpoly_credit()` |
| `routers/lowpoly.py` | Rutas `/credit/{token}` GET y POST |
| `services/email.py` | `send_lowpoly_credit_email()` |
| `main.py` | Rutas raíz `/lowpoly/credit/{token}` (sin prefijo `/api`) |
| `templates/lowpoly_credit.html` | Página de canje con demo interactivo |
| `static/examples/web/` | 32 imágenes de ejemplo (8 combos × 2 tipos × 2 orientaciones) |

---

## Notas de implementación

- **Idempotencia:** el webhook verifica `whop_id` antes de crear el crédito; doble disparo no crea duplicado.
- **Concurrencia:** un semáforo (`asyncio.Semaphore(2)`) limita la generación simultánea a 2 imágenes.
- **Demo interactivo:** la página usa JavaScript para intercambiar entre 32 imágenes de ejemplo pre-generadas según los parámetros seleccionados, sin llamadas al servidor.
- **Resolución de salida:** PNG a 2550×3300 px (retrato) o 3300×2550 px (paisaje), 300 DPI.
- **Email de descarga:** reutiliza `send_lowpoly_download_email()` (mismo flujo que el producto de pago directo).
