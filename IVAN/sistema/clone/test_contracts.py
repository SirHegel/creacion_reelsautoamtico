"""Pruebas del contrato y variaciones de contenido, no de detalles internos."""
import copy,json,pathlib,sys
sys.dont_write_bytecode=True
import engine as e

def variants():
    reports=[]
    for d in e.catalog():
        ident=d['id'];p=copy.deepcopy(d['defaults']);lo,hi=d['durationRange']
        ref=d['reference'];dur=ref[0]['exit_s']-ref[0]['entry_s'] if ref else 3
        dur=round(min(hi,max(lo,dur*1.35))*30)/30
        if 'caption'in p:p['caption']='UNA IDEA, VARIOS ESTADOS'
        if ident=='cancelled':p['final_price']=999
        if ident=='apps_clone_orbit':p.update(main='app_uber',satellites=['app_airbnb','app_notion'],badge='VARIANTE')
        if ident=='pixel_agents':p.update(roles=[{'role':'recon','label':'/ investigación'},{'role':'test','label':'/ revisión'},{'role':'deploy','label':'/ entrega'}],count=3,result='RESULTADO COORDINADO')
        if ident=='spotlight_agent':p.update(role='design',title='/ diseño de producto',goal='ACLARAR UNA IDEA')
        if ident=='agent_marquee':p.update(roles=['recon','test','deploy'],direction='right',cta='Revisa el proceso',highlight='test')
        if ident.startswith('phone_'):p['caption']='ENTRADA → ACCIÓN → RESULTADO'
        if ident in ('phone_recon','phone_rebuild','phone_qa'):p.update(appName='Equipo de prueba',title='Reserva una consulta')
        if ident=='phone_compare':p.update(score=73,metricLabel='DATO SINTÉTICO DE PRUEBA',apps=[{'name':'Airbnb','asset':'app_airbnb'},{'name':'Uber','asset':'app_uber'}])
        if ident=='problem_resolution':p.update(appName='Prueba de encaje',features=[{'problem':'Falta seguimiento','feature':'Seguimiento'},{'problem':'Falta información','feature':'Información'}],result='2 estados revisados')
        if ident=='github_cards':p.update(repository='componente-reutilizable',owner='equipo-de-prueba',forks=999,stars='2.4k',badge='DATOS DE PRUEBA',about='Una composición editable adapta nombres, cifras y párrafos más largos sin perder su estructura. Esta variante comprueba el encaje del contenido y las transformaciones del panel.')
        if ident=='product_card':p.update(appName='Producto de prueba',description='Contenido más largo para revisar el encaje',rating='TEST',price='TEST',status='TEST',domain='ejemplo.test')
        if ident=='radial_research':p.update(count=999,metric='entradas de prueba',sources=[{'asset':'app_reddit','label':'Reddit'},{'asset':'app_store','label':'App Store'}])
        if ident=='feedback_bars':p.update(categories=[{'label':'Revisión A','value':999,'color':'#d77357'},{'label':'Revisión B','value':11,'color':'#e99b22'}],reviews=[{'asset':'app_store','text':'Una observación contextual de prueba.','tag':'PRUEBA'},{'asset':'app_reddit','text':'Otra observación permite evaluar el encaje.','tag':'PRUEBA'}])
        if ident=='terminal_install':p.update(command='https://ejemplo.test/proyecto/con-una-ruta-larga-para-verificar-la-escritura',instruction='revisar el proceso',roles=['recon','test','deploy'],packageLabel='Componentes de prueba',result='Listo · representación conceptual',showRoleLabels=True)
        spec={'schema_version':1,'test_only':True,'scenes':[{'id':ident+'_variant','family':ident,'duration':dur,'content':'Contenido sintético para comprobar encaje y reutilización; no describe resultados auténticos.','objective':'Cambiar contenido, duración y número de elementos manteniendo la composición.','params':p}]}
        folder='.estado/tmp/clone_variants/'+ident
        try:e.compile_spec(spec,folder);reports.append({'family':ident,'ok':True,'folder':folder})
        except Exception as error:reports.append({'family':ident,'ok':False,'error':str(error)})
    e.write('proyectos/clone_motor/variantes_contrato.json',reports)
    return reports

def rejection_tests():
    valid={'schema_version':1,'scenes':[{'id':'test','family':'apps_clone_orbit','duration':2,'content':'Una app se duplica','objective':'Mostrar la transformación','params':{}}]}
    tests=[]
    def reject(name,mutate):
        item=copy.deepcopy(valid);mutate(item)
        try:e.validate_spec(item);tests.append({'name':name,'rejected':False})
        except ValueError as error:tests.append({'name':name,'rejected':True,'reason':str(error)})
    reject('superposición',lambda s:s['scenes'].append({**s['scenes'][0],'id':'another','start':1}))
    reject('ID repetido',lambda s:s['scenes'].append(copy.deepcopy(s['scenes'][0])))
    reject('familia desconocida',lambda s:s['scenes'][0].update(family='fake'))
    reject('tiempo no finito',lambda s:s['scenes'][0].update(duration=float('nan')))
    reject('no alineado a frames',lambda s:s['scenes'][0].update(duration=2.012))
    reject('parámetro inexistente',lambda s:s['scenes'][0]['params'].update(unknown='dato'))
    reject('entrada fuera del intervalo',lambda s:s['scenes'][0].update(actions=[{'at':1.9,'duration':.5}]))
    reject('código en datos',lambda s:s['scenes'][0]['params'].update(main={'javascript':'alert(1)'}))
    reject('duración fuera de familia',lambda s:s['scenes'][0].update(duration=90))
    e.write('proyectos/clone_motor/contratos_rechazos.json',tests)
    if not all(t['rejected']for t in tests):raise AssertionError('Entrada inválida aceptada')
    return tests

if __name__=='__main__':
    rejected=rejection_tests();cases=variants()
    print(json.dumps({'invalid_rejected':len(rejected),'variants':len(cases),'compiled':sum(c['ok']for c in cases)},ensure_ascii=False))
