"""Original y reconstrucción a escala equivalente. FASE 1: ninguna animación."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

p=Path(__file__).resolve().parent
root=p.parents[1]
w,h=1080,1920
original=Image.open(p/'referencia_3_100.png').convert('RGB').resize((w,h),Image.Resampling.LANCZOS)
result=Image.open(p/'clone_diseno_estatico.png').convert('RGB')
assert result.size==(w,h)
im=Image.new('RGB',(w*2+2,h+96),'#17171a');d=ImageDraw.Draw(im)
f=ImageFont.truetype(str(root/'recursos/Sequel_Sans_Bold_Disp.ttf'),34)
d.text((34,25),'CLONE · referencia 3,10 s',font=f,fill='white')
d.text((w+36,25),'Reconstrucción · segunda pasada',font=f,fill='white')
im.paste(original,(0,96));im.paste(result,(w+2,96));im.save(p/'clone_comparacion.png')
print('Comparación PNG a la misma escala: original izquierda, reconstrucción derecha.')
