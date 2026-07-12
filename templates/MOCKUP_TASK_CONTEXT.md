# Contexto de Tarea: Mockups PSD + Zoom Lens

> Archivo generado el 25 de abril de 2026 para retomar la integración de los nuevos mockups PSD descargados.

---

## 1. Resumen de lo que YA está hecho

### Zoom/Lupa en la página de producto
- Se agregó un efecto de lupa circular (180 px, zoom ×2.5) en `product.html`.
- Al pasar el cursor sobre el mockup, aparece un círculo con la imagen ampliada que sigue al mouse.
- El código está funcional y testeado.

### Mockups de stock eliminados
- Se eliminaron las escenas de Unsplash (`extra-scenes/`) y todo el código backend/frontend que las servía.
- El sistema volvió a usar **solo los PSD originales** (`studio`, `room`/`framed`, `acrylic`).

---

## 2. Archivos PSD nuevos que el usuario subió

Los 3 archivos se encuentran en:

```
/var/www/mathrelaxing.store/static/psd-mockups/
├── free-canvas-mockup.psd              (168 MB)
├── free-framed-poster-wall.psd         (39 MB)
└── free-vertical-wall-canvas.psd       (79 MB)
```

También están los zips originales en `templates/`:

```
/var/www/mathrelaxing.store/templates/
├── free-canvas-mockup.zip
├── free-framed-poster-by-wall-mockup-sachanati.com.psd
└── free-vertical-wall-canvas-frame-mockup.zip
```

---

## 3. Análisis de capas realizado

### `free-canvas-mockup.psd` — Canvas doble (2 lienzos)
- **Tamaño:** 4500×3200 px
- **Estructura:** Muestra 2 lienzos (Left + Right) en una escena de estudio.
- **Capas de interés:**
  - `DESIGN` → `Canvas Left` (smartobject, PSB 1502×1983)
  - `DESIGN` → `Canvas Right` (smartobject, PSB 1502×1983)
  - `Shadows` (4500×3200) — capa de sombras globales
  - `Highlights` (4500×3049) — capa de highlights globales
  - `Web Tag` — marca de agua
- **Problema:** Las coordenadas del smartobject no están en `_record.left/top/right/bottom` (son 0). Se necesita obtenerlas del `placed_layer` transform o del `tagged_blocks` (`PlLd`).

### `free-vertical-wall-canvas.psd` — Canvas vertical en pared
- **Tamaño:** 4500×3200 px
- **Estructura:** Un solo canvas vertical colgado en una pared.
- **Capas de interés:**
  - `COLOR` → `Canvas` — bbox `[2452, 505, 3543, 1933]` = 1091×1428 (área del canvas en la pared)
  - `DESIGN` → `Canvas` (smartobject, PSB 1103×1454) — el artwork a reemplazar
  - `Sahdows` (sic) — 1091×1428, sombra del canvas
  - `Highlights` — 1091×1428, iluminación
  - `Web Tag` — marca de agua
- **Problema:** El smartobject tiene `_record` en `[0,0,0,0]`, pero la capa `COLOR → Canvas` sí tiene coordenadas. El artwork se inserta escalado desde el smartobject. Se necesita mapear el PSB al área del canvas.

### `free-framed-poster-wall.psd` — Póster enmarcado en pared
- **Tamaño:** 1600×1600 px
- **Estructura:** Un póster enmarcado en una pared con efectos de luz.
- **Capas de interés:**
  - `[DOUBLE CLICK] Poster` — smartobject, bbox `[532, 321, 1211, 1286]` = 679×965
  - `Lighting FX` → `Shadow` — 680×966, sombra
  - `Lighting FX` → `Lighting` — 680×966, iluminación
  - `Reflection` — smartobject reflejado en el piso
- **PSB embebido:** 2213×3127 px (el póster se escala de 2213×3127 a 679×965)
- **Estado:** Este PSD tiene coordenadas claras y debería ser el más fácil de integrar.

---

## 4. Cómo funciona el sistema actual de mockups

El sistema usa `services/mockup.py` con `PSD_TEMPLATES`:

```python
PSD_TEMPLATES = [
    {
        "id": "studio",
        "path": "/root/canvas_mockup/PSD 001 3x4.psd",
        "art_l": 1662, "art_t": 716, "art_w": 1177, "art_h": 1569,
        "scale": 0.5,
        "psd_type": "studio",
    },
    {
        "id": "room",
        "path": "/root/canvas_mockup/vertical wall poster mockup.psd",
        "art_l": 1049, "art_t": 481, "art_w": 1111, "art_h": 1573,
        "scale": 0.5,
        "psd_type": "room",
    },
    {
        "id": "framed",
        "path": "/root/canvas_mockup/vertical wall poster mockup.psd",
        "art_l": 1049, "art_t": 481, "art_w": 1111, "art_h": 1573,
        "scale": 0.5,
        "psd_type": "room",
        "art_style": "framed",
    },
    {
        "id": "acrylic",
        "path": "/root/acrylic_mockup/Print-mockup.psd",
        "art_l": 2223, "art_t": 1163, "art_w": 1484, "art_h": 2109,
        "scale": 0.5,
        "psd_type": "acrylic-standoff",
    },
]
```

