# API local y automatización

Servidor `http://127.0.0.1:8765`. Todas las respuestas de acciones son JSON;
errores contienen `error` y, cuando procede, `details`. El navegador, CLI y MCP
comparten el mismo almacén canónico. Nunca exponen `.estado` como archivos.

| Método y ruta | Uso |
|---|---|
| GET `/api/status` | Capacidades disponibles/ausentes, límites, huellas y actividad externa observable |
| GET `/api/manual` | Documentos canónicos completos de IVAN, en solo lectura |
| GET `/api/templates` | Plantillas conceptuales implementadas y fases |
| GET `/api/font-library` | Fuentes locales, variantes reales, SHA y avisos; sin sustituir fuentes |
| GET `/api/text-presets` | Estilos, límites y presets tipográficos originales |
| GET `/api/typography-client.js` | Evaluador de preview confiable, servido localmente |
| POST `/api/text-layout` | Medición de un borrador, sin guardar ni aprobar; JSON máximo32KiB |
| GET `/api/assets` | Biblioteca con hashes, miniaturas, waveform y verificación |
| POST `/api/assets` | Upload RAW; `X-File-Name` codificado URL, `X-Asset-Kind` opcional |
| GET `/api/media/ID` | Medio con HTTP Range/HEAD para playback y scrub |
| GET `/api/projects` | Proyectos ordenados por última escritura |
| POST `/api/projects` | `{name,source?,drive_id?}`; reutiliza fuente idéntica |
| GET `/api/projects/ID` | Editable completo con revisión |
| PUT `/api/projects/ID` | Editable completo con `revision` vigente; conflicto = 409 |
| POST `/api/projects/ID/assets` | `{asset_id,source?}` asocia medio; cambiar crudo invalida edición/análisis |
| POST `/api/projects/ID/analyze` | `{transcribe:false,model:"tiny",language:"es"}`; ASR opt-in |
| POST `/api/projects/ID/automate` | Analizar y proponer storyboard; no aprobar ni renderizar por inercia |
| POST `/api/projects/ID/plan` | Borrador de storyboard desde transcripción real |
| GET `/api/projects/ID/validate?strict=true` | Errores, advertencias y métricas de presencia/cobertura |
| POST `/api/projects/ID/render` | `{seconds:10,technical:true,engine:"hyperframes"}`; engine debe coincidir con ajustes guardados; `technical:false` exige todos los requisitos ASCENDIA |
| GET/POST `/api/projects/ID/tracking` | Consultar mediciones / encolar MediaPipe CPU con opciones; sin cambiar escenas |
| GET `/api/projects/ID/tracking_proposals` | Verificar medidas y convertir a crop/split actual; propuestas de foco/barbilla pendientes |
| GET `/api/projects/ID/designs` | Capturas, revisiones protegidas y requisitos de diseño pendientes |
| POST `/api/projects/ID/design_snapshot` | `{scene_id}` captura diseño base sin animación; devuelve job |
| POST `/api/projects/ID/design_review` | Observaciones o aprobación explícita con SHA de captura y referencia; nunca automática |
| POST `/api/projects/ID/manual` | `{read_complete:true}` actualiza huellas tras leer; invalida revisión |
| POST `/api/projects/ID/review` | Checklist explícito, revisor y notas ligado al render vigente |
| POST `/api/projects/ID/authorize` | `{authorized:true,notes}`; nueva indicación después de prueba aprobada |
| POST `/api/projects/ID/export` | ZIP portable de proyecto y medios; no publica en Drive |
| GET `/api/projects/ID/skills` | Inventario de doce guías, registro del proyecto y errores de aplicación |
| POST `/api/projects/ID/skills` | `{}` crea plantilla pendiente; conserva el registro existente |
| POST `/api/bundles` | ZIP RAW editable; valida rutas/hashes, reutiliza fuente, reabre sin inventar aprobación |
| GET `/api/media-tools` | Once operaciones locales, parámetros, disponibilidad y motivos pendientes |
| POST `/api/assets/ID/process` | `{operation,options,project_id?}`; derivado o medición en cola |
| POST `/api/backups` | `{project}`; respaldo de cambios locales pendiente, sin sobrescribir el proyecto |
| GET `/api/jobs` y `/api/jobs/ID` | Progreso, estado, resultado y error persistidos |
| POST `/api/jobs/ID/cancel` | Cancelación en punto seguro; no interrumpe otros procesos |
| POST `/api/workflows` | `{project_id}` crea cinco roles dependientes |
| GET `/api/tasks` | Tareas, estados y artefactos asignados |
| POST `/api/tasks/claim` | `{role,agent}` reclama tarea disponible y devuelve lease |
| POST `/api/tasks/ID/complete` | `{lease,result:{observations,evidence}}` valida resultado vigente |
| POST `/api/tasks/ID/release` | `{lease}` libera una tarea abandonada para reanudar |
| GET `/api/files/RUTA` | Entregables permitidos en assets/projects/exports; rutas confinadas |

