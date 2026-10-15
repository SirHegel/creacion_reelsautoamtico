# Ejecución por agentes

El editor expone un DAG de cinco roles mediante API, CLI y MCP. Un cliente
Codex puede distribuir estos roles usando sus agentes disponibles. Crear el
DAG no ejecuta modelos ni demuestra que hubo una revisión; cada tarea necesita
lease, observaciones y archivos de evidencia reales.

Desde SOFTWARE:

```bash
python3 -B -m studio workflow ID_PROYECTO
python3 -B -m studio claim director --agent codex-director
python3 -B -m studio complete ID_TAREA --lease LEASE --result projects/ID_PROYECTO/agents/director_result.json
```

Director lee manual completo, observa YO y CLONE, escucha/comprende crudo y propone
storyboard. Recursos depende de director y observa candidatos. Motion depende
de ambos y utiliza exclusivamente CLONE para motion y YO para cámara/subtítulos/
split; especifica acciones conectadas. Audio depende de director y prepara
mezcla/risers. QA depende de recursos/motion/audio y revisa el candidato real.
Audio y recursos pueden trabajar en paralelo tras dirección. Cada rol escribe
solo su artefacto dentro de projects/ID/agents y conserva evidencia referenciada.
El director integra resultados mediante project_update con la revisión vigente.

Ejemplo de resultado (rellenar con hechos y archivos existentes):

```json
{"observations":"Qué se revisó y qué se encontró, con tiempos", "evidence":["projects/ID/agents/evidencia.jpg"], "proposed_changes":[]}
```

Cambiar manual, fuentes, medio o edición invalida tareas anteriores: ejecutar
workflow de nuevo. No aprobar por names/logos ni por solo métricas. Las tareas
QA no activan la aprobación: review exige ocho comprobaciones, revisor y notas
asociados a bytes del MP4 y proyecto vigentes.

En multiservicio todos parten del perfil `profiles/ivan_base.json`, con recursos y
branding propios. El cliente se autentica en `/mcp` con su credencial revocable.
`ivan_prepare` prepara voz alineada, mediciones y contexto sin API; el director
externo redacta el plan y usa `ivan_apply_plan` para aplicarlo explícitamente.
La alternativa `ivan_automate` usa la API propia confirmada. Ambos conservan
cronología editable, procedencia y preview técnico; QA no se autoaprueba.
Los encargos particulares B_V2/r26 permanecen en IVAN y no gobiernan las
cuentas ni heredan recursos o aprobaciones al software.

Para un proyecto `mode:scene_ir_component`, workflow_create crea los mismos
cinco roles con objetivos de componente: semántica declarada, gráficos originales,
motion, audio conservado y QC. Recursos excluye stock/b-roll/video; el render se
normaliza a la duración actual de la escena (máximo10s) y technical=true. No
requiere revisión estática previa para ejecutar una prueba de biblioteca y nunca
habilita aprobación de reel. Las ediciones mantienen protegido el origen JSON.
Usar scene_ir_preview antes de scene_ir_apply con expected_revision. El adaptador
no reconstruye familias CLONE ni ejecuta un LLM interno; un agente externo aporta
SceneIR explícito y conserva la evidencia de selección y fidelidad pendiente.

`python3 -B -m studio skills ID --prepare` prepara un registro pendiente.
`skills_inventory` / `skills_prepare` exponen lo mismo por MCP; GET/POST
`/api/projects/ID/skills` por HTTP. Cada entrada requiere lectura por el agente,
revisor, decisión concreta y archivos propios de evidencia con SHA, además de
referencias vigentes y consulta del catálogo en inglés. Completarlo por
project_update con revisión optimista; no marcar como usado lo solamente leído.

`python3 -B -m studio render ID --seconds 10 --technical` exporta una prueba del
motor local sin acreditar ASCENDIA. `preview_render` acepta `technical:true`.
El recibo conserva `mode:technical_library`, y no se puede aprobar ni autorizar
un completo. La validación narrativa exige recibo vigente del adaptador, diseño aprobado y
evidencias completas; disponibilidad técnica no autoriza una promoción. Código, guías y manual nuevos invalidan nuevas promociones;
no reescribir auditorías históricas para aparentar aplicación retroactiva.

Para usar MCP local, lanzar `python3 -B -m studio mcp` con cwd SOFTWARE. Su
stdio usa JSON-RPC por línea. `tools/list` describe las herramientas. Este
comando no instala ni altera configuración global de Codex. Configurar un
cliente requiere apuntarlo al intérprete, módulo y cwd de esta carpeta.

`media_tools` expone las once operaciones y sus estados reales. Para un derivado
de persona, `media_process` acepta `operation:remove_background_video`,
`asset_id`, `options` numéricos y `project_id` opcional; el ejemplo local está
en [persona_cpu.json](persona_cpu.json). Consultar el job, registrar qué se
revisó y conservar el original. Para cancelar, usar la interfaz o
`POST /api/jobs/ID/cancel` en un punto seguro.
Un resultado sin asociación por conflicto de revisión permanece en biblioteca;
el director decide después cómo incorporarlo. Esta herramienta no autoriza
cambiar el fondo original de un reel ASCENDIA ni aprueba un montaje.

Para letras, consultar `font_library` y `text_presets`, seleccionar la cara real
y adjuntarla mediante `asset_attach`. `text_layout` mide el borrador sin guardar.
Motion aporta `text_style`/`text_animation` en datos cerrados, mantiene el reloj
al cortar y comprueba glifos/contraste/desbordamientos. QA examina la secuencia
renderizada y los bytes/licencias del editable. `job_get` permite reanudar la
observación del trabajo; `job_cancel` cancela solo ese job del software.
Ejemplo de contrato: [tipografia_local.json](tipografia_local.json).
