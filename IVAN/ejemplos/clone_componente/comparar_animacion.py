"""Comparación animada CLONE vs reconstrucción a tiempos equivalentes."""
import pathlib,subprocess,sys
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def run():
    frames=ROOT/'.estado/tmp/clone_render_frames';frames.mkdir(exist_ok=True)
    target=HERE/'clone_segmento_animado.mp4'
    subprocess.run(['ffmpeg','-v','error','-i',str(target),'-map','0:v:0',
      '-fps_mode','passthrough','-start_number','0','-y',str(frames/'frame_%03d.png')],check=True)
    font='/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'
    graph="[0:v]trim=start_frame=48:end_frame=96,setpts=PTS-STARTPTS,scale=720:1280:flags=lanczos[a];"\
      "[1:v]setpts=PTS-STARTPTS,scale=720:1280:flags=lanczos[b];"\
      "[a][b]hstack=inputs=2,pad=1440:1344:0:64:color=0x151517,"\
      f"drawtext=fontfile={font}:text='CLONE - Original':fontcolor=white:fontsize=28:x=36:y=20,"\
      f"drawtext=fontfile={font}:text='Reconstruccion GSAP + HyperFrames':fontcolor=white:fontsize=28:x=756:y=20[v]"
    subprocess.run(['ffmpeg','-v','error','-i',str(ROOT/'recursos/B2_CLONE.mp4'),
      '-i',str(target),'-filter_complex',graph,'-map','[v]','-map','1:a:0',
      '-t','1.6','-r','30','-c:v','h264_nvenc','-preset','p5','-cq','18',
      '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart','-y',
      str(HERE/'clone_comparacion_animada.mp4')],check=True)
    sheet=Image.new('RGB',(2240,6*277),(15,15,17));draw=ImageDraw.Draw(sheet)
    for f in range(48):
        x=f%8*280;y=f//8*277
        draw.text((x+4,y+5),f'{(48+f)/30:.3f}s | original / reconstrucción',fill='white')
        for j,source in enumerate([ROOT/f'.estado/tmp/clone_movimiento_frames/frame_{48+f:03}.png',frames/f'frame_{f:03}.png']):
            sheet.paste(Image.open(source).resize((140,249)),(x+j*140,y+24))
    sheet.save(ROOT/'.estado/tmp/clone_render_48_comparados.jpg')
    for t,f in [('1_600',0),('2_400',24),('2_933',40),('3_100',45)]:
        out=Image.new('RGB',(1440,1344),(15,15,17));d=ImageDraw.Draw(out)
        d.text((30,20),'CLONE original',fill='white');d.text((750,20),'Reconstrucción · tiempo equivalente',fill='white')
        for j,source in enumerate([ROOT/f'.estado/tmp/clone_movimiento_frames/frame_{48+f:03}.png',frames/f'frame_{f:03}.png']):
            out.paste(Image.open(source).resize((720,1280)),(j*720,64))
        out.save(ROOT/f'.estado/tmp/clone_equivalente_{t}.png')
    print('Comparación animada y48frames comparados generados.')
if __name__=='__main__':run()