No hay endpoint shell, borrado de originales ni publicación remota. El Host y
Origin deben pertenecer al mismo servidor loopback. Uploads, opciones FFmpeg,
mensajes MCP y rutas se validan; solo se admite un Range de bytes por petición.

## Escena editable

```json
{
  "id":"scene_01", "start":0, "end":1.5, "type":"split",
  "template":"kinetic", "title":"Frase diseñada desde la narración",
  "emphasis":"contraste editorial", "font":"primary", "text_color":"#ffffff",
  "source_in":0, "asset_id":"ID_BROLL", "broll_in":1.2,
  "chin_y":0.65, "chin_reviewed":false,
  "effects":{"brightness":0,"contrast":1,"saturation":1},
  "keyframes":[{"time":0,"x":0,"y":0,"scale":1,"opacity":1}],
  "decision":{"search":"Bibliotecas y candidatos realmente vistos", "reason":"Relación con la frase", "evidence":["assets/images/evidencia.jpg"]}
}
```

`source_in` en split corresponde al crudo; `broll_in`, al recurso superior.
En b-roll completo, `source_in` corresponde al recurso. `chin_y` se mide en la
región del presentador, no en pantalla completa. Brillo es offset [-1,1], neutral
0; contraste/saturación son factores neutral1. Keyframes usan segundos locales,
offsets normalizados [-1,1], escala[.25,3] y opacidad[0,1]. El motor conserva la
voz del crudo a sus tiempos originales, sin reconstruir narración.

Burn Screen real usa `transition_asset_id`, `transition_duration`[.3,1] y
`transition_source_in`. Contador requiere `motion.value` suministrado por el
guion; workflow usa tres `nodes`, comparación dos `motion.labels` y tipografía
cinética `title`/`emphasis`. Estas plantillas muestran conceptos; no ejecutan
funciones de marcas reales ni fabrican resultados.

## Capas independientes y vistas previas

Cada escena puede incluir hasta ocho `overlays`, en orden de fondo a frente:

```json
{"id":"layer_01","asset_id":"ID_IMAGEN_O_VIDEO","start":0,"end":1.5,
 "source_in":0,"x":0.1,"y":0.2,"width":0.5,"height":0.3,
 "opacity":0.85,"blend":"normal",
 "keyframes":[{"time":0,"x":0,"y":0,"scale":1,"opacity":1}],
 "decision":{"search":"Búsqueda real","reason":"Qué explica","evidence":["assets/images/evidencia.jpg"]}}
```

`start/end` son segundos locales de la escena. `x/y` indican su esquina
superior izquierda y `width/height`, su caja en fracciones de pantalla.
Los offsets de keyframe son fracciones de pantalla; la escala se aplica desde
el centro de la capa. Su opacidad multiplica la opacidad base. `blend` admite
`normal` y `screen`. Imágenes estáticas usan `source_in:0`; video usa segundos
de su propio archivo. Contain conserva proporciones y transparencia; el audio
de un overlay no se incorpora automáticamente a la mezcla.

El catálogo devuelve `preview_url`, `preview_is_derivative` y procedencia
cuando se preparó un proxy del navegador. Identidad, hash, ruta y probe del
original siguen intactos. Reabrir un ZIP regenera estas vistas cuando hace
falta y conserva los recursos originales.

