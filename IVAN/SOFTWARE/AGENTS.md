# Ascendia Studio — ámbito del software

Prioridad del usuario para el multiservicio: todos los usuarios parten del estilo
automatizado de IVAN (YO + CLONE), con branding, colores, fuentes, logo, recursos y
conexiones de IA propios. Construir registro/login y espacios privados; no intervenir
en la producción de IVAN. El perfil canónico adaptado del software está en
profiles/ivan_base.json, con reglas completas y huellas de sus fuentes; no contiene
credenciales, IDs de Drive, materiales privados ni aprobaciones de otro proyecto.
Las restricciones de B_V2 y de la muestra r26 pertenecen al encargo padre, no son el
brief de todas las cuentas. Los datos legacy conservan su historia. El runtime de cada
workspace se fija al arrancar un proceso separado; nunca cambiar ROOT por petición.
Todos los workers comparten el lock CPU dentro de SOFTWARE. No heredar claves ni
tokens del Codex/Claude que trabaja en IVAN; API keys propias cifradas por espacio y
tokens revocables de agentes son canales distintos. No ejecutar código arbitrario
de agentes públicos en el host del SaaS. La edición automática sigue generando una
prueba y evidencias pendientes de revisión; no fabricar aprobación editorial.
El paquete inicial usa fuentes OFL públicas con sus nombres reales como branding
explícito. Las referencias privadas Sequel/Scholar no se redistribuyen a las cuentas.
Hay dos recorridos: Automático y Manual. La autorización del usuario para el
software multiservicio permite generar borradores técnicos completos de hasta
600s por el pipeline explícito o con draft_full:true en el espacio SaaS. Esos
borradores conservan approved:false y production_conformant:false; no heredan
aprobación editorial, identidad de voz ni publicación. Los guards históricos de
los proyectos de operador y de los componentes SceneIR de hasta10s siguen vigentes.
La colaboración es por proyecto: viewer lee/exporta, editor guarda por CAS y
renderiza técnico, propietario administra fuente, biblioteca, marca, conexiones,
automatización y permisos. Consumir el cuerpo antes de admitir una mutación,
revalidar sesión/permiso y serializar con revocación usando el gate del proyecto.
El almacenamiento actual es local al servidor y declara remote:false. No fingir
sincronización remota ni identidad verificada de correo. Referencia operativa:
docs/MODOS_COLABORACION_PIPELINE.md y workflows/reel_multiservice.json.
El respaldo explícito requiere configuración administrativa propia de SOFTWARE;
derivar el propietario del proceso, capturar archivos completos y verificar cada
blob antes del head remoto con CAS. No aceptar claves por HTTP/MCP ni heredar
las de IVAN. Restore sólo staging, aprobación pendiente y sin aplicación sobre
proyectos. Un transporte simulado nunca acredita conexión o sincronización real.
Las menciones posteriores a la fase histórica B_V2 y a tipografías obligatorias
describen datos legacy; la personalización nueva debe quedar declarada y vinculada
al proyecto mediante snapshot del servidor, nunca una sustitución silenciosa.

Construir y escribir exclusivamente dentro de SOFTWARE. Temporales, caches,
modelos, configuración y logs dentro de SOFTWARE/.estado. Leer el manual
canónico de IVAN (../AGENTS.md, ../PROMPT_MAESTRO.md, ../INSTRUCCIONES.md y
../STYLE_YO.md) completo antes de dirigir una edición; no copiarlo ni modificar
sus proyectos, estado, recursos, configuración o terminal activa.

No ejecutar ../sistema/workflow.py ni ../sistema/preflight.py desde este editor:
sus escrituras pertenecen a la producción paralela. No heredar credenciales ni
publicar en Drive. Usar CPU con un worker serial y máximo dos threads FFmpeg;
CUDA/NVENC están deshabilitados para preservar el trabajo externo.

YO define cámara, subtítulos y split; CLONE es la única referencia de motion.
AGENT/EDIT se conservan únicamente como historia. ASCENDIA V5
requiere prueba inicial de diez segundos, split 55/45, fondo auténtico, máximo
tres segundos de rostro continuo, Sequel/Scholar, texto en b-roll y animaciones
con acción/reacción/transformación/salida. No usar Tella.

