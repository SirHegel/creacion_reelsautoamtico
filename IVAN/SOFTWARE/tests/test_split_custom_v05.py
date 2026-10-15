"""Real CPU synthetic pixels and voice; no presenter or editorial approval."""
import copy
from pathlib import Path
import shutil

from PIL import Image
import pytest

from studio import hyperframes as hf,render as native


@pytest.fixture
def fixture(tmp_path):
    assert tmp_path.is_relative_to(hf.CODE_ROOT/'.estado/tmp')
    missing=[name for name in ('Sequel_Sans_Bold_Disp.ttf','Scholar_Italic.ttf')
             if not (hf.CODE_ROOT/'assets/fonts'/name).is_file()]
    if missing:
        pytest.skip('Optional licensed local Sequel/Scholar fonts are absent from the public source: '+', '.join(missing))
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('Optional local FFmpeg/ffprobe is required by synthetic media fixtures')
    (tmp_path/'assets/fonts').mkdir(parents=True)
    for name in ('Sequel_Sans_Bold_Disp.ttf','Scholar_Italic.ttf'):
        shutil.copyfile(hf.CODE_ROOT/'assets/fonts'/name,tmp_path/'assets/fonts'/name)
    source=tmp_path/'synthetic.mp4'
    from studio.jobs import cpu_slot
    with cpu_slot():
        native._run([native._tool('ffmpeg'),'-v','error','-n','-f','lavfi','-i','color=c=red:s=240x640:r=12:d=1.5',
                 '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1.5',
                     '-vf','drawbox=x=0:y=320:w=240:h=320:color=blue:t=fill','-c:v','libx264','-pix_fmt','yuv420p','-threads','1','-c:a','aac','-shortest',str(source)],tmp_path)
    design={'canvas':{'background':'#142018'},'elements':[{'id':'packet','type':'shape','shape':'rect','x':.1,'y':.2,'width':.12,'height':.12,'color':'#20bb89',
            'keyframes':[{'time':0,'x':.1},{'time':.75,'x':.7},{'time':1,'x':.1}]}]}
    first={'id':'split_custom','start':0,'end':1,'type':'split','template':'custom','motion_design':copy.deepcopy(design),
           'camera_anchors':[{'time':0,'focus_x':.5,'focus_y':0,'chin_y':.6},{'time':.9,'focus_x':.5,'focus_y':1,'chin_y':.6}]}
    second={'id':'motion_custom','start':1,'end':1.5,'type':'motion','template':'custom','motion_design':copy.deepcopy(design)}
    second['motion_design']['elements'][0]['keyframes']=[{'time':0,'x':.1},{'time':.5,'x':.7}]
    return tmp_path,{'source':'a_raw','assets':[{'id':'a_raw','path':'synthetic.mp4','kind':'video'}],
                     'fonts':{'primary':'assets/fonts/Sequel_Sans_Bold_Disp.ttf','accent':'assets/fonts/Scholar_Italic.ttf'},
                     'settings':{'width':160,'height':240,'fps':12},'timeline':[first,second],'audio':[]}


def frame(root,path,when):
    output=root/('frame_'+str(when)+'.rgb')
    native._run([native._tool('ffmpeg'),'-v','error','-n','-ss',str(when),'-i',str(path),'-frames:v','1','-threads','2','-pix_fmt','rgb24','-f','rawvideo',str(output)],root)
    return Image.frombytes('RGB',(160,240),output.read_bytes())


def require_hyperframes_runtime():
    dependencies=hf._dependencies()
    missing=[name for name in ('cli','cli_bundle','cli_package','gsap','path_plugin','gsap_package',
                              'node','browser','ffmpeg','ffprobe') if not dependencies[name].is_file()]
    if missing:
        pytest.skip('Optional local HyperFrames/GSAP runtime is unavailable: '+', '.join(missing))


@pytest.fixture
def hyperframes_fixture(request):
    require_hyperframes_runtime()
    return request.getfixturevalue('fixture')


