# Proceso existente de IVAN y convivencia con Ascendia Studio

Auditoría de lectura: 12 de octubre de 2026. Este informe describe archivos y código observados; no ejecuta la producción existente, no actualiza Drive y no certifica el resultado editorial de ningún reel. Los archivos de producción pueden cambiar mientras otra terminal trabaja. Los apartados iniciales conservan el snapshot histórico anterior al cambio de prioridad CLONE; la actualización fechada al final establece la precedencia más reciente.

## Alcance y evidencia

Se leyeron completos `IVAN/AGENTS.md` (31 líneas), `IVAN/PROMPT_MAESTRO.md` (959 líneas, incluidas todas las directivas), `IVAN/INSTRUCCIONES.md` (128 líneas) y `IVAN/STYLE_YO.md` (49 líneas). También se revisaron en solo lectura `sistema/workflow.py`, `render.py`, `composicion.py`, `seleccion.py`, `preflight.py`, `perfil.json`, `herramientas.json`, `ESTADO.json` y los metadatos de los proyectos.

Huellas SHA-256 observadas:

| Documento canónico en IVAN | SHA-256 |
|---|---|
| AGENTS.md | `29058e920ae7c639317981de85c77c67a34a3b66519a0ebbfb2c8a9047018dcd` |
| PROMPT_MAESTRO.md | `240a0b0db98dffb8fb7cc51de1e842355642377b04e9c08c879a93e7eb1d0704` |
| INSTRUCCIONES.md | `90bf5700bed4f0c99405a5f6c3bc7c8a520ad786e69ed25e646f2802b8dd09fb` |
| STYLE_YO.md | `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39` |

El código comprueba las huellas antes de renderizar, auditar o promover. Un hash comprueba identidad del archivo; por sí solo no demuestra comprensión del manual ni inspección de un video.

## Estructura observada

```text
IVAN/
├── AGENTS.md                 Reglas y precedencia
├── PROMPT_MAESTRO.md         Manual canónico completo
├── INSTRUCCIONES.md          Accesos, selección y operación
├── STYLE_YO.md               Perfil de identidad observado
├── ESTADO.json              Continuidad global de producción
├── sistema/                 Workflow, motores, QA y entrega
├── recursos/                Catálogo, referencias, fuentes y recursos
├── assets/
│   ├── broll/               Clips canónicos incorporados al workflow
│   └── referencias/YO/      Evidencias y mediciones de la referencia
├── proyectos/
│   ├── ID_CRUDO_PRIVADO/   Proyecto anterior Agent Reach
│   └── ID_CRUDO_PRIVADO/   Prueba nueva V5
├── .estado/                 Acceso privado, motores, caches y temporales
└── SOFTWARE/                Ascendia Studio, aislado de la producción
```

El proyecto de un crudo guarda su original, `proyecto.json`, transcripción, seguimiento facial, decisiones de recursos, storyboard, composición HTML, código de motion y auditorías. El catálogo compartido evita una copia por escena. La identidad primaria de una entrada es su ID de Drive; MD5 y tamaño permiten reconocer copias idénticas con IDs distintos.

## Qué estaba haciendo la otra terminal

El `ESTADO.json` observado registraba `analisis_v5_nuevo_crudo`, proyecto activo `ID_CRUDO_PRIVADO` y siguiente acción de analizar YO/narración, seleccionar recursos y producir diez segundos. Una lectura posterior de `proyecto.json` ya registraba `produccion_prueba_v5`, composición HyperFrames con alcance de diez segundos, escenas pendientes y aprobación del usuario pendiente. Esta diferencia muestra que el registro global puede quedar detrás del archivo de proyecto durante el trabajo.

El crudo activo figura como `Testeo Reels.mp4`. El storyboard observado comienza con «Google está furioso», continúa con Claude y lectura web, transforma fuentes en un proceso y termina la frase sobre no pagar una API. Los clips programados incluían Google Workspace, Claude y lectura web. La presencia programada era 0–1,3 s y 6,0667–6,6667 s; esto describe la cronología, no verifica su aparición real en el render.

Un snapshot de procesos mostró tres terminales `codex --yolo`, con directorios de trabajo en carruseles de Iván, la raíz de reels y IVAN. No apareció un proceso FFmpeg, HyperFrames, Remotion o Python de render en ese instante. Eso no prueba que la sesión esté detenida: puede estar analizando, escribiendo, esperando o entre renders. No se enviaron señales, teclas ni comandos a esas sesiones y no se leyó su historial privado.

