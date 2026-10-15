# Auditoría de Ascendia Studio

La entrega es un editor local funcional de código abierto con interfaz, motor
de render y acceso API/CLI/MCP. La revisión comprende el software y sus medios
de prueba. No aprueba el reel que la otra terminal está editando ni certifica
equivalencia completa con Adobe o CapCut Pro.

## Cierre vigente v0.6 — dos modos y colaboración

El inicio ofrece **Automático** y **Manual**, proyectos propios y compartidos,
búsqueda, orden y miniaturas. Las cuentas tienen biblioteca y branding propios.
El propietario invita a cuentas registradas con permiso de lectura o edición;
las mutaciones revalidan sesión y permiso, se serializan con revocación y usan
revisión optimista. Un conflicto conserva la edición local para recuperación.
No hay edición simultánea de caracteres mediante CRDT ni enlaces públicos.

La suite completa congelada pasó **2.166 pruebas en 346,23 s**, sin fallos ni
omisiones, con 114 archivos fuente estables. La revisión posterior encontró una
etiqueta de recibo que decía 45 % para split 50/50. Se corrigió metadata de
`studio/hyperframes.py` y se añadieron siete regresiones. Después pasaron
**121 pruebas relevantes en 203,10 s**, sin exclusiones, con 115 fuentes estables.
El cierre combina ambas ejecuciones; no atribuye una segunda suite completa
al cambio final. Evidencias privadas: `v06/python_suite.json`,
`v06/split_metadata_targeted_suite.json` y `v06/final_source_coverage.json`.

| Evidencia actual | Resultado | Límite |
|---|---|---|
| Inicio y modos en navegador real | 8/8 controles; cero errores de página o HTTP inesperados | Cuentas y proyectos de prueba; no despliegue público |
| Colaboración en navegador | Checkpoint histórico 17/17 con dos cuentas, conservado con sus hashes | El cierre actual añade regresiones de backend; no afirma 17 nuevas ejecuciones |
| SDK MCP oficial 1.28.0 | 8/8 controles; 61 herramientas, planes cerrados, render/export reales y revocación | Agente externo declarado; cero inferencias pagadas, sin certificación del proveedor |
| Pipeline reanudable | 12 s completos, seis escenas, dos chunks; ASR/tracking reutilizados con comprobantes idénticos | Fixture independiente: 7,918 s originales más cola silenciosa técnica; no entrega de cliente |
| HyperFrames/GSAP CPU | 360×640, 12 FPS, 144 frames; decode/check/runtime/MP4 y ZIP reales | Sin GPU ni aprobación editorial; máximo completo permitido 600 s no equivale a probar 600 s aquí |
| Inspección visual | 144 frames consecutivos y dos muestras a resolución completa; títulos y nombres corregidos | Último MP4 idéntico por SHA al revisado; no certifica fidelidad CLONE o todas las fuentes futuras |
| Audio original | 192.000 muestras a 16 kHz; Pearson 0,999774 y desfase 0; LUFS −20,87 y pico −7,39 dBTP | Sin escucha; ASR literal «Cloud» pendiente de cotejo; la cola contiene residual AAC, no cero exacto |
| Borrador manual completo | Fixture nativo 12 s con selección de pista y retraso PCM preservado; MP4/ZIP reales | Técnico explícito; no hereda aprobación de prueba o publicación |
| Registro de marcas | Procedencia HTTPS fijada, imagen y muestras observadas, SHA y contexto privado vigentes | El Google 150×48 utilizado no demuestra una interfaz ni concede derechos comerciales |
| Respaldo S3/R2 |Snapshot completo, blobs por SHA, head con CAS, reintento idempotente y restore en staging| Transporte probado con mocks; conexión remota desactivada, sin sincronización periódica |

El QC distingue texto demasiado pequeño y ausencia de un bloque legible.
`font_size` se expresa a ancho de referencia 1080: 42 se convierte en 14 px al
exportar a 360; 48 equivale a 16 px antes de escala animada. Comprueba fuentes
reales, escala, visibilidad y permanencia de al menos min(0,7 s, duración).
Permite etiquetas secundarias pequeñas cuando existe texto principal legible.
Son proxies geométricos a 10 Hz; no acreditan lectura humana, contraste, semántica
o calidad estética. La primera generación completa pasó el QC previo pero
la revisión de sus 144 frames rechazó texto pequeño y motion genérico. Sus
recibos y observaciones se conservan como históricos, sin aprobación fabricada.

El perfil público está en **revisión 4**, con las huellas de la lectura completa
r29: YO define identidad/cámara/subtítulos y CLONE exclusivamente motion;
nuevas cuentas empiezan con split 50/50, branding explícito y fuentes propias.
Los datos legacy conservan su historia. El software no modifica el proceso,
manuales, proyectos, recursos o terminal de IVAN ni hereda sus credenciales.
Los diez archivos del baseline y el proyecto técnico anterior se verifican
por hash. Todos los archivos generados y procesos nuevos pertenecen a SOFTWARE.

El paquete público usa una allowlist de código, documentación, ocho capturas
sintéticas revisadas y seis caras OFL con cuatro avisos. Excluye cuentas,
llaves, estados privados, proyectos, crudos, modelos, logos observados y
fuentes privadas. CRC, cobertura y SHA se verifican antes de sustituir el ZIP
canónico. Los medios de las pruebas anteriores no forman parte de ese paquete.
GSAP conserva su licencia propia; el código original del editor es MIT.

**La nube sigue desconectada y el servicio es local.** No hubo inferencias de
API pagadas ni publicación en Drive. El instalador y los runtimes externos no
se incluyen ni se presentan como instalados en otra máquina. SaaS público,
TLS, recuperación de cuenta, cuotas, cobros, OAuth y funciones aún ausentes
de Adobe/CapCut permanecen pendientes. Todos los borradores conservan
`editorial_approved:false`, `production_conformant:false` y
`audio_listened:false`; esta auditoría no los convierte en entregas aprobadas.

