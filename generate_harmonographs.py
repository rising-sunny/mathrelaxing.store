import os
import numpy as np
import random
import math

import generate_one_per_family as G

def generate_harmonograph(seed, t_max=150, num_points=25000):
    np.random.seed(seed)
    random.seed(seed)
    
    # 4 pendulum harmonograph parameters
    # Pick integer frequencies between 1 and 10 to create stable resonant figures
    f1 = np.random.randint(1, 6)
    f2 = np.random.randint(1, 6)
    f3 = np.random.randint(1, 6)
    f4 = np.random.randint(1, 6)
    
    # Random phases
    p1, p2, p3, p4 = np.random.uniform(0, 2*math.pi, 4)
    
    # Damping factors: very small so it creates dense line patterns
    d1 = np.random.uniform(0.001, 0.005)
    d2 = np.random.uniform(0.001, 0.005)
    d3 = np.random.uniform(0.001, 0.005)
    d4 = np.random.uniform(0.001, 0.005)
    
    # Amplitudes
    a1, a2, a3, a4 = np.random.uniform(1.0, 2.5, 4)
    
    t = np.linspace(0, t_max, num_points)
    x = a1 * np.sin(f1 * t + p1) * np.exp(-d1 * t) + a2 * np.sin(f2 * t + p2) * np.exp(-d2 * t)
    y = a3 * np.sin(f3 * t + p3) * np.exp(-d3 * t) + a4 * np.sin(f4 * t + p4) * np.exp(-d4 * t)
    
    pts = np.column_stack([x, y])
    return [pts]

if __name__ == "__main__":
    OUT_DIR = "/var/www/mathrelaxing.store/static/downloads/harmonographs_book"
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # Generate 50 unique harmonographs
    # We use explicit seeds to keep it reproducible
    seeds = [1000 + i for i in range(50)]
    
    for i, s in enumerate(seeds, 1):
        curves = generate_harmonograph(s)
        print(f"Rendering Harmonograph page {i:02d} (seed={s})...")
        G.render_full_page(curves, "Harmonographs", f"{i:02d}", OUT_DIR)
        
    print(f"\nDone! Test pages saved to {OUT_DIR}")
