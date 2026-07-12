# MathRelaxing.store — Agent Handoff Context

> Contexto para una IA agéntica que continúe el trabajo. Última actualización: **2026-06-08**.
> Dueño: **Esteban** (chileno, hispanohablante, solo founder). Prefiere **soluciones self-hosted / código propio** antes que SaaS o suscripciones. Es full-stack y trabaja sobre un único VPS. Respóndele en **español**.

---

## 0. Reglas operativas CRÍTICAS (leer primero)

- **Servidor:** VPS único. App en `/var/www/mathrelaxing.store/`. IP del VPS: `5.78.125.169`.
- **Stack:** FastAPI + Jinja2 + SQLAlchemy sobre **SQLite** (`/var/www/mathrelaxing.store/mathrelaxing.db`). `uvicorn` en `127.0.0.1:8000`, detrás de **nginx** (`/etc/nginx/sites-enabled/mathrelaxing.store`).
- **NO es un repo git.** Las ediciones son **en producción, en vivo**. No hay staging ni CI. Backups manuales como `*.bak-YYYYMMDD-*`.
- **Reiniciar tras cambios .py:** `systemctl restart mathrelaxing.service` (los templates Jinja recargan en caliente; el Python NO). Tras reiniciar, la 1ª request puede dar 502 ~5-15s (warmup) — reintentar antes de debuggear. **Nunca** `kill -HUP` uvicorn.
- **venvs:**
  - App: `/var/www/mathrelaxing.store/.venv` → tiene fastapi, httpx, sqlalchemy, PIL. **NO tiene shapely.**
  - Sistema `python3` (`/usr/bin/python3`) → tiene **shapely, matplotlib, numpy, PIL** (para scripts de render/diseño).
  - Scripts standalone deben: `from dotenv import load_dotenv; load_dotenv('/var/www/mathrelaxing.store/.env')` y `sys.path.insert(0,'/var/www/mathrelaxing.store')`.
- **Secretos:** el `.env` tiene muchísimos secretos. **Nunca** mostrar/loguear sus VALORES (solo nombres de claves). Al leer credenciales para un curl, expandir en runtime (`$TOKEN`) sin imprimir.
- **Lulu PRODUCCIÓN:** credenciales reales en `.env` (también copia en `/root/coloring_prototype/.env`). **NO** llamar a `create_print_job` / POST `/print-jobs/` (PAGA dinero) sin confirmación explícita. Los endpoints free de Lulu (cost-calc, validate) son seguros.
- **Auth de admin (patrón cookie-HMAC):** ver `routers/live.py`, `routers/gumroad.py`, `routers/bonanza.py`. Credenciales compartidas: env `PINTEREST_ADMIN_USER` + `PINTEREST_ADMIN_PASSWORD` (cada router puede tener su `*_ADMIN_*` con fallback a esas).
- **Migraciones DB:** `create_all` solo crea tablas nuevas. Para columnas nuevas, `ALTER TABLE … ADD COLUMN` guardado por `inspect(engine)` (ej. `_ensure_schema()` en `routers/live.py`).

---

## 1. Catálogo de productos

**Tabla `digital_products` (29 activos):** packs descargables.
- `product_type`: `image_pack` (15), `animation_pack` (13, loops MP4), `creator_assets` (1).
- Precios $5–$19. Colecciones: strange-attractors, de-jong, fractals, radial-symmetry, reaction-diffusion, complex-plane, turing-patterns, voronoi-organics, chladni-figures, harmonic-geometry, flow-fields, fractal-flames, fractal-series, particle-systems, kleinian-gardens.
- ⚠️ **BUG conocido:** `cover_image` y `thumbnail_url` de TODOS apuntan a `/api/render/preview?product=lorenz-dream` → ese slug **no existe** → **404**. El endpoint funciona con slug real (`?product={slug}` → 200). Afecta thumbnails web, Pinterest, OG/social. (Ver TODO.)