## Histórico v0.5 — espacios privados y automatización

**1.550 pruebas Python pasaron en 218,61 s**, sin fallos; el runner registró
`sources_stable:true` y salida 0. Evidencia privada:
`.estado/validacion/pytest_v05.json` y su log. La comprobación corresponde al
código/perfil congelados. Este cierre de README y auditoría se añadió después;
no cambia motores, perfil ni pruebas y no se atribuye una nueva ejecución
completa. El recibo `release_v05.json` separa los hashes documentales posteriores.

| Evidencia v0.5 | Resultado | Límite |
|---|---|---|
| Autenticación en navegador real | 14/14 controles; cero errores de página | Cuentas y espacios de prueba propios; no demuestra un despliegue público |
| Editor en navegador real | 13/13 controles; cero errores de página y HTTP; exportación y reapertura canónica | El recorrido final reutiliza el MP4 actual, sin nueva inferencia/render ni aprobación |
| SDK MCP oficial | 5/5 controles; 45 herramientas, conexión y revocación comprobadas | Cero llamadas a proveedores e inferencias durante esta comprobación de protocolo |
| Ocho adaptadores BYOK | Contratos de transporte, respuesta, límites y errores probados con mocks | No hubo llamadas a APIs externas; no verifica disponibilidad de modelos, cuentas o respuestas reales |
| ASR real | faster-whisper Small en CPU sobre habla real | «Cloud» sigue pendiente de cotejo; tiempos y texto automático no constituyen ground truth |
| Seguimiento facial real | MediaPipe WASM CPU, 16 muestras conservadas con evidencia | No acredita cada instante ni exactitud universal de rostro/barbilla |
| MP4 actual CPU | 1080×1920, 30 FPS, 7,933333 s; 238 fotogramas decodificados | Prueba técnica privada, sin GPU ni autorización narrativa |
| Comparación de voz | Pearson 0,999791; desfase 0 muestras, sobre 7,918 s de señal | Sin escucha ni aprobación sonora; correlación no valida contenido o mezcla perceptiva |
| Editable privado | 12.094.467 bytes; CRC/SHA y reapertura canónica comprobados | Preserva branding/fuentes/medios propios; no importa aprobación ni configura globalmente otra cuenta |

La inspección visual de los 238 fotogramas y límites de escenas identificó
correcciones pendientes. Los puntos invaden y ocluyen «SKILL» aproximadamente
entre 2,9–3,2 s; hay vacío y espaciado que reducen la jerarquía, y gráficos
genéricos que no son logos oficiales ni demostraciones auténticas. El cierre
también requiere revisar duplicación con subtítulos, contraste y continuidad
tipográfica en móvil. El nombre «Cloud» de la transcripción no se corrigió
silenciosamente. La muestra permanece **pendiente de corrección**, con
`audio_listened:false`, `editorial_approved:false`,
`production_conformant:false` y fidelidad CLONE sin aprobación. Pasar pruebas
técnicas o reproducir el archivo en Chrome no resuelve estos problemas.

Reportes privados de esta evidencia: `browser_multiservice_auth.json`,
`browser_multiservice_editor.json`,
`mcp_multiservice_sdk.json`, `multiservice_reel/prepared_context.json`,
`multiservice_reel/final_technical_audit.json` y
`multiservice_reel/visual_audit.json`, bajo `.estado/validacion`. Sus medios,
IDs, credenciales y capturas del reel no se redistribuyen en el paquete público.
La producción del padre, el original y los diez archivos protegidos conservan
los hashes del baseline; no se ejecutó ni modificó el proceso paralelo.

El perfil público `profiles/ivan_base.json` permanece en **revisión 2**, con
huellas y evidencia históricas. Se leyeron completos los cambios posteriores
del padre sobre ritmo, permanencias y registro de logos auténticos, incluida
la distinción entre revisión privada y permiso de publicación. El proceso
paralelo siguió actualizando sus manuales durante el cierre: las huellas de la
última lectura figuran en el recibo privado, sin declarar inmutable esa fase
ni reescribir revisiones anteriores. La adaptación de un registro auténtico
de marcas y de los tiempos de lectura sigue pendiente en el software. No se
heredan archivos privados, derechos ni promociones del padre. Los recursos
contextuales propios de cada usuario se rigen por su observación y procedencia;
la restricción de stock de una muestra padre no se aplica a todas las cuentas.

El ZIP público contiene únicamente código, configuración pública,
documentación, cinco capturas sintéticas revisadas y seis fuentes OFL con sus
cuatro avisos. La allowlist, CRC y SHA se verifican antes de reemplazar el ZIP
canónico. No incorpora cuentas, llaves, `.estado`, proyectos, crudos, modelos,
fuentes privadas ni harness. Es un checkout revisable; requiere dependencias,
runtimes/modelos y conexiones propias. No se ejecutó el instalador ni se publicó
un servicio remoto. **SaaS público, TLS, recuperación de cuenta, cuotas, cobros
y registro oficial de cliente OAuth siguen pendientes.** No hay paridad total
con Adobe/CapCut ni certificación de calidad CLONE. Los cierres v0.4 y anteriores
se conservan a continuación con su alcance histórico.

## Histórico v0.4 — fuentes y letras animadas

**1.171 pruebas Python pasan, sin fallos ni omisiones, en118,86s de pytest**
(119,32s del runner). Los25 módulos, tests y cuatro manuales conservaron SHA
antes/después de esta ejecución. Reporte:
`.estado/validacion/python-tests-v04-final.json` y su log. La primera pasada de
1.164 pruebas pasó antes de descubrir un defecto visual de color; se conserva
como histórica en `typography/python-tests-before-rgb-fix.json`, sin atribuirla
al código corregido. Se añadió la regresión y se repitió la suite completa.