La auditoría del MP4 registra LUFS integrados, pico real dBTP y LRA. Silencio
devuelve valores nulos; no representa una escucha. El motor rechaza subtítulos
que no caben bajo la barbilla transformada dentro de la zona segura.

## Revisión y MCP

Review requiere `visual`, `audio`, `sync`, `spelling`, `resources`, `movement`,
`identity`, `safe_zones`, `reviewer`, `notes`, `approve_preview`. Marcar audio
significa que el revisor escuchó; el motor no lo marca automáticamente. La
aprobación conserva un único `approved_preview.mp4`; candidatos nuevos no lo
sobrescriben. Cambios de bytes, fuentes, montaje o manual invalidan autorización.
El digest incluye también código real del motor y registro de skills. El recibo
`mode:technical_library` admite observaciones, pero rechaza `approve_preview:true`
y no autoriza render completo. La vía narrativa requiere CLONE exclusivo,
evidencias de YO/CLONE, skills vigentes y HyperFrames/GSAP verificado: ese
adaptador registra pruebas reales y comprueba sus hashes. No se habilita con
campos de proyecto ni sustituye la comparación visual.

`policy.technical_preview_seconds:3` es metadata histórica de la prueba de
arquitectura del padre. Su estado vigente es `parent_architecture` ya comprobada:
no solicita repetirla ni limita el exportado técnico propio a tres segundos.
La fase actual se expresa mediante `current_production_phase` y
`design_before_animation`; el editor permite hasta diez segundos de prueba
técnica independiente.

`approval_current` se calcula al leer el proyecto y se ignora en sus escrituras.
Comprueba aprobación, manual/código/skills vigentes, bytes del candidato y del
exportado aprobado, además de los requisitos de producción. Un badge del
navegador no sustituye ese control. Toda nueva exportación o revisión revoca
la autorización de completo; se exige nuevamente al encolar y antes de ejecutar.

La interfaz envía a `/manual` el mapa `expected_fingerprints` de nombres a
SHA-256 de los documentos que mostró. Si cambiaron, responde 409 y exige
releer. Las fuentes exportables deben permanecer en `assets/fonts`.

MCP stdio: `python3 -B -m studio mcp`, cwd SOFTWARE. JSON-RPC2.0 por línea;
`initialize`, `tools/list`, `tools/call` y `ping`. Herramientas incluyen el mismo
núcleo de proyectos, medios, validación, render de prueba y tareas. Salida stdout
contiene protocolo; no habilita comandos arbitrarios. No configura clientes ni
modifica la instalación de Codex global.

## Composición libre

```json
{"id":"motion_01","type":"motion","template":"custom","start":0,"end":2,
 "motion_design":{"canvas":{"background":"#101318"},"elements":[
   {"id":"titulo","type":"text","text":"Acción conectada","font":"primary",
    "font_size":84,"color":"#ffffff","x":0.1,"y":0.2,"width":0.8,"height":0.2,
    "start":0,"end":2,"z":2,"opacity":1,"rotation":0,
    "mask":{"type":"inset"},
    "keyframes":[{"time":0,"mask_progress":0},
                 {"time":1,"mask_progress":1,"x":0.15,"ease":"power2.out"}]}]}}
```

Hasta 64 elementos `text`, `shape` o `media`. Medios requieren `asset_id` y
`source_in`; formas admiten `rect`/`ellipse`. Caja base en fracciones de lienzo,
tamaño tipográfico/radio en píxeles a ancho 1080. Keyframes locales con posición
absoluta `x/y` en [-2,2], escala [.01,8], rotación, opacidad y revelación de
máscara. No usan los offsets de las capas antiguas. Las curvas permitidas son
linear, power1.inOut, power2.out, power2.inOut y power3.out. `ease_window:[0,1]`
permite conservar una porción de curva al cortar. `path.points` admite 2–64
puntos; su velocidad se mide en píxeles físicos y `orient` debe ser false.
Máscaras: `none`, `circle` o `inset` con top/right/bottom/left normalizados;
`mask_progress` requiere circle/inset. Datos HTML/JS arbitrarios no se ejecutan.