`sistema/herramientas.json`, actualizado por el proceso externo a `2026-10-12T22:18:38Z`, registraba HyperFrames, Playwright MCP, Remotion, Node, Codex CLI, FFmpeg y Parakeet como operativos; Tella figura excluido por el usuario. Este informe leyó ese comprobante. No repitió el preflight ni sus pruebas y no afirma haber utilizado aquí esas siete herramientas.

## Paso a paso observado en el snapshot inicial

Los siguientes comandos son documentación del sistema existente. **No deben ejecutarse desde Ascendia Studio ni durante esta auditoría**: algunos importan módulos que crean carpetas, actualizan estado o tocan GPU/Drive.

1. **Leer e integrar el manual vigente.** `workflow.py manual` comprueba que siguen presentes las quince secciones originales y calcula huellas de AGENTS, prompt e instrucciones. El proyecto conserva ese sello. V5 añade la huella de STYLE_YO.
2. **Comprobar el entorno.** `preflight.py` consulta versiones y comprobantes de ejecución. Sus llamadas tienen efectos: actualizan `sistema/herramientas.json` y consultan NVIDIA. La excepción vigente elimina el bloqueo de Tella. La nueva aplicación usa su propio diagnóstico y no llama este programa.
3. **Inventariar referencias y bibliotecas.** `bibliotecas.py actualizar` recorre Drive con paginación y guarda el inventario canónico. Las instrucciones observadas registran 42 carpetas, 1.876 archivos y 1.861 videos; ESTADO conservaba 1.875 archivos. Son datos de registros distintos, no una nueva verificación remota. El inventario completo no significa haber visto cada clip.
4. **Detectar entradas nuevas.** `workflow.py crudos --ingestar` verifica la carpeta Crudos, clasifica por ID y contenido MD5/tamaño, asocia aliases de copias idénticas y crea un solo proyecto por crudo. Un mismo ID con contenido distinto requiere revisión. No se ha instalado un vigilante periódico según el estado leído.
5. **Analizar el medio.** FFprobe mide duración, streams, resolución y FPS. La descarga usa un archivo `.part`, valida que no sea HTML y verifica el medio antes de promoverlo a original.
6. **Transcribir con tiempos.** `workflow.py transcribir ID` reutiliza `transcripcion.json` si ya existe. El motor predeterminado es Parakeet con CUDA; hay ruta alternativa faster-whisper CPU. Las palabras se agrupan por pausas, puntuación y longitud. La transcripción queda pendiente de cotejo de audio/nombres: ASR no es aprobación.
7. **Seguir el rostro.** `workflow.py rostro ID` conserva el seguimiento si existe. Si falta, genera un proxy temporal y usa el navegador/MediaPipe para obtener el rostro/barbilla. La presencia en split cuenta igual que en cámara completa.
8. **Crear el storyboard.** `workflow.py storyboard ID` prepara bloques alineados con la narración y deja vacíos objetivos, visual, animación, texto, recurso, sonido y transición para una decisión editorial. Si ya existe, exige editar el canónico.
9. **Seleccionar recursos frase por frase.** `seleccion.py crear ID` crea la ficha; el agente comprende la acción, función, situación y resultado, consulta ambas bibliotecas y preselecciona candidatos. `descargar` limita cada pasada a doce candidatos y deduplica. Deben verse en movimiento, escoger tramos y registrar evidencia, motivo y selección/descarte. `validar --hasta 10` verifica cobertura de la prueba; no aprueba todo el reel.
10. **Diseñar componentes y cronología.** El motor principal observado genera una composición HTML de 1080×1920, videos de fuente real, fuentes auténticas, componentes JavaScript/GSAP y cronología determinista. `composicion.py` es una composición específica de Agent Reach y rechaza otros IDs: no constituye un generador semántico universal. El montaje V5 necesita su composición propia.
11. **Renderizar únicamente diez segundos.** `render.py ID --muestra 10` valida manual, estilo, selección y preflight; captura HyperFrames a 30 FPS con un worker y mezcla audio con FFmpeg. El completo queda bloqueado por aprobación explícita de la prueba y cobertura del resto.
12. **Mezclar preservando la voz.** El audio original es el eje; el sistema puede aplicar filtro/normalización según proyecto, música con entrada elegida dentro del archivo, ducking por sidechain, SFX temporizados y limitador. Si la fuente termina antes de diez segundos, agrega silencio; no repite ni estira la narración. Los derechos de la música se registran.
13. **Auditar técnica y editorialmente.** FFprobe, decodificación y análisis de todos los fotogramas detectan problemas medibles. El agente además debe revisar movimiento, transiciones, rostro, texto, autenticidad, sincronización y pertinencia; las métricas no certifican calidad. La revisión sonora perceptiva debe distinguirse de niveles/ASR. El estado histórico reconoce que no hubo audición perceptiva por el agente.
14. **Aprobar y entregar con vigencia.** `aprobar` exige todos los controles, evidencias, cronología, escenas aprobadas y huellas coincidentes. `entregar` verifica permisos y reutiliza IDs/carpetas de Drive, publica solo lo aprobado y coteja tamaño/MD5. V5 se entrega como prueba y documentos; el procedimiento de final completo sigue bloqueado hasta nueva indicación.
15. **Limpiar descartes comprobados.** Se conservan originales, fuentes, recursos y aprobados. Solo pueden borrarse temporales o derivados descartados identificados. Cada hecho y siguiente acción se registra sin duplicar proyectos.

