"""Preparación concreta del storyboard de Agent Reach V4. No inventa futuros reels."""
import sys,zipfile,csv
sys.dont_write_bytecode=True
import workflow as w

ID='demo_montaje_v4'
F='proyectos/'+ID

def preparar():
    from preflight import require_ready
    require_ready()
    baseline=w.inside('.estado/tmp/base_v3.zip')
    if not baseline.exists():
        with zipfile.ZipFile(baseline,'w',zipfile.ZIP_DEFLATED) as z:
            for name in [F+'/proyecto.json',F+'/index.html',F+'/motion.js',F+'/seleccion_recursos.json','sistema/motion.js']:
                z.write(w.inside(name),name)
    p=w.read_json(F+'/proyecto.json')
    p['manual']=w.manual();p['etapa']='prueba_v4_pendiente_revision_usuario'
    p['requiere_aprobacion_prueba_v4']=True
    p['aprobacion_usuario_prueba']={'estado':'pendiente','motivo':'El usuario exige revisar y aprobar los primeros 10 s antes del completo'}
    p['muestra_nombre']='prueba_ascendia_v4_10s.mp4';p['final_nombre']='final_ascendia_v4.mp4'
    p['muestra']={'estado':'pendiente_render','duracion_s':10}
    p['motor'].update(alcance_hasta_s=10,captura_cpu=True,animacion='HyperFrames + GSAP: capas, máscaras, rutas SVG, morph y cámara interna',runtime='sistema/motion.js')
    specs=[('v4_hook',0,.62,'oscuro','La herramienta de ejemplo','Identidad y titular cinético integrado'),
           ('v4_lectura',.62,2.84,'oscuro','organiza los datos de entrada','Lectura web auténtica → expansión → titular integrado'),
           ('v4_trabajo',2.84,4.25,'oscuro','selecciona una fuente de muestra','Trabajo digital real → monitor se convierte en página editorial'),
           ('v4_fuentes',4.25,6.32,'claro','Fuente A y fuente B','Barrido de campos → extracción por trayectorias → morph perfil/video/post → reunión de fuentes'),
           ('v4_coste',6.32,8.08,'claro','datos preparados para el resultado de ejemplo','Fuentes se reúnen → contorno documento se transforma en cero → cero se convierte en lente'),
           ('v4_contraste',8.08,8.8,'oscuro','La herramienta advierte','Lente se transforma → provocación editorial roja → abre lectura real'),
           ('v4_claude',8.8,10,'oscuro','el asistente prepara el resultado','Ventana auténtica de lectura web → reencuadre interno → Claude lee la web')]
    later=[s for s in p['escenas'] if s['fin']>10]
    if later and later[0]['inicio']<10:later[0]['inicio']=10
    for s in later:s['estado']='pendiente_reconstruccion_v4'
    p['escenas']=[dict(id=i,inicio=a,fin=b,fondo=f,frase=n,objetivo=o,estado='pendiente_revision_prueba') for i,a,b,f,n,o in specs]+later
    p['presentador']=[{'inicio':0,'fin':1.86,'modo':'completo','split_desde':.62,'split_proporcion_superior':.60,'zoom':.23,'zoom_duracion':.20,'zoom_escala':1.08}]
    p['subtitulos']=[]
    p['texto_editorial']=[{'inicio':.08,'fin':.62,'texto':'UNA SKILL','tipo':'titular_hook'},
                        {'inicio':.62,'fin':1.86,'texto':'Claude','tipo':'titular_integrado'},
                        {'inicio':1.86,'fin':2.84,'texto':'TODO INTERNET','tipo':'titular_hook'},
                        {'inicio':6.32,'fin':7.92,'texto':'$0 · sin gastar','tipo':'resultado_tipografico'},
                        {'inicio':8.08,'fin':9.12,'texto':'Aviso de EJEMPLO','tipo':'provocacion_editorial','rojo':'EJEMPLO'}]
    p['broll']=[dict(id='webHook',inicio=.62,fin=2.84,offset=4.2,archivo='assets/broll/Claude_lectura_web.mp4'),
               dict(id='work',inicio=2.84,fin=4.25,offset=.3,archivo='assets/broll/Trabajo_pantalla.mp4'),
               dict(id='webFinal',inicio=8.8,fin=10,offset=4.2,archivo='assets/broll/Claude_lectura_web.mp4')]
    p['recursos']=[{'archivo':a} for a in ['assets/broll/Claude_lectura_web.mp4','assets/broll/Trabajo_pantalla.mp4','recursos/Riser_1.wav','recursos/Woosh_Effect_1.wav','recursos/Lovibe_A_Good_Man.mp3','recursos/Burn_01.mp4','recursos/gsap.min.js']]
    p['audio']['voz']={'procesamiento':'original_sin_procesar','fuente':p['original']['archivo'],'conservacion':'Sin cortes nuevos, estiramiento temporal, transcripción nueva ni filtros de voz'}
    p['audio']['musica']['ganancia_db']=-26
    p['audio']['efectos']=[dict(archivo='recursos/Riser_1.wav',inicio=1.1,impacto_visual=2.84,ganancia_db=-24),dict(archivo='recursos/Woosh_Effect_1.wav',inicio=3.72,impacto_visual=4.0,ganancia_db=-29),dict(archivo='recursos/Woosh_Effect_1.wav',inicio=8.53,impacto_visual=8.8,ganancia_db=-29)]
    p['decisiones']={'directiva':'ASCENDIA V4.0','alcance':'Primeros 10 s; resto pendiente de reconstrucción y aprobación',
        'presencia_s':1.86,'presencia_proporcion':.186,'maximo_presencia_continua_s':1.86,
        'split_proporciones':[.60,.40],'fondo_inferior':'Una sola grabación original; sin copia, blur o relleno',
        'categorias_dominantes_s':{'presentador':1.86,'broll_real':3.59,'motion':4.55},
        'broll_visible_incluido_split_s':4.83,'solapamiento_presentador_broll_s':1.24,
        'rojo':'Solo EJEMPLO, provocación pronunciada. No representa reacción verificada de Google.',
        'fuente_web':'Web Fetch Calendly real; no acredita scraping de LinkedIn ni ejecución de Agent Reach'}
    p['motion_graphics']=[s[-1] for s in specs]
    w.write_json(F+'/proyecto.json',p)
    candidates=w.read_json('.estado/tmp/recursos_v4.json')['candidatos_descargados']
    selected=[c for c in candidates if c.get('archivo') in ['assets/broll/Claude_lectura_web.mp4','assets/broll/Trabajo_pantalla.mp4']]
    inventory=w.read_json('recursos/inventario_drive.json');catalog=w.read_json('recursos/catalogo.json')
    converted={}
    for c in selected:
        evidence=[c['evidencia_secuencia']]+c.get('evidencias_adicionales',[])
        analysis={'estado':'revisado','contenido_observado':c['contenido_visual'],'evidencias':evidence,'limite':c['justificacion']}
        cc={'drive_id':c['id'],'archivo':c['archivo'],'sha256':w.digest(c['archivo']),'motivo_contextual':c['justificacion'],'analisis_visual':analysis}
        converted[c['archivo']]=cc
        catalog['archivos']['BROLL_'+c['md5_origen']]={**cc,'id':c['id'],'md5_origen':c['md5_origen'],'origen':c['fuente_original'],'metadata':w.probe(c['archivo']),'rol':inventory['elementos'][c['id']]['rol'],'derechos':'Recurso del cliente autorizado para esta edición; sin atribuir otra licencia','estado':'verificado_para_prueba_v4'}
        inv=inventory['elementos'][c['id']];inv['acceso']['descarga_binaria_comprobada']=True
        inv['contenido']={'estado':'inspeccionado_para_prueba_v4','observaciones':c['contenido_visual'],'evidencias':evidence}
    w.write_json('recursos/catalogo.json',catalog);w.write_json('recursos/inventario_drive.json',inventory)
    folders=['CONFIGURE_RECURSO_1090','CONFIGURE_RECURSO_1497','CONFIGURE_RECURSO_0704']
    blocks=[]
    for i,a,b,f,n,o in specs:
        choice={'tipo':'motion','motivo_contextual':o,'resultado_busqueda':'Claude Web Fetch y trabajo digital verificados. No hay ejecución auténtica comprobada de las cuatro plataformas; un esquema editorial explica la reunión de fuentes sin simular esa prueba.'}
        if i in ['v4_lectura','v4_claude','v4_trabajo']:
            file='assets/broll/Trabajo_pantalla.mp4' if i=='v4_trabajo' else 'assets/broll/Claude_lectura_web.mp4'
            offset=.3 if i=='v4_trabajo' else 4.2
            choice={'tipo':'broll','drive_id':converted[file]['drive_id'],'tramo_s':[offset,offset+b-a],'motivo_contextual':converted[file]['motivo_contextual']}
        if i=='v4_hook':choice={'tipo':'presentador','motivo_contextual':o,'resultado_busqueda':'Hook personal breve seguido inmediatamente de Web Fetch real; reproduce identidad de las referencias sin transcribir todas las palabras'}
        blocks.append(dict(escena_id=i,inicio=a,fin=b,narracion=n,intencion=o,carpetas_consultadas=folders,candidatos=list(converted.values()),decision=choice))
    w.write_json(F+'/seleccion_recursos.json',dict(proyecto_id=ID,estado='revisada_para_prueba',alcance_hasta_s=10,manual=w.manual(),inventario_sha256=w.digest('recursos/inventario_drive.json'),bibliotecas_consultadas=['CONFIGURE_RECURSO_1792','CONFIGURE_RECURSO_1351'],bloques=blocks,resto='Pendiente de selección final después de aprobar la prueba'))
    with w.inside(F+'/broll_manifest.csv').open('w',newline='',encoding='utf-8-sig') as f:
        csvout=csv.writer(f);csvout.writerow(['Archivo','Ruta local','Fuente original','Duración','Contenido visual','Frase a la que corresponde','Tiempo previsto de utilización','Tiempo realmente utilizado','Estado de verificación'])
        for c in selected:
            clips=[x for x in p['broll'] if x['archivo']==c['archivo']]
            csvout.writerow([c['name'],c['archivo'],c['fuente_original'],c['metadata_local']['duracion'],c['contenido_visual'],'Lectura web de Claude' if c['categoria']=='claude' else 'Trabajo digital y páginas web','; '.join(f"{x['inicio']:.2f}–{x['fin']:.2f}s (fuente {x['offset']:.2f}s)" for x in clips),'0; pendiente render','Recurso visto; aparición en render pendiente'])
    w.require_current_instructions(p);w.require_resource_selection(p,hasta=10)
    print('Storyboard y selección de 10 s preparados; completo bloqueado')

if __name__=='__main__':preparar()
