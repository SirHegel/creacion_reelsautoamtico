#!/usr/bin/env python3
"""Inspección independiente del MP4: continuidad y rostro auténtico en sus límites.

No aprueba dirección de arte. Compara píxeles decodificados con el crudo,
no una captura de la implementación HTML. Todas las salidas son privadas.
"""
import argparse
import json
import subprocess
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw
import workflow as w


def decode(path):
    data = subprocess.check_output([
        '/usr/bin/ffmpeg', '-v', 'error', '-threads', '2', '-i',
        str(w.inside(path)), '-vf', 'scale=180:320', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-'])
    return np.frombuffer(data, dtype=np.uint8).reshape(-1, 320, 180, 3)


def ncc(a, b):
    x = a.astype(np.float32).ravel()
    y = b.astype(np.float32).ravel()
    x -= x.mean()
    y -= y.mean()
    norm = float(np.sqrt(np.dot(x, x) * np.dot(y, y)))
    return float(np.dot(x, y) / norm) if norm > 1e-6 else 0.0


def face_at(frames, t):
    valid = [f for f in frames if f.get('bbox') and f.get('smooth_chin')]
    return min(valid, key=lambda f: abs(f['t'] - t))


def face_match(render, original, faces, t, pose):
    """Ajustar ubicación por búsqueda; no depender de la posición CSS exacta."""
    f = face_at(faces, t)
    x0, y0, x1, y1 = f['bbox']
    left, top, right, bottom = [round(v * s) for v, s in zip(
        (x0, y0, x1, y1), (180, 320, 180, 320))]
    factor = float(pose.get('escala_split', 1.0)) if pose['modo'] == 'split' else 1.0
    size = (max(8, round((right-left)*factor)), max(8, round((bottom-top)*factor)))
    chin_x, chin_y = f['smooth_chin']
    expected_x = round(90 + (x0 - chin_x) * 180 * factor)
    expected_y = round(float(pose.get('barbilla_destino_px', chin_y*1920))/6 +
                       (y0-chin_y)*320*factor)
    if pose['modo'] != 'split':
        expected_x, expected_y = left, top
    best = (-1.0, None, None)
    source_center = min(len(original)-1, round(t*30))
    # Captura/decodificación pueden escoger el frame vecino en fuentes VFR.
    for src_frame in range(max(0, source_center-1), min(len(original), source_center+2)):
        native = original[src_frame, top:bottom, left:right]
        if not native.size:
            continue
        template = np.asarray(Image.fromarray(native).resize(size, Image.Resampling.BICUBIC))
        width, height = size
        for y in range(max(0, expected_y-7), min(320-height+1, expected_y+8)):
            for x in range(max(0, expected_x-7), min(180-width+1, expected_x+8)):
                value = ncc(render[y:y+height, x:x+width], template)
                if value > best[0]:
                    best = value, (x, y, width, height), src_frame
    return {'correlacion_rostro_crudo':round(best[0], 5),
            'rectangulo_render_180x320':best[1], 'frame_fuente':best[2]}


def run(project_id):
    folder = 'proyectos/' + project_id
    p = w.read_json(folder + '/proyecto.json')
    movie = folder + '/' + p['muestra_nombre']
    sha_initial = w.digest(movie)
    rendered = decode(movie)
    original = decode(p['original']['archivo'])
    faces = w.read_json(folder + '/rostro.json')['detecciones']
    measurements, boundaries = [], set()
    for pose in p.get('presentador', []):
        first = int(np.ceil(pose['inicio'] * 30 - 1e-7))
        end = int(np.ceil(pose['fin'] * 30 - 1e-7))
        for i in range(max(0, first-2), min(len(rendered), end+2)):
            t = i/30
            measurements.append({'frame':i, 'tiempo_s':t,
                                 'visible_previsto':first <= i < end,
                                 **face_match(rendered[i], original, faces, t, pose)})
        boundaries.update(range(max(0, first-2), min(len(rendered), first+4)))
        boundaries.update(range(max(0, end-4), min(len(rendered), end+3)))
    mad = np.mean(np.abs(rendered[1:].astype(float)-rendered[:-1].astype(float)), axis=(1,2,3))
    flicker = []
    for i in range(1, len(rendered)-1):
        outside = np.mean(np.abs(rendered[i-1].astype(float)-rendered[i+1].astype(float)))
        if mad[i-1] > 14 and mad[i] > 14 and outside < 5:
            flicker.append({'frame':i, 'tiempo_s':i/30,
                            'entrada_mad':float(mad[i-1]), 'salida_mad':float(mad[i]),
                            'vecinos_mad':float(outside)})
    band_candidates=[]
    for i, im in enumerate(rendered):
        lower = im[-16:, 15:-15].astype(float)
        # Una banda plana, también gris, merece inspección. Fondos de diseño
        # uniformes pueden producir candidatos legítimos; no son errores solos.
        if np.max(np.std(lower.reshape(-1,3), axis=0)) < 2:
            band_candidates.append(i)
    cols = 5
    rows = int(np.ceil(len(boundaries)/cols))
    canvas = Image.new('RGB', (cols*180, rows*343), '#15191e')
    draw = ImageDraw.Draw(canvas)
    for n, i in enumerate(sorted(boundaries)):
        x, y = n%cols*180, n//cols*343
        canvas.paste(Image.fromarray(rendered[i]), (x,y))
        draw.text((x+5,y+322), f'f{i} {i/30:.4f}s', fill='white')
    sheet = '.estado/tmp/estabilidad_v5_limites.jpg'
    canvas.save(w.inside(sheet), quality=95)
    visible = [m for m in measurements if m['visible_previsto']]
    missing = [m for m in visible if m['correlacion_rostro_crudo'] < .80]
    unexpectedly_visible = [m for m in measurements if not m['visible_previsto'] and
                            m['correlacion_rostro_crudo'] > .85]
    sha_final = w.digest(movie)
    result={'archivo':movie, 'sha256':sha_final, 'sha256_inicio':sha_initial,
            'fecha':w.utc(),
            'frames_decodificados':len(rendered), 'rostro_visible':visible,
            'rostro_insuficiente_o_parcial':missing,
            'rostro_fuera_de_ventana':unexpectedly_visible,
            'parpadeo_aba_candidatos':flicker,
            'frames_fondo_inferior_uniforme_candidatos':band_candidates,
            'evidencia_limites':sheet,
            'comprobaciones':{'mp4_inmutable_durante_inspeccion':sha_initial==sha_final,
                             '300_frames':len(rendered)==300,
                             'rostro_autentico_completo_en_frames_visibles':bool(visible) and not missing,
                             'rostro_desaparece_en_limites':not unexpectedly_visible,
                             'sin_candidato_aba':not flicker},
            'limites':'Los candidatos de fondo uniforme y ABA requieren revisión visual. '
                      'La correlación verifica el rostro con el crudo; no certifica '
                      'identidad editorial, sombra o pertinencia de recursos.'}
    out = '.estado/tmp/estabilidad_v5.json'
    w.write_json(out, result)
    print(json.dumps({'reporte':out, 'sha256':result['sha256'],
                      'comprobaciones':result['comprobaciones'],
                      'min_correlacion_rostro':min((m['correlacion_rostro_crudo'] for m in visible),default=None),
                      'candidatos_parciales':missing,
                      'candidatos_aba':flicker}, ensure_ascii=False, indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('project_id')
    run(parser.parse_args().project_id)
