import os
import json
from contextlib import asynccontextmanager
from datetime import date
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

from database import engine, get_db
from models.product import Base, Product, Order, Certificate, DigitalProduct, Purchase
from routers import products, orders, render, mockup, webhooks
from routers import pinterest as pinterest_router
from routers import meta_ads as meta_ads_router
from routers import tiktok as tiktok_router
from routers import gpt as gpt_router
from routers import lowpoly as lowpoly_router
from models.tiktok_post import TikTokPost
from routers import telegram_bot as telegram_bot_router
from routers import ebay as ebay_router
from routers import gumroad as gumroad_router
from routers import bonanza as bonanza_router
from routers import live as live_router
from routers.coupons import router as coupons_router
from seed import get_seed_products
from routers import admin as admin_router
from routers import pet_admin as pet_admin_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COLLECTIONS = {
    "strange-attractors": {
        "name": "Strange Attractors",
        "description": "Chaotic trajectories through phase space. Lorenz, Clifford, Aizawa — systems that never repeat yet stay forever bounded.",
        "equation": "dx/dt = σ(y−x),  dy/dt = x(ρ−z)−y,  dz/dt = xy−βz",
    },
    "de-jong-attractors": {
        "name": "De Jong Attractors",
        "description": "Dense, complex attractor patterns from the De Jong map — intricate weaves, lattices, and fractal structures with stunning detail.",
        "equation": "x' = sin(a·y) − cos(b·x),  y' = sin(c·x) − cos(d·y)",
    },

    "complex-plane-geometry": {
        "name": "Complex Plane Geometry",
        "description": "Elegant transformations of the complex plane. Möbius grids and Joukowski airfoils reveal the hidden geometry of conformal mappings.",
        "equation": "f(z) = (az+b)/(cz+d),  w = z + 1/z",
    },
    "radial-symmetry": {
        "name": "Radial Symmetry",
        "description": "Rose curves and superformulas unfolding around a center point. Floral, orbital, and architectural forms generated from polar mathematics.",
        "equation": "r(theta) = a cos(k theta),  r(phi) = (|cos(m phi / 4)|^n2 + |sin(m phi / 4)|^n3)^(-1 / n1)",
    },
    "reaction-diffusion": {
        "name": "Reaction Diffusion",
        "description": "Two chemical species competing across space. Gray-Scott systems generate coral, fingerprints, spirals, and labyrinths from nothing but diffusion rates and a feed-kill pair.",
        "equation": "∂u/∂t = Du∇²u − uv² + f(1−u),  ∂v/∂t = Dv∇²v + uv² − (f+k)v",
    },
    "fractal-series": {
        "name": "Fractal Series",
        "description": "The boundary between order and chaos in the complex plane. Julia sets and the Mandelbrot set reveal infinite self-similar structure from a single iterated equation.",
        "equation": "z_{n+1} = z_n² + c,  escape when |z| ≥ 2",
    },
    "turing-patterns": {
        "name": "Turing Patterns",
        "description": "Reaction-diffusion patterns that mimic nature's designs. Spots, stripes and labyrinths emerge from chemical interactions, just as they do on animal coats and coral formations.",
        "equation": "∂u/∂t = Du∇²u + f(u,v),  ∂v/∂t = Dv∇²v + g(u,v)",
    },
    "voronoi-organics": {
        "name": "Voronoi Organics",
        "description": "Cellular structures found throughout nature. From bubbles to cracked earth, biological tissue to frost patterns—these organic Voronoi diagrams reveal the hidden geometry of natural formations.",
        "equation": "V(p) = {x | d(x,p) ≤ d(x,q) ∀ q ∈ P}",
    },
    "chladni-figures": {
        "name": "Chladni Figures",
        "description": "Nodal patterns of vibration—visualizing sound through geometry. These intricate mandala-like formations emerge from standing waves on resonant plates, revealing the hidden music of mathematics.",
        "equation": "Z(x,y) = sin(mπx)sin(nπy) + sin(nπx)sin(mπy)",
    },

    "flow-fields": {
        "name": "Flow Fields",
        "description": "Particles tracing vector fields and curl noise — turbulent, wind-swept streams and organic currents rendered from continuous flow mathematics.",
        "equation": "v(x, y) = ∇ × A(x, y)",
    },
    "fractal-flames": {
        "name": "Fractal Flames",
        "description": "Luminous fractal flames built from iterated function systems — glowing, smoke-like structures with infinite fine detail and organic color.",
        "equation": "F(x) = Σ pᵢ · fᵢ(x)",
    },
    "harmonic-geometry": {
        "name": "Harmonic Geometry",
        "description": "Lissajous figures, harmonographs and rose curves — the elegant geometry of combined oscillations and harmonic motion made visible.",
        "equation": "x = A·sin(a·t + δ),  y = B·sin(b·t)",
    },
    "notebooks": {
        "name": "Notebooks",
        "description": "Premium spiral notebooks with edge-to-edge mathematical art covers, each generated from a real equation.",
        "equation": "generative mathematical art printed on premium spiral notebooks",
    },
    "coloring-books": {
        "name": "Coloring Books",
        "description": "Mathematical coloring books — 50 hand-crafted line-art designs per book, drawn from real equations. Printable and physical editions.",
        "equation": "50 line-art designs per book, generated from real mathematics",
    },
    "coloring-book": {
        "name": "Coloring Books",
        "description": "Mathematical coloring books — 50 hand-crafted line-art designs per book, drawn from real equations. Printable and physical editions.",
        "equation": "50 line-art designs per book, generated from real mathematics",
    },

    "desk-mats": {
        "name": "Desk Mats",
        "description": "Wide-format mathematical compositions designed specifically for mouse pads and gaming desk mats. Horizontal, full-bleed designs built for a workspace rather than adapted from poster art.",
        "equation": "full-bleed landscape mathematical compositions for desk surfaces",
    },
    "apparel": {
        "name": "Apparel",
        "description": "Mathematical art made to wear — exclusive designs created specifically for premium tees, printed with true transparency so the equation floats clean on the fabric. Not poster reprints: each piece is composed for the body.",
        "equation": "attractors & harmonographs composed for fabric, on true-transparent backgrounds",
    },

    "digital-downloads": {
        "name": "Digital Downloads",
        "description": "Instant-download digital products — printable coloring book PDFs, iPad coloring bundles for GoodNotes & Procreate, STEM notebooks, and seamless loop animations. Every file is generated from real mathematics. Pay, download, keep forever.",
        "equation": "printable PDFs · iPad bundles · STEM notebooks · loop animations",
    },

}

# Physical product collection -> (card type label, grouping section title).
_PHYSICAL_LABELS = {
    "desk-mats": ("Desk Mat", "Desk Mats"),
    "apparel":   ("T-Shirt", "Apparel"),
}

# --- Digital-downloads grouping ------------------------------------------------
# Several distinct products share a product_type (esp. 'thematic_bundle' and
# 'ipad_bundle'), so keying sections off product_type alone dumped unrelated
# items together. These helpers split by slug so related products cluster into
# coherent, intuitively-ordered sections. Shared by the collection page and the
# homepage so both present the digital catalog the same way.
_DIGITAL_GROUP_BASE = {
    "digital_planner": "STEM Notebooks & Planners",
    "digital_notebook": "STEM Notebooks & Planners",
    "document_template": "Templates & Organizers",
    "printable_pdf": "Printable Coloring PDFs",
    "animation_pack": "4K Loop Animations",
    "image_pack": "Image Bundles",
    "creator_assets": "Creator Assets",
}

# Most-wanted-first display order for the digital sections.
DIGITAL_SECTION_ORDER = [
    "Printable Coloring PDFs",
    "iPad Coloring Bundles · GoodNotes & Procreate",
    "Interactive iPad Color-by-Number Apps",
    "STEM Notebooks & Planners",
    "Equation & Art Print Sets",
    "Templates & Organizers",
    "Procreate Color Palettes",
    "4K Loop Animations",
    "Image Bundles",
    "Creator Assets",
    "Digital Downloads",
]


