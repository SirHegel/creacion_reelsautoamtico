"""Two real audio streams: tones/silence are not claimed to be speech."""
import copy
import threading
import wave
from pathlib import Path

import numpy as np
import pytest

from studio import analysis, core, jobs, media_tools

REAL_ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def space(tmp_path,monkeypatch):
    assert tmp_path.is_relative_to(REAL_ROOT/'.estado/tmp')
    for module in (core,analysis,jobs):monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(jobs,'SHARED_CPU_LOCK',tmp_path/'.estado/cpu_worker.lock')
    (tmp_path/'.estado/tmp').mkdir(parents=True)
    return tmp_path


def fixture(space,offset=0):
    source=space/('two_tracks_offset.mkv' if offset else 'two_tracks.mkv')
    args=['-nostdin','-v','error','-filter_threads','2','-filter_complex_threads','2',
          '-f','lavfi','-i','color=c=navy:s=160x284:r=10:d=2',
          '-f','lavfi','-i','anullsrc=r=48000:cl=mono:d=2']
    if offset:args+=['-itsoffset',str(offset)]
    args+=['-f','lavfi','-i',f'sine=frequency=880:sample_rate=48000:duration={2-offset}',
           '-map','0:v:0','-map','1:a:0','-map','2:a:0','-c:v','ffv1','-c:a','pcm_s16le',
           '-ac:a:1','2','-threads','2','-n',str(source)]
    with jobs.cpu_slot():media_tools._run('ffmpeg',args,space)
    return source,{'id':'private_two_track_fixture','path':source.name,'sha256':core.digest(source),'duration':2.}


def pcm(path):
    with wave.open(str(path),'rb') as stream:
        return stream.getframerate(),stream.getnchannels(),np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(float)/32768


def test_global_index_selects_real_second_audio_and_legacy_ordinal_still_works(space):
    source,asset=fixture(space)
    info=analysis.probe(source)
    assert [(s['index'],s['codec_type']) for s in info['streams']]==[(0,'video'),(1,'audio'),(2,'audio')]
    assert analysis.select_audio_stream(info,2)['audio_ordinal']==1
    second=media_tools.process(asset,'extract_audio',{'audio_stream_index':2},space)
    legacy=media_tools.process(asset,'extract_audio',{'audio_stream':1},space)
    first=media_tools.process(asset,'extract_audio',{'audio_stream_index':1},space)
    assert second['sha256']==legacy['sha256'] and first['sha256']!=second['sha256']
    rate,channels,values=pcm(space/second['path'])
    assert rate==48000 and channels==2 and np.sqrt(np.mean(values*values))>.05
    assert not np.any(pcm(space/first['path'])[2])
    assert second['provenance']['audio_selection']['ffmpeg_map']=='0:2'
    assert second['provenance']['audio_selection']['voice_verified'] is False
    assert core.digest(source)==asset['sha256']
    assert media_tools.process(asset,'extract_audio',{'audio_stream_index':2},space)['reused'] is True


def test_real_activity_ranking_does_not_claim_tone_is_speech(space):
    source,asset=fixture(space)
    result=analysis.audio_tracks(source,duration=2)
    assert result['recommended_stream_index']==2 and result['ranking']==[2,1]
    assert result['tracks'][0]['rms_dbfs'] is None and result['tracks'][1]['active_window_ratio']>.99
    assert result['voice_verified'] is False and result['speech_detection_executed'] is False
    assert result['audio_listened'] is False and result['source_sha256']==asset['sha256']
    assert result['scope_seconds']==2 and 'música' in result['limitations'][0]
    assert result['tracks'][1]['decoded_seconds']==pytest.approx(2,abs=.01)


def test_waveform_and_silence_follow_selected_global_track(space):
    source,_=fixture(space)
    silent=analysis.waveform(source,audio_stream_index=1)
    active=analysis.waveform(source,audio_stream_index=2)
    assert max(silent['peaks'])==0 and max(active['peaks'])>.1
    assert active['audio_stream_index']==2 and silent['audio_stream_index']==1
    assert analysis.silence_analysis(source,audio_stream_index=1)[0]['start']==pytest.approx(0,abs=.01)
    assert analysis.silence_analysis(source,audio_stream_index=2)==[]


def test_positive_stream_pts_is_preserved_as_silence_before_selected_audio(space):
    source,asset=fixture(space,.5)
    selected=analysis.select_audio_stream(analysis.probe(source),2)
    assert float(selected['start_time'])==pytest.approx(.5,abs=.01)
    result=media_tools.process(asset,'extract_audio',{'audio_stream_index':2,'channels':1},space)
    rate,_,values=pcm(space/result['path'])
    assert len(values)/rate==pytest.approx(2,abs=.01)
    assert np.max(np.abs(values[:int(.45*rate)]))==0
    assert np.sqrt(np.mean(values[int(.65*rate):int(1.8*rate)]**2))>.05


def test_asr_receives_selected_real_pcm_with_source_clock_and_cleanup(space,monkeypatch):
    source,asset=fixture(space,.5);paths=[]
    def explicit_asr_stub(path,*args,**kwargs):
        paths.append(Path(path));rate,channels,values=pcm(path)
        assert rate==16000 and channels==1 and len(values)==32000
        assert np.max(np.abs(values[:int(.45*rate)]))==0
        assert np.sqrt(np.mean(values[int(.7*rate):]**2))>.05
        return {'status':'transcribed','engine':'explicit_asr_unit_stub','words':[],'segments':[]}
    monkeypatch.setattr(analysis,'_transcribe',explicit_asr_stub)
    result=analysis.transcribe(source,audio_stream_index=2)
    assert result['audio_source']['stream_index']==2 and result['audio_source']['ffmpeg_map']=='0:2'
    assert result['audio_source']['source_sha256']==asset['sha256']
    assert len(result['audio_source']['asr_pcm_sha256'])==64
    assert paths and all(not path.exists() for path in paths)
    assert core.digest(source)==asset['sha256']


