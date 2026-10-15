> Plantilla pública desidentificada. Las referencias y autorizaciones históricas describen un flujo de ejemplo; configure insumos y accesos propios. Los medios, transcripciones y comprobantes privados no se distribuyen.

# IVAN — instrucciones operativas vigentes

Este archivo organiza el trabajo. Antes de analizar, editar o renderizar un reel, leer completos `AGENTS.md`, `PROMPT_MAESTRO.md` —incluidas todas sus modificaciones— y este archivo. El resumen no sustituye el prompt. Prevalece la última instrucción del usuario; Tella está excluido.

**Alcance actual: PRODUCCIÓN COMPLETA V1.0 del crudo `demo_produccion`.** Reel entero sin alterar narración, velocidad, orden, cortes válidos ni duración. Autorizadas todas las escenas, iteraciones internas justificadas, render completo y entrega para revisión sin aprobación parcial. No nuevas pruebas aisladas ni arquitectura/instalaciones. YO define identidad/cámara/subtítulos; CLONE motion exclusiva. Preferir split_first50/50 desdeF0, permitir55/45 según encuadre y adaptar otras apariciones. Protagonista pertinente, logos auténticos del registry sobre contraste neutro, lectura suficiente, subtítulos centrados/bajo barbilla y fuente/sombraYO. Cámara original≤3s continuos incluyendo split, sinblur/fondos artificiales. Movimiento suave, estados conectados y familias elegidas semánticamente por planner real; no usarcomposition_graph para todo por defecto. Sin b-roll/stock/relleno estático. Analizar y transcribir TODO, diseñar storyboard completo, montar, mezclar voz/recursos existentes autorizados, renderizar todos losframes y revisar en movimiento/sonido; corregir errores antes de entrega. Entregar ascendia_reel_final.mp4, editable compacto, storyboard final e informe. Conservar V1/V2/V3/CANCELLED/15familias y todos los proyectos anteriores. Manual actual de17apartados en PROMPT_MAESTRO.md, regla29 deAGENTS prevalece sobre restricciones históricas de solo muestras.

CLONE conserva prioridad exclusiva de motion; YO define talking head, subtítulos y split. Conservar correcciones compatibles: montaje por crudo, rostro≤3s, fondo auténtico, hook integrado y fuentes. Las reglas históricas de búsqueda/cuotas de b-roll, componentes estáticos previos a aprobación y muestras previas al completo no se aplican a este encargo autorizado completo. AGENT/EDIT y pruebas genéricas quedan como historia. Nunca reinstalar o eliminar dependencias globales.

## Paso a paso permanente y skills del proyecto

