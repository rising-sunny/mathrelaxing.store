"""
Publish remaining 17 products to Gumroad with full metadata.
Covers, thumbnails (S3 blob), tags, and rich descriptions.
Run from /var/www/mathrelaxing.store
"""
import sys, os, json, math, io, re, base64, hashlib, time
sys.path.insert(0, '/var/www/mathrelaxing.store')

import requests
from PIL import Image
from database import SessionLocal
from models.product import DigitalProduct
from services.gumroad import (
    get_access_token, _load_map, _save_map,
    _product_description, API_BASE,
)

COVERS_DIR  = "/var/www/mathrelaxing.store/static/covers"
BASE_LOCAL  = "http://127.0.0.1:8000"
BASE_PUBLIC = "https://mathrelaxing.store"
token       = get_access_token()

os.makedirs(COVERS_DIR, exist_ok=True)

# ── Tags per product ────────────────────────────────────────────────────────

TAGS = {
    "chladni-figures-image-pack":    ["generative art","digital art","math art","chladni","vibration patterns","wallpaper","4k","image pack","standing waves","acoustic art"],
    "harmonic-geometry-image-pack":  ["generative art","digital art","math art","harmonograph","lissajous","wallpaper","4k","image pack","harmonic oscillation","wave art"],
    "flow-fields-image-pack":        ["generative art","digital art","math art","flow field","particle art","wallpaper","4k","image pack","vector field","abstract"],
    "flow-fields-loop-pack":         ["generative art","loop animation","motion graphics","math art","flow field","particle animation","seamless loop","4k video","vector field","abstract"],
    "fractal-flames-image-pack":     ["generative art","digital art","math art","fractal flame","IFS","wallpaper","4k","image pack","flame fractal","abstract"],
    "fractal-flames-loop-pack":      ["generative art","loop animation","motion graphics","math art","fractal flame","seamless loop","4k video","IFS","flame fractal","abstract"],
    "harmonic-geometry-loop-pack":   ["generative art","loop animation","motion graphics","math art","harmonograph","lissajous","seamless loop","4k video","harmonic","oscillation"],
    "fractal-series-loop-pack":      ["generative art","loop animation","motion graphics","math art","fractal","julia set","seamless loop","4k video","mandelbrot","chaos"],
    "radial-symmetry-loop-pack":     ["generative art","loop animation","motion graphics","math art","symmetry","mandala","seamless loop","4k video","rose curve","abstract"],
    "reaction-diffusion-loop-pack":  ["generative art","loop animation","motion graphics","math art","reaction diffusion","organic","seamless loop","4k video","turing pattern","abstract"],
    "complex-plane-loop-pack":       ["generative art","loop animation","motion graphics","math art","complex analysis","mobius","seamless loop","4k video","conformal map","geometric"],
    "turing-patterns-loop-pack":     ["generative art","loop animation","motion graphics","math art","turing pattern","organic","seamless loop","4k video","reaction diffusion","biology"],
    "voronoi-organics-loop-pack":    ["generative art","loop animation","motion graphics","math art","voronoi","organic","seamless loop","4k video","cellular","abstract"],
    "chladni-figures-loop-pack":     ["generative art","loop animation","motion graphics","math art","chladni","vibration","seamless loop","4k video","standing waves","acoustic"],
    "de-jong-loop-pack":             ["generative art","loop animation","motion graphics","math art","de jong","attractor","seamless loop","4k video","particle art","abstract"],
    "particle-systems-loop-pack":    ["generative art","loop animation","motion graphics","math art","particle system","physics simulation","seamless loop","4k video","vortex","nebula"],
    "particle-systems-image-pack":   ["generative art","digital art","math art","particle system","physics simulation","wallpaper","4k","image pack","nebula art","vortex"],
}

# ── Descriptions ─────────────────────────────────────────────────────────────