Cada template necesita:
1. `path`: ruta al PSD
2. `art_l`, `art_t`, `art_w`, `art_h`: coordenadas donde insertar el artwork
3. `scale`: factor de escala final del resultado
4. `psd_type`: tipo de procesamiento (`studio`, `room`, `acrylic-standoff`)
5. `art_style` (opcional): post-procesamiento (`framed`, `acrylic`)

El sistema usa `psd_tools` para cargar el PSD, extraer el fondo (`scene`) y las capas de overlay (`Shadows`, `Highlights`, etc.), luego pega el artwork generado en las coordenadas `art_l`, `art_t`.

---

## 5. Pendiente: Integrar los 3 PSDs nuevos

### Paso 1: Obtener coordenadas exactas del artwork en cada PSD

| PSD | Coordenadas actuales | Estado |
|-----|---------------------|--------|
| `free-canvas-mockup.psd` | Desconocidas (smartobjects en `[0,0,0,0]`) | ⚠️ Necesita investigación |
| `free-vertical-wall-canvas.psd` | `COLOR → Canvas` en `[2452, 505, 1091×1428]`, PSB 1103×1454 | ⚠️ Necesita mapear PSB al canvas |
| `free-framed-poster-wall.psd` | `[532, 321, 679×965]`, PSB 2213×3127 | ✅ Coordenadas claras |

#### Enfoque para obtener coordenadas del canvas-mockup:
El smartobject usa `placed_layer` transform. Opciones:
- **Opción A:** Abrir el PSD en Photoshop y usar "Reveal in Finder" sobre el smartobject para ver sus coordenadas.
- **Opción B:** Usar `psd_tools` para leer el `placed_layer` block (`PlLd`) y extraer la matriz de transformación.
- **Opción C:** Renderizar el PSD, luego renderizar ocultando el smartobject, y hacer diff para encontrar el bbox del artwork.

El último intento con **Opción C** falló porque `psd_tools` no reescribe bien el PSB embebido.

### Paso 2: Agregar templates a `services/mockup.py`

Una vez con las coordenadas, agregar entradas a `PSD_TEMPLATES`:

```python
{
    "id": "free-canvas-studio",
    "path": "/var/www/mathrelaxing.store/static/psd-mockups/free-canvas-mockup.psd",
    "art_l": ?, "art_t": ?, "art_w": ?, "art_h": ?,
    "scale": 0.5,
    "psd_type": "studio",  # o nuevo tipo si la estructura es diferente
},
```

### Paso 3: Actualizar `routers/render.py`

Agregar mapeos en `FORMAT_TO_VARIANT` para que la página de producto pueda servir los nuevos mockups.

### Paso 4: Actualizar frontend

Si se quiere permitir al usuario elegir entre mockups, agregar botones en `product.html` para cambiar la variante del mockup.

---

## 6. Código relevante para retomar

### Backend: `services/mockup.py`
Función clave: `generate_mockup(equation_type, params, variant)`
- Carga el PSD con `_load_template(tpl)`
- Extrae `scene` (fondo) y `overlays` (efectos)
- Genera el artwork con `_get_art_master()`
- Pega el artwork en `(tpl["art_l"], tpl["art_t"])`
- Aplica overlays con `_apply_overlays()`
- Escala con `tpl["scale"]`

### Backend: `services/mockup_compositor.py`
Tiene funciones alternativas para JPG mockups (no PSD). Actualmente no se usan para la página de producto principal.

### Frontend: `templates/product.html`
- Mockup principal: `/api/render/mockup?product={{ product.slug }}&format=canvas`
- El zoom lens está implementado en JavaScript inline.

---

## 7. Notas para el usuario

- Los PSDs nuevos son de **PsFiles** y tienen licencia "Personal & Commercial Use".
- Todos tienen **Web Tag** (marca de agua). Si se usan en producción, considera:
  - Ocultar la capa `Web Tag` durante el renderizado con `psd_tools`.
  - O comprar la licencia premium para removerla.
- `free-canvas-mockup.psd` muestra **2 lienzos** (Left + Right). Se puede usar solo uno (ej: `Canvas Right`) o adaptar el sistema para generar ambos.
- `free-vertical-wall-canvas.psd` muestra **1 canvas en pared** — es la escena más natural para e-commerce.
- `free-framed-poster-wall.psd` es el más pequeño (1600×1600) pero tiene buena calidad.

---

## 8. Próximos pasos sugeridos

1. **Obtener coordenadas exactas** de los smartobjects en los 2 canvas PSDs.
2. **Agregar 3 nuevas entradas** a `PSD_TEMPLATES` en `services/mockup.py`.
3. **Probar la generación** con `curl http://127.0.0.1:8000/api/render/mockup?product=...&format=...`.
4. **Agregar selector de mockups** en `product.html` si se quiere que el usuario elija entre escenas.
5. **Ocultar la capa `Web Tag`** durante el renderizado.