1. Leer completos AGENTS, PROMPT_MAESTRO con todas sus modificaciones e INSTRUCCIONES. Resolver conflictos por la última indicación: producción completa sin aprobar cada escena ni otra muestra; CLONE motion, YO identidad, Tella excluido. Arquitectura ya comprobada; usar componentes aprobados y corregir por instancia, sin reconstruir biblioteca. Guardar el manual vigente y su huella antes de inferir/editar/renderizar.
2. Usar las skills locales ya instaladas en `.agents/skills`; no actualizarlas ni reinstalarlas por rutina, y no instalar nada en este ejercicio. Si otro encargo autoriza mantenimiento, `python3 -B sistema/skills.py actualizar` es el equivalente aislado de `npx hyperframes skills update general-video motion-graphics`, conservando la CLI. La skill llamada `gsap` no existe en la publicación comprobada: leer `hyperframes-keyframes` y el adaptador oficial GSAP. No declarar instalada una skill ausente.
3. Leer los 12 SKILL.md aplicables y sus referencias necesarias. Router: hyperframes; reel narrado: general-video; escena técnica sin voz: motion-graphics. Dominios: core, creative, animation, keyframes, audio, cli, registry, studio y media-use. No convertir un reel narrado en un workflow sin voz. No forzar TTS, todos los runtimes, efectos o contadores cuando no sirven al contenido.
4. Registrar por proyecto con `python3 -B sistema/skills.py preparar ID`: lectura real, revisor, archivo/hash de la skill, decisión concreta, referencias y evidencia de aplicación. La plantilla comienza pendiente: instalar/imprimir/hacer hashes no acredita comprensión. `python3 -B sistema/skills.py validar ID` exige el registro y sus pruebas actuales antes del render.
5. Verificar herramientas locales con preflight; inventario/accesos y originales con los comandos posteriores. No reinstalar motores ya operativos. Usar CUDA para Parakeet, GPU de Chrome y NVENC para render. Los renders se serializan por lock para no pisar temporales. RAM/VRAM se asignan al trabajo útil, sin llenarlas por obligación.
6. Analizar narración, palabras y tiempos; conservar voz/cortes. Analizar visualmente YO y CLONE en secuencias; localizar originales antes de exports. Storyboard semántico por escena, con composición inicial, acción, reacción, transformación, salida, b-roll, texto y sonido. No reutilizar el guion de otro reel.
7. En esta producción NO buscar ni descargar b-roll/stock. Consultar assets/15familias CLONE y Brand Asset Registry según narración; inspeccionar componentes pertinentes, registrar origen y uso real. Usar sonidos existentes contextuales y música solo con licencia comprobada. Fuentes oficiales de marcas únicamente si falta una identidad pertinente y revisar condiciones; no presentar interfaces conceptuales como demos reales.
8. Consultar catálogo en inglés con CLI aislada antes de implementar motion; guardar consulta, resultados y decisión de reutilizar o construir. Una plantilla de tarjetas estáticas no cumple aunque la proporcione un catálogo.
9. Storyboard semántico completo antes del montaje; composición inicial→acción→reacción→transformación→permanencia→salida conectada. Timeline GSAP pausada/determinista con duración fija; sin relojes/timers/red para gráficos durante render. Preservar recursos/componentes aprobados y sus fuentes; adaptar instancias y combinaciones al nuevo guion. Movimiento suave y legible (parámetros nuevos0,2–0,4/0,35–0,7/0,5–1/0,7–1,3/0,3–0,6s según acción), no fades como solución principal ni miniaturas/etiquetas invisibles. No pedir aprobación por escena ni prueba genérica.
10. Antes del render completo, ejecutar check/keyframes conCLI0.8.147 y exigir navegador con muestras (`browserSkipped:false`). Abrir proyecto y revisar estados/transiciones; audio se conserva o mezcla de manera explícita enFFmpeg según recursos/condiciones. La autorización del reel completo ya existe: continuar sin aprobaciones parciales, respetando revisión y corrección integral.
11. Renderizar solo el alcance autorizado. Decodificar todos los frames del MP4 y revisar tiras consecutivas, límites, rostro, fuentes, sombras, rojo, lectura móvil, audio, pertinencia y transformaciones. Calcular presencia uniendo intervalos contiguos/solapados, incluyendo split. Exigir temporal y estabilidad vinculados al SHA del MP4 y revisión editorial de todos los criterios. No presentar niveles/correlación como escucha perceptiva ni pruebas puntuales de b-roll como verificación de cada segundo de su contenido.
12. Empaquetar editable de forma atómica y verificar cobertura/CRC antes de subir. Publicar solo entregables revisados en ENTREGA, reutilizar IDs, comprobar tamaño/MD5 y guardar recibo/estado. Mantener un final por prueba y sus fuentes; conservar originales e historia autorizada. Una actualización de guías/manual/código invalida nuevas promociones de renders anteriores: no reescribir las auditorías históricas para fingir aplicación retroactiva.

La auditoría de cobertura y las excepciones verificadas están en `sistema/AUDITORIA_WORKFLOW.md`; disponibilidad/hash/fuente en `sistema/skills_instaladas.json`. El workflow bloquea el render si no existe aplicación documentada de las skills. La revisión estética sigue requiriendo inspección del agente; ningún checklist certifica por sí solo equivalencia con CLONE/YO.

## Accesos autorizados

| Uso | Carpeta verificada |
|---|---|
| Raíz: Edición con IA | https://example.invalid/recurso |
| Originales: Crudos | https://example.invalid/recurso |
| Finales: ENTREGA | https://example.invalid/recurso |
| B-rolls dinámicos y cinematográficos | https://example.invalid/recurso |
| B-rolls de software y herramientas | https://example.invalid/recurso |
| Música | https://example.invalid/recurso |
| Transiciones | https://example.invalid/recurso |
| Efectos de Sonido | https://example.invalid/recurso |