DESCRIPTIONS = {
"chladni-figures-image-pack": """\
5 high-resolution mathematical art images of Chladni figures — nodal patterns of vibration rendered as stunning mandala-like compositions. These are the shapes that sound makes.

Ernst Chladni discovered in 1787 that sand on a vibrating plate organizes itself into precise geometric patterns. These images simulate that process mathematically — Z(x,y) = sin(mπx)sin(nπy) + sin(nπx)sin(mπy) — producing symmetric, intricate forms that bridge mathematics, physics, and art.

**What you get:**
- 5 unique Chladni pattern images across different vibrational modes
- Portrait (3200×4000), landscape (4000×3200), and square (3200×3200) orientations
- 4K resolution — print-ready and screen-perfect
- Instant download link emailed after purchase

**Perfect for:**
- Mandala-style wallpapers and meditative visuals
- Physics and acoustics education content
- Art prints with a scientific aesthetic
- Social media content for science communicators
- Geometric and symmetry art collections
- Home décor with an intellectual edge

Pure mathematical computation of acoustic physics — no AI, no filters. Browse the full collection at mathrelaxing.store/bundle/chladni-figures-image-pack
""",

"harmonic-geometry-image-pack": """\
14 high-resolution mathematical art images of harmonic geometry — Lissajous figures and harmonograph curves that make the mathematics of resonance visible.

When two oscillations interact, they trace curves in space. These images capture that interaction: x(t) = A·sin(f₁t + φ)·e^{−dt}, y(t) = B·sin(f₂t)·e^{−dt}. The result ranges from simple ellipses to impossibly complex knotted curves — the geometry of music, made visual.

**What you get:**
- 14 unique images across diverse frequency ratios and damping values
- Portrait (3200×4000), landscape (4000×3200), and square (3200×3200) orientations
- 4K resolution — print-ready and screen-perfect
- Instant download link emailed after purchase

**Perfect for:**
- Elegant minimal wallpapers and phone backgrounds
- Physics and music theory education visuals
- Art prints with a scientific and aesthetic appeal
- Meditation and focus visual content
- Mathematical art collections
- Interior decoration with a geometric sensibility

Computed from physics equations — no AI, pure oscillation mathematics. Browse the full collection at mathrelaxing.store/bundle/harmonic-geometry-image-pack
""",

"flow-fields-image-pack": """\
20 high-resolution mathematical art images of flow fields — thousands of particles tracing paths through mathematically-defined vector fields, rendered in stunning color gradients.

Each image is a portrait of an invisible force field: ∂x/∂t = cos(N(x,y)), ∂y/∂t = sin(N(x,y)), where N is a layered noise field. Particles follow the flow, leaving trails that reveal the underlying mathematical structure — the result looks like wind made visible, or currents frozen in time.

**What you get:**
- 20 unique flow field images with diverse noise parameters and color palettes
- Portrait (3200×4000), landscape (4000×3200), and square (3200×3200) orientations
- 4K resolution — print-ready and screen-perfect
- Instant download link emailed after purchase

**Perfect for:**
- Abstract wallpapers and phone backgrounds
- Art prints with fluid, organic aesthetics
- YouTube thumbnails and channel art
- Social media backgrounds for creative accounts
- Generative art collections
- Music and ambient content visuals

Simulated from vector field mathematics — no AI, no post-processing. Browse the full collection at mathrelaxing.store/bundle/flow-fields-image-pack
""",

"flow-fields-loop-pack": """\
5 seamless loop animations of mathematical flow fields — thousands of particles following vector field paths, rendered as smooth, hypnotic video loops in HD and 4K.

Watch invisible mathematical forces made visible: particles stream through noise-defined vector fields, leaving glowing trails that shift and evolve. Each animation runs seamlessly, perfect for ambient display or motion graphics backgrounds.

**What you get:**
- 5 unique flow field loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Stream overlays and OBS backgrounds
- Ambient display art and digital frames
- Video editing and motion graphics
- YouTube intros and channel art
- Instagram and TikTok reels backgrounds
- Live wallpapers and screensavers

Pure mathematical particle simulation — no AI, no stock footage. Browse the full collection at mathrelaxing.store/bundle/flow-fields-loop-pack
""",

"fractal-flames-image-pack": """\
20 high-resolution fractal flame images — iterated function systems rendered with logarithmic density estimation and flame coloring, producing luminous, organic, endlessly complex structures.

Fractal flames extend traditional IFS fractals with nonlinear variation functions and tone mapping. The result is fire-like structures of infinite complexity — aurora-like curtains of color, crystalline branching patterns, and glowing fractal foliage that seems to emit its own light.

**What you get:**
- 20 unique fractal flame images across diverse variation functions and color palettes
- Portrait (3200×4000), landscape (4000×3200), and square (3200×3200) orientations
- 4K resolution — print-ready and screen-perfect
- Instant download link emailed after purchase

**Perfect for:**
- Dramatic wallpapers and desktop backgrounds
- Art prints with luminous, otherworldly aesthetics
- Album covers and music visual content
- Social media content for creative accounts
- Fantasy and sci-fi themed visual projects
- Fractal and generative art collections

Computed from IFS equations with tone-mapped flame rendering — no AI, pure fractal mathematics. Browse the full collection at mathrelaxing.store/bundle/fractal-flames-image-pack
""",

"fractal-flames-loop-pack": """\
5 seamless loop animations of fractal flames — iterated function systems rendered with flame coloring as smooth, glowing video loops in HD and 4K.

Fractal flames in motion: luminous, fire-like structures that shift and evolve while maintaining their infinite fractal complexity. Each animation runs seamlessly, creating an ambient visual that's unlike anything in stock footage libraries.

**What you get:**
- 5 unique fractal flame loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Music visualizers and album release content
- Stream overlays and gaming backgrounds
- Ambient display art and digital frames
- Video editing and motion graphics
- Instagram Reels and TikTok backgrounds
- Live wallpapers and screensavers

IFS-generated fractal animation — no AI, no stock footage. Browse the full collection at mathrelaxing.store/bundle/fractal-flames-loop-pack
""",

"harmonic-geometry-loop-pack": """\
3 seamless loop animations of harmonic geometry — Lissajous figures and harmonograph curves animated as the oscillations evolve in real time, in HD and 4K.

Watch the mathematics of resonance unfold: two oscillations at different frequencies trace curves that slowly precess and transform. The result is meditative, endlessly fascinating motion — the geometry of sound made visible and alive.

**What you get:**
- 3 unique harmonic loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Meditation and mindfulness visual content
- Ambient display art and screensavers
- Music and audio visualization backgrounds
- Stream overlays with minimal aesthetic
- YouTube intros and study/focus content
- Live wallpapers

Computed from oscillation physics — no AI, pure harmonic mathematics. Browse the full collection at mathrelaxing.store/bundle/harmonic-geometry-loop-pack
""",

"fractal-series-loop-pack": """\
3 seamless loop animations of fractal series — Julia sets and Mandelbrot-derived structures animated as the parameter c sweeps through the complex plane, in HD and 4K.

Watch fractal boundaries emerge, dissolve, and transform: z_{n+1} = z_n² + c, with c varying continuously. The animation reveals how dramatically the fractal structure changes as you move through parameter space — from connected dendrites to scattered dust clouds to intricate spirals.

**What you get:**
- 3 unique fractal loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Mathematics education and visualization content
- Ambient display art and screensavers
- YouTube and social media content for science channels
- Stream overlays with a cerebral aesthetic
- Live wallpapers and digital art displays

Computed from complex iteration — no AI, pure fractal mathematics in motion. Browse the full collection at mathrelaxing.store/bundle/fractal-series-loop-pack
""",

"radial-symmetry-loop-pack": """\
3 seamless loop animations of radial symmetry — rose curves and superformula patterns rotating and morphing as their parameters evolve, in HD and 4K.

Pure rotational mathematics in motion: k-fold symmetry blooming, spinning, and transforming. These animations make the parameter space of polar equations visible — from simple petals to complex multi-layered geometric flowers.

**What you get:**
- 3 unique radial symmetry loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Mandala and geometric meditation content
- Ambient display art and digital frames
- Yoga and wellness visual backgrounds
- Stream overlays with a geometric aesthetic
- Instagram Reels and TikTok backgrounds

Computed from polar equations — no AI, pure rotational mathematics. Browse the full collection at mathrelaxing.store/bundle/radial-symmetry-loop-pack
""",

"reaction-diffusion-loop-pack": """\
3 seamless loop animations of reaction-diffusion systems — Gray-Scott chemical simulations evolving in real time, producing organic patterns that pulse, spread, and self-organize, in HD and 4K.

Watch chemistry happen mathematically: ∂u/∂t = Du∇²u − uv² + f(1−u). Two virtual chemicals interact across a 2D grid, generating coral-like growth, labyrinthine patterns, and pulsing spots — the same mathematics that creates animal coat patterns and coral formations, animated live.

**What you get:**
- 3 unique reaction-diffusion loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Organic and biomorphic ambient displays
- Science and biology video content
- Stream overlays with a living, breathing aesthetic
- Ambient art installations and digital frames
- Instagram Reels and TikTok backgrounds

Real-time chemical simulation — no AI, pure reaction-diffusion mathematics. Browse the full collection at mathrelaxing.store/bundle/reaction-diffusion-loop-pack
""",

"complex-plane-loop-pack": """\
3 seamless loop animations of complex plane geometry — Möbius transformations and conformal mappings animated as their parameters vary, in HD and 4K.

Watch geometry bend: grids transform into spirals, circles invert into lines, the entire complex plane flows through continuous transformations. f(z) = (az+b)/(cz+d) with slowly varying parameters creates a visual journey through the space of all conformal mappings.

**What you get:**
- 3 unique complex plane loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Mathematics and physics education content
- Ambient display art with an intellectual aesthetic
- Stream overlays for tech and science channels
- YouTube intros for math and engineering content
- Screensavers and digital art displays

Computed from complex analysis — no AI, pure Möbius transformation mathematics. Browse the full collection at mathrelaxing.store/bundle/complex-plane-loop-pack
""",

"turing-patterns-loop-pack": """\
3 seamless loop animations of Turing patterns — reaction-diffusion simulations showing how spots, stripes, and labyrinths emerge and evolve over time, in HD and 4K.

Alan Turing's 1952 morphogenesis equations animated: watch chemical concentrations self-organize from random noise into structured patterns — the same process that gives leopards their spots and zebras their stripes, happening in real time before your eyes.

**What you get:**
- 3 unique Turing pattern loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Biology and science education visual content
- Organic ambient displays and digital art
- Stream overlays with a living texture aesthetic
- Instagram Reels for science communicators
- Ambient screensavers and live wallpapers

Simulated from Turing's morphogenesis equations — no AI, pure mathematical biology. Browse the full collection at mathrelaxing.store/bundle/turing-patterns-loop-pack
""",

"voronoi-organics-loop-pack": """\
3 seamless loop animations of organic Voronoi diagrams — cellular structures that pulse, grow, and reorganize as their seed points move, in HD and 4K.

Living cellular geometry: Voronoi cells shifting as seed points slowly drift, creating the visual impression of biological tissue breathing, or cells dividing and reorganizing. The mathematics of spatial partitioning made organic and alive.

**What you get:**
- 3 unique Voronoi loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Organic and biomorphic ambient displays
- Nature and biology visual content
- Stream overlays with a cellular texture
- Ambient screensavers and digital frames
- Instagram Reels and TikTok backgrounds

Computed from dynamic Voronoi mathematics — no AI, pure spatial geometry in motion. Browse the full collection at mathrelaxing.store/bundle/voronoi-organics-loop-pack
""",

"chladni-figures-loop-pack": """\
3 seamless loop animations of Chladni figures — nodal vibration patterns morphing between different vibrational modes as the frequency parameter sweeps continuously, in HD and 4K.

Watch the shapes of sound transform: as the driving frequency changes, the sand (simulated mathematically) reorganizes from one symmetric nodal pattern to another. It's a visual journey through the spectrum of acoustic resonance.

**What you get:**
- 3 unique Chladni loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Physics and acoustics education content
- Mandala-style ambient displays
- Stream overlays with a geometric aesthetic
- Music and sound art visual content
- Screensavers and live wallpapers

Computed from acoustic vibration mathematics — no AI, pure resonance physics. Browse the full collection at mathrelaxing.store/bundle/chladni-figures-loop-pack
""",

"de-jong-loop-pack": """\
3 seamless loop animations of De Jong attractors — iterated map systems morphing between parameter sets, tracing ever-evolving particle clouds, in HD and 4K.

Watch the De Jong attractor transform: as parameters a, b, c, d vary continuously, the dense particle cloud reshapes from one intricate pattern to another — lattices dissolving into webs, webs reforming into geometric meshes, all in seamless motion.

**What you get:**
- 3 unique De Jong loop animations
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Abstract ambient displays and digital frames
- Generative art and math art video content
- Stream overlays with a particle aesthetic
- Instagram Reels and TikTok backgrounds
- Screensavers and live wallpapers

Computed from De Jong iterated function mathematics — no AI, pure parameter space exploration. Browse the full collection at mathrelaxing.store/bundle/de-jong-loop-pack
""",

"particle-systems-loop-pack": """\
5 seamless loop animations of mathematical particle systems — tens of thousands of particles governed by vortex forces, gravity wells, electromagnetic fields, and wave interference, in HD and 4K.

Pure physics simulation made beautiful: particles respond to mathematical force fields — spiraling into vortices, orbiting gravity wells, forming interference patterns, assembling into nebula-like clouds. Each animation is a different physical system, all running in real time.

**What you get:**
- 5 unique particle system loop animations (vortex, nebula, electric field, wave, galaxy spiral)
- 4 export formats per animation: 1080p30, 1080p60, 4K30, 4K60
- Seamless loop — no visible cut point
- Instant download link emailed after purchase

**Perfect for:**
- Sci-fi and space-themed visual content
- Music visualizer and album release backgrounds
- Stream overlays with epic visual impact
- YouTube intros for science and tech channels
- Ambient display art and digital frames
- Instagram Reels and TikTok backgrounds

Real physics simulation with tens of thousands of particles — no AI, pure mathematical force fields. Browse the full collection at mathrelaxing.store/bundle/particle-systems-loop-pack
""",

"particle-systems-image-pack": """\
5 high-resolution mathematical art images of particle systems — tens of thousands of particles frozen mid-flight through vortex tunnels, nebula clouds, electric storms, spiral galaxies, and interference waves.

Each image captures a single moment of a live physics simulation: F = f(x, y, t). Particles respond to mathematical force fields, leaving dense trails that reveal the invisible structure of the field itself — the result is otherworldly, detailed, and impossible to find in any stock library.

**What you get:**
- 5 unique particle system images (vortex, nebula, electric field, wave interference, galaxy)
- Portrait (3200×4000), landscape (4000×3200), and square (3200×3200) orientations
- 4K resolution — print-ready and screen-perfect
- Instant download link emailed after purchase

**Perfect for:**
- Sci-fi and space-themed wallpapers
- Epic art prints and large-format posters
- Album covers and music visual content
- YouTube thumbnails for science channels
- Social media content with maximum visual impact
- Generative and mathematical art collections

Simulated from particle physics equations — no AI, no post-processing. Browse the full collection at mathrelaxing.store/bundle/particle-systems-image-pack
""",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg): print(msg, flush=True)

