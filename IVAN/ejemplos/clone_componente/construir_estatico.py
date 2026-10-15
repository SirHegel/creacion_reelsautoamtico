"""Reconstrucción por capas del frame CLONE 3,100 s. No contiene animación."""
import pathlib,base64
import numpy as np
from PIL import Image,ImageFilter
from contornos import svg_coverage
ROOT=pathlib.Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
reference=Image.open(ROOT/'referencia_2_400.png')
target=np.array(Image.open(ROOT/'referencia_3_100.png').convert('RGB'),dtype=float)
again=target[980:1095,225:501]
expected_green=np.clip(209-(np.arange(980,1095)-990)*85/94,100,220)[:,None]
again_alpha=np.minimum(again[:,:,0]/240,again[:,:,1]/expected_green)
def smooth_field(alpha,blur=.4):
    mask=Image.fromarray((np.clip(alpha,0,1)*255).astype('uint8'))
    mask=mask.filter(ImageFilter.GaussianBlur(blur)).resize((mask.width*4,mask.height*4),Image.Resampling.BICUBIC)
    return np.array(mask,dtype=float)/255
again_layers=svg_coverage(smooth_field(again_alpha,0),(225,980),fill='url(#caption-fill)',tolerance=.045)
# El sello mantiene su caja medida. Lettering limpio a partir de Sequel,
# aproximación documentada; no conservar los escalones del raster comprimido.
sequel=base64.b64encode((PROJECT/'recursos/Sequel_Sans_Bold_Disp.ttf').read_bytes()).decode()
ui_regular=base64.b64encode(pathlib.Path('/usr/share/fonts/truetype/msttcorefonts/Arial.ttf').read_bytes()).decode()
font_root=PROJECT/'.agents/skills/hyperframes-creative/frame-presets/code-editorial/fonts'
inter_regular=base64.b64encode((font_root/'Inter-400.woff2').read_bytes()).decode()
inter_bold=base64.b64encode((font_root/'Inter-700.woff2').read_bytes()).decode()
names=['Notion','Spotify','Canva','Duolingo','Calendly','Headspace']
subtitles=['Plus','Premium','Pro','Super','Standard','Annual']
source_y=[280,377,474,570,666,763]
rows=[]
for i,(name,plan,sy) in enumerate(zip(names,subtitles,source_y)):
    asset=ROOT/'assets'/f'{name.lower()}.png'
    reference.crop((95,sy,155,sy+60)).save(asset)
    png=base64.b64encode(asset.read_bytes()).decode();center=[307,404,502,599,697,795][i];y=center-46
    top=259.5+i*97.5
    rows.append(f'''<g id="row-{name.lower()}">
      <rect x="72" y="{top}" width="576" height="91" rx="23" fill="url(#row-fill)" filter="url(#row-shadow)"/>
      <image id="logo-{name.lower()}" x="94" y="{center-29}" width="58" height="58" href="data:image/png;base64,{png}"/>
      <text x="171" y="{center-4}" class="item-name">{name}</text>
      <text x="170" y="{center+23}" class="item-plan">{plan} · renews monthly</text>
      <path d="M616 {y+39}L622 {y+47}L616 {y+55}" stroke="#ababaf" stroke-width="2.1" opacity=".8" fill="none"/>
    </g>''')
