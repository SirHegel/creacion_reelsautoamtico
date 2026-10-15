"""Mezcla original + FX verificados: sin retime, EQ, compresión ni gain en voz.

Ejecutar desde IVAN con --plan audio_plan.json tras vincular cues al storyboard.
No modifica proyecto.json. Imprime el contrato audio_mix para el integrador.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
FFMPEG = '/usr/bin/ffmpeg'
FFPROBE = '/usr/bin/ffprobe'


def inside(path):
    p = Path(path)
    p = (ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    if ROOT.name != 'IVAN' or not p.is_relative_to(ROOT):
        raise ValueError('Todas las entradas/salidas deben permanecer en IVAN')
    return p


def digest(path):
    return hashlib.sha256(inside(path).read_bytes()).hexdigest()


def command(args):
    return subprocess.check_output(args, cwd=ROOT, stderr=subprocess.PIPE)


def probe(path):
    return json.loads(command([FFPROBE, '-v', 'error', '-select_streams', 'a:0',
                               '-show_streams', '-of', 'json', str(path)]))['streams'][0]


def decode(path, sr=None, channels=None):
    args = [FFMPEG, '-v', 'error', '-i', str(path), '-map', '0:a:0']
    if sr is not None:
        args += ['-ar', str(sr)]
    if channels is not None:
        args += ['-ac', str(channels)]
    raw = command(args + ['-f', 'f32le', '-acodec', 'pcm_f32le', '-'])
    return raw


def mix(plan_path):
    plan_path = inside(plan_path)
    project = plan_path.parent
    if not project.is_relative_to(ROOT / 'proyectos') or len(project.relative_to(ROOT).parts) != 2:
        raise ValueError('El plan debe pertenecer a la raíz de un proyecto dentro de IVAN/proyectos')
    plan = json.loads(plan_path.read_text())
    if plan.get('status') != 'cues_verified_against_storyboard':
        raise ValueError('Los cues deben verificarse contra acciones reales del storyboard antes de mezclar')
    if plan.get('music', {}).get('used'):
        raise ValueError('Este encargo excluye música: no existe licencia comprobada en la biblioteca')
    source = inside(plan['voice']['path'])
    if digest(source) != plan['voice']['sha256']:
        raise ValueError('El original no corresponde a la narración verificada')
    if plan['voice'].get('gain_db', 0) != 0 or plan['voice'].get('speed', 1) != 1:
        raise ValueError('La voz debe tener gain unity y velocidad original')
    meta = probe(source)
    sr, channels = int(meta['sample_rate']), int(meta['channels'])
    voice_raw = decode(source)
    voice = np.frombuffer(voice_raw, dtype='<f4').reshape(-1, channels)
    original_hash = hashlib.sha256(voice_raw).hexdigest()
    # La extracción de paquetes también identifica el AAC original. El archivo
    # mezclado tendrá nuevos paquetes; este hash no se atribuye al mix final.
    packet_hash = command([FFMPEG, '-v', 'error', '-i', str(source), '-map', '0:a:0',
                           '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).decode().strip().split('=', 1)[1]
    fx = np.zeros_like(voice, dtype='f8')
    executed = []
    for cue in plan.get('cues', []):
        if not cue.get('enabled', True):
            continue
        if not cue.get('visual_action') or not cue.get('reason'):
            raise ValueError('Cada efecto debe registrar la acción visual real y su intención')
        item = plan['resources'][cue['resource_id']]
        if item.get('use_decision') != 'client_resource_private_review':
            raise ValueError('Recurso sonoro sin decisión de uso registrada')
        path = inside(item['path'])
        if digest(path) != item['sha256']:
            raise ValueError('Ha cambiado un recurso sonoro')
        sound = np.frombuffer(decode(path, sr, channels), dtype='<f4').reshape(-1, channels).astype('f8')
        start = round((float(cue['impact_time']) - float(item['rms_peak_10ms_time'])) * sr)
        offset = max(0, -start)
        start = max(0, start)
        # Fades cortos sólo sobre el FX; jamás sobre el stem original.
        fi = min(len(sound), round(float(cue.get('fade_in', .008)) * sr))
        fo = min(len(sound), round(float(cue.get('fade_out', .04)) * sr))
        if fi:
            sound[:fi] *= np.linspace(0, 1, fi)[:, None]
        if fo:
            sound[-fo:] *= np.linspace(1, 0, fo)[:, None]
        length = min(len(sound) - offset, len(voice) - start)
        if length <= 0:
            raise ValueError('Cue fuera de la duración original')
        gain = 10 ** (float(cue.get('gain_db', -22)) / 20)
        fx[start:start + length] += sound[offset:offset + length] * gain
        executed.append({**cue, 'path': str(path.relative_to(ROOT)), 'sha256': item['sha256'],
                         'start_sample': start, 'source_offset_sample': offset,
                         'mixed_samples': length, 'requested_gain_db': float(cue.get('gain_db', -22)),
                         'fade_applied_to_fx_only': True})
    if not executed:
        raise ValueError('No se han especificado efectos verificados para mezclar')
    ceiling = 10 ** (-1 / 20)
    if np.max(np.abs(voice)) >= ceiling:
        raise ValueError('La fuente supera el margen reservado: no se modifica la voz automáticamente')
    # Reservar margen atenuando únicamente el bus de efectos, sin limiter global.
    extra_db = 0.0
    while True:
        candidate = voice.astype('f8') + fx * 10 ** (extra_db / 20)
        if np.max(np.abs(candidate)) <= ceiling:
            break
        extra_db -= 3
        if extra_db < -60:
            raise ValueError('No se obtiene headroom sin alterar la voz')
    if hashlib.sha256(voice.tobytes()).hexdigest() != original_hash:
        raise ValueError('El stem original fue alterado en memoria')
    tmp = ROOT / '.estado/tmp' / ('audio_mix_' + project.name) / 'sonido'
    tmp.mkdir(parents=True, exist_ok=True)
    pcm = tmp / 'mix.f32le'
    pcm.write_bytes(candidate.astype('<f4').tobytes())
    final_dir = project / 'recursos/sonido'
    final_dir.mkdir(parents=True, exist_ok=True)
    pending = tmp / 'mezcla_pendiente.m4a'
    duration = float(meta['duration'])
    command([FFMPEG, '-v', 'error', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', str(channels),
             '-i', str(pcm), '-t', str(duration), '-c:a', 'aac', '-b:a', '256k',
             '-movflags', '+faststart', str(pending)])
    encoded_meta = probe(pending)
    encoded_raw = decode(pending)
    encoded = np.frombuffer(encoded_raw, dtype='<f4')
    if not np.isfinite(encoded).all() or np.max(np.abs(encoded)) >= 1:
        raise ValueError('La mezcla AAC presenta muestras fuera de rango o datos inválidos')
    target = final_dir / 'mezcla.m4a'
    pending.replace(target)
    proof = {
        'schema_version': 1, 'scope': 'voice_original_plus_verified_sfx',
        'original_source_sha256': digest(source), 'voice_source_sha256': packet_hash,
        'voice_packet_hash_method': 'ffmpeg stream copy hash SHA256; original AAC only',
        'voice_decoded_f32le_sha256': original_hash,
        'original_voice_stem_unchanged': True,
        'voice_stem_verification': 'PCM nativo float32 hash antes/después, gain unity; ningún filtro, EQ, compresor, limiter, retime, reordenación ni voz sintética.',
        'original_audio_duration': duration, 'original_decoded_samples': len(voice),
        'sample_rate': sr, 'channels': channels, 'voice_gain_db': 0, 'voice_speed': 1,
        'voice_rate': 1, 'voice_start_offset_samples': 0,
        'voice_timeline_transform': 'identity; decoded source starts at original time zero',
        'audio_original_bit_exact': False, 'reason_not_bit_exact': 'Se suman FX y se codifica una mezcla AAC nueva.',
        'output_path': str(target.relative_to(ROOT)), 'output_sha256': digest(target),
        'output_audio_duration': float(encoded_meta['duration']),
        'output_decoded_samples': len(encoded) // channels,
        'plan_path': str(plan_path.relative_to(ROOT)), 'plan_sha256': digest(plan_path),
        'sources_and_actions': executed, 'fx_bus_extra_gain_db': extra_db,
        'mixed_pcm_sample_peak_dbfs': float(20 * np.log10(np.max(np.abs(candidate)))),
        'decoded_aac_sample_peak_dbfs': float(20 * np.log10(np.max(np.abs(encoded)))),
        'samples_abs_gt1': 0, 'music_used': False,
        'perceptual_listening_verified': False,
        'limits': ['Los picos de muestra no certifican true peak intersample ni balance perceptivo.',
                   'La identidad del stem no significa paquetes AAC finales idénticos.',
                   'Sincronización verificada por cue/storyboard; requiere revisión audiovisual del render final.'],
    }
    receipt = final_dir / 'mezcla_provenance.json'
    receipt.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    contract = {'path': proof['output_path'], 'sha256': proof['output_sha256'],
                'provenance_path': str(receipt.relative_to(ROOT)), 'provenance_sha256': digest(receipt),
                'voice_source_sha256': packet_hash}
    (final_dir / 'audio_mix.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n')
    return contract


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', default=str(PROJECT / 'audio_plan.json'))
    args = ap.parse_args()
    print(json.dumps(mix(args.plan), ensure_ascii=False, indent=2))