**Tabla `products` (físicos POD):**
- **Libro de colorear** "Mathematical Tangle Art — A Coloring Book of Curves", slug `mathematical-tangle-art-coloring-book`, $24.99. POD vía **Lulu**. 54 pág, 8.5×11", 50 diseños de curvas matemáticas.
- **5 Desk mats** (`collection='desk-mats'`, $34 c/u): `aurora-interface-desk-mat`, `topographic-circuit-desk-mat`, `computational-textile-desk-mat`, `carbon-aurora-desk-mat`, `azure-bronze-topography-desk-mat`. POD vía **Printful**.
- **Art prints** (lorenz-*, clifford-*, aizawa-*, mobius-*, joukowski-*, rose-*, superformula-*, harmonograph-*, lissajous-*, gray-scott-*, julia-*, mandelbrot-*, etc.): POD vía **Gelato/Printful** (poster/canvas/acrylic/aluminum/postcard).

**Low Poly tool** ($2.99): generador de páginas para colorear, vendido vía **GPT/ChatGPT store**. Tabla `lowpoly_jobs`.

---

## 2. Canales de venta y fulfillment

| Canal | Qué vende | Fulfillment | Estado |
|---|---|---|---|
| **Web** (mathrelaxing.store) | todo | Lulu (libro), Printful (desk mats/prints), Gelato (prints) | activo |
| **Bonanza** | 29 digitales + libro + desk mats | Lulu/Printful (POD), entrega digital | ver §3 |
| **Gumroad** | 29 digitales | descarga | activo |
| **GPT store** | low poly tool | descarga | activo |

- Checkout web: PayPal / Lemon Squeezy / Whop. Webhooks en `routers/webhooks.py`.
- `routers/orders.py` `_resolve_provider(format_id)`: lulu → printful (deskmats/prints). Gelato también según formato.
- Pagos se registran como `purchase` en el dashboard vía `services/live_events.record_purchase(label=...)` (label = canal).

---

## 3. Bonanza (`services/bonanza.py`, `routers/bonanza.py`)

- API `api.bonanza.com/api_requests`. Credenciales: `BONANZA_DEV_ID`, `BONANZA_CERT_ID`, `BONANZA_TOKEN`. Fee: `BONANZA_FEE_RATE` (~11%) + `BONANZA_TRANSACTION_FEE`.
- Categorías: digital art `BONANZA_DIGITAL_ART_CATEGORY_ID` (550); libro `261186`; mouse pad `23895`.
- Maps de estado (archivos JSON en la raíz): `.bonanza_products.json` (digitales), `.bonanza_pod_products.json` (libro + desk mats, key `slug:format`), `.bonanza_fulfilled.json`.
- Funciones: `publish_product` (digital, add/revise), `publish_book` (libro POD vía Lulu), `publish_pod_product(product, format_id)` (físicos POD vía Printful), `get_listing_status` (usa `getUnlistedItemRequest` → `listingStatus`, `pictureURL`).
- Precio: `price_for_product` / `price_for_book` / `price_for_pod_format` hacen *gross-up* para cubrir el fee. **Override de precio desk mats:** `bonanza.POD_PRICE_OVERRIDE = {"gaming_mouse_pad": 44.99, "mouse_pad": 21.99}`.

### ⚠️ GOTCHAS Bonanza (muy importantes)
1. **Imágenes:** Bonanza NO ingiere URLs dinámicas con query string (`/api/render/...`). Hay que dar **JPGs estáticos**:
   - Digitales: `static/bonanza/{slug}.jpg` (lo busca `_listing_image_url`).
   - POD: `static/bonanza/pod/{slug}-{format}[-lifestyle].jpg` (lo busca `_pod_image_urls`).
   - Tras revise, Bonanza copia la imagen a su CDN (`images-bucket.bonanzastatic.com`). Verificar con `getUnlistedItemRequest` → `pictureURL`.
2. **Bienes digitales → "Requires admin review"** (1-2 días hábiles, revisión humana de Bonanza, **NO** se salta por API). Físicos (libro, desk mats) van **Active de inmediato**.
3. **Checkboxes de envío del Booth:** `getUnlistedItem` NO devuelve `shippingDetails`. Tras un revise por API, las casillas (ej. "Europe") **pueden requerir toggle manual en la UI** — verificar en la web de Bonanza.
4. Routing de fulfillment (poller `fulfill_new_orders`): `provider = pod.get("provider") or ("lulu" if fmt=='book' else "printful")`.