def test_native_split_custom_upper_motion_lower_real_crop_and_original_audio(fixture):
    root,project=fixture
    receipt=native.render(project,root,root/'native.mp4',seconds=1.5)
    first=frame(root,root/'native.mp4',0);last=frame(root,root/'native.mp4',.9)
    assert first.getpixel((80,220))[0]>180 and first.getpixel((80,220))[2]<60
    assert last.getpixel((80,220))[2]>180 and last.getpixel((80,220))[0]<60
    assert first.getpixel((25,35))[1]>100
    assert first.getpixel((80,120))[0]<40 and first.getpixel((80,140))[0]>180
    assert receipt['technical']['original_voice_present'] is True
    assert any(a['role']=='split' and a['asset_id']=='a_raw' and a['end']==1 for a in receipt['used_assets'])
    assert receipt['technical']['audio_listened'] is False


def test_hyperframes_split_real_dom_upper_lower_camera_and_voice(hyperframes_fixture):
    root,project=hyperframes_fixture
    receipt=hf.render(project,root,root/'hyperframes.mp4',seconds=1.5)
    assert hf.verify_receipt(receipt,root)
    proof=receipt['technical']['hyperframes']
    build=__import__('json').loads(hf._inside(root,proof['build_path'],True).read_text())
    assert all(e['editable_dom_motion'] for e in build['scene_engines'])
    assert 'camera lower' in build['scene_engines'][0]['engine']
    comp=hf._inside(root,build['directory']+'/compositions/scene_000.html',True).read_text()
    assert 'height:132px' in comp and 'top:132px' in comp and 'el_0_0' in comp
    first=frame(root,root/'hyperframes.mp4',0);last=frame(root,root/'hyperframes.mp4',.9)
    assert first.getpixel((80,220))[0]>170 and first.getpixel((80,220))[2]<70
    assert last.getpixel((80,220))[2]>170 and last.getpixel((80,220))[0]<70
    assert first.getpixel((25,35))[1]>100
    assert receipt['technical']['original_voice_present'] is True and receipt['technical']['audio_listened'] is False


@pytest.mark.parametrize('value',[
    [{'time':0,'focus_x':False,'focus_y':.5,'chin_y':.6}],
    [{'time':0,'focus_x':.5,'focus_y':.5,'chin_y':.6,'crop':'arbitrary'}],
    [{'time':0,'focus_x':.5,'focus_y':.5,'chin_y':.6},{'time':0,'focus_x':.6,'focus_y':.5,'chin_y':.6}],
    [{'time':2,'focus_x':.5,'focus_y':.5,'chin_y':.6}],
    [{'time':0,'focus_x':.5,'focus_y':float('nan'),'chin_y':.6}],
])
def test_anchors_are_bounded_numeric_only_before_decoder(fixture,value):
    root,project=fixture;project['timeline'][0]['camera_anchors']=value
    with pytest.raises(native.RenderError):native._prepare(project,root,1)


def test_anchor_interpolation_is_seek_safe_and_clamps_without_inventing(fixture):
    root,project=fixture;scene=project['timeline'][0]
    assert native._camera_state(scene,.9)['focus_y']==1
    assert native._camera_state(scene,.45)['focus_y']==pytest.approx(.5)
    assert native._camera_state(scene,0)['focus_y']==0
    assert native._camera_state(scene,3)['focus_y']==1


def test_even_subcanvas_for_642_height_preserves_split_boundary(fixture):
    root,project=fixture;project['settings']['height']=642
    assert native.split_height(642)==354 and native.split_height(640)==352
    cfg=native._prepare(project,root,1)
    assert cfg['scenes'][0]['_design_size']==(160,354)
    receipt=native.render(project,root,root/'even_regions.mp4',seconds=1)
    assert receipt['width']==160 and receipt['height']==642
    info=native.probe_media(root/'even_regions.mp4',root)
    assert info['streams'][0]['height']==642


def test_real_anamorphic_source_is_not_silently_distorted(fixture):
    root,project=fixture;source=root/'anamorphic.mp4'
    native._run([native._tool('ffmpeg'),'-v','error','-n','-f','lavfi','-i','color=c=black:s=160x240:r=12:d=1',
                 '-vf','drawbox=x=60:y=80:w=40:h=80:color=white:t=fill,setsar=2/1','-c:v','libx264','-pix_fmt','yuv420p','-threads','1',str(source)],root)
    raw=root/'anamorphic.rgb'
    native._decode({'local':source,'kind':'video'},(160,240),0,1,12,raw,root,{'type':'presenter'},None)
    image=Image.frombytes('RGB',(160,240),raw.read_bytes())
    occupied=[(x,y) for y in range(240) for x in range(160) if min(image.getpixel((x,y)))>200]
    width=max(x for x,y in occupied)-min(x for x,y in occupied)+1
    height=max(y for x,y in occupied)-min(y for x,y in occupied)+1
    assert 76<=width<=84 and 76<=height<=84


