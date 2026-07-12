import asyncio
import hashlib
import json
import os

# Per-product locks so a gallery's simultaneous thumbnail requests build the
# Printful view list only once (avoids a burst of duplicate tasks → rate limits).
_tshirt_locks: dict = {}

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from services.printful import FORMATS, MOCKUP_VERSION
from services.renderer import render_equation, TransparentRender
from services import pinterest_renderer

router = APIRouter()

RENDER_CACHE_DIR  = "/tmp/mathrelaxing_renders"
PRINT_CACHE_DIR   = "/tmp/mathrelaxing_print"
PREVIEW_CACHE_DIR = "/tmp/mathrelaxing_preview"
MOCKUP_CACHE_DIR  = "/var/www/mathrelaxing.store/mockup_cache"
STATIC_PREVIEW_DIR = "/var/www/mathrelaxing.store/static/previews"
os.makedirs(RENDER_CACHE_DIR, exist_ok=True)
os.makedirs(PRINT_CACHE_DIR, exist_ok=True)
os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
os.makedirs(MOCKUP_CACHE_DIR, exist_ok=True)
os.makedirs(STATIC_PREVIEW_DIR, exist_ok=True)

# Aspect ratios per equation type: "portrait" (4:5), "landscape" (5:4), "square" (1:1)
_ASPECT_MAP = {
    "lorenz": "portrait", "clifford": "portrait", "aizawa": "portrait",
    "julia": "portrait", "mandelbrot": "portrait", "rose": "portrait",
    "joukowski": "portrait", "mobius-grid": "portrait",
    "kleinian-inversion": "portrait",
    "de_jong": "portrait",
    "superformula": "square", "chladni": "square", "turing": "square",
    "gray-scott": "square", "voronoi": "square",
    "flow-field": "portrait",
    "fractal-flame": "portrait",
}
_BASE_PX = 1280  # base dimension for the shorter side

# Formats that use the flat poster compositor (art on white bg) instead of PSDs
_FLAT_POSTER_FORMATS = {"poster"}

def _preview_dims(eq_type: str) -> tuple:
    """Return (width, height) for a given equation type."""
    ratio = _ASPECT_MAP.get(eq_type, "portrait")
    if ratio == "landscape":
        return _BASE_PX * 5 // 4, _BASE_PX   # 1600×1280
    elif ratio == "square":
        return _BASE_PX, _BASE_PX              # 1280×1280
    else:
        return _BASE_PX, _BASE_PX * 5 // 4    # 1280×1600

# Color palettes for item variations
_ITEM_PALETTES = [
    ("#c8a96e", "#7ecfb3"),  # amber → teal
    ("#e85d75", "#6ec8cf"),  # rose → sky
    ("#a855f7", "#38bdf8"),  # violet → blue
    ("#f59e0b", "#ef4444"),  # amber → red
    ("#10b981", "#8b5cf6"),  # emerald → violet
    ("#ec4899", "#f97316"),  # pink → orange
    ("#06b6d4", "#a855f7"),  # cyan → violet
    ("#84cc16", "#0ea5e9"),  # lime → sky
    ("#f43f5e", "#c084fc"),  # rose → purple
    ("#14b8a6", "#f59e0b"),  # teal → amber
    ("#e879f9", "#34d399"),  # fuchsia → emerald
    ("#fb923c", "#4f46e5"),  # orange → indigo
    ("#22d3ee", "#fb7185"),  # cyan → rose
    ("#a3e635", "#7c3aed"),  # lime → violet
    ("#f472b6", "#2dd4bf"),  # pink → teal
    ("#fbbf24", "#6366f1"),  # yellow → indigo
    ("#34d399", "#e11d48"),  # emerald → rose
    ("#818cf8", "#facc15"),  # indigo → yellow
    ("#c084fc", "#22c55e"),  # purple → green
    ("#fb7185", "#0284c7"),  # rose → blue
]


