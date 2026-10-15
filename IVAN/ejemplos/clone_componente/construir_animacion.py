"""Derivar la composición animada sin modificar el SVG/PNG aprobados."""
import base64, copy, hashlib, json, pathlib, re, sys, xml.etree.ElementTree as E
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from contornos import svg_coverage

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NS = 'http://www.w3.org/2000/svg'
E.register_namespace('', NS)
E.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
def tag(name): return '{'+NS+'}'+name
def digest(file): return hashlib.sha256(pathlib.Path(file).read_bytes()).hexdigest()
def nonzero_caption(paths):
    """Contornos con huecos reales, sin perforar serifas superpuestas."""
    tree=E.fromstring('<svg xmlns="'+NS+'">'+paths+'</svg>')
    def area(poly):
        return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2
    def contains(poly,point):
        x,y=point;inside=False
        for (ax,ay),(bx,by) in zip(poly,poly[1:]+poly[:1]):
            if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:inside=not inside
        return inside
    for path in tree:
        rings=[]
        for data in re.findall(r'M([^Z]+)Z',path.get('d')):
            numbers=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',data)))
            rings.append(list(zip(numbers[::2],numbers[1::2])))
        signed=[area(r)for r in rings];out=[]
        for i,ring in enumerate(rings):
            probes=ring[::max(1,len(ring)//5)]
            depth=sum(abs(signed[j])>abs(signed[i]) and all(contains(other,p)for p in probes)
                      for j,other in enumerate(rings)if j!=i)
            if (signed[i]>0)!=(depth%2==0):ring=ring[::-1]
            # Microcontraformas aisladas son ruido de H.264, no diseño.
            if depth%2==1 and abs(signed[i])<3:continue
            out.append('M'+'L'.join(f'{x:.2f} {y:.2f}'for x,y in ring)+'Z')
        path.set('d',''.join(out));path.set('fill-rule','nonzero')
    return list(tree)
def build():
    p = json.loads((HERE/'proyecto.json').read_text())
    a = p['aprobacion_diseno']
    if not a['usuario_aprobo']: raise ValueError('Diseño no aprobado')
    for name, key in [('diseno.svg','diseno_sha256'),('clone_diseno_estatico.png','png_sha256')]:
        if digest(HERE/name) != a[key]: raise ValueError('El diseño aprobado cambió: '+name)
    svg = E.fromstring((HERE/'diseno.svg').read_text())
    nodes = {e.get('id'):e for e in svg.iter() if e.get('id')}
    defs = svg.find(tag('defs'))
    # Nuevos estados de texto observados dentro del tramo autorizado.
    # Se trazan solo sus glifos: nunca se inserta el panel ni el frame raster.
    for ident, frame, label in [('caption-without',64,'WITHOUT PAYING'),('caption-for',85,'FOR A SUBSCRIPTION')]:
        local_crop=HERE/'assets'/f'{ident}_referencia.png'
        if not local_crop.exists():
            im=Image.open(ROOT/f'.estado/tmp/clone_movimiento_frames/frame_{frame:03}.png').convert('RGB')
            im.crop((80,974,650,1090)).save(local_crop)
        crop=np.array(Image.open(local_crop).convert('RGB'),float)
        if ident=='caption-for':
            yy=np.arange(974,1090)
            rr=np.interp(yy,[1018,1032,1045,1058],[245,240,232,232])[:,None]
            gg=np.interp(yy,[1018,1032,1045,1058],[235,215,187,161])[:,None]
            bb=np.interp(yy,[1018,1032,1045,1058],[231,209,172,139])[:,None]
            # Separar tinta de halo rojo: R solo confundía glow con glifos.
            field=np.minimum.reduce([crop[:,:,0]/rr,crop[:,:,1]/gg,crop[:,:,2]/bb])
            field[:,:183]=crop[:,:183,:3].min(axis=2)/241
        else:field=crop[:,:,:3].min(axis=2)/241
        field=np.clip(field,0,1)
        field[field<.06] = 0
        mask = Image.fromarray((field*255).astype('uint8')).resize((570*4,116*4), Image.Resampling.BICUBIC)
        paths = svg_coverage(np.asarray(mask,float)/255,(80,974),fill='#f0eeed',tolerance=.06)
        g = E.Element(tag('g'),{'id':ident,'aria-label':label})
        children=nonzero_caption(paths)
        if ident=='caption-for':
            # Muestras de tintaF85 en1018/1032/1045/1058; no paleta nueva.
            grad=E.SubElement(defs,tag('linearGradient'),{'id':'for-caption-fill','x1':'0','y1':'1018','x2':'0','y2':'1058','gradientUnits':'userSpaceOnUse'})
            for off,color in [('0','#f5ebe7'),('.35','#f0d7d1'),('.675','#e8bbac'),('1','#e8a18b')]:
                E.SubElement(grad,tag('stop'),{'offset':off,'stop-color':color})
            for suffix,x,width in [('white',0,263),('pink',263,457)]:
                clip=E.SubElement(defs,tag('clipPath'),{'id':'for-'+suffix,'clipPathUnits':'userSpaceOnUse'})
                E.SubElement(clip,tag('rect'),{'x':str(x),'y':'974','width':str(width),'height':'116'})
                attrs={'clip-path':'url(#for-'+suffix+')'}
                if suffix=='pink':attrs['filter']='url(#caption-shadow)'
                group=E.SubElement(g,tag('g'),attrs)
                for child in children:
                    node=copy.deepcopy(child)
                    if suffix=='pink':node.set('fill','url(#for-caption-fill)')
                    group.append(node)
        else:
            for child in children:g.append(child)
        svg.append(g)
    panel = nodes['subscription-panel']; at = list(svg).index(panel); svg.remove(panel)
    # El sello de escala2 cruza los bordes enF88, igual que CLONE.
    camera = E.Element(tag('g'),{'id':'panel-camera','data-layout-allow-overflow':''}); shake = E.SubElement(camera,tag('g'),{'id':'panel-shake'})
    shake.append(panel);svg.insert(at,camera)
    stamp = E.SubElement(panel,tag('g'),{'id':'stamp-motion','opacity':'0'})
    for ident in ['stamp-glow','cancel-stamp']:
        panel.remove(nodes[ident]);stamp.append(nodes[ident])
    nodes['stamp-lettering'].set('data-layout-allow-overflow','')
    # Reveals aislados del push-in; conservan intacta la geometría interior.
    for i,name in enumerate(['notion','spotify','canva','duolingo','calendly','headspace']):
        top=259.5+97.5*i
        clip=E.SubElement(defs,tag('clipPath'),{'id':'row-mask-'+name,'clipPathUnits':'userSpaceOnUse'})
        E.SubElement(clip,tag('rect'),{'x':'68','y':str(top-5),'width':'585','height':'106','rx':'23'})
        row=nodes['row-'+name];parent=nodes['subscriptions'];idx=list(parent).index(row);parent.remove(row)
        wrapper=E.Element(tag('g'),{'id':'reveal-'+name,'clip-path':'url(#row-mask-'+name+')'})
        wrapper.append(row);parent.insert(idx,wrapper)
        if i>0:row.set('opacity','0')
    nodes['subscriptions'].set('opacity','1')
    nodes['cost'].set('fill','#f5f5f6')
    for i in range(6):
        nodes['cancel-line-'+str(i)].set('stroke-dasharray','540')
        nodes['cancel-line-'+str(i)].set('stroke-dashoffset','540')
    # El desenfoque de movimiento es temporal y local; nunca relleno de fondo.
    blur=E.SubElement(defs,tag('filter'),{'id':'caption-motion-blur','x':'-30%','y':'-100%','width':'160%','height':'300%'})
    E.SubElement(blur,tag('feGaussianBlur'),{'id':'caption-blur-value','stdDeviation':'0'})
    caption=E.Element(tag('g'),{'id':'caption-camera'})
    for ident in ['caption-without','caption-for','editorial-caption']:
        node=next(e for e in svg if e.get('id')==ident);svg.remove(node);caption.append(node)
        if ident!='caption-without':node.set('opacity','0')
    svg.append(caption)
    E.SubElement(svg,tag('rect'),{'id':'impact-flash','width':'720','height':'1280','fill':'#ffffff','opacity':'0'})
    body=E.tostring(svg,encoding='unicode')
    # Recursos ya instalados, empaquetados de forma local y portable.
    gsap = ROOT/'recursos/gsap.min.js'
    dest = HERE/'assets/gsap.min.js'
    if not dest.exists():dest.write_bytes(gsap.read_bytes())
    timeline=(HERE/'timeline.gsap.js').read_text()
    gsap_embedded=base64.b64encode(dest.read_bytes()).decode()
    html='''<!doctype html><html><head><meta charset="utf-8"><title>CLONE — componente aprobado animado</title>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#000}#clone-motion{width:100%;height:100%;position:relative}svg{display:block;width:100%;height:100%}</style>
</head><body><div id="clone-motion" data-composition-id="clone-motion" data-width="1080" data-height="1920" data-duration="1.6">'''+body+'''</div><script src="data:text/javascript;base64,'''+gsap_embedded+'''"></script><script>'''+timeline+'''</script></body></html>'''
    (HERE/'index.html').write_text(html)
    (HERE/'animacion.html').unlink(missing_ok=True)
    print('Composición derivada creada; SVG/PNG aprobados intactos.')
if __name__=='__main__':build()
