import numpy as np

def triangulate_grid(verts, u_steps, v_steps, closed_u=False, closed_v=False):
    faces = []
    for i in range(u_steps - 1):
        for j in range(v_steps - 1):
            p1 = i * v_steps + j
            p2 = i * v_steps + (j + 1)
            p3 = (i + 1) * v_steps + j
            p4 = (i + 1) * v_steps + (j + 1)
            faces.append([p1, p3, p2])
            faces.append([p2, p3, p4])
            
    if closed_u:
        for j in range(v_steps - 1):
            p1 = (u_steps - 1) * v_steps + j
            p2 = (u_steps - 1) * v_steps + (j + 1)
            p3 = 0 * v_steps + j
            p4 = 0 * v_steps + (j + 1)
            faces.append([p1, p3, p2])
            faces.append([p2, p3, p4])
            
    if closed_v:
        for i in range(u_steps - 1):
            p1 = i * v_steps + (v_steps - 1)
            p2 = i * v_steps + 0
            p3 = (i + 1) * v_steps + (v_steps - 1)
            p4 = (i + 1) * v_steps + 0
            faces.append([p1, p3, p2])
            faces.append([p2, p3, p4])
            
    if closed_u and closed_v:
        p1 = (u_steps - 1) * v_steps + (v_steps - 1)
        p2 = (u_steps - 1) * v_steps + 0
        p3 = 0 * v_steps + (v_steps - 1)
        p4 = 0 * v_steps + 0
        faces.append([p1, p3, p2])
        faces.append([p2, p3, p4])

    verts_flat = verts.reshape(-1, 3)
    return verts_flat, faces

def gen_torus(R=1.0, r=0.4, u_steps=20, v_steps=12, twists=0):
    u = np.linspace(0, 2*np.pi, u_steps)
    v = np.linspace(0, 2*np.pi, v_steps)
    U, V = np.meshgrid(u, v, indexing='ij')
    V += twists * U
    X = (R + r * np.cos(V)) * np.cos(U)
    Y = (R + r * np.cos(V)) * np.sin(U)
    Z = r * np.sin(V)
    verts = np.stack((X, Y, Z), axis=-1)
    return triangulate_grid(verts, u_steps, v_steps, closed_u=True, closed_v=True)

def gen_mobius(R=1.0, w=0.4, u_steps=30, v_steps=6, twists=1):
    u = np.linspace(0, 2*np.pi, u_steps)
    v = np.linspace(-w, w, v_steps)
    U, V = np.meshgrid(u, v, indexing='ij')
    half_u = (twists / 2.0) * U
    X = (R + V * np.cos(half_u)) * np.cos(U)
    Y = (R + V * np.cos(half_u)) * np.sin(U)
    Z = V * np.sin(half_u)
    verts = np.stack((X, Y, Z), axis=-1)
    return triangulate_grid(verts, u_steps, v_steps, closed_u=True, closed_v=False)

def gen_helicoid(R=1.0, h=0.5, twists=1.0, u_steps=30, v_steps=10):
    u = np.linspace(0, 2*np.pi * twists, u_steps)
    v = np.linspace(0.1, R, v_steps)
    U, V = np.meshgrid(u, v, indexing='ij')
    X = V * np.cos(U)
    Y = V * np.sin(U)
    Z = h * U
    verts = np.stack((X, Y, Z), axis=-1)
    return triangulate_grid(verts, u_steps, v_steps, closed_u=False, closed_v=False)

def gen_seashell(u_steps=40, v_steps=15):
    u = np.linspace(0, 6*np.pi, u_steps)
    v = np.linspace(0, 2*np.pi, v_steps)
    U, V = np.meshgrid(u, v, indexing='ij')
    X = 2 * (1 - np.exp(U/(6*np.pi))) * np.cos(U) * np.cos(V/2)**2
    Y = 2 * (-1 + np.exp(U/(6*np.pi))) * np.sin(U) * np.cos(V/2)**2
    Z = 1 - np.exp(U/(3*np.pi)) - np.sin(V) + np.exp(U/(6*np.pi)) * np.sin(V)
    verts = np.stack((X, Y, Z), axis=-1)
    return triangulate_grid(verts, u_steps, v_steps, closed_u=False, closed_v=True)