## Precedencia V5 observada en el snapshot inicial

V5 prevalece frente a proporciones o hooks anteriores. YO define identidad; AGENT, EDIT y CLONE elevan la técnica de motion. El montaje se diseña de nuevo para cada narración. Split inicial 55/45, una grabación original nítida, fondo auténtico, ninguna duplicación borrosa y rostro máximo tres segundos continuos, incluidos split/transiciones. Los subtítulos tradicionales se centran y siguen bajo barbilla; el hook usa una composición editorial fiel al discurso y no una transcripción automática. Después se usan bloques de dos o tres palabras por sentido y se mantiene representación textual durante b-roll salvo pausa justificada.

Las fuentes Sequel Sans Bold Disp y Scholar Italic son obligatorias en producción Ascendia; disponer del archivo no demuestra permiso de redistribución. Rojo semántico, sombra negra compacta, riser con culminación entre dos y seis segundos y transiciones con propósito. Un fade de tarjetas o logos estáticos no cumple motion avanzado: hacen falta acción, reacción, transformación y salida conectadas. La calidad se juzga viendo la secuencia.

Ascendia Studio debe ofrecer herramientas para cumplir esas reglas y guardar decisiones/evidencias. No debe afirmar que un plan automático ya alcanzó la identidad YO, que un b-roll apareció realmente sin comprobación ni que el audio se oyó sin audición.

## Regla de convivencia

Ascendia Studio escribe exclusivamente en `SOFTWARE/`, incluidos sus modelos, caches, temporales, estado, datos, proyectos y exportados. Lee los manuales canónicos del padre en modo de solo lectura y registra sus huellas; no crea otra fuente divergente del prompt. Los medios se importan por copia explícita al almacén propio. No importa `sistema/workflow.py`, no ejecuta la producción existente, no reutiliza sus temporales/credenciales, no publica en Drive y no cambia la terminal en marcha.

## Actualización posterior: CLONE, skills y prueba técnica

Snapshot de lectura del 12 de octubre de 2026, 23:45:31 UTC. Se releyeron completos AGENTS (32 líneas), PROMPT_MAESTRO (969), INSTRUCCIONES (149) y STYLE_YO (49). Se revisó completo `sistema/skills.py`, la auditoría declarada en `sistema/AUDITORIA_WORKFLOW.md`, el inventario `sistema/skills_instaladas.json` y las guías locales de entrada, core, animation, keyframes, registry y studio, el adaptador GSAP y las referencias de determinismo, estilo, composición y movimiento. Esta lectura de auditoría no registra aplicación de esas skills a un render de Ascendia Studio.

Huellas vigentes en este snapshot, distintas de las históricas de arriba:

| Documento canónico en IVAN | SHA-256 |
|---|---|
| AGENTS.md | `561a7cce0b486f97dd1c0926f969a9a0128ce65f259f2989df34716cde70fb9e` |
| PROMPT_MAESTRO.md | `3d02a5c313a34290007d2532370a666e3a1fb36922f1ac8ff0352378a64aade1` |
| INSTRUCCIONES.md | `7af7bc73e1f9ac2d57955319f85e91d2e3544ded1a98183a30f013367612f677` |
| STYLE_YO.md | `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39` |