La biblioteca de software es un acceso adicional autorizado; no afirmar que es hija de Edición con IA. El Doc «Prmopt Edicion video» de esa raíz contiene V1.0: leerlo al revisar cambios, conservando las correcciones V3 y posteriores. Las seis referencias y sus enlaces están en el prompt y el catálogo.

## Selección obligatoria de b-rolls por contexto

1. Transcribir y comprender cada frase completa: acción, herramienta, situación, resultado, emoción y objetivo narrativo. Cambiar de tema requiere una nueva selección; el guion de un proyecto anterior no se reutiliza para otro reel.
2. Actualizar el inventario de todas las subcarpetas y archivos autorizados, con paginación completa. Consultar tanto b-rolls dinámicos como software. Nombres, categorías y miniaturas sirven para preseleccionar; no demuestran qué ocurre en todo un clip.
3. Escoger pocos candidatos relacionados con la frase y registrar por qué. Si los nombres son numéricos u opacos, abrir miniaturas o una vista previa; no descartar una carpeta sin examinar candidatos pertinentes.
4. Descargar únicamente los candidatos preseleccionados para ese reel. Ver el contenido y su movimiento, medir duración/resolución/FPS y escoger un tramo concreto. No descargar toda la biblioteca ni insertar recursos sin inspección visual.
5. Registrar por bloque narración, carpeta consultada, candidatos, contenido observado, selección o descarte, motivo semántico, ID/enlace, hash, evidencia y tramo. Reutilizar archivos idénticos del catálogo; mantener una sola copia local de cada recurso utilizado.
6. Priorizar demostración real de la función → recurso contextual de las bibliotecas → motion específico que explique mejor → cinematográfico contextual → IA justificada. Usar b-roll dinámico cuando represente la situación o acción; no sustituirlo por tarjetas por comodidad. Un logo no es una demostración.
7. Herramienta y función concretas: mostrar su acción auténtica. Negocio/investigación/trabajo digital: buscar esa actividad en CINEMATICS y DOPAMINA. LUXURY solo cuando la narración justifique ese contexto. La categoría orienta la búsqueda; el clip visto determina la elección.
8. Si una animación explica mejor una idea abstracta o ningún candidato sirve, documentar la búsqueda y la razón específica. No imponer clips genéricos ni una cuota de b-roll que perjudique el significado. No presentar metáforas, simulaciones ni cifras del narrador como demostraciones verificadas.

## Workflow y agente de recursos

El usuario autoriza un agente de recursos para este workflow y futuros reels. Asignarle la selección contextual con transcripción, tiempos, intención de los bloques, estas instrucciones y el inventario. Debe consultar las carpetas pertinentes, proponer candidatos con motivos y revisar los descargados. El director revisa la correspondencia antes de integrarlos. El agente no descarga toda la biblioteca ni aprueba una edición solo por nombres o palabras clave. Si la colaboración no está disponible, el director ejecuta y registra los mismos pasos, sin afirmar una delegación inexistente.

Ejecutar desde IVAN:

```bash
python3 -B sistema/workflow.py manual
python3 -B sistema/skills.py actualizar
python3 -B sistema/preflight.py
python3 -B sistema/bibliotecas.py actualizar
python3 -B sistema/workflow.py crudos --ingestar
python3 -B sistema/workflow.py transcribir ID
python3 -B sistema/workflow.py rostro ID
python3 -B sistema/workflow.py storyboard ID
python3 -B sistema/skills.py preparar ID
# Leer guías y completar aplicación/evidencias por proyecto antes del diseño y render.
python3 -B sistema/seleccion.py crear ID
# Completar la preselección semántica en seleccion_recursos.json.
python3 -B sistema/seleccion.py descargar ID
# Ver los clips y completar el análisis y las decisiones por bloque.
python3 -B sistema/seleccion.py validar ID
python3 -B sistema/skills.py validar ID
# Diseñar las escenas desde el material y los recursos elegidos.
python3 -B sistema/render.py ID --muestra 10
# Corregir la prueba de 10 s, entregarla y registrar la aprobación explícita del usuario.
# El completo sigue bloqueado mientras la prueba no esté aprobada y falten escenas.
python3 -B sistema/render.py ID
python3 -B sistema/workflow.py auditar ID
# Registrar revisión editorial, evidencias y escenas aprobadas.
python3 -B sistema/workflow.py aprobar ID
python3 -B sistema/workflow.py entregar ID
```