def gen_sphere_bumpy(u_steps=20, v_steps=20, bumps=4, bump_depth=0.2):
    u = np.linspace(0, 2*np.pi, u_steps)
    v = np.linspace(0, np.pi, v_steps)
    U, V = np.meshgrid(u, v, indexing='ij')
    R = 1.0 + bump_depth * np.sin(bumps * U) * np.sin(bumps * V)
    X = R * np.sin(V) * np.cos(U)
    Y = R * np.sin(V) * np.sin(U)
    Z = R * np.cos(V)
    verts = np.stack((X, Y, Z), axis=-1)
    return triangulate_grid(verts, u_steps, v_steps, closed_u=True, closed_v=False)

def add_noise(verts, strength=0.05, seed=42):
    np.random.seed(seed)
    return verts + np.random.normal(0, strength, verts.shape)

def get_mesh(idx):
    """Returns (verts, faces, title) for idx from 0 to 49"""
    if 0 <= idx < 10:
        # Toroids
        i = idx
        R = 1.0 + (i % 3) * 0.2
        r = 0.3 + (i % 2) * 0.1
        u = 12 + i
        v = 6 + (i % 3)
        verts, faces = gen_torus(R=R, r=r, u_steps=u, v_steps=v)
        verts = add_noise(verts, 0.05, seed=idx)
        return verts, faces, f"Torus Topology {i+1}"
        
    elif 10 <= idx < 20:
        # Mobius Strips
        i = idx - 10
        twists = 1 + (i % 3)
        u = 15 + i
        v = 4 + (i % 3)
        verts, faces = gen_mobius(u_steps=u, v_steps=v, twists=twists)
        verts = add_noise(verts, 0.05, seed=idx)
        return verts, faces, f"Möbius Band {i+1}"
        
    elif 20 <= idx < 30:
        # Helicoids
        i = idx - 20
        twists = 1.0 + (i * 0.25)
        u = 16 + i
        v = 6 + (i % 3)
        verts, faces = gen_helicoid(twists=twists, u_steps=u, v_steps=v)
        verts = add_noise(verts, 0.05, seed=idx)
        return verts, faces, f"Helicoid Surface {i+1}"
        
    elif 30 <= idx < 40:
        # Seashells
        i = idx - 30
        u = 16 + i
        v = 6 + (i % 3)
        verts, faces = gen_seashell(u_steps=u, v_steps=v)
        verts = add_noise(verts, 0.05, seed=idx)
        return verts, faces, f"Golden Spiral {i+1}"
        
    elif 40 <= idx < 50:
        # Bumpy Spheres
        i = idx - 40
        bumps = 2 + (i%4)
        depth = 0.1 + (i*0.02)
        u = 12 + i
        v = 10 + (i % 3)
        verts, faces = gen_sphere_bumpy(bumps=bumps, bump_depth=depth, u_steps=u, v_steps=v)
        verts = add_noise(verts, 0.03, seed=idx)
        return verts, faces, f"Geometric Gem {i+1}"
    
    else:
        # Fallback to guaranteed well-behaved geometry (Spheres) to fill any gaps left by rejected models
        i = idx % 10
        variation = idx // 10
        bumps = 3 + (i%3)
        depth = 0.15
        u = 12 + i + variation
        v = 10 + (i%3) + variation
        verts, faces = gen_sphere_bumpy(bumps=bumps, bump_depth=depth, u_steps=u, v_steps=v)
        verts = add_noise(verts, 0.03, seed=idx)
        return verts, faces, f"Sacred Sphere {idx+1}"