strikes=''.join(f'<path id="cancel-line-{i}" d="M90 {y}H630" stroke="#e92f2c" stroke-opacity=".50" stroke-width="3.5" fill="none"/>' for i,y in enumerate([307,404,502,599,697,795]))
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1920" viewBox="0 0 720 1280" color-interpolation-filters="sRGB">
<style>
@font-face{{font-family:Sequel;src:url('data:font/ttf;base64,{sequel}')}}
@font-face{{font-family:Ui;src:url('data:font/ttf;base64,{ui_regular}');font-weight:400}}
@font-face{{font-family:InterUI;src:url('data:font/woff2;base64,{inter_regular}');font-weight:400}}
@font-face{{font-family:InterUI;src:url('data:font/woff2;base64,{inter_bold}');font-weight:700}}
.item-name{{font-family:InterUI;font-weight:700;font-size:24.5px;letter-spacing:-.25px;fill:#e8e8ec}}
.item-plan{{font-family:InterUI;font-size:17.2px;letter-spacing:.02px;fill:#adaab0}}
</style>
<defs>
 <linearGradient id="panel-fill" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#1a191c"/><stop offset="1" stop-color="#1a191c"/></linearGradient>
 <linearGradient id="row-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#28272a"/><stop offset="1" stop-color="#28272a"/></linearGradient>
 <linearGradient id="caption-fill" x1="0" y1="990" x2="0" y2="1084" gradientUnits="userSpaceOnUse"><stop stop-color="#f3e1e3"/><stop offset=".3723" stop-color="#f3bcc2"/><stop offset=".5425" stop-color="#f3a8ae"/><stop offset=".9255" stop-color="#f27b88"/><stop offset="1" stop-color="#f27280"/></linearGradient>
 <filter id="panel-shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#000" flood-opacity=".55"/></filter>
 <filter id="row-shadow" x="-10%" y="-25%" width="120%" height="150%"><feGaussianBlur stdDeviation="1.0"/><feDropShadow dx="0" dy="1.5" stdDeviation="2.5" flood-color="#000" flood-opacity=".09"/></filter>
 <filter id="stamp-shadow" x="-20%" y="-40%" width="140%" height="180%"><feDropShadow dx="0" dy="12" stdDeviation="17" flood-color="#e42f24" flood-opacity=".56"/></filter>
 <filter id="caption-shadow" x="-20%" y="-35%" width="140%" height="170%"><feDropShadow dx="0" dy="3" stdDeviation="6.5" flood-color="#782c26" flood-opacity=".55"/></filter>
 <mask id="stamp-outside" maskUnits="userSpaceOnUse" x="50" y="290" width="620" height="350" style="mask-type:luminance"><rect x="50" y="290" width="620" height="350" fill="white"/><rect x="123.9" y="376.8" width="471.4" height="145.4" rx="19" fill="black"/></mask>
</defs>
<rect id="background" width="720" height="1280" fill="#000"/>
<g id="subscription-panel">
 <rect x="51" y="114" width="618" height="859" rx="31" fill="url(#panel-fill)" stroke="#2d2c2f" stroke-width="1" filter="url(#panel-shadow)"/>
 <text id="panel-title" x="90" y="194.5" font-family="Sequel" font-size="44.8" letter-spacing=".7" textLength="272" lengthAdjust="spacingAndGlyphs" fill="#f5f5f6">Subscriptions</text>
 <text id="panel-subtitle" x="89" y="229" font-family="InterUI" font-size="20" letter-spacing=".7" textLength="315" lengthAdjust="spacingAndGlyphs" fill="#9f9da4">ACTIVE · BILLED EVERY MONTH</text>
 <g id="subscriptions" opacity=".50">{''.join(rows)}</g>
 <g id="cancel-lines">{strikes}</g>
 <g id="monthly-total">
  <rect x="72" y="848" width="576" height="103" rx="23" fill="#2b2a2d"/>
  <text x="101" y="907" font-family="Ui" font-size="22" letter-spacing=".55" fill="#b8b5bb">You pay</text>
  <text id="cost" x="619" y="916.5" text-anchor="end" font-family="InterUI" font-weight="700" font-size="49" letter-spacing="-.9" textLength="196" lengthAdjust="spacingAndGlyphs" fill="#ff4140">$214/mo</text>
 </g>
 <g id="stamp-glow" transform="rotate(-11.94 359.6 449.5)" mask="url(#stamp-outside)"><rect x="123.9" y="376.8" width="471.4" height="145.4" rx="19" fill="#1b1a1d" filter="url(#stamp-shadow)"/></g>
 <g id="cancel-stamp" transform="rotate(-11.94 359.6 449.5)">
  <rect id="stamp-border" x="123.9" y="376.8" width="471.4" height="145.4" rx="19" fill="#1b1a1d" fill-opacity=".9" stroke="#fc392f" stroke-width="8.6"/>
  <text id="stamp-lettering" x="359.6" y="476.5" text-anchor="middle" font-family="Sequel" font-size="74.2" letter-spacing="1.5" textLength="481" lengthAdjust="spacingAndGlyphs" fill="#fc392f" stroke="#fc392f" stroke-width="2.6" stroke-linejoin="miter" paint-order="stroke fill">CANCELLED</text>
 </g>
</g>
<g id="editorial-caption" filter="url(#caption-shadow)" aria-label="AGAIN">{again_layers}</g>
</svg>'''
(ROOT/'diseno.svg').write_text(svg)
(ROOT/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>CLONE — Diseño estático pendiente de aprobación</title><style>html,body{margin:0;width:1080px;height:1920px;overflow:hidden;background:black}svg{display:block}</style></head><body>'+svg+'</body></html>')
print('Diseño estático por capas generado; no GSAP, timeline, animación ni MP4.')
