"""Text geometry/state guards; no render process or production project writes."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
from html.parser import HTMLParser

from PIL import Image, ImageDraw, ImageFont
import pytest

from studio import core, design, hyperframes, typography as typo

SOFTWARE = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path):
    assert tmp_path.resolve().is_relative_to(SOFTWARE / ".estado")
    configured = core.fonts()
    missing = [role for role, original in configured.items() if not (SOFTWARE / original).is_file()]
    if missing:
        pytest.skip("Optional licensed local role fonts are unavailable; public fonts are never renamed as Sequel/Scholar: " + ", ".join(missing))
    fonts = {}
    for role, original in configured.items():
        destination = tmp_path / original
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOFTWARE / original, destination)
        fonts[role] = original
    return tmp_path, fonts


def element(**changes):
    return {"id":"headline","type":"text","text":"Ideas que avanzan", "font":"primary","font_size":84,
            "x":.05,"y":.1,"width":.9,"height":.3,"start":0,"end":2,"color":"#ffffff",**changes}


def scene(el=None):
    return {"id":"motion_text","type":"motion","template":"custom","start":0,"end":2,
            "motion_design":{"canvas":{"background":"#101318"},"elements":[el or element()]}}


@pytest.mark.parametrize("value", [True, [], "css", {"align":"justify"}, {"vertical_align":"baseline"},
    {"letter_spacing":True}, {"letter_spacing":float('nan')}, {"letter_spacing":81}, {"letter_spacing":-17},
    {"line_height":.79}, {"line_height":float('inf')}, {"stroke":True}, {"stroke":{"width":True}},
    {"stroke":{"width":17}}, {"stroke":{"color":"url(x)"}}, {"shadow":{"enabled":1}},
    {"shadow":{"blur":21}}, {"shadow":{"x":-41}}, {"shadow":{"opacity":float('nan')}},
    {"shadow":{"extra":"css"}}, {"font_weight":900}, {"shadow":{"color":"#fff;"}}])
def test_styles_reject_untrusted_values(value):
    with pytest.raises(core.StudioError):
        typo.normalize_style(value)


@pytest.mark.parametrize("value", [True, [], {"preset":"commercial"}, {"duration":True}, {"duration":float('nan')},
    {"exit":"bounce"}, {"exit_duration":0}, {"clock_offset":-1}, {"clock_start":float('inf')},
    {"clock_duration":0}, {"unknown":"onUpdate"}, {"preset":"fade_up","duration":2,"exit":"fade"},
    {"clock_start":.1}, {"clock_offset":1}, {"clock_duration":1}])
def test_animation_rejects_bad_data(value):
    with pytest.raises(core.StudioError):
        typo.normalize_animation(element(text_animation=value),2)


def test_style_defaults_keep_v03_values():
    assert typo.normalize_style()=={"align":"left","vertical_align":"top","letter_spacing":0,
        "line_height":1.15,"stroke":{"width":0,"color":"#000000"},
        "shadow":{"enabled":True,"x":2,"y":4,"blur":0,"color":"#000000","opacity":.85}}


def test_inactive_defaults_fit_a_short_element():
    result=typo.normalize_animation(element(end=.1),.1)
    assert result['preset']=='none' and result['clock_duration']==.1


def test_graphemes_are_real_unicode_clusters():
    assert typo.graphemes('e\u0301 👩🏽\u200d💻 🇨🇴')==['e\u0301',' ','👩🏽\u200d💻',' ','🇨🇴']


def test_layout_preserves_spaces_newlines_and_accents(workspace):
    root,fonts=workspace
    result=typo.layout_element(element(text='Árbol  y\n\ncafe\u0301'),(1080,1920),fonts,root=root)
    assert [line['text'] for line in result['lines']]==['Árbol  y','','cafe\u0301']
    assert result['word_count']==3
    assert result['grapheme_count']==len(typo.graphemes('Árbol  y\n\ncafe\u0301'))
    assert result['overflow'] is False


def test_long_word_not_silently_dropped_or_shrunk(workspace):
    root,fonts=workspace
    result=typo.layout_element(element(text='electroencefalografista'*8,width=.1),(1080,1920),fonts,root=root)
    assert result['lines'][0]['text']=='electroencefalografista'*8
    assert result['font_px']==84 and result['overflow'] is True


def test_alignment_and_tracking_use_measured_coordinates(workspace):
    root,fonts=workspace
    base=typo.layout_element(element(text='AVATAR'),(1080,1920),fonts,root=root)
    center=typo.layout_element(element(text='AVATAR',text_style={'align':'center','letter_spacing':8}),(1080,1920),fonts,root=root)
    assert center['lines'][0]['width']==pytest.approx(base['lines'][0]['width']+5*8)
    padding=center['padding']
    assert center['lines'][0]['x']==pytest.approx(padding['left']+(center['width']-padding['left']-padding['right']-center['lines'][0]['width'])/2)
    assert center['lines'][0]['units'][1]['x']>base['lines'][0]['units'][1]['x']


def test_vertical_align_keeps_em_and_shadow_inside_box(workspace):
    root,fonts=workspace
    layout=typo.layout_element(element(text='Ág',text_style={'vertical_align':'bottom'}),(1080,1920),fonts,root=root)
    line=layout['lines'][0]
    assert line['baseline']+layout['em_descent']+layout['padding']['bottom']==pytest.approx(layout['height'])
    assert layout['ink_overflow'] is False


def test_missing_unicode_glyph_does_not_use_system_font(workspace):
    root,fonts=workspace
    with pytest.raises(core.StudioError,match='glifos'):
        typo.layout_element(element(text='🛸'),(360,640),fonts,root=root)


def test_font_asset_resolved_only_from_explicit_verified_map(workspace):
    root,fonts=workspace
    file=root/fonts['primary']
    asset={'id':'a_font','kind':'font','path':fonts['primary'],'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
    el=element(font_asset_id='a_font')
    with pytest.raises(core.StudioError,match='adjunta'):
        typo.resolve_font(el,fonts,{},root)
    result=typo.resolve_font(el,fonts,{'a_font':asset},root)
    assert result['font_asset_id']=='a_font' and result['sha256']==asset['sha256']
    with pytest.raises(core.StudioError):
        typo.resolve_font(el,fonts,{'a_font':{**asset,'kind':'video'}},root)
    file.write_bytes(file.read_bytes()+b'changed')
    with pytest.raises(core.StudioError,match='cambió'):
        typo.resolve_font(el,fonts,{'a_font':asset},root)


@pytest.mark.parametrize('preset',typo.PRESETS)
def test_seek_out_of_order_and_trim_preserve_clock(preset):
    el=element(start=.2,end=2.4,text_animation={'preset':preset,'duration':.6,'exit':'slide','exit_duration':.3})
    trimmed=copy.deepcopy(el)
    trimmed.update(start=0,end=2)
    trimmed['text_animation'].update(clock_start=-.2,clock_duration=2.2,clock_offset=0)
    for t in [1.8,.1,1.1,0,.3]:
        assert typo.animation_state(trimmed,t,2)==pytest.approx(typo.animation_state(el,t+.4,3))


def test_typewriter_preserves_layout_and_complete_accent_cluster(workspace):
    root,fonts=workspace
    el=element(text='cafe\u0301  nuevo',text_animation={'preset':'typewriter','duration':1})
    layout=typo.layout_element(el,(1080,1920),fonts,root=root)
    state=typo.animation_state(el,.4,2)
    assert typo.line_prefix(layout['lines'][0],state,layout)=='cafe\u0301'
    assert typo.line_prefix(layout['lines'][0],typo.animation_state(el,1,2),layout)==el['text']
    assert layout==typo.layout_element(el,(1080,1920),fonts,root=root)


def test_word_reveal_is_real_words_not_characters(workspace):
    root,fonts=workspace
    el=element(text='uno  dos tres',text_animation={'preset':'word_reveal','duration':.6})
    layout=typo.layout_element(el,(1080,1920),fonts,root=root)
    value=typo.line_prefix(layout['lines'][0],typo.animation_state(el,.2,2),layout)
    assert value.strip()=='uno'


def test_static_native_snapshot_ignores_animation(workspace):
    root,fonts=workspace
    el=element(text_animation={'preset':'fade_up','duration':.6})
    live=design.draw_design(scene(el),0,(360,640),fonts,root=root)
    static=design.draw_design(scene(el),0,(360,640),fonts,root=root,animate=False)
    plain=design.draw_design(scene(element()),0,(360,640),fonts,root=root)
    assert static.tobytes()==plain.tobytes()
    assert live.tobytes()!=plain.tobytes()


def test_static_digest_excludes_animation_but_includes_style():
    baseline=scene()
    motion=copy.deepcopy(baseline)
    motion['motion_design']['elements'][0]['text_animation']={'preset':'pop'}
    assert design.design_digest(baseline)==design.design_digest(motion)
    motion['motion_design']['elements'][0]['text_style']={'align':'center'}
    assert design.design_digest(baseline)!=design.design_digest(motion)


def test_svg_and_gsap_are_data_only_and_clipped_clock(workspace):
    root,fonts=workspace
    el=element(text='</script><script>alert(1)</script>',text_animation={'preset':'typewriter','duration':1,'clock_start':-.3,'clock_duration':2.3})
    layout=typo.layout_element(el,(360,640),fonts,root=root)
    markup,selectors=hyperframes._text_svg(layout,el,'own_text','AscendiaPrimary',2)
    code=hyperframes._animate_text(el,layout,'own_text',selectors,2)
    assert '<script>' not in markup and '&lt;' in markup
    assert '</script>' not in code and 'textContent' in code
    assert 'onUpdate' not in code and 'Date.now' not in code
    assert 'tl.set(' in code


@pytest.mark.parametrize('tracking', [0,1.5])
def test_svg_shadow_overlap_waiver_does_not_disable_foreground_audits(workspace,tracking):
    """Reproduce the shadow/foreground pairs that blocked the actual UI check."""
    root,fonts=workspace
    el=element(text='Ágil  IA útil\nCódigo',font_size=81,height=.2,
        text_style={'align':'center','letter_spacing':tracking,
            'stroke':{'width':1,'color':'#20354a'},
            'shadow':{'x':3,'y':5,'blur':3,'opacity':.75}},
        text_animation={'preset':'typewriter','duration':.6,'clock_start':-.3,'clock_duration':2.3})
    layout=typo.layout_element(el,(360,640),fonts,root=root)
    markup,selectors=hyperframes._text_svg(layout,el,'measured','AscendiaPrimary',2)
    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags=[]
        def handle_starttag(self,tag,attrs):
            self.tags.append((tag,dict(attrs)))
    parsed=Tags()
    parsed.feed(markup)
    foreground=[a for t,a in parsed.tags if t=='text' and '_fg_' in a.get('id','')]
    shadows=[a for t,a in parsed.tags if t=='text' and '_sh_' in a.get('id','')]
    assert foreground and len(shadows)==len(foreground)
    for tag,attrs in parsed.tags:
        if tag=='text' and '_sh_' in attrs.get('id',''):
            assert 'data-layout-allow-overlap' in attrs and attrs['aria-hidden']=='true'
        else:
            assert not any(key.startswith('data-layout-') for key in attrs)
    assert all(len(pair)==2 for pair in selectors.values())
    assert layout['overflow'] is False
    assert 'data-layout-ignore' not in markup and 'data-layout-allow-overflow' not in markup


def test_native_styles_change_actual_pixels(workspace):
    root,fonts=workspace
    base=element(text='Ág')
    plain=typo.draw_text(base,(360,640),fonts,root=root,scene_duration=2)
    styled=typo.draw_text({**base,'text_style':{'align':'right','stroke':{'width':8,'color':'#ff0000'},'shadow':{'blur':4,'x':-6}}},(360,640),fonts,root=root,scene_duration=2)
    assert plain.tobytes()!=styled.tobytes()
    assert styled.getbbox()!=plain.getbbox()


def test_nontext_cannot_hide_font_or_animation():
    with pytest.raises(core.StudioError):
        typo.validate_text_element({'type':'media','font_asset_id':'a_font'},2)


def test_catalog_is_a_detached_copy():
    catalog=typo.catalog()
    catalog['style_defaults']['shadow']['enabled']=False
    assert typo.catalog()['style_defaults']['shadow']['enabled'] is True


def test_default_single_line_reserves_em_box_and_ink(workspace):
    root,fonts=workspace
    el=element(text='Ideas')
    layout=typo.layout_element(el,(1080,1920),fonts,root=root)
    assert layout['lines'][0]['baseline']>=layout['ascent']
    assert layout['ink_overflow'] is False and layout['overflow'] is False
    new=typo.draw_text(el,(1080,1920),fonts,root=root,scene_duration=2)
    bbox=new.getbbox()
    assert bbox and bbox[0]>=0 and bbox[1]>=0 and bbox[2]<=new.width and bbox[3]<=new.height


def test_ink_overflow_reports_shadow_and_stroke_clipping(workspace):
    root,fonts=workspace
    layout=typo.layout_element(element(text='Ág',height=.005,text_style={'vertical_align':'bottom','stroke':{'width':8}}),(360,640),fonts,root=root)
    assert layout['ink_overflow'] is True and layout['warnings']
    assert layout['ink_bounds'][1]<0 or layout['ink_bounds'][3]>layout['height']


def test_html_build_includes_real_font_and_safe_text_without_render(workspace,monkeypatch):
    root,fonts=workspace
    fontfile=root/fonts['primary']
    selected={'id':'a_selected_font','kind':'font','path':fonts['primary'],'sha256':hashlib.sha256(fontfile.read_bytes()).hexdigest()}
    source=root/'source.fixture'
    source.write_bytes(b'Unit fixture only; no video decode or source project.')
    el=element(font_asset_id=selected['id'],text='Árbol  nuevo',text_animation={'preset':'word_reveal','duration':.6})
    draft=scene(el)
    configured={**draft,'_planned_end':2,'overlays':[]}
    cfg={'primary':root/fonts['primary'],'accent':root/fonts['accent'],'font_assets':{selected['id']:selected},
         'source':{'local':source},'source_info':{'streams':[]},'assets':{},'width':360,'height':640,'fps':30,'duration':2,'scenes':[configured]}
    runtime=root/'runtime_fixture'
    runtime.mkdir()
    for name in ('gsap.min.js','MotionPathPlugin.min.js','third_party.json'):
        (runtime/name).write_text('// Unit fixture; not executed.' if name.endswith('.js') else '{}')
    monkeypatch.setattr(hyperframes.native,'_prepare',lambda *args:cfg)
    monkeypatch.setattr(hyperframes,'_runtime',lambda root:(runtime,{}, {'available':True,'verified_execution':False}))
    project={'source':'a_source','timeline':[draft],'assets':[selected],'fonts':fonts,'transcript':{'words':[]},'audio':[]}
    destination=root/'editable_fixture'
    result=hyperframes.build(project,root,destination,2)
    markup=(destination/'compositions/scene_000.html').read_text()
    main=(destination/'index.html').read_text()
    assert '<svg ' in markup and 'textContent' in markup and 'window.__timelines' in markup
    assert 'AscendiaFont0' in main and 'font-synthesis:none' in markup
    manifest=json.loads((destination/'fonts/font_manifest.json').read_text())
    assert manifest['fonts'][0]['sha256']==selected['sha256']
    assert (destination/manifest['fonts'][0]['file']).read_bytes()==fontfile.read_bytes()
    assert manifest['fonts'][0]['license']['status']=='supplied_by_user_unverified'
    assert any(item['role']=='font' for item in result['used_assets'])
