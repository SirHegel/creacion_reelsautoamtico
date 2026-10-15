# Auditoría final del sistema de IVAN

Última indicación: CLONE es referencia exclusiva de motion graphics; YO conserva talking head, subtítulos y split. Alcance actual: prueba técnica de 3 s; ningún reel completo nuevo está autorizado. La prueba narrativa V5 conserva su historial, MP4 y recibos originales.

## Skills y motores: hechos comprobados

HyperFrames 0.8.147 y GSAP 3.15.0 sí ejecutaron el V5: `sistema/render.py`, `sistema/motion.js`, `sistema/componentes_motion.js` y `.estado/tmp/render.log`. No existía un registro explícito de lectura/aplicación previa de skills; esta auditoría no lo atribuye retrospectivamente.

Se actualizaron las guías oficiales y se mantienen 12 skills en una única fuente de proyecto `.agents/skills`, legible desde IVAN: hyperframes, general-video, core, creative, animation, keyframes, audio, cli, registry, studio, media-use y motion-graphics. `sistema/skills_instaladas.json` registra rutas, fuentes, hashes y la comprobación real de actualidad. El resultado fue 12 actuales, cero core ausentes y cero desactualizadas; los otros nueve workflows publicados son géneros opcionales, no faltantes del sistema de reels.

El comando solicitado para `--skill gsap` fue ejecutado y devuelve `No matching skills found for: gsap`. La guía oficial vigente es `hyperframes-keyframes`, más el adaptador `hyperframes-animation/adapters/gsap.md`. GSAP como biblioteca ya estaba instalado; no se reinstaló el motor. La skill core es una guía, no el paquete SDK `@hyperframes/core`; los scripts opcionales que necesitan ese SDK no se declaran operativos.

La lectura actual se repartió entre el director y dos auditores: director —core, creative, animation, keyframes, adaptador GSAP y referencias de determinismo/composición/movimiento—; auditor de estabilidad —hyperframes, cli, registry, studio y contratos de verificación—; auditor de recursos —general-video, motion-graphics, media-use, audio y contratos de resolución/narración/mezcla—. Sus observaciones se contrastaron con el prompt completo V1/V3/V4/V5 y las últimas modificaciones.

## Cobertura de requisitos y controles

| Requisito vigente | Aplicación y evidencia | Control para futuros proyectos |
|---|---|---|
| Leer todo el prompt y sus correcciones | AGENTS/PROMPT/INSTRUCCIONES completos, huellas por proyecto | Cambios invalidan futuras promociones; no reescribir evidencia histórica |
| YO identidad; CLONE movimiento | STYLE_YO y fotogramas secuenciales de CLONE 0,60–3,60 s | Decisión explícita en storyboard; no reutilizar la prioridad histórica AGENT |
| Skills reales, leídas y aplicadas | 12 guías locales verificadas; lectura actual por auditores | Registro `skills_aplicadas.json` comienza pendiente; requiere decisiones y evidencia, no solo instalación |
| GSAP dentro de HyperFrames | Prueba técnica en `ejemplos/arquitectura_motion_3s` | Timeline pausada registrada, plugins locales, check/keyframes y MP4 real |
| Confinamiento y conflictos globales | `skills_entorno.mjs`, auditoría de rutas/hashes | Aislamiento heredado por procesos hijo; escrituras externas bloqueadas; no alterar otros proyectos |
| Herramientas y GPU | Preflight: siete motores locales operativos; Tella retirado por usuario | CUDA/Chrome GPU/NVENC solo para tareas compatibles; no llenar RAM sin finalidad |
| Voz y cortes originales | V5 conserva la voz; crudo 7,918 s y cierre visual hasta 10 s | No TTS ni guion inventado; alargar solo imagen si se autoriza |
| B-rolls reales del cliente | Tres clips V5 cotejados; inventario, selección y CSV | Acceso a ambas bibliotecas, descarga selectiva, revisión visual y tramos por frase |
| No infografías estáticas | V5 y prueba técnica contienen acciones conectadas | Storyboard con acción→reacción→transformación→salida; rechazo editorial de fades como única acción |
| Hook sin transcripción automática | V5 frase acumulada como YO; fuentes reales | Primera escena contextual; no palabra aislada por obligación |
| Rostro breve y split auténtico | V5: 19 %, máximo 1,3 s, split 55/45 | Unión común de intervalos; clip/split/transición no reinician presencia |
| Subtítulos bajo barbilla, centrado, fuentes y sombra | Seguimiento MediaPipe y comparación YO; Sequel/Scholar reales | Inspección visual de estados y encuadres; checklist completo antes de entrega |
| Rojo semántico y contraste | V5 riesgo/obstáculo; no títulos rojos arbitrarios | Revisión de significado y contraste; marcas conservan colores oficiales |
| Zoom y transformaciones rápidas | Duraciones explícitas en timelines | Keyframes y capturas de estados; no asumir velocidad por un único fotograma |
| Riser, woosh, música y burn | Mezcla V5, alineación, ducking y Screen | Conservar voz prioritaria; sincronizar impactos; no agregar sonido intenso a todo elemento |
| Estabilidad del borde y no parpadeo | V5 300 frames + auditor independiente; prueba técnica 90 frames | Temporal y estabilidad ligados al SHA del render; todos los frames revisados |
| Recursos y datos auténticos | Bibliotecas autorizadas; diagramas etiquetados conceptuales | No presentar esquemas como software ejecutado ni inventar métricas/licencias |
| Editable, manifest, comparativas e informe | Entrega V5 verificada por tamaño/MD5; ZIP íntegro 105 archivos | Paquete atómico y cobertura/CRC antes de subir; IDs reutilizados |
| Orden y continuidad | Una fuente de instrucciones y un proyecto por original | ESTADO registra etapa real; preservar originales y limpiar solo derivados propios |