def test_project_analysis_uses_configuration_and_explicit_option_precedence(space,monkeypatch):
    source,asset=fixture(space)
    project={'assets':[asset],'source':asset['id'],'settings':{'voice_audio_stream':2}}
    result=analysis.analyze_project(copy.deepcopy(project),{'transcribe':False})
    assert result['analysis']['audio_selection']['stream_index']==2
    assert max(result['analysis']['waveform']['peaks'])>.1
    implicit=analysis.analyze_project(copy.deepcopy(project),{'transcribe':False,'audio_stream_index':None})
    assert implicit['analysis']['audio_selection']['stream_index']==2
    alternate=analysis.analyze_project(copy.deepcopy(project),{'transcribe':False,'audio_stream_index':1})
    assert alternate['settings']['voice_audio_stream']==1 and max(alternate['analysis']['waveform']['peaks'])==0


@pytest.mark.parametrize('value',[True,False,2.,'2',-1,1024,float('nan'),[],{}])
def test_absolute_index_types_rejected_before_decode(space,monkeypatch,value):
    with pytest.raises(core.StudioError):analysis.select_audio_stream({'streams':[]},value)
    with pytest.raises(core.StudioError):analysis.validate_analysis_options({'audio_stream_index':value})
    with pytest.raises(core.StudioError):media_tools.validate_options('extract_audio',{'audio_stream_index':value})


@pytest.mark.parametrize('index',[0,3,1023])
def test_nonexistent_or_video_global_index_rejected(space,index):
    source,asset=fixture(space)
    with pytest.raises(core.StudioError,match='no existe o no es audio'):
        media_tools.process(asset,'extract_audio',{'audio_stream_index':index},space)
    assert not list((space/'.estado/tools').glob('*.wav')) if (space/'.estado/tools').exists() else True


def test_mutually_exclusive_selectors_and_normalized_options_roundtrip():
    with pytest.raises(core.StudioError,match='mutuamente excluyentes'):
        media_tools.validate_options('extract_audio',{'audio_stream_index':2,'audio_stream':1})
    options=media_tools.validate_options('extract_audio',{'audio_stream_index':2})
    assert 'audio_stream' not in options and media_tools.validate_options('extract_audio',options)==options


def test_cancelled_audio_work_does_not_start_a_decoder(space,monkeypatch):
    event=threading.Event();event.set()
    monkeypatch.setattr(analysis,'probe',lambda *a:pytest.fail('Cancelled selection must not probe'))
    with pytest.raises(core.StudioError,match='Cancelado|cancelado'):
        analysis.audio_tracks('missing.mkv',cancel=event)
    with pytest.raises(core.StudioError,match='Cancelado|cancelado'):
        analysis.transcribe('missing.mkv',audio_stream_index=2,cancel=event)


def test_source_change_during_asr_rejected_and_private_wav_cleaned(space,monkeypatch):
    source,_=fixture(space)
    def mutate(path,*a,**kw):
        source.write_bytes(b'unit source mutation')
        return {'status':'transcribed'}
    monkeypatch.setattr(analysis,'_transcribe',mutate)
    with pytest.raises(core.StudioError,match='fuente cambió'):
        analysis.transcribe(source,audio_stream_index=2)
    assert not list((space/'.estado/tmp').glob('asr-selected-*'))


def test_ranking_bounds_track_count_and_reports_unmeasured_streams(space,monkeypatch):
    source=space/'nine_tracks.mkv';source.write_bytes(b'explicit mocked inventory, no inference')
    info={'format':{'duration':'60'},'streams':[{'index':i+1,'codec_type':'audio'} for i in range(9)]}
    monkeypatch.setattr(analysis,'probe',lambda path:info)
    maps=[]
    def bounded_pcm(args,*unused):
        maps.append(args[args.index('-map')+1])
        return np.zeros(16000,dtype='<f4').tobytes()
    monkeypatch.setattr(analysis,'run',bounded_pcm)
    result=analysis.audio_tracks(source,duration=1,selected_index=9)
    assert maps==[f'0:{index}' for index in range(1,9)]
    assert result['unmeasured_stream_indices']==[9] and result['selected_stream_index']==9
    assert result['total_audio_tracks']==9 and result['recommended_stream_index'] is None


def test_source_changes_while_ranking_are_rejected(space,monkeypatch):
    source=space/'changed.mkv';source.write_bytes(b'unit source original')
    monkeypatch.setattr(analysis,'probe',lambda path:{'format':{'duration':'1'},'streams':[{'index':1,'codec_type':'audio'}]})
    def mutate(*unused):
        source.write_bytes(b'unit source changed')
        return np.zeros(16000,dtype='<f4').tobytes()
    monkeypatch.setattr(analysis,'run',mutate)
    with pytest.raises(core.StudioError,match='fuente cambió'):
        analysis.audio_tracks(source,duration=1)


@pytest.mark.parametrize('name,value',[('script','alert(1)'),('model',[]),('language',True),('audio_stream_index',1.)])
def test_invalid_analysis_options_fail_before_media_io(space,monkeypatch,name,value):
    monkeypatch.setattr(analysis,'probe',lambda *a:pytest.fail('Invalid options must not start IO'))
    with pytest.raises(core.StudioError):analysis.analyze_project({}, {name:value})