**14 controles de navegador pasan**, sin errores de página ni respuestas HTTP
inesperadas. El cierre reutiliza diez controles de UI de su checkpoint, con el
mismo SHA de app.js, y renueva renders, playback, ZIP y captura responsive. El
reporte registra esa continuidad; no afirma catorce ejecuciones nuevas en una
única pasada. Los abortos de fuente/layout y catálogo no disponible son fallos
inyectados explícitamente para comprobar recuperación. Los intentos anteriores
conservan sus fallos de harness y el fallo real de HyperFrames.

Se cargaron realmente las seis caras OFL en Chrome con sus hashes y métricas.
La biblioteca tiene Source Sans3 Regular/Bold, Anton Regular, DM Serif Display
Regular/Italic e IBM Plex Mono Regular; cuatro notices canónicos y1.132.700bytes
de fuentes sin modificar. Sequel Sans Bold Disp y Scholar Italic conservan sus
roles. Solo Source Sans3 Regular aparece en este MP4; disponibilidad/importación
no se presenta como uso de todas las fuentes en el render.

| Evidencia nueva real | Resultado | Alcance |
|---|---|---|
| UI y presets | Siete opciones de entrada, tres salidas; estilos guardados; seek repetido idéntico, claves originales intactas | Incluye estado sin animación; no biblioteca comercial ni loops |
| Corte de escena | Corte a0,3s conserva clock_duration4 y clock_start−0,3 en el segundo tramo | No reinicia la fase ni desplaza el texto |
| Native |4s,360×640,30FPS,120frames;63.583bytes | SourceSans3 real, typewriter, contorno/sombra y fade; tono sintético, sin voz humana |
| HyperFrames |4s,360×640,30FPS,120frames; ejecución/check/snapshots y dinámica verificados | Mismo proyecto y fuente; fuente local SVG y GSAP |
| Reproducción Chrome |readyState4, avanza a0,613648s, errornull | Playback muted; no acredita escucha |
| Editable |13 miembros; ZIP HTML anidado14; CRC/SHA y fuente/notices/manifiesto correctos | Sin cachés ni aprobaciones importadas |
| Matemática existente |609 poses,1274 recortes,567 inserciones de claves | No mutaciones de proyectos |

La revisión del agente inspeccionó las secuencias consecutivas de ambos motores,
las entradas/salidas ampliadas y muestras alineadas. Á combinada aparece como un
solo grafema; las dos líneas y espacios mantienen posición al dividir. La
escritura termina a0,6s, sostiene el texto y se desvanece entre3,8–4s. No se
observó corte de glifos ni salto en0,3s. AA, contorno y blur difieren ligeramente
entre Pillow y SVG: no se anuncia identidad píxel a píxel. Es una muestra
funcional de tipografía, sin certificación CLONE ni aprobación narrativa.
`audio_listened:false` y `editorial_approved:false` permanecen explícitos.

La revisión encontró y corrigió defectos concretos:

1. Fuentes malformadas podían llegar al parser cmap y producir una excepción
   Python; SFNT/nombres/Unicode ahora se comprueban antes del registro.
2. La caché podía devolver SHA antiguo si el archivo cambiaba después de leer
   su firma. Se revalida al consultar caché y antes/después de medir/dibujar.
3. Metadata de licencia no objeto provocaba500. Se devuelve estado desconocido
   sin fabricar permisos, y avisos/aliases se confinan a rutas canónicas.
4. Un manifiesto tipográfico fuera de proof_files podía usarse para empaquetar.
   Su presencia y cobertura exacta de fuentes/avisos son obligatorias.
5. Espaciado negativo extremo producía avances no positivos. Se rechaza con
   explicación; no devuelve una caja supuestamente correcta con texto recortado.
6. La baseline antigua cortaba la caja em de Scholar en SVG. El layout común
   reserva ascent/bearings/contorno/sombra. Defaults de parámetros se conservan,
   con pequeño ajuste de padding; no se afirma igualdad de raster conv0.3.
7. HyperFrames interpretaba una sombra y su glifo como dos textos solapados.
   Solo cada texto decorativo de sombra tiene marca de solape intencional; texto
   principal, wrappers y recortes conservan las auditorías.
8. Una FontFace podía completar/fallar con layout cacheado y dejar el inspector
   cargando. El estado se actualiza si ese ID sigue seleccionado; hay reintento
   explícito y no se impone una respuesta tardía a otro proyecto/modal.

**Defecto detectado después de pasar pruebas:** el MP4 HyperFrames tenía una
banda negra de8px a la derecha, ausente en PNG y en Native. Se reprodujo en la
conversión FFmpeg JPEG→RGB planar, antes de mezclar audio. La captura JPEG de
Chrome no fue la causa. El adaptador agrega `full_chroma_int+accurate_rnd` solo
para la cadena SDR exacta del CLI; no cambia layout, recorta, estira ni rellena,
no desactiva SIMD globalmente y no modifica dependencias del padre. Siete
regresiones incluyen JPEG→H.264 reales a360/1080px con bordes de color distintos
que deben conservarse; son un frame de prueba, no otros renders de reel FullHD.

El nuevo MP4 tiene fila100, columnas352–359, RGB(14,18,24), igual a columna340
**en sus120 frames**. Native también ocupa todo el ancho. Evidencia:
`typography/jpeg_diagnosis/before_after.json`, `typography/visual_audit.json` y
sus filmstrips. El MP4 anterior se conserva exclusivamente como evidencia del
fallo en `hyperframes_before_rgb_fix.mp4`, con SHA histórico.