El motor HyperFrames produce HTML editable, timeline GSAP pausada, check real,
keyframes, capturas de navegador y MP4. Los recursos de presenter/split/b-roll
y plantillas antiguas que pasan por raster quedan identificados como tales.
Los recibos guardan comandos, versiones y SHA de código/runtime/evidencia.
El ZIP principal incluye `hyperframes_editable.zip` cuando el último render
HyperFrames mantiene su digest y pruebas vigentes. Ese paquete contiene HTML,
subcomposiciones, medios, fuentes y runtime con sus licencias separadas; audio
permanece en el proyecto principal. Reabrir recupera datos, remapea medios y
reinicia aprobaciones; nunca ejecuta HTML importado. El empaquetado comprueba
CRC, SHA y entradas estables antes de reemplazar el editable anterior.

## Diseños y medidas faciales

La captura estática ignora tiempos, keyframes y trayectorias; conserva el diseño
base. Animarlo no cambia su huella base; cambiar texto, geometría, fuente, color
o medio sí. Manual o código nuevos exigen captura y revisión nuevas. Las
escrituras normales y los ZIP no pueden inyectar evidencia ni aprobaciones.

Revisión de diseño:

```json
{"scene_id":"motion_01","expected_sha256":"SHA_CAPTURA_VISTA",
 "reviewer":"Nombre","notes":"Observaciones concretas","approve_design":false}
```

Aprobar requiere además `approval_text` con la indicación explícita,
`reference_asset_id` de una imagen importada, `reference_name`, `reference_time`
y `checks:{composition:true,typography:true,spacing:true,color:true,depth:true}`.
La promoción ASCENDIA exige referencia CLONE vigente en 3.10 s. Guarda un PNG
aprobado y conserva sus bytes si falla el commit. Comentarios o ensayos técnicos
no autorizan el componente paralelo del cliente.

Tracking acepta start/end, sample_fps [.5,10], min_confidence [.3,.99],
smoothing [.05,1], minimum_coverage [.5,1] y max_samples [1,600]. Hasta 120 s
por análisis CPU. Reporta PTS reales, detector_score, 468/478 landmarks,
barbilla estimada, cobertura, huecos, JPG y hashes. No interpola rostros ausentes
ni aplica automáticamente coordenadas originales al crop/split. Audio y
revisión editorial permanecen pendientes.

`tracking_proposals` verifica recibo privado, report/JPG, fuente canónica,
modelo y código. Recalcula cada escena según su source_in y geometría actual,
sin ejecutar FFmpeg. Para SAR1 y rotación ortogonal propone foco constante,
barbilla máxima observada y muestras transformadas en la región real. Huecos,
varias personas, rostro recortado o geometría incierta bloquean la propuesta.
No cambia `chin_reviewed` ni crea seguimiento continuo entre muestras.

MCP dispone de 45 herramientas en la versión0.5; `tools/list` devuelve el catálogo actual. CLI adicional: `tracking-proposals ID`.
Si cambia el código mientras está abierto el servidor, nuevos trabajos
responden409 y requieren reinicio; una tarea en cola tampoco ejecuta código
importado anterior bajo huellas nuevas. `status.restart_required` lo indica.


## SceneIR: componente técnico desde datos

`GET /api/scene-ir/schema` devuelve el esquema JSON cerrado.
`POST /api/projects/ID/scene_ir_preview` acepta exclusivamente `{"document":IR}`
y devuelve `project`, `validation`, `warnings`, `can_apply`; no guarda archivos.
Una compilación válida puede aplicarse aunque `validation.errors` señale manual
pendiente u otro impedimento técnico de render. Un IR inválido devuelve400.
`POST /api/projects/ID/scene_ir` requiere también `expected_revision` entero;
conflicto devuelve409 y conserva la cronología vigente.

```json
{"schema":"ascendia.sceneir/1","content":{"text":"{{subject}} se desplaza"},
 "narrative_goal":"Representación conceptual declarada de un traslado",
 "family":"authored_transfer","representation":"conceptual","duration":2,
 "composition":{"background":"#102030"},"parameters":{"subject":"DATO"},
 "components":[{"id":"block","type":"shape","shape":"rect","color":"#607080",
   "x":0.1,"y":0.4,"width":0.2,"height":0.1}],
 "actions":[{"target_id":"block","time":0,"properties":{"x":0.1}},
   {"target_id":"block","time":2,"properties":{"x":0.6},"ease":"power2.out"}]}
```