La última modificación del prompt y la regla 19 prevalecen: **CLONE es la referencia exclusiva de motion graphics; YO conserva talking head, subtítulos y split**. AGENT y EDIT permanecen como historia de encargos anteriores. Continúan montaje específico por narración, split 55/45, rostro máximo tres segundos continuos, fondo auténtico, Sequel/Scholar reales, texto durante b-roll y selección contextual inspeccionada. El texto antiguo de STYLE_YO que menciona las tres referencias no desplaza esta indicación posterior.

El encargo técnico previo al siguiente reel exige tres segundos con HyperFrames y GSAP reales, varios elementos que interactúen, posiciones/escalas, máscaras, trayectorias y transformaciones sincronizadas. Debe entregar MP4 y código GSAP. Esta prueba acredita arquitectura; no sustituye la próxima muestra narrativa contextual de diez segundos ni concede autorización para un completo. El padre tiene archivos de `proyectos/arquitectura_motion_3s`, incluido MP4, timeline, diagnósticos y registro de skills. Se observó su existencia y metadata; esta auditoría no ejecutó el motor ni inspeccionó ese MP4, y no atribuye esos resultados a SOFTWARE.

`sistema/skills.py` exige doce guías: hyperframes, general-video, core, creative, animation, keyframes, audio, cli, registry, studio, media-use y motion-graphics. Su registro por proyecto enlaza manual, ruta, SHA del SKILL.md y hash del árbol completo, lectura real por agente, revisor, decisión concreta y evidencias con archivo/SHA. También verifica cinco referencias: adaptador GSAP, determinismo, house-style, video-composition y motion-principles. El gate de render exige consulta de catálogo, resultado guardado y decisión de reutilizar/construir; una plantilla pendiente no satisface estos controles.

La skill independiente `gsap` no figura entre las publicadas según el comprobante del padre: registra el fallo `No matching skills found for: gsap`; la guía es keyframes más el adaptador GSAP. No equivale a ausencia de la biblioteca GSAP. El actualizador de skills importa el workflow del padre y ejecuta Node; SOFTWARE debe implementar su propia lectura de archivos y sus propios registros, sin importar ni ejecutar ese actualizador. La auditoría del padre registra un incidente previo de copias globales y su corrección; no se repitió esa operación ni se verificaron aquí los globales.

Para reflejar los requisitos nuevos en SOFTWARE:

1. Actualizar el preset y las tareas para separar YO identidad de CLONE motion; conservar evidencias anteriores con sus fechas y huellas, invalidando nuevas promociones cuando cambien manual, guías, medios o código aplicable.
2. Ofrecer un inventario de las doce fuentes locales de IVAN en solo lectura y una plantilla propia de aplicación por proyecto en SOFTWARE. Lectura, decisión, referencias y pruebas deben completarse conscientemente; calcular hashes o imprimir documentos no constituye lectura ni aplicación.
3. Mantener un estado explícito de integración HyperFrames pendiente. Los frames Pillow/FFmpeg actuales y un video existente del padre no prueban que Ascendia Studio cargue GSAP, registre una timeline o ejecute HyperFrames. Los diagnósticos del padre se pueden citar como procedencia externa, sin marcar operativo un adaptador propio ausente.
4. Cuando exista adaptador propio, exigir una timeline pausada registrada tras completarse con el mismo `data-composition-id`, duración fija, assets/runtime locales y estados deterministas. Registrar versiones y SHA de HTML, JS y GSAP; exigir check con navegador ejecutado (`browserSkipped:false` y muestras reales), keyframes, poses de prueba y revisión del MP4 decodificado. Un check estático con cero muestras no aprueba la arquitectura.
5. Mantener la prueba técnica de tres segundos y la revisión narrativa de diez segundos como etapas distintas. Los controles técnicos y registros de skills no aprueban por sí solos fidelidad CLONE/YO, pertinencia ni audición.
6. Aislar cualquier instalación, cache y diagnóstico propio en SOFTWARE/.estado, respetar la exclusión CPU local y conservar la GPU/proceso del padre. No copiar sus credenciales ni modificar su fuente de skills, sus registros, estado, artefactos o prueba técnica.

Estos puntos documentan la adaptación necesaria. No declaran ejecutada una integración HyperFrames de Ascendia Studio ni reinterpretan sus pruebas sintéticas anteriores como cumplimiento retroactivo.