La auditoría independiente añadió66 casos hostiles; los del paquete motion
simulan únicamente el verificador externo, mientras UI y render tienen pruebas
reales separadas. API/CLI/MCP añaden16 controles de integración y MCP dispone de
36 herramientas. `job_get` y `job_cancel` consultan/cancelan solo trabajos propios.
La implementación y las limitaciones tipográficas están en
[TIPOGRAFIA.md](TIPOGRAFIA.md), con enlaces oficiales y commits de las fuentes.

Los cuatro proyectos anteriores y el original del padre mantienen SHA exactos.
La lectura actual de los manuales incorpora la regla25 B_V2, sin ejecutar ese
encargo ni heredar aprobación. Solo se reinició el servicio propio inactivo de
SOFTWARE, con comprobación de cwd/comando/cola; ninguna señal o tecla al Codex
padre. Toda escritura, modelo, perfil y temporal permanece en SOFTWARE.

No hay paridad con Adobe/CapCut: rich-text por fragmentos, selectores arbitrarios
por letra/línea, loops, texto sobre curva, 3D por carácter, rotoscopia manual,
separación neuronal de voz, relleno generativo, HDR y multicámara siguen
pendientes o limitados. Las pruebas cubren los casos declarados; no garantizan
todos los idiomas, fuentes, códecs o condiciones de entrada.

Los siguientes apartados preservan resultados históricos de versiones anteriores;
las capacidades vigentes se consultan en la API y en este cierrev0.4.

## Histórico v0.3 — 13 de octubre de 2026 UTC

**1016 pruebas Python pasaron en 116,77 s**, sin fallos ni omisiones. Los 23
módulos, los tests y los cuatro manuales conservaron sus SHA durante la
ejecución 04:22:03–04:24:01 UTC. Reporte y log:
`.estado/validacion/python-tests-v03-final.json`. Los ensayos anteriores
conservan sus huellas y no se atribuyen retrospectivamente a esta versión.

**23 controles de navegador actuales pasaron**, sin errores de página:
10 de segmentación, 7 del editor/MP4/ZIP/diseño/tracking y 6 de reapertura tras
reiniciar el servidor. Los 13 últimos fueron de solo lectura, sin trabajos ni
escrituras HTTP; reutilizaron
renders previos verificados y conservaron los reportes/capturas históricos.
La prueba de modelo ausente fue un mock explícito del catálogo, separado de
la inferencia real. La matemática del preview volvió a pasar 609 poses,
1274 recortes y567 inserciones de claves.

La herramienta nueva `remove_background_video` ejecuta MediaPipe WASM CPU
con modelo fijado por SHA, sin GPU. Procesa un tramo SDR a MOV QTRLE/ARGB
transparente con la primera pista de audio decodificada a PCM a 48 kHz. El navegador
usa un proxy VP9 alfa; fuente y escenas no se reemplazan automáticamente.
El catálogo muestra disponibilidad, ejecución verificada y motivos pendientes.
API/CLI/MCP usan el mismo contrato de parámetros y cola.

| Evidencia real v0.3 | Resultado | Límite |
|---|---|---|
| SDK privado |1 s, 360×640, 15 FPS, 15 máscaras, MOV de 6.169.308 bytes; inferencia/procesamiento en 3,749 s| Un extracto privado previo; no modifica el original del padre |
| Primer job de interfaz | Mismo tramo, feather de 2 px; MOV de 6.257.815 bytes, 3,981 s; decodificación/alfa verificadas | Ejecución real guardada en recibo; el cierre de UI reutiliza esa caché |
| Alfa decodificado en Chrome |98.825 px transparentes, 126.414 opacos, 5.161 intermedios en un frame | Prueba de transparencia; no mide exactitud de la máscara |
| Audio numérico |14.400 muestras de 0,9 s; correlación 0,9999999993, error RMS 0,000005086 | Comparación de señal, sin escucha ni aprobación sonora |
| ZIP editable del proyecto UI |9 archivos, CRC/SHA de recursos/fuentes correctos, original y MOV conservados | Proxy regenerable omitido; no se reimportó ni se aprobó |

Se inspeccionaron la fuente y las máscaras de inicio/medio/final, los 15
fotogramas consecutivos decodificados de ambas variantes, y su composición
sobre cuadros/blanco con detalle inferior. Rostro, gafas, ropa y manos se
conservan en esta muestra; también quedan mesa, micrófono y dispositivos.
Aparecen huecos variables en el borde inferior, especialmente 0,467–0,600 s.
Feather de 2 px suaviza el borde y no demuestra mejora temporal. Por ello no se
presenta como rotoscopia ni matting perfecto. Esta inspección por secuencia
y los datos de reproducción no sustituyen una revisión perceptiva completa
en tiempo real, de otros clips o del reel de cliente.

La auditoría independiente añadió 155 casos adversariales con fixtures/mocks;
el SDK tiene 47 pruebas, incluidas dos ejecuciones reales cortas. Se corrigieron
validaciones de cache/recibo/evidencias, presupuestos de disco, cambios de
fuente/modelo durante procesamiento y cancelación después de verificar caché.
La asociación canónica comprueba catálogo/ruta/SHA antes de sustituir la copia
privada por un enlace interno; el recibo sigue verificable después de asociarla.

Otros fallos concretos corregidos: arranque del modal sin contexto; respuesta
tardía del catálogo sobre otro clip; cambio de proyecto durante un guardado;
actualización de biblioteca bloqueada por edición local pendiente; observaciones
que intentaban escribir el origen técnico protegido. Los formularios conservan
el contexto y revisión, guardan `origin_observed` aparte y no activan aprobación.
La cancelación en UI del job propio no registró un derivado. Un proyecto modificado
durante proceso recibe el recurso únicamente en biblioteca. La validación
narrativa rechaza fuentes conocidas con fondo retirado, incluso vía proxy.