La copia compilada reemplaza timeline por una escena motion/custom, conserva
fuente/audio/transcripción/fuentes y revoca revisiones/aprobaciones activas.
`mode:scene_ir_component` y `scene_ir` son origen protegido: project_update no
puede inventarlos, modificarlos ni eliminarlos. Geometría, textos, curvas y
duración actual siguen editables. El registro conserva el JSON original y SHA,
con `semantic_origin:author_declared`, QC pendiente y fidelidad no revisada.
Los medios visuales permitidos son imágenes adjuntas canónicas declaradas como
`metadata.declaration_original:{kind:original_graphic,author:...}`; no footage,
stock ni crudo/derivados del presentador. Declarar autor no verifica derechos.

Los parámetros se sustituyen una vez, como texto literal, en content.text y
components[].text; nunca en IDs, rutas, CSS, números ni código. Una `family`
declarada no demuestra reconstrucción CLONE. No hay generador semántico interno.
El render de componentes fuerza technical=true y usa el mínimo entre duración
solicitada y escena actual, máximo10s. No exige aprobación estática por cada
prueba de biblioteca; conserva QC pendiente y bloquea aprobación de reel.
Los ZIP conservan ese modo y remapean IDs/SHA del documento; revisiones y
tracking importados se descartan como autoridad. El HTML/GSAP anidado se trata
como archivo de datos y no se ejecuta al reabrir.

CLI: `scene-ir-schema`, `scene-ir-preview ID ARCHIVO_JSON`,
`scene-ir-apply ID ARCHIVO_JSON --expected-revision N`.
MCP: `scene_ir_schema`, `scene_ir_preview`, `scene_ir_apply`.
Workflow específico: [scene_ir_component.json](../workflows/scene_ir_component.json).

Declarar una imagen propia al importarla: CLI `import RUTA --kind image --original-graphic-author "AUTOR"`; MCP asset_import admite `original_graphic_author`. La declaración se registra en el catálogo del primer importado y nunca equivale a verificar derechos. La deduplicación conserva la metadata de un recurso ya registrado.

## Segmentación de personas CPU — v0.3

`GET /api/status` expone `capabilities.segmentation`; el catálogo incorpora
`remove_background_video` con `available`, `unavailable_reason` y `capability`.
`verified_execution` exige un recibo real cuyos bytes, evidencia, modelo,
runtime y código siguen vigentes. Instalar un modelo solo prueba disponibilidad.
La interfaz consulta el catálogo al abrir cada clip y muestra los estados pendientes.

```json
{"operation":"remove_background_video","project_id":"ID_PROYECTO",
 "options":{"start":0,"duration":5,"fps":15,"max_width":540,
 "max_height":960,"threshold":0.5,"softness":0.1,"feather":2,
 "temporal_smoothing":0}}
```

Enviar a `POST /api/assets/ID/process`. Responde 202 con el job; consultar
`GET /api/jobs/ID`. Los parámetros son números JSON finitos, nunca booleanos,
texto numérico ni claves desconocidas. `duration:null` procesa el resto solo
si cabe en los límites: no trunca silenciosamente un video largo.

| Parámetro | Rango | Valor inicial |
|---|---|---|
| `start` | 0–86400 s; dentro del video | 0 |
| `duration` | 0,01–30 s, o null | null |
| `fps` | Entero 10–30 | 30 |
| `max_width`, `max_height` | Enteros pares 160–1080; sin ampliar la fuente | 540, 960 |
| `threshold` | 0,05–0,95 | 0,5 |
| `softness` | 0,01–1 | 0,1 |
| `feather` | 0–8 px | 0 |
| `temporal_smoothing` | 0–0,8 | 0 |

Se rechazan HDR PQ/HLG, más de 900 frames, más de 2 GiB de RGBA procesado
y espacio de disco insuficiente. La duración de video se redondea a frames
CFR; un tramo de 0,01 s genera al menos un frame, con duración codificada
de 1/fps. El recibo conserva las dos duraciones y los PTS medidos.