### Estado actual Bonanza (2026-06-07)
- **29 digitales:** publicados, imágenes arregladas (JPGs estáticos generados desde `static/previews/{slug}_clean.jpg` o frame del loop). Estado **"Requires admin review"** → esperando aprobación manual de Bonanza.
- **Libro:** item `1808525001`, **Active**. Envío: US (doméstico) + UK + **Europe** + Australia (free). Descripción con estimados por país. (Alemania excluida — ver §5.)
- **Desk mats:** **10 listings Active**: 5 `gaming_mouse_pad` (36×18", **$44.99**) + 5 `mouse_pad` (8.7×7.1", **$21.99**). Imágenes en CDN. Fulfillment → Printful.

---

## 4. Gumroad (`services/gumroad.py`, `routers/gumroad.py`)

- OAuth (`GUMROAD_CLIENT_ID/SECRET/REDIRECT_URI`). Token en `.gumroad_token.json` (scope `edit_products view_sales mark_sales_as_shipped`). Map `.gumroad_products.json` (29 slugs → gumroad_id).
- `publish_product` hace create (POST) o update (PUT) + enable. `publish-all` endpoint admin.
- **Estado:** los **29 digitales están publicados y actualizados**. Dueño confirmó que NO hay productos nuevos pendientes en el catálogo.

---

## 5. Lulu (libro) — `services/lulu.py`

- Print API. Credenciales `LULU_CLIENT_KEY/SECRET`, `LULU_SANDBOX=0` (prod). PDFs: `static/downloads/book/{interior,cover}.pdf`. SKU `0850X1100.BW.STD.PB.060UW444.MXX`, 54 pág. Costo print ~$4.24/u.
- `create_order` = PAID (`/print-jobs/`), solo tras captura PayPal real. Setea `order.printful_order_id = "lulu:{job_id}"`.
- **Envío del libro — `BOOK_COUNTRIES` = {US, GB, ES, AU} ∪ `EUROPE_COUNTRIES` (29) = 33 países.**
  - Incluye toda Europa **EXCEPTO Alemania** (excluida por **LUCID** / registro de empaques alemán; el dueño no está registrado → excluida en web Y Bonanza).
  - **NO incluye Canadá (CA) ni Nueva Zelanda (NZ)** — Lulu sí puede enviar ahí, pero no están habilitados (decisión pendiente del dueño, ver TODO).
  - Free shipping. Estimados (`DELIVERY_ESTIMATES`): US/UK 6-9, ES/DE 7-11, AU 8-14, resto Europa 7-13 días hábiles.

---

## 6. Printful / Gelato (físicos)

- **Printful** (`services/printful.py`): desk mats (`gaming_mouse_pad`: $34 web, costo $19.33 + ship US $11.99 / intl $26.99; `mouse_pad`: $22, costo $9.13 + $4.49/$11.99) y art prints (poster). `DESK_MAT_FORMAT_IDS=("gaming_mouse_pad","mouse_pad")`.
- **Gelato** (`services/gelato.py`): canvas $90, framed-poster $105, acrylic $115, poster $35, aluminum $98, postcard-set $32. (Sin formato desk mat.)

---

## 7. Dashboard de tráfico en vivo — `/admin/live` (`routers/live.py`)

- Self-hosted, **reemplazó a PostHog**. Estilo Shopify Live View: visitantes activos, carritos/checkouts activos ($), ventas hoy, feed de eventos, top fuentes/campañas/países/productos. Histórico en `/admin/live/history`.
- Tracking snippet en `templates/base.html` → `window.mrTrack(type, data)`; atribución first-touch (UTMs + clickIDs fbclid/gclid/ttclid/msclkid) sticky en localStorage (TTL 30 días).
- Eventos válidos: pageview, product_view, add_to_cart, cart_view, checkout_start, payment_redirect, purchase. Ingesta: `POST /api/track` (parsea raw body, tolera sendBeacon). Bots filtrados por UA.
- Tabla `live_events`. Retención `LIVE_EVENT_RETENTION_DAYS` (default 365). Geo vía ip-api.com (cache 24h).
- **Compras** = `LiveEvent(event_type='purchase', source=<canal>, ua_class='server')` escritas por `services/live_events.record_purchase`. Canales: bonanza, gumroad, lowpoly, paypal/lemon/whop/direct (web). Físicos atribuidos en `telegram.notify_new_physical_order` (`bonanza` si `lemon_order_id` empieza `bonanza_pod_`, si no `direct`).

