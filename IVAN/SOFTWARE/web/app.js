'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const clone = value => structuredClone(value);
  const uid = prefix => `${prefix}_${crypto.randomUUID().slice(0, 12)}`;
  const fmt = (value, precise = true) => {
    const n = Math.max(0, num(value));
    return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(Math.floor(n % 60)).padStart(2, '0')}${precise ? '.' + String(Math.floor((n % 1) * 1000)).padStart(3, '0') : ''}`;
  };
  const lines = value => String(value || '').split('\n').map(s => s.trim()).filter(Boolean);
  const state = {project: null, projects: [], assets: [], templates: [], status: null, jobs: [], mediaTools: null, selectedScene: null, selectedElement:null, selectedPathPoint:null, motionAutokey:true, motionPlayers:new Map(), selectedAsset: null, dirty: false, editEpoch:0, loadEpoch:0, history: [], redo: [], time: 0, playing: false, mode: 'timeline', zoom: 70, filter: 'all', safe: true, sourceId: null, brollId: null, transitionId: null, imageCache: new Map(), audioPlayers: new Map(), overlayPlayers:new Map(), pollBusy: false, saving: false, jobSeen: new Map(), fontsLoaded: false, fontLibrary:null, fontLibraryEpoch:0, fontLoads:new Map(), textPresets:null, textLayouts:new Map(), textLayoutQueue:[], textLayoutBusy:false};
  const canvas = $('preview-canvas'), source = $('source-video'), broll = $('broll-video'), presenter = $('presenter-video'), transition = $('transition-video');
  let ctx=canvas.getContext('2d');
  let lastTick = performance.now(), lastDraw = 0, sourceReady = false, manualCache = null;

  const SaaS=/^(?:\/w\/[^/]+)?\/editor\/?$/.test(location.pathname),sessionRequests=new Set(),sessionUploads=new Set(),sessionFaces=new Set(),sessionBlobs=new Set();
  let identity=null,identityEpoch=0,jobPollTimer=null,sessionChannel=null,sharedObserver=null;
  const identityScope=()=>({epoch:identityEpoch,workspace:identity?.workspace?.id,actorWorkspace:identity?.actor_workspace?.id||identity?.workspace?.id,user:identity?.user?.id});
  const identityCurrent=scope=>!SaaS||scope.epoch===identityEpoch&&scope.workspace===identity?.workspace?.id&&scope.actorWorkspace===(identity?.actor_workspace?.id||identity?.workspace?.id)&&scope.user===identity?.user?.id;
  const isShared=()=>Boolean(state.sharedContext?.access?.shared);
  const canEdit=()=>!isShared()||state.sharedContext.access.role==='editor'&&state.sharedContext.access.can_edit===true;
  function namespaceURL(path,scope=identityScope()){
    if(!SaaS)return path;if(!scope.workspace)throw new DOMException('Entra de nuevo para abrir tu estudio.','AbortError');
    const url=new URL(path,location.origin),prefix='/w/'+encodeURIComponent(scope.workspace);if(url.origin!==location.origin)throw new Error('El recurso debe pertenecer a tu espacio.');
    if(url.pathname.startsWith('/api/auth/'))return url.pathname+url.search;
    if(url.pathname.startsWith('/w/')){if(!url.pathname.startsWith(prefix+'/'))throw new DOMException('El espacio cambió.','AbortError');}
    else if(url.pathname.startsWith('/api/'))url.pathname=prefix+url.pathname;
    if(isShared()&&/^\/w\/[^/]+\/api\/(?:media\/|files\/|fonts\/|font-notices\/)/.test(url.pathname)){url.searchParams.set('project_id',state.sharedContext.access.project_id);url.searchParams.set('actor_workspace_id',scope.actorWorkspace);}
    return url.pathname+url.search;
  }
  function preferenceKey(){return SaaS?'ascendia.project.'+identity.user.id+'.'+identity.workspace.id:'ascendia.project';}
  function clearSessionData(){
    identityEpoch++;identity=null;clearInterval(jobPollTimer);sharedObserver?.disconnect();sharedObserver=null;$('shared-project-banner')?.remove();document.body.classList.remove('shared-readonly','has-shared-project');for(const request of sessionRequests)request.abort();sessionRequests.clear();for(const xhr of sessionUploads)xhr.abort();sessionUploads.clear();pause();
    for(const media of new Set([...document.querySelectorAll('video,audio'),...state.audioPlayers.values(),...state.overlayPlayers.values(),...state.motionPlayers.values()])){media.pause();media.onloadedmetadata=null;media.onloadeddata=null;media.onerror=null;media.removeAttribute('src');media.load();}
    for(const url of sessionBlobs)URL.revokeObjectURL(url);sessionBlobs.clear();for(const face of sessionFaces)document.fonts.delete(face);sessionFaces.clear();for(const entry of state.fontLoads.values())if(entry.face)document.fonts.delete(entry.face);state.fontLoads.clear();state.imageCache.forEach(image=>{image.onload=null;image.removeAttribute('src');});state.imageCache.clear();state.sharedContext=null;
    state.audioPlayers.clear();state.overlayPlayers.clear();state.motionPlayers.clear();$('audio-engine').replaceChildren();state.project=null;state.projects=[];state.assets=[];state.jobs=[];state.history=[];state.redo=[];state.jobSeen.clear();state.textLayouts.clear();state.textLayoutQueue=[];state.textLayoutBusy=false;state.fontLibrary=null;state.fontLibraryEpoch++;state.roleFonts={};state.roleFontKey=null;state.roleFontPending=null;state.fontsLoaded=false;state.dirty=false;state.selectedScene=null;state.selectedElement=null;state.selectedPathPoint=null;state.selectedAsset=null;state.sourceId=null;state.brollId=null;state.transitionId=null;state.time=0;state.status=null;state.templates=[];state.textPresets=null;state.mediaTools=null;state.fontModalScope=null;state.assetModalScope=null;state.voiceModalScope=null;state.trackingOverlay=false;state.loadEpoch++;state.editEpoch++;sourceReady=false;manualCache=null;
    state.mode='timeline';viewCtx.clearRect(0,0,canvas.width,canvas.height);baseCtx.clearRect(0,0,baseCanvas.width,baseCanvas.height);
    if($('modal').open)$('modal').close();$('modal-content').replaceChildren();$('project-select').innerHTML='<option value="">Seleccionar proyecto</option>';$('validation-results').replaceChildren();$('job-progress').hidden=true;renderProject();
    for(const input of document.querySelectorAll('#scene-form input,#scene-form textarea')){if(input.type==='checkbox')input.checked=false;else input.value='';}for(const id of ['motion-element-inspector','motion-elements-list','keyframes-list','overlay-list','scene-asset','scene-transition'])$(id).replaceChildren();
  }
  function expiredSession(message='La sesión o el espacio cambió. Vuelve a entrar.'){clearSessionData();$('connection-label').textContent='Sesión cerrada';$('studio-session-message').textContent=message;$('studio-session-banner').hidden=false;document.querySelector('.studio').hidden=true;}
  function roleRecord(role){if(SaaS){const selected=state.project?.style?.branding?.fonts?.[role],id=typeof selected==='string'?selected:selected?.asset_id||selected?.id;if(id){const font=fontRecord(id);if(font)return font;const asset=assetById(id);if(asset)return {...asset.metadata?.font_info,sha256:asset.sha256,name:asset.name};}}return state.fontLibrary?.roles?.find(font=>font.role===role);}
  function roleName(role){const record=roleRecord(role);return SaaS?record?.full_name||record?.family||record?.name||'Fuente de marca':role==='accent'?'Scholar Italic':'Sequel Sans Bold Disp';}
  function roleFamily(role){return SaaS?state.roleFonts?.[role]?.family:role==='accent'?'Scholar':'Sequel';}
  function roleItalic(role){return SaaS?fontItalic(roleRecord(role)):role==='accent';}
  function roleCSS(role,size){return `${roleItalic(role)?'italic ':''}${size}px "${roleFamily(role)}"`;}
  function projectRoleKey(){return JSON.stringify([identityEpoch,state.project?.id,state.project?.fonts,state.project?.style?.branding?.fonts]);}
  async function loadProjectRoleFonts(){
    if(!SaaS||!identity||!state.project)return;const key=projectRoleKey();if(state.roleFontKey===key&&state.fontsLoaded)return;if(state.roleFontPending?.key===key)return state.roleFontPending.promise;
    const scope=identityScope(),pid=state.project.id,previous=state.roleFonts;state.roleFontKey=key;state.fontsLoaded=false;state.roleFonts={};const pending={key,promise:null};state.roleFontPending=pending;
    pending.promise=(async()=>{try{
      const faces=await Promise.all(['primary','accent'].map(async role=>{const metadata=roleRecord(role),family='AscendiaRole_'+scope.actorWorkspace.replace(/\W/g,'_')+'_'+scope.workspace.replace(/\W/g,'_')+'_'+pid+'_'+role+'_'+(metadata?.sha256||'').slice(0,12),face=new FontFace(family,`url("${namespaceURL('/api/fonts/'+role+'?project_id='+encodeURIComponent(pid),scope)}")`,{style:fontItalic(metadata)?'italic':'normal'});await face.load();return {role,family,face};}));
      if(!identityCurrent(scope)||state.project?.id!==pid||projectRoleKey()!==key)throw new DOMException('La selección cambió.','AbortError');
      for(const old of Object.values(previous||{})){document.fonts.delete(old.face);sessionFaces.delete(old.face);}for(const item of faces){document.fonts.add(item.face);sessionFaces.add(item.face);}state.roleFonts=Object.fromEntries(faces.map(face=>[face.role,face]));state.fontsLoaded=true;renderInspector();drawPreview();
    }finally{if(state.roleFontPending===pending)state.roleFontPending=null;}})();return pending.promise;
  }
  async function initializeIdentity(){
    if(!SaaS)return true;const response=await fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'}),data=await response.json(),expected=new URLSearchParams(location.search).get('workspace');
    if(!data.authenticated||!expected){location.replace('/portal');return false;}identity=data;
    const banner=document.createElement('div');banner.id='studio-session-banner';banner.hidden=true;banner.innerHTML='<span id="studio-session-message"></span> <a href="/portal">Volver a mi estudio</a>';document.body.prepend(banner);
    if(expected!==identity.workspace.id){
      const pid=new URLSearchParams(location.search).get('project');if(!pid){expiredSession('Elige un proyecto compartido desde tu estudio.');return false;}
      const response=await fetch('/w/'+encodeURIComponent(expected)+'/api/projects/'+encodeURIComponent(pid)+'/editor-context',{headers:{'X-Workspace-ID':data.workspace.id},credentials:'same-origin',cache:'no-store'});
      if(!response.ok){expiredSession('El proyecto compartido no está disponible para tu cuenta.');return false;}
      const shared=await response.json(),access=shared.access;if(access?.shared!==true||access.actor_workspace_id!==data.workspace.id||access.owner_workspace_id!==expected||access.project_id!==pid||!['viewer','editor'].includes(access.role)){expiredSession('El servidor no confirmó el permiso de este proyecto.');return false;}
      state.sharedContext=shared;identity={...data,actor_workspace:data.workspace,workspace:{id:expected,name:shared.project?.name||'Proyecto compartido'}};
    }
    for(const sheet of document.styleSheets){try{for(let i=sheet.cssRules.length-1;i>=0;i--)if(sheet.cssRules[i].type===CSSRule.FONT_FACE_RULE)sheet.deleteRule(i);}catch{}}
    document.body.classList.add('saas-editor');document.querySelector('.brand').href='/portal';$('render-project').innerHTML=icon('film')+'Exportar video';$('read-manual').textContent='Leer perfil editorial completo';document.querySelector('#tab-style .panel-description').textContent='La base Iván define cámara, subtítulos, split y motion. Lee el perfil del software y revisa tus decisiones y tu marca en este proyecto.';document.querySelector('#tab-style .note span').textContent='Base Iván: YO para cámara, subtítulos y split; CLONE para motion. Tu marca define colores, logo y fuentes de este proyecto. La prueba queda pendiente de revisión.';const controls=document.createElement('span');controls.className='studio-session-controls';controls.innerHTML='<a class="icon-button" href="/portal" title="Mi estudio" aria-label="Volver a mi estudio">⌂</a><button class="icon-button" id="studio-logout" title="Cerrar sesión" aria-label="Cerrar sesión">↪</button>';document.querySelector('.top-actions').append(controls);
    $('studio-logout').onclick=()=>guardUnsaved(async()=>{await api('/api/auth/logout',{method:'POST',body:{}});sessionChannel?.postMessage({type:'session-changed'});clearSessionData();location.replace('/portal');});
    if(typeof BroadcastChannel==='function'){sessionChannel=new BroadcastChannel('ascendia.session');sessionChannel.onmessage=event=>{if(event.data?.type==='session-changed'&&identity)expiredSession();};}
    window.addEventListener('pagehide',()=>clearSessionData());window.addEventListener('pageshow',event=>{if(event.persisted)expiredSession();});if(isShared()){document.body.classList.add('has-shared-project');const notice=document.createElement('div');notice.id='shared-project-banner';notice.setAttribute('role','status');document.querySelector('.topbar').after(notice);sharedObserver=new MutationObserver(()=>queueMicrotask(applySharedControls));sharedObserver.observe(document.querySelector('.studio'),{childList:true,subtree:true});sharedObserver.observe($('modal-content'),{childList:true,subtree:true});applySharedControls();}return true;
  }
  async function api(path, options = {}) {
    const scope=identityScope(),controller=new AbortController(),request={...options,headers:{...options.headers}};
    if(SaaS){if(!identity)throw new DOMException('La sesión terminó.','AbortError');request.credentials='same-origin';request.cache='no-store';request.headers['X-Workspace-ID']=scope.actorWorkspace;if(request.method&&!['GET','HEAD'].includes(request.method))request.headers['X-CSRF-Token']=identity.csrf_token;request.signal=controller.signal;sessionRequests.add(controller);}
    if(isShared()){
      const shared=state.sharedContext,route=new URL(path,location.origin).pathname,method=request.method||'GET',pid=shared.access.project_id;
      if(method==='GET'){const snapshots={'/api/status':shared.status,'/api/projects':{projects:[shared.project]},'/api/assets':{assets:shared.assets||[]},'/api/font-library':shared.font_library,'/api/templates':{templates:shared.templates?.templates||shared.templates||[]},'/api/text-presets':Array.isArray(shared.text_presets)?{presets:shared.text_presets}:shared.text_presets,'/api/manual':shared.manual,'/api/jobs':{jobs:shared.jobs||[]},'/api/media-tools':{operations:[]}};if(Object.hasOwn(snapshots,route)){sessionRequests.delete(controller);return clone(snapshots[route]||{});}}
      else{const permitted=method==='POST'&&route==='/api/auth/logout'||method==='POST'&&route==='/api/text-layout'&&options.body?.project_id===pid||method==='POST'&&route===`/api/projects/${pid}/export`||method==='PUT'&&route===`/api/projects/${pid}`&&canEdit()||method==='POST'&&route===`/api/projects/${pid}/render`&&canEdit()&&shared.access.can_render===true&&options.body?.technical===true;
        if(!permitted){sessionRequests.delete(controller);throw new Error('Tu acceso compartido no permite esta acción. La persona propietaria gestiona recursos, automatización y revisiones.');}
      }
    }
    if(request.body&&typeof request.body!=='string'&&!(request.body instanceof Blob)){request.body=JSON.stringify(request.body);request.headers['Content-Type']='application/json';}
    try{const response=await fetch(namespaceURL(path,scope),request),contentType=response.headers.get('Content-Type')||'',result=contentType.includes('json')?await response.json():await response.text();if(!identityCurrent(scope))throw new DOMException('La sesión cambió.','AbortError');
      if(!response.ok){if(SaaS&&[401,403,409].includes(response.status)&&(isShared()&&response.status===403||/workspace|sesión|session|espacio|cuenta|account|csrf/i.test(String(result.error||''))||response.status===401)){expiredSession(isShared()?'El proyecto compartido ya no está disponible para tu cuenta.':undefined);throw new DOMException('La sesión cambió.','AbortError');}const error=new Error(typeof result==='object'?result.error||result.message||`Error ${response.status}`:result||`Error ${response.status}`);error.status=response.status;error.detail=result;throw error;}return result;
    }finally{sessionRequests.delete(controller);}
  }

  function applySharedControls(){
    if(!isShared())return;const access=state.sharedContext.access,readOnly=!canEdit();document.body.classList.toggle('shared-readonly',readOnly);
    const banner=$('shared-project-banner'),text=`Proyecto compartido · ${readOnly?'solo lectura':'puedes editar'} · ${state.sharedContext.project.name}. ${state.dirty?'Tus cambios locales están pendientes.':'La cronología y los archivos permanecen en el espacio del propietario.'}`;if(banner&&banner.textContent!==text)banner.textContent=text;
    for(const id of ['new-project','import-media','import-audio','import-editable','start-import','analyze-source','automate-project','plan-project','agent-workflow','agent-tasks','track-source','save-identity','snapshot-design','review-design','review-project','import-scene-ir','scene-ir-schema'])if($(id))$(id).disabled=true;
    for(const node of document.querySelectorAll('[data-shared-readonly]'))if(!readOnly){node.disabled=node.dataset.sharedReadonly==='true';delete node.dataset.sharedReadonly;}
    for(const field of document.querySelectorAll('#asset-review-form input,#asset-review-form textarea,#asset-review-form button,#font-upload,#manual-read-check,#record-manual,[data-cancel-job]'))field.disabled=true;
    $('project-select').disabled=true;if(readOnly){for(const id of ['save-project','add-scene','split-scene','undo','redo','create-free-motion','choose-motion-template','edit-words'])if($(id))$(id).disabled=true;for(const field of document.querySelectorAll('#scene-form input,#scene-form select,#scene-form textarea,#scene-form button,#tab-audio input,#tab-audio select,#tab-audio button,#transcript-list input,#transcript-list textarea,#settings-form input,#settings-form select,#settings-form button,[data-motion-delete],#font-apply,[data-use],[data-template]')){if(!Object.hasOwn(field.dataset,'sharedReadonly'))field.dataset.sharedReadonly=String(field.disabled);field.disabled=true;}}
    $('render-project').disabled=!state.project?.source||!canEdit()||access.can_render!==true;$('export-project').disabled=!state.project;
  }

  async function refreshSharedContext(){
    if(!isShared())return;const scope=identityScope(),previous=state.sharedContext,context=await api(`/api/projects/${previous.access.project_id}/editor-context`);if(!identityCurrent(scope))return;
    if(context.access?.shared!==true||context.access?.actor_workspace_id!==scope.actorWorkspace||context.access?.owner_workspace_id!==scope.workspace||context.access?.project_id!==previous.access.project_id||context.project?.id!==previous.access.project_id||!['viewer','editor'].includes(context.access?.role)){expiredSession('El permiso de este proyecto compartido cambió.');return;}
    state.sharedContext=context;state.assets=context.assets||[];state.fontLibrary=context.font_library;state.status=context.status;
    if(state.project&&!state.dirty&&state.project.revision!==context.project.revision)setProject(context.project,false);
    applySharedControls();
  }

  function toast(message, error = false, lifetime = 6000) {
    const node = document.createElement('div');
    node.className = 'toast' + (error ? ' error' : '');
    node.textContent = message;
    $('toast-region').append(node);
    setTimeout(() => node.remove(), lifetime);
  }

  function action(handler) {
    return async event => {
      try { await handler(event); }
      catch (error) { if(error.name==='AbortError')return;console.error(error); toast(error.message, true, 10000); }
    };
  }

  function modal(title, html, bind) {
    $('modal-title').textContent = title;
    $('modal-content').innerHTML = html;
    if (!$('modal').open) $('modal').showModal();
    if (bind) bind($('modal-content'));
  }

  function projectData(result) { return result.project || result; }
  function assetById(id) {
    const attached=state.project?.assets?.find(a=>a.id===id),canonical=state.assets.find(a=>a.id===id);
    if(!attached)return canonical;if(!canonical||canonical.sha256!==attached.sha256)return attached;
    return {...attached,...Object.fromEntries(Object.entries(canonical).filter(([key])=>key.startsWith('preview_')))};
  }
  function assetUrl(asset) { const path=asset?.preview_url||asset?.url||(asset?.id?`/api/media/${encodeURIComponent(asset.id)}`:'');return path?namespaceURL(path):''; }
  function fileUrl(path) { return path ? namespaceURL('/api/files/'+String(path).split('/').map(encodeURIComponent).join('/')) : ''; }
  function thumbnailUrl(asset) { return asset?.thumbnail_url?namespaceURL(asset.thumbnail_url):asset?.thumbnail?.startsWith('/api/')?namespaceURL(asset.thumbnail):fileUrl(asset?.thumbnail); }
  function assetKind(asset) { const kind=asset?.kind; return ['music','sfx'].includes(kind)?'audio':kind==='broll'?'video':kind || (asset?.probe?.streams?.some(s => s.codec_type === 'video') ? 'video' : 'audio'); }
  function evidencePath(asset) { return (asset?.thumbnails?.[0] || asset?.thumbnail || asset?.path || '').replace(/^\/api\/files\//,''); }
  function duration() {
    const p = state.project;
    if (!p) return 0;
    if(p.mode==='scene_ir_component'&&state.mode!=='source')return Math.max(...p.timeline.map(scene=>num(scene.end)),0);
    return Math.max(num(assetById(p.source)?.duration), num(p.duration), ...p.timeline.map(s => num(s.end)), ...p.audio.map(a => num(a.end)), 0);
  }
  function selectedScene() { return state.project?.timeline.find(s => s.id === state.selectedScene); }
  function currentScene() { return state.project?.timeline.find(s => state.time >= num(s.start) && state.time < num(s.end)); }
  function normalizeProject(project) {
    project.timeline ||= [];
    project.audio ||= [];
    project.assets ||= [];
    project.transcript ||= {words: [], segments: []};
    project.transcript.words ||= [];
    project.transcript.segments ||= [];
    project.settings ||= {width: 1080, height: 1920, fps: 30};
    project.reference_review ||= {identity_observations: '', evidence: []};
    for(const scene of project.timeline){
      if(!scene.motion_design)continue;scene.motion_design.canvas||={background:'#101318'};scene.motion_design.canvas.background??='#101318';
      for(const element of scene.motion_design.elements||[]){const defaults={x:0,y:0,width:.25,height:.25,start:0,end:scene.end-scene.start,opacity:1,rotation:0,z:0,color:'#ffffff',radius:0,keyframes:[],mask:{type:'none'}};if(element.type==='text')Object.assign(defaults,{font:'primary',font_size:84});if(element.type==='shape')defaults.shape='rect';if(element.type==='media')defaults.source_in=0;for(const[key,value]of Object.entries(defaults))element[key]??=value;}
    }
    return project;
  }
  function pushHistory() {
    if (!state.project) return;
    state.history.push(clone(state.project));
    if (state.history.length > 60) state.history.shift();
    state.redo.length = 0;
  }
  function dirty() {
    state.dirty = true;
    state.editEpoch++;
    $('save-state').textContent = 'Cambios sin guardar';
    $('save-state').style.color = '#e5ae83';
    $('save-project').disabled = state.saving || !state.project;
    $('undo').disabled = !state.history.length;
    $('redo').disabled = !state.redo.length;
    if (state.project?.review?.approved_preview) state.project.review.approved_preview = false;
  }
  function mutate(fn, inspector = true) {
    if (!state.project) return;
    if(!canEdit()){toast('Este proyecto compartido está en modo de lectura.',true);return;}
    pushHistory();
    fn(state.project);
    cleanMotionPlayers();
    dirty();
    renderTimeline();
    if (inspector) renderInspector();
    renderWorkflow();
    drawPreview();
  }

  async function refreshProjects() {
    const result = await api('/api/projects');
    state.projects = result.projects || [];
    $('project-select').innerHTML = '<option value="">Seleccionar proyecto</option>' + state.projects.map(p => `<option value="${esc(p.id)}">${esc(p.name || p.id)}</option>`).join('');
    if (state.project) $('project-select').value = state.project.id;
  }

  function setProject(project, resetHistory = true) {
    pause();
    const prevSource = state.project?.source,previousId=state.project?.id;
    state.project = normalizeProject(projectData(project));
    if(SaaS&&state.roleFontKey!==projectRoleKey())state.fontsLoaded=false;
    state.dirty = false;
    state.editEpoch++;
    state.loadEpoch++;
    if(previousId!==state.project.id||prevSource!==state.project.source){$('render-video').removeAttribute('src');$('render-video').load();previewMode('timeline');}
    else if(state.mode==='render'&&state.project.renders?.length)previewMode('render');
    if (resetHistory) {state.history = []; state.redo = []; state.selectedScene = null;state.selectedElement=null; state.time = 0;}
    if (prevSource !== state.project.source || state.sourceId !== state.project.source) loadSource();
    renderProject();
    if(SaaS)loadProjectRoleFonts().catch(error=>{if(error.name!=='AbortError')toast(error.message,true);});
    try {localStorage.setItem(preferenceKey(), state.project.id);} catch (_) {}
  }

  async function loadProject(id) {
    if (!id) return;
    const ticket=++state.loadEpoch,result=await api(`/api/projects/${encodeURIComponent(id)}`);
    if(ticket!==state.loadEpoch)return;
    setProject(result);
    $('project-select').value = id;
  }

  async function saveProject() {
    if (!state.project || !state.dirty) return state.project;
    if(!canEdit())throw new Error('El permiso es de lectura. Conserva tus cambios locales antes de recargar.');
    if (state.saving) throw new Error('El proyecto ya se está guardando.');
    state.saving = true;
    $('save-project').disabled=true;
    $('save-state').textContent = 'Guardando…';
    const selection = state.selectedScene, time = state.time,snapshot=clone(state.project),epoch=state.editEpoch;
    try {
      const data = projectData(await api(`/api/projects/${snapshot.id}`, {method: 'PUT', body: snapshot}));
      if(state.project.id!==snapshot.id)return data;
      if(state.editEpoch===epoch){
        state.project=normalizeProject(data);state.dirty=false;renderProject();
      }else{
        state.project.revision=data.revision;state.project.updated_at=data.updated_at;state.project.history=data.history;state.project.review={};state.dirty=true;
        $('save-state').textContent=`Nuevos cambios sin guardar · rev. ${data.revision}`;$('save-state').style.color='#e5ae83';
      }
      return state.project;
    } catch (error) {
      $('save-state').textContent = 'No se pudo guardar';
      if (error.status === 409) {
        error.message = 'Otro agente cambió este proyecto. Conserva tus cambios en JSON o recarga la revisión guardada.';
        const local=clone(state.project);
        modal('Conflicto de revisión','<p class="modal-copy">Otro editor o agente guardó una revisión nueva. Tus cambios siguen en esta sesión. Descarga un respaldo antes de recargar para poder compararlos.</p><div class="modal-actions"><button id="backup-conflict" class="button ghost">Guardar respaldo JSON</button><button id="reload-conflict" class="button primary">Recargar revisión guardada</button></div>',()=>{
          $('backup-conflict').onclick=action(async()=>{let result;if(isShared()){const url=URL.createObjectURL(new Blob([JSON.stringify(local,null,2)],{type:'application/json'}));sessionBlobs.add(url);result={url,path:'memoria de esta sesión'};}else result=await api('/api/backups',{method:'POST',body:{project:local}});let link=$('conflict-backup-link');if(!link){link=document.createElement('a');link.id='conflict-backup-link';link.className='button ghost full';$('modal-content').append(link);}link.href=result.url||fileUrl(result.path);link.download=`${local.id}-cambios-pendientes.json`;link.textContent='Descargar copia del respaldo JSON';toast(`Respaldo preparado en ${result.path}. La revisión canónica se conserva.`);});
          $('reload-conflict').onclick=action(async()=>{const latest=await api(`/api/projects/${local.id}`);setProject(latest);$('modal').close();toast('Revisión guardada recargada. Compara tu respaldo antes de aplicar cambios.');});
        });
      }
      throw error;
    } finally {state.saving=false;$('save-project').disabled=!state.project||!canEdit();}
  }

  function guardUnsaved(next) {
    if (!state.dirty) {Promise.resolve(next()).catch(error=>toast(error.message,true)); return;}
    modal('Cambios pendientes', '<p class="modal-copy">Guarda el proyecto antes de cambiar. También puedes continuar con la última versión guardada.</p><div class="modal-actions"><button id="discard-change" class="button ghost">Descartar cambios</button><button id="save-change" class="button primary">Guardar y continuar</button></div>', () => {
      $('discard-change').onclick = action(async () => {$('modal').close(); state.dirty = false; await next();});
      $('save-change').onclick = action(async () => {await saveProject(); $('modal').close(); await next();});
    });
  }

  function newProjectDialog() {
    modal('Nuevo proyecto', '<p class="modal-copy">Un proyecto conserva su crudo, storyboard, recursos y revisiones en una sola cronología editable.</p><form id="create-project-form" class="modal-form"><label class="field">Nombre del reel<input id="project-name" required maxlength="100" placeholder="Por ejemplo: una idea que vale contar" autofocus></label><div class="modal-actions"><button type="submit" class="button primary">Crear proyecto</button></div></form>', () => {
      $('create-project-form').onsubmit = action(async event => {
        event.preventDefault();
        const name = $('project-name').value.trim();
        if (!name) return;
        const project = await api('/api/projects', {method: 'POST', body: {name}});
        $('modal').close();
        setProject(project);
        await refreshProjects();
        toast('Proyecto creado. Importa tu crudo para comenzar.');
      });
    });
  }

  async function ensureProject(name) {
    if (state.project) return;
    const load=state.loadEpoch,edit=state.editEpoch,project=await api('/api/projects', {method:'POST',body:{name:name.replace(/\.[^.]+$/,'')}});
    if(state.project||state.loadEpoch!==load||state.editEpoch!==edit){await refreshProjects();throw new Error('La selección cambió mientras se creaba el proyecto. El proyecto nuevo está en tu lista.');}
    setProject(project);await refreshProjects();
  }

  function uploadFile(file,endpoint='/api/assets',kind=null) {
    if(isShared())return Promise.reject(new Error('La persona propietaria incorpora los archivos de este proyecto compartido.'));
    return new Promise((resolve, reject) => {
      const scope=identityScope(),xhr = new XMLHttpRequest();
      xhr.open('POST', namespaceURL(endpoint,scope));
      if(SaaS){sessionUploads.add(xhr);xhr.withCredentials=true;xhr.setRequestHeader('X-Workspace-ID',scope.actorWorkspace);xhr.setRequestHeader('X-CSRF-Token',identity.csrf_token);xhr.onabort=()=>{sessionUploads.delete(xhr);reject(new DOMException('La sesión cambió.','AbortError'));};}
      xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
      if(kind)xhr.setRequestHeader('X-Asset-Kind',kind);
      else if (file.type.startsWith('image/')) xhr.setRequestHeader('X-Asset-Kind', 'image');
      else if (file.type.startsWith('audio/')) xhr.setRequestHeader('X-Asset-Kind', 'audio');
      xhr.upload.onprogress = event => {
        if (identityCurrent(scope)&&event.lengthComputable) showJobProgress(`Importando ${file.name}`, event.loaded / event.total);
      };
      xhr.onload = () => {
        sessionUploads.delete(xhr);if(!identityCurrent(scope)){reject(new DOMException('La sesión cambió.','AbortError'));return;}
        let result;
        try {result = JSON.parse(xhr.responseText);} catch (_) {reject(new Error('El servidor devolvió una respuesta inválida.')); return;}
        if (xhr.status >= 200 && xhr.status < 300) resolve(result.asset || result);
        else reject(new Error(result.error || result.message || 'No se pudo importar el archivo.'));
      };
      xhr.onerror = () => {sessionUploads.delete(xhr);reject(new Error('Se perdió la conexión al importar.'));};
      xhr.send(file);
    });
  }

  async function previewSceneIR(file){
    if(!file||!state.project)return;
    const scope={id:state.project.id,revision:state.project.revision,load:state.loadEpoch,edit:state.editEpoch},original=clone(state.project),active=()=>state.project?.id===scope.id&&state.loadEpoch===scope.load&&state.editEpoch===scope.edit&&state.project.revision===scope.revision&&!state.dirty;
    if(state.dirty)throw new Error('Guarda los cambios antes de previsualizar un SceneIR.');
    let document;
    try{
      if(file.size>2*1024*1024)throw new Error('El documento supera el límite de 2 MB.');
      document=JSON.parse(await file.text());
      if(!document||typeof document!=='object'||Array.isArray(document))throw new Error('SceneIR requiere un objeto JSON.');
    }catch(error){$('scene-ir-input').value='';modal('SceneIR no válido',`<p id="scene-ir-preview-errors" class="review-warning">${esc(error instanceof SyntaxError?'El archivo no contiene JSON válido.':error.message)}</p><p class="small-copy">La cronología se conserva. Elige un documento compatible desde Motion.</p>`);return;}
    $('scene-ir-input').value='';if(!active())throw new Error('El proyecto cambió mientras se leía el archivo. Vuelve a importar el documento.');
    let result;
    try{result=await api(`/api/projects/${scope.id}/scene_ir_preview`,{method:'POST',body:{document}});}
    catch(error){if(active())modal('SceneIR no pudo compilarse',`<p id="scene-ir-preview-errors" class="review-warning">${esc(error.message)}</p><p class="small-copy">La cronología no se reemplazó. Corrige el documento y vuelve a previsualizarlo.</p>`);return;}
    if(!active())throw new Error('El proyecto o su revisión cambió durante la compilación. Vuelve a previsualizar el documento.');
    const proposed=result.project;if(!proposed||proposed.id!==scope.id||!Array.isArray(proposed.timeline))throw new Error('La compilación no devolvió una cronología para este proyecto.');
    const validation=result.validation||{},messages=value=>(Array.isArray(value)?value:[]).map(item=>typeof item==='string'?item:item.message||JSON.stringify(item)),errors=messages(validation.errors),warnings=[...messages(result.warnings),...messages(validation.warnings)],canApply=result.can_apply!==false;
    const span=proposed.timeline.reduce((end,scene)=>Math.max(end,num(scene.end)),0),elementCount=proposed.timeline.reduce((count,scene)=>count+(scene.motion_design?.elements?.length||0),0);
    modal('SceneIR · vista previa de compilación',`<p class="modal-copy">${esc(file.name)} se compiló como datos editables para <strong>${esc(original.name)}</strong>. Esta importación técnica no acredita generación semántica ni fidelidad a CLONE.</p><div id="scene-ir-preview-summary"><div class="tool-row"><span>Cronología actual → propuesta</span><span>${original.timeline.length} → ${proposed.timeline.length} escenas</span></div><div class="tool-row"><span>Duración de las escenas</span><span>${fmt(span)}</span></div><div class="tool-row"><span>Elementos editables</span><span>${elementCount}</span></div><div class="tool-row"><span>Motor propuesto</span><span>${esc(proposed.settings?.engine||'native')}</span></div></div><div id="scene-ir-preview-errors" aria-live="polite">${errors.map(error=>`<p class="review-warning">${esc(error)}</p>`).join('')}${warnings.map(warning=>`<p class="small-copy">${esc(warning)}</p>`).join('')}</div><details><summary>Escenas y elementos compilados</summary><pre id="scene-ir-preview-json" class="code-view">${esc(JSON.stringify(proposed.timeline,null,2))}</pre></details><details><summary>Documento importado</summary><pre class="code-view">${esc(JSON.stringify(document,null,2))}</pre></details><label class="review-check"><input id="scene-ir-replace-check" type="checkbox" ${canApply?'':'disabled'}><span>Aplicar este SceneIR a <strong>${esc(original.name)}</strong> reemplaza su cronología de escenas actual. Revisé la propuesta y quiero reemplazarla.</span></label><p class="small-copy">La aplicación no inicia un render ni aprueba diseño, animación o edición narrativa.</p><div class="modal-actions"><button type="button" id="scene-ir-cancel" class="button ghost">Conservar cronología actual</button><button type="button" id="scene-ir-apply" class="button primary" disabled>Reemplazar cronología con SceneIR</button></div>`,()=>{
      const checkbox=$('scene-ir-replace-check'),button=$('scene-ir-apply'),errorBox=$('scene-ir-preview-errors');let applying=false;
      $('scene-ir-cancel').onclick=()=>$('modal').close();checkbox.onchange=()=>{button.disabled=applying||!canApply||!checkbox.checked;};
      button.onclick=action(async()=>{
        if(applying||!checkbox.checked||!canApply)return;if(!active())throw new Error('El proyecto cambió. Vuelve a previsualizar antes de reemplazar la cronología.');
        applying=true;button.disabled=true;checkbox.disabled=true;
        try{
          const response=projectData(await api(`/api/projects/${scope.id}/scene_ir`,{method:'POST',body:{document,expected_revision:scope.revision}}));
          if(!response||response.id!==scope.id)throw new Error('El servidor no devolvió el proyecto original.');
          if(active()){setProject(response);previewMode('timeline');state.selectedScene=state.project.timeline[0]?.id||null;state.selectedElement=selectedScene()?.motion_design?.elements?.[0]?.id||null;renderProject();$('modal').close();toast('SceneIR aplicado a la cronología. Revisa los elementos antes de renderizar.');}
          else toast(`SceneIR guardado en ${original.name}. La selección actual se conserva; vuelve a abrir ese proyecto para verlo.`);
          await refreshProjects();
        }catch(error){errorBox.innerHTML=`<p class="review-warning">${esc(error.status===409?'La revisión guardada cambió. Se conservó la cronología más reciente; vuelve a abrir el proyecto y previsualiza otra vez.':error.message)}</p>`;checkbox.checked=false;throw error;}
      });
    });
  }

  async function importBundle(file){
    if(!file)return;await saveProject();
    const result=await uploadFile(file,'/api/bundles');
    if(!result.project)throw new Error('El paquete no devolvió un proyecto editable.');
    setProject(result.project);await refreshProjects();await refreshAssets();$('bundle-input').value='';
    showJobProgress('Editable abierto',0);toast(result.reused?'Se abrió el proyecto canónico existente.':'Proyecto editable importado. Los recursos se deduplican por contenido.');
  }

  async function importFiles(files) {
    if(!files.length)return;if(state.importBusy)throw new Error('Espera a que termine la importación actual.');state.importBusy=true;
    const initial={id:state.project?.id||null,load:state.loadEpoch,edit:state.editEpoch};
    const initialMatches=()=>(state.project?.id||null)===initial.id&&state.loadEpoch===initial.load&&state.editEpoch===initial.edit;
    try{
      const fontFiles=[...files].filter(file=>/\.(ttf|otf)$/i.test(file.name));
      if(fontFiles.length){for(const file of fontFiles){if(file.size>16777216)throw new Error('La fuente supera el límite de 16 MB.');await uploadFile(file,'/api/assets','font');}await refreshAssets();await refreshFontLibrary();toast('Fuentes importadas en la biblioteca. Sus roles y escenas se conservan.');files=[...files].filter(file=>!fontFiles.includes(file));if(!files.length){$('file-input').value='';return;}}
      if(!initialMatches())throw new Error('La selección o edición cambió. Los archivos de fuente importados siguen en la biblioteca.');
      await ensureProject(files[0].name);const scope={id:state.project.id,load:state.loadEpoch,edit:state.editEpoch};await saveProject();
      const matches=()=>state.project?.id===scope.id&&state.loadEpoch===scope.load&&state.editEpoch===scope.edit;
      if(!matches()||state.dirty)throw new Error('Guarda los cambios y vuelve a importar desde el proyecto deseado.');
      const hasSource=Boolean(state.project.source);
      for(const file of files){
        const asset=await uploadFile(file);if(!state.assets.some(a=>a.id===asset.id))state.assets.push(asset);renderAssets();
        if(!matches())throw new Error('La selección o edición cambió durante la carga. El recurso está en la biblioteca; no se aplicó al proyecto actual.');
        const isSource=!state.project.source&&['video','audio'].includes(assetKind(asset));
        if(!isSource){await attachForOverlay(asset.id);if(!matches())throw new Error('La selección cambió. El recurso permanece adjunto al proyecto de origen.');continue;}
        const imported=normalizeProject(projectData(await api(`/api/projects/${scope.id}/assets`,{method:'POST',body:{asset_id:asset.id,source:true}})));
        if(state.project?.id!==scope.id||state.loadEpoch!==scope.load)throw new Error('La fuente se registró en el proyecto de origen. La selección actual se conserva.');
        if(state.editEpoch!==scope.edit){for(const item of imported.assets)if(!state.project.assets.some(a=>a.id===item.id))state.project.assets.push(item);if(imported.id===scope.id){state.project.source||=imported.source;state.project.revision=imported.revision;state.project.review={};state.project.approval_current=false;}throw new Error('Conservas nuevos cambios sin guardar. Revisa la fuente registrada antes de continuar.');}
        if(imported.id!==scope.id){setProject(imported);scope.id=state.project.id;scope.load=state.loadEpoch;scope.edit=state.editEpoch;await refreshProjects();}else state.project=imported;
      }
      loadSource();renderProject();showJobProgress('Medios importados',0);toast(hasSource?'Recursos añadidos a la biblioteca.':'Crudo listo. Analiza la voz o construye tu primera escena.');$('file-input').value='';
    }finally{state.importBusy=false;}
  }

  async function refreshAssets() {
    const result = await api('/api/assets');
    state.assets = result.assets || [];
    renderAssets();
    renderAudio();
  }

  function renderAssets() {
    const search = $('asset-search').value.trim().toLocaleLowerCase('es');
    const assets = state.assets.map(a=>assetById(a.id)).filter(a => (state.filter === 'all' || assetKind(a) === state.filter) && (!search || `${a.name} ${a.metadata?.content || ''}`.toLocaleLowerCase('es').includes(search)));
    $('asset-count').textContent = state.assets.length;
    $('library-empty').hidden = state.assets.length > 0;
    $('assets-grid').innerHTML = assets.map(asset => `<article class="asset-card ${state.selectedAsset === asset.id ? 'selected' : ''}" data-asset="${esc(asset.id)}" draggable="true" tabindex="0" role="button" aria-label="Ver ${esc(asset.name)}"><div class="asset-thumbnail">${thumbnailUrl(asset) ? `<img loading="lazy" src="${esc(thumbnailUrl(asset))}" alt="Miniatura de ${esc(asset.name)}">` : icon(assetKind(asset) === 'audio' ? 'audio' : assetKind(asset)==='font'?'text':'film')}<span class="asset-duration">${num(asset.duration) ? fmt(asset.duration, false) : assetKind(asset) === 'image' ? 'IMAGEN' : assetKind(asset)==='font'?'FUENTE':'—'}</span></div><span class="asset-name" title="${esc(asset.name)}">${esc(asset.name)}</span><span class="asset-meta"><span>${esc(assetKind(asset).toUpperCase())}</span>${state.project?.source === asset.id ? '<span class="asset-source">CRUDO</span>' : asset.verification?.visual ? '<span>REVISADO</span>' : '<span>PENDIENTE</span>'}</span><div class="asset-card-actions"><button data-view="${esc(asset.id)}">${assetKind(asset)==='font'?'Ver fuente':'Ver clip'}</button><button data-use="${esc(asset.id)}">${assetKind(asset)==='font'?'Elegir':'Usar'}</button></div></article>`).join('');
    $('assets-grid').querySelectorAll('[data-asset]').forEach(node => {
      node.ondragstart = event => {if(assetKind(assetById(node.dataset.asset))==='font'){event.preventDefault();return;}event.dataTransfer.setData('application/ascendia-asset', node.dataset.asset); event.dataTransfer.effectAllowed = 'copy';};
      node.onclick = event => {if (!event.target.closest('button')) assetDetail(node.dataset.asset);};
      node.onkeydown = event => {if (event.key === 'Enter') assetDetail(node.dataset.asset);};
    });
    $('assets-grid').querySelectorAll('[data-view]').forEach(button => button.onclick = () => assetDetail(button.dataset.view));
    $('assets-grid').querySelectorAll('[data-use]').forEach(button => button.onclick = action(() => useAsset(button.dataset.use)));
  }

  async function useAsset(id) {
    const asset = assetById(id);
    if (!asset) return;
    if(assetKind(asset)==='font'){await fontLibraryDialog(id);return;}
    await ensureProject(asset.name);
    const scope={id:state.project.id,scene:state.selectedScene,load:state.loadEpoch,edit:state.editEpoch};
    await attachForOverlay(id);
    if(state.project?.id!==scope.id||state.selectedScene!==scope.scene||state.loadEpoch!==scope.load||state.editEpoch!==scope.edit)throw new Error('La selección cambió mientras se adjuntaba el recurso. Elige dónde deseas colocarlo.');
    if (assetKind(asset) === 'audio') {addAudio(id); switchTab('audio'); return;}
    const scene = selectedScene();
    if (scene) mutate(() => {scene.asset_id = id; if (scene.type === 'presenter' || scene.type==='motion') scene.type = 'broll';if(scene.type==='broll')scene.source_in=0;if(scene.type==='split')scene.broll_in=0;});
    else addScene({type: 'broll', asset_id: id});
    toast('Recurso colocado. Documenta su relación con la narración en el inspector.');
  }

  function textSelectionScope(){const scene=selectedScene(),element=motionElement();return {projectId:state.project?.id||null,sceneId:scene?.id||null,elementId:element?.type==='text'?element.id:null,load:state.loadEpoch,edit:state.editEpoch};}
  function textScopeMatches(scope){return Boolean(scope)&&state.project?.id===scope.projectId&&state.selectedScene===scope.sceneId&&state.selectedElement===scope.elementId&&state.loadEpoch===scope.load&&state.editEpoch===scope.edit;}
  function fontRecord(id){return state.fontLibrary?.fonts?.find(font=>(font.asset_id||font.id)===id);}
  function fontFamily(id){const scope=identityScope(),prefix=SaaS?[scope.user,scope.actorWorkspace,scope.workspace,state.project?.id||'library',fontRecord(id)?.sha256||''].map(value=>String(value||'').replace(/\W/g,'_')).join('_')+'_':'';return 'AscendiaFont_'+prefix+String(id).replace(/[^a-zA-Z0-9_]/g,'_');}
  function fontItalic(font){return /italic|oblique/i.test(String(font?.style||''));}
  function licenseLabel(font){const license=font?.license||{};return license.label||license.status||'Licencia pendiente';}
  function safeLink(value){try{const url=new URL(value,location.origin);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch(_){return null;}}
  async function loadFontRecord(font){
    const id=font?.asset_id||font?.id;if(!id)throw new Error('La fuente no tiene un ID canónico.');
    const previous=state.fontLoads.get(id),family=fontFamily(id);if(previous&&previous.family===family)return previous.promise;if(previous?.face){document.fonts.delete(previous.face);sessionFaces.delete(previous.face);}
    const scope=identityScope(),loaded={status:'loading',family,error:null};state.fontLoads.set(id,loaded);
    loaded.promise=(async()=>{try{if(!font.url)throw new Error('La fuente requiere un archivo local servido por el editor.');const path=namespaceURL(font.url,scope),url=new URL(path,location.origin);if(url.origin!==location.origin)throw new Error('La fuente debe pertenecer a este estudio.');const face=new FontFace(loaded.family,`url("${url.href.replace(/["\\]/g,'')}")`,{style:fontItalic(font)?'italic':'normal'});await face.load();if(!identityCurrent(scope)||state.fontLoads.get(id)!==loaded)throw new DOMException('La biblioteca cambió.','AbortError');document.fonts.add(face);if(SaaS)sessionFaces.add(face);loaded.face=face;loaded.status='loaded';drawPreview();if(motionElement()?.font_asset_id===id)updateTextPreviewStatus();return loaded;}catch(error){loaded.status='error';loaded.error=error.message;if(identityCurrent(scope)&&state.fontLoads.get(id)===loaded&&motionElement()?.font_asset_id===id)updateTextPreviewStatus();throw error;}})();
    return loaded.promise;
  }
  async function refreshFontLibrary(){const ticket=++state.fontLibraryEpoch,result=await api('/api/font-library');if(ticket!==state.fontLibraryEpoch)return state.fontLibrary||result;state.fontLibrary=result;for(const[id,entry]of state.fontLoads)if(entry.status==='error')state.fontLoads.delete(id);for(const[key,entry]of state.textLayouts)if(entry.status==='error')state.textLayouts.delete(key);renderAssets();if(selectedScene())renderFreeMotion();return result;}
  function customFontStatus(element){const id=element.font_asset_id;if(!id)return null;const font=fontRecord(id);if(!font)return {status:'missing',error:'La fuente adjunta no aparece en el catálogo local.'};if(font.available===false)return {status:'unavailable',error:font.unavailable_reason||'La fuente no está disponible en el catálogo actual.'};if(!state.fontLoads.has(id)||state.fontLoads.get(id).family!==fontFamily(id))loadFontRecord(font).catch(()=>drawPreview());return state.fontLoads.get(id);}
  async function selectTextFont(choice,scope=textSelectionScope()){
    if(!textScopeMatches(scope)||!scope.elementId)throw new Error('Selecciona el texto que deseas modificar.');
    if(choice.startsWith('role:')){const role=choice.slice(5);if(!['primary','accent'].includes(role))throw new Error('Rol de fuente inválido.');mutate(()=>{const element=motionElement();element.font=role;delete element.font_asset_id;});return;}
    const id=choice.slice(6),font=fontRecord(id);if(!font||!choice.startsWith('asset:'))throw new Error('La fuente no está en el catálogo local.');if(font.available===false)throw new Error(font.unavailable_reason||'El archivo de fuente no está disponible.');
    await loadFontRecord(font);if(!textScopeMatches(scope))throw new Error('La selección cambió mientras se cargaba la fuente.');
    await attachForOverlay(id);if(!textScopeMatches(scope))throw new Error('La selección cambió mientras se adjuntaba la fuente.');
    mutate(()=>{const element=motionElement();element.font_asset_id=id;});
  }
  function updateFontActions(){const scope=state.fontModalScope;if(!scope?.host?.isConnected)return;const button=$('font-apply');if(!button)return;const valid=Boolean(scope.selection.elementId)&&textScopeMatches(scope.selection),font=fontRecord(scope.selectedId);button.disabled=!valid||font?.available===false||state.fontLoads.get(scope.selectedId)?.status!=='loaded'||scope.applying||scope.uploading||!canEdit();const note=$('font-context-state');if(note&&!valid)note.textContent='La selección cambió o no hay un texto seleccionado. Puedes consultar e importar fuentes; vuelve a abrir la biblioteca desde el texto deseado para aplicarla.';}
  async function fontLibraryDialog(selectedId=null){
    const selection=textSelectionScope(),scope={selection,selectedId,host:null,uploading:false,applying:false};state.fontModalScope=scope;
    modal('Fuentes locales',`<p class="modal-copy">Importa archivos TTF u OTF y consulta sus metadatos y la licencia comunicada. ${SaaS?'Las fuentes de tu proyecto conservan sus roles de marca.':'Sequel y Scholar conservan sus roles de marca.'} La fuente elegida se aplica solo al texto seleccionado.</p><div id="font-library-host"><p class="small-copy">Consultando catálogo local…</p></div>`,()=>{scope.host=$('font-library-host');});
    const current=()=>state.fontModalScope===scope&&scope.host?.isConnected;
    const paint=()=>{
      if(!current())return;const catalog=state.fontLibrary||{},fonts=catalog.fonts||[],roles=catalog.roles||[];
      scope.host.innerHTML=`<div class="font-role-list">${roles.map(font=>`<div class="tool-row"><span>${esc(font.family||font.name||font.role)} · ${esc(font.role)}</span><span>${esc(licenseLabel(font))}</span></div>`).join('')}</div><label class="field">Buscar una fuente<input id="font-search" placeholder="Nombre, familia o corte"></label><div class="font-library-grid"><div id="font-library-list" class="font-library-list"></div><div id="font-library-detail" class="font-library-detail"></div></div><label class="field font-upload-label">Importar TTF / OTF · máximo ${Math.round(num(catalog.max_upload_bytes,16777216)/1048576)} MB<input id="font-upload" type="file" accept=".ttf,.otf,font/ttf,font/otf" ${scope.uploading?'disabled':''}></label><p id="font-upload-status" class="small-copy" aria-live="polite">La importación añade una fuente a la biblioteca; no cambia el proyecto ni acredita derechos de redistribución.</p>`;
      const paintList=()=>{const search=$('font-search').value.toLocaleLowerCase('es');$('font-library-list').innerHTML=fonts.filter(font=>`${font.name} ${font.family} ${font.style}`.toLocaleLowerCase('es').includes(search)).map(font=>`<button type="button" class="font-library-item ${scope.selectedId===(font.asset_id||font.id)?'selected':''}" data-font-detail="${esc(font.asset_id||font.id)}"><strong>${esc(font.family||font.name)}</strong><span>${esc(font.style||'Corte local')} · ${esc(licenseLabel(font))}</span></button>`).join('')||'<p class="small-copy">No hay fuentes que coincidan. Puedes importar un archivo local.</p>';$('font-library-list').querySelectorAll('[data-font-detail]').forEach(button=>button.onclick=()=>{scope.selectedId=button.dataset.fontDetail;paintList();paintDetail();});};
      const paintDetail=()=>{
        const font=fontRecord(scope.selectedId),detail=$('font-library-detail');if(!font){detail.innerHTML='<p class="small-copy">Selecciona una fuente para ver su archivo y licencia.</p>';return;}
        const id=font.asset_id||font.id,license=font.license||{},url=safeLink(license.source_url),notice=safeLink(license.notice_url);
        detail.innerHTML=`<strong>${esc(font.family||font.name)}</strong><p class="small-copy">${esc(font.style||'Corte local')} · ${esc(font.name)}</p><div class="font-sample" id="font-sample">Cargando archivo de fuente…</div><p class="small-copy">${esc(licenseLabel(font))}${license.status?` · estado: ${esc(license.status)}`:''}</p>${url?`<a class="button compact ghost" href="${esc(url)}" target="_blank" rel="noopener">Fuente de licencia</a>`:''}${notice?`<a class="button compact ghost" href="${esc(notice)}" target="_blank" rel="noopener">Leer aviso</a>`:''}<p class="small-copy font-digest">SHA256 · ${esc(font.sha256||'Sin huella comunicada')}</p><details><summary>Metadatos del archivo</summary><pre class="code-view">${esc(JSON.stringify(font,null,2))}</pre></details><button type="button" id="font-apply" class="button primary full" ${textScopeMatches(selection)&&selection.elementId&&font.available!==false&&state.fontLoads.get(id)?.status==='loaded'?'':'disabled'}>Usar en el texto seleccionado</button><p id="font-context-state" class="small-copy">${selection.elementId?'Aplicar conserva los roles del proyecto y adjunta el archivo canónico.':'Selecciona un elemento de texto en el lienzo para aplicarla.'}</p>`;
        (font.available===false?Promise.reject(new Error(font.unavailable_reason||'Archivo de fuente no disponible.')):loadFontRecord(font)).then(loaded=>{if(!current()||scope.selectedId!==id)return;const sample=$('font-sample');sample.style.fontFamily=loaded.family;sample.style.fontStyle=fontItalic(font)?'italic':'normal';sample.textContent='Aa Áéñ ¿? 0123';updateFontActions();}).catch(error=>{if(current()&&scope.selectedId===id){$('font-sample').textContent='No se pudo cargar la fuente: '+error.message;updateFontActions();}});
        $('font-apply').onclick=action(async()=>{if(!textScopeMatches(selection))throw new Error('La selección cambió. Vuelve a abrir la biblioteca desde el texto deseado.');scope.applying=true;updateFontActions();try{await selectTextFont('asset:'+id,selection);if(current())$('modal').close();toast('Fuente local aplicada al texto seleccionado. La revisión estética sigue pendiente.');}finally{scope.applying=false;updateFontActions();}});
      };
      $('font-search').oninput=paintList;paintList();paintDetail();
      $('font-upload').onchange=action(async()=>{
        const file=$('font-upload').files[0];if(!file)return;if(!/\.(ttf|otf)$/i.test(file.name))throw new Error('Importa un archivo TTF u OTF.');if(file.size>num(catalog.max_upload_bytes,16777216))throw new Error('El archivo supera el límite de importación.');
        scope.uploading=true;$('font-upload').disabled=true;$('font-upload-status').textContent='Importando el archivo local…';
        try{const asset=await uploadFile(file,'/api/assets','font');await refreshAssets();await refreshFontLibrary();if(current()){scope.selectedId=asset.id;paint();toast('Fuente importada en la biblioteca. Consulta su licencia antes de distribuirla.');}}finally{scope.uploading=false;if(current())$('font-upload').disabled=false;}
      });
    };
    try{await refreshFontLibrary();paint();}catch(error){if(current())scope.host.innerHTML=`<p class="review-warning">${esc(error.message)}</p>`;}
  }

  function assetModalMatches(scope){return Boolean(scope)&&state.assetModalScope===scope&&scope.form?.isConnected&&state.selectedAsset===scope.assetId;}
  function assetProjectMatches(scope){return assetModalMatches(scope)&&(state.project?.id||null)===scope.projectId&&state.loadEpoch===scope.load&&state.editEpoch===scope.edit;}
  function updateAssetActions(){
    const scope=state.assetModalScope;if(!assetModalMatches(scope))return;
    const valid=assetProjectMatches(scope),hasProject=Boolean(scope.projectId),process=scope.panel.querySelector('button[type="submit"]');
    scope.form.querySelector('button[type="submit"]').disabled=!valid||!hasProject||scope.reviewing||scope.processing;
    $('asset-make-source').disabled=isShared()||!valid||!hasProject||scope.reviewing||scope.processing;
    if(process)process.disabled=!valid||scope.processing||scope.reviewing||scope.tool?.available!==true||scope.tool?.implemented===false;
    $('asset-scope-state').textContent=!valid?'La selección o edición cambió. Puedes ver este archivo; vuelve a abrirlo antes de ejecutar acciones.':!hasProject?'Selecciona un proyecto para guardar observaciones o asignar un crudo. Las herramientas pueden producir recursos en la biblioteca.':'';
  }

  function assetDetail(id) {
    const asset=assetById(id);if(!asset)return;
    if(assetKind(asset)==='font'){action(()=>fontLibraryDialog(id))();return;}
    state.selectedAsset=id;renderAssets();
    const kind=assetKind(asset),verified=state.project?.assets.find(a=>a.id===id)||asset;
    const scope={assetId:id,projectId:state.project?.id||null,load:state.loadEpoch,edit:state.editEpoch,processing:false,reviewing:false};state.assetModalScope=scope;
    const visual=kind!=='audio',alpha=asset.preview_preserves_alpha||asset.probe?.streams?.some(stream=>/rgba|argb|bgra|abgr|yuva|gbrap/.test(stream.pix_fmt||''));
    const media=kind==='image'?`<img class="asset-detail-media" src="${esc(assetUrl(asset))}" alt="${esc(asset.name)}">`:`<${kind==='audio'?'audio':'video'} id="asset-review-media" class="asset-detail-media" controls playsinline aria-label="Previsualización de ${esc(asset.name)}" src="${esc(assetUrl(asset))}"></${kind==='audio'?'audio':'video'}>`;
    const previewInfo=asset.preview_error?`<p class="review-warning">La vista previa no está disponible: ${esc(asset.preview_error)}. El archivo canónico se conserva.</p>`:asset.preview_is_derivative?`<p class="small-copy">Vista previa compatible${asset.preview_preserves_alpha?' con transparencia':''}. El render usa el archivo canónico.</p>`:'';
    const provenance=asset.metadata?.provenance,derived=Boolean(provenance?.operation||(typeof asset.metadata?.source==='string'&&asset.metadata.source.startsWith('a_')));
    modal(asset.name,`${visual?`<div id="asset-preview-frame" class="asset-preview-frame" data-background="${alpha?'checker':'dark'}">${media}</div><label class="field">Fondo de inspección<select id="asset-preview-background"><option value="checker" ${alpha?'selected':''}>Damero · transparencia</option><option value="dark" ${alpha?'':'selected'}>Oscuro</option><option value="light">Claro</option></select></label>`:media}${previewInfo}<div class="asset-detail-meta"><div>Duración<strong>${fmt(asset.duration)}</strong></div><div>Formato canónico<strong>${esc(asset.probe?.format?.format_name||asset.probe?.format_name||kind)}</strong></div></div>${derived?'<p class="review-warning">Derivado técnico. El original se conserva; bordes, pelo, objetos y continuidad requieren revisión. No se colocó automáticamente en una escena ni se eligió como crudo.</p>':''}${derived?`<a class="button ghost full" href="${esc(namespaceURL(asset.url||fileUrl(asset.path)))}" download>Descargar derivado canónico</a>`:''}${derived&&provenance?`<details><summary>Procedencia y parámetros aplicados</summary><pre id="asset-provenance" class="code-view">${esc(JSON.stringify(provenance,null,2))}</pre></details>`:''}<p id="asset-scope-state" class="small-copy" aria-live="polite"></p><div id="media-tools-panel"><p class="small-copy">Consultando herramientas y modelo local…</p></div><form id="asset-review-form" style="margin-top:16px"><label class="field">Contenido observado<textarea id="asset-content" rows="3" placeholder="Describe la acción real que comprobaste">${esc(verified.metadata?.content||'')}</textarea></label><p id="asset-technical-origin" class="small-copy">Origen técnico registrado: ${esc(asset.metadata?.source||provenance?.source_asset_id||'archivo local')}. La procedencia técnica se conserva.</p><label class="field">Origen y permisos observados<input id="asset-origin" placeholder="Anota lo que comprobaste; no sustituye la procedencia técnica" value="${esc(verified.metadata?.origin_observed||'')}"></label><label class="review-check"><input id="asset-verified" type="checkbox" ${(kind==='audio'?verified.verification?.audio:verified.verification?.visual)?'checked':''}><span>Vi el contenido en movimiento y verifiqué que sirve al contexto. En audio, escuché el archivo.</span></label><div class="modal-actions"><button id="asset-make-source" type="button" class="button ghost">Usar como crudo</button><button type="submit" class="button primary">Guardar revisión</button></div></form>`,()=>{
      scope.form=$('asset-review-form');scope.panel=$('media-tools-panel');
      if(visual)$('asset-preview-background').onchange=()=>{$('asset-preview-frame').dataset.background=$('asset-preview-background').value;};
      loadMediaTools(scope).catch(error=>{if(assetModalMatches(scope))scope.panel.innerHTML=`<p class="review-warning">${esc(error.message)}</p>`;});
      scope.form.onsubmit=action(async event=>{
        event.preventDefault();if(scope.processing||scope.reviewing)throw new Error('Espera a que termine la acción del medio.');if(!assetProjectMatches(scope)||!scope.projectId)throw new Error('La selección cambió. Vuelve a abrir el medio en el proyecto deseado.');
        const content=$('asset-content').value.trim(),origin=$('asset-origin').value.trim(),checked=$('asset-verified').checked;
        if(checked&&!content)throw new Error('Describe el contenido observado antes de marcar la verificación.');
        scope.reviewing=true;updateAssetActions();
        try{
          await attachForOverlay(id);if(!assetProjectMatches(scope))throw new Error('El proyecto cambió antes de registrar las observaciones.');
          mutate(project=>{const item=project.assets.find(a=>a.id===id);item.metadata={...item.metadata,content,origin_observed:origin};item.verification={...item.verification,visual:kind==='audio'?Boolean(item.verification?.visual):checked,audio:kind==='audio'?checked:Boolean(item.verification?.audio),reviewed_at:new Date().toISOString()};});scope.edit=state.editEpoch;
          await saveProject();if(assetProjectMatches(scope)){renderAssets();$('modal').close();}toast('Observaciones guardadas en el proyecto de origen.');
        }finally{scope.reviewing=false;updateAssetActions();}
      });
      $('asset-make-source').onclick=action(async()=>{
        if(scope.processing||scope.reviewing)throw new Error('Espera a que termine la acción del medio.');if(!['video','audio'].includes(kind))throw new Error('El crudo debe ser video o audio.');
        if(!assetProjectMatches(scope)||!scope.projectId)throw new Error('La selección cambió. Vuelve a abrir el medio en el proyecto deseado.');
        scope.reviewing=true;updateAssetActions();
        try{
          await saveProject();if(!assetProjectMatches(scope)||state.dirty)throw new Error('El proyecto cambió antes de asignar el crudo.');
          const project=await api(`/api/projects/${scope.projectId}/assets`,{method:'POST',body:{asset_id:id,source:true}});
          if(assetProjectMatches(scope)){setProject(project);$('modal').close();}toast('Asignación guardada en el proyecto de origen. Revisa el storyboard.');
        }finally{scope.reviewing=false;updateAssetActions();}
      });
      updateAssetActions();
    });
  }

  async function loadMediaTools(scope){
    const results=await Promise.allSettled([api('/api/media-tools'),api('/api/status')]);
    if(!assetModalMatches(scope))return;if(results[0].status==='rejected')throw results[0].reason;
    state.mediaTools=results[0].value.operations||[];if(results[1].status==='fulfilled')state.status=results[1].value;
    const panel=scope.panel,tools=state.mediaTools;if(!tools.length){panel.innerHTML='<p class="small-copy">El servidor no informó operaciones para este medio.</p>';return;}
    panel.innerHTML=`<details><summary>Herramientas del medio</summary><form id="media-process-form"><label class="field">Operación local<select id="media-operation">${tools.map(tool=>`<option value="${esc(tool.id)}">${esc(tool.name)}${tool.available===false?' · no disponible':''}</option>`).join('')}</select></label><p id="media-tool-description" class="small-copy"></p><div id="media-model-state" aria-live="polite"></div><div id="media-tool-parameters"></div><p id="media-tool-availability" class="small-copy" aria-live="polite"></p><button type="submit" class="button primary full">Ejecutar herramienta</button></form></details>`;
    const paint=()=>{
      const tool=tools.find(item=>item.id===$('media-operation').value);scope.tool=tool;
      $('media-tool-description').textContent=[tool.description,...(tool.limitations||[])].filter(Boolean).join(' ');
      const segment=tool.id==='remove_background_video',capability=tool.capability||state.status?.segmentation||state.status?.capabilities?.segmentation||{},model=tool.model||capability.model||Object.fromEntries(['engine','model_sha256','runtime_version','device','gpu_used'].filter(key=>capability[key]!==undefined).map(key=>[key,capability[key]])),available=tool.available===true&&tool.implemented!==false;
      $('media-model-state').innerHTML=segment?`<div class="tool-row ${available?'':'warning'}"><span>Segmentación de persona · CPU</span><span>${available?'Modelo disponible':'Modelo pendiente'}</span></div><p class="small-copy">${capability.verified_execution===true?'Existe ejecución real verificada por el servidor.':'La ejecución real aún no está verificada por el servidor.'} El resultado conserva revisión de bordes y continuidad pendiente.</p>${model&&Object.keys(model).length?`<details><summary>Modelo comunicado por el servidor</summary><pre class="code-view">${esc(JSON.stringify(model,null,2))}</pre></details>`:''}`:'';
      $('media-tool-availability').textContent=available?segment?'Se crea otro MOV con alfa y una vista previa WebM; el audio del tramo se conserva según el recibo. No cambia escenas ni el crudo.':'El resultado es un recurso nuevo de la biblioteca; no reemplaza el original.':tool.unavailable_reason||'La operación no está disponible en el entorno actual.';
      $('media-tool-parameters').innerHTML=(tool.parameters||[]).map(parameter=>`<label class="field">${esc(parameter.name||parameter.key)}${parameter.optional?' · opcional':''}<input data-tool-param="${esc(parameter.key)}" data-param-type="${esc(parameter.type)}" type="${parameter.type==='color'?'color':parameter.type==='number'||parameter.type==='integer'?'number':'text'}" ${parameter.min!=null?`min="${num(parameter.min)}"`:''} ${parameter.max!=null?`max="${num(parameter.max)}"`:''} step="${parameter.type==='integer'?['max_width','max_height'].includes(parameter.key)?'2':'1':'.01'}" value="${esc(parameter.default??'')}" ${parameter.optional?'':'required'}></label>`).join('');
      updateAssetActions();
    };
    $('media-operation').onchange=paint;paint();
    $('media-process-form').onsubmit=action(async event=>{
      event.preventDefault();if(scope.processing||scope.reviewing)throw new Error('Espera a que termine la acción del medio.');if(!assetProjectMatches(scope))throw new Error('La selección cambió. Vuelve a abrir el medio antes de procesarlo.');
      const operation=$('media-operation').value,tool=tools.find(item=>item.id===operation),options={};
      if(tool.available!==true||tool.implemented===false)throw new Error(tool.unavailable_reason||'La operación no está disponible.');
      $('media-tool-parameters').querySelectorAll('[data-tool-param]').forEach(input=>{if(input.value!=='')options[input.dataset.toolParam]=['number','integer'].includes(input.dataset.paramType)?Number(input.value):input.value;});
      scope.processing=true;updateAssetActions();
      try{
        await saveProject();if(!assetProjectMatches(scope)||state.dirty)throw new Error('El proyecto cambió antes de encolar la herramienta.');
        const body={operation,options};if(scope.projectId)body.project_id=scope.projectId;
        const job=await api(`/api/assets/${encodeURIComponent(scope.assetId)}/process`,{method:'POST',body});if(job.id)state.jobSeen.set(job.id,'queued');
        if(assetProjectMatches(scope)){$('modal').close();showJobProgress(job.message||'Herramienta local en cola CPU.',num(job.progress));}
        await pollJobs();toast('Herramienta en cola para el recurso de origen. El original se conserva; el derivado requiere revisión.');
      }finally{scope.processing=false;updateAssetActions();}
    });
  }

  function switchTab(tab) {
    document.querySelectorAll('.rail-item[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.tab-view').forEach(node => node.classList.toggle('active', node.id === `tab-${tab}`));
  }

  function renderProject() {
    cleanMotionPlayers();
    const p = state.project, enabled = Boolean(p);if(SaaS&&identity){const link=document.querySelector('.studio-session-controls a');if(link)link.href='/portal'+(p?(isShared()?'?shared=':'?project=')+encodeURIComponent(p.id):'');}
    $('scene-type').querySelector('[value="split"]').textContent='Split · '+splitLabel(p);
    const libraryFoot=document.querySelector('.library-foot');if(libraryFoot){const label=SaaS?isShared()?'Biblioteca de este proyecto':'Biblioteca de tu espacio':'Biblioteca local';if(libraryFoot.dataset.label!==label){libraryFoot.dataset.label=label;libraryFoot.innerHTML='<span class="status-dot"></span>'+label;}}
    $('policy-label').textContent=SaaS?'Borrador editable · revisión pendiente':'ASCENDIA V5 · prueba de 10 s · revisión explícita';
    const workflowNote=$('workflow-scope-note');if(SaaS&&workflowNote)workflowNote.textContent='Puedes producir un borrador completo en Automático o Manual. Revisa el montaje y el sonido antes de darlo por aprobado.';
    const cloudButton=$('cloud-backup');if(cloudButton){cloudButton.hidden=!SaaS||isShared()||state.status?.capabilities?.cloud_storage?.project_backup_jobs!==true;cloudButton.disabled=!p||!canEdit()||isShared();}
    const styleNote=document.querySelector('#tab-style .note span');if(styleNote)styleNote.textContent=SaaS?'Base Iván: YO para cámara, subtítulos y split '+splitLabel(p)+'; CLONE para motion. Tu marca define colores, logo y fuentes de este proyecto. La prueba queda pendiente de revisión.':'YO: split '+splitLabel(p)+', rostro máximo 3 s y subtítulos. CLONE: acciones y transformaciones de motion. Sequel y Scholar auténticas, rojo semántico y revisión de la secuencia.';
    ['save-project','export-project','add-scene','save-identity','validate-project','read-manual','agent-workflow','create-free-motion','import-scene-ir'].forEach(id => $(id).disabled = !enabled);
    if(SaaS&&identity)$('read-manual').disabled=false;
    ['render-project','analyze-source','automate-project'].forEach(id => $(id).disabled = !p?.source);
    $('plan-project').disabled = !p?.transcript?.segments?.length && !p?.transcript?.words?.length;
    $('review-project').disabled = !p?.renders?.length;
    $('review-project').textContent=isTechnicalRender(p?.renders?.at(-1))?'Anotar revisión técnica':'Revisar prueba narrativa de 10 s';
    $('track-source').disabled=!p?.source||capabilityAvailability(state.status?.capabilities?.tracking)!==true;
    $('view-tracking').hidden=!p?.tracking;
    $('tracking-state').textContent=p?.tracking?`${num(p.tracking.summary?.detected_samples)} / ${num(p.tracking.sampling?.count)} muestras con detección. Medidas originales pendientes de revisión; ningún cambio aplicado.`:'El seguimiento genera muestras y propuestas; no cambia el encuadre ni aprueba el contenido.';
    $('save-state').textContent = p ? state.dirty ? 'Cambios sin guardar' : `Guardado · rev. ${p.revision ?? 1}` : 'Local · sin proyecto';
    $('save-state').style.color = state.dirty ? '#e5ae83' : '';
    $('resolution-label').textContent = `${p?.settings.width || 1080} × ${p?.settings.height || 1920}`;
    $('undo').disabled = !state.history.length;
    $('redo').disabled = !state.redo.length;
    $('preview-empty').hidden = Boolean(p?.source || p?.timeline.length);
    $('preview-render').disabled = !p?.renders?.length;
    $('identity-observations').value = p?.reference_review?.identity_observations || '';
    $('identity-evidence').value = (p?.reference_review?.evidence || []).join('\n');
    const manualRead=p?.history?.some(h=>h.action==='manual_refreshed_after_reading')&&JSON.stringify(p.manual)===JSON.stringify(state.status?.manual);
    $('manual-state').textContent = manualRead || p?.manual_review?.read_complete || p?.manual?.read_complete ? 'Lectura completa registrada para este proyecto.' : 'Lectura del proyecto pendiente.';
    renderAssets(); renderTimeline(); renderInspector(); renderTranscript(); renderTemplates(); renderAudio(); renderWorkflow(); updateTimecode(); drawPreview(); updateAssetActions();updateFontActions();applySharedControls();
  }

  function addScene(values = {}) {
    if (!state.project) return;
    const start = Math.round(state.time * 100) / 100;
    const sourceDuration = num(assetById(state.project.source)?.duration);
    const end = sourceDuration > start ? Math.min(start + 2.5, sourceDuration) : start + 2.5;
    const scene = {id: uid('scene'), start, end, type: 'motion', title: '', subtitle: '', template: 'kinetic', source_in: values.type==='broll'?0:start, chin_y: .65, text_color: '#ffffff', effects: {brightness: 0, contrast: 1, saturation: 1}, keyframes: [], decision: {search: '', reason: '', evidence: []}, ...values};
    mutate(p => {p.timeline.push(scene); p.timeline.sort((a,b) => a.start-b.start); state.selectedScene = scene.id;});
  }

  function removeScene() {
    const scene = selectedScene();
    if (!scene) return;
    mutate(p => {p.timeline = p.timeline.filter(s => s.id !== scene.id); state.selectedScene = null;});
  }

  function trimScene(scene,start,end){
    const oldStart=scene.start,shift=start-oldStart,anchors=trimCameraAnchors(scene,shift,end-oldStart),oldKeys=clone(scene.keyframes||[]),before={...scene,keyframes:oldKeys};
    const design=trimMotionDesign(scene,shift,end-oldStart);if(design)scene.motion_design=design;
    const staticImage=!['presenter','split','motion'].includes(scene.type)&&assetKind(assetById(scene.asset_id))==='image';
    scene.source_in=staticImage?0:Math.max(0,num(scene.source_in,['presenter','split'].includes(scene.type)?oldStart:0)+shift);
    if(scene.type==='split')scene.broll_in=assetKind(assetById(scene.asset_id))==='image'?0:Math.max(0,num(scene.broll_in)+shift);
    scene.start=start;scene.end=end;if(anchors)scene.camera_anchors=anchors;
    if(oldKeys.length){
      const entry=keyframeAt(before,shift),exit=keyframeAt(before,end-oldStart),length=end-start;
      scene.keyframes=oldKeys.filter(k=>k.time>=shift&&k.time<=end-oldStart).map(k=>({...k,time:Math.max(0,k.time-shift)}));
      if(!scene.keyframes.some(k=>Math.abs(k.time)<.001))scene.keyframes.unshift({time:0,...entry});
      if(!scene.keyframes.some(k=>Math.abs(k.time-length)<.001))scene.keyframes.push({time:length,...exit});
    }
    if(scene.overlays)scene.overlays=scene.overlays.filter(o=>o.end>shift&&o.start<end-oldStart).map(o=>{const item=clone(o);trimScene(item,Math.max(o.start,shift),Math.min(o.end,end-oldStart));item.start-=shift;item.end-=shift;return item;});
  }

  function splitScene() {
    const scene = selectedScene() || currentScene();
    if (!scene || state.time <= scene.start + .05 || state.time >= scene.end - .05) {toast('Sitúa el cursor dentro de una escena para dividirla.'); return;}
    const cut = Math.round(state.time * 1000) / 1000;
    mutate(p => {
      const originalEnd = scene.end;
      const splitAt=cut-scene.start,leftDesign=trimMotionDesign(scene,0,splitAt),rightDesign=trimMotionDesign(scene,splitAt,originalEnd-scene.start),leftAnchors=trimCameraAnchors(scene,0,splitAt),rightAnchors=trimCameraAnchors(scene,splitAt,originalEnd-scene.start);
      const boundary=keyframeAt(scene,cut-scene.start);
      const right = {...clone(scene), id: uid('scene'), start: cut, end: originalEnd, source_in: num(scene.source_in, scene.type === 'presenter' || scene.type === 'split' ? scene.start : 0) + cut - scene.start};
      if(scene.type==='broll'&&assetKind(assetById(scene.asset_id))==='image')right.source_in=0;
      if (scene.type === 'split') right.broll_in = assetKind(assetById(scene.asset_id))==='image'?0:num(scene.broll_in) + cut - scene.start;
      right.keyframes = (scene.keyframes || []).filter(k => k.time >= cut - scene.start).map(k => ({...k,time:k.time - (cut - scene.start)}));
      scene.keyframes = (scene.keyframes || []).filter(k => k.time < cut - scene.start);
      if((scene.keyframes.length||right.keyframes.length)){scene.keyframes.push({time:cut-scene.start,...boundary});if(!right.keyframes.some(k=>Math.abs(k.time)<.001))right.keyframes.unshift({time:0,...boundary});}
      if(scene.overlays){const splitAt=cut-scene.start;right.overlays=scene.overlays.filter(o=>o.end>splitAt).map(o=>{const item=clone(o);trimScene(item,Math.max(o.start,splitAt),o.end);item.start-=splitAt;item.end-=splitAt;return item;});scene.overlays=scene.overlays.filter(o=>o.start<splitAt).map(o=>{const item=clone(o);trimScene(item,o.start,Math.min(o.end,splitAt));return item;});}
      scene.end=cut;if(leftAnchors){scene.camera_anchors=leftAnchors;right.camera_anchors=rightAnchors;}
      if(leftDesign){scene.motion_design=leftDesign;right.motion_design=rightDesign;}
      p.timeline.push(right);
      p.timeline.sort((a,b) => a.start-b.start);
      state.selectedScene = right.id;
    });
  }

  function undo() {
    if (!state.history.length) return;
    state.redo.push(clone(state.project));
    const revision = state.project.revision;
    state.project = state.history.pop();
    state.project.revision = revision;
    dirty(); renderProject();
  }
  function redo() {
    if (!state.redo.length) return;
    state.history.push(clone(state.project));
    const revision = state.project.revision;
    state.project = state.redo.pop();
    state.project.revision = revision;
    dirty(); renderProject();
  }

  function renderTimeline() {
    const total = Math.max(duration(), 10), scale = state.zoom;
    const available = $('timeline-scroll').clientWidth - $('timeline-scroll').querySelector('.track-labels').clientWidth;
    const width = Math.max(total * scale + 45, available, 300);
    $('timeline-content').style.width = `${width}px`;
    document.querySelectorAll('.timeline-track').forEach(node => node.style.backgroundSize = `${scale}px 100%`);
    const tickEvery = scale < 40 ? 5 : scale < 70 ? 2 : 1;
    let ruler = '';
    for (let t = 0; t <= total; t += tickEvery) ruler += `<span class="ruler-tick" style="left:${t * scale}px">${fmt(t, false)}</span>`;
    if (scale > 55) for (let t = .5; t < total; t += 1) ruler += `<span class="ruler-tick minor" style="left:${t * scale}px"></span>`;
    $('timeline-ruler').innerHTML = ruler;
    const scenes = state.project?.timeline || [];
    $('scene-count').textContent = `${scenes.length} escena${scenes.length === 1 ? '' : 's'}`;
    $('picture-track').innerHTML = scenes.map((s,index) => `<div class="timeline-clip ${esc(s.type)} ${s.id === state.selectedScene ? 'selected' : ''}" data-scene="${esc(s.id)}" tabindex="0" role="button" aria-label="Escena ${index+1}: ${esc(s.title || s.type)}, ${fmt(s.start)} a ${fmt(s.end)}" style="left:${s.start*scale}px;width:${Math.max(8,(s.end-s.start)*scale)}px"><span class="trim-handle left" data-trim="left"></span>${icon(s.type === 'motion' ? 'spark' : 'film')}<span class="clip-label">${String(index+1).padStart(2,'0')} · ${esc(s.title || ({presenter:'Presentador',split:'Split '+splitLabel(),broll:assetById(s.asset_id)?.name || 'B-roll',motion:'Motion'})[s.type] || s.type)}</span><span class="trim-handle right" data-trim="right"></span></div>`).join('');
    $('text-track').innerHTML = scenes.filter(s => s.title || s.subtitle).map(s => `<button class="text-clip" data-scene="${esc(s.id)}" style="left:${s.start*scale}px;width:${Math.max(8,(s.end-s.start)*scale)}px">${esc(s.title || s.subtitle)}</button>`).join('');
    $('overlay-track').innerHTML=scenes.flatMap(s=>(s.overlays||[]).map((o,i)=>`<button class="text-clip overlay-clip" data-overlay-scene="${esc(s.id)}" style="left:${(s.start+o.start)*scale}px;width:${Math.max(8,(o.end-o.start)*scale)}px">${i+1} · ${esc(assetById(o.asset_id)?.name||'Capa visual')}</button>`)).join('');
    const freeScenes=scenes.filter(isFreeMotion);document.querySelector('.studio').classList.toggle('has-free-motion',Boolean(freeScenes.length));document.querySelectorAll('.motion-track-label').forEach(n=>n.hidden=!freeScenes.length);
    for(const type of ['text','shape','media']){const track=$(`motion-${type}-track`);track.hidden=!freeScenes.length;track.innerHTML=freeScenes.flatMap(s=>s.motion_design.elements.filter(e=>e.type===type).map((e,i)=>`<button class="text-clip motion-element-clip" data-motion-scene="${esc(s.id)}" data-motion-element="${esc(e.id)}" style="left:${(s.start+num(e.start))*scale}px;width:${Math.max(8,(num(e.end,s.end-s.start)-num(e.start))*scale)}px;top:${3+(i%3)*8}px" title="${esc(e.type==='text'?e.text:e.type)} · ${num(e.start)}–${num(e.end)} s">${e.type==='text'?'T':e.type==='shape'?'◧':'▧'} ${esc(e.type==='text'?e.text:assetById(e.asset_id)?.name||e.shape||e.type)}</button>`)).join('');track.querySelectorAll('[data-motion-element]').forEach(node=>node.onclick=()=>{selectScene(node.dataset.motionScene);selectMotionElement(node.dataset.motionElement);$('free-motion-section').open=true;});}
    $('music-track').innerHTML = (state.project?.audio || []).map(a => `<button class="audio-clip" data-audio="${esc(a.id || a.asset_id)}" style="left:${a.start*scale}px;width:${Math.max(8,(a.end-a.start)*scale)}px">${a.is_riser ? '↗ ' : ''}${esc(assetById(a.asset_id)?.name || a.role)} · ${num(a.gain_db)} dB</button>`).join('');
    $('picture-track').querySelectorAll('[data-scene]').forEach(node => {
      node.onpointerdown = event => sceneDrag(event, node);
      node.onkeydown = event => {if (event.key === 'Enter') selectScene(node.dataset.scene);};
    });
    $('text-track').querySelectorAll('[data-scene]').forEach(node => node.onclick = () => selectScene(node.dataset.scene));
    $('overlay-track').querySelectorAll('[data-overlay-scene]').forEach(node=>node.onclick=()=>{selectScene(node.dataset.overlayScene);$('overlay-section').open=true;$('overlay-section').scrollIntoView({block:'nearest'});});
    $('music-track').querySelectorAll('[data-audio]').forEach(node => node.onclick = () => switchTab('audio'));
    updatePlayhead(); drawWaveform();
    $('split-scene').disabled = !scenes.length;
  }

  function selectScene(id, seek = true) {
    if(state.selectedScene!==id){state.selectedElement=state.project?.timeline.find(s=>s.id===id)?.motion_design?.elements[0]?.id||null;state.selectedPathPoint=null;}
    state.selectedScene = id;
    const scene = selectedScene();
    if (seek && scene) seekTime(scene.start);
    renderTimeline(); renderInspector();document.querySelector('.inspector-panel').scrollTop=0;
  }

  function sceneDrag(event, node) {
    if (event.button !== 0) return;
    event.preventDefault(); event.stopPropagation();
    if(!canEdit()){selectScene(node.dataset.scene);return;}
    const scene = state.project.timeline.find(s => s.id === node.dataset.scene);
    if (!scene) return;
    state.selectedScene = scene.id;
    renderInspector();
    node.classList.add('selected');
    const mode = event.target.dataset.trim || 'move', x = event.clientX, start = scene.start, end = scene.end, snapshot=clone(scene);
    let changed = false;
    node.setPointerCapture(event.pointerId);
    const move = e => {
      const delta = Math.round((e.clientX - x) / state.zoom * 100) / 100;
      if (Math.abs(delta) < .03 && !changed) return;
      if (!changed) {pushHistory(); changed = true;}
      if(mode==='left'||mode==='right'){const candidate=clone(snapshot);trimScene(candidate,mode==='left'?clamp(start+delta,0,end-.1):start,mode==='right'?Math.max(start+.1,end+delta):end);Object.assign(scene,candidate);}
      else {scene.start = Math.max(0, start + delta); scene.end = scene.start + end - start;if(['presenter','split'].includes(scene.type))scene.source_in=Math.max(0,num(snapshot.source_in,start)+scene.start-start);}
      node.style.left = `${scene.start * state.zoom}px`;
      node.style.width = `${(scene.end - scene.start) * state.zoom}px`;
      dirty(); drawPreview();
    };
    const finish = () => {
      node.removeEventListener('pointermove', move); node.removeEventListener('pointerup', finish); node.removeEventListener('pointercancel', finish);
      if (changed) state.project.timeline.sort((a,b) => a.start-b.start); else seekTime(scene.start);
      renderTimeline(); renderInspector();
    };
    node.addEventListener('pointermove', move); node.addEventListener('pointerup', finish); node.addEventListener('pointercancel', finish);
  }

  function timelineSeek(event) {
    if (event.target.closest('.timeline-clip,.text-clip,.audio-clip')) return;
    if (event.button !== 0) return;
    const target = event.currentTarget;
    const rect = $('timeline-content').getBoundingClientRect();
    seekTime((event.clientX - rect.left) / state.zoom);
    target.setPointerCapture(event.pointerId);
    const move = e => seekTime((e.clientX - $('timeline-content').getBoundingClientRect().left) / state.zoom);
    const finish = () => {target.removeEventListener('pointermove', move); target.removeEventListener('pointerup', finish); target.removeEventListener('pointercancel', finish);};
    target.addEventListener('pointermove', move); target.addEventListener('pointerup', finish); target.addEventListener('pointercancel', finish);
  }

  function waveformPeaks() {
    const waveform = state.project?.analysis?.waveform || state.project?.waveform || assetById(state.project?.source)?.waveform;
    if (Array.isArray(waveform)) return waveform;
    return waveform?.peaks || waveform?.samples || [];
  }
  function drawWaveform() {
    const wave = $('waveform'), peaks = waveformPeaks(), height = 34;
    wave.width = Math.min(16384, Math.round($('timeline-content').clientWidth)); wave.height = height;
    const context = wave.getContext('2d'); context.clearRect(0,0,wave.width,height);
    $('waveform-status').hidden = peaks.length > 0;
    if (!peaks.length) return;
    const sourceDuration = num(assetById(state.project.source)?.duration, duration()), width = Math.min(wave.width, sourceDuration * state.zoom);
    context.strokeStyle = '#81b7ac'; context.lineWidth = 1;
    for (let x = 0; x < width; x += 2) {
      const entry = peaks[Math.min(peaks.length-1, Math.floor(x/width*peaks.length))];
      const amplitude = Array.isArray(entry) ? Math.max(Math.abs(num(entry[0])), Math.abs(num(entry[1]))) : Math.abs(num(entry));
      const size = clamp(amplitude,0,1)*14;
      context.beginPath(); context.moveTo(x,height/2-size); context.lineTo(x,height/2+size); context.stroke();
    }
  }

  function renderInspector() {
    const s = selectedScene();
    if(SaaS){for(const role of ['primary','accent'])$('scene-emphasis').querySelector(`[value="${role}"]`).textContent=roleName(role);$('scene-accent-text').parentElement.firstChild.textContent='Palabra de énfasis · '+roleName('accent');}
    $('inspector-empty').hidden = Boolean(s); $('scene-form').hidden = !s;
    if (!s) return;
    $('inspector-scene-name').textContent = `Escena ${String(state.project.timeline.indexOf(s)+1).padStart(2,'0')}`;
    $('inspector-scene-duration').textContent = `${(s.end-s.start).toFixed(2)} s`;
    $('scene-type').value = s.type; $('scene-start').value = s.start; $('scene-end').value = s.end;
    $('scene-asset').innerHTML = '<option value="">Sin recurso</option>' + state.project.assets.filter(a => ['video','image'].includes(assetKind(a))&&!sourceRelated(a)).map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('');
    $('scene-asset').value=s.asset_id||'';$('scene-asset').disabled=Boolean(isFreeMotion(s));const tracked=Boolean(s.camera_anchors?.length);for(const id of ['scene-focus-x','scene-focus-y','scene-chin'])$(id).disabled=tracked;let note=$('camera-anchor-state');if(!note){note=document.createElement('p');note.id='camera-anchor-state';note.className='small-copy';$('presenter-in-field').after(note);}note.hidden=!tracked;note.textContent=tracked?`${s.camera_anchors.length} anclas temporales de cámara registradas. El encuadre y la barbilla se interpolan en el cursor; no se sustituyen con los controles estáticos.`:'';
    $('scene-source-in').value = s.type === 'split' ? num(s.broll_in) : num(s.source_in, s.type === 'presenter' ? s.start : 0);
    $('scene-source-in').disabled=isFreeMotion(s)||['broll','split'].includes(s.type)&&assetKind(assetById(s.asset_id))==='image';
    $('scene-source-in').parentElement.firstChild.textContent = s.type === 'split' ? 'Entrada del b-roll superior (s)' : 'Entrada del recurso (s)';
    $('presenter-in-field').hidden=s.type!=='split';$('scene-presenter-in').value=num(s.source_in,s.start);for(const axis of ['x','y']){$(`scene-focus-${axis}`).value=num(s[`focus_${axis}`],.5);$(`focus-${axis}-output`).textContent=`${Math.round(num(s[`focus_${axis}`],.5)*100)} %`;}
    $('scene-template').value = s.template || 'kinetic'; $('scene-template').disabled = s.type !== 'motion' && s.type !== 'split';
    $('scene-title').value = s.title || ''; $('scene-subtitle').value = s.subtitle || '';
    $('scene-color').value = s.text_color || '#ffffff'; $('scene-emphasis').value = s.font === 'accent' ? 'accent' : 'primary';
    $('scene-accent-text').value=s.emphasis||'';$('scene-text-pause').value=s.text_pause_reason||'';
    $('scene-chin').value = num(s.chin_y,.65); $('chin-output').textContent = `${Math.round(num(s.chin_y,.65)*100)} %`;
    $('scene-color-reason').value = s.red_reason || s.color_reason || ''; $('scene-chin-reviewed').checked = Boolean(s.chin_reviewed);
    $('scene-nodes').value=(s.nodes||s.motion?.nodes||[]).map(n=>typeof n==='object'?n.label:n).join('\n');$('scene-labels').value=(s.motion?.labels||s.labels||[]).join('\n');$('scene-value').value=s.motion?.value??'';$('scene-value-from').value=s.motion?.from??0;$('scene-decimals').value=s.motion?.decimals??0;$('scene-suffix').value=s.motion?.suffix||'';
    $('motion-data-section').hidden=!['motion','split'].includes(s.type)||s.template==='custom';$('workflow-data').hidden=s.template!=='workflow';$('compare-data').hidden=s.template!=='compare';$('counter-data').hidden=s.template!=='counter';
    $('scene-transition').innerHTML='<option value="">Corte limpio</option>'+state.project.assets.filter(a=>assetKind(a)==='video'&&!sourceRelated(a)).map(a=>`<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('');$('scene-transition').value=s.transition_asset_id||'';$('scene-transition-duration').value=num(s.transition_duration,.5);$('scene-transition-source').value=num(s.transition_source_in);
    for (const effect of ['brightness','contrast','saturation']) {const display=effect==='brightness'?1+num(s.effects?.brightness):num(s.effects?.[effect],1);$( `scene-${effect}`).value = display; $(`${effect}-output`).textContent = `${Math.round(display*100)} %`;}
    $('scene-search').value = s.decision?.search || ''; $('scene-reason').value = s.decision?.reason || ''; $('scene-evidence').value = (s.decision?.evidence || []).join('\n');
    renderKeyframes();renderOverlays();renderFreeMotion(); renderSceneWarnings();
  }

  function sourceRelated(asset){
    const raw=assetById(state.project?.source);if(!asset||!raw)return false;
    const catalog=[...(state.project?.assets||[]),...state.assets],byId=new Map(catalog.map(item=>[item.id,item])),bySha=new Map(catalog.filter(item=>item.sha256).map(item=>[item.sha256,item]));let item=byId.get(asset.id)||asset;const seen=new Set();
    for(let index=0;index<64;index++){
      if(item.id===raw.id||raw.sha256&&item.sha256===raw.sha256)return true;const identity=item.id||item.sha256;if(seen.has(identity))return true;seen.add(identity);
      const metadata=item.metadata||{},provenance=metadata.provenance||{},declared=provenance.source_asset_id||metadata.source,parentId=typeof declared==='string'?declared:null,parentSha=typeof provenance.source_sha256==='string'?provenance.source_sha256:null;
      if(parentId===raw.id||parentSha&&parentSha===raw.sha256)return true;const parent=byId.get(parentId)||bySha.get(parentSha);if(!parent)return false;item=parent;
    }
    return true;
  }
  function visualCandidates(){return state.assets.map(a=>assetById(a.id)).filter(a=>['video','image'].includes(assetKind(a))&&!sourceRelated(a));}

  const motionEases=['linear','power1.inOut','power2.out','power2.inOut','power3.out'];
  const motionChannels=['x','y','scale','opacity','rotation','mask_progress'];
  const motionLabels={linear:'Lineal','power1.inOut':'Suave · entrada y salida','power2.out':'Rápida · salida suave','power2.inOut':'Aceleración y frenado','power3.out':'Impulso · salida larga'};
  function splitRatio(project=state.project){const value=project?.settings?.split_motion_ratio;return typeof value==='number'&&Number.isFinite(value)&&value>=.5&&value<=.55?value:.55;}
  function splitHeight(height,ratio=splitRatio()){return 2*Math.floor(height*ratio/2+.5);}
  function splitLabel(project=state.project){const ratio=splitRatio(project),percent=value=>String(Math.round(value*10000)/100);return percent(ratio)+'/'+percent(1-ratio);}
  function splitRatioOptions(project=state.project){const current=splitRatio(project),values=[.5,.55];if(!values.includes(current))values.splice(1,0,current);return values.map(value=>`<option value="${value}" ${value===current?'selected':''}>${splitLabel({settings:{split_motion_ratio:value}})} · motion / cámara</option>`).join('');}
  function selectedResolution(value,settings){const width=Number(value);return value==='current'?{width:settings.width,height:settings.height}:{width,height:Math.round(width*16/9)};}
  function motionDimensions(scene,width=canvas.width,height=canvas.height){return {width,height:scene?.type==='split'?splitHeight(height):height};}
  function isFreeMotion(scene){return ['motion','split'].includes(scene?.type)&&scene.template==='custom'&&scene.motion_design;}
  function cameraAt(scene,time=state.time-scene.start){
    const anchors=scene.camera_anchors||[];if(!anchors.length)return scene;if(time<=anchors[0].time)return anchors[0];for(let i=1;i<anchors.length;i++){const left=anchors[i-1],right=anchors[i];if(time<=right.time){const u=clamp((time-left.time)/Math.max(.000001,right.time-left.time),0,1);return Object.fromEntries(['focus_x','focus_y','chin_y'].map(key=>[key,left[key]+(right[key]-left[key])*u]));}}return anchors.at(-1);
  }
  function trimCameraAnchors(scene,lo,hi){
    if(!scene.camera_anchors?.length)return null;const points=[{time:0,...cameraAt(scene,lo)},...scene.camera_anchors.filter(key=>key.time>lo&&key.time<hi).map(key=>({...key,time:key.time-lo})),{time:hi-lo,...cameraAt(scene,hi)}];points[0].time=0;points.at(-1).time=hi-lo;const result=points.map(point=>({time:point.time,focus_x:point.focus_x,focus_y:point.focus_y,chin_y:point.chin_y}));if(result.length>300)throw new Error('El corte superaría 300 anclas de cámara. Reduce sus puntos antes de ampliar el tramo.');if(result.some((point,index)=>index&&point.time-result[index-1].time<.000001))throw new Error('El corte queda demasiado cerca de un ancla de cámara. Desplaza el cursor al siguiente fotograma.');return result;
  }
  function motionElement(){return selectedScene()?.motion_design?.elements.find(e=>e.id===state.selectedElement);}
  function motionLocal(scene=selectedScene()){return clamp(state.time-num(scene?.start),0,num(scene?.end)-num(scene?.start));}
  function motionEase(u,ease,window){
    u=clamp(u,0,1);const raw=value=>{if(ease==='linear')return value;const p={'power1.inOut':2,'power2.inOut':3,'power2.out':3,'power3.out':4}[ease]||1;return ease.endsWith('.out')?1-(1-value)**p:value<.5?(2*value)**p/2:1-(2*(1-value))**p/2;};
    if(!window)return raw(u);const [lo,hi]=window,a=raw(lo),b=raw(hi);return Math.abs(b-a)<1e-12?u:(raw(lo+(hi-lo)*u)-a)/(b-a);
  }
  function motionPathPoint(element,t,span,width=1080,height=1920){
    const points=element.path?.points;if(!points?.length)return null;
    const distances=points.slice(1).map((b,i)=>Math.hypot((b.x-points[i].x)*width,(b.y-points[i].y)*height)),total=distances.reduce((a,b)=>a+b,0);
    let travel=clamp((t-num(element.start))/Math.max(.00001,num(element.end,span)-num(element.start)),0,1)*total;
    if(!total)return {...points[0]};
    for(let i=0;i<distances.length;i++){const d=distances[i];if(d>0&&travel<=d){const u=travel/d,a=points[i],b=points[i+1];return {x:a.x+(b.x-a.x)*u,y:a.y+(b.y-a.y)*u};}travel-=d;}
    return {...points.at(-1)};
  }
  function motionPose(element,t,scene){
    const base={x:num(element.x),y:num(element.y),scale:1,opacity:num(element.opacity,1),rotation:num(element.rotation),mask_progress:1},poses=[{time:0,pose:base,ease:'linear'}];
    for(const key of [...element.keyframes||[]].sort((a,b)=>a.time-b.time)){
      const pose={...poses.at(-1).pose};for(const channel of motionChannels)if(key[channel]!==undefined)pose[channel]=num(key[channel]);
      const item={time:key.time,pose,ease:key.ease||'linear',window:key.ease_window};if(item.time===poses.at(-1).time)poses[poses.length-1]=item;else poses.push(item);
    }
    t=clamp(t,0,scene.end-scene.start);let pose={...poses.at(-1).pose};
    for(let i=1;i<poses.length;i++){const a=poses[i-1],b=poses[i];if(t<=b.time){const u=motionEase((t-a.time)/(b.time-a.time),b.ease,b.window);pose=Object.fromEntries(motionChannels.map(k=>[k,a.pose[k]+(b.pose[k]-a.pose[k])*u]));break;}}
    const designSize=motionDimensions(scene,state.project?.settings.width||1080,state.project?.settings.height||1920),path=motionPathPoint(element,t,scene.end-scene.start,designSize.width,designSize.height);return path?{...pose,...path}:pose;
  }
  function trimMotionDesign(scene,lo,hi){
    if(!isFreeMotion(scene))return scene.motion_design;
    const {width,height}=motionDimensions(scene,state.project.settings.width,state.project.settings.height),span=scene.end-scene.start,design=clone(scene.motion_design);
    design.elements=design.elements.filter(el=>num(el.end,span)>lo&&num(el.start)<hi).map(el=>{
      const original=clone(el),withoutPath={...original};delete withoutPath.path;
      if(original.type==='text'&&original.text_animation){const animation=original.text_animation;el.text_animation={...animation,clock_start:num(animation.clock_start,num(original.start))-lo,clock_offset:num(animation.clock_offset),clock_duration:num(animation.clock_duration,num(original.end,span)-num(original.start))};}
      const originalKeys=[...original.keyframes||[]].sort((a,b)=>a.time-b.time),times=[...new Set([lo,...(lo<0?[0]:[]),...originalKeys.filter(k=>k.time>lo&&k.time<hi).map(k=>k.time),...(hi>span?[span]:[]),hi])].sort((a,b)=>a-b);
      if(originalKeys.length){
        el.keyframes=times.map((t,i)=>{
          const pose=motionPose(withoutPath,t,scene),entry={time:t-lo,...pose,ease:'linear'};
          if(i){const previous=times[i-1],right=originalKeys.find(k=>k.time>=t),leftTime=right?Math.max(0,...originalKeys.filter(k=>k.time<right.time).map(k=>k.time)):0;
            if(right&&right.time>leftTime){const window=right.ease_window||[0,1],range=window[1]-window[0],a=window[0]+range*clamp((previous-leftTime)/(right.time-leftTime),0,1),b=window[0]+range*clamp((t-leftTime)/(right.time-leftTime),0,1);if(b>a){entry.ease=right.ease||'linear';entry.ease_window=[a,b];}}
          }
          if(!['circle','inset'].includes(el.mask?.type))delete entry.mask_progress;
          return entry;
        });
      }
      const start=Math.max(num(original.start),lo),end=Math.min(num(original.end,span),hi);
      el.start=start-lo;el.end=end-lo;if(el.type==='media'&&assetKind(assetById(el.asset_id))!=='image')el.source_in=num(original.source_in)+start-num(original.start);
      if(original.path){
        const points=original.path.points,distances=points.slice(1).map((b,i)=>Math.hypot((b.x-points[i].x)*width,(b.y-points[i].y)*height)),total=distances.reduce((a,b)=>a+b,0),a=clamp((start-num(original.start))/(num(original.end,span)-num(original.start)),0,1)*total,b=clamp((end-num(original.start))/(num(original.end,span)-num(original.start)),0,1)*total;
        let running=0;const middle=[];for(let i=1;i<points.length-1;i++){running+=distances[i-1];if(running>a&&running<b)middle.push(points[i]);}
        el.path={orient:false,points:[motionPathPoint(original,start,span,width,height),...middle,motionPathPoint(original,end,span,width,height)]};
      }
      return el;
    });
    if(design.elements.some(e=>(e.keyframes||[]).length>128))throw new Error('El corte añade claves de frontera y superaría 128 claves. Elimina una clave antes de cortar.');
    if(!design.elements.length)throw new Error('El corte dejaría la composición libre sin elementos. Ajusta primero sus intervalos visibles.');
    return design;
  }
  function newMotionElement(type,scene){
    const start=state.time>=scene.start&&state.time<scene.end?state.time-scene.start:0;
    const base={id:uid('element'),type,x:.1,y:.35,width:.8,height:.2,start,end:scene.end-scene.start,opacity:1,rotation:0,z:(scene.motion_design?.elements.length||0),color:'#ffffff',mask:{type:'none'},keyframes:[]};
    if(type==='text')return {...base,text:'Tu idea aquí',font:'primary',font_size:84};
    if(type==='shape')return {...base,x:.2,y:.4,width:.6,height:.15,shape:'rect',radius:24,color:'#40546b'};
    return {...base,x:.15,y:.25,width:.7,height:.45,asset_id:'',source_in:0};
  }
  function enableFreeMotion(scene){
    if(scene.type!=='split')scene.type='motion';scene.template='custom';scene.motion_design||={canvas:{background:'#101318'},elements:[]};
    if(!scene.motion_design.elements.length)scene.motion_design.elements.push(newMotionElement('text',scene));
    state.project.settings.engine='hyperframes';state.selectedElement=scene.motion_design.elements[0].id;
  }
  function createFreeMotion(){
    if(!state.project)return;addScene({template:'custom'});const scene=selectedScene();enableFreeMotion(scene);dirty();renderProject();switchTab('motion');canvas.focus();
  }
  async function addMotionElement(type,assetId){
    let scene=selectedScene();if(!isFreeMotion(scene))return;
    if(scene.motion_design.elements.length>=64)throw new Error('Una composición admite hasta 64 elementos.');
    let asset;
    if(type==='media'){
      const raw=assetById(state.project.source),candidates=visualCandidates().filter(a=>a.sha256!==raw?.sha256);
      if(!candidates.length)throw new Error('Importa un recurso visual distinto del crudo para añadir un medio.');
      if(!assetId){modal('Añadir un medio al diseño',`<p class="modal-copy">Elige una imagen o clip propio. El crudo y sus copias quedan excluidos de motion.</p><div class="assets-grid">${candidates.map(a=>`<button type="button" class="asset-card" data-motion-media="${esc(a.id)}"><div class="asset-thumbnail">${thumbnailUrl(a)?`<img src="${esc(thumbnailUrl(a))}" alt="">`:icon('film')}</div><span class="asset-name">${esc(a.name)}</span><span class="asset-meta">${esc(assetKind(a))} · ${fmt(a.duration,false)}</span></button>`).join('')}</div>`,()=>{$('modal-content').querySelectorAll('[data-motion-media]').forEach(b=>b.onclick=action(async()=>{$('modal').close();await addMotionElement('media',b.dataset.motionMedia);}));});return;}
      asset=candidates.find(a=>a.id===assetId);if(!asset)throw new Error('Selecciona un recurso distinto del crudo.');
      const sceneId=scene.id;await attachForOverlay(asset.id);scene=state.project.timeline.find(s=>s.id===sceneId);if(!isFreeMotion(scene)||state.selectedScene!==sceneId)throw new Error('La selección cambió mientras se adjuntaba el medio. Vuelve a añadirlo en la escena deseada.');if(scene.motion_design.elements.length>=64)throw new Error('La escena ya tiene 64 elementos.');
    }
    mutate(()=>{const element=newMotionElement(type,scene);if(asset){element.asset_id=asset.id;element.end=Math.min(element.end,assetKind(asset)==='image'?element.end:element.start+num(asset.duration,element.end-element.start));}scene.motion_design.elements.push(element);state.selectedElement=element.id;state.selectedPathPoint=null;});
  }
  function selectMotionElement(id){if(state.selectedElement!==id)state.selectedPathPoint=null;state.selectedElement=id;renderFreeMotion();drawPreview();const element=motionElement();$('canvas-edit-status').textContent=element?`Seleccionado: ${element.type==='text'?element.text.slice(0,60):element.type==='shape'?'forma':assetById(element.asset_id)?.name||'medio'}`:'Elemento deseleccionado.';}
  function motionNumber(key,label,value,min,max,step='.01',attrs=''){return `<label class="field">${label}<input data-motion-field="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${num(value)}" ${attrs}></label>`;}
  function textStyle(element){const style=element.text_style||{};return {align:style.align||'left',vertical_align:style.vertical_align||'top',letter_spacing:num(style.letter_spacing),line_height:num(style.line_height,1.15),stroke:{width:num(style.stroke?.width),color:style.stroke?.color||'#000000'},shadow:{enabled:style.shadow?.enabled!==false,x:num(style.shadow?.x,2),y:num(style.shadow?.y,4),blur:num(style.shadow?.blur),color:style.shadow?.color||'#000000',opacity:num(style.shadow?.opacity,.85)}};}
  function textAnimation(element,scene){const value=element.text_animation||{},span=num(value.clock_duration,num(element.end,scene.end-scene.start)-num(element.start));return {...value,preset:value.preset||'none',duration:num(value.duration,Math.max(.01,Math.min(.6,span))),exit:value.exit||'none',exit_duration:num(value.exit_duration,Math.max(.01,Math.min(.2,span)))};}
  function validateTextTiming(element,scene){const animation=textAnimation(element,scene),span=num(animation.clock_duration,num(element.end,scene.end-scene.start)-num(element.start)),elapsedStart=num(element.start)-num(animation.clock_start,num(element.start))+num(animation.clock_offset),elapsedEnd=num(element.end,scene.end-scene.start)-num(animation.clock_start,num(element.start))+num(animation.clock_offset);const active=(animation.preset!=='none'?animation.duration:0)+(animation.exit!=='none'?animation.exit_duration:0);if(active>span+1e-7)throw new Error('La entrada y salida sumadas deben caber en el tramo del texto. Reduce una de sus duraciones.');if(elapsedStart<-.0000001||elapsedEnd>span+.0000001)throw new Error('Este cambio saldría del reloj original. Reinicia la animación del tramo antes de ampliar su intervalo.');}
  function textStyleNumber(key,label,value,min,max,step='.01'){return `<label class="field">${label}<input data-text-style="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${num(value)}"></label>`;}
  function textStyleColor(key,label,value){return `<label class="field">${label}<input data-text-style="${key}" type="color" value="${esc(value)}"></label>`;}
  function textControls(element,scene){
    const style=textStyle(element),animation=textAnimation(element,scene),clockSpan=num(animation.clock_duration,num(element.end,scene.end-scene.start)-num(element.start)),fonts=state.fontLibrary?.fonts||[],labels={none:'Sin entrada',fade_up:'Elevar y revelar',slide:'Desplazar desde izquierda',pop:'Énfasis de escala',wipe:'Revelación por máscara',typewriter:'Revelar caracteres',word_reveal:'Revelar palabras'},presets=(state.textPresets?.presets||[]).map(value=>typeof value==='string'?{id:value,name:labels[value]||value}:value),choice=element.font_asset_id?'asset:'+element.font_asset_id:element.font||'primary';
    return `<div class="field-pair"><label class="field">Fuente local<select data-motion-field="font"><optgroup label="Roles de marca"><option value="primary" ${choice==='primary'?'selected':''}>${esc(roleName('primary'))}</option><option value="accent" ${choice==='accent'?'selected':''}>${esc(roleName('accent'))}</option></optgroup>${fonts.length?`<optgroup label="Biblioteca local">${fonts.map(font=>`<option value="asset:${esc(font.asset_id||font.id)}" ${choice==='asset:'+(font.asset_id||font.id)?'selected':''} ${font.available===false?'disabled':''}>${esc(font.family||font.name)} · ${esc(font.style||'Local')}</option>`).join('')}</optgroup>`:''}${element.font_asset_id&&!fonts.some(font=>(font.asset_id||font.id)===element.font_asset_id)?`<option value="${esc(choice)}" selected>Fuente adjunta · catálogo pendiente</option>`:''}</select></label>${motionNumber('font_size','Tamaño · px1080',element.font_size,8,400,1)}</div><button id="text-font-library" type="button" class="button ghost full">Ver fuentes y licencia</button><p id="motion-text-preview-state" class="small-copy" aria-live="polite"></p><button id="retry-text-preview" type="button" class="button ghost full" hidden>Volver a consultar la fuente y preparar el texto</button>
      <details open class="motion-text-style"><summary>Tipografía y acabado</summary><div class="field-pair"><label class="field">Alineación<select data-text-style="align">${[['left','Izquierda'],['center','Centro'],['right','Derecha']].map(([value,label])=>`<option value="${value}" ${style.align===value?'selected':''}>${label}</option>`).join('')}</select></label><label class="field">Posición vertical<select data-text-style="vertical_align">${[['top','Arriba'],['middle','Medio'],['bottom','Abajo']].map(([value,label])=>`<option value="${value}" ${style.vertical_align===value?'selected':''}>${label}</option>`).join('')}</select></label></div><div class="field-pair">${textStyleNumber('letter_spacing','Espaciado · px1080',style.letter_spacing,-16,80)}${textStyleNumber('line_height','Interlineado',style.line_height,.8,3)}</div><div class="field-pair">${textStyleNumber('stroke.width','Contorno · px1080',style.stroke.width,0,16)}${textStyleColor('stroke.color','Color del contorno',style.stroke.color)}</div><label class="review-check"><input data-text-style="shadow.enabled" type="checkbox" ${style.shadow.enabled?'checked':''}><span>Sombra del texto</span></label><div class="field-pair">${textStyleNumber('shadow.x','Sombra X · px1080',style.shadow.x,-40,40)}${textStyleNumber('shadow.y','Sombra Y · px1080',style.shadow.y,-40,40)}</div><div class="field-pair">${textStyleNumber('shadow.blur','Desenfoque · px1080',style.shadow.blur,0,20)}${textStyleNumber('shadow.opacity','Opacidad de sombra',style.shadow.opacity,0,1)}</div>${textStyleColor('shadow.color','Color de la sombra',style.shadow.color)}<p class="small-copy">Texto dentro de su caja. El acabado se aplica a este elemento; los subtítulos de la marca conservan sus reglas.</p></details>
      <details open class="motion-text-animation"><summary>Animación del texto</summary><label class="field">Entrada<select data-text-animation="preset" ${presets.length?'':'disabled'}><option value="none" ${animation.preset==='none'?'selected':''}>Sin entrada</option>${presets.filter(preset=>(preset.id||preset.preset)!=='none').map(preset=>`<option value="${esc(preset.id||preset.preset)}" ${animation.preset===(preset.id||preset.preset)?'selected':''}>${esc(preset.name||preset.label||preset.id||preset.preset)}</option>`).join('')}</select></label><label class="field">Duración de entrada (s)<input data-text-animation="duration" type="number" min=".01" max="${Math.min(10,clockSpan)}" step=".01" value="${animation.duration}"></label><div class="field-pair"><label class="field">Salida<select data-text-animation="exit">${[['none','Sin salida'],['fade','Disolver'],['slide','Desplazar']].map(([value,label])=>`<option value="${value}" ${animation.exit===value?'selected':''}>${label}</option>`).join('')}</select></label><label class="field">Duración de salida (s)<input data-text-animation="exit_duration" type="number" min=".01" max="${Math.min(10,clockSpan)}" step=".01" value="${animation.exit_duration}"></label></div><p class="small-copy">La entrada y salida actúan dentro del texto, conservando las claves y trayectorias del elemento.</p>${animation.clock_start!==undefined||animation.clock_offset!==undefined||animation.clock_duration!==undefined?`<p class="small-copy">Este tramo conserva la fase de una animación recortada.</p><button id="text-reset-clock" type="button" class="button ghost full">Reiniciar animación en este tramo</button>`:''}</details>`;
  }
  function updateTextPreviewStatus(){const element=motionElement(),scene=selectedScene(),node=$('motion-text-preview-state'),retry=$('retry-text-preview');if(!node||element?.type!=='text'||!scene)return;if(retry)retry.hidden=true;const status=customFontStatus(element);if(status&&status.status!=='loaded'){node.textContent=status.error||'Cargando el archivo de fuente local…';if(retry)retry.hidden=!status.error;return;}if(!window.AscendiaTypography){node.textContent='La vista previa tipográfica espera al motor local actualizado.';return;}const entry=textLayout(element,scene);node.textContent=entry.status==='ready'?'Texto preparado con la fuente local. Revisa la captura y el render para comprobar su apariencia.':entry.error||'Preparando el texto y sus líneas…';if(retry)retry.hidden=!entry.error;}
  function textLayout(element,scene){
    const role=roleRecord(element.font||'primary'),font=element.font_asset_id?fontRecord(element.font_asset_id):role,span=scene.end-scene.start;
    const draft={id:element.id,type:'text',text:element.text,font:element.font||'primary',font_size:num(element.font_size,84),font_asset_id:element.font_asset_id,color:element.color||'#ffffff',x:0,y:0,width:element.width,height:element.height,start:0,end:span,text_style:element.text_style||{}};
    const body={project_id:state.project.id,element:draft,scene_duration:span,width:canvas.width,height:motionDimensions(scene).height},key=JSON.stringify([state.loadEpoch,font?.sha256||'',body]);
    let entry=state.textLayouts.get(key);if(entry)return entry;
    const scope={projectId:state.project.id,load:state.loadEpoch,edit:state.editEpoch,sceneId:scene.id,elementId:element.id};entry={key,body,scope,status:'loading',layout:null,error:null};state.textLayouts.set(key,entry);state.textLayoutQueue.push(entry);
    if(state.textLayouts.size>256){const first=state.textLayouts.keys().next().value;if(first!==key)state.textLayouts.delete(first);}
    pumpTextLayouts();return entry;
  }
  async function pumpTextLayouts(){
    if(state.textLayoutBusy)return;state.textLayoutBusy=true;
    try{while(state.textLayoutQueue.length){const entry=state.textLayoutQueue.shift(),scope=entry.scope;if(state.project?.id!==scope.projectId||state.loadEpoch!==scope.load||currentScene()?.id!==scope.sceneId&&!(state.selectedScene===scope.sceneId&&state.selectedElement===scope.elementId)){state.textLayouts.delete(entry.key);continue;}try{const response=await api('/api/text-layout',{method:'POST',body:entry.body});entry.layout=response.layout||response;entry.status='ready';}catch(error){entry.status='error';entry.error=error.message;}if(state.project?.id===scope.projectId&&state.loadEpoch===scope.load){drawPreview();if(state.selectedElement===scope.elementId)updateTextPreviewStatus();}}}finally{state.textLayoutBusy=false;}
  }

  function easingOptions(ease){return motionEases.map(v=>`<option value="${v}" ${v===(ease||'linear')?'selected':''}>${motionLabels[v]}</option>`).join('');}
  function motionFocusToken(panel){
    const active=document.activeElement;if(!panel.contains(active))return null;let selector;
    if(active.id)selector=`#${CSS.escape(active.id)}`;
    else if(active.dataset.motionField)selector=`[data-motion-field="${active.dataset.motionField}"]`;
    else if(active.dataset.motionKeyField)selector=`[data-motion-key="${active.closest('[data-motion-key]').dataset.motionKey}"] [data-motion-key-field="${active.dataset.motionKeyField}"]`;
    else if(active.dataset.motionPointField)selector=`[data-motion-point="${active.closest('[data-motion-point]').dataset.motionPoint}"] [data-motion-point-field="${active.dataset.motionPointField}"]`;
    else if(active.dataset.textStyle)selector=`[data-text-style="${active.dataset.textStyle}"]`;
    else if(active.dataset.textAnimation)selector=`[data-text-animation="${active.dataset.textAnimation}"]`;
    else if(active.dataset.motionMask)selector=`[data-motion-mask="${active.dataset.motionMask}"]`;
    return selector?{selector,start:active.selectionStart,end:active.selectionEnd}:null;
  }
  function renderFreeMotion(){
    const scene=selectedScene(),design=isFreeMotion(scene)?scene.motion_design:null;$('free-motion-section').hidden=!design;
    $('canvas-edit-help').hidden=!isFreeMotion(currentScene())||state.mode!=='timeline';if(!design)return;
    const elements=design.elements,span=scene.end-scene.start;
    if(state.selectedElement!==null&&!elements.some(e=>e.id===state.selectedElement))state.selectedElement=elements[0]?.id||null;
    $('motion-background').value=design.canvas?.background||'#101318';
    $('snapshot-design').disabled=capabilityAvailability(state.status?.capabilities?.static_design)!==true;
    const snapshot=state.project.design_snapshots?.[scene.id],review=state.project.design_reviews?.[scene.id];$('review-design').hidden=!snapshot;
    $('design-snapshot-state').textContent=snapshot?`PNG generado · ${String(snapshot.sha256||'').slice(0,12)}. ${review?'Revisión registrada; el backend comprobará su vigencia.':'Pendiente de revisión explícita.'} La vista del lienzo es aproximada; revisa esta captura real.`:'La captura real y su aprobación explícita se comprueban antes de la animación narrativa.';
    ['text','shape','media'].forEach(type=>$(`motion-add-${type}`).disabled=elements.length>=64);
    $('motion-elements-list').innerHTML=elements.map((e,i)=>`<button type="button" class="motion-element-item ${e.id===state.selectedElement?'selected':''}" data-motion-select="${esc(e.id)}" aria-pressed="${e.id===state.selectedElement}"><span class="motion-kind">${e.type==='text'?'T':e.type==='shape'?'◧':'▧'}</span><span>${esc(e.type==='text'?e.text.slice(0,45)||'Texto vacío':e.type==='shape'?(e.shape==='ellipse'?'Elipse':'Rectángulo'):assetById(e.asset_id)?.name||'Medio')}<small>${num(e.start).toFixed(2)}–${num(e.end,span).toFixed(2)} s · orden ${num(e.z,i)}</small></span><span>${(e.keyframes||[]).length?'◆':''}</span></button>`).join('');
    $('motion-elements-list').querySelectorAll('[data-motion-select]').forEach(b=>b.onclick=()=>selectMotionElement(b.dataset.motionSelect));
    const el=motionElement(),panel=$('motion-element-inspector'),focus=motionFocusToken(panel),detailStates=new Map([...$('motion-element-inspector').querySelectorAll('details')].map(n=>[n.className,n.open]));if(!el){panel.innerHTML='';return;}
    const raw=assetById(state.project.source),candidates=visualCandidates().filter(a=>a.sha256!==raw?.sha256),pose=motionPose(el,motionLocal(scene),scene),mask=el.mask||{type:'none'};
    panel.innerHTML=`<div class="motion-element-tools"><strong>Elemento ${elements.indexOf(el)+1} / ${elements.length}</strong><button type="button" id="motion-duplicate" aria-label="Duplicar elemento" title="Duplicar elemento" ${elements.length>=64?'disabled':''}>⧉</button><button type="button" id="motion-raise" aria-label="Subir elemento delante" title="Subir delante">↑</button><button type="button" id="motion-lower" aria-label="Bajar elemento detrás" title="Bajar detrás">↓</button><button type="button" id="motion-delete" aria-label="Eliminar elemento" title="Eliminar elemento" ${elements.length<=1?'disabled':''}>×</button></div>
      ${el.type==='text'?`<label class="field">Texto libre<textarea data-motion-field="text" rows="3" maxlength="2000">${esc(el.text)}</textarea></label>${textControls(el,scene)}`:''}
      ${el.type==='shape'?`<div class="field-pair"><label class="field">Forma<select data-motion-field="shape"><option value="rect" ${el.shape==='rect'?'selected':''}>Rectángulo</option><option value="ellipse" ${el.shape==='ellipse'?'selected':''}>Elipse</option></select></label>${motionNumber('radius','Radio · px1080',el.radius,0,540,1)}</div>`:''}
      ${el.type==='media'?`<label class="field">Medio local<select data-motion-field="asset_id">${candidates.map(a=>`<option value="${esc(a.id)}" ${a.id===el.asset_id?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label>${motionNumber('source_in','Entrada del archivo (s)',el.source_in,0,86400,'.01',assetKind(assetById(el.asset_id))==='image'?'disabled':'')}<p class="small-copy">Contain centrado: conserva proporciones y transparencia.</p>`:`<label class="field">Color<input data-motion-field="color" type="color" value="${esc(el.color||'#ffffff')}"></label><label class="field">Intención del color · si usas rojo<input data-motion-field="color_reason" value="${esc(el.color_reason||'')}" placeholder="Riesgo, contraste o significado en el guion"></label>`}
      <div class="field-pair">${motionNumber('start','Visible desde (s)',el.start,0,num(el.end,span)-.01)}${motionNumber('end','Visible hasta (s)',el.end,num(el.start)+.01,span)}</div>
      <div class="field-pair">${motionNumber('x','X base · 0–1',el.x,0,1-el.width)}${motionNumber('y','Y base · 0–1',el.y,0,1-el.height)}</div>
      <div class="field-pair">${motionNumber('width','Ancho de caja',el.width,.005,1-el.x)}${motionNumber('height','Alto de caja',el.height,.005,1-el.y)}</div>
      <div class="field-pair">${motionNumber('opacity','Opacidad base',el.opacity,0,1)}${motionNumber('rotation','Rotación base · °',el.rotation,-3600,3600,1)}</div>
      <p class="motion-pose-readout">Cursor local <strong id="motion-local-time">${motionLocal(scene).toFixed(2)} s</strong> · X <span id="motion-current-x">${pose.x.toFixed(3)}</span> / Y <span id="motion-current-y">${pose.y.toFixed(3)}</span></p>
      <details open class="motion-animation-details"><summary>Keyframes y curvas</summary><label class="review-check"><input id="motion-auto-key" type="checkbox" ${state.motionAutokey?'checked':''}><span>Con claves existentes, arrastrar añade una clave en el cursor. Sin claves, mueve el diseño base.</span></label><button id="motion-add-key" type="button" class="button ghost full" ${(el.keyframes||[]).length>=128?'disabled':''}>◆ Capturar pose en el cursor</button><div id="motion-keyframes">${[...el.keyframes||[]].sort((a,b)=>a.time-b.time).map((key,i)=>`<div class="motion-keyframe" data-motion-key="${i}"><div class="motion-key-heading"><button type="button" data-motion-seek-key="${i}">◆ ${key.time.toFixed(2)} s</button><button type="button" data-motion-delete-key="${i}" aria-label="Eliminar clave a ${key.time.toFixed(2)} segundos" title="Eliminar keyframe">×</button></div><div class="field-pair">${[['time','Tiempo',0,span],['x','X absoluto',-2,2],['y','Y absoluto',-2,2],['scale','Escala',.01,8],['opacity','Opacidad',0,1],['rotation','Rotación °',-3600,3600],...(['circle','inset'].includes(mask.type)?[['mask_progress','Revelación máscara',0,1]]:[])].map(([k,label,min,max])=>`<label class="field">${label}<input data-motion-key-field="${k}" type="number" min="${min}" max="${max}" step=".01" value="${num(key[k],motionPose(el,key.time,scene)[k])}"></label>`).join('')}</div><label class="field">Curva hacia esta clave<select data-motion-key-field="ease">${easingOptions(key.ease)}</select></label><svg class="motion-curve" viewBox="0 0 160 48" role="img" aria-label="Curva ${esc(motionLabels[key.ease||'linear'])}"><path class="curve-grid" d="M0 46H160 M2 0V48"/><path d="${Array.from({length:41},(_,j)=>`${j?'L':'M'}${2+j/40*156},${46-motionEase(j/40,key.ease||'linear',key.ease_window)*44}`).join(' ')}"/></svg>${key.ease_window?`<p class="motion-window-note">Curva recortada: ${key.ease_window.map(v=>v.toFixed(3)).join(" → ")}. Conserva el movimiento original.</p>`:""}</div>`).join('')||'<p class="small-copy">El diseño permanece estático hasta añadir claves.</p>'}</div></details>
      <details class="motion-mask-details"><summary>Máscara geométrica</summary><label class="field">Recorte<select id="motion-mask-type"><option value="none" ${mask.type==='none'?'selected':''}>Sin máscara</option><option value="circle" ${mask.type==='circle'?'selected':''}>Círculo centrado</option><option value="inset" ${mask.type==='inset'?'selected':''}>Insets de la caja</option></select></label>${mask.type==='inset'?`<div class="field-pair">${['top','right','bottom','left'].map((side,i)=>`<label class="field">${['Arriba','Derecha','Abajo','Izquierda'][i]}<input data-motion-mask="${side}" type="number" min="0" max=".99" step=".01" value="${num(mask.inset?.[side])}"></label>`).join('')}</div>`:''}</details>
      <details class="motion-path-details" ${el.path?'open':''}><summary>Trayectoria por puntos</summary><p class="small-copy">Posiciones absolutas de la esquina superior. Velocidad constante por distancia real desde el inicio hasta el fin del elemento; sustituye X/Y de las claves.</p><label class="review-check"><input id="motion-path-enabled" type="checkbox" ${el.path?'checked':''}><span>Seguir una trayectoria editable</span></label>${el.path?`<div id="motion-path-points">${el.path.points.map((point,i)=>`<div class="motion-path-point" data-motion-point="${i}"><button type="button" data-motion-select-point="${i}" aria-label="Seleccionar punto ${i+1} en el lienzo" title="Editar este punto en el lienzo">${i+1}</button>${['x','y'].map(axis=>`<label>${axis.toUpperCase()}<input data-motion-point-field="${axis}" type="number" min="-2" max="2" step=".01" value="${point[axis]}"></label>`).join('')}<button type="button" data-motion-delete-point="${i}" aria-label="Eliminar punto ${i+1}" title="Eliminar punto" ${el.path.points.length<=2?'disabled':''}>×</button></div>`).join('')}</div><button id="motion-add-point" class="button ghost full" type="button" ${el.path.points.length>=64?'disabled':''}>Añadir punto después del último</button>`:''}</details>`;
    panel.querySelectorAll('[data-motion-field]').forEach(input=>input.onchange=action(async()=>{
      const key=input.dataset.motionField;let value=input.type==='number'?num(input.value):input.value;
      if(key==='font'){await selectTextFont(value.startsWith('asset:')?value:'role:'+value);return;}
      if(input.type==='number')value=clamp(value,num(input.min,-Infinity),num(input.max,Infinity));
      if(key==='asset_id'){const sceneId=scene.id;await attachForOverlay(value);state.selectedScene=sceneId;}
      const item=motionElement(),timing=item.type==='text'&&['start','end'].includes(key)&&item.text_animation?{...item.text_animation,clock_start:num(item.text_animation.clock_start,num(item.start)),clock_offset:num(item.text_animation.clock_offset),clock_duration:num(item.text_animation.clock_duration,num(item.end,span)-num(item.start))}:null;if(timing){const draft={...item,[key]:value,text_animation:timing};validateTextTiming(draft,scene);}
      mutate(()=>{if(timing)item.text_animation=timing;item[key]=value;if(key==='asset_id'){item.source_in=0;const asset=assetById(value);if(assetKind(asset)!=='image')item.end=Math.min(item.end,item.start+num(asset.duration,span));}});
    }));
    if(el.type==='text'){
      $('text-font-library').onclick=action(()=>fontLibraryDialog(el.font_asset_id||null));
      $('retry-text-preview').onclick=action(async()=>{const scope=textSelectionScope();await refreshFontLibrary();if(textScopeMatches(scope)){updateTextPreviewStatus();drawPreview();}});
      panel.querySelectorAll('[data-text-style]').forEach(input=>input.onchange=()=>{const path=input.dataset.textStyle.split('.'),value=input.type==='checkbox'?input.checked:input.type==='number'?clamp(num(input.value),num(input.min,-Infinity),num(input.max,Infinity)):input.value;mutate(()=>{el.text_style=textStyle(el);if(path.length===2)el.text_style[path[0]][path[1]]=value;else el.text_style[path[0]]=value;});});
      panel.querySelectorAll('[data-text-animation]').forEach(input=>input.onchange=action(()=>{const key=input.dataset.textAnimation,value=input.type==='number'?clamp(num(input.value),num(input.min,.01),Math.min(10,num(input.max,Infinity))):input.value,draft=clone(el);draft.text_animation=textAnimation(el,scene);draft.text_animation[key]=value;validateTextTiming(draft,scene);mutate(()=>el.text_animation=draft.text_animation);}));
      if($('text-reset-clock'))$('text-reset-clock').onclick=action(()=>{const draft=clone(el);for(const key of ['clock_start','clock_offset','clock_duration'])delete draft.text_animation[key];const animation=draft.text_animation,span=el.end-el.start,active=(animation.preset!=='none'?animation.duration:0)+(animation.exit!=='none'?animation.exit_duration:0);if(active>span){const factor=span/active;if(animation.preset!=='none')animation.duration=Math.max(.01,animation.duration*factor);if(animation.exit!=='none')animation.exit_duration=Math.max(.01,animation.exit_duration*factor);}validateTextTiming(draft,scene);mutate(()=>el.text_animation=animation);});
      updateTextPreviewStatus();
    }
    $('motion-duplicate').onclick=()=>mutate(()=>{const item=clone(el);item.id=uid('element');item.z=Math.max(...elements.map(e=>num(e.z)))+1;elements.push(item);state.selectedElement=item.id;});
    $('motion-delete').onclick=deleteMotionElement;
    for(const [id,direction] of [['motion-raise',1],['motion-lower',-1]])$(id).onclick=()=>mutate(()=>{const ordered=[...elements].sort((a,b)=>num(a.z)-num(b.z)),index=ordered.indexOf(el),other=ordered[index+direction];ordered.forEach((item,i)=>item.z=i);if(other){const z=el.z;el.z=other.z;other.z=z;}});
    $('motion-auto-key').onchange=()=>{state.motionAutokey=$('motion-auto-key').checked;};
    $('motion-add-key').onclick=action(()=>{if((el.keyframes||[]).length>=128)throw new Error('El máximo es de 128 keyframes por elemento.');mutate(()=>upsertMotionKey(el,motionLocal(scene),motionPose(el,motionLocal(scene),scene),span));});
    const keys=[...el.keyframes||[]].sort((a,b)=>a.time-b.time);
    panel.querySelectorAll('[data-motion-key-field]').forEach(input=>input.onchange=action(()=>{const key=keys[Number(input.closest('[data-motion-key]').dataset.motionKey)],field=input.dataset.motionKeyField,value=field==='ease'?input.value:clamp(num(input.value),num(input.min,-Infinity),num(input.max,Infinity));if(field==='time'&&el.keyframes.some(k=>k!==key&&Math.abs(k.time-value)<.00001)){input.value=key.time;throw new Error('Ya existe una clave en ese tiempo.');}mutate(()=>{key[field]=value;el.keyframes.sort((a,b)=>a.time-b.time);});}));
    panel.querySelectorAll('[data-motion-delete-key]').forEach(b=>b.onclick=()=>mutate(()=>el.keyframes.splice(el.keyframes.indexOf(keys[Number(b.dataset.motionDeleteKey)]),1)));
    panel.querySelectorAll('[data-motion-seek-key]').forEach(b=>b.onclick=()=>seekTime(scene.start+keys[Number(b.dataset.motionSeekKey)].time));
    $('motion-mask-type').onchange=()=>mutate(()=>{el.mask={type:$('motion-mask-type').value,inset:{top:0,right:0,bottom:0,left:0}};if(el.mask.type==='none')for(const key of el.keyframes||[])delete key.mask_progress;});
    panel.querySelectorAll('[data-motion-mask]').forEach(input=>input.onchange=action(()=>{const side=input.dataset.motionMask,opposite={top:'bottom',bottom:'top',left:'right',right:'left'}[side],value=clamp(num(input.value),0,.99);if(value+num(el.mask.inset[opposite])>=1){input.value=num(el.mask.inset[side]);throw new Error('La máscara debe conservar una parte visible de la caja.');}mutate(()=>el.mask.inset[side]=value);}));
    $('motion-path-enabled').onchange=()=>mutate(()=>{state.selectedPathPoint=null;if($('motion-path-enabled').checked)el.path={points:[{x:el.x,y:el.y},{x:Math.min(1-el.width,el.x+.15),y:Math.min(1-el.height,el.y+.1)}],orient:false};else delete el.path;});
    panel.querySelectorAll('[data-motion-select-point]').forEach(button=>button.onclick=()=>{state.selectedPathPoint=Number(button.dataset.motionSelectPoint);drawPreview();canvas.focus();$('canvas-edit-status').textContent=`Punto ${state.selectedPathPoint+1} seleccionado. Ajusta con flechas o arrastra en el lienzo.`;});
    panel.querySelectorAll('[data-motion-point-field]').forEach(input=>input.onchange=()=>mutate(()=>{el.path.points[Number(input.closest('[data-motion-point]').dataset.motionPoint)][input.dataset.motionPointField]=clamp(num(input.value),-2,2);}));
    panel.querySelectorAll('[data-motion-delete-point]').forEach(b=>b.onclick=()=>mutate(()=>{const index=Number(b.dataset.motionDeletePoint);el.path.points.splice(index,1);if(state.selectedPathPoint===index)state.selectedPathPoint=null;else if(state.selectedPathPoint>index)state.selectedPathPoint--; }));
    if($('motion-add-point'))$('motion-add-point').onclick=()=>mutate(()=>{const last=el.path.points.at(-1);el.path.points.push({x:clamp(last.x+.1,-2,2),y:clamp(last.y+.1,-2,2)});});
    panel.querySelectorAll('details').forEach(n=>{if(detailStates.has(n.className))n.open=detailStates.get(n.className);});
    if(focus){const target=panel.querySelector(focus.selector);if(target){target.focus({preventScroll:true});if(typeof target.setSelectionRange==='function'&&focus.start!==null)try{target.setSelectionRange(focus.start,focus.end);}catch(_){}}}
  }
  function deleteMotionElement(){const scene=selectedScene(),element=motionElement();if(!element)return;if(scene.motion_design.elements.length<=1){toast('Una composición libre requiere al menos un elemento.');return;}mutate(()=>{scene.motion_design.elements=scene.motion_design.elements.filter(e=>e.id!==element.id);state.selectedElement=scene.motion_design.elements[0].id;});}
  function upsertMotionKey(element,time,pose,maxTime=Infinity){
    element.keyframes||=[];pose={...pose};if(!['circle','inset'].includes(element.mask?.type))delete pose.mask_progress;time=clamp(time,0,maxTime);
    const keys=[...element.keyframes].sort((a,b)=>a.time-b.time),existing=keys.find(k=>Math.abs(k.time-time)<1e-7);
    if(existing)Object.assign(existing,pose,{time});
    else{
      if(keys.length>=128)throw new Error('El máximo es de 128 keyframes por elemento.');
      const key={time,...pose,ease:'linear'},right=keys.find(k=>k.time>time),leftTime=Math.max(0,...keys.filter(k=>k.time<time).map(k=>k.time));
      if(right&&time>leftTime){const window=right.ease_window||[0,1],cut=window[0]+(window[1]-window[0])*(time-leftTime)/(right.time-leftTime);key.ease=right.ease||'linear';key.ease_window=[window[0],cut];right.ease_window=[cut,window[1]];}
      element.keyframes.push(key);
    }
    element.keyframes.sort((a,b)=>a.time-b.time);
  }
  function motionMedia(element,scene){
    const asset=assetById(element.asset_id);if(!asset)return null;if(assetKind(asset)==='image')return imageFor(asset);
    const key=`${scene.id}:${element.id}`;let video=state.motionPlayers.get(key);
    if(!video){video=document.createElement('video');video.className='media-engine';video.muted=true;video.playsInline=true;video.preload='auto';document.body.append(video);state.motionPlayers.set(key,video);video.onseeked=drawPreview;}
    const time=num(element.source_in)+state.time-scene.start-num(element.start),url=assetUrl(asset);
    if(video.dataset.asset!==url){video.dataset.asset=url;video.pause();video.src=url;video.load();video.onloadedmetadata=()=>{video.currentTime=clamp(time,0,Math.max(0,video.duration-.03));};video.onerror=()=>toast('El medio de la composición no puede reproducirse. Comprueba su proxy.',true);}
    if(video.readyState>=2&&!video.seeking&&Math.abs(video.currentTime-time)>.1)video.currentTime=clamp(time,0,Math.max(0,video.duration-.03));
    if(state.playing&&video.paused&&video.readyState>=2){video.playbackRate=Number($('playback-speed').value);video.play().catch(()=>{});}else if(!state.playing)video.pause();return video;
  }
  function motionClip(context,el,bw,bh,progress=1){
    context.beginPath();context.rect(0,0,bw,bh);context.clip();const mask=el.mask||{};
    if(mask.type==='circle'){context.beginPath();context.arc(bw/2,bh/2,Math.min(bw,bh)/2*progress,0,Math.PI*2);context.clip();}
    else if(mask.type==='inset'){const m=mask.inset||{},left=num(m.left)*bw,top=num(m.top)*bh,right=num(m.right)+(1-num(m.left)-num(m.right))*(1-progress);context.beginPath();context.rect(left,top,bw-left-right*bw,bh-top-num(m.bottom)*bh);context.clip();}
  }
  function drawFreeMotion(scene){
    const {width:w,height:h}=motionDimensions(scene),span=scene.end-scene.start,t=state.time-scene.start,active=new Set();canvas.dataset.motionCanvas=JSON.stringify({width:w,height:h});
    ctx.save();ctx.beginPath();ctx.rect(0,0,w,h);ctx.clip();ctx.fillStyle=scene.motion_design.canvas?.background||'#101318';ctx.fillRect(0,0,w,h);
    for(const el of [...scene.motion_design.elements].sort((a,b)=>num(a.z)-num(b.z))){
      if(t<num(el.start)||t>=num(el.end,span))continue;
      const pose=motionPose(el,t,scene),bw=el.width*w,bh=el.height*h;
      ctx.save();ctx.globalAlpha=pose.opacity;ctx.translate(pose.x*w+bw/2,pose.y*h+bh/2);ctx.rotate(pose.rotation*Math.PI/180);ctx.scale(pose.scale,pose.scale);ctx.translate(-bw/2,-bh/2);motionClip(ctx,el,bw,bh,pose.mask_progress);
      if(el.type==='shape'){ctx.fillStyle=el.color||'#ffffff';ctx.beginPath();if(el.shape==='ellipse')ctx.ellipse(bw/2,bh/2,bw/2,bh/2,0,0,Math.PI*2);else ctx.roundRect(0,0,bw,bh,Math.min(num(el.radius)*w/1080,bw/2,bh/2));ctx.fill();}
      else if(el.type==='text'){
        const fontState=customFontStatus(el),ready=el.font_asset_id?fontState?.status==='loaded':!SaaS||state.fontsLoaded,helper=window.AscendiaTypography;
        if(ready&&helper){const entry=textLayout(el,scene);if(entry.status==='ready'){const font=el.font_asset_id?fontRecord(el.font_asset_id):null,family=el.font_asset_id?fontState.family:roleFamily(el.font||'primary');helper.paintTextLayout(ctx,entry.layout,helper.animationState(el,t,span),{fontFamily:family,fontItalic:font?fontItalic(font):roleItalic(el.font||'primary')});}}
      }else{
        active.add(`${scene.id}:${el.id}`);const media=motionMedia(el,scene),mw=media?.videoWidth||media?.naturalWidth,mh=media?.videoHeight||media?.naturalHeight;
        if(mw&&mh&&(media.naturalWidth||media.readyState>=2)){const scale=Math.min(bw/mw,bh/mh),dw=mw*scale,dh=mh*scale;ctx.drawImage(media,(bw-dw)/2,(bh-dh)/2,dw,dh);}
      }
      ctx.restore();
    }
    state.motionPlayers.forEach((video,key)=>{if(!active.has(key))video.pause();});ctx.restore();
  }
  function motionScenePoint(point,scene,inverse=false){
    const w=canvas.width,h=canvas.height,pose=keyframeAt(scene),scale=pose.scale||1;
    return inverse?{x:(point.x-w/2-pose.x*w)/scale+w/2,y:(point.y-h/2-pose.y*h)/scale+h/2}:{x:w/2+pose.x*w+(point.x-w/2)*scale,y:h/2+pose.y*h+(point.y-h/2)*scale};
  }
  function motionBox(scene,el){const {width:w,height:h}=motionDimensions(scene),pose=motionPose(el,state.time-scene.start,scene),bw=el.width*w,bh=el.height*h,angle=pose.rotation*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);return {pose,bw,bh,center:{x:pose.x*w+bw/2,y:pose.y*h+bh/2},corners:[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]].map(([x,y])=>motionScenePoint({x:pose.x*w+bw/2+(x*bw*c-y*bh*s)*pose.scale,y:pose.y*h+bh/2+(x*bw*s+y*bh*c)*pose.scale},scene))};}
  function drawMotionSelection(scene){
    const free=isFreeMotion(scene);$('canvas-edit-help').hidden=!free||state.mode!=='timeline';canvas.classList.toggle('editable-motion',Boolean(free));
    delete canvas.dataset.motionElement;delete canvas.dataset.motionPose;
    if(!free||scene.id!==state.selectedScene)return;const el=motionElement();if(!el)return;
    const t=motionLocal(scene),box=motionBox(scene,el);if(t<num(el.start)||t>=num(el.end,scene.end-scene.start))return;
    viewCtx.save();viewCtx.lineWidth=1.7;viewCtx.strokeStyle='#a9c9ff';viewCtx.fillStyle='#a9c9ff';
    if(el.path){viewCtx.strokeStyle='#91afdc';viewCtx.setLineDash([5,5]);viewCtx.beginPath();el.path.points.forEach((p,i)=>{const point=motionScenePoint({x:p.x*canvas.width,y:p.y*motionDimensions(scene).height},scene);i?viewCtx.lineTo(point.x,point.y):viewCtx.moveTo(point.x,point.y);});viewCtx.stroke();viewCtx.setLineDash([]);el.path.points.forEach((p,i)=>{const point=motionScenePoint({x:p.x*canvas.width,y:p.y*motionDimensions(scene).height},scene);viewCtx.beginPath();viewCtx.arc(point.x,point.y,state.selectedPathPoint===i?8:5,0,Math.PI*2);viewCtx.fill();});}
    viewCtx.strokeStyle='#a9c9ff';viewCtx.beginPath();box.corners.forEach((p,i)=>i?viewCtx.lineTo(p.x,p.y):viewCtx.moveTo(p.x,p.y));viewCtx.closePath();viewCtx.stroke();for(const p of box.corners){viewCtx.fillStyle='#14212f';viewCtx.fillRect(p.x-5,p.y-5,10,10);viewCtx.strokeRect(p.x-5,p.y-5,10,10);}viewCtx.restore();
    if($('motion-local-time')){$('motion-local-time').textContent=`${t.toFixed(2)} s`;$('motion-current-x').textContent=box.pose.x.toFixed(3);$('motion-current-y').textContent=box.pose.y.toFixed(3);}
    canvas.dataset.motionElement=el.id;canvas.dataset.motionPose=JSON.stringify(box.pose);
  }
  function canvasPoint(event){const rect=canvas.getBoundingClientRect();return {x:(event.clientX-rect.left)*canvas.width/rect.width,y:(event.clientY-rect.top)*canvas.height/rect.height};}
  function hitMotionElement(point,scene){
    point=motionScenePoint(point,scene,true);const t=state.time-scene.start;if(point.y<0||point.y>motionDimensions(scene).height)return null;
    return [...scene.motion_design.elements].sort((a,b)=>num(b.z)-num(a.z)).find(el=>{if(t<num(el.start)||t>=num(el.end,scene.end-scene.start))return false;const box=motionBox(scene,el),a=-box.pose.rotation*Math.PI/180,dx=point.x-box.center.x,dy=point.y-box.center.y,x=(dx*Math.cos(a)-dy*Math.sin(a))/box.pose.scale+box.bw/2,y=(dx*Math.sin(a)+dy*Math.cos(a))/box.pose.scale+box.bh/2;return x>=0&&y>=0&&x<=box.bw&&y<=box.bh;});
  }
  function translateMotionElement(el,scene,dx,dy,snapshot=clone(el)){
    if(snapshot.path){const shiftX=clamp(dx,-snapshot.x,1-snapshot.width-snapshot.x),shiftY=clamp(dy,-snapshot.y,1-snapshot.height-snapshot.y);el.x=snapshot.x+shiftX;el.y=snapshot.y+shiftY;el.path.points=snapshot.path.points.map(p=>({x:clamp(p.x+shiftX,-2,2),y:clamp(p.y+shiftY,-2,2)}));el.keyframes=(snapshot.keyframes||[]).map(k=>({...k,...(k.x!==undefined?{x:clamp(k.x+shiftX,-2,2)}:{}),...(k.y!==undefined?{y:clamp(k.y+shiftY,-2,2)}:{})}));return;}
    const pose=motionPose(snapshot,motionLocal(scene),scene);
    if(state.motionAutokey&&snapshot.keyframes?.length)upsertMotionKey(el,motionLocal(scene),{...pose,x:clamp(pose.x+dx,-2,2),y:clamp(pose.y+dy,-2,2)},scene.end-scene.start);
    else{dx=clamp(dx,-snapshot.x,1-snapshot.width-snapshot.x);dy=clamp(dy,-snapshot.y,1-snapshot.height-snapshot.y);el.x=snapshot.x+dx;el.y=snapshot.y+dy;el.keyframes=(snapshot.keyframes||[]).map(k=>({...k,...(k.x!==undefined?{x:clamp(k.x+dx,-2,2)}:{}),...(k.y!==undefined?{y:clamp(k.y+dy,-2,2)}:{})}));}
  }
  function canvasMotionDrag(event){
    if(event.button!==0||state.mode!=='timeline')return;const scene=currentScene();if(!isFreeMotion(scene))return;
    pause();event.preventDefault();const start=canvasPoint(event),designSize=motionDimensions(scene);if(motionScenePoint(start,scene,true).y>designSize.height)return;let el=motionElement(),handle=-1,pathPoint=-1;
    if(scene.id===state.selectedScene&&el&&motionLocal(scene)>=num(el.start)&&motionLocal(scene)<num(el.end,scene.end-scene.start)){handle=motionBox(scene,el).corners.findIndex(p=>Math.hypot(p.x-start.x,p.y-start.y)<13);pathPoint=(el.path?.points||[]).findIndex(p=>{const point=motionScenePoint({x:p.x*canvas.width,y:p.y*motionDimensions(scene).height},scene);return Math.hypot(point.x-start.x,point.y-start.y)<13;});}
    if(handle<0&&pathPoint<0)el=hitMotionElement(start,scene);
    if(scene.id!==state.selectedScene){state.selectedScene=scene.id;renderTimeline();renderInspector();}
    if(!el){selectMotionElement(null);canvas.focus();return;}selectMotionElement(el.id);state.selectedPathPoint=pathPoint<0?null:pathPoint;canvas.focus();if(!canEdit())return;
    const snapshot=clone(el),first=motionScenePoint(start,scene,true),pose=motionPose(el,motionLocal(scene),scene);let changed=false;
    if(state.motionAutokey&&el.keyframes?.length>=128&&!el.keyframes.some(k=>Math.abs(k.time-motionLocal(scene))<.0005)&&handle<0&&!el.path){toast('El máximo es de 128 claves; edita una existente.',true);return;}
    canvas.setPointerCapture(event.pointerId);
    const move=e=>{const current=motionScenePoint(canvasPoint(e),scene,true),dx=current.x-first.x,dy=current.y-first.y;if(!changed&&Math.hypot(dx,dy)<1)return;if(!changed){pushHistory();changed=true;}
      if(pathPoint>=0){el.path.points[pathPoint]={x:clamp(snapshot.path.points[pathPoint].x+dx/canvas.width,-2,2),y:clamp(snapshot.path.points[pathPoint].y+dy/designSize.height,-2,2)};}
      else if(handle>=0){const a=-pose.rotation*Math.PI/180,localX=(dx*Math.cos(a)-dy*Math.sin(a))/pose.scale,localY=(dx*Math.sin(a)+dy*Math.cos(a))/pose.scale,signX=[-1,1,1,-1][handle],signY=[-1,-1,1,1][handle];el.width=clamp(snapshot.width+signX*2*localX/canvas.width,.005,Math.min(snapshot.width+2*snapshot.x,2-2*snapshot.x-snapshot.width));el.height=clamp(snapshot.height+signY*2*localY/designSize.height,.005,Math.min(snapshot.height+2*snapshot.y,2-2*snapshot.y-snapshot.height));const sx=(snapshot.width-el.width)/2,sy=(snapshot.height-el.height)/2;el.x=snapshot.x+sx;el.y=snapshot.y+sy;el.keyframes=(snapshot.keyframes||[]).map(k=>({...k,...(k.x!==undefined?{x:clamp(k.x+sx,-2,2)}:{}),...(k.y!==undefined?{y:clamp(k.y+sy,-2,2)}:{})}));if(snapshot.path)el.path.points=snapshot.path.points.map(p=>({x:clamp(p.x+sx,-2,2),y:clamp(p.y+sy,-2,2)}));}
      else translateMotionElement(el,scene,dx/canvas.width,dy/designSize.height,snapshot);dirty();drawPreview();};
    const finish=()=>{canvas.removeEventListener('pointermove',move);canvas.removeEventListener('pointerup',finish);canvas.removeEventListener('pointercancel',finish);if(changed){renderTimeline();renderFreeMotion();$('canvas-edit-status').textContent=pathPoint>=0?`Punto ${pathPoint+1} ajustado.`:`${handle>=0?'Tamaño':'Posición'} ajustado. ${el.width.toFixed(3)} por ${el.height.toFixed(3)}.`;}};
    canvas.addEventListener('pointermove',move);canvas.addEventListener('pointerup',finish);canvas.addEventListener('pointercancel',finish);
  }
  function cleanMotionPlayers(){
    const valid=new Set((state.project?.timeline||[]).flatMap(scene=>(scene.motion_design?.elements||[]).filter(e=>e.type==='media').map(e=>`${scene.id}:${e.id}`)));
    state.motionPlayers.forEach((video,key)=>{if(!valid.has(key)){video.pause();video.removeAttribute('src');video.load();video.remove();state.motionPlayers.delete(key);}});
  }

  async function attachForOverlay(id){
    const projectId=state.project?.id,load=state.loadEpoch;if(!projectId)throw new Error('Selecciona un proyecto para adjuntar el recurso.');
    if(state.project.assets.some(a=>a.id===id))return;
    await saveProject();if(state.project?.id!==projectId||state.loadEpoch!==load)throw new Error('Cambiaste de proyecto antes de adjuntar el recurso.');
    if(state.dirty)throw new Error('Hay nuevos cambios sin guardar. Guárdalos antes de añadir el medio.');
    const epoch=state.editEpoch,response=normalizeProject(projectData(await api(`/api/projects/${projectId}/assets`,{method:'POST',body:{asset_id:id}})));
    if(state.project?.id!==projectId||state.loadEpoch!==load)throw new Error('El recurso se adjuntó al proyecto de origen. La selección actual se conserva.');
    if(state.editEpoch===epoch){state.project=response;return;}
    for(const asset of response.assets)if(!state.project.assets.some(a=>a.id===asset.id))state.project.assets.push(asset);
    if(num(response.revision)>=num(state.project.revision)){state.project.revision=response.revision;state.project.updated_at=response.updated_at;state.project.history=response.history;state.project.review={};state.project.approval_current=false;}
    $('save-state').textContent='Recurso adjuntado · conservas nuevos cambios sin guardar';
    throw new Error('El recurso se adjuntó, y tus nuevos cambios se conservaron. Guarda y vuelve a añadir la capa.');
  }

  async function addOverlay(){
    let scene=selectedScene();if(!scene)return;
    const candidates=visualCandidates();if(!candidates.length)throw new Error('Importa una imagen o un clip distinto del crudo para añadir una capa.');
    if((scene.overlays||[]).length>=8)throw new Error('El máximo por escena es de 8 capas visuales.');
    const id=scene.id,asset=candidates[0];await attachForOverlay(asset.id);scene=state.project.timeline.find(s=>s.id===id);if(!scene||state.selectedScene!==id)throw new Error('La escena cambió mientras se adjuntaba el recurso. Selecciona la escena deseada.');
    mutate(()=>{scene.overlays||=[];scene.overlays.push({id:uid('overlay'),asset_id:asset.id,start:0,end:Math.min(scene.end-scene.start,assetKind(asset)==='image'?scene.end-scene.start:num(asset.duration,scene.end-scene.start)),source_in:0,x:.1,y:.25,width:.3,height:.3,opacity:1,blend:'normal',keyframes:[],decision:{search:'',reason:'',evidence:[]}});},false);renderOverlays();
  }

  function renderOverlays(){
    const scene=selectedScene();if(!scene)return;const candidates=visualCandidates(),span=scene.end-scene.start;
    const openState=new Map([...$('overlay-list').querySelectorAll('[data-overlay-id]')].map(card=>[card.dataset.overlayId,[...card.querySelectorAll(':scope > details')].map(detail=>detail.open)]));
    $('add-overlay').disabled=(scene.overlays||[]).length>=8||!candidates.length;
    $('overlay-list').innerHTML=(scene.overlays||[]).map((o,i)=>`<div class="overlay-card" data-overlay="${i}" data-overlay-id="${esc(o.id)}"><div class="overlay-heading"><strong>Capa ${i+1}</strong><div><button type="button" data-layer-order="${i}:up" title="Subir en el orden">↑</button><button type="button" data-layer-order="${i}:down" title="Bajar en el orden">↓</button><button type="button" data-layer-delete="${i}" title="Eliminar capa">×</button></div></div><label>Recurso auténtico<select data-layer-field="asset_id">${candidates.map(a=>`<option value="${esc(a.id)}" ${a.id===o.asset_id?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label><div class="field-pair"><label>Inicio local (s)<input data-layer-field="start" type="number" min="0" max="${o.end-.01}" step=".01" value="${num(o.start)}"></label><label>Fin local (s)<input data-layer-field="end" type="number" min="${o.start+.01}" max="${span}" step=".01" value="${num(o.end,span)}"></label></div><label>Entrada del medio (s)<input data-layer-field="source_in" type="number" min="0" step=".01" value="${num(o.source_in)}" ${assetKind(assetById(o.asset_id))==='image'?'disabled':''}></label><div class="field-pair">${[['x','X (0–1)',0,1-num(o.width,.3)],['y','Y (0–1)',0,1-num(o.height,.3)],['width','Ancho',.01,1-num(o.x)],['height','Alto',.01,1-num(o.y)]].map(([key,label,min,max])=>`<label>${label}<input data-layer-field="${key}" type="number" min="${min}" max="${max}" step=".01" value="${num(o[key],['width','height'].includes(key)?.3:0)}"></label>`).join('')}</div><div class="field-pair"><label>Opacidad<input data-layer-field="opacity" type="number" min="0" max="1" step=".01" value="${num(o.opacity,1)}"></label><label>Mezcla<select data-layer-field="blend"><option value="normal" ${o.blend==='normal'?'selected':''}>Normal · alfa</option><option value="screen" ${o.blend==='screen'?'selected':''}>Screen</option></select></label></div><details><summary>Movimiento de la capa</summary><div class="overlay-keyframes">${(o.keyframes||[]).map((k,j)=>`<div class="keyframe-row" data-layer-key="${j}"><div>${[['time','Tiempo',0,o.end-o.start],['x','X offset',-1,1],['y','Y offset',-1,1],['scale','Escala',.25,3],['opacity','Opacidad',0,1]].map(([key,label,min,max])=>`<label>${label}<input data-layer-key-field="${key}" type="number" min="${min}" max="${max}" step=".01" value="${num(k[key],['scale','opacity'].includes(key)?1:0)}"></label>`).join('')}</div><button type="button" data-layer-remove-key="${j}">Eliminar keyframe</button></div>`).join('')}</div><button data-layer-add-key="${i}" type="button" class="button ghost full">Keyframe en el cursor</button></details><details><summary>Selección y evidencia</summary><label>Búsqueda<textarea data-layer-field="search" rows="2">${esc(o.decision?.search||'')}</textarea></label><label>Relación con la frase<textarea data-layer-field="reason" rows="2">${esc(o.decision?.reason||'')}</textarea></label><label>Evidencia real<textarea id="overlay-evidence-${i}" data-layer-field="evidence" rows="2">${esc((o.decision?.evidence||[]).join('\n'))}</textarea></label><button type="button" data-layer-evidence="${i}" class="button ghost full">Elegir captura real</button></details></div>`).join('');
    $('overlay-list').querySelectorAll('[data-overlay-id]').forEach(card=>{const saved=openState.get(card.dataset.overlayId);if(saved)[...card.querySelectorAll(':scope > details')].forEach((detail,i)=>detail.open=Boolean(saved[i]));});
    $('overlay-list').querySelectorAll('[data-layer-field]').forEach(input=>input.onchange=action(async()=>{
      const index=Number(input.closest('[data-overlay]').dataset.overlay),field=input.dataset.layerField,sceneId=scene.id;
      if(field==='asset_id')await attachForOverlay(input.value);
      const current=state.project.timeline.find(s=>s.id===sceneId),layer=current.overlays[index],value=input.value;
      mutate(()=>{
        if(['search','reason','evidence'].includes(field)){layer.decision||={};layer.decision[field]=field==='evidence'?lines(value):value;}
        else if(['asset_id','blend'].includes(field))layer[field]=value;
        else if(field==='start'||field==='end')trimScene(layer,field==='start'?clamp(Number(value),0,layer.end-.01):layer.start,field==='end'?clamp(Number(value),layer.start+.01,current.end-current.start):layer.end);
        else if(field==='x'||field==='y')layer[field]=clamp(Number(value),0,1-num(layer[field==='x'?'width':'height'],.3));
        else if(field==='width'||field==='height')layer[field]=clamp(Number(value),.01,1-num(layer[field==='width'?'x':'y']));
        else if(field==='opacity')layer.opacity=clamp(Number(value),0,1);
        else layer[field]=Math.max(0,Number(value));
      },false);if(['start','end','x','y','width','height','asset_id'].includes(field))renderOverlays();
    }));
    $('overlay-list').querySelectorAll('[data-layer-delete]').forEach(b=>b.onclick=()=>{mutate(()=>scene.overlays.splice(Number(b.dataset.layerDelete),1),false);renderOverlays();});
    $('overlay-list').querySelectorAll('[data-layer-order]').forEach(b=>b.onclick=()=>{const [index,dir]=b.dataset.layerOrder.split(':'),a=Number(index),target=a+(dir==='up'?1:-1);if(target<0||target>=scene.overlays.length)return;mutate(()=>{[scene.overlays[a],scene.overlays[target]]=[scene.overlays[target],scene.overlays[a]];},false);renderOverlays();});
    $('overlay-list').querySelectorAll('[data-layer-evidence]').forEach(b=>b.onclick=()=>evidenceDialog(`overlay-evidence-${b.dataset.layerEvidence}`));
    $('overlay-list').querySelectorAll('[data-layer-key-field]').forEach(input=>input.onchange=()=>{const index=Number(input.closest('[data-overlay]').dataset.overlay),key=Number(input.closest('[data-layer-key]').dataset.layerKey);mutate(()=>{scene.overlays[index].keyframes[key][input.dataset.layerKeyField]=Number(input.value);scene.overlays[index].keyframes.sort((a,b)=>a.time-b.time);},false);renderOverlays();});
    $('overlay-list').querySelectorAll('[data-layer-remove-key]').forEach(b=>b.onclick=()=>{const index=Number(b.closest('[data-overlay]').dataset.overlay);mutate(()=>scene.overlays[index].keyframes.splice(Number(b.dataset.layerRemoveKey),1),false);renderOverlays();});
    $('overlay-list').querySelectorAll('[data-layer-add-key]').forEach(b=>b.onclick=()=>{const layer=scene.overlays[Number(b.dataset.layerAddKey)],time=clamp(state.time-scene.start-layer.start,0,layer.end-layer.start),values=keyframeAt(layer,time);mutate(()=>{layer.keyframes||=[];const existing=layer.keyframes.find(k=>Math.abs(k.time-time)<.005);if(existing)Object.assign(existing,{time,...values});else layer.keyframes.push({time,...values});layer.keyframes.sort((a,b)=>a.time-b.time);},false);renderOverlays();});
  }

  function renderKeyframes() {
    const s = selectedScene();
    $('keyframes-list').innerHTML = (s?.keyframes || []).map((k,index) => `<div class="keyframe-row" data-keyframe="${index}"><div>${[['time','Tiempo',0,s.end-s.start],['x','X',-1,1],['y','Y',-1,1],['scale','Escala',.25,3],['opacity','Opacidad',0,1]].map(([field,label,min,max]) => `<label>${label}<input data-key="${field}" type="number" min="${min}" max="${max}" step="0.01" value="${num(k[field],field==='scale'||field==='opacity'?1:0)}"></label>`).join('')}</div><button type="button" data-remove-key="${index}">Eliminar keyframe</button></div>`).join('');
    $('keyframes-list').querySelectorAll('[data-key]').forEach(input => input.onchange = () => {
      const index = Number(input.closest('[data-keyframe]').dataset.keyframe);
      mutate(() => {s.keyframes[index][input.dataset.key] = Number(input.value); s.keyframes.sort((a,b) => a.time-b.time);}, false);
      renderKeyframes();
    });
    $('keyframes-list').querySelectorAll('[data-remove-key]').forEach(button => button.onclick = () => {mutate(() => s.keyframes.splice(Number(button.dataset.removeKey),1),false); renderKeyframes();});
  }

  function renderSceneWarnings() {
    const s = selectedScene(); if (!s) return;
    const warnings = [];
    if (['presenter','split'].includes(s.type) && s.end-s.start>3) warnings.push('Esta escena supera 3 s de rostro. Las escenas contiguas con presentador también cuentan.');
    if (s.type==='split' && !s.asset_id && !s.title) warnings.push('Selecciona un b-roll real o diseña el motion superior.');
    if (s.type==='broll' && !s.asset_id) warnings.push('Falta el recurso visual.');
    if (s.start<6 && s.subtitle) warnings.push('En el hook usa texto editorial integrado; evita la transcripción automática.');
    if (!s.decision?.search || !s.decision?.reason) warnings.push('Documenta búsqueda y motivo de selección antes de renderizar.');
    if (s.type==='motion') warnings.push('Plantilla conceptual. Verifica acción, reacción y transformación en el render.');
    if(s.template==='counter'&&s.motion?.value===undefined)warnings.push('El contador requiere un valor real del guion en Datos de la animación.');
    $('scene-warnings').innerHTML = warnings.map(w => `<p>${esc(w)}</p>`).join('');
  }

  function bindSceneField(id, setter, eventName='change') {
    $(id).addEventListener(eventName, action(() => {
      const s=selectedScene(); if(!s)return;
      const value=$(id).type==='checkbox'?$(id).checked:$(id).value;
      mutate(() => setter(s,value), false);
      if (eventName === 'change') renderInspector(); else renderSceneWarnings();
    }));
  }

  function renderTranscript() {
    const segments = state.project?.transcript?.segments || [];
    $('edit-words').disabled = !state.project;
    $('add-transcript').disabled = !state.project;
    $('transcript-list').innerHTML = segments.length ? segments.map((s,index) => `<div class="transcript-block" data-segment="${index}"><div class="transcript-times"><button data-seek="${num(s.start)}">${fmt(s.start,false)}</button><span>→</span><input data-time="start" aria-label="Inicio del bloque" type="number" min="0" step="0.01" value="${num(s.start)}"><input data-time="end" aria-label="Fin del bloque" type="number" min="0" step="0.01" value="${num(s.end)}"><button data-remove="${index}" title="Eliminar bloque" aria-label="Eliminar bloque">×</button></div><textarea data-text rows="2" aria-label="Texto del bloque ${index+1}">${esc(s.text)}</textarea></div>`).join('') : '<p class="muted empty-copy">Analiza la voz del crudo o importa la narración manualmente. El storyboard se construye desde este texto.</p>';
    $('transcript-list').querySelectorAll('[data-seek]').forEach(b=>b.onclick=()=>seekTime(Number(b.dataset.seek)));
    $('transcript-list').querySelectorAll('[data-text],[data-time]').forEach(input=>input.onchange=()=>{
      const index=Number(input.closest('[data-segment]').dataset.segment);
      mutate(p=>{if(input.hasAttribute('data-text'))p.transcript.segments[index].text=input.value;else p.transcript.segments[index][input.dataset.time]=Number(input.value);},false);
    });
    $('transcript-list').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{mutate(p=>p.transcript.segments.splice(Number(b.dataset.remove),1),false);renderTranscript();});
  }

  function wordsDialog() {
    if (!state.project) return;
    const words=clone(state.project.transcript.words || []);
    const rows = () => words.map((w,i)=>`<div class="word-row" data-word="${i}"><input data-field="word" aria-label="Palabra" value="${esc(w.word)}"><input data-field="start" aria-label="Inicio de palabra" type="number" step="0.01" min="0" value="${num(w.start)}"><input data-field="end" aria-label="Fin de palabra" type="number" step="0.01" min="0" value="${num(w.end)}"><button data-remove-word="${i}" class="icon-button" aria-label="Eliminar palabra">×</button></div>`).join('');
    modal('Alineación de palabras', '<p class="modal-copy">Ajusta la transcripción escuchando la voz. Los tiempos son segundos del crudo original.</p><div class="word-head"><span>Palabra</span><span>Inicio</span><span>Fin</span></div><div id="word-editor"></div><button id="add-word" class="button ghost compact">Añadir palabra</button><div class="modal-actions"><button id="save-words" class="button primary">Guardar alineación</button></div>',()=>{
      function paint(){
        $('word-editor').innerHTML=rows();
        $('word-editor').querySelectorAll('[data-field]').forEach(input=>input.onchange=()=>{const i=Number(input.closest('[data-word]').dataset.word);words[i][input.dataset.field]=input.dataset.field==='word'?input.value:Number(input.value);});
        $('word-editor').querySelectorAll('[data-remove-word]').forEach(b=>b.onclick=()=>{words.splice(Number(b.dataset.removeWord),1);paint();});
      }
      paint(); $('add-word').onclick=()=>{words.push({word:'',start:state.time,end:state.time+.25});paint();};
      $('save-words').onclick=()=>{if(words.some(w=>!w.word.trim()||w.end<=w.start)){toast('Cada palabra necesita texto y un final posterior al inicio.',true);return;}mutate(p=>{p.transcript.words=words.sort((a,b)=>a.start-b.start);});$('modal').close();renderTranscript();};
    });
  }

  function renderTemplates() {
    const adapter=capabilityAvailability(state.status?.capabilities?.hyperframes_adapter);
    $('motion-engine-status').textContent=(adapter===true?'El servidor informa disponible el adaptador HyperFrames/GSAP. Su aplicación y la calidad de cada escena requieren evidencia.':adapter===false?'Adaptador HyperFrames/GSAP pendiente de integración en este editor. La arquitectura comprobada en IVAN no acredita por sí sola esta integración.':'Estado del adaptador HyperFrames/GSAP sin verificar. La instalación por sí sola no acredita su uso.')+' '+productionPhaseNote();
    $('templates-list').innerHTML=state.templates.map(t=>`<button class="template-card" data-template="${esc(t.id)}"><div class="template-art">${t.id==='workflow'?'<span>Entrada</span>'+icon('chevron')+'<span>Acción</span>':t.id==='compare'?'<span>Antes</span>'+icon('chevron')+'<span>Después</span>':t.id==='counter'?icon('nodes'):icon('text')}</div><strong>${esc(t.name)}</strong><p>${esc(t.description)}</p><span class="template-phases">${esc((t.phases||[]).join(' → '))}</span></button>`).join('');
    $('templates-list').querySelectorAll('[data-template]').forEach(b=>b.onclick=()=>{
      if(!state.project){toast('Crea o importa un proyecto para añadir motion.');return;}
      const s=selectedScene();if(s)mutate(()=>{s.type='motion';if(b.dataset.template==='custom')enableFreeMotion(s);else{s.template=b.dataset.template;delete s.motion_design;state.selectedElement=null;}});else if(b.dataset.template==='custom')createFreeMotion();else addScene({type:'motion',template:b.dataset.template});
    });
  }

  function addAudio(id) {
    const asset=assetById(id);if(!asset||assetKind(asset)!=='audio'||!state.project)return;
    const start=clamp(state.time,0,Math.max(0,(duration()||10)-.1)),end=Math.max(start+.1,Math.min(duration()||10,start+num(asset.duration,3)));
    mutate(p=>p.audio.push({id:uid('audio'),asset_id:id,start,end,source_in:0,gain_db:-18,role:'music',is_riser:false}),false);
    renderAudio();
  }

  function renderAudio() {
    $('audio-assets').innerHTML=state.assets.filter(a=>assetKind(a)==='audio').map(a=>`<div class="audio-asset">${icon('audio')}<span title="${esc(a.name)}">${esc(a.name)}</span><button class="icon-button" data-audio-add="${esc(a.id)}" title="Añadir a la pista" aria-label="Añadir ${esc(a.name)} a la pista">+</button></div>`).join('') || '<p class="muted empty-copy">Importa música y efectos para diseñar tu mezcla.</p>';
    $('audio-assets').querySelectorAll('[data-audio-add]').forEach(b=>b.onclick=action(()=>useAsset(b.dataset.audioAdd)));
    $('audio-tracks').innerHTML=(state.project?.audio||[]).map((a,i)=>`<div class="audio-track-card" data-audio-index="${i}"><strong>${esc(assetById(a.asset_id)?.name || a.asset_id)}</strong><div class="field-pair"><label>Entrada (s)<input data-audio-field="start" type="number" min="0" step="0.01" value="${num(a.start)}"></label><label>Salida (s)<input data-audio-field="end" type="number" min="0.1" step="0.01" value="${num(a.end)}"></label></div><div class="field-pair"><label>Desde archivo<input data-audio-field="source_in" type="number" min="0" step="0.01" value="${num(a.source_in)}"></label><label>Ganancia (dB)<input data-audio-field="gain_db" type="number" min="-60" max="6" step="1" value="${num(a.gain_db,-18)}"></label></div><label>Función<select data-audio-field="role"><option value="music" ${a.role==='music'?'selected':''}>Música</option><option value="sfx" ${a.role==='sfx'?'selected':''}>Efecto sonoro</option></select></label><label class="review-check"><input data-audio-field="is_riser" type="checkbox" ${a.is_riser?'checked':''}><span>Es el riser del hook</span></label>${a.is_riser?`<label>Pico de impacto (s del reel)<input data-audio-field="impact_at" type="number" min="2" max="6" step="0.01" value="${num(a.impact_at,3)}"></label><label>Transformación que acompaña<input data-audio-field="visual_event" value="${esc(a.visual_event || '')}" placeholder="Acción visual comprobable"></label>`:''}<button data-audio-delete="${i}" class="button danger full" style="margin:10px 0 0;min-height:25px;padding:4px;font-size:9px">Eliminar pista</button></div>`).join('') || '<p class="muted empty-copy">Aún no hay música ni efectos en la cronología.</p>';
    $('audio-tracks').querySelectorAll('[data-audio-field]').forEach(input=>input.onchange=()=>{
      const index=Number(input.closest('[data-audio-index]').dataset.audioIndex),field=input.dataset.audioField;
      mutate(p=>{p.audio[index][field]=input.type==='checkbox'?input.checked:['role','visual_event'].includes(field)?input.value:Number(input.value);if(field==='is_riser'&&input.checked)p.audio[index].role='sfx';},false);
      if(field==='is_riser')renderAudio();syncAudio();
    });
    $('audio-tracks').querySelectorAll('[data-audio-delete]').forEach(b=>b.onclick=()=>{mutate(p=>p.audio.splice(Number(b.dataset.audioDelete),1),false);renderAudio();syncAudio();});
  }

  function renderWorkflow() {
    const p=state.project;
    const technical=isTechnicalRender(p?.renders?.at(-1));
    const steps=p?.mode==='scene_ir_component'?[['Fuente canónica','Narración original conservada como fuente del componente.',Boolean(p.source)],['SceneIR declarado','Contenido, objetivo, parámetros y acciones explícitos; no generación semántica automática.',Boolean(p.scene_ir)],['Composición editable','Primitivas, curvas y máscaras en una escena libre.',Boolean(p.timeline[0]?.motion_design?.elements?.length)],['Renders registrados','Exporta la cronología vigente antes de revisarla; una prueba previa puede corresponder a otra edición.',Boolean(p.renders?.length)],['Control de calidad pendiente','Revisa fidelidad, movimiento, variantes y sonido; un control técnico no los certifica.',false]]:[['Material original','Importa el crudo y tus recursos.',Boolean(p?.source)],['Narración alineada','Voz, palabras y estructura verificables.',Boolean(p?.transcript?.segments?.length)],['Storyboard contextual','Cada escena responde a una frase.',Boolean(p?.timeline?.length)],['Recursos y estilo','Búsqueda y evidencias de YO; motion según CLONE.',Boolean(p?.reference_review?.identity_observations&&p?.timeline?.every(s=>s.decision?.reason&&s.decision?.search))],['Prueba de 10 segundos',technical?'Exportado técnico del editor; sin aprobación narrativa.':'Prueba narrativa con revisión visual y sonora.',Boolean(p?.renders?.length)],['Aprobación explícita','YO: cámara, subtítulos y split. CLONE: motion.',hasCurrentApproval(p)]];
    $('workflow-steps').innerHTML=steps.map(([title,desc,done])=>`<li class="${done?'done':''}"><div><strong>${esc(title)}</strong><small>${esc(desc)}</small></div></li>`).join('');
  }

  function loadSource() {
    sourceReady=false;const asset=assetById(state.project?.source);state.sourceId=asset?.id||null;
    source.pause();presenter.pause();
    if(asset){source.src=assetUrl(asset);source.load();presenter.src=assetUrl(asset);presenter.load();}
    else {source.removeAttribute('src');source.load();presenter.removeAttribute('src');presenter.load();}
    state.brollId=null;broll.pause();broll.removeAttribute('src');
  }

  function updateTimecode() {
    $('timecode').innerHTML=`${fmt(state.time)} <span>/ ${fmt(duration())}</span>`;
    const s=currentScene(),proxy=assetById(state.project?.source)?.preview_is_derivative;$('scene-indicator').textContent=state.mode==='source'?proxy?'CRUDO · PROXY DE PREVISUALIZACIÓN':'ORIGINAL · AUDIO ORIGINAL':state.mode==='render'?isTechnicalRender(state.project?.renders?.at(-1))?'RENDER TÉCNICO · SIN APROBACIÓN ASCENDIA':'PRUEBA NARRATIVA · REVISIÓN EXPLÍCITA':s?`${s.type.toUpperCase()} · ESCENA ${String(state.project.timeline.indexOf(s)+1).padStart(2,'0')}`:state.project?.mode==='scene_ir_component'?'FIN DEL COMPONENTE':state.project?.source?'ORIGINAL · SIN ESCENA':'SIN MATERIAL';
  }
  function updatePlayhead() {$('playhead').style.left=`${state.time*state.zoom}px`;}
  function seekTime(time) {
    state.time=clamp(num(time),0,duration());
    if(state.mode==='render')$('render-video').currentTime=clamp(state.time,0,$('render-video').duration||10);
    if(sourceReady&&Math.abs(source.currentTime-state.time)>.025)source.currentTime=clamp(state.time,0,source.duration||duration());
    prepareBroll(currentScene(),true);preparePresenter(currentScene(),true);syncAudio(true);updateTimecode();updatePlayhead();drawPreview();
  }
  async function play() {
    if(!state.project?.source && !state.project?.timeline?.length)return;
    if(state.mode==='render'){await $('render-video').play();return;}
    if(state.time>=duration()-.02)seekTime(0);
    if(state.project.source&&sourceReady){source.currentTime=state.time;source.playbackRate=Number($('playback-speed').value);await source.play();}
    state.playing=true;lastTick=performance.now();syncAudio(true);updatePlayButton();
  }
  function pause(){source.pause();broll.pause();presenter.pause();transition.pause();$('render-video').pause();state.playing=false;state.audioPlayers.forEach(a=>a.pause());state.overlayPlayers.forEach(a=>a.pause());state.motionPlayers.forEach(a=>a.pause());updatePlayButton();}
  function updatePlayButton(){$('play-button').innerHTML=icon(state.playing?'pause':'play');$('play-button').setAttribute('aria-label',state.playing?'Pausar':'Reproducir');}
  function previewMode(mode){
    pause();state.mode=mode;['timeline','source','render'].forEach(m=>$(`preview-${m}`).classList.toggle('active',m===mode));
    if(state.project?.mode==='scene_ir_component'&&mode!=='source')state.time=Math.min(state.time,duration());
    $('render-video').hidden=mode!=='render';canvas.hidden=mode==='render';$('safe-overlay').hidden=mode==='render';
    $('canvas-edit-help').hidden=mode!=='timeline'||!isFreeMotion(currentScene());
    if(mode!=='timeline'){canvas.classList.remove('editable-motion');delete canvas.dataset.motionElement;delete canvas.dataset.motionPose;}
    if(mode==='render'){
      const render=state.project.renders.at(-1);$('render-video').src=render.url?namespaceURL(render.url):fileUrl(render.path);$('render-video').currentTime=0;
    }
    updateTimecode();drawPreview();
  }

  function prepareBroll(scene, force=false) {
    const id=scene && ['broll','split'].includes(scene.type)?scene.asset_id:null,asset=assetById(id);
    if(!asset || assetKind(asset)!=='video'){if(state.brollId){broll.pause();state.brollId=null;}return;}
    const time=num(scene.type==='split'?scene.broll_in:scene.source_in)+state.time-scene.start;
    if(state.brollId!==id){state.brollId=id;broll.src=assetUrl(asset);broll.load();broll.onloadedmetadata=()=>{broll.currentTime=clamp(time,0,Math.max(0,broll.duration-.05));if(state.playing)broll.play().catch(()=>{});};}
    else if(broll.readyState>=2&&(force||Math.abs(broll.currentTime-time)>.2))broll.currentTime=clamp(time,0,Math.max(0,broll.duration-.05));
    if(state.playing && broll.paused && broll.readyState>=2){broll.playbackRate=Number($('playback-speed').value);broll.play().catch(()=>{});}else if(!state.playing&&!broll.paused)broll.pause();
  }

  function preparePresenter(scene,force=false){
    if(!scene||!['presenter','split'].includes(scene.type)||state.mode!=='timeline'){presenter.pause();return;}
    const time=num(scene.source_in,scene.start)+state.time-scene.start;
    if(presenter.readyState>=2&&(force||Math.abs(presenter.currentTime-time)>.2))presenter.currentTime=clamp(time,0,Math.max(0,presenter.duration-.05));
    if(state.playing&&presenter.paused&&presenter.readyState>=2){presenter.playbackRate=Number($('playback-speed').value);presenter.play().catch(()=>{});}else if(!state.playing&&!presenter.paused)presenter.pause();
  }

  function drawTransition(scene){
    const asset=assetById(scene.transition_asset_id),span=num(scene.transition_duration,.5),start=scene.end-span;
    if(!asset||state.time<start){transition.pause();return;}
    const time=num(scene.transition_source_in)+state.time-start;
    if(state.transitionId!==asset.id){state.transitionId=asset.id;transition.src=assetUrl(asset);transition.load();transition.onloadedmetadata=()=>{transition.currentTime=clamp(time,0,Math.max(0,transition.duration-.05));};}
    if(transition.readyState<2)return;
    if(Math.abs(transition.currentTime-time)>.15)transition.currentTime=clamp(time,0,Math.max(0,transition.duration-.05));
    if(state.playing&&transition.paused){transition.playbackRate=Number($('playback-speed').value);transition.play().catch(()=>{});}else if(!state.playing)transition.pause();
    ctx.save();ctx.globalCompositeOperation='screen';drawCover(transition,0,0,canvas.width,canvas.height);ctx.restore();
  }

  function drawOverlays(scene){
    const local=state.time-scene.start,w=canvas.width,h=canvas.height,active=new Set();
    for(const layer of scene.overlays||[]){
      if(local<layer.start||local>=layer.end)continue;const asset=assetById(layer.asset_id);if(!asset||asset.id===state.project.source)continue;
      const key=layer.id,relative=local-layer.start,transform=keyframeAt(layer,relative);let media;
      if(assetKind(asset)==='image')media=imageFor(asset);
      else{
        active.add(key);media=state.overlayPlayers.get(key);
        if(!media){media=document.createElement('video');media.className='media-engine';media.muted=true;media.playsInline=true;media.preload='auto';document.body.append(media);state.overlayPlayers.set(key,media);media.onseeked=drawPreview;}
        const target=assetUrl(asset);if(media.dataset.asset!==asset.id){media.dataset.asset=asset.id;media.pause();media.src=target;media.load();media.onloadedmetadata=()=>{media.currentTime=clamp(num(layer.source_in)+relative,0,Math.max(0,media.duration-.03));};media.onerror=()=>toast('Este medio no puede previsualizarse en el navegador. Comprueba su proxy y el render.',true);}
        const time=num(layer.source_in)+relative;if(media.readyState>=2&&Math.abs(media.currentTime-time)>.16)media.currentTime=clamp(time,0,Math.max(0,media.duration-.03));
        if(state.playing&&media.paused&&media.readyState>=2){media.playbackRate=Number($('playback-speed').value);media.play().catch(()=>{});}else if(!state.playing&&!media.paused)media.pause();
      }
      if(assetKind(asset)!=='image'&&media.readyState<2)continue;
      const mw=media.videoWidth||media.naturalWidth,mh=media.videoHeight||media.naturalHeight;if(!mw||!mh)continue;
      const boxWidth=num(layer.width,.3)*w*transform.scale,boxHeight=num(layer.height,.3)*h*transform.scale,boxX=num(layer.x)*w+transform.x*w+(num(layer.width,.3)*w-boxWidth)/2,boxY=num(layer.y)*h+transform.y*h+(num(layer.height,.3)*h-boxHeight)/2,fit=Math.min(boxWidth/mw,boxHeight/mh),dw=mw*fit,dh=mh*fit;
      ctx.save();ctx.globalAlpha=clamp(num(layer.opacity,1)*transform.opacity,0,1);ctx.globalCompositeOperation=layer.blend==='screen'?'screen':'source-over';ctx.drawImage(media,boxX+(boxWidth-dw)/2,boxY+(boxHeight-dh)/2,dw,dh);ctx.restore();
    }
    state.overlayPlayers.forEach((video,key)=>{if(!active.has(key))video.pause();});
  }

  function syncAudio(force=false) {
    const tracks=state.project?.audio||[],valid=new Set();
    tracks.forEach((track,i)=>{
      const key=track.id||`${track.asset_id}_${i}`;valid.add(key);
      const asset=assetById(track.asset_id);if(!asset)return;
      let player=state.audioPlayers.get(key);
      if(!player){player=document.createElement('audio');player.src=assetUrl(asset);player.preload='metadata';$('audio-engine').append(player);state.audioPlayers.set(key,player);}
      player.volume=clamp(Math.pow(10,num(track.gain_db,-18)/20),0,1);player.muted=source.muted;player.playbackRate=Number($('playback-speed').value);
      const active=state.time>=track.start&&state.time<track.end&&state.mode==='timeline';
      if(active){const t=num(track.source_in)+state.time-track.start;if(player.readyState&& (force||Math.abs(player.currentTime-t)>.2))player.currentTime=t;if(state.playing&&player.paused)player.play().catch(()=>{});if(!state.playing)player.pause();}else player.pause();
    });
    state.audioPlayers.forEach((player,key)=>{if(!valid.has(key)){player.pause();player.remove();state.audioPlayers.delete(key);}});
  }

  function imageFor(asset) {
    if(!asset)return null;
    if(!state.imageCache.has(asset.id)){const image=new Image();image.onload=()=>drawPreview();image.src=assetUrl(asset);state.imageCache.set(asset.id,image);}
    return state.imageCache.get(asset.id);
  }
  function roundRect(x,y,w,h,r=10){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}
  const ease = value => {const p=clamp(value,0,1);return p*p*(3-2*p);};
  function keyframeAt(scene,localTime=state.time-scene.start) {
    const keys=[...(scene.keyframes||[])].sort((a,b)=>a.time-b.time),time=localTime;
    const base={x:0,y:0,scale:1,opacity:1};if(!keys.length)return base;
    const pick=frame=>Object.fromEntries(Object.keys(base).map(key=>[key,num(frame[key],base[key])]));
    const first=keys[0],last=keys.at(-1);if(time<=first.time)return pick(first);if(time>=last.time)return pick(last);
    const right=keys.findIndex(k=>k.time>time),a=keys[right-1],b=keys[right],p=ease((time-a.time)/(b.time-a.time));
    return Object.fromEntries(Object.keys(base).map(key=>[key,num(a[key],base[key])+(num(b[key],base[key])-num(a[key],base[key]))*p]));
  }
  function drawCover(media,x,y,w,h,focusY=.5,focusX=.5){
    const mw=media.videoWidth||media.naturalWidth,mh=media.videoHeight||media.naturalHeight;if(!mw||!mh)return false;
    const scale=Math.max(w/mw,h/mh),sw=w/scale,sh=h/scale,sx=clamp((mw-sw)*focusX,0,mw-sw),sy=clamp((mh-sh)*focusY,0,mh-sh);
    ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();ctx.drawImage(media,sx,sy,sw,sh,x,y,w,h);ctx.restore();return true;
  }
  function drawMedia(asset,x,y,w,h,focusY=.5,focusX=.5){
    if(!asset)return false;
    if(assetKind(asset)==='image')return drawCover(imageFor(asset),x,y,w,h,focusY,focusX);
    if(state.brollId===asset.id&&broll.readyState>=2)return drawCover(broll,x,y,w,h,focusY,focusX);
    return false;
  }
  function placeholder(text,x=0,y=0,w=540,h=960){ctx.fillStyle='#1e2025';ctx.fillRect(x,y,w,h);ctx.fillStyle='#6d737f';ctx.font='19px system-ui';ctx.textAlign='center';ctx.fillText(text,x+w/2,y+h/2);}
  function textLines(text,maxWidth){const words=String(text).split(/\s+/),linesOut=[];let line='';words.forEach(word=>{const trial=line?line+' '+word:word;if(ctx.measureText(trial).width>maxWidth&&line){linesOut.push(line);line=word;}else line=trial;});if(line)linesOut.push(line);return linesOut;}
  function paintText(text,x,y,size,color='#fff',font='primary',maxWidth=440){
    if(!text||SaaS&&!state.fontsLoaded)return;
    ctx.save();size=Math.max(8,Math.floor(size));const family=roleFamily(font);let linesOut;
    const setFace=()=>{ctx.font=roleCSS(font,size);linesOut=textLines(text,maxWidth);};setFace();
    while((linesOut.length>4||linesOut.some(line=>ctx.measureText(line).width>maxWidth))&&size>8){size--;setFace();}
    ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowBlur=0;const lh=size*1.1;
    linesOut.forEach((line,i)=>{const yy=y+(i-(linesOut.length-1)/2)*lh;ctx.strokeStyle='rgba(0,0,0,.88)';ctx.fillStyle='rgba(0,0,0,.88)';ctx.lineWidth=2;ctx.strokeText(line,x+1,yy+2);ctx.fillText(line,x+1,yy+2);ctx.fillStyle=color;ctx.fillText(line,x,yy);});ctx.restore();
  }

  function drawNode(box,label,w,activated=0,accent=false){
    const [x0,y0,x1,y1]=box.map(Math.round),shift=Math.max(1,Math.floor(w*.01));
    ctx.fillStyle='#04060c';roundRect(x0+shift,y0+shift,x1-x0,y1-y0,w*.028);ctx.fill();
    const initial=[32,37,48],target=accent?[90,32,40]:[57,67,83];ctx.fillStyle=`rgb(${initial.map((a,i)=>Math.round(a+(target[i]-a)*activated)).join(',')})`;
    roundRect(x0,y0,x1-x0,y1-y0,w*.028);ctx.fill();ctx.lineWidth=Math.max(1,Math.floor(w/320));ctx.strokeStyle='#646b77';ctx.stroke();
    paintText(label,(x0+x1)/2,(y0+y1)/2,w*.062,'#ffffff','primary',Math.max(10,x1-x0-w*.04));
  }

  function drawKinetic(scene,p,w,h){
    if(!scene.title)return;
    const entrance=ease(p/.14),exit=ease((p-.9)/.1);
    ctx.save();ctx.beginPath();ctx.rect(0,0,w*entrance,h);ctx.clip();
    paintText(scene.title,w*.5,h*(.42+(1-entrance)*.12-exit*.5),w*.105,scene.text_color||'#ffffff',scene.font,w*.85);ctx.restore();
    if(scene.emphasis)paintText(scene.emphasis,w*.5+w*.02*Math.sin(p*Math.PI),h*.63,w*.14,scene.red_reason?'#d81c2d':'#ffffff','accent',w*.85);
  }

  function drawMotion(scene,x=0,y=0,w=540,h=960){
    const local=state.time-scene.start,p=clamp(local/Math.max(scene.end-scene.start,.001),0,1),template=scene.template||'workflow';
    ctx.save();ctx.translate(x,y);ctx.beginPath();ctx.rect(0,0,w,h);ctx.clip();ctx.fillStyle='#101217';ctx.fillRect(0,0,w,h);
    const step=Math.max(16,Math.floor(w/9)),drift=Math.floor(local*w*.012)%step;ctx.strokeStyle='#16191f';ctx.lineWidth=1;
    for(let xx=-step;xx<w+step;xx+=step){ctx.beginPath();ctx.moveTo(xx+drift,0);ctx.lineTo(xx+drift,h);ctx.stroke();}
    for(let yy=-step;yy<h+step;yy+=step){ctx.beginPath();ctx.moveTo(0,yy+drift);ctx.lineTo(w,yy+drift);ctx.stroke();}
    if(template==='workflow'){
      const supplied=scene.nodes?.length?scene.nodes:scene.motion?.nodes?.length?scene.motion.nodes:['Entrada','Proceso','Resultado'],labels=supplied.slice(0,3).map(n=>typeof n==='object'?n.label:n);
      if(labels.length!==3){paintText('Define tres nodos del proceso',w*.5,h*.5,w*.052,'#ffffff');ctx.restore();return;}
      const centers=[[w*.5,h*.35],[w*.5,h*.53],[w*.5,h*.71]],entry=ease(p/.12),convergence=ease((p-.76)/.14),exit=ease((p-.92)/.08);
      centers.forEach(([cx,cy],i)=>{cy=cy+(1-entry)*h*.16+convergence*(h*.53-cy)-exit*h*.8;const activated=ease((p-(.15+i*.2))/.1),size=1+.04*Math.sin(activated*Math.PI),halfw=w*.32*size,halfh=h*.056*size;drawNode([cx-halfw,cy-halfh,cx+halfw,cy+halfh],labels[i],w,activated);});
      if(p>.16&&p<.78){const transfer=clamp((p-.16)/.52,0,1),yy=h*(.4+.28*transfer),radius=w*.024;ctx.strokeStyle='#5a6477';ctx.lineWidth=Math.max(2,Math.floor(w/180));ctx.beginPath();ctx.moveTo(w*.5,h*.406);ctx.lineTo(w*.5,h*.655);ctx.stroke();ctx.fillStyle='#f4f7fc';ctx.beginPath();ctx.arc(w*.5,yy,radius,0,Math.PI*2);ctx.fill();}
      if(convergence>.5)drawNode([w*.16,h*.465-exit*h*.8,w*.84,h*.6-exit*h*.8],labels.at(-1),w,1);
    }else if(template==='compare'){
      const labels=scene.motion?.labels||scene.labels||['Antes','Después'];
      if(labels.length<2){paintText('Define dos estados de comparación',w*.5,h*.5,w*.052,'#ffffff');ctx.restore();return;}
      const reveal=ease(p/.16),merge=ease((p-.55)/.25),exit=ease((p-.91)/.09),yy=h*.53-exit*h*.85;
      [w*(.25+.25*merge),w*(.75-.25*merge)].forEach((cx,i)=>{const halfw=w*(.2+.13*merge),halfh=h*(.15-.075*merge);drawNode([cx-halfw,yy-halfh+(1-reveal)*h*.3,cx+halfw,yy+halfh+(1-reveal)*h*.3],labels[i],w,merge,i===0&&Boolean(scene.red_reason));});
      if(merge>.85)drawNode([w*.17,yy-h*.075,w*.83,yy+h*.075],labels[1],w,1);
    }else if(template==='counter'){
      const data=scene.motion||{};
      if(data.value===undefined){paintText('Añade un valor real del guion',w*.5,h*.5,w*.052,'#ffffff');ctx.restore();return;}
      const completion=ease((p-.15)/.55),shown=num(data.from)+(num(data.value)-num(data.from))*completion,decimals=Math.floor(clamp(num(data.decimals),0,4)),label=shown.toFixed(decimals)+String(data.suffix||''),yy=h*.57-ease((p-.92)/.08)*h*.8;
      ctx.fillStyle='#303741';roundRect(w*.12,yy+h*.09,w*.76,h*.025,w*.014);ctx.fill();
      if(completion>0){ctx.fillStyle='#f2f2f7';roundRect(w*.12,yy+h*.09,w*.76*completion,h*.025,w*.014);ctx.fill();}
      paintText(label,w*.5,yy,w*.18,'#ffffff','primary',w*.83);
    }else drawKinetic(scene,p,w,h);
    if(template!=='kinetic'&&scene.title)paintText(scene.title,w*.5,h*.15,w*.09,scene.text_color||'#ffffff',scene.font,w*.86);
    ctx.restore();
  }

  const captionCache=new WeakMap();
  function captionAt(scene){
    const hook=num(state.project?.style?.hook_seconds,4.5);
    if(state.time<hook)return '';
    if(scene.subtitle)return scene.subtitle;
    const words=state.project?.transcript?.words||[];
    let cached=captionCache.get(words);
    if(!cached||cached.hook!==hook){
      const chunks=[];let group=[];
      const flush=()=>{if(group.length){chunks.push({start:group[0].start,end:group.at(-1).end,text:group.map(w=>w.word).join(' ')});group=[];}};
      [...words].sort((a,b)=>a.start-b.start).forEach(word=>{if(word.start<hook||word.end<=word.start)return;if(group.length&&(word.start-group.at(-1).end>.32||group.length>=3))flush();group.push(word);});flush();cached={hook,chunks};captionCache.set(words,cached);
    }
    return cached.chunks.find(chunk=>state.time>=chunk.start&&state.time<chunk.end)?.text||'';
  }

  const baseCanvas=document.createElement('canvas');baseCanvas.width=540;baseCanvas.height=960;
  const baseCtx=baseCanvas.getContext('2d',{willReadFrequently:true}),viewCtx=canvas.getContext('2d');
  function applyPixelEffects(effects){
    const brightness=num(effects?.brightness),contrast=num(effects?.contrast,1),saturation=num(effects?.saturation,1);
    if(!brightness&&contrast===1&&saturation===1)return;
    const pixels=baseCtx.getImageData(0,0,baseCanvas.width,baseCanvas.height),data=pixels.data,shift=Math.round(brightness*255);
    let mean=0;
    for(let i=0;i<data.length;i+=4){for(let c=0;c<3;c++)data[i+c]=clamp(data[i+c]+shift,0,255);if(contrast!==1)mean+=Math.round(data[i]*.299+data[i+1]*.587+data[i+2]*.114);}
    mean=Math.round(mean/(data.length/4));
    if(contrast!==1||saturation!==1)for(let i=0;i<data.length;i+=4){
      if(contrast!==1)for(let c=0;c<3;c++)data[i+c]=clamp(Math.floor(mean+(data[i+c]-mean)*contrast),0,255);
      if(saturation!==1){const gray=Math.round(data[i]*.299+data[i+1]*.587+data[i+2]*.114);for(let c=0;c<3;c++)data[i+c]=clamp(Math.floor(gray+(data[i+c]-gray)*saturation),0,255);}
    }
    baseCtx.putImageData(pixels,0,0);
  }

  function drawPreview(){
    if(state.mode==='render')return;
    const w=canvas.width,h=canvas.height;ctx=viewCtx;ctx.clearRect(0,0,w,h);ctx.fillStyle='#101217';ctx.fillRect(0,0,w,h);
    if(!state.project)return;
    if(state.mode==='source'){state.motionPlayers.forEach(video=>video.pause());if(source.readyState>=2&&!drawCover(source,0,0,w,h))placeholder('Fuente de audio');drawTrackingGuides();return;}
    const scene=currentScene();
    if(!scene){state.overlayPlayers.forEach(video=>video.pause());state.motionPlayers.forEach(video=>video.pause());$('canvas-edit-help').hidden=true;canvas.classList.remove('editable-motion');delete canvas.dataset.motionElement;delete canvas.dataset.motionPose;if(state.project.mode==='scene_ir_component')placeholder('Fin del componente');else if(source.readyState>=2)drawCover(source,0,0,w,h);return;}
    if(!isFreeMotion(scene))state.motionPlayers.forEach(video=>video.pause());const camera=cameraAt(scene);if(['presenter','split'].includes(scene.type))canvas.dataset.cameraPose=JSON.stringify({focus_x:num(camera.focus_x,.5),focus_y:num(camera.focus_y,.5),chin_y:num(camera.chin_y,.65)});else delete canvas.dataset.cameraPose;
    prepareBroll(scene);preparePresenter(scene);ctx=baseCtx;ctx.clearRect(0,0,w,h);ctx.fillStyle='#101217';ctx.fillRect(0,0,w,h);
    if(scene.type==='presenter'){if(!drawCover(presenter.readyState>=2?presenter:source,0,0,w,h,num(camera.focus_y,.5),num(camera.focus_x,.5)))placeholder('Crudo cargando');}
    else if(scene.type==='broll'){if(!drawMedia(assetById(scene.asset_id),0,0,w,h,num(scene.focus_y,.5),num(scene.focus_x,.5)))placeholder(scene.asset_id?'Recurso cargando':'Selecciona un b-roll');}
    else if(scene.type==='split'){
      const top=splitHeight(h);
      if(scene.asset_id){if(!drawMedia(assetById(scene.asset_id),0,0,w,top,num(scene.focus_y,.5),num(scene.focus_x,.5)))placeholder('B-roll superior',0,0,w,top);}else if(isFreeMotion(scene))drawFreeMotion(scene);else drawMotion(scene,0,0,w,top);
      if(!drawCover(presenter.readyState>=2?presenter:source,0,top,w,h-top,num(camera.focus_y,.5),num(camera.focus_x,.5)))placeholder('Crudo original',0,top,w,h-top);
    }else if(isFreeMotion(scene))drawFreeMotion(scene);else drawMotion(scene);
    applyPixelEffects(scene.effects);ctx=viewCtx;
    const transform=keyframeAt(scene);ctx.save();ctx.globalAlpha=clamp(transform.opacity,0,1);ctx.translate(w/2+transform.x*w,h/2+transform.y*h);ctx.scale(transform.scale,transform.scale);ctx.drawImage(baseCanvas,-w/2,-h/2);ctx.restore();
    drawOverlays(scene);
    const p=clamp((state.time-scene.start)/Math.max(scene.end-scene.start,.001),0,1);
    if(scene.type!=='motion'&&!(scene.type==='split'&&!scene.asset_id)&&scene.title)drawKinetic(scene,p,w,scene.type==='split'?splitHeight(h):h);
    const caption=captionAt(scene);
    canvas.setAttribute('aria-label',`Previsualización vertical. ${scene.type==='split'?'Split '+splitLabel()+'. ':''}${scene.title?'Titular: '+scene.title+'. ':''}${caption?'Texto activo: '+caption: 'Sin subtítulo automático activo.'}`);
    if(caption&&caption!==scene.title&&(!SaaS||state.fontsLoaded)){
      ctx.save();let size=Math.max(12,Math.round(w/15));ctx.textBaseline='middle';ctx.font=roleCSS('primary',size);
      while(ctx.measureText(caption).width>w*.86&&size>8){size--;ctx.font=roleCSS('primary',size);}
      const metrics=ctx.measureText(caption),unit=Math.max(1,Math.round(w/540)),maxY=Math.min(h*.87,h*.9-num(metrics.actualBoundingBoxDescent,size*.35)-2*unit-1);
      let y=Math.min(h*.78,maxY),minimum=0;
      if(scene.type==='presenter'||scene.type==='split'){
        const regionStart=scene.type==='split'?splitHeight(h):0,regionHeight=h-regionStart,baseChin=regionStart+num(camera.chin_y,.65)*regionHeight;
        const chin=h*.5+(baseChin-h*.5)*transform.scale+transform.y*h;minimum=chin+unit+num(metrics.actualBoundingBoxAscent,size*.55);y=Math.min(maxY,Math.max(minimum,chin+h*.04));
      }
      ctx.restore();
      if(minimum<=maxY){paintText(caption,w*.5,y,size,'#ffffff','primary',w*.86);canvas.dataset.captionY=String(y);}
      else{canvas.dataset.captionY='blocked';ctx.fillStyle='#442a1ded';ctx.fillRect(0,h-36,w,36);ctx.fillStyle='#ffd49b';ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText('El subtítulo no cabe bajo la barbilla: ajusta el encuadre',w/2,h-14);}
    }else delete canvas.dataset.captionY;

    drawTransition(scene);
    drawMotionSelection(scene);
    if(!state.fontsLoaded&&(scene.title||caption||scene.motion_design?.elements.some(e=>e.type==='text'))){ctx.fillStyle='#412529ed';ctx.fillRect(0,h-36,w,36);ctx.fillStyle='#ffb6a7';ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText(SaaS?'Fuentes del proyecto cargando o no disponibles':'Fuentes obligatorias cargando o no disponibles',w/2,h-14);}
  }

  function frame(now) {
    const delta=(now-lastTick)/1000;lastTick=now;
    if(state.playing&&state.mode!=='render'){
      state.time=sourceReady&&!source.paused?source.currentTime:state.time+delta*Number($('playback-speed').value);
      if(state.time>=duration()){state.time=duration();pause();}
      prepareBroll(currentScene());preparePresenter(currentScene());syncAudio();updateTimecode();updatePlayhead();
    }
    if(now-lastDraw>30){drawPreview();lastDraw=now;}
    requestAnimationFrame(frame);
  }

  function showJobProgress(message,progress) {
    $('job-message').textContent=message;$('job-progress').style.width=`${clamp(progress,0,1)*100}%`;
    $('jobs-strip').querySelector('.status-dot').classList.toggle('busy',progress>0&&progress<1);
  }

  async function runJob(endpoint,body,message) {
    await saveProject();
    const job=await api(`/api/projects/${state.project.id}/${endpoint}`,{method:'POST',body});
    if(job.id)state.jobSeen.set(job.id,'queued');showJobProgress(message, .01);toast(message);await pollJobs();return job;
  }

  async function pollJobs() {
    if(state.pollBusy)return;state.pollBusy=true;
    try {
      if(isShared()){await refreshSharedContext();if(!identity)return;}
      const response=await api('/api/jobs');state.jobs=response.jobs||[];$('connection-label').textContent='Motor local';
      const jobs=state.jobs.filter(j=>!state.project||j.project_id===state.project.id||j.project===state.project.id).reverse();
      const active=jobs.find(j=>['running','queued','pending'].includes(j.status));
      if(active)showJobProgress(active.message||active.stage||active.type||'Procesando',num(active.progress)>1?num(active.progress)/100:num(active.progress,.02));
      else if(jobs.length){const last=jobs[0];showJobProgress(last.message||`${last.action||last.type||'Tarea'} · ${last.status}`,0);}
      for(const job of state.jobs){
        const relevant=!state.project||job.project_id===state.project.id||job.project===state.project.id;
        const old=state.jobSeen.get(job.id);state.jobSeen.set(job.id,job.status);
        if(old&&old!==job.status&&['completed','done','succeeded','failed','error','blocked','cancelled'].includes(job.status)){
          const failed=['failed','error','blocked'].includes(job.status),cancelled=job.status==='cancelled';
          if(relevant)toast(job.error||job.message||(cancelled?'Tarea cancelada sin promover el derivado.':failed?'La tarea requiere atención.':'Tarea completada.'),failed);
          if(!failed&&!cancelled){
            await refreshAssets();
            if(state.project&&!state.dirty&&(job.project_id===state.project.id||job.project===state.project.id)){const id=state.project.id,epoch=state.editEpoch,load=state.loadEpoch,p=await api(`/api/projects/${id}`);if(state.project?.id===id&&state.editEpoch===epoch&&state.loadEpoch===load)setProject(p,false);}
          }
        }
      }
      if($('modal').open&&$('jobs-dialog-list'))renderJobsDialog();if($('settings-form'))paintVoiceAnalysis();
    } catch(error){if(error.name!=='AbortError')$('connection-label').textContent='Sin conexión';}
    finally{state.pollBusy=false;}
  }

  function renderJobsDialog() {
    const list=$('jobs-dialog-list');if(!list)return;
    list.innerHTML=[...state.jobs].reverse().map(j=>`<div class="job-card"><div class="job-card-head"><strong>${esc(j.operation?(state.mediaTools?.find(tool=>tool.id===j.operation)?.name||j.operation):(j.action||j.type||j.kind||'Tarea local'))}</strong><span>${esc(j.status)}</span></div><p>${esc(j.message||j.stage||j.error||'')}<br>${esc(j.project_id||'')}</p><div class="job-bar"><i style="width:${clamp(num(j.progress)>1?num(j.progress):num(j.progress)*100,0,100)}%"></i></div>${j.error?`<p>${esc(j.error)}</p>`:''}${j.result?`<details><summary>Resultado y mediciones</summary><pre class="code-view">${esc(JSON.stringify(j.result,null,2))}</pre></details>`:''}${j.result?.asset?.id?`<button class="button compact ghost" data-job-asset="${esc(j.result.asset.id)}" style="margin-top:10px">Ver derivado · revisión pendiente</button>`:''}${['queued','running'].includes(j.status)?`<button class="button compact ghost" data-cancel-job="${esc(j.id)}" style="margin-top:10px">Cancelar esta tarea local</button>`:''}</div>`).join('')||'<p class="modal-copy">No hay tareas en la cola. El análisis y render se ejecutan de forma local.</p>';
    list.querySelectorAll('[data-job-asset]').forEach(button=>button.onclick=action(async()=>{if(!state.assets.some(asset=>asset.id===button.dataset.jobAsset))await refreshAssets();assetDetail(button.dataset.jobAsset);}));
    list.querySelectorAll('[data-cancel-job]').forEach(b=>b.onclick=action(async()=>{await api(`/api/jobs/${b.dataset.cancelJob}/cancel`,{method:'POST',body:{}});await pollJobs();toast('Cancelación solicitada para esta tarea de SOFTWARE.');}));
  }
  function jobsDialog(){modal('Cola de producción','<p class="modal-copy">Progreso real de las tareas del motor. Los trabajos externos de edición se conservan sin alteraciones.</p><div id="jobs-dialog-list"></div>',renderJobsDialog);}

  async function validateProject({strict=true,seconds=10}={}) {
    if(!state.project)return;await saveProject();
    if(state.dirty)throw new Error('Hay nuevos cambios pendientes. Guárdalos antes de comprobar el proyecto.');
    const result=await api(`/api/projects/${state.project.id}/validate?seconds=${seconds}&strict=${strict?'true':'false'}`);
    $('validation-results').innerHTML=`<p class="${result.valid?'pass':''}">${result.valid?strict?'Controles narrativos superados. La revisión editorial sigue siendo necesaria.':'Controles técnicos del editor superados. No acreditan fidelidad a CLONE/YO ni aprobación narrativa.':'El proyecto necesita ajustes antes del render.'}</p>`+(result.errors||[]).map(e=>`<p>${esc(typeof e==='string'?e:e.message||JSON.stringify(e))}</p>`).join('')+(result.warnings||[]).map(e=>`<p>${esc(typeof e==='string'?e:e.message||JSON.stringify(e))}</p>`).join('');
    if(result.metrics) $('validation-results').innerHTML+=`<details><summary>Mediciones</summary><pre class="code-view">${esc(JSON.stringify(result.metrics,null,2))}</pre></details>`;
    switchTab('workflow');return result;
  }

  function isTechnicalRender(render){return Boolean(render&&(render.mode==='technical_library'||render.production_conformant===false||render.technical_demo===true||render.technical===true||render.status==='technical_not_approved'));}
  function hasCurrentApproval(project){
    const render=project?.renders?.at(-1),review=project?.review;
    return Boolean(project?.approval_current===true&&render&&!isTechnicalRender(render)&&review?.approved_preview&&review.render_sha256===render.sha256&&review.manual&&state.status?.manual&&JSON.stringify(review.manual)===JSON.stringify(state.status.manual));
  }
  function productionPhaseNote(){
    if(SaaS)return 'La base editorial de Iván se adapta a tu marca. La prueba queda pendiente de revisión; las aprobaciones y los encargos del proceso privado de Iván no se trasladan a este proyecto.';
    const policy=state.status?.policy||{};
    if(policy.current_production_phase==='clone_generative_library')return 'En IVAN se construye la biblioteca generativa CLONE con render por lotes y control de calidad por componente. No se monta todavía un reel completo. El SceneIR importado en este editor conserva su revisión pendiente.';
    if(policy.current_production_phase==='clone_approved_design_animation')return 'En IVAN se anima únicamente el diseño CLONE ya aprobado. Esa aprobación no se traslada a nuevos diseños de este editor, que requieren su propia revisión explícita. La prueba técnica del software es independiente.';
    return policy.design_before_animation===true||policy.current_production_phase==='clone_static_design_approval'?'En IVAN se aprueba primero el diseño estático de CLONE antes de animar. Esta prueba del editor es independiente.':'La prueba técnica del editor es independiente de las etapas de aprobación del flujo IVAN.';
  }
  function manualFullScope(project=state.project){
    const source=assetById(project?.source),seconds=num(source?.duration),limit=num(state.status?.capabilities?.render?.manual_full_draft?.max_seconds,600),available=SaaS&&state.status?.capabilities?.render?.manual_full_draft?.available===true&&project?.mode!=='scene_ir_component';
    return {seconds,available:Boolean(available&&seconds>10&&seconds<=limit),covered:Boolean(project?.timeline?.length&&Math.max(...project.timeline.map(scene=>num(scene.end)))>=seconds-1/num(project.settings?.fps,30))};
  }
  function renderDialog(){
    if(!state.project?.source){toast('Importa un crudo antes de renderizar.',true);return;}if(!canEdit()){toast('El permiso de lectura permite reproducir y exportar el editable guardado.');return;}
    const projectId=state.project.id,scope=identityScope(),load=state.loadEpoch,full=manualFullScope();
    modal(full.available?'Exportar video':'Exportar prueba de 10 s',`<form id="render-form"><label class="field">Tipo de exportado<select id="render-kind"><option value="technical">Prueba técnica del editor · hasta 10 s</option>${full.available?'<option value="manual-full">Borrador completo manual · '+fmt(full.seconds)+'</option>':''}<option value="narrative">Prueba narrativa V5</option></select></label><label class="field">Motor de composición<select id="render-engine">${renderEngineOptions(state.project.settings.engine)}</select></label><p class="small-copy">El motor elegido se guarda en el proyecto. No se cambia a otro motor silenciosamente si falta una herramienta.</p><p id="render-scope" class="modal-copy"></p><div class="modal-actions"><button id="start-render" type="submit" class="button primary">Renderizar prueba técnica</button></div></form>`,()=>{
      const form=$('render-form'),button=$('start-render'),explain=()=>{const kind=$('render-kind').value,technical=kind!=='narrative',adapter=capabilityAvailability(state.status?.capabilities?.hyperframes_adapter);$('render-engine').querySelector('[value="native"]').disabled=!technical;if(!technical)$('render-engine').value='hyperframes';$('render-scope').textContent=(kind==='manual-full'?`Exporta la duración real del crudo (${fmt(full.seconds)}) usando la cronología manual. Exige que las escenas cubran toda la fuente. El archivo conserva su revisión pendiente; no aprueba la estética ni autoriza publicación.`:technical?'Verifica reproducción, capas, animaciones locales y mezcla durante los primeros 10 s. El archivo no aprueba fidelidad a CLONE/YO ni el render completo.':`Prueba narrativa de los primeros 10 s: YO para cámara, subtítulos y split; CLONE para motion. Exige HyperFrames/GSAP, manual vigente, diseño aprobado, aplicación comprobada de herramientas y controles narrativos. ${adapter===true?'El motor disponible no sustituye la revisión del resultado.':'El adaptador pendiente o sin verificar puede bloquear este modo.'}`)+' '+productionPhaseNote();button.textContent=kind==='manual-full'?'Exportar borrador completo manual':technical?'Renderizar prueba técnica':'Renderizar prueba narrativa V5';button.disabled=kind==='manual-full'&&!full.covered;};
      if(isShared())$('render-kind').querySelector('[value="narrative"]').disabled=true;$('render-kind').onchange=explain;explain();
      form.onsubmit=action(async event=>{
        event.preventDefault();if(!form.isConnected||!identityCurrent(scope)||state.project?.id!==projectId||state.loadEpoch!==load)throw new DOMException('La selección cambió.','AbortError');if(button.disabled||!canEdit())return;const kind=$('render-kind').value,technical=kind!=='narrative',draftFull=kind==='manual-full',engine=$('render-engine').value,currentFull=manualFullScope();if(draftFull&&(!currentFull.available||!currentFull.covered))throw new Error('Completa la cronología hasta el final del crudo antes de exportar el borrador completo.');const seconds=draftFull?currentFull.seconds:10;button.disabled=true;
        try{if((state.project.settings.engine||'native')!==engine)mutate(p=>p.settings.engine=engine);const result=await validateProject({strict:!technical,seconds});if(!identityCurrent(scope)||state.project?.id!==projectId)throw new DOMException('La selección cambió.','AbortError');
          if(!result.valid){$('modal').close();toast('Completa los controles que aparecen en Producción antes de renderizar.',true,10000);return;}
          if(form.isConnected)$('modal').close();await runJob('render',{seconds,technical,engine,...(draftFull?{draft_full:true}:{})},draftFull?'Exportando borrador completo manual · revisión pendiente…':technical?`Renderizando prueba técnica con ${engine==='hyperframes'?'HyperFrames / GSAP':'motor nativo'} (10 s)…`:'Renderizando prueba narrativa ASCENDIA V5 (10 s)…');
        }finally{if(form.isConnected&&identityCurrent(scope))explain();}
      });
    });
  }

  function reviewDialog() {
    if(!state.project?.renders?.length){toast('Renderiza una prueba antes de revisarla.',true);return;}
    pause();previewMode('render');
    if(isTechnicalRender(state.project.renders.at(-1))){
      modal('Observaciones del exportado técnico','<div class="review-warning">Este exportado verifica el funcionamiento del editor. No puede aprobarse como prueba narrativa ASCENDIA ni certificar fidelidad a CLONE/YO. Anota únicamente lo que hayas comprobado.</div><form id="technical-review-form"><label class="field" style="margin-top:16px">Persona que revisa<input name="reviewer" required placeholder="Nombre del revisor"></label><label class="field">Observaciones técnicas<textarea name="notes" required rows="5" placeholder="Reproducción, capas, sincronización, mezcla y fallos observados. Distingue reproducción escuchada de mediciones automáticas."></textarea></label><div class="modal-actions"><button type="submit" class="button primary">Guardar observaciones sin aprobación</button></div></form>',()=>{
        $('technical-review-form').onsubmit=action(async event=>{event.preventDefault();await saveProject();if(state.dirty)throw new Error('Guarda los nuevos cambios y renderiza la cronología vigente antes de revisarla.');const form=new FormData(event.target);state.project=normalizeProject(projectData(await api(`/api/projects/${state.project.id}/review`,{method:'POST',body:{reviewer:String(form.get('reviewer')).trim(),notes:String(form.get('notes')).trim(),approve_preview:false}})));renderProject();$('modal').close();toast('Observaciones técnicas guardadas sin aprobación narrativa.');});
      });return;
    }
    const checks=[['visual','Composición y continuidad','Vi todas las escenas y transiciones; rostro íntegro, sin blur añadido ni parpadeos.'],['audio','Revisión sonora','Escuché voz, música y efectos; claridad, equilibrio y riser sincronizado.'],['sync','Sincronización','Comprobé texto, acciones y sonidos contra la narración.'],['spelling','Ortografía y legibilidad','Revisé todo el texto, fuentes auténticas y sombra compacta.'],['resources','Pertinencia de recursos','Vi los clips y comprobé su aparición real en el render.'],['movement','Movimiento según CLONE','Comparé la secuencia con CLONE, respetando el diseño estático aprobado: acciones, transformaciones, ritmo y continuidad.'],['identity','Cámara, subtítulos y split según YO',`Comparé cámara, subtítulos, split ${splitLabel()}, jerarquía y presencia máxima con YO.`],['safe_zones','Zonas seguras','Comprobé que texto, rostro e información quedan dentro de las zonas seguras.']];
    modal('Revisión explícita de la prueba',`<div class="review-warning">Esta revisión declara observaciones humanas reales. Reproduce el render completo con audio antes de marcar cada control. Una comprobación técnica no aprueba el contenido.</div><form id="review-form">${checks.map(([key,title,desc])=>`<label class="review-check"><input name="${key}" type="checkbox"><span><strong>${title}</strong><small>${desc}</small></span></label>`).join('')}<label class="field" style="margin-top:16px">Persona que revisa<input name="reviewer" required placeholder="Nombre del revisor"></label><label class="field">Observaciones y evidencia<textarea name="notes" rows="3" required placeholder="Qué comparaste, qué comprobaste y qué falta corregir"></textarea></label><label class="review-check"><input name="approve_preview" type="checkbox"><span>Aprobar explícitamente esta prueba de 10 s. Esto no autoriza el render completo.</span></label><div class="modal-actions"><button type="submit" class="button primary">Registrar revisión</button></div></form>`,()=>{
      $('review-form').onsubmit=action(async event=>{
        event.preventDefault();await saveProject();const form=new FormData(event.target),body={};checks.forEach(([key])=>body[key]=form.has(key));body.approve_preview=form.has('approve_preview');body.reviewer=String(form.get('reviewer')).trim();body.notes=String(form.get('notes')).trim();
        state.project=normalizeProject(projectData(await api(`/api/projects/${state.project.id}/review`,{method:'POST',body})));renderProject();$('modal').close();toast(body.approve_preview?'Revisión y aprobación explícita registradas.':'Revisión registrada sin aprobar la prueba.');
      });
    });
  }

  function evidenceDialog(fieldId) {
    const candidates=state.assets.filter(a=>a.thumbnail||assetKind(a)==='image');
    modal('Elegir evidencia real',`<p class="modal-copy">Una captura documenta lo que viste. Seleccionarla no sustituye revisar el clip en movimiento.</p><div class="assets-grid">${candidates.map(a=>`<button class="asset-card" data-evidence="${esc(evidencePath(a))}"><div class="asset-thumbnail"><img src="${esc(thumbnailUrl(a)||assetUrl(a))}" alt="${esc(a.name)}"></div><span class="asset-name">${esc(a.name)}</span></button>`).join('')}</div>${!candidates.length?'<p class="modal-copy">Importa una captura o un recurso con miniatura para seleccionarlo aquí.</p>':''}`,()=>{
      $('modal-content').querySelectorAll('[data-evidence]').forEach(b=>b.onclick=()=>{const entries=lines($(fieldId).value);if(!entries.includes(b.dataset.evidence))entries.push(b.dataset.evidence);$(fieldId).value=entries.join('\n');$(fieldId).dispatchEvent(new Event('change'));$('modal').close();});
    });
  }

  async function designReviewDialog(){
    const id=state.project?.id,sceneId=selectedScene()?.id;if(!id||!sceneId)return;
    await saveProject();if(state.project?.id!==id||state.selectedScene!==sceneId||state.dirty)throw new Error('La selección o edición cambió. Guarda y vuelve a abrir la revisión del diseño.');
    const data=await api(`/api/projects/${id}/designs`);if(state.project?.id!==id||state.selectedScene!==sceneId)return;
    const snapshot=data.snapshots?.[sceneId];if(!snapshot)throw new Error('Genera primero el PNG del diseño vigente.');
    const snapshotEngine=snapshot.technical?.hyperframes?'hyperframes':snapshot.technical?.engine==='Pillow static design'?'native':null,engineChanged=snapshotEngine!==null&&snapshotEngine!==(state.project.settings.engine||'native');
    const images=state.project.assets.filter(a=>assetKind(a)==='image'),policy=state.status?.policy||{},referenceTime=num(policy.clone_static_reference_time,3.1),checks=[['composition','Composición y proporciones'],['typography','Tipografía y jerarquía'],['spacing','Márgenes, alineación y espaciado'],['color','Fondo, acentos y contraste'],['depth','Sombras, bordes y profundidad']];
    modal('Diseño estático · captura y revisión',`<p class="modal-copy">Esta es una captura real del motor ${esc(snapshot.technical?.engine||'registrado en el recibo')}, sin los keyframes ni las guías del editor. Compararla no aprueba el video ni la revisión narrativa.</p>${engineChanged?'<p class="review-warning" id="design-engine-stale">El motor del proyecto cambió desde este PNG. Genera una nueva captura con el motor actual antes de registrar la revisión.</p>':''}<div class="design-comparison"><figure><img id="design-candidate-image" src="${esc(snapshot.url||fileUrl(snapshot.path))}?sha=${esc(snapshot.sha256)}" alt="Captura real del diseño estático"><figcaption>Diseño candidato · ${esc(String(snapshot.sha256).slice(0,16))}</figcaption></figure><figure id="design-reference-figure" hidden><img id="design-reference-image" alt="Fotograma importado para comparar"><figcaption>Referencia importada</figcaption></figure></div><a class="button ghost full" href="${esc(snapshot.url||fileUrl(snapshot.path))}" download>Descargar PNG del diseño</a><form id="design-review-form"><label class="field">Persona que revisa<input name="reviewer" required maxlength="200" placeholder="Nombre del revisor"></label><label class="field">Observaciones reales<textarea name="notes" required rows="4" placeholder="Composición, tipografía, espaciado, color, profundidad y pendientes que comprobaste en el PNG"></textarea></label><label class="review-check"><input id="approve-design" name="approve_design" type="checkbox" ${engineChanged?'disabled':''}><span>Aprobar este diseño después de compararlo y recibir aprobación explícita del usuario.</span></label><div id="design-approval-fields" hidden><p class="review-warning">Solo una referencia auténtica y una indicación explícita aprueban el diseño. La prueba técnica del software no acredita fidelidad a CLONE.</p><label class="field">Fotograma de referencia importado<select name="reference_asset_id" id="design-reference-asset"><option value="">Elige una imagen del proyecto</option>${images.map(a=>`<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select></label><p class="small-copy">Importa primero el fotograma auténtico si falta en esta lista.</p><div class="field-pair"><label class="field">Referencia<input name="reference_name" value="CLONE" maxlength="200"></label><label class="field">Tiempo de referencia (s)<input name="reference_time" type="number" min="0" max="86400" step=".01" value="${referenceTime}"></label></div>${checks.map(([key,title])=>`<label class="review-check"><input type="checkbox" name="${key}"><span>Comparé ${title.toLowerCase()} con la referencia.</span></label>`).join('')}<label class="field">Indicación explícita de aprobación<textarea name="approval_text" rows="3" placeholder="Transcribe la aprobación del usuario para este diseño vigente"></textarea></label></div><div class="modal-actions"><button type="submit" class="button primary" ${engineChanged?'disabled':''}>Registrar revisión del PNG</button></div></form>`,()=>{
      $('approve-design').onchange=()=>{$('design-approval-fields').hidden=!$('approve-design').checked;};
      $('design-reference-asset').onchange=()=>{const asset=assetById($('design-reference-asset').value);$('design-reference-figure').hidden=!asset;if(asset)$('design-reference-image').src=assetUrl(asset);};
      $('design-review-form').onsubmit=action(async event=>{
        event.preventDefault();if(state.project?.id!==id||state.selectedScene!==sceneId||state.dirty)throw new Error('El proyecto cambió. Guarda y genera la captura vigente antes de revisarla.');
        const form=new FormData(event.target),approve=form.has('approve_design'),body={scene_id:sceneId,expected_sha256:snapshot.sha256,reviewer:String(form.get('reviewer')).trim(),notes:String(form.get('notes')).trim(),approve_design:approve};
        if(approve){Object.assign(body,{reference_asset_id:form.get('reference_asset_id'),reference_name:String(form.get('reference_name')).trim(),reference_time:num(form.get('reference_time')),approval_text:String(form.get('approval_text')).trim(),checks:Object.fromEntries(checks.map(([key])=>[key,form.has(key)]))});if(!body.reference_asset_id||!body.approval_text||!Object.values(body.checks).every(Boolean))throw new Error('Completa la comparación real y la indicación explícita de aprobación.');}
        const response=await api(`/api/projects/${id}/design_review`,{method:'POST',body});if(state.project?.id===id){state.project=normalizeProject(projectData(response));renderProject();}$('modal').close();toast(approve?'Revisión y aprobación explícita del diseño registradas.':'Observaciones del diseño guardadas sin aprobarlo.');
      });
    });
  }

  function trackingDialog(){
    if(!state.project?.source)return;
    const raw=assetById(state.project.source),end=Math.min(60,num(raw.duration,10));
    modal('Medidas faciales · originales',`<p class="modal-copy">MediaPipe analiza muestras reales del crudo en CPU. Devuelve detección, barbilla estimada, foco y evidencia. Las coordenadas pertenecen al original: no se aplican a crop, split ni subtítulos automáticamente.</p><form id="tracking-form"><div class="field-pair"><label class="field">Inicio del original (s)<input id="tracking-start" type="number" min="0" max="14400" step=".01" value="0"></label><label class="field">Fin del original (s)<input id="tracking-end" type="number" min=".01" max="14400" step=".01" value="${end}"></label></div><div class="field-pair"><label class="field">Muestras por segundo<input id="tracking-fps" type="number" min=".5" max="10" step=".5" value="4"></label><label class="field">Máximo de muestras<input id="tracking-max" type="number" min="1" max="600" step="1" value="240"></label></div><div class="field-pair"><label class="field">Umbral del detector<input id="tracking-confidence" type="number" min=".3" max=".99" step=".01" value=".6"></label><label class="field">Suavizado<input id="tracking-smoothing" type="number" min=".05" max="1" step=".05" value=".4"></label></div><p class="small-copy">Hasta 120 s por análisis. Varias personas, perfiles u oclusión pueden impedir la medida; no se inventan posiciones ausentes.</p><div class="modal-actions"><button type="submit" class="button primary">Medir sin cambiar la edición</button></div></form>`,()=>{
      $('tracking-form').onsubmit=action(async event=>{event.preventDefault();const options={start:num($('tracking-start').value),end:num($('tracking-end').value),sample_fps:num($('tracking-fps').value),max_samples:num($('tracking-max').value),min_confidence:num($('tracking-confidence').value),smoothing:num($('tracking-smoothing').value)};if(options.end<=options.start||options.end-options.start>120)throw new Error('Elige un intervalo positivo de hasta 120 segundos.');$('modal').close();await runJob('tracking',options,'Midiendo rostro y barbilla sin aplicar cambios…');});
    });
  }
  async function trackingResultsDialog(){
    const id=state.project?.id;if(!id)return;const data=await api(`/api/projects/${id}/tracking`);if(state.project?.id!==id)return;
    const tracking=data.tracking;if(!tracking)throw new Error('No hay medidas faciales en este proyecto.');const samples=tracking.samples||[],summary=tracking.summary||{},sourceAsset=assetById(state.project.source),matches=sourceAsset?.id===tracking.source&&sourceAsset.sha256===tracking.source_sha256;
    modal('Medidas y evidencia facial',`<p class="modal-copy">${num(summary.detected_samples)} / ${samples.length} muestras detectadas · cobertura ${(num(summary.coverage)*100).toFixed(1)} %. El score del detector no certifica identidad ni precisión de la barbilla. Revisa las muestras; no demuestran presencia en cada fotograma.</p>${!matches?'<p class="review-warning">Estas medidas corresponden a otro contenido original y no se superpondrán a la fuente actual.</p>':''}<label class="review-check"><input id="tracking-guide-toggle" type="checkbox" ${state.trackingOverlay?'checked':''} ${matches?'':'disabled'}><span>Mostrar guía de la muestra más cercana en Original. Solo es una ayuda de lectura.</span></label><div class="tracking-evidence-frame" id="tracking-evidence-frame" hidden><img id="tracking-evidence-image" alt="Fotograma real analizado"><svg id="tracking-evidence-guide" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Caja facial y barbilla estimadas"></svg></div><p id="tracking-sample-detail" class="small-copy"></p><div class="tracking-samples">${samples.map((sample,i)=>`<button type="button" data-tracking-sample="${i}" class="tracking-sample">${fmt(sample.time)} <span>${sample.detected?'Detectado · '+num(sample.confidence).toFixed(3):sample.status==='no_face'?'Sin detección':esc(sample.status)}</span></button>`).join('')}</div>${tracking.proposals?.length?`<details><summary>Propuestas pendientes de transformación y revisión</summary><pre class="code-view">${esc(JSON.stringify(tracking.proposals,null,2))}</pre></details>`:''}<p class="small-copy">No se modificaron encuadre, foco, barbilla ni criterios de aprobación.</p>${tracking.url?`<a class="button ghost full" href="${esc(tracking.url)}" target="_blank" rel="noopener">Abrir informe de medidas</a>`:''}`,()=>{
      const proposalPanel=document.createElement('section');proposalPanel.className='tracking-proposals';proposalPanel.innerHTML='<button type="button" id="read-tracking-proposals" class="button ghost full">Ver propuestas de encuadre por escena</button><div id="tracking-proposal-results" aria-live="polite"></div>';
      $('modal-content').querySelector('.tracking-samples').after(proposalPanel);
      $('read-tracking-proposals').onclick=action(async()=>{
        const proposals=await api(`/api/projects/${id}/tracking_proposals`);if(state.project?.id!==id||!$('tracking-proposal-results'))return;
        const items=proposals.proposals||[],errors=proposals.errors||[];
        $('tracking-proposal-results').innerHTML=`<p class="small-copy">Sugerencias de lectura: no se aplican al montaje ni marcan la barbilla como revisada.</p>${errors.length?`<p class="review-warning">${errors.map(esc).join('<br>')}</p>`:!items.length?'<p class="small-copy">No hay escenas de cámara o split para proponer un encuadre.</p>':''}${items.map(item=>`<details><summary>${esc(item.scene_id)} · ${item.status==='pending_visual_review'?'Pendiente de revisión visual':'Sin propuesta aplicable'}</summary>${item.errors?.length?`<p class="small-copy">${item.errors.map(esc).join('<br>')}</p>`:''}<pre class="code-view">${esc(JSON.stringify(item,null,2))}</pre></details>`).join('')}`;
      });
      $('tracking-guide-toggle').onchange=()=>{state.trackingOverlay=$('tracking-guide-toggle').checked;if(state.trackingOverlay){previewMode('source');drawPreview();}};
      $('tracking-evidence-image').onload=event=>{$('tracking-evidence-frame').style.aspectRatio=`${event.target.naturalWidth}/${event.target.naturalHeight}`;};
      $('modal-content').querySelectorAll('[data-tracking-sample]').forEach(button=>button.onclick=()=>{
        const sample=samples[Number(button.dataset.trackingSample)],box=sample.bbox,point=sample.smoothed||sample.raw;$('tracking-evidence-frame').hidden=!sample.evidence;if(sample.evidence)$('tracking-evidence-image').src=fileUrl(sample.evidence);
        $('tracking-evidence-guide').innerHTML=sample.detected&&box&&point?`<rect x="${box.x*100}" y="${box.y*100}" width="${box.width*100}" height="${box.height*100}"/><circle cx="${point.chin_x*100}" cy="${point.chin_y*100}" r="1"/>`:'';
        $('tracking-sample-detail').textContent=`Original ${fmt(sample.time)} · ${sample.detected?`barbilla estimada Y=${num(point?.chin_y).toFixed(3)}, score=${num(sample.confidence).toFixed(3)}`:'No hay una posición facial válida en esta muestra.'}`;if(matches){state.project.tracking=tracking;previewMode('source');seekTime(sample.time);}
      });
      if(samples.length)$('modal-content').querySelector('[data-tracking-sample]').click();
    });
  }
  function drawTrackingGuides(){
    if(!state.trackingOverlay||state.mode!=='source')return;const tracking=state.project.tracking,raw=assetById(state.project.source);if(!tracking||tracking.source!==raw?.id||tracking.source_sha256!==raw.sha256)return;
    const sample=(tracking.samples||[]).reduce((nearest,item)=>!nearest||Math.abs(item.time-state.time)<Math.abs(nearest.time-state.time)?item:nearest,null),fps=num(tracking.sampling?.requested_fps,4);
    if(!sample?.detected||Math.abs(sample.time-state.time)>.5/fps+.02||!sample.bbox)return;
    const w=canvas.width,h=canvas.height,mw=source.videoWidth,mh=source.videoHeight;if(!mw||!mh)return;const scale=Math.max(w/mw,h/mh),sx=(mw-w/scale)/2,sy=(mh-h/scale)/2,box=sample.bbox,p=sample.smoothed||sample.raw;
    ctx.save();ctx.lineWidth=2;ctx.strokeStyle='#91c3e5';ctx.setLineDash([6,5]);ctx.strokeRect((box.x*mw-sx)*scale,(box.y*mh-sy)*scale,box.width*mw*scale,box.height*mh*scale);ctx.setLineDash([]);if(p){ctx.fillStyle='#c5e3fa';ctx.beginPath();ctx.arc((p.chin_x*mw-sx)*scale,(p.chin_y*mh-sy)*scale,4,0,Math.PI*2);ctx.fill();}ctx.fillStyle='#13202edb';ctx.fillRect(0,0,w,28);ctx.fillStyle='#c5e3fa';ctx.font='11px system-ui';ctx.textAlign='left';ctx.fillText(`Muestra ${sample.time.toFixed(2)} s · barbilla estimada · score ${sample.confidence.toFixed(3)}`,10,18);ctx.restore();
  }

  async function manualDialog() {
    const scope={id:state.project?.id||null,load:state.loadEpoch,edit:state.editEpoch},matches=()=>state.project?.id===scope.id&&state.loadEpoch===scope.load&&state.editEpoch===scope.edit;
    manualCache=await api('/api/manual');
    if(scope.id&&!matches())return;
    const documents=manualCache.documents||[];
    const shownFingerprints=Object.fromEntries(documents.map(d=>[d.name,d.sha256]));
    modal(SaaS?'Perfil editorial completo · base Iván':'Manual completo · ASCENDIA',`<p class="modal-copy">${SaaS?'Este perfil del software contiene las reglas duraderas de edición. Su lectura no acredita haber leído los manuales originales del proceso privado de Iván.':'Las directivas más recientes prevalecen.'} Lee completos los documentos para registrar la lectura de este proyecto.</p>${documents.map(d=>`<details open><summary>${esc(d.name)} <small>${esc((d.sha256||'').slice(0,12))}</small></summary><pre class="code-view" style="max-height:360px">${esc(d.content)}</pre></details>`).join('')}<label class="review-check"><input id="manual-read-check" type="checkbox"><span>He leído completos todos los documentos y sus modificaciones.</span></label><div class="modal-actions"><button id="record-manual" class="button primary" disabled>Registrar lectura completa</button></div>`,()=>{
      $('manual-read-check').onchange=()=>$('record-manual').disabled=!$('manual-read-check').checked||!scope.id;
      $('record-manual').onclick=action(async()=>{
        const fresh=await api('/api/manual'),current=Object.fromEntries((fresh.documents||[]).map(d=>[d.name,d.sha256]));
        if(!matches())throw new Error('La selección o edición cambió. Abre de nuevo el perfil desde el proyecto deseado.');
        if(JSON.stringify(shownFingerprints)!==JSON.stringify(current)){await manualDialog();toast('El manual cambió mientras lo leías. Revisa los documentos actualizados antes de registrar la lectura.',true);return;}
        await saveProject();if(!matches()||state.dirty)throw new Error('La selección o edición cambió. Guarda y abre de nuevo el perfil antes de registrar la lectura.');
        const result=await api(`/api/projects/${scope.id}/manual`,{method:'POST',body:{read_complete:true,expected_fingerprints:shownFingerprints}});if(!matches())return;state.project=normalizeProject(projectData(result));if(state.status)state.status.manual=state.project.manual;renderProject();$('modal').close();toast('Lectura completa registrada con las huellas de los documentos.');
      });
    });
  }

  function sourceAudioTracks(asset=assetById(state.project?.source)){
    return (asset?.probe?.streams||[]).filter(stream=>stream.codec_type==='audio'&&Number.isInteger(stream.index)).map(stream=>({...stream,label:`Pista global ${stream.index} · ${stream.codec_name||'audio'} · ${stream.channels||'?'} canal${stream.channels===1?'':'es'}${stream.tags?.language?' · '+stream.tags.language:''}${stream.tags?.title?' · '+stream.tags.title:''}`}));
  }
  function paintVoiceAnalysis(){
    const form=$('settings-form'),host=$('voice-analysis-result'),scope=state.voiceModalScope;if(!host||!form||scope?.form!==form||state.project?.id!==scope.projectId||state.project.source!==scope.assetId)return;
    const job=scope.requestedJobId?state.jobs.find(job=>job.id===scope.requestedJobId&&job.action==='audio_tracks'&&job.asset_id===scope.assetId):[...state.jobs].reverse().find(job=>job.action==='audio_tracks'&&job.asset_id===scope.assetId),result=job?.result,button=$('analyze-voice-tracks');if(button)button.disabled=isShared()||!canEdit()||capabilityAvailability(state.status?.capabilities?.audio?.track_selection)!==true||!sourceAudioTracks().length||scope.submitting||Boolean(scope.requestedJobId&&!job)||Boolean(job&&['queued','running','pending'].includes(job.status));host.replaceChildren();if(scope.submitting||scope.requestedJobId&&!job){const pending=document.createElement('p');pending.className='small-copy';pending.textContent=scope.submitting?'Solicitando una nueva medición de actividad…':'Medición solicitada en cola · '+scope.requestedJobId;host.append(pending);return;}if(!job)return;
    const status=document.createElement('p');status.className='small-copy';status.textContent=(scope.requestedJobId?'Medición solicitada · ':'Última medición registrada · ')+(job.error||job.message||'Midiendo actividad de las pistas')+' · '+job.status;host.append(status);if(job.status!=='completed'||result?.source_sha256!==scope.sha)return;
    const table=document.createElement('div');table.className='voice-track-results';for(const track of result.tracks||[]){const line=document.createElement('p');line.className='small-copy';line.textContent=`Pista global ${track.stream_index}: actividad ${(num(track.active_window_ratio)*100).toFixed(1)} % · RMS ${track.rms_dbfs===null?'silencio':num(track.rms_dbfs).toFixed(1)+' dBFS'} · ${num(track.decoded_seconds).toFixed(2)} s decodificados`;table.append(line);}host.append(table);
    const note=document.createElement('p');note.className='small-copy';note.textContent='Actividad puede ser voz, música o ruido. No se identificó al narrador ni se escuchó el archivo; no se cambió la pista seleccionada.';host.append(note);
    if(Number.isInteger(result.recommended_stream_index)&&sourceAudioTracks().some(track=>track.index===result.recommended_stream_index)){const button=document.createElement('button');button.type='button';button.className='button ghost full';button.id='use-suggested-voice-track';button.textContent='Elegir pista sugerida por actividad · '+result.recommended_stream_index;button.disabled=!canEdit();button.onclick=()=>{if(form===state.voiceModalScope?.form&&state.project?.id===scope.projectId&&canEdit())$('setting-voice-track').value=String(result.recommended_stream_index);};host.append(button);}
  }
  function settingsDialog() {
    if(!state.project){toast('Crea un proyecto para configurar la salida.');return;}
    const s=state.project.settings,asset=assetById(state.project.source),tracks=sourceAudioTracks(asset),scope={projectId:state.project.id,assetId:asset?.id||null,sha:asset?.sha256,identity:identityScope(),load:state.loadEpoch,edit:state.editEpoch};
    modal('Configuración del proyecto',`<p class="modal-copy">Formato vertical y salida editable. Los exportados técnicos mantienen su revisión pendiente.</p><form id="settings-form"><label class="field">Motor<select id="setting-engine">${renderEngineOptions(s.engine)}</select></label><label class="field">Resolución<select id="setting-resolution">${[[1080,1920],[720,1280],[360,640]].some(([width,height])=>s.width===width&&s.height===height)?'':`<option value="current" selected>${s.width} × ${s.height} · formato actual</option>`}<option value="1080" ${s.width===1080&&s.height===1920?'selected':''}>1080 × 1920 · producción</option><option value="720" ${s.width===720&&s.height===1280?'selected':''}>720 × 1280 · edición</option><option value="360" ${s.width===360&&s.height===640?'selected':''}>360 × 640 · prueba rápida</option></select></label><label class="field">Fotogramas por segundo<select id="setting-fps">${[24,30,60].includes(s.fps)?'':`<option value="${s.fps}" selected>${s.fps} FPS · valor actual</option>`}<option value="24" ${s.fps===24?'selected':''}>24 FPS</option><option value="30" ${s.fps===30?'selected':''}>30 FPS · estilo YO</option><option value="60" ${s.fps===60?'selected':''}>60 FPS</option></select></label><label class="field">Pantalla dividida<select id="setting-split-ratio">${splitRatioOptions()}</select></label><p class="small-copy">Motion arriba y grabación original abajo. Cambiar la proporción altera el recorte; revisa rostro, barbilla y zonas seguras.</p><label class="field">Pista de voz para transcripción y render<select id="setting-voice-track" ${tracks.length?'':'disabled'}><option value="" ${s.voice_audio_stream===null||s.voice_audio_stream===undefined?'selected':''}>Selección automática por el motor</option>${tracks.map(track=>`<option value="${track.index}" ${s.voice_audio_stream===track.index?'selected':''}>${esc(track.label)}</option>`).join('')}</select></label><p class="small-copy">${tracks.length?'Los números son índices globales reales de FFprobe, no la posición dentro de esta lista.':'El crudo no informa pistas de audio disponibles.'} ${tracks.length>1?'La vista Original del navegador reproduce la pista predeterminada del archivo; la selección explícita se aplica a la transcripción y al render.':''}</p><button id="analyze-voice-tracks" class="button ghost full" type="button" ${tracks.length&&!isShared()&&capabilityAvailability(state.status?.capabilities?.audio?.track_selection)===true?'':'disabled'}>Medir actividad de audio · hasta 30 s</button><div id="voice-analysis-result" aria-live="polite"></div><div class="tool-row"><span>Fuente principal</span><span>${esc(roleName('primary'))}</span></div><div class="tool-row"><span>Fuente de énfasis</span><span>${esc(roleName('accent'))}</span></div><div class="modal-actions"><button id="apply-project-settings" type="submit" class="button primary">Aplicar configuración</button></div></form>`,()=>{
      const form=$('settings-form');state.voiceModalScope={...scope,form};if(!canEdit())for(const control of form.querySelectorAll('input,select,button'))control.disabled=true;
      const matches=()=>form.isConnected&&identityCurrent(scope.identity)&&state.project?.id===scope.projectId&&(state.project.source||null)===scope.assetId&&state.loadEpoch===scope.load;
      $('analyze-voice-tracks').onclick=action(async()=>{if(!matches()||isShared()||!canEdit())throw new DOMException('La selección cambió.','AbortError');const button=$('analyze-voice-tracks'),voiceScope=state.voiceModalScope;if(voiceScope.submitting||voiceScope.requestedJobId&&state.jobs.some(job=>job.id===voiceScope.requestedJobId&&['queued','running','pending'].includes(job.status)))return;voiceScope.submitting=true;voiceScope.requestedJobId=null;button.disabled=true;paintVoiceAnalysis();try{const job=await api('/api/assets/'+encodeURIComponent(scope.assetId)+'/audio-tracks',{method:'POST',body:{start:0,duration:Math.min(30,num(asset.duration,30))}});if(!matches())return;voiceScope.requestedJobId=job.id;voiceScope.submitting=false;state.jobSeen.set(job.id,'queued');toast('Análisis de actividad en cola; no identifica ni selecciona voz automáticamente.');await pollJobs();}finally{if(matches()){voiceScope.submitting=false;paintVoiceAnalysis();}}});
      form.onsubmit=event=>{event.preventDefault();if(!matches()||!canEdit())return;const dimensions=selectedResolution($('setting-resolution').value,s),value=$('setting-voice-track').value;mutate(p=>{p.settings={...p.settings,...dimensions,fps:Number($('setting-fps').value),engine:$('setting-engine').value,split_motion_ratio:Number($('setting-split-ratio').value),voice_audio_stream:value===''?null:Number(value)};});renderProject();$('modal').close();};paintVoiceAnalysis();
    });
  }

  function renderEngineOptions(engine='native'){return `<option value="native" ${engine==='hyperframes'?'':'selected'}>Nativo · composición local</option><option value="hyperframes" ${engine==='hyperframes'?'selected':''}>HyperFrames · GSAP</option>`;}

  function capabilityAvailability(value){if(typeof value==='boolean')return value;if(typeof value?.available==='boolean')return value.available;if(typeof value?.ready==='boolean')return value.ready;return null;}
  function toolsDialog() {
    const status=state.status||{},capabilities=status.capabilities||{},entries=Array.isArray(capabilities)?capabilities.map(c=>[c.name||c.id,c]):Object.entries(capabilities);
    const rows=entries.map(([name,value])=>{const available=capabilityAvailability(value),label=available===true?'Disponible':available===false||value?.installed===false?'Pendiente':value?.installed===true?'Instalado · uso sin verificar':'Sin verificar',detail=typeof value==='string'?value:typeof value==='object'?[value?.version,value?.status].filter(Boolean).join(' · '):'';return `<div class="tool-row ${available===true?'':'warning'}"><span>${esc(name)}</span><span>${esc(label+(detail?' · '+detail:''))}</span></div>`;}).join('');
    modal('Motor local y herramientas',`<p class="modal-copy">${esc(status.app||'Ascendia Studio')} ${esc(status.version||'')}. Estado comunicado por el servidor local. Instalación, disponibilidad y aplicación comprobada en un proyecto son controles distintos.</p>${rows||'<p class="modal-copy">El servidor aún no informó las capacidades.</p>'}<details><summary>Estado y procesos externos</summary><pre class="code-view">${esc(JSON.stringify({policy:status.policy,active_external:status.active_external},null,2))}</pre></details>`);
  }

  async function tasksDialog(){
    const response=await api('/api/tasks'),tasks=(response.tasks||response||[]).filter(t=>!state.project||t.project_id===state.project.id),roles={director:'Dirección',resources:'Recursos',motion:'Motion',audio:'Sonido',qa:'Control de calidad'};
    modal('Workflow de agentes',`<p class="modal-copy">Encargos concretos para clientes Codex o MCP. Cada agente reclama su tarea, aporta observaciones y evidencia; la aprobación editorial sigue siendo explícita.</p>${tasks.map(t=>`<div class="job-card"><div class="job-card-head"><strong>${esc(roles[t.role]||t.role)}</strong><span>${esc(t.status)}</span></div><p>${esc(t.purpose)}${t.agent?'<br>Agente: '+esc(t.agent):''}<br>Depende de: ${esc((t.depends||[]).map(r=>roles[r]||r).join(', ')||'Ninguna etapa')}</p>${t.result_path?`<a class="button compact ghost" href="${esc(fileUrl(t.result_path))}" target="_blank" rel="noopener">Abrir resultado</a>`:''}</div>`).join('')||'<p class="modal-copy">Prepara las tareas desde Producción cuando el proyecto tenga su crudo y contexto.</p>'}`);
  }

  async function exportProject() {
    if(canEdit())await saveProject();const result=await api(`/api/projects/${state.project.id}/export`,{method:'POST',body:{}});
    const href=result.url||fileUrl(result.path),name=result.name||`${state.project.name}-editable.zip`;
    modal('Proyecto editable listo',`<p class="modal-copy">El paquete contiene la cronología guardada, recursos y evidencias.${isShared()?' Es la revisión guardada por el propietario; los cambios locales pendientes no se incluyen.':' Puedes reabrirlo desde Biblioteca → Abrir editable ZIP.'}</p><div class="tool-row"><span>Tamaño del archivo</span><span>${(num(result.size)/1024/1024).toFixed(2)} MB</span></div><div class="modal-actions"><a id="download-editable-link" class="button primary" href="${esc(namespaceURL(href))}" download="${esc(name)}">${icon('export')}Descargar editable ZIP</a></div>`);
  }

  async function cloudBackupDialog(){
    if(!SaaS||isShared()||!state.project)return;
    const pid=state.project.id,scope=identityScope();
    const [config,backup]=await Promise.all([api('/api/cloud-storage'),api(`/api/projects/${pid}/cloud-backup`)]);
    if(!identityCurrent(scope)||state.project?.id!==pid)return;
    const ready=config.configured===true&&config.enabled===true;
    const verified=backup.integrity_verified===true&&backup.live_remote_execution_verified===true&&backup.pending===false;
    const label=verified?(backup.project_revision===state.project.revision?'Respaldo remoto verificado':'Respaldo verificado de una revisión anterior'):backup.pending?'Respaldo pendiente':'Guardado en este servidor';
    modal('Respaldo del proyecto',`<p class="modal-copy">${ready?'El respaldo incluye el proyecto guardado, sus recursos y los exportados pertinentes. Cada archivo se verifica antes de actualizar la copia remota.':'El administrador todavía no conectó un almacenamiento remoto. Tus proyectos y recursos se guardan en este servidor.'}</p><div class="tool-row"><span>Estado</span><strong>${esc(label)}</strong></div>${backup.project_revision?`<div class="tool-row"><span>Revisión respaldada</span><span>${esc(backup.project_revision)}</span></div>`:''}<p class="small-copy">Compartir un proyecto permite colaborar en la copia del servidor. Un respaldo en nube conserva también la revisión editorial pendiente.</p><div class="modal-actions"><button id="start-cloud-backup" class="button primary" ${ready?'':'disabled'}>Respaldar proyecto guardado</button></div>`,()=>{
      $('start-cloud-backup').onclick=action(async()=>{
        if(!identityCurrent(scope)||state.project?.id!==pid)return;
        await saveProject();
        if(!identityCurrent(scope)||state.project?.id!==pid)return;
        const projectRevision=state.project.revision;
        const latest=await api(`/api/projects/${pid}/cloud-backup`);
        if(!identityCurrent(scope)||state.project?.id!==pid||state.project.revision!==projectRevision)return;
        await api(`/api/projects/${pid}/cloud-backup`,{method:'POST',body:{expected_revision:projectRevision,expected_outbox_revision:latest.revision||0,expected_etag:latest.manifest_etag||null,include_outputs:true}});
        toast('Respaldo en cola. Consulta su verificación en Producción.');await pollJobs();jobsDialog();
      });
    });
  }

  function bindEvents() {
    document.querySelectorAll('.rail-item[data-tab]').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));
    $('close-modal').onclick=()=>$('modal').close();
    $('modal').addEventListener('click',event=>{if(event.target===$('modal')){const r=$('modal').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('modal').close();}});
    $('new-project').onclick=()=>guardUnsaved(newProjectDialog);
    $('project-select').onchange=()=>{const id=$('project-select').value;if(id)guardUnsaved(()=>loadProject(id));};
    ['import-media','start-import'].forEach(id=>$(id).onclick=()=>{$('file-input').accept='video/*,audio/*,image/*,.mkv,.mov,.mxf,.webm,.avi,.m4a,.flac,.ogg';$('file-input').click();});
    $('import-audio').onclick=()=>{$('file-input').accept='audio/*,.wav,.mp3,.m4a,.flac,.ogg';$('file-input').click();};
    $('import-editable').onclick=()=>guardUnsaved(()=>$('bundle-input').click());$('bundle-input').onchange=action(()=>importBundle($('bundle-input').files[0]));
    $('file-input').onchange=action(()=>importFiles([...$('file-input').files]));
    $('asset-search').oninput=renderAssets;
    document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{state.filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(c=>c.classList.toggle('active',c===b));renderAssets();});
    $('save-project').onclick=action(async()=>{await saveProject();toast(state.dirty?'Se guardó la revisión anterior. Conservas nuevos cambios pendientes.':'Proyecto guardado.');});
    $('export-project').onclick=action(exportProject);
    if($('cloud-backup'))$('cloud-backup').onclick=action(cloudBackupDialog);
    $('add-scene').onclick=()=>addScene();$('split-scene').onclick=action(splitScene);$('delete-scene').onclick=removeScene;
    $('create-free-motion').onclick=createFreeMotion;
    $('import-scene-ir').onclick=()=>guardUnsaved(()=>{$('scene-ir-input').value='';$('scene-ir-input').click();});$('scene-ir-input').onchange=action(()=>previewSceneIR($('scene-ir-input').files[0]));
    ['manage-library-fonts','manage-motion-fonts'].forEach(id=>$(id).onclick=action(()=>fontLibraryDialog()));
    $('scene-ir-schema').onclick=action(async()=>{const schema=await api('/api/scene-ir/schema');modal('SceneIR · esquema de datos',`<p class="modal-copy">Contrato del compilador local: contenido declarado, geometría, acciones y parámetros explícitos. El documento no ejecuta código ni acredita reconstrucción de CLONE.</p><pre id="scene-ir-schema-json" class="code-view">${esc(JSON.stringify(schema,null,2))}</pre>`);});
    $('snapshot-design').onclick=action(async()=>{const scene=selectedScene();if(isFreeMotion(scene))await runJob('design_snapshot',{scene_id:scene.id},'Capturando PNG del diseño estático…');});$('review-design').onclick=action(designReviewDialog);
    $('track-source').onclick=trackingDialog;$('view-tracking').onclick=action(trackingResultsDialog);
    ['text','shape','media'].forEach(type=>$(`motion-add-${type}`).onclick=action(()=>addMotionElement(type)));
    $('motion-background').onchange=()=>{const scene=selectedScene();if(isFreeMotion(scene))mutate(()=>scene.motion_design.canvas.background=$('motion-background').value);};
    canvas.addEventListener('pointerdown',canvasMotionDrag);
    canvas.addEventListener('keydown',event=>{
      if(!canEdit()&&event.key!=='Escape')return;
      const scene=currentScene(),element=motionElement();if(!isFreeMotion(scene)||scene.id!==state.selectedScene)return;
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();if(state.selectedPathPoint!==null){state.selectedPathPoint=null;drawPreview();}else selectMotionElement(null);return;}
      if(['Delete','Backspace'].includes(event.key)){event.preventDefault();event.stopPropagation();if(element){if(state.selectedPathPoint!==null&&element.path){if(element.path.points.length>2)mutate(()=>{element.path.points.splice(state.selectedPathPoint,1);state.selectedPathPoint=null;});else toast('Una trayectoria necesita al menos dos puntos.');}else deleteMotionElement();}return;}
      if(!element)return;
      if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();event.stopPropagation();const pixels=event.shiftKey?10:1,dx=(event.key==='ArrowLeft'?-pixels:event.key==='ArrowRight'?pixels:0)/(state.project.settings.width||1080),dy=(event.key==='ArrowUp'?-pixels:event.key==='ArrowDown'?pixels:0)/motionDimensions(scene,state.project.settings.width||1080,state.project.settings.height||1920).height;mutate(()=>{if(state.selectedPathPoint!==null&&element.path?.points[state.selectedPathPoint]){const point=element.path.points[state.selectedPathPoint];point.x=clamp(point.x+dx,-2,2);point.y=clamp(point.y+dy,-2,2);}else translateMotionElement(element,scene,dx,dy);});}
    });
    $('undo').onclick=undo;$('redo').onclick=redo;
    $('play-button').onclick=action(()=>state.playing?pause():play());$('jump-start').onclick=()=>seekTime(0);
    ['timeline','source','render'].forEach(mode=>$(`preview-${mode}`).onclick=()=>previewMode(mode));
    $('safe-zones').onclick=()=>{state.safe=!state.safe;$('safe-zones').classList.toggle('active',state.safe);$('safe-overlay').classList.toggle('visible',state.safe);};$('safe-overlay').classList.add('visible');
    $('mute-button').onclick=()=>{source.muted=!source.muted;$('mute-button').classList.toggle('active',source.muted);$('mute-button').title=source.muted?'Activar voz':'Silenciar voz';$('render-video').muted=source.muted;syncAudio();};
    $('playback-speed').onchange=()=>{source.playbackRate=Number($('playback-speed').value);broll.playbackRate=source.playbackRate;$('render-video').playbackRate=source.playbackRate;syncAudio();};
    $('fullscreen-preview').onclick=action(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('preview-frame').requestFullscreen();});
    $('timeline-zoom').oninput=()=>{state.zoom=Number($('timeline-zoom').value);renderTimeline();};
    $('fit-timeline').onclick=()=>{state.zoom=clamp(($('timeline-scroll').clientWidth-140)/Math.max(10,duration()),25,180);$('timeline-zoom').value=state.zoom;renderTimeline();};
    ['timeline-ruler','picture-track','overlay-track','motion-text-track','motion-shape-track','motion-media-track','text-track','voice-track','music-track'].forEach(id=>$(id).onpointerdown=timelineSeek);
    $('playhead').querySelector('i').onpointerdown=timelineSeek;
    $('picture-track').ondragover=event=>{if(event.dataTransfer.types.includes('application/ascendia-asset'))event.preventDefault();};
    $('picture-track').ondrop=action(async event=>{event.preventDefault();const id=event.dataTransfer.getData('application/ascendia-asset');if(!id)return;seekTime((event.clientX-$('timeline-content').getBoundingClientRect().left)/state.zoom);state.selectedScene=null;await useAsset(id);});
    $('preview-stage').ondragover=event=>{if(event.dataTransfer.types.includes('Files'))event.preventDefault();};
    $('preview-stage').ondrop=action(async event=>{event.preventDefault();if(event.dataTransfer.files.length)await importFiles([...event.dataTransfer.files]);});
    $('scene-form').onsubmit=event=>event.preventDefault();
    ['scene-form','transcript-list','audio-tracks'].forEach(id=>$(id).addEventListener('input',event=>{if(state.project&&event.target.id!=='motion-auto-key')dirty();}));
    bindSceneField('scene-type',(s,v)=>{s.type=v;if(!['motion','split'].includes(v)&&s.template==='custom'){delete s.motion_design;s.template='kinetic';}});bindSceneField('scene-start',(s,v)=>{const t=Number(v);if(t>=0&&t<s.end)trimScene(s,t,s.end);});bindSceneField('scene-end',(s,v)=>{const t=Number(v);if(t>s.start)trimScene(s,s.start,t);});
    bindSceneField('scene-asset',(s,v)=>s.asset_id=v||null);bindSceneField('scene-source-in',(s,v)=>{if(s.type==='split')s.broll_in=Math.max(0,Number(v));else s.source_in=Math.max(0,Number(v));});bindSceneField('scene-template',(s,v)=>{if(v==='custom')enableFreeMotion(s);else{s.template=v;delete s.motion_design;state.selectedElement=null;}});
    bindSceneField('scene-presenter-in',(s,v)=>s.source_in=Math.max(0,Number(v)));for(const axis of ['x','y'])bindSceneField(`scene-focus-${axis}`,(s,v)=>{s[`focus_${axis}`]=Number(v);$(`focus-${axis}-output`).textContent=`${Math.round(Number(v)*100)} %`;});
    bindSceneField('scene-title',(s,v)=>s.title=v);bindSceneField('scene-accent-text',(s,v)=>s.emphasis=v);bindSceneField('scene-subtitle',(s,v)=>s.subtitle=v);bindSceneField('scene-color',(s,v)=>{s.text_color=v;s.semantic_red=/^#(?:ff|f[0-9a-f]|e[0-9a-f]|d[0-9a-f]|c[0-9a-f]|b[0-9a-f])/i.test(v)&&parseInt(v.slice(1,3),16)>parseInt(v.slice(3,5),16)*1.5;});bindSceneField('scene-emphasis',(s,v)=>s.font=v);bindSceneField('scene-color-reason',(s,v)=>{s.red_reason=v;s.color_reason=v;});bindSceneField('scene-text-pause',(s,v)=>s.text_pause_reason=v);
    bindSceneField('scene-chin',(s,v)=>{s.chin_y=Number(v);$('chin-output').textContent=`${Math.round(Number(v)*100)} %`;});
    ['brightness','contrast','saturation'].forEach(effect=>bindSceneField(`scene-${effect}`,(s,v)=>{s.effects||={};s.effects[effect]=effect==='brightness'?Number(v)-1:Number(v);$(`${effect}-output`).textContent=`${Math.round(Number(v)*100)} %`;}));
    bindSceneField('scene-nodes',(s,v)=>s.nodes=lines(v));bindSceneField('scene-labels',(s,v)=>{s.motion||={};s.motion.labels=lines(v);});bindSceneField('scene-value',(s,v)=>{s.motion||={};if(v.trim())s.motion.value=Number(v);else delete s.motion.value;});bindSceneField('scene-value-from',(s,v)=>{s.motion||={};s.motion.from=Number(v);});bindSceneField('scene-decimals',(s,v)=>{s.motion||={};s.motion.decimals=clamp(Number(v),0,4);});bindSceneField('scene-suffix',(s,v)=>{s.motion||={};s.motion.suffix=v;});
    bindSceneField('scene-transition',(s,v)=>s.transition_asset_id=v||null);bindSceneField('scene-transition-duration',(s,v)=>s.transition_duration=clamp(Number(v),.3,1));bindSceneField('scene-transition-source',(s,v)=>s.transition_source_in=Math.max(0,Number(v)));
    bindSceneField('scene-search',(s,v)=>{s.decision||={};s.decision.search=v;});bindSceneField('scene-reason',(s,v)=>{s.decision||={};s.decision.reason=v;});bindSceneField('scene-evidence',(s,v)=>{s.decision||={};s.decision.evidence=lines(v);});bindSceneField('scene-chin-reviewed',(s,v)=>s.chin_reviewed=v);
    $('add-keyframe').onclick=()=>{const s=selectedScene();if(!s)return;const time=Math.round(clamp(state.time-s.start,0,s.end-s.start)*100)/100,values=keyframeAt(s,time);mutate(()=>{s.keyframes||=[];const existing=s.keyframes.find(k=>Math.abs(k.time-time)<.005);if(existing)Object.assign(existing,{time,...values});else s.keyframes.push({time,...values});s.keyframes.sort((a,b)=>a.time-b.time);},false);renderKeyframes();};
    $('add-overlay').onclick=action(addOverlay);
    $('choose-scene-evidence').onclick=()=>evidenceDialog('scene-evidence');$('choose-identity-evidence').onclick=()=>evidenceDialog('identity-evidence');
    $('save-identity').onclick=action(async()=>{const observations=$('identity-observations').value.trim(),evidence=lines($('identity-evidence').value);if(!observations||!evidence.length)throw new Error('Registra observaciones reales y al menos una evidencia de la referencia.');mutate(p=>p.reference_review={...p.reference_review,identity_observations:observations,evidence});await saveProject();toast('Observaciones de identidad guardadas.');});
    $('read-manual').onclick=action(manualDialog);
    $('add-transcript').onclick=()=>{if(!state.project)return;mutate(p=>p.transcript.segments.push({start:state.time,end:Math.min(duration()||10,state.time+2),text:''}),false);renderTranscript();};
    $('edit-words').onclick=wordsDialog;
    $('analyze-source').onclick=action(()=>runJob('analyze',{transcribe:true,model:$('asr-model').value,language:'es'},'Analizando voz y video…'));
    $('automate-project').onclick=action(()=>runJob('automate',{transcribe:true,model:$('asr-model').value,language:'es'},'Analizando narración y preparando storyboard…'));
    $('plan-project').onclick=action(async()=>{await saveProject();setProject(await api(`/api/projects/${state.project.id}/plan`,{method:'POST',body:{}}));toast('Storyboard borrador creado. Revisa escenas y selecciona recursos.');});
    $('render-project').onclick=renderDialog;
    $('validate-project').onclick=action(validateProject);$('review-project').onclick=reviewDialog;$('open-settings').onclick=settingsDialog;$('tools-status').onclick=toolsDialog;$('open-jobs').onclick=jobsDialog;
    $('agent-tasks').onclick=action(tasksDialog);$('agent-workflow').onclick=action(async()=>{await saveProject();await api('/api/workflows',{method:'POST',body:{project_id:state.project.id}});await tasksDialog();});
    source.onloadedmetadata=()=>{sourceReady=true;source.currentTime=Math.min(state.time,source.duration||0);renderTimeline();updateTimecode();drawPreview();};source.onseeked=drawPreview;source.onended=()=>{pause();state.time=duration();updateTimecode();};source.onerror=()=>{if(source.src)toast('El navegador no puede previsualizar este códec. El motor puede analizarlo y convertirlo al render H.264.',true);};
    broll.onseeked=drawPreview;presenter.onseeked=drawPreview;presenter.onloadedmetadata=()=>{preparePresenter(currentScene(),true);drawPreview();};transition.onseeked=drawPreview;$('render-video').onplay=()=>{state.playing=true;updatePlayButton();};$('render-video').onpause=()=>{state.playing=false;updatePlayButton();};$('render-video').ontimeupdate=()=>{if(state.mode==='render'){state.time=$('render-video').currentTime;updateTimecode();updatePlayhead();}};
    document.addEventListener('keydown',event=>{
      if(event.target.closest('input,textarea,select')||$('modal').open)return;
      if(!canEdit()&&(['Delete','Backspace'].includes(event.key)||event.key.toLowerCase()==='s'||(event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z')){event.preventDefault();return;}
      if(event.code==='Space'){event.preventDefault();action(()=>state.playing?pause():play())(event);}
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?redo():undo();}
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();action(saveProject)(event);}
      if(event.key.toLowerCase()==='s'&&!event.ctrlKey&&!event.metaKey)action(splitScene)(event);
      if(['Delete','Backspace'].includes(event.key)&&selectedScene()){event.preventDefault();removeScene();}
      if(event.key==='ArrowRight'){event.preventDefault();seekTime(state.time+1/num(state.project?.settings.fps,30));}
      if(event.key==='ArrowLeft'){event.preventDefault();seekTime(state.time-1/num(state.project?.settings.fps,30));}
    });
    window.addEventListener('beforeunload',event=>{if(state.dirty){event.preventDefault();event.returnValue='';}});
    new ResizeObserver(()=>{renderTimeline();}).observe($('timeline-scroll'));
  }

  async function initialize() {
    if(!await initializeIdentity())return;const scope=identityScope();bindEvents();renderProject();requestAnimationFrame(frame);
    const results=await Promise.allSettled([api('/api/status'),refreshProjects(),refreshAssets(),api('/api/templates'),refreshFontLibrary(),api('/api/text-presets')]);
    if(!identityCurrent(scope)||SaaS&&!identity)return;
    if(results[0].status==='fulfilled'){state.status=results[0].value;$('connection-label').textContent='Motor local';$('connection-label').parentElement.querySelector('.status-dot').classList.remove('error');}else{$('connection-label').textContent='Sin conexión';$('connection-label').parentElement.querySelector('.status-dot').classList.add('error');toast('No se pudo conectar al motor local. Inicia el servidor de Ascendia Studio.',true);}
    if(results[3].status==='fulfilled'){state.templates=results[3].value.templates||[];renderTemplates();}
    if(results[4].status==='fulfilled')state.fontLibrary=results[4].value;
    if(results[5].status==='fulfilled')state.textPresets=results[5].value;
    for(const r of results.slice(1))if(r.status==='rejected')console.warn(r.reason.message);
    let previous=null;try{previous=localStorage.getItem(preferenceKey());}catch(_){}
    const requested=new URLSearchParams(location.search).get('project'),chosen=state.projects.find(p=>p.id===requested)||state.projects.find(p=>p.id===previous)||state.projects[0];if(chosen&&!state.project&&state.loadEpoch===0)try{await loadProject(chosen.id);}catch(e){toast(e.message,true);}
    if(!SaaS)try{const fonts=await Promise.all([document.fonts.load('36px Sequel'),document.fonts.load('italic 36px Scholar')]);state.fontsLoaded=fonts.every(f=>f.length>0);if(!state.fontsLoaded)toast('Faltan las fuentes obligatorias para la previsualización.',true);drawPreview();}catch(_){toast('El motor no ha servido las fuentes obligatorias. No se sustituyen silenciosamente en el render.',true);}
    if(!identityCurrent(scope)||SaaS&&!identity)return;await pollJobs();if(identityCurrent(scope))jobPollTimer=setInterval(pollJobs,2500);
  }
  initialize().catch(error=>toast(error.message,true,12000));
})();