La revisión externa verificó manual/API/código y los hashes de tres proyectos
anteriores, muestra privada y original del padre. El proceso Codex padre
continuó observable; no recibió señales, teclas ni escrituras. El único
proyecto temporal vacío de los checks fue retirado con recibo; permanece
el proyecto técnico de prueba con su crudo y MOV sin aprobación editorial.

El servidor propio terminó con código 143 por una causa no identificada, después
de las primeras pruebas. Se reabrió en una sesión independiente y se comprobaron
persistencia, huellas actuales, playback/alfa, descarga canónica y ausencia de
nuevas escrituras/trabajos en seis controles. No se atribuye esa terminación a
un fallo del motor ni se oculta: queda en `server_recovery_v03.json`. El primer
arranque del nuevo harness de reapertura usó un TMPDIR absoluto demasiado largo
para el socket Unix de Chrome; se corrigió a `.estado/tmp` relativo dentro de
SOFTWARE antes de la ejecución correcta, sin cambios del software.

Reportes privados: `browser_segmentation.json`, `browser_motion_final_v03.json`,
`browser_segmentation_reopen_v03.json`, `segmentation/temporal_technical.json`,
`segmentation_visual_review.json` y `v03_independent_final.json`, todos
en `.estado/validacion`. Las capturas de escritorio y móvil contienen material
privado y se excluyen de la distribución pública.

Siguen pendientes la rotoscopia manual, separación/restauración neuronal de
voz, relleno generativo, HDR, multicámara, Blender y un generador semántico
interno evaluado. SceneIR continúa recibiendo semántica declarada por su autor;
este avance no certifica fidelidad CLONE/YO ni toda la suite Adobe/CapCut.
Los renders de cliente y la producción paralela no se aprobaron ni publicaron.

## Cierre histórico v0.2 — 13 de octubre de 2026

**797 pruebas Python pasaron en 109,58 s**, sin fallos ni omisiones. El código de
22 módulos, los tests y los cuatro manuales conservaron sus SHA durante la
batería completa (03:08:20–03:10:10UTC). El log y su hash quedan en
`.estado/validacion/python-tests-v02-final.json`. Los reportes anteriores
conservan sus fechas/manuales; las 589 pruebas previas no se presentan como
verificación retroactiva de SceneIR o de la regla 23.

En Chrome real, sobre el JavaScript final, pasaron **16 controles actuales**:
9 de SceneIR y 7 de reapertura/MP4/ZIP/diseño/tracking. Cero errores de página.
SceneIR comprobó los rechazos esperados400/409; el recorrido de reapertura tuvo
cero errores HTTP y cero peticiones de escritura. Lab y MotionWorkbench
conservaron los mismos bytes. Escritorio/móvil, fuentes exactas y ausencia de
desbordamiento quedaron comprobados. La matemática del preview pasó609 poses,
1274 recortes y567 inserciones de keyframes, en seis canales/cinco curvas.

Capacidades nuevas verificadas:

- Composición libre de texto, formas y medios: arrastre/tamaño/orden, máscaras,
  trayectorias, curvas parciales, claves y deshacer; validación finita y límites.
- HyperFrames/GSAP real, seek determinista, browser check no omitido y HTML
  editable empaquetado con CRC/SHA. Las escenas raster se declaran aparte.
- Seguimiento facial MediaPipe CPU con478 landmarks, PTS medidos, huecos y
  ambigüedades; propuestas geométricas de crop/split sin aplicación automática.
  Muestra real de 7,918 s:32/32 detecciones, confianza 0,9539–0,9813,12,077 s de cálculo.
  Este dato no equivale a revisión humana del rostro ni escucha de audio.
- PNG de diseño base y revisión con procedencia, referencia y SHA; PUT/ZIP no
  pueden forjar aprobación. El inspector identifica correctamente el motor de
  la captura y bloquea revisar una captura obsoleta como diseño actual.
- SceneIR de datos explícitos a una motion/custom editable. Preview sin
  escrituras, aplicación con revisión optimista, origen protegido y modo
  componente. Biblioteca permite render técnico sin aprobación por cada pieza;
  QC sigue pendiente, sin generar ni certificar semántica/CLONE por sí solo.
- 31 herramientas MCP, CLI/API y workflows diferenciados de reel/componente.

Pruebas reales conservadas:

| Evidencia | Resultado | Alcance |
|---|---|---|
| HyperFrames FullHD |1080×1920, 30 FPS, 10 s, 300 frames decodificados,39,903 s| Prueba técnica sintética; pixel backend sigue verificable; manual histórico regla 22 |
| MotionWorkbench |360×640, 30 FPS, 10 s, 300 frames; ZIP 720783 bytes| Dos escenas DOM/GSAP; reapertura actual conserva JSON/medios; promoción editorial obsoleta/no aprobada |
| SceneIR actual |360×640, 30 FPS, 4 s, 120 frames; ZIP 211402 bytes| Regla23 y código actual; origen declarado, QC pendiente; recibo/digest vigentes |
| SceneIR editable |9 miembros principales,10 HTML/runtime anidados; CRC/SHA válidos| Reabierto con mismo ID/source y JSON intacto; HTML importado no se ejecuta |

El MP4 SceneIR histórico y su ZIP editable se conservan en el entorno privado
de validación; estos medios no forman parte del paquete público de código.
SHA del MP4: `474615a9fa66bc3c0d0cdd3e256524fc3f9f02858bf06dd44bbad580c0f012a4`.
SHA del ZIP: `ab7b9a7b0ed0fecad4f7414656ce7a2709cda8cba436802c2f70cb6aa7b34a64`.
La solicitud de 10 s se normalizó explícitamente a 4 s y technical=true, dejando
constancia en el job; no produjo un completo ni heredó aprobación del padre.
Se vieron16 muestras cronológicas del componente y secuencias/transiciones del
motion técnico previo. Son gráficos sintéticos de diagnóstico; no se afirma
revisión completa de fidelidad CLONE, pertinencia para Iván ni escucha perceptiva.
Todas las aprobaciones editoriales permanecen falsas.

