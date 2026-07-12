#!/usr/bin/env python3
"""Pre-generate all preview images at high resolution with watermark.

Saves files to /var/www/mathrelaxing.store/static/previews/ so nginx
can serve them directly without hitting the app server.

Usage:
    python3 pregen_previews.py              # generate all
    python3 pregen_previews.py --force       # regenerate all
    python3 pregen_previews.py --slug xxx    # single product
"""
import json
import os
import sys
import time

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from dotenv import load_dotenv
load_dotenv(".env")

from database import SessionLocal
from models.product import DigitalProduct, Product
from services.renderer import render_equation
from services.watermark import add_watermark, enhance_preview
from PIL import Image
import io

# Aspect ratios per equation type
_ASPECT_MAP = {
    "lorenz": "portrait", "clifford": "portrait", "aizawa": "portrait",
    "julia": "portrait", "mandelbrot": "portrait", "rose": "portrait",
    "joukowski": "portrait", "mobius-grid": "portrait",
    "lissajous": "landscape", "harmonograph": "landscape",
    "superformula": "square", "chladni": "square", "turing": "square",
    "gray-scott": "square", "voronoi": "square",
}
_BASE_PX = 1280

def _preview_dims(eq_type):
    ratio = _ASPECT_MAP.get(eq_type, "portrait")
    if ratio == "landscape":
        return _BASE_PX * 5 // 4, _BASE_PX   # 1600×1280
    elif ratio == "square":
        return _BASE_PX, _BASE_PX              # 1280×1280
    else:
        return _BASE_PX, _BASE_PX * 5 // 4    # 1280×1600

OUTPUT_DIR = "/var/www/mathrelaxing.store/static/previews"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Color palettes for bundle item variations
_ITEM_PALETTES = [
    ("#c8a96e", "#7ecfb3"), ("#e85d75", "#6ec8cf"), ("#a855f7", "#38bdf8"),
    ("#f59e0b", "#ef4444"), ("#10b981", "#8b5cf6"), ("#ec4899", "#f97316"),
    ("#06b6d4", "#a855f7"), ("#84cc16", "#0ea5e9"), ("#f43f5e", "#c084fc"),
    ("#14b8a6", "#f59e0b"), ("#e879f9", "#34d399"), ("#fb923c", "#4f46e5"),
    ("#22d3ee", "#fb7185"), ("#a3e635", "#7c3aed"), ("#f472b6", "#2dd4bf"),
    ("#fbbf24", "#6366f1"), ("#34d399", "#e11d48"), ("#818cf8", "#facc15"),
    ("#c084fc", "#22c55e"), ("#fb7185", "#0284c7"),
]