def test_direct_renderer_obtains_global_cpu_and_preserves_cancel_exception(fixture,monkeypatch):
    from studio import jobs
    import threading
    root,project=fixture
    monkeypatch.setattr(native,'_render',lambda *a,**k: {'held':getattr(jobs.CPU_ACTIVE,'active',False)})
    assert native.render(project,root,root/'unused.mp4')['held'] is True
    assert not getattr(jobs.CPU_ACTIVE,'active',False)
    event=threading.Event();event.set()
    with pytest.raises(native.RenderCancelled):native.render(project,root,root/'unused.mp4',cancel=event)


def public_brand(root,project):
    from studio import branding
    project['id']='p_public_brand_fixture';project['style']={}
    branding.bootstrap(root,'Explicit public-font fixture')
    branding.bind_project(project,root)
    for scene in project['timeline']:
        scene['motion_design']['elements'].append({'id':'role_text','type':'text','text':'Datos reales','font':'primary','font_size':50,
                                                  'x':.1,'y':.5,'width':.8,'height':.3,'color':'#ffffff'})
    return project


def test_branding_roles_without_font_asset_id_bundle_authentic_bytes_and_notices_once(hyperframes_fixture):
    import json,zipfile
    from studio.motion_bundle import write_bundle
    root,project=hyperframes_fixture;public_brand(root,project)
    assert all('font_asset_id' not in el for s in project['timeline'] for el in s['motion_design']['elements'])
    receipt=hf.render(project,root,root/'public_brand.mp4',1.5)
    assert hf.verify_receipt(receipt,root)
    proof=receipt['technical']['hyperframes']
    build=json.loads(hf._inside(root,proof['build_path'],True).read_text())
    folder=hf._inside(root,build['directory'])
    manifest=json.loads((folder/'fonts/font_manifest.json').read_text())
    assert len(manifest['fonts'])==2
    roles=project['style']['branding']['fonts']
    expected={face['sha256'] for face in roles.values()}
    assert {f['sha256'] for f in manifest['fonts']}==expected
    assert len(list((folder/'fonts').glob('*.ttf')))+len(list((folder/'fonts').glob('*.otf')))==2
    assert not (folder/'fonts/primary.ttf').exists() and not (folder/'fonts/accent.ttf').exists()
    for record in manifest['fonts']:
        assert hf._sha(folder/record['file'])==record['sha256']
        notice=record['license']['bundled_notice']
        assert notice and hf._sha(folder/notice)==record['license']['notice_sha256']
    destination=root/'.estado/tmp/public_editable.zip'
    result=write_bundle(receipt,root,destination)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        for record in manifest['fonts']:
            assert __import__('hashlib').sha256(archive.read(record['file'])).hexdigest()==record['sha256']
            assert __import__('hashlib').sha256(archive.read(record['license']['bundled_notice'])).hexdigest()==record['license']['notice_sha256']
    assert result['editorial_approved'] is False


def test_branding_font_snapshot_is_authoritative_and_current(fixture):
    root,project=fixture;public_brand(root,project)
    cfg=native._prepare(project,root,1)
    hf._font_identity(cfg,root)
    forged=copy.deepcopy(project);forged['style']['branding']['fonts']['primary']['family']='Sequel Sans'
    with pytest.raises(native.RenderError,match='marca'):native._prepare(forged,root,1)
    source=root/project['fonts']['primary'];data=source.read_bytes();source.write_bytes(data[:-1]+bytes([data[-1]^1]))
    with pytest.raises(native.RenderError):native._prepare(project,root,1)


def test_split_snapshot_accepts_static_upper_and_authentic_camera_at_original_time(hyperframes_fixture):
    root,project=hyperframes_fixture;selected=project['timeline'][0]
    receipt=hf.snapshot_design(project,selected['id'],root,root/'split_static.png')
    assert receipt['technical']['hyperframes']['static_only'] is True
    image=Image.open(root/'split_static.png').convert('RGB')
    assert image.size==(160,240) and image.getpixel((80,220))[0]>170
    assert receipt['technical']['editorial_approved'] is False