Fallos materiales corregidos durante v0.2: keys fraccionales al recortar,
máscaras vacías subpixel, caché compartida entre elementos con el mismo asset,
duración final no entera en FPS, booleanos confundidos con 0/1 al mezclar acciones,
crudo/derivados ocultos como gráficos, PNG nativo mal rotulado como HyperFrames,
JSON mal formado que terminaba 500, handler SceneIR en ruta incorrecta,
controles asincrónicos que podían actuar sobre otro proyecto y duración del
crudo usada para el componente. ZIP verifica origen/media antes de registrar
archivos; vuelve a comprobar bytes/digest antes de reemplazar un exportado.
Los fallos de los harness y sus checkpoints se conservan como tales.

Se eliminaron solo temporales propios duplicados y un proyecto vacío propio;
las fuentes, modelos, assets canónicos, MP4/ZIP y evidencias se mantienen.
El proceso paralelo de IVAN continúa independiente; no se ejecutó ni señalizó.
La regla 23 autoriza la biblioteca padre A–F y preserva CANCELLED: este adaptador
no realiza ese encargo paralelo ni hereda su aprobación. Su lectura completa
está registrada en `.estado/manual_read.json` y PROCESO_IVAN.md.

Límites actuales: no hay paridad completa Adobe/CapCut, generador semántico
interno, familias CLONE completas certificadas, rotoscopia, separación neuronal,
relleno generativo, HDR, multicámara ni Blender. ASR depende de modelos CPU y
puede errar nombres/tiempos. Fuentes, modelos, FFmpeg y GSAP conservan sus
licencias; GSAP no es MIT. Los componentes pueden probarse automáticamente;
la promoción narrativa sigue necesitando evidencias y revisión perceptiva.

## Registro histórico v0.1

Las comprobaciones y limitaciones que siguen describen la versión anterior
bajo los manuales y tiempos allí registrados. El cierre v0.2 anterior es el
estado vigente; seguimiento y HyperFrames ya están implementados.

## Alcance implementado

- Biblioteca por hash, inspección de pistas, miniaturas y waveform; originales
  conservados y un proyecto canónico por fuente/ID de Drive declarado.
- Cronología editable, split 55/45, reencuadre, texto Sequel/Scholar, color,
  keyframes y cuatro composiciones de motion parametrizadas.
- Hasta ocho capas independientes por escena, transparencia, Screen, tiempos
  de medio y animación; audio original separado de las capas visuales.
- ASR CPU multilingüe opcional, segmentos y palabras editables. El borrador de
  storyboard parte de esa narración y exige selección contextual posterior.
- Mezcla con voz, música, ducking, riser/SFX, limitador sin ganancia automática,
  normalización opcional y medición real de LUFS/pico del AAC exportado.
- Diez herramientas multimedia con parámetros validados: inspección, cortes,
  niveles, extracción, denoise, normalización, proxy, velocidad, reversa y
  chroma key. Son filtros y mediciones reales; denoise no es separación neural.
- Exportación/reapertura ZIP con recursos, fuentes, proyecto y subtítulos;
  validación de rutas, hashes, ZIP y fuentes antes de incorporarlo.
- Tareas para director, recursos, motion, audio y QA, con dependencias, leases,
  evidencia y revisión vigente. Los modelos/agentes externos usan MCP o API;
  crear tareas no despliega por sí solo un proveedor de IA.

## Comprobaciones de la entrega

La ejecución integrada definitiva terminó con **336 pruebas Python correctas
en 43,21 s**, sin fallos ni omisiones, el 13 de octubre a las 00:12:23 UTC
(12 de octubre en Bogotá). Código e instrucciones permanecieron iguales
durante la ejecución. El reporte privado enlaza las huellas de los catorce
archivos del motor. Se verificaron API HTTP, CLI, MCP, formatos, render, audio,
capas, ZIP, hashes, concurrencia, cancelación, controles V5 y las correcciones
posteriores. Se conservan los reportes anteriores, incluidos 248 controles
iniciales, 317 previas al último guard de ASR y un fallo intermedio de mensaje de autorización, corregido antes
de repetir la batería completa.

En Chrome real pasaron **21 comprobaciones del editor y tres de formatos**,
con cero errores de página y cero respuestas HTTP inesperadas. Incluyen
guardados simultáneos y durante un PUT pendiente, recuperación de cambios,
reapertura canónica, cambio de proyecto, subtítulos animados, waveform,
transparencia, exportación y reapertura del ZIP y lectura vigente del manual.
La URL de descarga devolvió un ZIP válido; no se atribuye una descarga a disco
del navegador al mero éxito HTTP.

Tras el cambio de instrucciones se verificaron siete casos adicionales por
lectura: referencia CLONE, ámbito de YO, herramientas pendientes, elección
técnica/narrativa, gate narrativo real, gate técnico disponible y observaciones
del laboratorio sin aprobación. Cero mutaciones de proyecto, errores JS o HTTP.
CLI, MCP y HTTP también comprobaron doce guías y cinco referencias disponibles,
sin afirmar su lectura/aplicación. MCP expone 24 herramientas.

El cierre con el manual vigente añadió **14 comprobaciones de extremo a extremo
correctas**, sin errores de página ni respuestas HTTP fallidas. Chrome encoló
un único render técnico y guardó únicamente observaciones comprobadas. FFprobe
midió H.264/AAC, 360×640, 30 FPS, 300 frames y diez segundos; FFmpeg decodificó
todo el archivo y Chrome avanzó su reproducción real. El SHA coincidió con el
primer candidato técnico, sin crear otro archivo de entrega. Los comentarios
se guardaron con todos los controles editoriales y `approved_preview` falsos;
`approval_current` también permaneció falso. No se atribuye escucha ni revisión
completa del movimiento a la reproducción de una parte en Chrome. El gate
narrativo actual pide diseño estático CLONE/adaptador verificado y no otra
prueba genérica de tres segundos. Proyecto, cuatro recursos, cronología y
observaciones de referencia conservaron sus contenidos.