def _vary_params(base_params: dict, index: int, eq_type: str = "") -> tuple:
    """Return (varied_params, eq_type_override). Override is '' if no change."""
    import copy, hashlib, random
    params = copy.deepcopy(base_params)
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
        # Reset zoom and center for each distinct Julia set
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
            # (eq_type_override, params_dict)
            ("lorenz",   {"sigma": 10.0, "rho": 28.0,  "beta": 2.667}),    # Lorenz Dream
            ("lorenz",   {"sigma": 14.0, "rho": 28.0,  "beta": 2.667}),    # Lorenz Cascade
            ("clifford", {"a": -1.4,  "b": 1.6,   "c": 1.0,  "d": 0.7}),   # Clifford Spiral
            ("clifford", {"a": -1.7,  "b": 1.8,   "c": -0.9, "d": 0.4}),   # Clifford Bloom
            ("aizawa",   {"a": 0.95,  "b": 0.7,   "c": 0.6,  "d": 3.5, "e": 0.25, "f": 0.1}),  # Aizawa Orbit
            ("aizawa",   {"a": 0.7,   "b": 0.8,   "c": 0.5,  "d": 3.0, "e": 0.35, "f": 0.15}), # Aizawa Ribbon
            ("lorenz",   {"sigma": 10.0, "rho": 24.0,  "beta": 1.5}),      # Lorenz Midnight
            ("clifford", {"a": 1.1,   "b": -1.3,  "c": 1.0,  "d": 1.7}),   # Clifford Nebula
            ("lorenz",   {"sigma": 12.0, "rho": 34.0,  "beta": 2.8}),      # Lorenz Aurora
            ("aizawa",   {"a": 1.1,   "b": 0.5,   "c": 0.8,  "d": 4.0, "e": 0.2,  "f": 0.05}), # Aizawa Vortex
            ("clifford", {"a": -1.8,  "b": -1.9,  "c": -1.0, "d": -0.9}),  # Clifford Crystal
            ("lorenz",   {"sigma": 10.0, "rho": 30.0,  "beta": 2.0}),      # Lorenz Ember
            ("aizawa",   {"a": 0.8,   "b": 0.9,   "c": 0.4,  "d": 2.5, "e": 0.3,  "f": 0.2}),  # Aizawa Silk
            ("clifford", {"a": 1.7,   "b": 1.8,   "c": -0.5, "d": -1.0}),  # Clifford Frost
            ("lorenz",   {"sigma": 8.0,  "rho": 26.0,  "beta": 3.0}),      # Lorenz Dusk
            ("aizawa",   {"a": 0.95,  "b": 0.7,   "c": 0.6,  "d": 3.5, "e": 0.25, "f": 0.1}),  # Aizawa Storm
            ("clifford", {"a": 1.2,   "b": 1.1,   "c": -1.0, "d": -1.6}),  # Clifford Petal
            ("lorenz",   {"sigma": 10.0, "rho": 22.0,  "beta": 2.5}),      # Lorenz Zen
            ("aizawa",   {"a": 0.6,   "b": 1.0,   "c": 0.3,  "d": 2.0, "e": 0.4,  "f": 0.25}), # Aizawa Echo
            ("clifford", {"a": 1.3,   "b": -1.1,  "c": 0.8,  "d": 1.4}),   # Clifford Wave
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
            {"pattern_type": "coral",       "f": 0.055, "k": 0.062, "f_var": 0.003, "k_var": 0.002, "var_freq": 3.0},  # Coral Growth
            {"pattern_type": "fingerprint",  "f": 0.025, "k": 0.055, "f_var": 0.002, "k_var": 0.001, "var_freq": 5.0},  # Fingerprint
            {"pattern_type": "coral",       "f": 0.014, "k": 0.045, "f_var": 0.004, "k_var": 0.003, "var_freq": 2.0},  # RD Spiral
            {"pattern_type": "labyrinth",   "f": 0.029, "k": 0.057, "f_var": 0.002, "k_var": 0.001, "var_freq": 4.0},  # Labyrinth
            {"pattern_type": "mitosis",     "f": 0.036, "k": 0.065, "f_var": 0.001, "k_var": 0.001, "var_freq": 6.0},  # Mitosis
            {"pattern_type": "spots",       "f": 0.035, "k": 0.065, "f_var": 0.002, "k_var": 0.002, "var_freq": 3.0},  # RD Spots
            {"pattern_type": "worms",       "f": 0.04,  "k": 0.06,  "f_var": 0.003, "k_var": 0.002, "var_freq": 2.5},  # Worms
            {"pattern_type": "stripes",     "f": 0.025, "k": 0.05,  "f_var": 0.002, "k_var": 0.001, "var_freq": 4.0},  # RD Stripe
            {"pattern_type": "coral",       "f": 0.048, "k": 0.06,  "f_var": 0.005, "k_var": 0.004, "var_freq": 2.0},  # Coral Bloom
            {"pattern_type": "labyrinth",   "f": 0.026, "k": 0.051, "f_var": 0.003, "k_var": 0.002, "var_freq": 3.5},  # RD Maze
            {"pattern_type": "fingerprint", "f": 0.02,  "k": 0.05,  "f_var": 0.003, "k_var": 0.002, "var_freq": 6.0},  # Fingerprint II
            {"pattern_type": "waves",       "f": 0.014, "k": 0.054, "f_var": 0.004, "k_var": 0.003, "var_freq": 2.0},  # RD Waves
            {"pattern_type": "coral",       "f": 0.062, "k": 0.063, "f_var": 0.003, "k_var": 0.002, "var_freq": 4.0},  # Coral Reef
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
            {"pattern_type": "spots",     "scale": 2.0},   # Turing Spots
            {"pattern_type": "stripes",   "scale": 1.5},   # Turing Stripes
            {"pattern_type": "labyrinth", "scale": 1.5},   # Turing Labyrinth
            {"pattern_type": "spots",     "scale": 1.0},   # Turing Leopard (dense spots)
            {"pattern_type": "stripes",   "scale": 1.0},   # Turing Giraffe (dense stripes)
            {"pattern_type": "labyrinth", "scale": 1.0},   # Turing Coral (dense labyrinth)
        ]
        preset = turing_presets[index % len(turing_presets)]
        for key, val in preset.items():
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""
    
    # For Voronoi Organics, force distinct cell counts, shapes, and visual effects
    if eq_type == "voronoi":
        voronoi_presets = [
            {"n_cells": 40,  "organic": 0.9,  "irregularity": 0.2, "glow_strength": 0.7, "cell_color_var": 0.4},  # Bubbles
            {"n_cells": 150, "organic": 0.1,  "irregularity": 0.8, "glow_strength": 0.3, "cell_color_var": 0.1},  # Cracks
            {"n_cells": 70,  "organic": 0.6,  "irregularity": 0.4, "glow_strength": 0.5, "cell_color_var": 0.3},  # Cells
            {"n_cells": 200, "organic": 0.3,  "irregularity": 0.3, "glow_strength": 0.8, "cell_color_var": 0.5},  # Frost
            {"n_cells": 30,  "organic": 0.5,  "irregularity": 0.1, "glow_strength": 0.6, "cell_color_var": 0.2},  # Honeycomb
        ]
        preset = voronoi_presets[index % len(voronoi_presets)]
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
            if key in params:
                params[key]["value"] = val
            else:
                params[key] = {"value": val}
        return params, ""
    
    # For Fractal Flames, explicitly assign variations matching the image pack descriptions
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
    
    seed_hash = int(hashlib.md5(f"item-{index}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_hash)
    numeric_keys = [k for k, v in params.items()
                    if isinstance(v, dict) and isinstance(v.get("value"), (int, float))
                    and k not in ("color_start", "color_end", "background_color")]
    for key in numeric_keys:
        val = params[key]["value"]
        delta = val * 0.15 * (rng.random() * 2 - 1)
        params[key]["value"] = type(val)(val + delta)
    return params, ""


def _render_and_watermark(eq_type, params, width, height, hq=False) -> tuple:
    """Render equation, return (watermarked_bytes, clean_bytes)."""
    img_bytes = render_equation(eq_type, params, width=width, height=height, hq=hq)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = enhance_preview(img)

    # Clean version (no watermark) for zoom
    clean_buf = io.BytesIO()
    img.save(clean_buf, format="JPEG", quality=90, optimize=True)
    clean_bytes = clean_buf.getvalue()

    # Watermarked version for display
    img_wm = add_watermark(img, text="PREVIEW", opacity=30)
    wm_buf = io.BytesIO()
    img_wm.save(wm_buf, format="JPEG", quality=85, optimize=True)
    wm_bytes = wm_buf.getvalue()

    return wm_bytes, clean_bytes


def generate_preview(slug: str, eq_type: str, params: dict, force: bool = False):
    """Generate main preview image for a product."""
    out_path = os.path.join(OUTPUT_DIR, f"{slug}.jpg")
    clean_path = os.path.join(OUTPUT_DIR, f"{slug}_clean.jpg")
    if not force and os.path.exists(out_path) and os.path.exists(clean_path):
        print(f"  [skip] {slug} (exists)", flush=True)
        return

    w, h = _preview_dims(eq_type)
    t0 = time.time()
    wm_bytes, clean_bytes = _render_and_watermark(eq_type, params, w, h, hq=False)
    with open(out_path, "wb") as f:
        f.write(wm_bytes)
    with open(clean_path, "wb") as f:
        f.write(clean_bytes)
    elapsed = time.time() - t0
    print(f"  [OK] {slug} ({w}×{h}) — wm={len(wm_bytes):,}B clean={len(clean_bytes):,}B — {elapsed:.1f}s", flush=True)


def generate_bundle_items(slug: str, eq_type: str, params: dict, contents_json: str, force: bool = False):
    """Generate bundle item preview images."""
    items = json.loads(contents_json or "[]")
    w, h = _preview_dims(eq_type)
    for i in range(len(items)):
        out_path = os.path.join(OUTPUT_DIR, f"{slug}_{i}.jpg")
        clean_path = os.path.join(OUTPUT_DIR, f"{slug}_{i}_clean.jpg")
        if not force and os.path.exists(out_path) and os.path.exists(clean_path):
            continue

        varied, eq_override = _vary_params(params, i, eq_type)
        render_type = eq_override if eq_override else eq_type
        t0 = time.time()
        wm_bytes, clean_bytes = _render_and_watermark(render_type, varied, w, h, hq=False)
        with open(out_path, "wb") as f:
            f.write(wm_bytes)
        with open(clean_path, "wb") as f:
            f.write(clean_bytes)
        elapsed = time.time() - t0
        print(f"  [OK] {slug}[{i}] ({w}×{h}) — wm={len(wm_bytes):,}B clean={len(clean_bytes):,}B — {elapsed:.1f}s", flush=True)


def main():
    force = "--force" in sys.argv
    slug_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--slug="):
            slug_filter = arg.split("=", 1)[1]

    db = SessionLocal()
    try:
        query = db.query(DigitalProduct).filter(DigitalProduct.active == True)
        if slug_filter:
            query = query.filter(DigitalProduct.slug == slug_filter)
        products = query.all()
    finally:
        db.close()

    print(f"Pre-generating previews for {len(products)} products...", flush=True)
    print(f"Base resolution: {_BASE_PX}px (per-equation aspect ratios)", flush=True)
    print(f"Output: {OUTPUT_DIR}", flush=True)
    print()

    # Main previews — one bad equation_type must not kill the whole run
    # (e.g. "particle" packs are rendered by the app through a different path).
    for p in products:
        try:
            params = json.loads(p.params_json) if getattr(p, 'params_json', None) else {}
            generate_preview(p.slug, p.equation_type, params, force=force)
        except Exception as e:
            print(f"  [SKIP] {p.slug}: {e}", flush=True)

    print()
    print("Bundle item previews...", flush=True)

    # Bundle item previews
    for p in products:
        try:
            params = json.loads(p.params_json) if getattr(p, 'params_json', None) else {}
            generate_bundle_items(p.slug, p.equation_type, params, p.contents_json, force=force)
        except Exception as e:
            print(f"  [SKIP] {p.slug} items: {e}", flush=True)

    # Also generate for legacy Product model (collection cards)
    db = SessionLocal()
    try:
        legacy = db.query(Product).all()
    finally:
        db.close()

    for p in legacy:
        try:
            params = json.loads(p.params_json) if p.params_json else {}
            generate_preview(p.slug, p.equation_type, params, force=force)
        except Exception as e:
            print(f"  [SKIP] {p.slug}: {e}", flush=True)

    print()
    total = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".jpg")])
    print(f"Done. {total} preview files in {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