def digital_group(p) -> str:
    """The section a digital product belongs to on /collection/digital-downloads."""
    s = (p.slug or "").lower()
    if p.product_type == "ipad_bundle":
        if "interactive" in s or "svg" in s:
            return "Interactive iPad Color-by-Number Apps"
        return "iPad Coloring Bundles · GoodNotes & Procreate"
    if p.product_type == "document_template":
        return "Templates & Organizers"
    if p.product_type == "thematic_bundle":
        if "procreate" in s or "palette" in s:
            return "Procreate Color Palettes"
        if any(k in s for k in ("print-set", "prints", "poster", "equation")):
            return "Equation & Art Print Sets"
        return "Digital Downloads"
    return _DIGITAL_GROUP_BASE.get(p.product_type, "Digital Downloads")


def digital_type_label(p) -> str:
    """Card sub-label that reads like a product, not a code enum."""
    s = (p.slug or "").lower()
    if p.product_type == "ipad_bundle":
        return "Interactive iPad App" if ("interactive" in s or "svg" in s) else "iPad Bundle"
    if p.product_type == "document_template":
        if "resume" in s:
            return "Resume Kit"
        if "recommendation" in s or "lor" in s:
            return "Letter Templates"
        if "emergency" in s or "binder" in s:
            return "Printable Binder"
        return "Template Pack"
    if p.product_type == "thematic_bundle":
        if "procreate" in s or "palette" in s:
            return "Procreate Palette"
        if any(k in s for k in ("print-set", "prints", "poster", "equation")):
            return "Print Set"
        return "Digital Bundle"
    return p.product_type.replace("_", " ").title()


# Unique long-form mathematical content per collection — used to enrich bundle
# pages with non-duplicated, indexable text. Each entry is ~120-180 words. The
# goal is to give Google substantive content per page (combats "Discovered:
# currently not indexed" thin-content perception) while giving readers actual
# context about what they're buying.

COLLECTION_MATH = {
    "strange-attractors": (
        "A strange attractor is a region of phase space toward which a dynamical system "
        "evolves over time — but unlike a fixed point or a periodic orbit, the trajectory "
        "never repeats. It folds and stretches forever inside a bounded volume. The Lorenz "
        "attractor, discovered by Edward Lorenz in 1963 while modeling atmospheric "
        "convection, is the canonical example: three coupled differential equations whose "
        "solutions trace a butterfly-shaped manifold that has become a symbol of "
        "deterministic chaos. The Clifford and Aizawa systems extend this idea with "
        "different nonlinear couplings, producing scrolls, shells, and toroidal sheets. "
        "What you see in these images is not a sketch or a stylization — each line is the "
        "literal trajectory of a point obeying the equations, rendered at full numerical "
        "precision over millions of integration steps."
    ),
    "de-jong-attractors": (
        "The De Jong map is a two-dimensional discrete dynamical system defined by four "
        "real parameters: x' = sin(a·y) − cos(b·x), y' = sin(c·x) − cos(d·y). It was "
        "popularized by Peter de Jong in the 1980s as a generator of dense, intricate "
        "attractor patterns. Iterating the map millions of times and recording every visited "
        "point produces lattices, weaves, and fractal embroideries with stunning fine "
        "structure — small changes in (a, b, c, d) reveal completely different worlds inside "
        "the same equation. Each image in this collection is a single set of parameters "
        "iterated at high density, with point-density coloring that reveals the underlying "
        "probability distribution of the map. The result feels woven, almost textile — "
        "patterns that emerge from pure trigonometric iteration."
    ),
    "harmonic-geometry": (
        "Harmonographs are mechanical drawing devices invented in the 1840s that use "
        "coupled pendulums to trace Lissajous-like curves with slowly decaying amplitude. "
        "The mathematics is simple — x(t) = A·sin(f₁t + φ)·e^(−dt), y(t) = B·sin(f₂t)·e^(−dt) "
        "— but the visual result is anything but: looped rosettes, knotted braids, and "
        "spirographs that breathe inward as the pendulums lose energy. By choosing "
        "frequency ratios near small integer fractions, you get closed figures; choose them "
        "irrational and the curve fills the canvas with quasi-periodic embroidery. Lissajous "
        "figures, the closed limit case, were first studied by Jules-Antoine Lissajous in "
        "1857 to visualize sound interference. Every image in this collection is the literal "
        "trace of two oscillators, rendered as continuous strokes through phase space."
    ),
    "complex-plane-geometry": (
        "The complex plane is the natural home of conformal transformations — maps that "
        "preserve angles locally while warping distances. Möbius transformations of the form "
        "f(z) = (az + b) / (cz + d) move circles to circles and lines to lines, and they "
        "generate every angle-preserving symmetry of the Riemann sphere. The Joukowski "
        "transform w = z + 1/z maps a circle to an airfoil cross-section — the same one "
        "used in early aerodynamics to compute lift. Apply these maps to a regular grid "
        "and the result is unmistakably geometric and unmistakably mathematical: the "
        "lines bend exactly as the complex algebra demands. Each image and animation in "
        "this collection is computed from the underlying complex function — no Bézier "
        "curves, no artistic license."
    ),
    "radial-symmetry": (
        "Polar coordinates collapse two-dimensional geometry to two simple ideas: a "
        "distance from the center and an angle around it. From this minimal starting point "
        "you can grow elaborate symmetric forms. The rose curves r = a·cos(kθ) trace petal "
        "patterns whose count depends on whether k is even or odd. The superformula of "
        "Johan Gielis generalizes this further with six parameters, producing flowers, "
        "stars, leaves, and shells from a single closed-form expression. The result is "
        "geometry that recalls nature without imitating it — the same mathematics that "
        "describes radiolaria, snowflakes, and pollen grains. Every form in this collection "
        "is the literal locus of a polar equation, rendered as a continuous mathematical "
        "object."
    ),
    "reaction-diffusion": (
        "Reaction-diffusion systems model two chemical species that diffuse across space "
        "and react with one another according to nonlinear coupling. The Gray-Scott model "
        "uses just two parameters — a feed rate and a kill rate — and yet produces an "
        "astonishing zoo of patterns: spots that self-replicate like cells, labyrinths that "
        "tile the plane, traveling fronts, and coral-like growth. Alan Turing first proposed "
        "in 1952 that such systems could explain the spots on a leopard and the stripes on "
        "a zebra. Every image in this collection is a snapshot of a simulation: a grid of "
        "concentrations updated thousands of time steps until the pattern stabilizes or "
        "settles into perpetual motion. Nothing here is hand-drawn — the patterns emerge "
        "from the equations alone."
    ),
    "fractal-series": (
        "The Mandelbrot set and its companion Julia sets live in the complex plane at the "
        "edge of order and chaos. For each complex number c, iterate z → z² + c starting "
        "from z = 0: if the sequence stays bounded, c belongs to the Mandelbrot set; "
        "otherwise, the escape speed colors the surrounding fractal boundary. Julia sets "
        "fix c and vary the starting point, producing connected dust, dendrites, or solid "
        "regions depending on where c lies. Both reveal infinite self-similar detail at "
        "every zoom level — you can keep magnifying forever and the structure keeps "
        "renewing itself. Every image in this collection is computed at high iteration depth "
        "with smooth-iteration coloring, so the gradients you see correspond exactly to how "
        "fast each point escapes."
    ),
    "turing-patterns": (
        "Turing patterns are the spatial structures that arise when two diffusing chemicals "
        "react at different rates. Alan Turing showed in 1952 that under the right "
        "conditions, an initially uniform mixture will spontaneously break symmetry and "
        "settle into stripes, spots, or labyrinths — purely as a consequence of diffusion "
        "rates and reaction kinetics, without any external template. The same mechanism is "
        "now believed to govern the markings on fish, the arrangement of hair follicles, and "
        "the branching of fingers in embryonic limbs. Each image in this collection is a "
        "Turing simulation run to equilibrium on a high-resolution grid. The patterns are not "
        "designed — they self-organize from random noise, the way they do on a leopard."
    ),
    "voronoi-organics": (
        "Given a set of points in the plane, the Voronoi diagram partitions space into "
        "regions where each region contains every location closer to its seed point than to "
        "any other. The cells tile space perfectly, with shared edges marking the lines of "
        "equal distance between neighbors. This simple geometric idea governs an enormous "
        "range of natural structures: the cracking of dried mud, the cells of biological "
        "tissue, the territories of birds, the foam of soap bubbles, the structure of "
        "metallic grains. By choosing different point distributions — Poisson, jittered grid, "
        "centroidal relaxation — you get different organic vocabularies. Every image here is "
        "a literal Voronoi computation over carefully placed seeds, rendered with shaded "
        "cells and crisp edges."
    ),
    "chladni-figures": (
        "When a thin plate is set into vibration at one of its resonant frequencies, sand "
        "scattered on its surface migrates to the nodal lines where the plate isn't moving — "
        "revealing the underlying vibration mode as a geometric pattern. Ernst Chladni first "
        "demonstrated this in 1787 with a violin bow on a brass plate, and the resulting "
        "figures helped found the field of acoustics. The mathematics is a sum of "
        "trigonometric eigenmodes: Z(x, y) = sin(mπx)·sin(nπy) + sin(nπx)·sin(mπy), where m "
        "and n are mode numbers. Each combination produces a distinct mandala. Every image "
        "in this collection is a high-resolution evaluation of these eigenmode sums, "
        "rendered as continuous fields rather than discrete sand grains."
    ),
    "flow-fields": (
        "A flow field assigns to every point in the plane a direction — and a particle "
        "dropped into the field will trace a curve that always follows the local arrow. "
        "Build the field from smoothly varying noise (Perlin, simplex, or layered sinusoids) "
        "and the resulting trajectories braid into curtains, vortices, and rivers without "
        "ever crossing. The technique sits at the boundary of generative art and "
        "computational fluid dynamics. Each image in this collection is the result of "
        "thousands of particles released into a fixed mathematical field, each one rendered "
        "as a continuous trail. The animations show the same fields evolving slowly in "
        "time, so that the entire flow pattern breathes while maintaining its underlying "
        "structure."
    ),
    "fractal-flames": (
        "Fractal flames are an iterated function system rendered with log-density coloring, "
        "developed by Scott Draves in 1992. A small set of affine transformations is "
        "applied repeatedly to a moving point, but each transformation can be composed "
        "with a nonlinear variation — sinusoids, spherical inversions, polar maps — that "
        "warps the result into organic, luminous forms. The log-density rendering, in which "
        "brightness scales with how often each pixel was visited, gives the images their "
        "characteristic glow and depth. Every image in this collection is computed from a "
        "specific set of transformations and variations, with millions of iterations driving "
        "each pixel value. The result feels painterly but is entirely the consequence of "
        "the underlying IFS algebra."
    ),
    "kleinian-gardens": (
        "Kleinian groups are discrete groups of Möbius transformations of the Riemann "
        "sphere — and the orbits of points under these groups produce some of the most "
        "intricate geometric objects in mathematics. Apollonian circle packings, the "
        "limit case where the group fills space with nested tangent circles, were studied "
        "by Apollonius of Perga around 200 BCE and rediscovered as a deep topic in "
        "hyperbolic geometry in the 20th century. The limit sets of more complex Kleinian "
        "groups produce dendritic, foam-like, and lace-like structures that tile the "
        "hyperbolic plane. Every image and animation in this collection is computed by "
        "iterating actual Möbius transformations and inversions, with the resulting circle "
        "packings rendered at full mathematical precision."
    ),
    "particle-systems": (
        "Particle systems treat each pixel as a discrete object responding to a "
        "mathematically defined force field — gravity wells, vortex centers, electromagnetic "
        "potentials, wave interference. Tens of thousands of particles released into the "
        "field trace continuous trajectories that, viewed in aggregate, reveal the shape of "
        "the field itself. The technique sits at the boundary of physics simulation and "
        "generative art. Every image and animation in this collection is the result of a "
        "live simulation: F = f(x, y, t) evaluated at each particle's position, integrated "
        "over time, with each particle leaving a trail proportional to its velocity. No two "
        "runs are identical, and yet the field structure remains unmistakable beneath the "
        "chaos."
    ),
}