## Continuidad observada al cerrar la construcción

Lectura del 13 de octubre de 2026 a las 00:00:04 UTC (12 de octubre en Bogotá):
el estado del padre, actualizado a las 23:43:40 UTC, registra
`arquitectura_verificada_y_entregada`, proyecto `arquitectura_motion_3s` y
«Prueba técnica 3 s entregada; no se produjo otro reel completo». Su siguiente
acción es revisión del usuario de MP4/timeline; después, un nuevo crudo con
muestra narrativa de diez segundos y autorización pendiente del completo.
Son hechos declarados en `../ESTADO.json`, conservados en el snapshot privado
de SOFTWARE. No se repitió la comprobación del render, Drive o GPU del padre,
ni se convirtió su prueba en evidencia de un adaptador de Ascendia Studio.

## Tercer snapshot: diseño CLONE antes de cualquier animación

Lectura completa del 13 de octubre de 2026 a las **00:10:29 UTC** (12 de octubre, 19:10:29 en Bogotá): AGENTS 33 líneas, PROMPT_MAESTRO 979, INSTRUCCIONES 151 y STYLE_YO 49. Las fuentes de esta nueva precedencia son la regla 20 de `../AGENTS.md`, la última sección «componente CLONE, diseño antes de animación» de `../PROMPT_MAESTRO.md` y el alcance inicial/paso 9 de `../INSTRUCCIONES.md`.

| Documento canónico en IVAN | SHA-256 de este snapshot |
|---|---|
| AGENTS.md | `0492f5c98c87f61d65c6fc183781de2edb6266b3f1064f11b63d5907fc34ad73` |
| PROMPT_MAESTRO.md | `b318b5e350135c59cfe11bae39713474970259c116be245d0c5da809c976cca7` |
| INSTRUCCIONES.md | `c928dae2ddc411c044db9efae2ebf75c3dff1c58d7b1dd21418ae2f44c8c79ac` |
| STYLE_YO.md | `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39` |

**La indicación más reciente da por comprobada la arquitectura GSAP y prohíbe repetir sus pruebas genéricas.** El snapshot de 23:45 y la regla 19 conservan el encargo anterior. Las menciones residuales a «prueba técnica 3 s» en pasos anteriores del manual no desplazan la regla 20 ni el nuevo alcance inicial. No se reescriben los resultados históricos para simular cumplimiento de requisitos posteriores.

El trabajo actual de la producción paralela tiene tres fases:

1. **Diseño visual estático.** Analizar exclusivamente CLONE entre 1,6 y 3,2 s; reconstruir un fotograma representativo respetando composición, tipografía, colores, paneles, espaciado, sombras y elementos reales. Entregar PNG reconstruido y PNG comparativo con la referencia. No sustituirlo por rectángulos genéricos. Esta fase espera aprobación explícita del diseño; no autoriza animación.
2. **Animación del diseño aprobado.** Solo después de esa aprobación, reproducir con GSAP/HyperFrames los cambios de estado, movimientos y transiciones observados, conservando la geometría, colores, fuentes y elementos del diseño aceptado.
3. **Validación comparativa.** Comparar referencia y reconstrucción en instantes equivalentes y evaluar por separado fidelidad visual, movimiento, ritmo y continuidad. Después de aprobar el componente, volver al sistema completo con talking head YO, split 55/45 y motion CLONE. La aprobación del componente no autoriza por sí sola el reel completo.

No se instalaron herramientas, no se extrajeron fotogramas ni se generó/animó este componente durante esta auditoría. La reconstrucción CLONE corresponde al otro proceso. Las pruebas de regresión y laboratorios genéricos de SOFTWARE comprueban las herramientas del editor con sus propios datos; no repiten el encargo de arquitectura GSAP, no producen el componente CLONE y no constituyen su aprobación. La evidencia externa de GSAP tampoco instala un adaptador dentro de Ascendia Studio.

Para una futura integración de este flujo en SOFTWARE, el paso previo a animar debe enlazar la **aprobación explícita con el SHA del diseño estático**. El registro debería conservar la instrucción de aprobación, fecha/revisor, referencia y tiempo del fotograma, hashes del PNG reconstruido/comparativo y una descripción canónica del diseño con geometría, fuentes, colores, paneles y assets. Cambiar ese diseño o sus fuentes/recursos invalida la aprobación para una nueva animación. Una casilla en JSON, un hash o una prueba técnica no sustituyen la indicación del usuario; el software no debe inventarla ni usar un aprobado de otro componente.

