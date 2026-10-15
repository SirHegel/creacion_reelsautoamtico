"""Compilar HTML legible por el auditor estático desde la timeline editable."""
import pathlib,hashlib
root=pathlib.Path(__file__).resolve().parent
timeline=(root/'timeline.gsap.js').read_text()
sources=''.join(f'<div id="source-{key}" class="source"><div class="source-name">{name}</div><div class="source-data"><i></i><i></i><i></i></div></div>' for key,name in [('a','Documento'),('b','Página web'),('c','Datos')])
lines=''.join(f'<div class="result-line" style="top:{925+i*69}px;width:{330-i%3*42}px"></div>' for i in range(6))
html='''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1"><title>Prueba de arquitectura GSAP</title>
<script src="lib/gsap.min.js"></script><script src="lib/MotionPathPlugin.min.js"></script><script src="lib/MorphSVGPlugin.min.js"></script>
<style>
@font-face{font-family:Sequel;src:url('fonts/Sequel_Sans_Bold_Disp.ttf')}
@font-face{font-family:Scholar;src:url('fonts/Scholar_Italic.ttf')}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}
#root{width:100%;height:100%;position:relative;overflow:hidden;font-family:Sequel;color:#f4f3ef;background:#07090d}
#world{position:absolute;inset:0}#opening-title,#final-title{position:absolute;left:90px;top:240px;width:900px;line-height:1.0;font-size:104px;letter-spacing:-3px}
#opening-title{max-width:750px}#final-title{font-size:101px;clip-path:inset(0% 0% 100% 0%)}.editorial{font-family:Scholar}
.source{position:absolute;width:300px;height:220px;background:#f4f3ef;border-radius:20px;color:#191d24;box-shadow:0 18px 24px #0008;padding:30px}
#source-a{left:90px;top:650px}#source-b{left:690px;top:650px}#source-c{left:390px;top:530px}.source-name{font-size:34px;letter-spacing:-1px}.source-data{margin-top:25px;clip-path:inset(0% 100% 0% 0%)}
.source-data i{display:block;background:#73777e;width:200px;height:12px;margin-bottom:15px;border-radius:2px}.source-data i:nth-child(2){width:150px}.source-data i:nth-child(3){width:185px}
svg{position:absolute;inset:0;width:1080px;height:1920px;overflow:visible}#routes{z-index:0}.source{z-index:3}.packet{position:absolute;width:26px;height:26px;left:0;top:0;background:#fff;border-radius:5px;opacity:0;z-index:5}
#processing-label{position:absolute;left:390px;top:1127px;width:300px;text-align:center;font-size:39px;z-index:6}#fold{position:absolute;left:655px;top:720px;width:110px;height:110px;clip-path:inset(0% 100% 0% 0%);z-index:6}#fold:after{content:'';position:absolute;inset:0;background:#bdc2c9;clip-path:polygon(0% 0%,0% 100%,100% 100%)}
.result-line{position:absolute;left:370px;height:15px;background:#686f79;border-radius:3px;z-index:6}.result-line:first-of-type{height:22px;background:#202631}
#grid{opacity:.03}#identity{position:absolute;bottom:200px;left:90px;width:900px;font-size:32px;color:#afb4bf;letter-spacing:1px}
</style></head><body><div id="root" data-composition-id="arquitectura-gsap" data-width="1080" data-height="1920" data-duration="3" data-fps="30">
<svg id="grid" viewBox="0 0 1080 1920"><defs><pattern id="grid-pattern" width="90" height="90" patternUnits="userSpaceOnUse"><path d="M90 0H0V90" fill="none" stroke="#fff" stroke-width="1"/></pattern></defs><rect width="1080" height="1920" fill="url(#grid-pattern)"/></svg>
<div id="world"><div id="opening-title">Datos en <span class="editorial">movimiento.</span></div><div id="final-title">Información <span class="editorial">organizada.</span></div>
<svg id="routes" viewBox="0 0 1080 1920"><path id="route-a" d="M240 820C210 1080 440 1180 540 1160" fill="none" stroke="#d9dee7" stroke-width="4"/><path id="route-b" d="M840 820C850 1110 640 1210 540 1160" fill="none" stroke="#d9dee7" stroke-width="4"/><path id="route-c" d="M540 620C440 800 670 970 540 1160" fill="none" stroke="#d9dee7" stroke-width="4"/></svg>
SOURCES
<svg id="system" viewBox="0 0 1080 1920"><path id="processor" d="M540 985L690 1055L690 1265L540 1335L390 1265L390 1055Z" fill="#171b24" stroke="#cfd4de" stroke-width="3"/></svg>
<div id="processing-label">ORDENAR</div><div id="packet-a" class="packet"></div><div id="packet-b" class="packet"></div><div id="packet-c" class="packet"></div><div id="fold"></div>LINES</div>
<div id="identity">FUENTES → PROCESO → RESULTADO</div></div><script>TIMELINE</script></body></html>'''
html=html.replace('SOURCES',sources).replace('LINES',lines).replace('TIMELINE',timeline)
(root/'index.html').write_text(html)
print('HTML compilado desde timeline.gsap.js; SHA timeline:',hashlib.sha256(timeline.encode()).hexdigest())