def _vary_params(base_params: dict, index: int, eq_type: str = "") -> tuple:
    """Return (varied_params, eq_type_override). Override is '' if no change."""
    import copy
    params = copy.deepcopy(base_params)

    # Rotate color palette
    cs, ce = _ITEM_PALETTES[index % len(_ITEM_PALETTES)]
    if "color_start" in params:
        params["color_start"]["value"] = cs
    else:
        params["color_start"] = {"value": cs}
    if "color_end" in params:
        params["color_end"]["value"] = ce
    else:
        params["color_end"] = {"value": ce}

    # For Chladni, force distinct mode pairs per item so each has a unique shape
    if eq_type == "chladni":
        chladni_modes = [(4, 4), (7, 2), (5, 7), (3, 6), (9, 8),
                         (6, 3), (8, 5), (2, 9), (10, 4), (11, 7),
                         (3, 9), (7, 11), (5, 2), (8, 10), (6, 8)]
        m, n = chladni_modes[index % len(chladni_modes)]
        if "mode_m" in params:
            params["mode_m"]["value"] = m
        else:
            params["mode_m"] = {"value": m}
        if "mode_n" in params:
            params["mode_n"]["value"] = n
        else:
            params["mode_n"] = {"value": n}
        return params, ""

    # For Julia fractals, force distinct c values per item for unique shapes
    if eq_type == "julia":
        julia_c_values = [
            (-0.7, 0.27015),   # Classic spiral
            (0.285, 0.01),     # Ice crystal
            (-0.835, -0.2321), # Dragon
            (-0.8, 0.156),     # Dendrite
            (-0.4, 0.6),       # Rabbit
            (0.355, 0.355),    # Siegel disk
            (-0.54, 0.54),     # Galaxy spiral
            (-0.1, 0.651),     # Starfish
            (-1.25, 0.0),      # Basilica
            (-0.12, -0.77),    # Nebula
            (0.28, 0.008),     # Frost
            (-0.75, 0.11),     # Mandala
            (-0.62, 0.42),     # Coral
        ]
        c_re, c_im = julia_c_values[index % len(julia_c_values)]
        if "c_re" in params:
            params["c_re"]["value"] = c_re
        else:
            params["c_re"] = {"value": c_re}
        if "c_im" in params:
            params["c_im"]["value"] = c_im
        else:
            params["c_im"] = {"value": c_im}
        params["zoom"] = {"value": 1.0}
        params["cx"] = {"value": 0.0}
        params["cy"] = {"value": 0.0}
        return params, ""

    # For Superformula (Radial Symmetry), force distinct shape parameters per item
    if eq_type == "superformula":
        superformula_presets = [
            {"m": 8.0,  "n1": 0.28, "n2": 1.95, "n3": 1.85, "turns": 14.0, "wave_freq": 6.5},   # Bloom
            {"m": 5.0,  "n1": 0.30, "n2": 1.70, "n3": 1.70, "turns": 10.0, "wave_freq": 4.0},   # Rose 5
            {"m": 12.0, "n1": 0.50, "n2": 0.80, "n3": 2.50, "turns": 18.0, "wave_freq": 9.0},   # Star
            {"m": 7.0,  "n1": 0.25, "n2": 1.90, "n3": 1.60, "turns": 12.0, "wave_freq": 5.5},   # Rose 7
            {"m": 6.0,  "n1": 0.15, "n2": 2.50, "n3": 2.20, "turns": 16.0, "wave_freq": 7.0},   # Shell
            {"m": 3.0,  "n1": 0.35, "n2": 1.50, "n3": 1.50, "turns": 8.0,  "wave_freq": 3.0},   # Rose 3
            {"m": 20.0, "n1": 0.60, "n2": 0.70, "n3": 2.80, "turns": 22.0, "wave_freq": 12.0},  # Gear
            {"m": 9.0,  "n1": 0.20, "n2": 2.10, "n3": 1.40, "turns": 15.0, "wave_freq": 7.5},   # Mandala
            {"m": 4.0,  "n1": 0.80, "n2": 1.00, "n3": 1.00, "turns": 10.0, "wave_freq": 4.5},   # Crystal
            {"m": 8.0,  "n1": 0.22, "n2": 1.80, "n3": 2.00, "turns": 20.0, "wave_freq": 8.0},   # Rose 8
            {"m": 15.0, "n1": 0.40, "n2": 1.20, "n3": 2.00, "turns": 20.0, "wave_freq": 10.0},  # Orbit
            {"m": 6.0,  "n1": 0.18, "n2": 2.30, "n3": 1.30, "turns": 24.0, "wave_freq": 6.0},   # Spiral
        ]
        preset = superformula_presets[index % len(superformula_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""

    # For De Jong Attractors, force distinct parameter sets for dense complex patterns
    if eq_type == "de_jong":
        dejong_presets = [
            {"a": -2.0, "b": -2.0, "c": -1.2, "d": 2.0},    # De Jong Lattice
            {"a": 1.4,  "b": -2.3, "c": 2.4,  "d": -2.1},   # De Jong Weave
            {"a": -1.5, "b": -2.3, "c": 1.6,  "d": -1.9},   # De Jong Tapestry
            {"a": -1.9, "b": -2.1, "c": 1.7,  "d": -1.8},   # De Jong Nebula
            {"a": -2.0, "b": -2.0, "c": 2.0,  "d": -2.0},   # De Jong Crystal
            {"a": 2.0,  "b": 2.0,  "c": -2.0, "d": 2.0},    # De Jong Prism
            {"a": 1.7,  "b": -1.9, "c": -2.0, "d": -1.3},   # De Jong Vortex
            {"a": 1.0,  "b": -2.0, "c": -1.0, "d": 2.0},    # De Jong Fractal
            {"a": -1.6, "b": 2.0,  "c": -1.8, "d": -1.4},   # De Jong Loom
            {"a": -2.0, "b": 1.5,  "c": 1.5,  "d": -2.0},   # De Jong Cascade
            {"a": 1.3,  "b": -2.0, "c": -2.0, "d": 1.3},    # De Jong Bloom
            {"a": -1.7, "b": -2.3, "c": 1.8,  "d": -1.6},   # De Jong Storm
            {"a": 2.0,  "b": -1.5, "c": 1.5,  "d": -2.0},   # De Jong Flame
            {"a": -1.4, "b": 2.0,  "c": -1.6, "d": 1.8},    # De Jong Mandala
        ]
        preset = dejong_presets[index % len(dejong_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""

    # For Strange Attractors, cycle through Lorenz/Clifford/Aizawa with distinct params
    if eq_type == "lorenz":
        attractor_presets = [
            ("lorenz",   {"sigma": 10.0, "rho": 28.0,  "beta": 2.667}),
            ("lorenz",   {"sigma": 14.0, "rho": 28.0,  "beta": 2.667}),
            ("clifford", {"a": -1.4,  "b": 1.6,   "c": 1.0,  "d": 0.7}),
            ("clifford", {"a": -1.7,  "b": 1.8,   "c": -0.9, "d": 0.4}),
            ("aizawa",   {"a": 0.95,  "b": 0.7,   "c": 0.6,  "d": 3.5, "e": 0.25, "f": 0.1}),
            ("aizawa",   {"a": 0.7,   "b": 0.8,   "c": 0.5,  "d": 3.0, "e": 0.35, "f": 0.15}),
            ("lorenz",   {"sigma": 10.0, "rho": 24.0,  "beta": 1.5}),
            ("clifford", {"a": 1.1,   "b": -1.3,  "c": 1.0,  "d": 1.7}),
            ("lorenz",   {"sigma": 12.0, "rho": 34.0,  "beta": 2.8}),
            ("aizawa",   {"a": 1.1,   "b": 0.5,   "c": 0.8,  "d": 4.0, "e": 0.2,  "f": 0.05}),
            ("clifford", {"a": -1.8,  "b": -1.9,  "c": -1.0, "d": -0.9}),
            ("lorenz",   {"sigma": 10.0, "rho": 30.0,  "beta": 2.0}),
            ("aizawa",   {"a": 0.8,   "b": 0.9,   "c": 0.4,  "d": 2.5, "e": 0.3,  "f": 0.2}),
            ("clifford", {"a": 1.7,   "b": 1.8,   "c": -0.5, "d": -1.0}),
            ("lorenz",   {"sigma": 8.0,  "rho": 26.0,  "beta": 3.0}),
            ("aizawa",   {"a": 0.95,  "b": 0.7,   "c": 0.6,  "d": 3.5, "e": 0.25, "f": 0.1}),
            ("clifford", {"a": 1.2,   "b": 1.1,   "c": -1.0, "d": -1.6}),
            ("lorenz",   {"sigma": 10.0, "rho": 22.0,  "beta": 2.5}),
            ("aizawa",   {"a": 0.6,   "b": 1.0,   "c": 0.3,  "d": 2.0, "e": 0.4,  "f": 0.25}),
            ("clifford", {"a": 1.3,   "b": -1.1,  "c": 0.8,  "d": 1.4}),
        ]
        override_type, preset = attractor_presets[index % len(attractor_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, override_type

    # For Gray-Scott (Reaction Diffusion), force distinct pattern types and spatial variation
    if eq_type == "gray-scott":
        rd_presets = [
            {"pattern_type": "coral",       "f": 0.055, "k": 0.062, "f_var": 0.003, "k_var": 0.002, "var_freq": 3.0},
            {"pattern_type": "fingerprint",  "f": 0.025, "k": 0.055, "f_var": 0.002, "k_var": 0.001, "var_freq": 5.0},
            {"pattern_type": "coral",       "f": 0.014, "k": 0.045, "f_var": 0.004, "k_var": 0.003, "var_freq": 2.0},
            {"pattern_type": "labyrinth",   "f": 0.029, "k": 0.057, "f_var": 0.002, "k_var": 0.001, "var_freq": 4.0},
            {"pattern_type": "mitosis",     "f": 0.036, "k": 0.065, "f_var": 0.001, "k_var": 0.001, "var_freq": 6.0},
            {"pattern_type": "spots",       "f": 0.035, "k": 0.065, "f_var": 0.002, "k_var": 0.002, "var_freq": 3.0},
            {"pattern_type": "worms",       "f": 0.04,  "k": 0.06,  "f_var": 0.003, "k_var": 0.002, "var_freq": 2.5},
            {"pattern_type": "stripes",     "f": 0.025, "k": 0.05,  "f_var": 0.002, "k_var": 0.001, "var_freq": 4.0},
            {"pattern_type": "coral",       "f": 0.048, "k": 0.06,  "f_var": 0.005, "k_var": 0.004, "var_freq": 2.0},
            {"pattern_type": "labyrinth",   "f": 0.026, "k": 0.051, "f_var": 0.003, "k_var": 0.002, "var_freq": 3.5},
            {"pattern_type": "fingerprint", "f": 0.02,  "k": 0.05,  "f_var": 0.003, "k_var": 0.002, "var_freq": 6.0},
            {"pattern_type": "waves",       "f": 0.014, "k": 0.054, "f_var": 0.004, "k_var": 0.003, "var_freq": 2.0},
            {"pattern_type": "coral",       "f": 0.062, "k": 0.063, "f_var": 0.003, "k_var": 0.002, "var_freq": 4.0},
        ]
        preset = rd_presets[index % len(rd_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""

    # For Turing Patterns, force distinct pattern types with closer, detailed patterns
    if eq_type == "turing":
        turing_presets = [
            {"pattern_type": "spots",     "scale": 2.0},
            {"pattern_type": "stripes",   "scale": 1.5},
            {"pattern_type": "labyrinth", "scale": 1.5},
            {"pattern_type": "spots",     "scale": 1.0},
            {"pattern_type": "stripes",   "scale": 1.0},
            {"pattern_type": "labyrinth", "scale": 1.0},
        ]
        preset = turing_presets[index % len(turing_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""

    # For Flow Fields, assign a completely different field+style per item index
    if eq_type == "flow-field":
        ff_presets = [
            {"field_type": "noise",    "style": "lines",   "seed": 42,   "frequency": 1.5, "octaves": 3, "curl": 0.0, "num_particles": 1600, "steps": 700, "step_size": 0.004, "line_width": 0.6, "alpha": 0.6},
            {"field_type": "noise",    "style": "lines",   "seed": 137,  "frequency": 1.8, "octaves": 3, "curl": 0.3, "num_particles": 1600, "steps": 700, "step_size": 0.004, "line_width": 0.6, "alpha": 0.6},
            {"field_type": "noise",    "style": "density", "seed": 7,    "frequency": 0.8, "octaves": 2, "curl": 0.0, "num_particles": 2000, "steps": 900, "step_size": 0.004},
            {"field_type": "noise",    "style": "density", "seed": 333,  "frequency": 1.0, "octaves": 3, "curl": 0.0, "num_particles": 2000, "steps": 800, "step_size": 0.004},
            {"field_type": "cellular", "style": "density", "seed": 13,   "frequency": 2.2, "num_particles": 2000, "steps": 800, "step_size": 0.004},
            {"field_type": "cellular", "style": "density", "seed": 77,   "frequency": 1.6, "num_particles": 2000, "steps": 900, "step_size": 0.004},
            {"field_type": "vortex",   "style": "lines",   "seed": 88,   "n_poles": 6,     "num_particles": 1800, "steps": 700, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "vortex",   "style": "lines",   "seed": 22,   "n_poles": 4,     "num_particles": 1600, "steps": 700, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "vortex",   "style": "density", "seed": 22,   "n_poles": 3,     "num_particles": 2000, "steps": 900, "step_size": 0.004},
            {"field_type": "vortex",   "style": "density", "seed": 256,  "n_poles": 5,     "num_particles": 2000, "steps": 800, "step_size": 0.004},
            {"field_type": "sources",  "style": "lines",   "seed": 333,  "n_poles": 7,     "num_particles": 1800, "steps": 600, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "sources",  "style": "lines",   "seed": 99,   "n_poles": 5,     "num_particles": 1800, "steps": 600, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "noise",    "style": "brush",   "seed": 137,  "frequency": 0.55,"octaves": 2, "curl": 0.0, "num_particles": 1200, "steps": 900, "step_size": 0.005, "line_width": 0.9, "alpha": 0.7},
            {"field_type": "noise",    "style": "brush",   "seed": 512,  "frequency": 0.7, "octaves": 2, "curl": 0.0, "num_particles": 1200, "steps": 800, "step_size": 0.005, "line_width": 0.9, "alpha": 0.7},
            {"field_type": "cellular", "style": "lines",   "seed": 77,   "frequency": 1.4, "num_particles": 1600, "steps": 700, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "cellular", "style": "lines",   "seed": 31,   "frequency": 2.0, "num_particles": 1600, "steps": 600, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "noise",    "style": "lines",   "seed": 1024, "frequency": 2.5, "octaves": 4, "curl": 0.5, "num_particles": 1600, "steps": 700, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "noise",    "style": "density", "seed": 2048, "frequency": 1.2, "octaves": 3, "curl": 0.4, "num_particles": 2000, "steps": 800, "step_size": 0.004},
            {"field_type": "vortex",   "style": "lines",   "seed": 777,  "n_poles": 8,     "num_particles": 1800, "steps": 700, "step_size": 0.004, "line_width": 0.5, "alpha": 0.55},
            {"field_type": "sources",  "style": "density", "seed": 11,   "n_poles": 6,     "num_particles": 2000, "steps": 700, "step_size": 0.004},
        ]
        preset = ff_presets[index % len(ff_presets)]
        for key, val in preset.items():
            params[key] = {"value": val}
        return params, ""

    # For Voronoi Organics, force distinct cell counts, shapes, and visual effects
    if eq_type == "voronoi":
        voronoi_presets = [
            {"n_cells": 40,  "organic": 0.9,  "irregularity": 0.2, "glow_strength": 0.7, "cell_color_var": 0.4},
            {"n_cells": 150, "organic": 0.1,  "irregularity": 0.8, "glow_strength": 0.3, "cell_color_var": 0.1},
            {"n_cells": 70,  "organic": 0.6,  "irregularity": 0.4, "glow_strength": 0.5, "cell_color_var": 0.3},
            {"n_cells": 200, "organic": 0.3,  "irregularity": 0.3, "glow_strength": 0.8, "cell_color_var": 0.5},
            {"n_cells": 30,  "organic": 0.5,  "irregularity": 0.1, "glow_strength": 0.6, "cell_color_var": 0.2},
        ]
        preset = voronoi_presets[index % len(voronoi_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""
    


    if eq_type == "fractal-flame":
        ff_presets = [
            {"variation":"sinusoidal","var2":"linear",   "v_mix":0.0,"seed":42,   "n_funcs":4,"symmetry":1,"color_start":"#C8A96E","color_end":"#4EC9B0","brightness":1.2},
            {"variation":"swirl",    "var2":"linear",   "v_mix":0.0,"seed":137,  "n_funcs":3,"symmetry":3,"color_start":"#F472B6","color_end":"#FBBF24","brightness":1.0},
            {"variation":"spherical","var2":"linear",   "v_mix":0.0,"seed":7,    "n_funcs":4,"symmetry":1,"color_start":"#7C3AED","color_end":"#2563EB","brightness":1.3},
            {"variation":"julia",    "var2":"linear",   "v_mix":0.0,"seed":333,  "n_funcs":3,"symmetry":6,"color_start":"#A5F3FC","color_end":"#F0ABFC","brightness":1.1},
            {"variation":"swirl",    "var2":"sinusoidal","v_mix":0.4,"seed":88,   "n_funcs":5,"symmetry":1,"color_start":"#14B8A6","color_end":"#6366F1","brightness":1.0},
            {"variation":"sinusoidal","var2":"spherical","v_mix":0.3,"seed":2024, "n_funcs":4,"symmetry":4,"color_start":"#FB923C","color_end":"#F9A8D4","brightness":1.2},
            {"variation":"horseshoe","var2":"linear",   "v_mix":0.0,"seed":666,  "n_funcs":4,"symmetry":1,"color_start":"#1E40AF","color_end":"#06B6D4","brightness":1.4},
            {"variation":"julia",    "var2":"swirl",    "v_mix":0.3,"seed":1618, "n_funcs":5,"symmetry":2,"color_start":"#C8A96E","color_end":"#1E3A5F","brightness":1.0},
            {"variation":"eyefish",  "var2":"sinusoidal","v_mix":0.5,"seed":999,  "n_funcs":4,"symmetry":1,"color_start":"#10B981","color_end":"#EC4899","brightness":1.1},
            {"variation":"polar",    "var2":"linear",   "v_mix":0.0,"seed":314,  "n_funcs":4,"symmetry":2,"color_start":"#F59E0B","color_end":"#8B5CF6","brightness":1.2},
            {"variation":"sinusoidal","var2":"julia",   "v_mix":0.4,"seed":271,  "n_funcs":3,"symmetry":5,"color_start":"#E11D48","color_end":"#0EA5E9","brightness":1.0},
            {"variation":"swirl",    "var2":"eyefish",  "v_mix":0.5,"seed":577,  "n_funcs":4,"symmetry":3,"color_start":"#34D399","color_end":"#A78BFA","brightness":1.1},
            {"variation":"julia",    "var2":"sinusoidal","v_mix":0.3,"seed":144,  "n_funcs":5,"symmetry":1,"color_start":"#FCD34D","color_end":"#7C3AED","brightness":1.0},
            {"variation":"horseshoe","var2":"swirl",    "v_mix":0.4,"seed":89,   "n_funcs":3,"symmetry":4,"color_start":"#F97316","color_end":"#06B6D4","brightness":1.3},
            {"variation":"bubble",   "var2":"sinusoidal","v_mix":0.5,"seed":55,   "n_funcs":4,"symmetry":1,"color_start":"#FCA5A5","color_end":"#60A5FA","brightness":1.2},
            {"variation":"disk",     "var2":"swirl",    "v_mix":0.4,"seed":377,  "n_funcs":4,"symmetry":6,"color_start":"#6EE7B7","color_end":"#F9A8D4","brightness":1.1},
            {"variation":"heart",    "var2":"linear",   "v_mix":0.0,"seed":233,  "n_funcs":3,"symmetry":2,"color_start":"#FCA5A5","color_end":"#A78BFA","brightness":1.0},
            {"variation":"sinusoidal","var2":"disk",    "v_mix":0.4,"seed":610,  "n_funcs":5,"symmetry":1,"color_start":"#C8A96E","color_end":"#EC4899","brightness":1.2},
            {"variation":"julia",    "var2":"polar",    "v_mix":0.3,"seed":987,  "n_funcs":4,"symmetry":3,"color_start":"#38BDF8","color_end":"#FB923C","brightness":1.1},
            {"variation":"swirl",    "var2":"bubble",   "v_mix":0.4,"seed":1597, "n_funcs":4,"symmetry":2,"color_start":"#4ADE80","color_end":"#F472B6","brightness":1.0},
        ]
        preset = ff_presets[index % len(ff_presets)]
        for key, val in preset.items():
            params[key] = {"value": val}
        return params, ""

    # Slightly vary equation-specific numeric params
    import hashlib
    seed_hash = int(hashlib.md5(f"item-{index}".encode()).hexdigest()[:8], 16)
    rng = __import__("random").Random(seed_hash)

    numeric_keys = [k for k, v in params.items()
                    if isinstance(v, dict) and isinstance(v.get("value"), (int, float))
                    and k not in ("color_start", "color_end", "background_color")]
    for key in numeric_keys:
        val = params[key]["value"]
        # Vary by ±15%
        delta = val * 0.15 * (rng.random() * 2 - 1)
        params[key]["value"] = type(val)(val + delta)

    return params, ""


@router.get("/render/bundle-item")
async def render_bundle_item(product: str = Query(...), index: int = Query(0)):
    # 1. Serve static pre-generated file
    static_path = os.path.join(STATIC_PREVIEW_DIR, f"{product}_{index}.jpg")
    if os.path.exists(static_path):
        with open(static_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=604800"})

    # 2. Fall back to dynamic render
    from database import SessionLocal
    from models.product import DigitalProduct, Product

    db = SessionLocal()
    try:
        item = db.query(DigitalProduct).filter(DigitalProduct.slug == product).first()
        if not item:
            item = db.query(Product).filter(Product.slug == product).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        equation_type = item.equation_type
        params_json = getattr(item, 'params_json', None)
        base_params = json.loads(params_json) if params_json else {}
    finally:
        db.close()

    # Uploaded/file products (e.g. digital-downloads PDFs) carry no real
    # equation_type — they're served from static previews, not rendered here.
    # Return 404 instead of letting render_equation raise a 500.
    if not equation_type or equation_type == "none":
        raise HTTPException(status_code=404, detail="No rendered preview for this product")

    varied, eq_override = _vary_params(base_params, index, equation_type)
    render_type = eq_override if eq_override else equation_type
    thumb_w, thumb_h = _preview_dims(equation_type)

    cache_key = hashlib.md5(
        json.dumps(
            {"eq": render_type, "params": varied, "w": thumb_w, "h": thumb_h, "idx": index},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache_path = os.path.join(PREVIEW_CACHE_DIR, f"bi_{cache_key}.jpg")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})

    img_bytes = render_equation(render_type, varied, width=thumb_w, height=thumb_h, hq=False)

    from PIL import Image
    import io as _io
    from services.watermark import add_watermark, enhance_preview
    img = Image.open(_io.BytesIO(img_bytes)).convert("RGB")
    img = enhance_preview(img)
    img = add_watermark(img, text="PREVIEW", opacity=30)
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    result = buf.getvalue()

    with open(cache_path, "wb") as f:
        f.write(result)

    return Response(content=result, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/render/pinterest")
async def render_pinterest_pin(
    product: str = Query(...),
    variant: int = Query(0, ge=0, le=2),
):
    """Render a 1000x1500 Pinterest-optimized pin image (vertical 2:3).
    Variants 0/1/2 produce visually distinct compositions for the same product
    so the auto-pinner can publish multiple non-identical pins."""
    from database import SessionLocal
    from models.product import DigitalProduct, Product

    db = SessionLocal()
    try:
        item = db.query(DigitalProduct).filter(DigitalProduct.slug == product).first()
        item_kind = "digital" if item else "physical"
        if not item:
            item = db.query(Product).filter(Product.slug == product).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        name = item.name
        price = float(getattr(item, "price_usd", 0) or 0)
        collection = getattr(item, "collection", "") or ""
        if item_kind == "digital":
            digital_type = (getattr(item, "product_type", "") or "").lower()
            product_label = {
                "image_pack": "Image Pack",
                "animation_pack": "Loop Animation Pack",
                "creator_assets": "Creator Assets",
                "thematic_bundle": "Digital Bundle",
            }.get(digital_type, "Digital Download")
        else:
            collection_l = collection.lower()
            name_l = (name or "").lower()
            product_l = product.lower()
            if "desk-mats" in collection_l or ("desk" in name_l and "mat" in name_l) or "desk-mat" in product_l:
                product_label = "Desk Mat"
            else:
                product_label = "Poster / Framed / Canvas"
    finally:
        db.close()

    jpeg = pinterest_renderer.render_pin(
        product_slug=product, name=name, price_usd=price,
        collection=collection, variant=variant,
        product_label=product_label,
    )
    return Response(content=jpeg, media_type="image/jpeg", headers={
        "Cache-Control": "public, max-age=86400",
    })


@router.get("/render/preview")
async def render_preview(product: str = Query(...)):
    # 1. Serve static pre-generated file (instant, served by nginx in prod)
    static_path = os.path.join(STATIC_PREVIEW_DIR, f"{product}.jpg")
    if os.path.exists(static_path):
        with open(static_path, "rb") as file:
            return Response(
                content=file.read(),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=604800"},
            )

    # 2. Fall back to dynamic render
    from database import SessionLocal
    from models.product import Product, DigitalProduct

    db = SessionLocal()
    try:
        item = db.query(DigitalProduct).filter(DigitalProduct.slug == product).first()
        if not item:
            item = db.query(Product).filter(Product.slug == product).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        equation_type = item.equation_type
        params_json = getattr(item, 'params_json', None)
        if params_json:
            params = json.loads(params_json)
        else:
            params = {}
        item_collection = getattr(item, "collection", "") or ""
    finally:
        db.close()

    # Desk-mat products use a dedicated renderer with landscape composition,
    # bypassing the equation engines used for posters / digital graphs.
    # NOTE: no watermark — desk-mats are physical POD products (Printful prints
    # them onto fabric), there is nothing pirate-able about a preview JPEG.
    if item_collection == "desk-mats":
        from services.deskmat_renderer import render_deskmat_design
        preview_w, preview_h = 1600, 800  # 2:1 landscape preview
        cache_key = hashlib.md5(
            json.dumps(
                {"dm": equation_type, "params": params, "w": preview_w, "h": preview_h, "v": "no-wm"},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cache_path = os.path.join(PREVIEW_CACHE_DIR, f"deskmat_{cache_key}.jpg")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/jpeg",
                                headers={"Cache-Control": "public, max-age=86400"})
        png_bytes = render_deskmat_design(equation_type, params, preview_w, preview_h)
        from PIL import Image as _Image
        import io as _io
        img = _Image.open(_io.BytesIO(png_bytes)).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        result = buf.getvalue()
        with open(cache_path, "wb") as fh:
            fh.write(result)
        return Response(content=result, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    preview_w, preview_h = _preview_dims(equation_type)

    cache_key = hashlib.md5(
        json.dumps(
            {"eq": equation_type, "params": params, "w": preview_w, "h": preview_h},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache_path = os.path.join(PREVIEW_CACHE_DIR, f"{cache_key}.jpg")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as file:
            return Response(
                content=file.read(),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )

    try:
        img_bytes = render_equation(
            equation_type,
            params,
            width=preview_w,
            height=preview_h,
            hq=False,
        )
    except Exception:
        # Some products (e.g. coloring books with equation_type "mixed") aren't
        # renderable here. Serve the brand fallback instead of a 500 so cards /
        # og:images never break. (Drop a static preview JPG for a real image.)
        _fallback = "/var/www/mathrelaxing.store/static/img/og-default.jpg"
        if os.path.exists(_fallback):
            with open(_fallback, "rb") as fh:
                return Response(content=fh.read(), media_type="image/jpeg",
                                headers={"Cache-Control": "public, max-age=3600"})
        raise HTTPException(status_code=404, detail="Preview not available for this product")

    from PIL import Image
    import io as _io
    from services.watermark import add_watermark, enhance_preview

    img = Image.open(_io.BytesIO(img_bytes)).convert("RGB")
    img = enhance_preview(img)
    img = add_watermark(img, text="PREVIEW", opacity=30)
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    result = buf.getvalue()

    with open(cache_path, "wb") as file:
        file.write(result)

    return Response(
        content=result,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/render/preview")
async def render_preview_custom():
    raise HTTPException(status_code=410, detail="Custom preview rendering has been retired.")


@router.get("/render/print")
async def render_print_file(
    product: str = Query(...),
    format: str = Query(default="poster"),
):
    from database import SessionLocal
    from models.product import Product
    from services.printful import FORMATS_BY_ID

    db = SessionLocal()
    try:
        item = db.query(Product).filter(Product.slug == product).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        equation_type = item.equation_type
        params = json.loads(item.params_json or "{}")
        item_collection = getattr(item, "collection", "") or ""
    finally:
        db.close()

    # ── Desk-mat dedicated path ───────────────────────────────────────
    # Desk-mat products bypass the equation renderers and use the
    # desk-mat-specific design system (services/deskmat_renderer.py)
    # which generates landscape, full-bleed, product-native artwork.
    if item_collection == "desk-mats" and format in ("gaming_mouse_pad", "mouse_pad"):
        from services.deskmat_renderer import render_deskmat_design
        fmt = FORMATS_BY_ID.get(format)
        specs = fmt["print_specs"]
        width, height = specs["width_px"], specs["height_px"]

        cache_key = hashlib.md5(
            json.dumps(
                {"dm": equation_type, "params": params, "w": width, "h": height, "fmt": format},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cache_path = os.path.join(PRINT_CACHE_DIR, f"deskmat_{cache_key}.png")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/png")
        img_bytes = render_deskmat_design(equation_type, params, width, height)
        with open(cache_path, "wb") as fh:
            fh.write(img_bytes)
        return Response(content=img_bytes, media_type="image/png")

    # ── Sticker dedicated path ────────────────────────────────────────
    # Stickers ship a pre-made static print file (real-equation art exported
    # to Printful's 900×900 kiss-cut printfile), not an equation render.
    if item_collection == "stickers":
        rel = (params.get("print_image") or "").lstrip("/")
        static_path = os.path.join("/var/www/mathrelaxing.store/static", rel)
        if rel and os.path.exists(static_path):
            with open(static_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/png",
                                headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(status_code=404, detail="Sticker print file not found")

    # Flat poster: the print file IS the mockup — art on white background at print resolution.
    # Printful prints exactly what it receives, so the customer gets what they saw on screen.
    if format in _FLAT_POSTER_FORMATS:
        from services.mockup import generate_flat_poster
        # 18×24 in at 300 dpi → 5400×7200 px (matches _SPEC_POSTER)
        pw, ph = 5400, 7200
        cache_key = hashlib.md5(
            json.dumps({"eq": equation_type, "params": params, "w": pw, "h": ph, "fmt": format},
                       sort_keys=True).encode()
        ).hexdigest()
        cache_path = os.path.join(PRINT_CACHE_DIR, f"poster_{cache_key}.png")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
        img_bytes = generate_flat_poster(equation_type, params, width=pw, height=ph)
        with open(cache_path, "wb") as f:
            f.write(img_bytes)
        return Response(content=img_bytes, media_type="image/png")

    fmt = FORMATS_BY_ID.get(format, FORMATS_BY_ID.get("canvas", FORMATS[0]))
    specs = fmt["print_specs"]
    width, height = specs["width_px"], specs["height_px"]

    cache_key = hashlib.md5(
        json.dumps(
            {"eq": equation_type, "params": params, "w": width, "h": height, "fmt": format},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache_path = os.path.join(PRINT_CACHE_DIR, f"{cache_key}.png")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as file:
            return Response(content=file.read(), media_type="image/png")

    img_bytes = render_equation(equation_type, params, width=width, height=height, hq=True)

    if "-notebook" in product:
        from PIL import Image as _Image
        import io as _io
        from services.watermark import add_elegant_equation
        
        # Map equation_type to Title and Equation
        eq_map = {
            "lorenz": ("LORENZ ATTRACTOR", "dx/dt = σ(y - x)"),
            "clifford": ("CLIFFORD ATTRACTOR", "x_{n+1} = sin(a y_n) + c cos(a x_n)"),
            "aizawa": ("AIZAWA ATTRACTOR", "dz/dt = c + a*z - z^3/3 - (x^2+y^2)(1+e*z) + f*z*x^3"),
            "julia": ("JULIA SET", "z_{n+1} = z_n^2 + c"),
            "mandelbrot": ("MANDELBROT SET", "z_{n+1} = z_n^2 + c"),
            "rose": ("POLAR ROSE", "r = a cos(kθ)"),
            "joukowski": ("JOUKOWSKI TRANSFORM", "w = z + 1/z"),
            "mobius-grid": ("MÖBIUS TRANSFORM", "f(z) = (az + b)/(cz + d)"),
            "superformula": ("SUPERFORMULA", "r = ( |cos(mθ/4)/a|^n_2 + |sin(mθ/4)/b|^n_3 )^{-1/n_1}"),
            "chladni": ("CHLADNI RESONANCE", "cos(nπx/L)cos(mπy/L) - cos(mπx/L)cos(nπy/L) = 0"),
            "turing": ("TURING PATTERN", "∂u/∂t = D_u ∇²u + f(u,v)"),
            "gray-scott": ("REACTION DIFFUSION", "∂v/∂t = D_v ∇²v - uv² - (F+k)v"),
            "voronoi": ("VORONOI TESSELLATION", "R_k = { x | d(x, P_k) ≤ d(x, P_j) }"),
            "flow-field": ("VECTOR FLOW", "v(x, y) = ∇ × A(x, y)"),
            "fractal-flame": ("FRACTAL FLAME", "F(x) = Σ p_i f_i(x)"),
            "de_jong": ("DE JONG ATTRACTOR", "x_{n+1} = sin(a y_n) - cos(b x_n)"),
        }
        
        title, eq = eq_map.get(equation_type, ("MATHEMATICAL PATTERN", "f(x, y) = 0"))
        
        img = _Image.open(_io.BytesIO(img_bytes)).convert("RGB")
        img = add_elegant_equation(img, title, eq)
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()


    with open(cache_path, "wb") as file:
        file.write(img_bytes)

    return Response(content=img_bytes, media_type="image/png")


_PSD_ONLY_FORMATS = {"canvas-studio"}  # spiral_notebook usa el mockup nativo de Printful (product 946); el compositor PSD queda solo como fallback

_PSD_VARIANT_MAP = {
    "canvas":        "free-vertical-canvas",
    "canvas-studio": "free-canvas-left",
    "framed-poster": "free-framed-poster",
    "acrylic":       "acrylic",
    "spiral_notebook": "spiral_notebook",
}

_FLAT_POSTER_PREVIEW_W = 1200
_FLAT_POSTER_PREVIEW_H = 1600


def _load_product_eq_params(product_slug: str):
    from database import SessionLocal
    from models.product import Product
    db = SessionLocal()
    try:
        item = db.query(Product).filter(Product.slug == product_slug).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        return item.equation_type, json.loads(item.params_json or "{}")
    finally:
        db.close()


async def _flat_poster_mockup(product_slug: str) -> bytes:
    from services.mockup import generate_flat_poster
    eq_type, params = _load_product_eq_params(product_slug)
    
    # Use Printful's exact spiral notebook print dimensions (1650x2550) so the aspect ratio matches
    # and Printful doesn't squish our circular designs.
    if "-notebook" in product_slug:
        pw, ph = 1650, 2550
    else:
        pw, ph = _FLAT_POSTER_PREVIEW_W, _FLAT_POSTER_PREVIEW_H
        
    img_bytes = generate_flat_poster(
        eq_type, params,
        width=pw,
        height=ph,
    )
    if "-notebook" in product_slug:
        from PIL import Image as _Image
        import io as _io
        from services.watermark import add_elegant_equation
        
        eq_map = {
            "lorenz": ("LORENZ ATTRACTOR", "dx/dt = σ(y - x)"),
            "clifford": ("CLIFFORD ATTRACTOR", "x_{n+1} = sin(a y_n) + c cos(a x_n)"),
            "aizawa": ("AIZAWA ATTRACTOR", "dz/dt = c + a*z - z^3/3 - (x^2+y^2)(1+e*z) + f*z*x^3"),
            "julia": ("JULIA SET", "z_{n+1} = z_n^2 + c"),
            "mandelbrot": ("MANDELBROT SET", "z_{n+1} = z_n^2 + c"),
            "rose": ("POLAR ROSE", "r = a cos(kθ)"),
            "joukowski": ("JOUKOWSKI TRANSFORM", "w = z + 1/z"),
            "mobius-grid": ("MÖBIUS TRANSFORM", "f(z) = (az + b)/(cz + d)"),
            "superformula": ("SUPERFORMULA", "r = ( |cos(mθ/4)/a|^n_2 + |sin(mθ/4)/b|^n_3 )^{-1/n_1}"),
            "chladni": ("CHLADNI RESONANCE", "cos(nπx/L)cos(mπy/L) - cos(mπx/L)cos(nπy/L) = 0"),
            "turing": ("TURING PATTERN", "∂u/∂t = D_u ∇²u + f(u,v)"),
            "gray-scott": ("REACTION DIFFUSION", "∂v/∂t = D_v ∇²v - uv² - (F+k)v"),
            "voronoi": ("VORONOI TESSELLATION", "R_k = { x | d(x, P_k) ≤ d(x, P_j) }"),
            "flow-field": ("VECTOR FLOW", "v(x, y) = ∇ × A(x, y)"),
            "fractal-flame": ("FRACTAL FLAME", "F(x) = Σ p_i f_i(x)"),
            "de_jong": ("DE JONG ATTRACTOR", "x_{n+1} = sin(a y_n) - cos(b x_n)"),
        }
        
        title, eq = eq_map.get(eq_type, ("MATHEMATICAL PATTERN", "f(x, y) = 0"))
        
        img = _Image.open(_io.BytesIO(img_bytes)).convert("RGB")
        img = add_elegant_equation(img, title, eq)
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()
    return img_bytes


@router.get("/render/apparel-print")
async def render_apparel_print(product: str = Query(...)):
    """Transparent, unwatermarked PNG for clothing prints."""
    from database import SessionLocal
    from models.product import Product

    db = SessionLocal()
    try:
        item = db.query(Product).filter(Product.slug == product).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        equation_type = item.equation_type
        params = json.loads(item.params_json or "{}")
    finally:
        db.close()

    # For t-shirts, Printful wants 4500x5398 (from print_specs)
    # We render at slightly lower res to be faster, it's just for mockups/print
    # We will use 2250x2699
    width, height = 2250, 2699

    if params.get("apparel_design"):
        # Garment-exclusive bold design (motif + glow + elegant equation).
        from services.renderer import render_apparel_design
        img_bytes = render_apparel_design(params, width, height)
    else:
        with TransparentRender():
            img_bytes = render_equation(equation_type, params, width=width, height=height, hq=True)

    return Response(content=img_bytes, media_type="image/png")


@router.get("/render/aop-print")
async def render_aop_print(product: str = Query(...), v: str = Query("1")):
    """Full-bleed pattern print for all-over-print (cut-and-sew) garments, rendered
    at (capped) printfile resolution and cached so Printful gets a print-quality file."""
    import io as _io
    from PIL import Image as _Image
    from database import SessionLocal
    from models.product import Product
    from services.printful import format_for_garment

    db = SessionLocal()
    try:
        item = db.query(Product).filter(Product.slug == product).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        equation_type = item.equation_type
        params = json.loads(item.params_json or "{}")
    finally:
        db.close()

    # Target the garment's real printfile size, capped on the short side to stay
    # memory-safe on the 4 GB VPS (organic patterns tolerate a slight upscale).
    spec = format_for_garment(params.get("garment", "aop_leggings")).get("print_specs", {})
    tw, th = int(spec.get("width_px", 4096)), int(spec.get("height_px", 4096))
    SHORT_CAP = 4600
    short = min(tw, th)
    if short > SHORT_CAP:
        sc = SHORT_CAP / short
        tw, th = max(2, int(tw * sc)), max(2, int(th * sc))

    cache_path = os.path.join(MOCKUP_CACHE_DIR, f"aop_{product}_{tw}x{th}_v{MOCKUP_VERSION}.png")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as fh:
            return Response(content=fh.read(), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=604800"})

    # Render at a moderate base, then resize to the printfile dimensions.
    base = render_equation(equation_type, params, width=2600,
                           height=int(2600 * th / tw), hq=True)
    img = _Image.open(_io.BytesIO(base)).convert("RGB").resize((tw, th), _Image.LANCZOS)
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    with open(cache_path, "wb") as fh:
        fh.write(data)
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})



async def _psd_mockup(product_slug: str, format_id: str) -> bytes:
    from database import SessionLocal
    from models.product import Product
    from services.mockup import generate_mockup as _gen

    variant = _PSD_VARIANT_MAP.get(format_id, "free-vertical-canvas")
    db = SessionLocal()
    try:
        item = db.query(Product).filter(Product.slug == product_slug).first()
        if not item:
            raise HTTPException(status_code=404, detail="Product not found")
        eq_type = item.equation_type
        params = json.loads(item.params_json or "{}")
    finally:
        db.close()
    return _gen(eq_type, params, variant=variant, art_style=None, product_slug=product_slug)


@router.get("/render/mockup")
async def render_mockup(
    product: str = Query(...),
    format: str = Query(default="poster"),
):
    import services.printful as pf
    from services.printful import FORMATS_BY_ID

    # Sticker packs bundle several designs — there is no single Printful mockup,
    # so the product image is the composite card served by /render/preview.
    if format == "sticker_pack":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/api/render/preview?product={product}")

    # Stylized, self-generated sticker scenes (Printful only returns one flat
    # mockup for Kiss-Cut stickers). format = "sticker_kiss_3in-<scene>".
    if format.startswith("sticker_kiss_3in-"):
        from services.sticker_scenes import SCENES, render_scene
        suffix = format.split("-", 1)[1]
        if suffix in SCENES:
            cache_key = hashlib.md5(f"{product}:{format}:{MOCKUP_VERSION}".encode()).hexdigest()
            cache_path = os.path.join(MOCKUP_CACHE_DIR, f"{cache_key}.jpg")
            if not os.path.exists(cache_path):
                from database import SessionLocal
                from models.product import Product
                db = SessionLocal()
                try:
                    item = db.query(Product).filter(Product.slug == product).first()
                    params = json.loads(item.params_json or "{}") if item else {}
                finally:
                    db.close()
                rel = (params.get("print_image") or "").lstrip("/")
                design_path = os.path.join("/var/www/mathrelaxing.store/static", rel)
                if not rel or not os.path.exists(design_path):
                    raise HTTPException(status_code=404, detail="Sticker design not found")
                with open(cache_path, "wb") as fh:
                    fh.write(render_scene(design_path, suffix))
            with open(cache_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/jpeg",
                                headers={"Cache-Control": "public, max-age=604800"})

    # Lifestyle scene: Printful room mockup — uses clean (no watermark) flat poster as source
    if format == "poster-lifestyle":
        cache_key = hashlib.md5(f"poster-lifestyle:{product}:{MOCKUP_VERSION}".encode()).hexdigest()
        cache_path = os.path.join(MOCKUP_CACHE_DIR, f"{cache_key}.jpg")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/jpeg",
                                headers={"Cache-Control": "public, max-age=604800"})
        fmt = FORMATS_BY_ID["poster"]
        # the version token forces Printful to bypass their artwork URL cache and fetch the latest clean poster
        image_url = f"https://mathrelaxing.store/api/render/mockup?product={product}&format=poster-clean&v={MOCKUP_VERSION}"
        scene = pf.get_mockup_scene("poster", product)
        img_bytes = await pf.generate_mockup(
            fmt["printful_product_id"],
            fmt.get("printful_variant_id") or fmt.get("printful_variants", {}).get("L"),
            image_url,
            "poster",
            scene=scene,
        )
        if img_bytes:
            with open(cache_path, "wb") as fh:
                fh.write(img_bytes)
            return Response(content=img_bytes, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=604800"})
        raise HTTPException(status_code=503, detail="Lifestyle mockup temporarily unavailable")

    # Clean flat poster (no watermark) — internal use only, source image for Printful
    if format == "poster-clean":
        cache_key = hashlib.md5(f"flatposter:{product}:poster:{MOCKUP_VERSION}".encode()).hexdigest()
        cache_path = os.path.join(MOCKUP_CACHE_DIR, f"{cache_key}.png")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/png",
                                headers={"Cache-Control": "public, max-age=604800"})
        img_bytes = await _flat_poster_mockup(product)
        with open(cache_path, "wb") as fh:
            fh.write(img_bytes)
        return Response(content=img_bytes, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=604800"})

    # Flat poster ART view: same image but with PREVIEW watermark
    if format in _FLAT_POSTER_FORMATS:
        cache_key = hashlib.md5(f"flatposter:{product}:{format}:{MOCKUP_VERSION}".encode()).hexdigest()
        cache_path = os.path.join(MOCKUP_CACHE_DIR, f"{cache_key}.png")
        if not os.path.exists(cache_path):
            img_bytes = await _flat_poster_mockup(product)
            with open(cache_path, "wb") as fh:
                fh.write(img_bytes)
        with open(cache_path, "rb") as fh:
            clean_bytes = fh.read()
        # Apply watermark for display
        from PIL import Image as _Image
        import io as _io
        from services.watermark import add_watermark
        img = _Image.open(_io.BytesIO(clean_bytes)).convert("RGB")
        img = add_watermark(img, text="PREVIEW", opacity=30)
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        wm_bytes = buf.getvalue()
        return Response(content=wm_bytes, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})



    # Room-scene variants always use the PSD compositor
    if format in _PSD_ONLY_FORMATS:
        img_bytes = await _psd_mockup(product, format)
        return Response(content=img_bytes, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})

    # Check Printful mockup cache. MOCKUP_VERSION is part of the key so bumping
    # that one constant invalidates the disk cache too — no manual rm needed.
    cache_key = hashlib.md5(f"{product}:{format}:{MOCKUP_VERSION}".encode()).hexdigest()
    cache_path = os.path.join(MOCKUP_CACHE_DIR, f"{cache_key}.jpg")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as fh:
            return Response(content=fh.read(), media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})

    # Apparel: one Printful task yields several distinct views (Front/Back/Left/
    # Right/…). Cache that URL list per product and serve scene N → the Nth view,
    # so the gallery shows genuinely different mockups instead of repeats.
    _ap_base = format.rsplit("-", 1)[0] if format not in FORMATS_BY_ID else format
    if _ap_base in ("unisex_tshirt", "unisex_hoodie", "aop_leggings", "aop_joggers", "aop_sweatshirt") and pf.PRINTFUL_API_KEY:
        import httpx
        suffix = format.rsplit("-", 1)[1] if "-" in format else "1"
        idx = (int(suffix) - 1) if suffix.isdigit() else 0
        views_path = os.path.join(MOCKUP_CACHE_DIR, f"{product}_{_ap_base}_v{MOCKUP_VERSION}_views.json")
        views = []
        if os.path.exists(views_path):
            try:
                with open(views_path) as fh:
                    views = json.load(fh)
            except Exception:
                views = []
        if not views:
            lock = _tshirt_locks.setdefault(f"{product}:{_ap_base}", asyncio.Lock())
            async with lock:
                # Re-check: another concurrent request may have built it while we waited.
                if os.path.exists(views_path):
                    try:
                        with open(views_path) as fh:
                            views = json.load(fh)
                    except Exception:
                        views = []
                if not views:
                    fmt_t = FORMATS_BY_ID.get(_ap_base)
                    if fmt_t.get("aop"):
                        image_url = f"https://mathrelaxing.store/api/render/aop-print?product={product}&v={MOCKUP_VERSION}"
                    else:
                        image_url = f"https://mathrelaxing.store/api/render/apparel-print?product={product}&v={MOCKUP_VERSION}"
                    views = await pf.generate_mockup_views(
                        fmt_t["printful_product_id"],
                        fmt_t.get("printful_variants", {}).get("L"),
                        image_url, _ap_base,
                    )
                    if views:
                        with open(views_path, "w") as fh:
                            json.dump(views, fh)
        if views:
            url = views[min(idx, len(views) - 1)]
            async with httpx.AsyncClient() as client:
                r = await client.get(url, timeout=20)
            if r.status_code == 200:
                with open(cache_path, "wb") as fh:
                    fh.write(r.content)
                return Response(content=r.content, media_type="image/jpeg",
                                headers={"Cache-Control": "public, max-age=86400"})

    # Try Printful Mockup Generator
    # Resolve alias suffixes (e.g. "gaming_mouse_pad-flat" → base "gaming_mouse_pad",
    # scene is picked by the alias via get_mockup_scene).
    base_format = format.rsplit("-", 1)[0] if format not in FORMATS_BY_ID else format
    fmt = FORMATS_BY_ID.get(base_format)
    if fmt and pf.PRINTFUL_API_KEY and format != "spiral_notebook":
        # v=clean3 busts Printful's URL-side cache so they re-fetch the
        # current (no-watermark) preview instead of a stale watermarked copy.
        if base_format == "spiral_notebook":
            image_url = f"https://mathrelaxing.store/api/render/print?product={product}&format=spiral_notebook&v={MOCKUP_VERSION}"
        elif fmt.get("aop"):
            image_url = f"https://mathrelaxing.store/api/render/aop-print?product={product}&v={MOCKUP_VERSION}"
        elif base_format in ("unisex_tshirt", "unisex_hoodie"):
            image_url = f"https://mathrelaxing.store/api/render/apparel-print?product={product}&v={MOCKUP_VERSION}"
        elif base_format == "sticker_kiss_3in":
            image_url = f"https://mathrelaxing.store/api/render/print?product={product}&format=sticker_kiss_3in&v={MOCKUP_VERSION}"
        else:
            # Any other physical product (mouse pads, and any future flat product):
            # use the clean print file as the Printful source. NEVER fall back to
            # /render/preview here — that endpoint bakes in the "PREVIEW" watermark
            # for most products, which would print onto the 3D mockup.
            image_url = (
                f"https://mathrelaxing.store/api/render/print"
                f"?product={product}&format={base_format}&v={MOCKUP_VERSION}"
            )
        img_bytes = await pf.generate_mockup(
            fmt["printful_product_id"],
            fmt.get("printful_variant_id") or fmt.get("printful_variants", {}).get("L"),
            image_url,
            base_format,
            scene=pf.get_mockup_scene(format, product),
        )
        if img_bytes:
            with open(cache_path, "wb") as fh:
                fh.write(img_bytes)
            return Response(content=img_bytes, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})

    # Stickers have no PSD scene; if Printful is momentarily unavailable, serve
    # the flat print file so the gallery still shows the sticker art (the PSD
    # fallback below renders from equation_type, which stickers don't have).
    if base_format == "sticker_kiss_3in":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/api/render/print?product={product}&format=sticker_kiss_3in")

    # PSD fallback
    img_bytes = await _psd_mockup(product, format)
    return Response(content=img_bytes, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=604800"})


@router.get("/render/hq-image")
async def render_hq_image(
    token: str = Query(...),
    product: str = Query(...),
    index: int = Query(0),
    orientation: str = Query("portrait"),  # portrait | landscape | square
):
    """Generate a HQ image for a paid purchase, in the requested orientation."""
    from database import SessionLocal
    from models.product import Purchase, DigitalProduct

    db = SessionLocal()
    try:
        purchase = db.query(Purchase).filter(Purchase.download_token == token).first()
        if not purchase or purchase.status != "paid":
            raise HTTPException(status_code=403, detail="Invalid or unpaid download token")
        product_obj = db.query(DigitalProduct).filter(
            DigitalProduct.slug == product,
            DigitalProduct.id == purchase.product_id,
        ).first()
        if not product_obj:
            raise HTTPException(status_code=404, detail="Product not found for this token")
        equation_type = product_obj.equation_type
        params_json = getattr(product_obj, "params_json", None)
        base_params = json.loads(params_json) if params_json else {}
    finally:
        db.close()

    _HQ_SHORT = 3200
    orientation = orientation.lower()
    if orientation == "landscape":
        hq_w, hq_h = _HQ_SHORT * 5 // 4, _HQ_SHORT   # 4000×3200
    elif orientation == "square":
        hq_w, hq_h = _HQ_SHORT, _HQ_SHORT             # 3200×3200
    else:
        hq_w, hq_h = _HQ_SHORT, _HQ_SHORT * 5 // 4   # 3200×4000

    static_download_candidates = [
        f"/var/www/mathrelaxing.store/static/downloads/{product}_{index}_{orientation}.jpg",
        f"/var/www/mathrelaxing.store/static/downloads/{product}_{index}_{orientation}.png",
        f"/var/www/mathrelaxing.store/static/downloads/{product}_{index}_portrait.jpg",
        f"/var/www/mathrelaxing.store/static/downloads/{product}_{index}_portrait.png",
        f"/var/www/mathrelaxing.store/static/previews/{product}_{index}_clean.jpg",
    ]
    for static_path in static_download_candidates:
        if os.path.exists(static_path):
            from PIL import Image
            import io as _io

            img = Image.open(static_path).convert("RGB")
            src_ratio = img.width / img.height
            dst_ratio = hq_w / hq_h
            if src_ratio > dst_ratio:
                new_w = int(img.height * dst_ratio)
                left = max(0, (img.width - new_w) // 2)
                img = img.crop((left, 0, left + new_w, img.height))
            elif src_ratio < dst_ratio:
                new_h = int(img.width / dst_ratio)
                top = max(0, (img.height - new_h) // 2)
                img = img.crop((0, top, img.width, top + new_h))
            if img.size != (hq_w, hq_h):
                img = img.resize((hq_w, hq_h), Image.Resampling.LANCZOS)
            buf = _io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            fname = f"mathrelaxing-{product}-{index}-{orientation}.png"
            return Response(
                content=buf.getvalue(),
                media_type="image/png",
                headers={
                    "Content-Disposition": f'attachment; filename="{fname}"',
                    "Cache-Control": "private, max-age=86400",
                },
            )

    varied, eq_override = _vary_params(base_params, index, equation_type)
    render_type = eq_override if eq_override else equation_type

    cache_key = hashlib.md5(
        json.dumps(
            {"tok": token, "prod": product, "idx": index, "ori": orientation},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache_path = os.path.join(RENDER_CACHE_DIR, f"hq_{cache_key}.png")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            data = f.read()
    else:
        data = render_equation(render_type, varied, width=hq_w, height=hq_h, hq=True)
        with open(cache_path, "wb") as f:
            f.write(data)

    fname = f"mathrelaxing-{product}-{index}-{orientation}.png"
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.post("/render")
async def render_image():
    raise HTTPException(status_code=410, detail="Custom rendering has been retired.")


STATIC_VIDEO_DIR = "/var/www/mathrelaxing.store/static/videos"


@router.api_route("/video/{animation_key}", methods=["GET", "HEAD"])
async def serve_video(animation_key: str, format: str = Query("1080p30")):
    """Serve a pre-generated seamless loop video.

    animation_key: lorenz_flow, clifford_spin, aizawa_dance, attractor_morph, lorenz_drift
    format: 1080p30, 1080p60, 4k30, 4k60
    """
    # Validate format
    valid_formats = {"1080p30", "1080p60", "4k30", "4k60"}
    if format not in valid_formats:
        raise HTTPException(status_code=400,
                            detail=f"Invalid format. Choose from: {', '.join(sorted(valid_formats))}")

    filename = f"{animation_key}_{format}.mp4"
    path = os.path.join(STATIC_VIDEO_DIR, filename)

    if not os.path.exists(path):
        raise HTTPException(status_code=404,
                            detail=f"Video not found. It may still be generating.")

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=604800",
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.api_route("/video-preview/{animation_key}", methods=["GET", "HEAD"])
async def video_preview(animation_key: str):
    """Serve a low-res preview of a seamless loop video for the product page."""
    # Try 1080p30 as preview (smallest file)
    for fmt in ("1080p30",):
        path = os.path.join(STATIC_VIDEO_DIR, f"{animation_key}_{fmt}.mp4")
        if os.path.exists(path):
            return FileResponse(
                path,
                media_type="video/mp4",
                headers={"Cache-Control": "public, max-age=604800"},
            )

    raise HTTPException(status_code=404, detail="Preview video not found")