La animación necesita su propia evidencia de que conserva el diseño aprobado. Su auditoría debe distinguir:

| Dimensión | Evidencia necesaria |
|---|---|
| Fidelidad visual | Referencia y reconstrucción alineadas: composición, tipografía, colores, espaciado, sombras y elementos |
| Movimiento | Estados, trayectorias, máscaras, transformaciones, interacciones y sus transiciones en secuencia |
| Ritmo | Tiempos y duraciones comparados en instantes equivalentes del segmento original |
| Continuidad | Fotogramas consecutivos y transiciones sin saltos, parpadeo, sustituciones arbitrarias o cambios del diseño aceptado |

La correlación entre HTML y su MP4 comprueba integridad del propio render; no mide semejanza con CLONE. Los resultados técnicos y los juicios editoriales permanecen separados y no se convierten automáticamente en aprobación. Este tercer snapshot actualiza la interpretación del manual; no declara implementado ese nuevo gate de diseño ni un renderer HyperFrames en SOFTWARE.

Una relectura completa de INSTRUCCIONES a las 00:17:49 UTC confirmó la misma
precedencia y reconciliaba sus dos líneas históricas pendientes: diseño estático
y dos PNG antes de animar. Su SHA-256 pasó a
`78119c339487036aeeed64f5e802e706a14fa8c212587c6e28856834d442a4bf`.
AGENTS, PROMPT_MAESTRO y STYLE_YO conservaron los hashes del tercer snapshot.
Esta actualización no acredita realización ni aprobación del componente.

A las 00:19:24 UTC, una lectura de `../ESTADO.json` registró
`diseno_estatico_pendiente_aprobacion`, proyecto activo `clone_componente`,
actualizado a las 00:17:48 UTC. Su siguiente acción declarada es esperar
aprobación explícita del diseño antes de construir la timeline GSAP/HyperFrames.
No se revisaron ni aprobaron aquí sus PNG. La sesión Codex seguía viva y el
original de Testeo Reels conservó el SHA-256 de la lectura inicial.

## Snapshot del 2026-10-13T01:47:29Z — diseño revisión2 aprobado en el proceso padre

Se releyeron completos los cuatro documentos canónicos: AGENTS36 líneas, PROMPT988, INSTRUCCIONES151 y STYLE49. La regla22 autoriza al proceso padre a animar el diseño estático CLONE revisión2, preservando SVG/PNG por SHA y reconstruyendo únicamente1,6–3,2s. Debe entregar MP4, editable y comparación animada a tiempos equivalentes. No autoriza reel completo ni rediseño. Este software no ejecuta el encargo paralelo ni hereda su aprobación.

El ESTADO observado aún decía segunda_pasada_estatica_pendiente_aprobacion/clone_componente; la instrucción canónica posterior prevalece. La terminal Codex PID2392456 estaba viva y no recibió señales ni teclas. El proceso de reel Testeo Reels mantenía su proyecto canónico separado.

- AGENTS.md: `4ce41d0604af283250adf048bea2b44c1fe96eadec018df15e951cb458aaa19b`.
- PROMPT_MAESTRO.md: `91a7f9d61c9a9efcb5805370bb93b64e78cce8f04e07671d435fd1d2d1805f5a`.
- INSTRUCCIONES.md: `a722e644917efe8f3719b3d4204c2332ef42dc54cbe588fd26b0b18dee75c4b9`.
- STYLE_YO.md: `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39`.


## Snapshot vigente: biblioteca generativa CLONE, regla23

Lectura completa registrada el 13 de octubre de2026,02:54:11UTC: AGENTS38líneas,
PROMPT_MAESTRO1003, INSTRUCCIONES151 y STYLE_YO49. La última directiva del manual
cambia el encargo paralelo a etapas A–F: inventario completo de secuencias,
sistema visual, familias parametrizadas, SceneIR, generación semántica y nuevo
concepto validado. Permite render y batch de biblioteca sin aprobación por cada
pieza, con QC individual y registro de fallos. Conserva el CANCELLED aprobado.
Excluye AGENT/EDIT, b-roll, stock y relleno estático de ese motor. YO/split55/45
quedan como contratos futuros; no se autoriza montar un reel completo.