### Exclusión del dueño (que sus visitas no cuenten)
- 2 vías (`_is_ignored`): (1) cookie por navegador en `/admin/live/ignore-me` (~3 años); (2) IP server-side en env `LIVE_IGNORE_IPS`. **IP actual del PC del dueño excluida: `190.5.32.36`** (puede rotar — la cookie es el respaldo durable).

---

## 8. Telegram bot

- Bot: **@MathRelaxing_bot**. `TELEGRAM_CHAT_ID = 8644526873` (cuenta actual del dueño "Esteban Navarro Rojas"). Webhook activo: `https://mathrelaxing.store/api/telegram/webhook` (`routers/telegram_bot.py`).
  - *(Nota: hubo una cuenta vieja `5774052858` que el dueño ya no controla; se re-vinculó a la actual. Tema personal aparte: el dueño quiere recuperar `5774052858` por un bot de empresa "GENCEC" — eso es 100% del lado de Telegram/número de teléfono, NO del servidor.)*
- **Comando `/stats`** (reescrito): muestra carritos/checkouts/compras **por canal** (🌐 Web directa, 🛍 Bonanza, 🤖 GPT Store, 🍋 Gumroad) hoy + histórico. Web = compras con `source NOT IN (bonanza,gumroad,lowpoly)`. GPT = `lowpoly_jobs` paid ($2.99). `/start` responde un saludo.
- **Alertas:**
  - Carrito/checkout/payment: `_funnel_alert` en `routers/live.py` (1ª vez por sesión).
  - **Visita a `/book`: DESACTIVADA** por pedido del dueño (código comenteado; `_book_visit_alert` queda definido pero sin uso).
  - Compras: `notify_new_*` en `services/telegram.py` (vía webhooks), parse_mode correcto.
- ⚠️ **BUG PENDIENTE:** `telegram.send_message(text)` NO pasa `parse_mode`, así que las alertas de carrito/checkout (`_funnel_alert`, que usan `<b>`) **muestran los tags HTML literales**. **Fix:** agregar `parse_mode: Optional[str]=None` a `send_message` y llamar `send_message(text, parse_mode="HTML")` desde `_funnel_alert`. (Verificado: los otros callers de `send_message` — bonanza.py, ebay.py, webhooks.py — usan texto plano sin tags, así que el cambio es seguro.)

---

## 9. Assets de marketing creados (esta sesión)

- **Video promo TikTok del libro** (vertical 1080×1920, ~12.5s): página que se "traza" sola → se pinta → CTA, música ambiental procedural (royalty-free). Archivo: `static/video/tiktok_poc.mp4`. Script: `/root/coloring_prototype/tiktok_trace_video.py` (usa `generate_one_per_family.py`, system python3). Captions/hashtags ya entregados al dueño (inglés).
- **Pack 4K "Strange Attractors" para Creative Market:**
  - 5 loops renderizados a **4K 3840×2160 / 30fps**: `static/videos/{lorenz_flow,clifford_spin,aizawa_dance,attractor_morph,lorenz_drift}_2160p30.mp4`.
  - Render via `services/video_renderer.py` (`ANIMATION_GENERATORS` registry; cada gen acepta `width/height`). Script usado: `/root/render_4k_sa.py`.
  - **Preview 1820×1214** (formato CM): `static/previews/cm_strange_attractors_1820x1214.png`.
  - **ZIP a la venta** (4K + 1080p bonus, 443MB): `static/downloads/strange-attractors-loops-4k_c67c8fd2c1c2.zip` ← **link público temporal, BORRAR tras descarga**.
  - Catálogo `strange-attractors-loop-pack` actualizado a resolución 3840×2160.
- **Creative Market:** categoría = **Graphics** (no hay "Video"); pregunta "generative AI?" → responder **No** (es código propio, no IA); precios sugeridos Personal $15 / Commercial $18-24 / Extended $60. Title/description/tags ya entregados.
- Pinterest: pin del libro creado. Auto-pin loop existe (`services/pinterest_jobs.py`).

---

## 10. Mapa de archivos clave