`recursos/inventario_drive.json` contiene todo lo disponible; `recursos/catalogo.json`, los recursos locales y análisis comprobados; `proyectos/ID/seleccion_recursos.json`, las decisiones de ese reel. Ningún hash sustituye leer el contenido ni verlo. Un cambio en instrucciones, decisiones o recursos invalida la revisión anterior. El render y la publicación requieren selección contextual documentada.

En la selección, cada candidato registra `drive_id`, `motivo_contextual`, archivo y hash. Tras verlo, completar `analisis_visual` con estado `revisado`, `contenido_observado` y rutas de `evidencias`. La decisión `tipo: broll` indica su ID, `tramo_s: [entrada, salida]` y motivo contextual. Para `motion`, `presentador` o `tipografia`, documentar el `resultado_busqueda` que justifica elegir esa representación. Para la prueba inicial, marcar `revisada_para_prueba`, `alcance_hasta_s: 10` y validar con `python3 -B sistema/seleccion.py validar ID --hasta 10`. Esto no aprueba el reel completo. Solo marcar `revisada_contextualmente` después de completar todos los bloques. Marcar `descargar: true` únicamente en los pocos candidatos elegidos para examinar; la descarga limita cada pasada a 12 y desactiva solicitudes ya atendidas.

Si falta una demostración adecuada, investigar con Playwright MCP en una fuente oficial y capturar solo con acceso y permiso de uso. Registrar `tipo: demo_externa`, URL, `fuente_tipo: oficial`, derechos, archivo de `registro_captura`, tramo, evidencia visual y resultado de la búsqueda previa en las bibliotecas. No confundir una captura reconstruida o conceptual con una ejecución auténtica.

## Calidad y entrega

Conservar audio original, narración y cortes. YO determina identidad, split, fuentes, sombras, texto y cámara; CLONE es la única referencia de motion. Presentador nunca más de 3 s continuos, incluido split; objetivo 15–20 % orientativo. Split inicial 55/45 con una sola grabación original a ancho completo, sin rellenos duplicados, desenfoque ni fondos AI. Hook sin subtítulos convencionales automáticos: tipografía integrada, cámara breve y b-roll relevante o explicación visual fiel a YO. Después bloques breves, centrados y bajo barbilla; durante b-rolls sigue existiendo representación textual, salvo pausa de composición justificada. Sequel/Scholar reales, sombra negra compacta y rojo semántico. Motion con acción, reacción, profundidad, transformación y salida; fades, zooms y tarjetas aisladas no bastan. Zooms rápidos y riser 2–6 s sincronizado. Guardar clips en `assets/broll` y documentar uso previsto/real en `broll_manifest.csv`; la pertinencia y calidad prevalecen sobre cuotas. Alcance actual: segmento animado CLONE1,6–3,2s desde la revisión2 estática aprobada; MP4, editable y comparación animada. La siguiente prueba narrativa conserva el proceso V5 de 10 s y sus entregables. El completo exige indicación posterior y prueba aprobada. Verificar tamaño/MD5 en ENTREGA y limpiar descartes. Todas las escrituras propias permanecen en IVAN.

## Mapa detallado de subcarpetas

El inventario canónico registra la ruta y el acceso real de cada carpeta y archivo. El mapa siguiente se actualiza a partir de ese inventario, conservando una sola fuente de metadatos.

<!-- MAPA DRIVE -->

Inventario del 2026-10-12T17:44:59Z: **42 carpetas, 1.876 archivos y 1.861 videos**; recorrido completo sin errores. Los archivos sin inspección visual siguen marcados pendientes.