El alcance de SOFTWARE permanece independiente. Su adaptador SceneIR recibe
contenido/acciones/geometría explícitos y los convierte a composición editable.
No sustituye el inventario, las familias ni el generador semántico que se está
construyendo en el padre. No ejecuta sus scripts, no modifica sus proyectos y
no hereda la aprobación de CANCELLED. Los snapshots anteriores y sus renders
mantienen sus fechas/hashes; no se atribuyen a esta nueva directiva.

Huellas SHA-256 de la lectura vigente:

- AGENTS.md: `a1bcf333eee20dd96b7c8f4a8087f6e2f4faa96a805bf841463b780f6ebcdb7b`
- PROMPT_MAESTRO.md: `254743f544706f998b296b6162963b172fc2712979d9d717895687487f5610c7`
- INSTRUCCIONES.md: `e228cf600126855e3b09ba94f885726485431d80e1872a9acf5cf5bba82042ce`
- STYLE_YO.md: `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39`


### Estado observado del proceso paralelo,03:15:25UTC

Comprobación independiente solo lectura: PID2392456, proceso codex vivo, estado
Sl+, tiempo transcurrido05:04:58. No se leyeron argumentos ni entorno y no se
le enviaron señales/teclas. En sistema/clone y proyectos/clone_motor se observa:

1. A: inventario de18secuencias, frames0–1269/42,3s, cobertura sin huecos;
   el SHA del CLONE fuente coincide con el registro.
2. B: sistema visual y documentación existentes,37assets actuales.
3. C:14familias en5módulosJS más CANCELLED reutilizable:15definidas.
   Hay14MP4 cuyos SHA coinciden con14QC. terminal_install tiene HTML/SceneIR/
   timeline/QC pero todavía no MP4. Todos requieren revisión visual real.
4. D–F: parámetros, ejemplos, compiler SceneIR y CLI existen; no se observó
   salida de generador semántico, demo_nueva, galeria.html ni registro final.
   Tres revision_timelines declaraban ok=false/seek=false.

ESTADO global aún señalaba el componente anterior esperando usuario, mientras
el proyecto clone_motor marcaba faseC/biblioteca_en_validacion. El batch mantenía
problem_resolution pendiente pese a existir MP4/QC: son registros de un proceso
en movimiento, no una fuente suficiente para declarar final. SOFTWARE conserva
esa divergencia como observación y no modifica ningún estado del padre.
El crudo original mantuvo SHA
`ffe94d66d50ef7cd1e570a30c882a24b4286f7c9309cecc3215d17466614351c`.
La evidencia está en .estado/validacion/parent_readonly_final.json de SOFTWARE.


## Snapshot v0.4 — letras y directiva B_V2

Los cuatro manuales se releyeron completos con el prompt de1025 líneas, incluyendo
la regla25. El padre debe mejorar B_V2 conservando estructura/componentes de B,
quince familias y CANCELLED; conservar B_V1 para comparar. No generar tres demos
adicionales ni integrar YO. Ese encargo no se ejecuta desde SOFTWARE.

El estado leído a 2026-10-13T19:01:47.762662+00:00 registra `B_V2_revisado_pendiente_usuario`,
proyecto `clone_motor`; su siguiente acción declarada es revisar B_V2 por el
usuario, sin integrar YO ni generar otras demos antes de su indicación. El campo
alcance conserva aún una descripción histórica de las tres pruebas. No se
revisaron aquí sus MP4 ni se cambió su estado. Snapshot privado:
`.estado/validacion/parent_snapshot_v04.json`.

SOFTWARE añade únicamente tipografía local, estilos y animaciones deterministas
con sus propios medios sintéticos y QA. Su prueba de nueva funcionalidad no
repite la arquitectura GSAP del padre ni aprueba B_V2 o un reel de Iván. El
servidor reiniciado es exclusivamente el de SOFTWARE; el Codex del padre se
observa por lectura y no recibe señales/teclas.

Las huellas de esta lectura son:

| Documento | SHA-256 |
|---|---|
| AGENTS.md | `21bac8a0d3459d2bc3e27cccc73bd4a2249544a32298b12640d5649176fd58f7` |
| PROMPT_MAESTRO.md | `6b93c06fa53034add28efdf3fa6ef877fb6d84bf6658e5d1346c62c77099d5b3` |
| INSTRUCCIONES.md | `4c67397913147852f3ce05d52edd3b361b58bfe2f751e625ee99d96bbefc3dca` |
| STYLE_YO.md | `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39` |
