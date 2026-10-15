"""Dos láminas de referencias reales contra el MP4 final, sin editar la fuente.

Desde IVAN, después del render verificado:
python3 -B ejemplos/demo_produccion/comparar_referencias.py \
    --mp4-sha <SHA_FINAL> --composition-sha <SHA_FUENTE>

Las capturas nativas van a .estado/tmp; únicamente las dos láminas y su JSON
de procedencia quedan en integracion/evidencia_qa/comparaciones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
FOLDER = PROJECT / 'integracion'
FFMPEG = '/usr/bin/ffmpeg'
REFERENCES = {
    'YO': ('recursos/A3_YO.mp4', 'e1b65353565fa839e17a35a05b72755524c2551a88afdca25c14431757eac68f'),
    'CLONE': ('recursos/B2_CLONE.mp4', '7ef3e586a481156e8b88250c8ccfb1633834f679935554c46c10570ae78b2dc8'),
}


def owned(path):
    path = Path(path)
    result = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if ROOT.name != 'IVAN' or not result.is_relative_to(ROOT):
        raise ValueError('La comparación debe permanecer en IVAN')
    return result


def digest(path):
    return hashlib.sha256(owned(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(owned(path).read_text())


def relative(path):
    return str(owned(path).relative_to(ROOT))


def frame_capture(source, source_sha, frame):
    """Select por índice n, sin aproximación mediante seek temporal."""
    cache = ROOT / '.estado/tmp' / ('produccion_' + PROJECT.name) / 'comparaciones' / source_sha
    cache.mkdir(parents=True, exist_ok=True)
    image = cache / ('frame_%06d.png' % frame)
    proof = image.with_suffix('.json')
    expected = {'source': relative(source), 'source_sha256': source_sha, 'frame': frame, 'fps': 30}
    if image.is_file() and proof.is_file():
        previous = load(proof)
        if all(previous.get(k) == v for k, v in expected.items()) and previous.get('png_sha256') == digest(image):
            return image
    subprocess.run([
        FFMPEG, '-v', 'error', '-threads', '1', '-i', str(owned(source)),
        '-vf', 'select=eq(n\\,%d)' % frame, '-frames:v', '1', '-vsync', '0', '-y', str(image),
    ], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    expected['png_sha256'] = digest(image)
    proof.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n')
    return image


def wrap(draw, text, font, width):
    result, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if line and draw.textlength(candidate, font=font) > width:
            result.append(line)
            line = word
        else:
            line = candidate
    if line:
        result.append(line)
    return result


def plate(target, title, panels, notes):
    """Muestra todos los encuadres completos, cada uno a 360×640."""
    margin, gap, panel_width, header_height, picture_y = 20, 16, 360, 94, 116
    width = margin * 2 + panel_width * len(panels) + gap * (len(panels) - 1)
    fonts = ROOT / '.agents/skills/hyperframes-creative/frame-presets/code-editorial/fonts'
    bold = ImageFont.truetype(str(fonts / 'Inter-700.woff2'), 23)
    regular = ImageFont.truetype(str(fonts / 'Inter-400.woff2'), 16)
    small = ImageFont.truetype(str(fonts / 'Inter-400.woff2'), 14)
    probe = Image.new('RGB', (width, 100))
    draw = ImageDraw.Draw(probe)
    footer_lines = [line for note in notes for line in wrap(draw, note, regular, width - margin * 2)]
    height = picture_y + 640 + 32 + len(footer_lines) * 23 + 20
    canvas = Image.new('RGB', (width, height), '#F4F4F5')
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 18), title, font=bold, fill='#171719')
    for index, panel in enumerate(panels):
        x = margin + index * (panel_width + gap)
        draw.text((x, 57), panel['title'], font=regular, fill='#171719')
        draw.text((x, 80), panel['label'], font=small, fill='#505055')
        picture = Image.open(panel['path']).convert('RGB')
        if abs(picture.width / picture.height - 9 / 16) > 1e-6:
            raise ValueError('La captura no conserva el encuadre 9:16')
        picture = picture.resize((360, 640), Image.Resampling.LANCZOS)
        canvas.paste(picture, (x, picture_y))
        draw.rectangle((x - 1, picture_y - 1, x + 360, picture_y + 640), outline='#C9C9CD')
    y = picture_y + 660
    for line in footer_lines:
        draw.text((margin, y), line, font=regular, fill='#34343A')
        y += 23
    canvas.save(target)


def generate(mp4_sha, composition_sha):
    sys.path.insert(0, str(ROOT / 'sistema/clone'))
    import engine as e
    project = load(FOLDER / 'proyecto.json')
    mp4 = FOLDER / project['output_name']
    receipt = load(FOLDER / 'integration_qc.json')
    if digest(mp4) != mp4_sha or receipt.get('final_mp4_sha256') != mp4_sha:
        raise ValueError('El MP4 no corresponde al export final solicitado')
    if receipt.get('source_sha256') != composition_sha or e.source_fingerprint(FOLDER)['sha256'] != composition_sha:
        raise ValueError('La composición no corresponde al export verificado')
    if receipt.get('decoded_all_frames') is not True or receipt.get('frames') != project['frames']:
        raise ValueError('Falta el recibo de todos los fotogramas del render')
    if project['frames'] != 1533 or project['fps'] != 30:
        raise ValueError('Este diagnóstico corresponde al crudo completo de 51,1 segundos')
    reference_paths = {}
    for name, (path, sha) in REFERENCES.items():
        if digest(path) != sha:
            raise ValueError('La referencia original cambió: ' + name)
        reference_paths[name] = owned(path)
    out = FOLDER / 'evidencia_qa/comparaciones'
    out.mkdir(parents=True, exist_ok=True)
    captures = {
        'yo_split': frame_capture(reference_paths['YO'], REFERENCES['YO'][1], 24),
        'yo_caption': frame_capture(reference_paths['YO'], REFERENCES['YO'][1], 72),
        'new_split': frame_capture(mp4, mp4_sha, 1110),
        'clone_spotlight': frame_capture(reference_paths['CLONE'], REFERENCES['CLONE'][1], 630),
        'new_spotlight': frame_capture(mp4, mp4_sha, 774),
        'clone_terminal': frame_capture(reference_paths['CLONE'], REFERENCES['CLONE'][1], 1134),
        'new_terminal': frame_capture(mp4, mp4_sha, 882),
    }
    yo_file, clone_file = out / 'comparacion_YO.png', out / 'comparacion_CLONE.png'
    plate(yo_file, 'YO: composición y subtítulo frente al export real', [
        {'title': 'YO · split de referencia', 'label': 'F24 · 0,800 s · encuadre completo', 'path': captures['yo_split']},
        {'title': 'YO · subtítulo de referencia', 'label': 'F72 · 2,400 s · cámara completa', 'path': captures['yo_caption']},
        {'title': 'Reel nuevo · split y subtítulo', 'label': 'F1110 · 37,000 s · export H.264', 'path': captures['new_split']},
    ], [
        'Los tres encuadres completos se muestran a 360×640. El split YO de 0,8 s tiene el titular arriba; el subtítulo bajo barbilla se observa por separado en 2,4 s.',
        'Son grabaciones distintas: se conserva cada fondo original. La lámina permite revisar composición, escala y legibilidad; no identifica parámetros CSS exactos de la referencia ni aprueba estética.',
    ])
    plate(clone_file, 'CLONE: spotlight y terminal frente a instancias nuevas', [
        {'title': 'CLONE · spotlight', 'label': 'F630 · 21,000 s', 'path': captures['clone_spotlight']},
        {'title': 'Reel nuevo · spotlight', 'label': 'F774 · 25,800 s · export H.264', 'path': captures['new_spotlight']},
        {'title': 'CLONE · terminal', 'label': 'F1134 · 37,800 s', 'path': captures['clone_terminal']},
        {'title': 'Reel nuevo · terminal', 'label': 'F882 · 29,400 s · export H.264', 'path': captures['new_terminal']},
    ], [
        'Comparación del lenguaje gráfico: foco, sprite, píldora, título; panel de terminal, comando, progreso y activación de roles. Los textos, funciones y número de roles difieren.',
        'CLONE es referencia exclusiva de motion; su presentador no define la identidad del nuevo reel. Las fuentes internas son aproximaciones documentadas. Los fotogramas no acreditan por sí solos ritmo ni continuidad.',
    ])
    comparisons = []
    for name, path, ref_frames, new_frames in [
        ('YO', yo_file, [24, 72], [1110]),
        ('CLONE', clone_file, [630, 1134], [774, 882]),
    ]:
        comparisons.append({
            'reference': name, 'comparison': relative(path), 'comparison_sha256': digest(path),
            'source': REFERENCES[name][0], 'source_sha256': REFERENCES[name][1],
            'source_frames': [{'frame': n, 'time': n / 30} for n in ref_frames],
            'export_frames': [{'frame': n, 'time': n / 30} for n in new_frames],
            'export_path': relative(mp4), 'mp4_sha256': mp4_sha, 'composition_sha256': composition_sha,
            'method': 'Selección exacta por índice n del MP4; encuadres completos redimensionados a 360×640, sin blur, reencuadre ni recolor.',
            'aesthetic_approval': False,
        })
    metadata = {
        'schema_version': 1, 'scope': 'real_reference_frames_against_encoded_final_export',
        'mp4_sha256': mp4_sha, 'composition_sha256': composition_sha,
        'reference_comparisons': comparisons, 'aesthetic_approval': False,
        'limits': ['Sin correlación HTML–MP4 como métrica de similitud estética.', 'Las láminas son estados concretos; el ritmo requiere revisar la secuencia.', 'La aprobación estética permanece pendiente del usuario.'],
    }
    (out / 'referencias_comparadas.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mp4-sha', required=True)
    parser.add_argument('--composition-sha', required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.mp4_sha, args.composition_sha), ensure_ascii=False, indent=2))