```
/var/www/mathrelaxing.store/
  database.py                      # engine SQLite, SessionLocal
  mathrelaxing.db                  # DB
  .env                             # secretos (NO exponer valores)
  routers/  live.py bonanza.py gumroad.py orders.py webhooks.py
            telegram_bot.py pinterest.py render.py gpt.py lowpoly.py
  services/ bonanza.py lulu.py printful.py gelato.py gumroad.py
            telegram.py live_events.py geo.py video_renderer.py
            deskmat_renderer.py pinterest_jobs.py
  models/   product.py (Product, DigitalProduct, Order, Purchase) live.py (LiveEvent)
  templates/ index.html book.html product.html checkout.html base.html admin_live*.html
  static/   bonanza/{slug}.jpg, bonanza/pod/, bonanza/book/, previews/, videos/, video/, downloads/book/
  .bonanza_products.json .bonanza_pod_products.json .gumroad_products.json .gumroad_token.json
/root/coloring_prototype/          # generadores del libro + script video TikTok (system python3, shapely)
/root/render_4k_sa.py              # script render 4K loops
/root/.claude/projects/-root/memory/  # memoria persistente del agente (MEMORY.md + project_*.md)
```

---

## 11. TODOs / decisiones abiertas

1. **[Telegram] Arreglar render HTML de alertas carrito/checkout** (bug §8): agregar `parse_mode` a `send_message`, pasar `"HTML"` desde `_funnel_alert`. (La alerta de visita /book ya quedó desactivada — eso era lo que el dueño quería.)
2. **[Envío libro] ¿Habilitar Canadá 🇨🇦 y Nueva Zelanda 🇳🇿?** — decisión pendiente del dueño (mercados angloparlantes clave para la promo TikTok). Implica: agregar "CA","NZ" a `lulu.BOOK_COUNTRIES` + `DELIVERY_ESTIMATES`, y reflejar en `bonanza.BOOK_SHIP_COUNTRIES` (Canadá tiene checkbox propio; NZ va en "Worldwide"/aparte) + textos web (`index.html` promo + `book.html`). Re-publicar libro Bonanza + restart.
3. **[Promo TikTok del libro]** target recomendado: **US + UK + Australia** (inglés, envía, mejor conversión). Evitar Alemania (no envía) y países sin envío. Sumar Canadá/NZ si se habilitan. España/Francia/Italia: envían pero anuncio en inglés convierte poco (targetear solo con creativo en español).
4. **[Creative Market]** subir el primer producto (pack 4K listo): files = ZIP 4K, preview = PNG 1820×1214, category Graphics, AI=No.
5. **[Bug] `digital_products.cover_image`** = `lorenz-dream` (404) → arreglar a `?product={slug}` o valor válido (afecta web/Pinterest/social). *(Hay un chip de tarea spawneado para esto.)*
6. **[Bonanza digitales]** esperar aprobación manual (1-2 días hábiles desde 2026-06-07); luego verificar que pasen a "Active/sellable" vía `getUnlistedItemRequest`.
7. **[Limpieza]** borrar el ZIP temporal `static/downloads/strange-attractors-loops-4k_*.zip` cuando el dueño lo haya descargado.
8. **[Opcional]** revisar precio desk mats $44.99/$21.99 si se quiere más competitivo (costo real grande $31.32, chico $13.62).

---

## 12. Cómo verificar estados rápido (snippets)

```bash
# Servicio
systemctl is-active mathrelaxing.service && systemctl restart mathrelaxing.service

# Estado de un listing Bonanza (imagen + status)
cd /var/www/mathrelaxing.store && .venv/bin/python - <<'PY'
import asyncio,sys; from dotenv import load_dotenv
load_dotenv('/var/www/mathrelaxing.store/.env'); sys.path.insert(0,'/var/www/mathrelaxing.store')
from services import bonanza as B
async def m():
    d=await B._request("getUnlistedItemRequest",{"requesterCredentials":B._credentials(),"itemId":"1808525001"})
    print(d.get("getUnlistedItemResponse",{}).get("item",{}).get("listingStatus"))
asyncio.run(m())
PY

# Países de envío del libro
cd /var/www/mathrelaxing.store && .venv/bin/python -c "import sys;sys.path.insert(0,'.');from services import lulu;print(sorted(lulu.BOOK_COUNTRIES))"

# Telegram: confirmar entrega a un chat (sin exponer token)
TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env|cut -d= -f2-); curl -s "https://api.telegram.org/bot$TOKEN/getMe"|python3 -m json.tool
```