El resultado es MOV QTRLE/ARGB con alfa y, si existe, la primera pista de audio
original decodificada a PCM16 a 48 kHz sin normalización. El proxy web es VP9 alfa.
Cada resultado conserva fuente, SHA, parámetros, modelo, código y muestras
fuente/máscara/composición/decodificación. Son comprobaciones técnicas;
`visual_reviewed`, `audio_listened` y `approved_for_ascendia` permanecen falsos.
El algoritmo ofrece confianza de persona, no matting físico del cabello ni
selección de identidad entre varias personas.

El job captura revisión, código y huella del motor al encolar. Un cambio de
modelo/código antes de ejecutar lo rechaza. Durante ejecución comprueba
cancelación, fuente y runtime antes de promover. Si cambia el proyecto,
`result.project_attachment.attached:false` y `reason:project_changed` indican
que el derivado quedó únicamente en biblioteca. Nunca reemplaza crudo ni escenas.
La caché comprueba recibo, evidencia y bytes antes de reutilizar; la asociación
canónica reutiliza el medio por SHA en vez de conservar otra copia privada.

Para narrativa ASCENDIA, una fuente conocida como segmentada o chroma key,
incluidas sus derivaciones declaradas, incumple el fondo auténtico. Tampoco se
admite un derivado del propio crudo como b-roll/overlay del mismo proyecto.
La inspección técnica independiente permanece disponible.

## Fuentes y letras animadas — v0.4

La carga RAW existente admite `X-Asset-Kind:font`, TTF/OTF individuales de hasta
16MiB. Valida SFNT, tablas, Unicode y decodificación real antes de registrar;
deduplica por SHA y conserva la variante del archivo. No acepta WOFF/TTC ni
instala fuentes en el sistema. La biblioteca distingue permisos aportados por
el usuario de las seis variantes OFL comprobadas contra sus fuentes públicas.

`POST /api/text-layout` requiere exactamente:

```json
{"project_id":"ID_PROYECTO","element":{"id":"titulo","type":"text",
 "text":"Árbol y acción","font":"primary","font_asset_id":"ID_FUENTE",
 "font_size":84,"x":0.1,"y":0.2,"width":0.8,"height":0.4,
 "text_style":{"align":"center","line_height":1.2,"letter_spacing":2,
   "stroke":{"width":1,"color":"#000000"},
   "shadow":{"enabled":true,"x":2,"y":4,"blur":2,"color":"#000000","opacity":0.85}},
 "text_animation":{"preset":"typewriter","duration":0.6,"exit":"fade","exit_duration":0.2}},
 "scene_duration":4,"width":540,"height":960}
```

Responde `layout`, `font:{family,style,sha256}`, `project_revision`,
`persisted:false`, `approved:false`. La medición puede consultar una fuente de
biblioteca aún no adjunta para previsualizar; guardado y render exigen adjuntarla.
Los objetos de estilo/animación son cerrados, con números finitos y booleanos
estrictos. El esquema SceneIR publica el mismo contrato.

`clock_start`, `clock_offset` y `clock_duration` preservan la fase tras un corte;
la duración original no se recalcula con cada fragmento. El diseño estático
ignora el preset/tiempo pero incorpora estilo y bytes reales de la fuente.
El receipt HyperFrames incorpora runtime de layout, fuente, aviso y manifiesto;
su editable anidado comprueba cobertura de SHA antes de empaquetar.

CLI: `font-library`, `text-presets`, `text-layout ID ELEMENTO_JSON --duration 4`,
`job ID`, `cancel-job ID`. MCP: `font_library`, `text_presets`, `text_layout`,
`job_get`, `job_cancel`. La cancelación usa el worker del servidor propio cuando
está disponible; no envía señales a otras terminales.
Especificaciones y límites: [TIPOGRAFIA.md](TIPOGRAFIA.md).

CLI usa `process ID remove_background_video --options workflows/persona_cpu.json`;
MCP usa `media_process` con los mismos argumentos. No se añade un shell ni un
servicio remoto. El ejemplo procesa cinco segundos y debe ajustarse al medio.