| Ruta relativa | Acceso | Archivos directos | Uso orientativo |
|---|---|---:|---|
| B-rolls AI | [Abrir](https://example.invalid/recurso) | 0 | Comprobar herramienta y función reales |
| B-rolls AI/Hotmart | [Abrir](https://example.invalid/recurso) | 2 | Comprobar herramienta y función reales |
| B-rolls AI/chatgpt | [Abrir](https://example.invalid/recurso) | 7 | Comprobar herramienta y función reales |
| B-rolls AI/claude | [Abrir](https://example.invalid/recurso) | 20 | Comprobar herramienta y función reales |
| B-rolls AI/google | [Abrir](https://example.invalid/recurso) | 3 | Comprobar herramienta y función reales |
| B-rolls AI/heygen | [Abrir](https://example.invalid/recurso) | 9 | Comprobar herramienta y función reales |
| B-rolls AI/make | [Abrir](https://example.invalid/recurso) | 3 | Comprobar herramienta y función reales |
| B-rolls AI/manychat | [Abrir](https://example.invalid/recurso) | 5 | Comprobar herramienta y función reales |
| B-rolls AI/n8n | [Abrir](https://example.invalid/recurso) | 9 | Comprobar herramienta y función reales |
| Edición con IA | [Abrir](https://example.invalid/recurso) | 1 | Raíz y documento original |
| Crudos | [Abrir](https://example.invalid/recurso) | 1 | Originales del reel |
| ENTREGA | [Abrir](https://example.invalid/recurso) | 1 | Solo entregables, no b-roll |
| ENTREGA/Agent Reach | [Abrir](https://example.invalid/recurso) | 3 | Solo entregables, no b-roll |
| Efectos de Sonido | [Abrir](https://example.invalid/recurso) | 3 | Riser y woosh sincronizados |
| Música | [Abrir](https://example.invalid/recurso) | 5 | Elegir entrada 10–15 s dentro del archivo |
| Transiciones | [Abrir](https://example.invalid/recurso) | 5 | Burn Screen selectivo |
| b-rolls | [Abrir](https://example.invalid/recurso) | 0 | Escoger según acción y contexto |
| b-rolls/CINEMATICS-20260702T222216Z-3-001 | [Abrir](https://example.invalid/recurso) | 0 | Escoger según acción y contexto |
| b-rolls/CINEMATICS | [Abrir](https://example.invalid/recurso) | 33 | Escoger según acción y contexto |
| b-rolls/DOPAMINA-20260702T222212Z-3-001 | [Abrir](https://example.invalid/recurso) | 0 | Escoger según acción y contexto |
| b-rolls/DOPAMINA | [Abrir](https://example.invalid/recurso) | 7 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/500 CLIPS MÁS | [Abrir](https://example.invalid/recurso) | 497 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Batman | [Abrir](https://example.invalid/recurso) | 1 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Ciudad | [Abrir](https://example.invalid/recurso) | 60 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Cámara | [Abrir](https://example.invalid/recurso) | 10 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Dinero-Autos | [Abrir](https://example.invalid/recurso) | 35 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Dopamina chill | [Abrir](https://example.invalid/recurso) | 59 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Flasheros-efectos raros-videos raros | [Abrir](https://example.invalid/recurso) | 62 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Gym | [Abrir](https://example.invalid/recurso) | 21 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Light Leaks | [Abrir](https://example.invalid/recurso) | 1 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Muy dopaminicos | [Abrir](https://example.invalid/recurso) | 500 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Paisajes | [Abrir](https://example.invalid/recurso) | 58 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Rutina-trabajar | [Abrir](https://example.invalid/recurso) | 32 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Tiempo-Reloj | [Abrir](https://example.invalid/recurso) | 1 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/Triste-Serio-Enojado | [Abrir](https://example.invalid/recurso) | 39 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/comida | [Abrir](https://example.invalid/recurso) | 2 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/cuaderno-Libro-Escribir | [Abrir](https://example.invalid/recurso) | 18 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/pareja-amor | [Abrir](https://example.invalid/recurso) | 50 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/sitckman blanco | [Abrir](https://example.invalid/recurso) | 12 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/televisor | [Abrir](https://example.invalid/recurso) | 2 | Escoger según acción y contexto |
| b-rolls/DOPAMINA/tranquilidad-paz-Divertirse-ocio | [Abrir](https://example.invalid/recurso) | 111 | Escoger según acción y contexto |
| b-rolls/LUXURY CLIPS | [Abrir](https://example.invalid/recurso) | 188 | Escoger según acción y contexto |

DOPAMINA incluye trabajo, escritura, cámaras, tiempo, deporte, ciudades, paisajes, emociones y otras categorías. Son orientaciones por nombres; comprobar los clips. CINEMATICS tiene nombres numéricos y LUXURY nombres poco descriptivos: abrir candidatos antes de decidir. Software: Claude (20), ChatGPT (7), Google (3), HeyGen (9), n8n (9), Make (3), ManyChat (5), Hotmart (2).

Hay 462 grupos de contenido repetido por MD5/tamaño. Reutilizar una sola descarga local aunque existan varios IDs; no borrar originales de Drive.