El corpus comprobó MP4, MOV, MKV, WebM, AVI y MXF; WAV, MP3, M4A, FLAC y OGG;
video sin audio, audio con portada y PNG/JPG/BMP/TIF/TIFF. MOV transparente se
reprodujo mediante WebM alfa y TIFF mediante PNG transparente en Chrome.
Los originales conservaron sus hashes y no sustituyeron el crudo.

Tras las pruebas se retiraron exclusivamente dos proyectos y seis medios
sintéticos propios, sus derivados y temporales descartados. Permanecen el
Laboratorio, cuatro recursos, sus fuentes y los reportes privados. Una última
carga comprobó esas cuatro escenas/recursos, fuentes reales, waveform de 240
picos y escritorio/móvil sin errores ni desbordamientos. Los comandos de
reproducción están en README.md.

**Render Full HD real.** Una fuente sintética reutilizada, capas transparentes
y keyframes produjeron MP4 H.264/AAC de 1080×1920, 30 FPS, diez segundos y
300 fotogramas. Render y auditoría tardaron 7,813 s en esta máquina; el archivo
midió 2.117.640 bytes. Es una medida de ese ejemplo, no un SLA para cualquier
reel. Se decodificaron los 300 frames, se prepararon secuencias/transiciones
consecutivas y un proxy de revisión. El audio sintético exportado midió
−21,78 LUFS y −15,51 dBTP. No se afirmó escucha ni aprobación editorial.

**Laboratorio visible.** El proyecto de ejemplo combina medios sintéticos,
audio de prueba, cuatro escenas y mezcla. Su render actualizado midió
−17,19 LUFS y −6,31 dBTP. Su diseño no pretende representar la narración de
Iván ni sustituye la observación de YO. Permanece expresamente sin aprobación.

**Reconocimiento de voz.** Se ejecutó faster-whisper Tiny en CPU sobre una
muestra de habla real en inglés y un extracto privado limitado a diez segundos
en español, cuya duración real fue 7,918 s. Produjo 22 y 31 palabras alineadas,
respectivamente. Tiny confundió
nombres y expresiones en español: disponer de timestamps no prueba exactitud
del texto. Es obligatorio cotejar audio, cifras, marcas y sincronía; el editor
permite corregir bloques y palabras. Las comparaciones con otra transcripción
automática tampoco constituyen ground truth ni escucha.

Small produjo 25 palabras alineadas sobre ese extracto; una segunda ejecución
desde caché, con la red deshabilitada, tardó 3,031 s incluyendo carga del modelo.
Todavía quedaron nombres por cotejar. Su caché local ocupa aproximadamente
464 MiB y la evaluación usó cerca de 1 GiB de memoria máxima. Se ofrece como
opción; estos resultados de una muestra no garantizan precisión universal.

## Problemas encontrados y corregidos

Las revisiones independientes reprodujeron fallos concretos antes de añadir
regresiones:

1. La ganancia automática del limitador elevaba el bus. Se desactivó y se mide
   el AAC final, con avisos por pico real y valores nulos para silencio.
2. Un subtítulo podía quedar sobre la barbilla tras un zoom o por falta de
   espacio. Se ajusta a una línea, se calcula el encuadre animado y se rechaza
   el render si sus glifos/sombra no caben dentro de la zona segura.
3. Los cambios hechos mientras esperaba un guardado podían perderse. La
   interfaz conserva los cambios nuevos y la revisión devuelta por el servidor.
4. Cambiar de proyecto podía dejar visible el render anterior. El reproductor
   y el modo se reinician cuando cambia proyecto o fuente.
5. Recortar una capa estática desplazaba su tiempo de fuente. Las imágenes
   conservan `source_in:0` al recortar y dividir.
6. El preview ignoraba la transformación de barbilla del motor. Ahora aplica
   escala/desplazamiento y límites de la caja del texto.
7. Una copia antigua del manual podía recibir huellas nuevas. Se muestra el
   contenido recién leído, se calcula su SHA de esos mismos bytes y se comprueba
   el mapa esperado antes de registrar lectura; los cambios devuelven 409.
8. Una fuente privada podía entrar en el ZIP. Las fuentes del proyecto deben
   estar en `assets/fonts` y el exportador valida el esquema antes de escribir.
9. La importación podía mezclar un SHA antiguo con bytes nuevos. Se inspecciona
   una copia estable, se verifican hashes antes de promover y se conservan
   originales. Contenido canónico alterado o rutas ocupadas se rechazan.
10. Un fallo al preparar el lock podía dejar retenido el bloqueo de hilos.
    La liberación y cierre del descriptor cubren también esos errores.
11. Repetir un trabajo terminado podía sobrescribir su resultado. La ejecución
    acepta únicamente trabajos en cola y conserva estados finales.
12. Importaciones y proxies podían eludir la coordinación CPU o invertir
    bloqueos. CPU se reserva antes del almacén, se reutiliza dentro del worker
    y se rechazan llamadas anidadas o con orden inválido.
13. Reabrir un ZIP podía omitir el proxy o utilizar metadata antigua. Se prepara
    después de la transacción y se actualizan solo campos de preview, sin
    cambiar observaciones, huellas editoriales ni revisiones.
14. El ZIP rechazaba MXF admitido por el motor y una imagen BMP se aceptaba como
    crudo. Se alineó MXF y se clasifican las imágenes reales como imágenes;
    también se excluyen las portadas `attached_pic` del video original.