La arquitectura GSAP del padre ya está comprobada; no repetirla. La regla25
vigente pide mejorar B_V2 preservando montaje/componentes, quince familias y
CANCELLED, con B_V1 conservado para comparar; no nuevas demos A/B/C ni YO.
Los componentes técnicos del software conservan render/batch con QC pendiente.
Preservar el CANCELLED aprobado en su
proceso; no ejecutar aquí su reconstrucción ni alterar proyectos del padre.
Este software añade solo el adaptador SceneIR a motion editable con semántica
declarada, no un modelo generador ni certificación de fidelidad CLONE.
Validar visual, movimiento, ritmo y continuidad por separado. Los componentes
SceneIR son técnicos de hasta10s, QC pendiente y sin promoción a reel aprobado.
La promoción narrativa sigue exigiendo la prueba revisada y autorización; los
borradores técnicos completos nuevos usan el contrato multiservicio anterior.
El adaptador propio HyperFrames/GSAP requiere recibos actuales de ejecución,
check, capturas y MP4; su estado real se consulta en studio status. Las plantillas Pillow/FFmpeg
producen exportados técnicos propios, nunca equivalencia con CLONE ni aprobación
ASCENDIA. GSAP tiene licencia propia; no distribuirlo como código MIT.
Consultar las doce guías canónicas en ../.agents/skills por lectura, sin importar
ni ejecutar ../sistema/skills.py. Registrar comprensión, decisión, hashes de
árbol/referencias, catálogo y evidencia real por proyecto con studio skills.
Una plantilla pendiente o un inventario no acreditan aplicación. Las pruebas
sintéticas del software son independientes del componente CLONE y no lo aprueban.

Composición libre: datos cerrados en motion_design; ningún HTML/JS de proyecto
se ejecuta. El diseño base y sus PNG se revisan con design_snapshot/design_review,
sin forjar aprobaciones por project_update/ZIP. Cambios de manual/código/fuentes/
diseño/referencia invalidan promociones. Tracking MediaPipe conserva muestras y
hashes; coordenadas originales no equivalen a foco/barbilla en crop o split.
Propuestas geométricas siguen pendientes de revisión, nunca autoaplicadas.

Segmentación CPU: consultar media-tools y usar remove_background_video solo
como derivado técnico explícito. Revisar los bordes en movimiento; confianza de
persona no equivale a rotoscopia ni matting perfecto. Conservar audio, fuente y
procedencia; cancelar únicamente jobs propios. El resultado nunca reemplaza
automáticamente crudo/escenas. El fondo auténtico de ASCENDIA impide promover
como fuente narrativa un recorte/chroma conocido, incluso mediante proxies.

Tipografía: fuentes TTF/OTF individuales reales, máximo16MiB. Registrar SHA y
avisos de licencia; no atribuir permisos a metadata del usuario/importada ni
redistribuir Adobe Fonts. font_asset_id debe ser canónico y estar adjunto al
proyecto para guardar/renderizar. Sequel/Scholar siguen obligatorias en narrativa
ASCENDIA. No usar fallback de sistema ni falso bold/italic. Medir glifos reales,
avisar desbordamientos, mantener grafemas y reloj al cortar/dividir. Presets
tipográficos no prueban calidad CLONE ni aprueban el diseño por sí solos.

Los borradores y las coincidencias de texto no constituyen selección semántica.
Observar recursos y secuencias; registrar fuentes, tramos, motivos y evidencia.
No afirmar haber oído audio tras mirar niveles o ASR. La auditoría técnica no
aprueba el montaje. Revisar en movimiento y escuchar antes de registrar
aprobación. Promover un completo como aprobado requiere autorización explícita
posterior a la prueba; producir un borrador técnico del SaaS no lo promueve.

Para delegar: crear workflow, reclamar tarea por rol y entregar observaciones
con evidencias en el artifact asignado. No editar simultáneamente project.json
en disco: usar API/CLI/MCP y su revisión optimista. Las tareas nunca aprueban
automáticamente el proyecto. Usar python3 -B y pytest -p no:cacheprovider con
--basetemp dentro de .estado/tmp; no crear temporales globales.
