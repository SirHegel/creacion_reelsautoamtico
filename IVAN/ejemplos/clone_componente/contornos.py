"""Contornos vectoriales medidos en el fotograma; sin instalar bibliotecas.

Marching squares con interpolación subpíxel. No inserta un recorte del
fotograma como sustituto de la composición: devuelve paths SVG editables.
"""
import math
import numpy as np


def contours(field, threshold=.5, min_area=1.5):
    field = np.pad(np.asarray(field, dtype=float), 1)
    # Aristas: arriba, derecha, abajo, izquierda. Casos diagonales separados.
    pairs = {1:[(3,0)],2:[(0,1)],3:[(3,1)],4:[(1,2)],
             5:[(3,0),(1,2)],6:[(0,2)],7:[(3,2)],8:[(2,3)],
             9:[(0,2)],10:[(0,1),(2,3)],11:[(1,2)],12:[(1,3)],
             13:[(0,1)],14:[(3,0)]}
    adjacency = {}
    active=field>=threshold
    codes=(active[:-1,:-1].astype('uint8')+active[:-1,1:].astype('uint8')*2+
           active[1:,1:].astype('uint8')*4+active[1:,:-1].astype('uint8')*8)
    for y,x in np.argwhere((codes!=0)&(codes!=15)):
            values = [field[y,x],field[y,x+1],field[y+1,x+1],field[y+1,x]]
            code = sum((v >= threshold) << i for i,v in enumerate(values))
            if code not in pairs:
                continue
            coords = [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
            def point(edge):
                a,b = edge,(edge+1)%4
                t = (threshold-values[a])/(values[b]-values[a])
                return tuple(round(coords[a][i]+t*(coords[b][i]-coords[a][i])-1,5) for i in (0,1))
            for ea,eb in pairs[code]:
                a,b = point(ea),point(eb)
                adjacency.setdefault(a,[]).append(b)
                adjacency.setdefault(b,[]).append(a)
    paths = []
    visited = set()
    for start in adjacency:
        if start in visited:
            continue
        path = [start];previous=None;current=start
        while True:
            visited.add(current)
            candidates=[p for p in adjacency[current] if p != previous]
            if not candidates:
                break
            nxt=candidates[0]
            if nxt == start:
                break
            if nxt in visited:
                break
            path.append(nxt);previous,current=current,nxt
        area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(path,path[1:]+path[:1])))/2
        if area >= min_area:
            paths.append(path)
    return paths


def simplify(points, tolerance=.16):
    """Ramer–Douglas–Peucker; conserva curvas y contraformas pequeñas."""
    if len(points)<3:
        return points
    a,b=points[0],points[-1];dx,dy=b[0]-a[0],b[1]-a[1]
    length=math.hypot(dx,dy)
    distances=[abs(dx*(a[1]-p[1])-(a[0]-p[0])*dy)/length if length else math.dist(a,p) for p in points[1:-1]]
    distance=max(distances,default=0)
    if distance <= tolerance:
        return [a,b]
    split=distances.index(distance)+1
    return simplify(points[:split+1],tolerance)[:-1]+simplify(points[split:],tolerance)


def svg_path(field, origin, transform=lambda x,y:(x,y),threshold=.5,scale=1,tolerance=.16,pixel_center=False):
    output=[]
    for ring in contours(field,threshold=threshold,min_area=1.5*scale*scale):
        halfway=len(ring)//2
        ring=simplify(ring[:halfway+1],tolerance*scale)[:-1]+simplify(ring[halfway:]+ring[:1],tolerance*scale)[:-1]
        # Al reescalar una imagen, su primer centro queda en(0.5/scale-0.5).
        # SVG sitúa el centro del primer píxel en0.5: conservar ese desfase.
        offset=.5/scale if pixel_center else 0
        points=[transform(x/scale+origin[0]+offset,y/scale+origin[1]+offset) for x,y in ring]
        output.append('M'+'L'.join(f'{x:.2f} {y:.2f}' for x,y in points)+'Z')
    return ''.join(output)


def svg_coverage(field, origin, *, transform=lambda x,y:(x,y),fill='#fff',scale=4,tolerance=.08):
    """Capas vectoriales de cobertura: conserva los trazos subpíxel.

    Un único umbral engorda trazos finos o los rompe. Estas curvas de nivel
    aproximan la opacidad observada sin insertar una captura del texto.
    """
    paths=[]
    # Centro sólido y dos bordes de cobertura. Evita convertir el ruido de
    # compresión del interior de las letras en pequeñas islas transparentes.
    for threshold,opacity in [(.10,.12),(.30,.40),(.53,1.)]:
        d=svg_path(field,origin,transform=transform,threshold=threshold,
                   scale=scale,tolerance=tolerance,pixel_center=True)
        if d:
            paths.append(f'<path d="{d}" fill="{fill}" fill-opacity="{opacity:.5f}" fill-rule="evenodd"/>')
    return ''.join(paths)