# Per-equation educational copy for individual physical product pages.
# Reused across product variants of the same system (e.g. lorenz-classic and
# lorenz-storm share the Lorenz description). Differentiation between variants
# comes from the unique name, params, color palette, and rendered image.
# Keys match Product.equation_type values seeded in seed.py.

PRODUCT_MATH = {
    "lorenz": (
        "The Lorenz system is the canonical example of deterministic chaos. Three coupled "
        "ordinary differential equations — dx/dt = σ(y−x), dy/dt = x(ρ−z)−y, dz/dt = xy−βz "
        "— derived by Edward Lorenz in 1963 while modeling atmospheric convection. The "
        "trajectory through 3D phase space traces the now-iconic butterfly manifold, "
        "wrapping forever around two unstable equilibria without repeating. This print "
        "renders the literal path of a point obeying these equations, integrated over "
        "millions of fourth-order Runge-Kutta steps."
    ),
    "clifford": (
        "The Clifford attractor is a two-dimensional discrete iterated map popularized by "
        "Clifford A. Pickover: x' = sin(a·y) + c·cos(a·x), y' = sin(b·x) + d·cos(b·y). The "
        "trajectory never escapes a bounded region of the plane, but it also never repeats, "
        "filling out an intricate invariant measure that depends sensitively on the four "
        "parameters. Each image is the density map of millions of iterates, colored by how "
        "often each pixel was visited — a portrait of the attractor's hidden probability "
        "distribution."
    ),
    "aizawa": (
        "The Aizawa attractor is a three-dimensional continuous-time dynamical system: "
        "dx/dt = (z−b)x − dy, dy/dt = dx + (z−b)y, dz/dt = c + az − z³/3 − (x²+y²)(1+ez) "
        "+ fzx³. Unlike the planar Lorenz butterfly, Aizawa produces stacked toroidal "
        "shells with vertical filaments threading through them — a 3-body topology rarely "
        "seen in the strange-attractor literature. The image is the literal trajectory of "
        "a single point integrated through millions of steps."
    ),
    "de_jong": (
        "The De Jong map is a two-dimensional discrete iterated system defined by four "
        "real parameters: x' = sin(a·y) − cos(b·x), y' = sin(c·x) − cos(d·y). It was "
        "popularized by Peter de Jong in the 1980s and is famed for producing dense, "
        "woven, almost textile-like attractors whose appearance shifts dramatically with "
        "tiny changes in (a, b, c, d). Each image is millions of iterates rendered with "
        "density coloring, revealing the invariant measure of one specific parameter set."
    ),
    "mandelbrot": (
        "The Mandelbrot set is the most famous object in fractal mathematics: the set of "
        "complex numbers c for which the iteration z → z² + c (starting at z=0) remains "
        "bounded. Its boundary is infinitely complex, exhibiting self-similar detail at "
        "every magnification. Outside the set, points are colored by escape speed — how "
        "many iterations they take to grow past a threshold. The result is a high-precision "
        "rendering at deep iteration depth with smooth-iteration coloring."
    ),
    "julia": (
        "Julia sets are the partners of the Mandelbrot set: fix c and ask which starting "
        "points z₀ remain bounded under z → z² + c. The shape of each Julia set depends "
        "entirely on the chosen c — connected dust, dendrites, or solid regions emerge "
        "as c moves through the complex plane. Each image is a high-resolution Julia set "
        "for a specific c, rendered with smooth-iteration coloring so the color gradient "
        "corresponds directly to escape velocity."
    ),
    "harmonograph": (
        "A harmonograph is a 19th-century mechanical drawing device that uses two coupled "
        "pendulums with slowly decaying amplitude to trace ornate curves. The mathematics "
        "is a pair of damped sinusoids: x(t) = A·sin(f₁t + φ)·e^(−dt), "
        "y(t) = B·sin(f₂t + ψ)·e^(−dt). Choose frequency ratios near small integers and "
        "the curve closes into rosettes; choose them irrational and it spirals inward "
        "forever. This image is the literal trace of two oscillators in motion."
    ),
    "lissajous": (
        "Lissajous figures are the limit case of a harmonograph with no damping: "
        "x(t) = sin(at + δ), y(t) = sin(bt). When the ratio a/b is rational the curve "
        "closes into a figure with (a−1)(b−1) crossings; when it is irrational the trace "
        "fills a rectangle with a quasi-periodic weave. Jules-Antoine Lissajous studied "
        "these curves in 1857 using mirror-mounted tuning forks to visualize sound. This "
        "print is a single mathematical Lissajous curve, rendered at vector precision."
    ),
    "rose": (
        "Rose curves are defined in polar coordinates by r = a·cos(kθ) or r = a·sin(kθ). "
        "When k is an integer, the curve has k petals if k is odd, and 2k petals if k is "
        "even — a delightful number-theoretic surprise. When k is irrational, the petals "
        "never close and the curve fills the disk with a dense quasi-periodic pattern. "
        "This image is the literal locus of a single polar equation, traced as a continuous "
        "mathematical object."
    ),
    "superformula": (
        "The superformula, introduced by Johan Gielis in 1997, generalizes the polar rose "
        "curve with six free parameters: r(φ) = (|cos(mφ/4)/a|^n₂ + |sin(mφ/4)/b|^n₃)^(−1/n₁). "
        "By varying these parameters, the same single equation can produce flowers, "
        "stars, leaves, snowflakes, and shells. Gielis proposed it as a unified "
        "mathematical description of natural form. Each image is the literal trace of a "
        "specific parameter choice."
    ),
    "mobius-grid": (
        "Möbius transformations are the angle-preserving (conformal) maps of the Riemann "
        "sphere, all of the form f(z) = (az + b) / (cz + d). They take circles to circles "
        "and lines to lines, generate every symmetry of the hyperbolic plane, and underlie "
        "everything from special relativity boost transformations to the topology of "
        "knots. This image applies a single Möbius map to a regular grid, revealing the "
        "transformation's geometry directly."
    ),
    "joukowski": (
        "The Joukowski transform w = z + 1/z maps a circle in the complex z-plane to an "
        "airfoil cross-section in the w-plane — the same construction Nikolai Joukowski "
        "used in 1906 to derive lift in early aerodynamics. The transform is conformal "
        "everywhere except at z = ±1, where it concentrates the airfoil's trailing edge. "
        "This image visualizes the transform applied to a polar grid, producing an "
        "airfoil-shaped warp."
    ),
    "gray-scott": (
        "The Gray-Scott model is a reaction-diffusion system: two chemicals u and v "
        "diffuse across a grid and react with one another via ∂u/∂t = Dᵤ∇²u − uv² + "
        "f(1−u) and ∂v/∂t = Dᵥ∇²v + uv² − (f+k)v. Depending on the feed rate f and the "
        "kill rate k, the system produces self-replicating spots, labyrinths, traveling "
        "fronts, or coral-like growth. This image is a snapshot of a live simulation "
        "iterated to equilibrium on a high-resolution grid."
    ),
    "turing": (
        "Turing patterns emerge from Alan Turing's 1952 reaction-diffusion mechanism: an "
        "initially uniform mixture of two chemicals spontaneously breaks symmetry into "
        "spots, stripes, or labyrinths simply because the chemicals diffuse at different "
        "rates. Turing proposed this as the explanation for the markings on animal coats "
        "— leopard spots, zebra stripes, fish patterns. Each image is the equilibrium "
        "state of a Turing simulation, the patterns self-organizing from random initial "
        "noise."
    ),
    "voronoi": (
        "A Voronoi diagram partitions space into cells, one per seed point, where each "
        "cell contains every location closer to its seed than to any other. The "
        "construction is ancient — Descartes drew the first one in 1644 — but it governs "
        "an enormous range of natural structures: cracked mud, soap foam, biological "
        "tissue, metallic grain boundaries, even bird territory. This image is the literal "
        "Voronoi cell decomposition of a chosen seed distribution."
    ),
    "chladni": (
        "Chladni figures are the nodal patterns of a vibrating plate, first demonstrated "
        "by Ernst Chladni in 1787 by drawing a violin bow across a brass plate covered "
        "with sand. The sand migrates to the nodes — the lines where the plate isn't "
        "moving — revealing the underlying eigenmode of vibration. Mathematically: "
        "Z(x,y) = sin(mπx)·sin(nπy) + sin(nπx)·sin(mπy) for integer mode numbers m, n. "
        "This image is the literal level-set rendering of one such eigenmode sum."
    ),
    "flow-field": (
        "A flow field assigns a direction to every point in the plane. A particle dropped "
        "into the field traces a curve that always follows the local arrow. Build the "
        "field from smoothly varying noise (Perlin, simplex, or layered sinusoids) and "
        "thousands of trajectories braid into curtains, vortices, and rivers without ever "
        "crossing. This image is the result of thousands of particles released into one "
        "specific mathematical field, each particle leaving a continuous trail."
    ),
    "fractal-flame": (
        "Fractal flames, invented by Scott Draves in 1992, are an iterated function "
        "system rendered with log-density tone-mapping. A small set of affine "
        "transformations is applied repeatedly to a moving point, but each transformation "
        "is composed with a nonlinear variation — sinusoids, spherical inversion, polar "
        "maps — that warps the result into organic, luminous forms. The log-density "
        "coloring gives the images their characteristic glow. This print is the result of "
        "millions of iterations of one specific flame parameter set."
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _seed_products)
    await loop.run_in_executor(None, _seed_digital_products)
    warmup_task = asyncio.create_task(_warmup_preview_cache())
    ebay_task = asyncio.create_task(_ebay_order_poller())
    bonanza_task = asyncio.create_task(_bonanza_order_poller())
    pinterest_task = asyncio.create_task(_pinterest_auto_pin_loop())
    tiktok_task = asyncio.create_task(_tiktok_auto_post_loop())
    try:
        yield
    finally:
        warmup_task.cancel()
        ebay_task.cancel()
        bonanza_task.cancel()
        pinterest_task.cancel()
        tiktok_task.cancel()


def _seed_products():
    from database import SessionLocal
    db = SessionLocal()
    try:
        active_collections = {
            collection
            for (collection,) in db.query(Product.collection)
            .filter(Product.active == True)
            .distinct()
            .all()
        }
        target_collections = active_collections | set(COLLECTIONS.keys())
        existing_products = {p.slug: p for p in db.query(Product).all()}
        changed = False
        for p in get_seed_products():
            if p.get("collection") not in target_collections:
                continue
            existing = existing_products.get(p["slug"])
            if existing:
                existing.name = p["name"]
                existing.collection = p["collection"]
                existing.equation_type = p["equation_type"]
                existing.description = p.get("description")
                existing.params_json = p["params_json"]
                existing.price_usd = p["price_usd"]
                existing.image_url = p.get("image_url")
                # Do NOT touch `active` here: the seed refreshes product metadata,
                # but the publish/unpublish state is an admin decision that must
                # survive restarts. (Previously this line resurrected retired
                # products on every boot.)
                changed = True
                continue
            db.add(Product(**p))
            existing_products[p["slug"]] = p
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _seed_digital_products():
    """Seed digital product bundles from existing products."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        existing = {p.slug for p in db.query(DigitalProduct).all()}
        from seed_digital import get_digital_bundles
        for bundle in get_digital_bundles():
            if bundle["slug"] not in existing:
                db.add(DigitalProduct(**bundle))
        db.commit()
    except Exception as e:
        print(f"[seed_digital] FAILED: {e}", flush=True)
        import traceback; traceback.print_exc()
    finally:
        db.close()


async def _ebay_order_poller():
    """Poll eBay every 10 minutes for new orders and auto-fulfill them."""
    import asyncio
    from services import ebay as ebay_svc
    await asyncio.sleep(60)  # wait for server to settle
    while True:
        try:
            if ebay_svc.is_configured():
                from database import SessionLocal
                db = SessionLocal()
                try:
                    results = await ebay_svc.fulfill_new_orders(db)
                    if results:
                        print(f"[ebay poller] fulfilled {len(results)} orders", flush=True)
                finally:
                    db.close()
        except Exception as e:
            print(f"[ebay poller] error: {e}", flush=True)
        await asyncio.sleep(600)  # 10 minutes


async def _bonanza_order_poller():
    """Poll Bonanza every 10 minutes for completed digital orders."""
    import asyncio
    from services import bonanza as bonanza_svc
    await asyncio.sleep(75)  # wait for server to settle
    while True:
        try:
            if bonanza_svc.is_configured():
                from database import SessionLocal
                db = SessionLocal()
                try:
                    results = await bonanza_svc.fulfill_new_orders(db)
                    if results:
                        print(f"[bonanza poller] fulfilled {len(results)} orders", flush=True)
                finally:
                    db.close()
        except Exception as e:
            print(f"[bonanza poller] error: {e}", flush=True)
        await asyncio.sleep(600)


async def _pinterest_auto_pin_loop():
    """Periodically pin products to Pinterest. Disabled when no token is connected."""
    import asyncio
    interval_h = int(os.getenv("PINTEREST_CYCLE_HOURS", "4"))
    enabled = os.getenv("PINTEREST_AUTO_PIN_ENABLED", "1") != "0"
    if not enabled:
        print("[pinterest auto-pin] disabled via PINTEREST_AUTO_PIN_ENABLED=0", flush=True)
        return
    await asyncio.sleep(180)  # wait 3 min so warmup finishes first
    while True:
        try:
            from services import pinterest_jobs
            summary = await pinterest_jobs.run_auto_pin_cycle()
            if summary.get("created"):
                print(f"[pinterest auto-pin] created {summary['created']} pins "
                      f"(failed: {summary.get('failed', 0)})", flush=True)
            elif summary.get("skipped"):
                # quiet — most cycles will skip if nothing to pin or not connected
                pass
        except Exception as e:
            print(f"[pinterest auto-pin] error: {e}", flush=True)
        await asyncio.sleep(interval_h * 3600)


async def _tiktok_auto_post_loop():
    """Periodically post to TikTok using the Direct Post API."""
    import asyncio
    interval_h = int(os.getenv("TIKTOK_CYCLE_HOURS", "24"))
    enabled = os.getenv("TIKTOK_AUTO_POST_ENABLED", "1") != "0"
    if not enabled:
        print("[tiktok auto-post] disabled via TIKTOK_AUTO_POST_ENABLED=0", flush=True)
        return
    await asyncio.sleep(240)  # wait 4 min so warmup finishes first
    while True:
        try:
            from services import tiktok_jobs
            summary = await tiktok_jobs.run_auto_post_cycle()
            if summary.get("created"):
                print(f"[tiktok auto-post] created post (publish_id: {summary.get('publish_id')})", flush=True)
            elif summary.get("skipped"):
                pass
            elif summary.get("failed"):
                print(f"[tiktok auto-post] failed: {summary.get('error')}", flush=True)
        except Exception as e:
            print(f"[tiktok auto-post] error: {e}", flush=True)
        await asyncio.sleep(interval_h * 3600)


async def _warmup_preview_cache():
    """Pre-render preview images for all digital products on startup."""
    import asyncio
    import logging
    log = logging.getLogger("warmup")

    try:
        await asyncio.sleep(8)  # let the server settle

        from database import SessionLocal
        db = SessionLocal()
        try:
            # Exclude the digital-downloads section: those are uploaded PDFs/ZIPs
            # with static previews — they aren't equation-rendered, so warming
            # /api/render/* (esp. bundle-item) would 500 on their non-math content.
            products = db.query(DigitalProduct.slug, DigitalProduct.contents_json).filter(
                DigitalProduct.active == True,
                DigitalProduct.collection != "digital-downloads",
            ).all()
        finally:
            db.close()

        if not products:
            return

        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            # Warm main previews
            for slug, _ in products:
                try:
                    resp = await client.get(f"http://127.0.0.1:8000/api/render/preview?product={slug}")
                    if resp.status_code == 200:
                        print(f"[warmup] cached preview: {slug}", flush=True)
                except Exception as e:
                    print(f"[warmup] error preview: {slug} ({e})", flush=True)
                await asyncio.sleep(0.3)

            # Warm bundle item thumbnails
            for slug, contents_json in products:
                try:
                    import json as _json
                    items = _json.loads(contents_json or "[]")
                    for i in range(len(items)):
                        resp = await client.get(f"http://127.0.0.1:8000/api/render/bundle-item?product={slug}&index={i}")
                        if resp.status_code != 200:
                            print(f"[warmup] warn bundle-item: {slug}[{i}] (status {resp.status_code})", flush=True)
                except Exception as e:
                    print(f"[warmup] error bundle-items: {slug} ({e})", flush=True)
                await asyncio.sleep(0.2)

        print(f"[warmup] preview cache complete: {len(products)} products + bundle items", flush=True)
    except Exception as exc:
        print(f"[warmup] FAILED: {exc}", flush=True)


limiter = Limiter(key_func=get_remote_address)
# docs_url/redoc_url disabled in production: the interactive API consoles expose
# the full endpoint surface and are flagged by domain-security scanners (TikTok
# Business rejected the domain citing "security"). /openapi.json stays available
# because the ChatGPT Store action (low-poly tool) consumes it.
app = FastAPI(title="MathRelaxing Store", lifespan=lifespan,
              docs_url=None, redoc_url=None,
              servers=[{"url": "https://mathrelaxing.store"}])


@app.head("/")
async def home_head():
    return Response(status_code=200, media_type="text/html")


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

app.mount(
    "/.well-known",
    StaticFiles(directory=os.path.join(BASE_DIR, ".well-known")),
    name="well-known",
)

from jinja2 import FileSystemLoader, Environment
jinja_env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")))
jinja_env.globals["meta_pixel_id"] = os.getenv("META_PIXEL_ID", "").strip()


def _pinterest_verify_code():
    try:
        from services.pinterest_claim import get_verify_code
        return get_verify_code() or ""
    except Exception:
        return ""


jinja_env.globals["pinterest_verify_code"] = _pinterest_verify_code
templates = Jinja2Templates(env=jinja_env)

# ── Include routers ──────────────────────────────────────────────────────────
app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(render.router, prefix="/api")
app.include_router(mockup.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(gpt_router.router, prefix="/api")
app.include_router(lowpoly_router.router, prefix="/api")
app.include_router(telegram_bot_router.router, prefix="/api")
app.include_router(coupons_router, prefix="/api")
app.include_router(pinterest_router.router)
app.include_router(meta_ads_router.router)
app.include_router(tiktok_router.router)
app.include_router(ebay_router.router)
app.include_router(gumroad_router.router)
app.include_router(bonanza_router.router)
app.include_router(live_router.router)
app.include_router(admin_router.router)
app.include_router(pet_admin_router.router)


# ── Error handlers ───────────────────────────────────────────────────────────
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        html = templates.get_template("404.html").render({"request": request})
        return HTMLResponse(content=html, status_code=404)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# ── HTML routes ──────────────────────────────────────────────────────────────
@app.get("/start", response_class=HTMLResponse)
@app.get("/tiktok", response_class=HTMLResponse)
async def paid_landing(request: Request, db: Session = Depends(get_db)):
    """Focused landing page for cold paid-social traffic (TikTok/Meta).
    Minimal nav, a hero product with price + express Buy Now, and a small
    grid of low-priced hook bundles. Point ad campaigns here instead of /."""
    hooks = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True, DigitalProduct.product_type == "image_pack")
        .order_by(DigitalProduct.price_usd.asc())
        .limit(6)
        .all()
    )
    if not hooks:
        hooks = db.query(DigitalProduct).filter(DigitalProduct.active == True).order_by(DigitalProduct.price_usd.asc()).limit(6).all()
    hero = hooks[0] if hooks else None
    if hero is None:
        return RedirectResponse("/", status_code=302)
    cheapest = min(h.price_usd for h in hooks)
    qs = request.query_params
    return templates.TemplateResponse(
        "tiktok_landing.html",
        {
            "request": request,
            "hero": hero,
            "hooks": hooks,
            "cheapest": cheapest,
            "src": qs.get("utm_source", "tiktok"),
            "medium": qs.get("utm_medium", "paid_social"),
            "campaign": qs.get("utm_campaign", "landing"),
        },
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    # Apparel for the "Featured Clothing" strip. Previously this section was fed
    # ALL active digital products and rendered each as a t-shirt mockup — coloring
    # PDFs and iPad bundles shown as apparel. Feed it real apparel instead.
    apparel_rows = (db.query(Product)
                      .filter(Product.collection == "apparel", Product.active == True)
                      .order_by(Product.id).limit(8).all())
    _garment_fmt = {"hoodie": "unisex_hoodie", "aop_leggings": "aop_leggings",
                    "aop_joggers": "aop_joggers", "aop_sweatshirt": "aop_sweatshirt"}
    apparel = []
    for p in apparel_rows:
        garment = json.loads(p.params_json or "{}").get("garment", "tshirt")
        apparel.append({"slug": p.slug, "name": p.name, "price_usd": p.price_usd,
                        "format": _garment_fmt.get(garment, "unisex_tshirt")})
    notebooks = (db.query(Product)
                   .filter(Product.collection == "notebooks", Product.active == True)
                   .order_by(Product.id).limit(4).all())

    # A curated cross-section of the digital catalog, in the same intuitive order
    # as the collection page (coloring PDFs first, then iPad, then tools), so the
    # flagship instant-buy line actually has a correct presence on the homepage.
    all_digital = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    _rank = {name: i for i, name in enumerate(DIGITAL_SECTION_ORDER)}
    digital_featured = sorted(
        all_digital, key=lambda p: (_rank.get(digital_group(p), 99), (p.name or "").lower())
    )[:8]
    digital_featured = [
        {"slug": p.slug, "name": p.name, "price_usd": p.price_usd,
         "type_label": digital_type_label(p)}
        for p in digital_featured
    ]

    # Only surface printed-book promos for books that actually resolve — a
    # registered /book/ route AND an active product. This stops the homepage
    # linking to books that aren't published yet (dead /book/ 404s).
    book_slugs = {
        s for s in BOOK_TEMPLATES
        if db.query(Product).filter(Product.slug == s, Product.active == True).first()
    }

    collections_simple = {k: dict(v) if isinstance(v, dict) else v for k, v in COLLECTIONS.items()}
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "collections": collections_simple,
         "featured": apparel, "notebooks": notebooks,
         "digital_featured": digital_featured, "book_slugs": book_slugs},
    )


@app.get("/collections", response_class=HTMLResponse)
async def collections_page(request: Request, db: Session = Depends(get_db)):
    # Only show collections that still have published products.
    visible = {slug: col for slug, col in COLLECTIONS.items()
               if _collection_active_count(db, slug) > 0}

    # De-duplicate collections that render under the same display name (e.g.
    # coloring-book / coloring-books both show as "Coloring Books"), keeping the
    # slug with more published products so the index never shows twin cards.
    by_name = {}
    for slug, col in visible.items():
        name = col["name"]
        if (name not in by_name
                or _collection_active_count(db, slug) > _collection_active_count(db, by_name[name])):
            by_name[name] = slug
    deduped = {slug: visible[slug] for slug in by_name.values()}

    # Intuitive browse order: flagship instant-buy + core brand lines first, then
    # the mathematical-art print collections. Anything unlisted falls to the end.
    index_order = [
        "digital-downloads", "coloring-books", "coloring-book",
        "apparel", "notebooks", "desk-mats",
        "strange-attractors", "de-jong-attractors", "harmonic-geometry",
        "complex-plane-geometry", "radial-symmetry", "fractal-series",
        "fractal-flames", "flow-fields", "reaction-diffusion",
        "turing-patterns", "voronoi-organics", "chladni-figures",
    ]
    rank = {s: i for i, s in enumerate(index_order)}
    ordered = dict(sorted(deduped.items(), key=lambda kv: rank.get(kv[0], 999)))
    return templates.TemplateResponse("collections.html", {"request": request, "all_collections": ordered})


@app.get("/collection/{slug}", response_class=HTMLResponse)
async def collection_page(slug: str, request: Request, db: Session = Depends(get_db)):
    if slug not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Collection not found")
    col = dict(COLLECTIONS[slug])

    digital = db.query(DigitalProduct).filter(
        DigitalProduct.collection == slug, DigitalProduct.active == True
    ).all()
    physical = db.query(Product).filter(
        Product.collection == slug, Product.active == True
    ).order_by(Product.id).all()

    # A collection with no published products is a dead page — 404 it so it
    # drops out of the index (avoids thin/empty pages after a line is retired).
    if not digital and not physical:
        raise HTTPException(status_code=404, detail="Collection not found")

    items = [
        {
            "slug": p.slug, "name": p.name, "price_usd": p.price_usd,
            "type_label": digital_type_label(p) if slug == "digital-downloads" else p.product_type.replace("_", " ").title(),
            "price_prefix": "Bundle",
            "url": f"/bundle/{p.slug}",
            "kind": "digital",
            "delivery": "Instant download",
            "group": digital_group(p) if slug == "digital-downloads" else "Digital Downloads",
            "card_format": None,
        }
        for p in digital
    ]
    for p in physical:
        if p.collection == "apparel":
            garment = json.loads(p.params_json or "{}").get("garment", "tshirt")
            type_label = {"hoodie": "Hoodie", "aop_leggings": "Leggings",
                          "aop_joggers": "Joggers", "aop_sweatshirt": "Sweatshirt"}.get(garment, "T-Shirt")
            group = "Apparel"
            card_format = {"hoodie": "unisex_hoodie", "aop_leggings": "aop_leggings",
                           "aop_joggers": "aop_joggers", "aop_sweatshirt": "aop_sweatshirt"}.get(garment, "unisex_tshirt")
        else:
            type_label, group = _PHYSICAL_LABELS.get(p.collection, ("Art Print", "Art Prints"))
            card_format = None
        items.append({
            "slug": p.slug, "name": p.name, "price_usd": p.price_usd,
            "type_label": type_label,
            "price_prefix": "From",
            "url": f"/product/{p.slug}",
            "collection": p.collection,
            "kind": "physical",
            "delivery": "Ships to you",
            "group": group,
            "card_format": card_format,
        })

    # Group products by kind so visitors can tell digital downloads from physical
    # prints at a glance, in a stable display order.
    # Digital sections most-wanted-first (shared constant), then physical.
    section_order = DIGITAL_SECTION_ORDER + [
        "Art Prints", "Apparel", "Desk Mats", "Notebooks"
    ]
    groups = [
        {"title": name, "cards": [it for it in items if it["group"] == name]}
        for name in section_order
    ]
    groups = [g for g in groups if g["cards"]]

    return templates.TemplateResponse(
        "collection.html",
        {"request": request, "collection": col, "slug": slug,
         "products": items, "groups": groups},
    )


def _collection_active_count(db, slug: str) -> int:
    """How many published products a collection currently has (physical + digital)."""
    return (
        db.query(Product).filter(Product.collection == slug, Product.active == True).count()
        + db.query(DigitalProduct).filter(DigitalProduct.collection == slug, DigitalProduct.active == True).count()
    )


def _retired_redirect(db, slug: str):
    """If `slug` is a RETIRED (inactive) product, return a 301 to its collection
    — preserves SEO link-equity, avoids a 404 in GSC, and (since it doesn't
    render the page) prevents phantom product_view/add_to_cart in /admin/live.
    Only redirects to a collection that still has published products; otherwise
    returns None so the caller 404s (avoids redirecting to an empty page)."""
    from fastapi.responses import RedirectResponse
    for Model in (Product, DigitalProduct):
        row = db.query(Model).filter(Model.slug == slug).first()
        if (row and not row.active and row.collection in COLLECTIONS
                and _collection_active_count(db, row.collection) > 0):
            return RedirectResponse(url=f"/collection/{row.collection}", status_code=301)
    return None


@app.get("/bundle/{slug}", response_class=HTMLResponse)
async def bundle_page(slug: str, request: Request, db: Session = Depends(get_db)):
    product = db.query(DigitalProduct).filter(
        DigitalProduct.slug == slug, DigitalProduct.active == True
    ).first()
    if not product:
        red = _retired_redirect(db, slug)
        if red:
            return red
        raise HTTPException(status_code=404, detail="Bundle not found")
    product_dict = {
        "id": product.id,
        "slug": product.slug,
        "name": product.name,
        "product_type": product.product_type,
        "collection": product.collection,
        "equation_type": product.equation_type,
        "description": product.description,
        "price_usd": product.price_usd,
        "contents_json": product.contents_json,
        "cover_image": product.cover_image,
        "thumbnail_url": product.thumbnail_url,
        "file_size": product.file_size,
        "license_type": product.license_type,
        "active": product.active,
    }
    contents = json.loads(product.contents_json or "[]")
    col = COLLECTIONS.get(product.collection, {})
    related_raw = db.query(DigitalProduct).filter(
        DigitalProduct.collection == product.collection,
        DigitalProduct.slug != product.slug,
        DigitalProduct.active == True,
    ).all()
    related = [{"slug": r.slug, "name": r.name, "description": r.description,
                "price_usd": r.price_usd, "product_type": r.product_type} for r in related_raw]

    # Uploaded digital products (PDFs, iPad bundles, notebooks, loops) use a
    # dedicated detail template — the math-art bundle page doesn't fit them.
    if product.collection == "digital-downloads":
        gal_dir = f"/var/www/mathrelaxing.store/static/digital/{product.slug}"
        gallery = []
        if os.path.isdir(gal_dir):
            files = sorted(os.listdir(gal_dir))
            prio = [f for f in files if "hero" in f or "cover" in f]
            gallery = [f"/static/digital/{product.slug}/{f}"
                       for f in prio + [f for f in files if f not in prio]]
        return templates.TemplateResponse(
            "bundle_download.html",
            {
                "request": request,
                "product": product_dict,
                "contents": contents,
                "gallery": gallery,
                "related": related,
            },
        )

    return templates.TemplateResponse(
        "bundle.html",
        {
            "request": request,
            "product": product_dict,
            "contents": contents,
            "collection": dict(col) if isinstance(col, dict) else col,
            "collections": {k: dict(v) if isinstance(v, dict) else v for k, v in COLLECTIONS.items()},
            "related": related,
            "collection_math": COLLECTION_MATH.get(product.collection, ""),
        },
    )


@app.get("/product/{slug}", response_class=HTMLResponse)
async def product_page(slug: str, request: Request, db: Session = Depends(get_db)):
    digital = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if digital:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/bundle/{slug}")

    product = db.query(Product).filter(Product.slug == slug, Product.active == True).first()
    if not product:
        red = _retired_redirect(db, slug)
        if red:
            return red
        raise HTTPException(status_code=404, detail="Product not found")

    # The physical coloring books have their own dedicated landing pages.
    if product.slug in BOOK_TEMPLATES:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/book/{product.slug}")

    from services.printful import formats_for_collection, format_for_garment, MOCKUP_VERSION
    params = json.loads(product.params_json or "{}")
    col = COLLECTIONS.get(product.collection, {})
    if product.collection == "apparel":
        # Each apparel product is a specific garment (t-shirt or hoodie).
        formats = [format_for_garment(params.get("garment", "tshirt"))]
    else:
        formats = formats_for_collection(product.collection)
    excluded = sorted({
        country
        for fmt in formats
        for country in fmt.get("excluded_countries", [])
    })
    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "product": product,
            "params": params,
            "formats": formats,
            "collection": dict(col) if isinstance(col, dict) else col,
            "excluded_countries": excluded,
            "product_math": PRODUCT_MATH.get(product.equation_type, ""),
            "collection_math": COLLECTION_MATH.get(product.collection, ""),
            "mockup_v": MOCKUP_VERSION,
        },
    )


# Maps each coloring-book product slug to its dedicated landing template.
BOOK_TEMPLATES = {
    "mathematical-tangle-art-coloring-book": "book_tangle.html",
    "sacred-harmonics-coloring-book": "book_sacred_harmonics.html",
    "hyperbolic-gardens-coloring-book": "book_hyperbolic.html",
    "harmonograph-dreams-coloring-book": "book_harmonographs.html",
    "fractal-flora-coloring-book": "book_fractal.html",
}


@app.get("/book", response_class=HTMLResponse)
async def book_page(request: Request):
    # Legacy single-book URL — keep it working by sending it to the first book.
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/book/mathematical-tangle-art-coloring-book")


@app.get("/book/{slug}", response_class=HTMLResponse)
async def book_page_slug(slug: str, request: Request, db: Session = Depends(get_db)):
    template = BOOK_TEMPLATES.get(slug)
    if not template:
        raise HTTPException(status_code=404, detail="Book not found")
    # Only serve landing pages for products still published. Otherwise a retired
    # book keeps rendering (and firing product_view/add_to_cart), showing up as
    # phantom traffic in /admin/live.
    prod = db.query(Product).filter(Product.slug == slug, Product.active == True).first()
    if not prod:
        red = _retired_redirect(db, slug)
        if red:
            return red
        raise HTTPException(status_code=404, detail="Book not found")
    return templates.TemplateResponse(template, {"request": request})


@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    return templates.TemplateResponse("cart.html", {"request": request})


@app.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request):
    return templates.TemplateResponse("checkout.html", {"request": request})


@app.get("/checkout/return", response_class=HTMLResponse)
async def checkout_return_page(request: Request):
    return templates.TemplateResponse("checkout_return.html", {"request": request})


@app.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success_page(request: Request):
    return templates.TemplateResponse("checkout_success.html", {"request": request})


@app.get("/download/{token}", response_class=HTMLResponse)
async def download_page(token: str, request: Request, db: Session = Depends(get_db)):
    purchase = db.query(Purchase).filter(Purchase.download_token == token).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Download link not found")
    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    return templates.TemplateResponse(
        "download.html",
        {
            "request": request,
            "purchase": purchase,
            "product": product,
            "token": token,
        },
    )


@app.get("/gpt-landing", response_class=HTMLResponse)
async def gpt_landing_page(request: Request, db: Session = Depends(get_db)):
    product_slug = request.query_params.get("product", "")
    product = None
    if product_slug:
        product = db.query(DigitalProduct).filter(DigitalProduct.slug == product_slug).first()
    featured = db.query(DigitalProduct).filter(DigitalProduct.active == True).limit(4).all()
    return templates.TemplateResponse(
        "gpt_landing.html",
        {
            "request": request,
            "product": product,
            "featured": featured,
            "ref": request.query_params.get("ref", "gpt"),
        },
    )


@app.get("/my-downloads", response_class=HTMLResponse)
async def my_downloads_page(request: Request):
    return templates.TemplateResponse("my_downloads.html", {"request": request})


@app.get("/lowpoly", response_class=HTMLResponse)
async def lowpoly_page(request: Request):
    return templates.TemplateResponse("lowpoly.html", {"request": request})


@app.get("/lowpoly/access", response_class=HTMLResponse)
async def lowpoly_access_page(request: Request):
    return templates.TemplateResponse("lowpoly_access.html", {"request": request})


@app.get("/experiences/{experience_id}", response_class=HTMLResponse)
async def whop_experience_page(request: Request, experience_id: str):
    """Entry point when a user opens the Low Poly experience inside Whop."""
    resp = templates.TemplateResponse("lowpoly_access.html", {"request": request})
    resp.headers["X-Frame-Options"] = "ALLOW-FROM https://whop.com"
    resp.headers["Content-Security-Policy"] = "frame-ancestors https://*.whop.com https://whop.com"
    return resp


@app.post("/lowpoly/access")
async def lowpoly_access_resend(email_addr: str = Form(...), db=Depends(get_db)):
    from models.product import LowPolyCredit
    from services import email as email_svc
    credits = (
        db.query(LowPolyCredit)
        .filter(LowPolyCredit.customer_email == email_addr.strip().lower())
        .filter(LowPolyCredit.status != "exhausted")
        .order_by(LowPolyCredit.created_at.desc())
        .all()
    )
    if credits:
        for credit in credits:
            await email_svc.send_lowpoly_credit_email(credit)
    # Always return success to avoid email enumeration
    from fastapi.responses import JSONResponse
    return JSONResponse({"status": "ok"})


@app.get("/lowpoly/credit/{token}", response_class=HTMLResponse)
async def lowpoly_credit_page_root(token: str, db=Depends(get_db)):
    from routers.lowpoly import lowpoly_credit_page
    return lowpoly_credit_page(token, db)


@app.post("/lowpoly/credit/{token}/generate")
async def lowpoly_credit_generate_root(
    token: str,
    image: UploadFile = File(...),
    email_addr: str = Form(...),
    colors: int = Form(16),
    grid: str = Form("square"),
    orientation: str = Form("portrait"),
    db=Depends(get_db),
):
    from routers.lowpoly import lowpoly_credit_generate
    return await lowpoly_credit_generate(token, image, email_addr, colors, grid, orientation, db)


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


@app.api_route("/privacy", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.api_route("/terms", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/terms-of-service", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


TIKTOK_VERIFICATION_FILES = {
    "tiktokYwy3u4HtNA5WRNCLuBPETMf8qmSiMk0Q.txt",
    "tiktokYkG8Vm71yq3JtY7PRTPksnwRJgeH3Xt6.txt",
}


@app.api_route("/tiktokYwy3u4HtNA5WRNCLuBPETMf8qmSiMk0Q.txt", methods=["GET", "HEAD"])
@app.api_route("/tiktokYkG8Vm71yq3JtY7PRTPksnwRJgeH3Xt6.txt", methods=["GET", "HEAD"])
async def tiktok_site_verification(request: Request):
    verification_file = request.url.path.rsplit("/", 1)[-1]
    if verification_file not in TIKTOK_VERIFICATION_FILES:
        raise HTTPException(status_code=404, detail="Verification file not found")
    verification_path = os.path.join(BASE_DIR, verification_file)
    with open(verification_path, "r", encoding="utf-8") as file:
        return Response(content=file.read(), media_type="text/plain")


# Published long-form articles. slug → (title, category, hero_product, collection)
BLOG_ARTICLES = {
    "what-is-radial-symmetry-in-art": ("What Is Radial Symmetry in Art?", "Mathematics", "superformula-velvet-star", "radial-symmetry"),
    "chladni-figures-geometry-of-sound": ("Chladni Figures: The Patterns Sound Leaves Behind", "Physics", "chladni-mandala", "chladni-figures"),
    "voronoi-patterns-in-nature": ("Voronoi Patterns in Nature", "Mathematics", "voronoi-bubbles", "voronoi-organics"),
}


@app.get("/blog", response_class=HTMLResponse)
async def blog_page(request: Request):
    return templates.TemplateResponse(
        "blog/index.html",
        {"request": request, "articles": BLOG_ARTICLES},
    )


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_article(slug: str, request: Request):
    if slug not in BLOG_ARTICLES:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse(f"blog/{slug}.html", {"request": request})


@app.get("/certificate/{order_id}", response_class=HTMLResponse)
async def certificate_page(order_id: int, request: Request, db: Session = Depends(get_db)):
    cert = db.query(Certificate).filter(Certificate.order_id == order_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    order = db.query(Order).filter(Order.id == order_id).first()
    product = db.query(Product).filter(Product.id == order.product_id).first() if order else None
    params = json.loads(cert.params_json)

    col = COLLECTIONS.get(product.collection, {}) if product else {}
    raw_eq = col.get("equation", "")
    equation_lines = [l.strip() for l in raw_eq.split(",  ")] if raw_eq else []

    return templates.TemplateResponse(
        "certificate.html",
        {
            "request": request,
            "cert": cert,
            "order": order,
            "product": product,
            "params": params,
            "collection": col,
            "equation_lines": equation_lines,
        },
    )


@app.get("/robots.txt")
async def robots_txt():
    # Allow crawling of content + product images (/api/render is used for
    # og:image), block private/transactional and noise paths, point to sitemap.
    body = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /download/\n"
        "Disallow: /checkout\n"
        "Disallow: /cart\n"
        "Disallow: /my-downloads\n"
        "Disallow: /api/purchases/\n"
        "Disallow: /api/track\n"
        "Allow: /\n"
        "\n"
        "Sitemap: https://mathrelaxing.store/sitemap.xml\n"
    )
    return Response(content=body, media_type="text/plain")


@app.get("/sitemap.xml")
async def sitemap(db: Session = Depends(get_db)):
    base = "https://mathrelaxing.store"
    today = date.today().isoformat()

    def url(loc, changefreq="monthly", priority="0.5", lastmod=None):
        # Always emit <lastmod> (defaults to today) — every URL having a fresh
        # lastmod helps search engines schedule crawls of a new, unindexed site.
        lm = f"\n    <lastmod>{lastmod or today}</lastmod>"
        return (
            f"  <url>\n"
            f"    <loc>{loc}</loc>{lm}\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>\n"
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += url(base,                    changefreq="weekly",  priority="1.0")
    xml += url(f"{base}/collections",  changefreq="weekly",  priority="0.9")
    xml += url(f"{base}/about",        changefreq="monthly", priority="0.4")
    xml += url(f"{base}/blog",         changefreq="weekly",  priority="0.6")
    xml += url(f"{base}/lowpoly",      changefreq="weekly",  priority="0.8")
    for slug in BLOG_ARTICLES:
        xml += url(f"{base}/blog/{slug}", changefreq="monthly", priority="0.7")
    for slug in COLLECTIONS:
        if _collection_active_count(db, slug) > 0:  # skip empty (retired) collections
            xml += url(f"{base}/collection/{slug}", changefreq="weekly", priority="0.8")
    for p in db.query(DigitalProduct).filter(DigitalProduct.active == True).all():
        lm = p.created_at.date().isoformat() if hasattr(p, "created_at") and p.created_at else today
        xml += url(f"{base}/bundle/{p.slug}", changefreq="monthly", priority="0.9", lastmod=lm)
    for p in db.query(Product).filter(Product.active == True).all():
        # Coloring books with a dedicated landing page redirect /product → /book,
        # so emit the canonical /book URL to avoid "Page with redirect" in GSC.
        if p.slug in BOOK_TEMPLATES:
            xml += url(f"{base}/book/{p.slug}", changefreq="monthly", priority="0.9")
        else:
            xml += url(f"{base}/product/{p.slug}", changefreq="monthly", priority="0.8")
    xml += "</urlset>"
    return Response(content=xml, media_type="application/xml")