def fetch_image(url):
    r = requests.get(url, timeout=40)
    if r.ok:
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    return None

def make_collage(imgs, W=1600, H=900, COLS=4, GAP=6, BG=(15,15,15)):
    n = len(imgs)
    cols = min(COLS, n)
    rows = math.ceil(n / cols)
    cw = (W - GAP*(cols+1)) // cols
    ch = (H - GAP*(rows+1)) // rows
    canvas = Image.new("RGB", (W, H), BG)
    for i, img in enumerate(imgs):
        col, row = i % cols, i // cols
        img.thumbnail((cw, ch), Image.LANCZOS)
        x = GAP + col*(cw+GAP) + (cw-img.width)//2
        y = GAP + row*(ch+GAP) + (ch-img.height)//2
        canvas.paste(img, (x, y))
    return canvas

def make_square(img, size=600):
    s = min(img.width, img.height)
    x = (img.width-s)//2; y = (img.height-s)//2
    return img.crop((x,y,x+s,y+s)).resize((size,size), Image.LANCZOS)

def get_csrf():
    r = requests.get("https://gumroad.com/", headers={"Authorization": f"Bearer {token}"})
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', r.text)
    return (m.group(1) if m else ""), r.cookies

def upload_blob_s3(csrf, cookies, fname, file_bytes, ctype="image/jpeg"):
    md5 = base64.b64encode(hashlib.md5(file_bytes).digest()).decode()
    r = requests.post("https://gumroad.com/rails/active_storage/direct_uploads",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "application/json", "X-CSRF-Token": csrf},
        cookies=cookies,
        json={"blob": {"filename": fname, "byte_size": len(file_bytes),
                       "checksum": md5, "content_type": ctype}})
    blob = r.json()
    du = blob["direct_upload"]
    requests.put(du["url"], data=file_bytes, headers={**du["headers"], "Content-Type": ctype})
    return blob["signed_id"]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db = SessionLocal()
    published = _load_map()
    products = {p.slug: p for p in db.query(DigitalProduct).filter(DigitalProduct.active==True).all()}
    db.close()

    remaining = [slug for slug in products if slug not in published]
    log(f"Publishing {len(remaining)} products...\n")

    csrf, cookies = get_csrf()

    for i, slug in enumerate(remaining):
        p = products[slug]
        items = json.loads(p.contents_json or "[]")
        gumroad_price = math.ceil(p.price_usd / 0.90)
        is_loop = "loop" in slug
        anim_key = next((it.get("animation_key") for it in items if it.get("animation_key")), None)

        log(f"[{i+1}/{len(remaining)}] {slug}  ${p.price_usd} → ${gumroad_price}  {'loop' if is_loop else 'image'}")

        desc = DESCRIPTIONS.get(slug, _product_description(p))
        payload = {
            "access_token":   token,
            "name":           p.name,
            "price":          gumroad_price * 100,
            "description":    desc.strip(),
            "custom_summary": (p.description or "")[:150],
            "shown_on_profile": "true",
            "published":      "false",  # create unpublished, then enable
        }

        # ── Step 1: Create product ──────────────────────────────────────────
        r = requests.post(f"{API_BASE}/products", data=payload)
        body = r.json()
        if not body.get("success"):
            log(f"  ✗ CREATE failed: {body.get('message','?')} (status {r.status_code})")
            if r.status_code == 429:
                log("  Rate limited — waiting 60s before retrying")
                time.sleep(60)
                r = requests.post(f"{API_BASE}/products", data=payload)
                body = r.json()
                if not body.get("success"):
                    log(f"  ✗ Retry failed: {body.get('message','?')}")
                    time.sleep(8)
                    continue

        prod_data = body.get("product", {})
        gid = prod_data.get("id")
        if not gid:
            log(f"  ✗ No product ID in response"); time.sleep(8); continue

        published[slug] = gid
        _save_map(published)
        log(f"  ✓ Created  gid={gid}")
        time.sleep(3)

        # ── Step 2: Enable ────────────────────────────────────────────────
        r2 = requests.put(f"{API_BASE}/products/{gid}/enable", data={"access_token": token})
        body2 = r2.json()
        log(f"  {'✓' if body2.get('success') else '✗'} Enabled  published={body2.get('product',{}).get('published')}")
        time.sleep(2)

        # ── Step 3: Cover ─────────────────────────────────────────────────
        if is_loop and anim_key:
            video_url = f"{BASE_PUBLIC}/api/video/{anim_key}?format=1080p30"
            r3 = requests.post(f"{API_BASE}/products/{gid}/covers",
                               data={"access_token": token, "url": video_url})
            log(f"  {'✓' if r3.json().get('success') else '✗'} Cover (video) → {anim_key}")
        else:
            # Build collage from bundle items
            n_items = min(8, len(items))
            imgs = []
            for idx in range(n_items):
                img = fetch_image(f"{BASE_LOCAL}/api/render/bundle-item?product={slug}&index={idx}")
                if img: imgs.append(img)
            if imgs:
                collage = make_collage(imgs)
                buf = io.BytesIO(); collage.save(buf, "JPEG", quality=92); buf.seek(0)
                out_path = f"{COVERS_DIR}/{slug}.jpg"
                collage.save(out_path, "JPEG", quality=92)
                cover_url = f"{BASE_PUBLIC}/static/covers/{slug}.jpg"
                r3 = requests.post(f"{API_BASE}/products/{gid}/covers",
                                   data={"access_token": token, "url": cover_url})
                log(f"  {'✓' if r3.json().get('success') else '✗'} Cover (collage {len(imgs)} imgs)")
            else:
                log(f"  ✗ Cover: no images fetched")
        time.sleep(2)

        # ── Step 4: Thumbnail via S3 blob ─────────────────────────────────
        thumb_src = fetch_image(f"{BASE_LOCAL}/api/render/bundle-item?product={slug}&index=0")
        if thumb_src:
            thumb = make_square(thumb_src)
            buf = io.BytesIO(); thumb.save(buf, "JPEG", quality=92)
            file_bytes = buf.getvalue()
            try:
                signed_id = upload_blob_s3(csrf, cookies, f"{slug}-thumb.jpg", file_bytes)
                r4 = requests.post(f"{API_BASE}/products/{gid}/thumbnail",
                                   data={"access_token": token, "signed_blob_id": signed_id})
                body4 = r4.json()
                log(f"  {'✓' if body4.get('success') else '✗'} Thumbnail  {body4.get('thumbnail',{}).get('url','')[:50]}")
            except Exception as e:
                log(f"  ✗ Thumbnail error: {e}")
        time.sleep(2)

        # ── Step 5: Tags + rich description ──────────────────────────────
        tags = TAGS.get(slug, [])
        data = [("access_token", token), ("description", desc.strip())] + [("tags[]", t) for t in tags]
        r5 = requests.put(f"{API_BASE}/products/{gid}", data=data)
        body5 = r5.json()
        log(f"  {'✓' if body5.get('success') else '✗'} Tags+desc  {body5.get('product',{}).get('tags',[])}")

        log(f"  Done ✓  {BASE_PUBLIC}/bundle/{slug}\n")

        # Conservative delay between products
        if i < len(remaining) - 1:
            log("  Waiting 12s before next product...")
            time.sleep(12)

    log(f"\n=== All done. Published map now has {len(published)} products ===")

if __name__ == "__main__":
    main()