## Multiservicio privado — v0.5

`./iniciar_multiservice.sh` inicia el gateway local en8776 y `/portal`.
Registro/login usan `POST /api/auth/register` y `POST /api/auth/login`, JSON y
Origin del portal. `GET /api/auth/me` devuelve identidad, workspace y CSRF;
la cookie de sesión es HttpOnly. Las mutaciones de navegador requieren
`X-CSRF-Token` y `X-Workspace-ID`. Toda URL de proyecto/medio queda bajo
`/w/<workspace>/api/...`; cambiar de cuenta invalida la pestaña anterior.
Los backends son procesos con root inmutable, autenticados por el gateway y
sin shell público. Todos comparten el mismo bloqueo CPU dentro de SOFTWARE.

- `GET/PUT /api/branding`: configuración privada con `revision`, `name`,
  `colors:{background,text,accent,muted}`, `fonts:{primary,accent}` por assetID,
  `logo_asset_id`, `instructions` y `language`. No incluye aprobaciones.
- `POST /w/<workspace>/api/projects/<id>/branding`:
  `{expected_revision,expected_branding_revision}`. Ambas revisiones se comprueban;
  cambia el snapshot de ese proyecto e invalida su revisión editorial.
- `GET /api/providers`: ocho adaptadores, modelo/hint y última prueba de la cuenta.
  `PUT /api/providers/<id>`: `{api_key,model,label?}`; la clave se cifra localmente.
  `POST /api/providers/<id>/test`: `{confirmed:true}`; ejecuta una llamada real
  que puede consumir tokens. `DELETE` elimina únicamente esa conexión.
- `GET/POST /api/agent-tokens`: crear con `{name}`. El secreto aparece una vez;
  `DELETE /api/agent-tokens/<id>` lo revoca. No es la clave del proveedor de IA.
- `POST /mcp`: JSON-RPC HTTP con `Authorization: Bearer <credencial propia>`.
  Admite initialize, ping, tools/list y tools/call; las notificaciones responden202.
  El transporte es JSON sin SSE persistente. El agente no puede administrar
  cuentas, claves API ni credenciales de otros agentes.

Los ocho proveedores son OpenAI, Anthropic, Gemini, Mistral, Groq, xAI, DeepSeek
 y OpenRouter. Sus endpoints HTTPS están fijados: no hay URLs arbitrarias,
redirecciones, proxy del entorno ni comandos recibidos. El usuario aporta el
ID exacto de un modelo autorizado por su cuenta. La disponibilidad del
adaptador no acredita haber probado su API real.

### Dirección IVAN por API o agente externo

`POST .../projects/<id>/auto_ivan` recibe opciones cerradas:
`{provider,confirmed:true,instructions?,seconds?:10,language?:"es",
asr_model?:"tiny",plan_only?:false,max_tokens?:8192}`. Devuelve un job202.
ASR/tracking se ejecutan con CPU; dirección usa la API propia. El plan válido
se compila en escenas editables, conserva crudo/voz y encola una prueba técnica.

`POST .../projects/<id>/ivan_prepare` y MCP `ivan_prepare` reciben
`{seconds?,language?,asr_model?,instructions?}`; preparan transcripción,
mediciones y contexto para Codex/Claude, sin llamar a un proveedor ni modificar
la cronología. Consultar `job_get` hasta obtener preparation_id/context.

MCP `ivan_apply_plan` recibe `{project_id,preparation_id,expected_revision,
document,agent:{name,model?,notes?}}`; la ruta HTTP homónima recibe los mismos
campos excepto project_id. Comprueba preparación, revisión, archivos, perfil
 y recursos vigentes; rechaza hechos ajenos a la narración, continuidad facial
excesiva y diseños desconectados. La dirección externa se registra como
`external_agent_declared`, sin inventar inferencia interna ni uso de tokens.
El resultado devuelve preview_job_id; conservar y revisar el MP4 resultante.
La edición automática continúa pendiente de revisión editorial.

### Observación de biblioteca