## Defectos del workflow corregidos en esta auditoría

1. Se unificó el cálculo de presencia: las muestras ahora unen clips contiguos/solapados y recortan al alcance real; antes podían aceptar más de 3 s consecutivos repartidos en varios clips.
2. La muestra ahora incorpora el resultado temporal en sus comprobaciones; su publicación exige auditoría temporal y estabilidad vigentes, evidencia existente y todos los criterios editoriales.
3. El hash de edición incluye `recursos/gsap.min.js`; cambiar el runtime invalida una auditoría anterior.
4. El render dispone de exclusión mediante lock; dos jobs ya no pueden pisar `muestra.html`, `imagen.mp4` o la NVIDIA de este workflow.
5. El registro de skills bloquea renders sin lectura, decisiones y evidencia actuales. `check` debe ejecutar el navegador y muestras: `browserSkipped:true` o cero muestras no aprueban nada.
6. Se adaptaron los comandos a la CLI instalada: check admite un directorio; keyframes admite HTML. Las rutas de recursos se comprueban realmente. La prueba técnica coloca registro GSAP explícito en el HTML compilado desde el JS editable para que el auditor estático pueda leerlo.
7. Se acortó el alias de temporales de Chrome sin sacar ningún archivo de IVAN; evita el fallo `Socket path too long`. El aislamiento se propaga a npm y procesos Node hijo.

## Límites que se conservan explícitos

- La sofisticación, fidelidad a YO/CLONE, pertinencia, ortografía y significado del rojo siguen requiriendo revisión editorial. Una skill instalada o un check técnico no certifican gusto visual.
- La auditoría anterior de audio mide conservación, correlación, picos y reproducción; no consta escucha perceptiva del agente. No se declara una escucha inexistente.
- El reconocimiento V5 de b-roll compara un instante/ROI por recurso y se acompaña de revisión secuencial; no demuestra cada segundo de cada clip ni todas las afirmaciones del narrador.
- El editable V5 es código; la mezcla audiovisual completa reside en el MP4. Studio no se presenta como timeline de audio separada si no la contiene.
- `keyframes --layout strip` de la CLI instalada no siempre produce película de píxeles para selectores DOM. Para detectar corrupción se revisa el MP4 decodificado completo.
- El check añadido detectó que el HTML V5 remite el registro de timeline a un JS externo y su analizador estático no lo reconoce; devolvió error y omitió el navegador. No se convierte ese fallo en aprobación ni se modifica el exportado histórico. La arquitectura de la prueba técnica usa registro explícito verificable; una nueva edición deberá satisfacer el gate actualizado.
- El primer actualizador creó además 11 copias globales de skills. Se retiraron únicamente sus copias recientes idénticas; no se eliminaron dependencias ni archivos ajenos. Se corrigió herencia de aislamiento. Las comprobaciones posteriores son de lectura y no modifican dependencias globales. El detalle de ese incidente está en `.estado/tmp/skills_aislamiento.json`.

La prueba técnica acredita la arquitectura de animación; no aprueba un reel completo ni reemplaza la próxima prueba narrativa contextual de 10 s.