15. Asignar un crudo o guardar JSON podía eludir la unicidad del proyecto. Un
    borrador vacío reabre el canónico; un cambio incompatible devuelve 409 y
    conserva ambos editables. Un ID de Drive con contenido diferente también
    se rechaza. La interfaz actualiza selector, almacenamiento e ID al reabrirlo.
16. Variables modernas de caché o tokens de modelos podían heredarse del entorno.
    Hub, Xet y assets usan rutas propias; las descargas públicas no heredan
    tokens ni activan telemetría implícita.
17. La interfaz podía conservar un badge vigente tras cambiar solo código o
    guías. `approval_current` ahora se calcula en el backend, se ignora en
    escrituras del editable y comprueba candidato, aprobado y requisitos
    actuales. La interfaz exige ese indicador.
18. Una autorización anterior podía sobrevivir a un nuevo render o comentario.
    Todo render/revisión la revoca; el completo exige aprobación vigente al
    encolar y antes de ejecutar, incluida la verificación de sus bytes.
19. Un opt-in ASR recibido como texto `"false"` podía resultar verdadero.
    Se exige booleano explícito antes de encolar o iniciar análisis. Los datos
    inválidos devuelven 400 sin modelo, trabajo ni lectura de medios; 19 casos
    comprueban HTTP y llamadas directas.

Las 38 regresiones de política cubren los controles actuales y las afirmaciones
forjadas de motor. Las 31 de skills cubren confinamiento, fuentes/referencias,
evidencias, registros malformados, cambios simultáneos de árbol y vigencia de
receipts/leases. Las pruebas unitarias de aprobación aíslan el adaptador ausente
con fixtures explícitas para comprobar cada gate; no acreditan integración de
HyperFrames ni aprobación de un reel real.

Los conflictos entre ventanas conservan los cambios locales y permiten un
respaldo JSON pendiente. Ningún respaldo ni resultado de agente activa una
aprobación. Una prueba aprobada se guarda separadamente del nuevo candidato;
cambios posteriores invalidan su autorización y conservan sus bytes anteriores.

## Aislamiento y límites

Archivos, caches, modelos, perfiles de navegador, pruebas y exportados quedan
en SOFTWARE. Los cuatro manuales del padre se leyeron completos al inicio.
En la comprobación posterior, la producción paralela cambió AGENTS,
PROMPT_MAESTRO e INSTRUCCIONES; STYLE_YO conservó su hash. Se releeyeron completos
y se registró la nueva lectura el 12 de octubre a las 23:46:15 UTC, conservando
las huellas históricas. SOFTWARE adoptó CLONE exclusivo para motion y YO para
cámara/subtítulos/split; en ese snapshot la prueba técnica HyperFrames/GSAP de
tres segundos era un requisito separado del reel narrativo. La directiva
posterior, descrita abajo, declara esa arquitectura comprobada. No se atribuye esa
prueba a este motor Pillow. La sesión Codex de IVAN continuaba
observable en la comprobación final. No se enviaron señales ni teclas a ella,
no se ejecutó su workflow/preflight y no se modificó su estado. Los únicos
reinicios corresponden al servidor creado aquí.

La aplicación escucha en loopback, reserva un procesador multimedia local,
usa FFmpeg con hasta dos hilos y prioridad reducida; CUDA/NVENC no se utilizan.
No hereda credenciales, no sirve `.estado`, no permite shell arbitrario y no
publica en Drive.

Faltan seguimiento facial automático, rotoscopia, separación neuronal de voz,
relleno generativo, mastering HDR, multicámara y adaptadores HyperFrames/Blender.
Los recursos premium propietarios no forman parte del código MIT. Los formatos
dependen de FFmpeg y los proxies del navegador instalado. Una revisión técnica
no decide fidelidad a YO, pertinencia semántica, encuadre real, ortografía ni
calidad sonora perceptiva. Esos controles siguen requiriendo revisión explícita
en movimiento y escucha antes de aprobar la prueba de diez segundos y autorizar
un completo. Tras las nuevas instrucciones, el gate narrativo exige también
registro vigente de doce guías y adaptador HyperFrames/GSAP verificado.
El adaptador está pendiente. La exportación técnica sigue disponible, con
recibo identificable y sin posibilidad de aprobación ASCENDIA. GSAP conserva
su [licencia propia](https://gsap.com/community/standard-license/), distinta
de la licencia MIT del código original y Apache 2.0 de HyperFrames.

La lectura posterior del 13 de octubre a las 00:10:27 UTC detectó un segundo
cambio de los mismos tres manuales. Se releyeron completos y se registraron
las nuevas huellas. La última fase del padre es diseño estático CLONE1,6–3,2 s
y comparación PNG, con aprobación explícita antes de animar sin modificar el
diseño. La arquitectura GSAP se declara ya comprobada y no debe repetirse.
La política/tareas del editor reflejan esta precedencia; no se ejecutó ese
encargo ni se presentó el laboratorio sintético como su reconstrucción.

Después de las 336 pruebas, INSTRUCCIONES volvió a cambiar: reconciliaba dos
líneas históricas con esa misma fase estática, sin añadir una política nueva.
Se leyó completo y se registró a las 00:17:49 UTC, con SHA-256
`78119c339487036aeeed64f5e802e706a14fa8c212587c6e28856834d442a4bf`.
Los otros tres documentos y los catorce archivos del motor conservaron sus
huellas. El laboratorio recibió el sello actual por la API. El reporte de las
336 pruebas conserva el manual bajo el cual se ejecutó; no se reescribió para
atribuirle la lectura posterior. El gate rechazó correctamente una exportación
con el sello anterior antes de encolar trabajo alguno.

Proceso original y paso a paso: [PROCESO_IVAN.md](PROCESO_IVAN.md).
Repositorios y fuentes primarias: [INVESTIGACION.md](INVESTIGACION.md).
Contrato de automatización: [API.md](API.md).