MCP `resource_review_prepare` o `POST .../assets/<id>/review-prepare` preparan
muestras reales y opcionalmente un clip mudo, con start/duration, hasta12
muestras y30s. `resource_review_get` o `GET .../review` consulta integridad y
alcance. `resource_review_record` o `POST .../review` exige hashes fuente/recibo,
CAS de observación, contenido, notas y evidencia. Fotogramas observados son
puntos; una secuencia vista declara únicamente su intervalo. No certifica
licencias ni aprueba el reel. Las rutas review-files sirven solo medios
verificados; los recibos privados nunca se sirven.

### Configurar un cliente propio

El portal muestra la URL MCP y una credencial revocable. En la configuración
local del cliente Codex, usar una variable de entorno del usuario:

```toml
[mcp_servers.ascendia]
url = "http://127.0.0.1:8776/mcp"
bearer_token_env_var = "ASCENDIA_AGENT_TOKEN"
```

En un cliente que acepte JSON:

```json
{"mcpServers":{"ascendia":{"type":"http","url":"http://127.0.0.1:8776/mcp","headers":{"Authorization":"Bearer CREDENCIAL_PROPIA"}}}}
```

El software no escribe configuración global de Codex/Claude ni recoge su
login. Los contratos oficiales están en [Codex MCP](https://developers.openai.com/codex/mcp)
 y [Claude Code MCP](https://code.claude.com/docs/en/mcp). Para identidad o plan
ChatGPT hace falta registro oficial de cliente y consentimiento separado;
no está habilitado aquí ([guía](https://developers.openai.com/siwc/quickstart)).
La API de Claude usa Console; el login nativo sigue en la aplicación del
proveedor ([condiciones](https://code.claude.com/docs/en/legal-and-compliance)).

## Modos, colaboración y respaldo en0.6

El [procedimiento del reel completo](MODOS_COLABORACION_PIPELINE.md) describe
los contratos de Automático y Manual, las generaciones reanudables y los
permisos de proyectos compartidos. `pipeline_start/get/plan/resume/restart/cancel`
trabajan sobre el proyecto propio; `draft_render` exporta un borrador manual
completo de hasta600s. No constituyen aprobación editorial ni publicación.

Las rutas siguientes pertenecen al propietario y usan su namespace
`/w/ID_ESPACIO/api/`. Los tokens de agente conservan su espacio propio.

| Método y ruta | Resultado |
|---|---|
| `GET /cloud-storage` | Estado seguro de configuración administrativa; no revela claves, bucket ni endpoint. |
| `GET /projects/ID/cloud-backup` | Estado y recibo del outbox propio, con revisión de proyecto, integridad y ETag del manifiesto. |
| `POST /projects/ID/cloud-backup` | Job de captura y respaldo, solamente si el administrador conectó el almacenamiento. |

El cuerpo del respaldo es cerrado:

```json
{"expected_revision":7,"expected_outbox_revision":0,"expected_etag":null,"include_outputs":true}
```

`expected_revision` corresponde al proyecto, y `expected_outbox_revision` al
estado de respaldo consultado. Para reemplazar un head remoto existente,
usar su `manifest_etag` como `expected_etag`; no adivinarlo. El job captura
recursos, fuentes/avisos y exportados pertinentes, comprueba sus hashes y
usa CAS para actualizar el manifiesto. Un ETag no sustituye el SHA del contenido.
Consultar el job y el recibo: una solicitud202 todavía no es sincronización.
Un transporte de pruebas conserva `live_remote_execution_verified:false`.

Los equivalentes MCP son `cloud_storage_status`, `cloud_backup_get` y
`cloud_backup_start`. Este último acepta el ID del proyecto y los campos del
cuerpo, con ETag omitido para la primera copia. Ni HTTP ni MCP permiten
configurar las credenciales del almacenamiento. La configuración es una
operación local del administrador, documentada en [Nube](NUBE.md).

El respaldo remoto permanece desactivado en esta instalación. No hay servicio
de sincronización periódica ni restauración directa sobre proyectos: el
restore produce un staging verificado para revisión, conserva originales y
no hereda aprobación. Los colaboradores no pueden respaldar ni administrar
almacenamiento o conexiones del propietario.
