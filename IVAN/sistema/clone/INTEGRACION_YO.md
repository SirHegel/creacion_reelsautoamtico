# Integración CLONE + YO

El adaptador `integration.py` integra SceneIR CLONE, dirección YO y grabación original en un reloj HyperFrames/GSAP. El perfil opt-in `production_complete` procesa el nuevo reel completo de 51,1 s/1533 fotogramas, conforme al manual vigente. YO conserva identidad, cámara, tipografía y hook; CLONE define el movimiento gráfico. Las pruebas históricas V1/V2/V3, sus alcances y fuentes permanecen intactos.

La corrección histórica V3 afecta únicamente al hook de 0–3,6 s / 108 frames. Comienza directamente en split 50/50; conserva la escena y decisión primaria de V2, su continuación radial de 3,6–7,9 s y las familias originales. La dirección V3 es una inferencia real de cámara/foco/textos, con procedencia separada del plan primario histórico. Sus reglas legacy no fijan el crop, ritmo o número de apariciones del nuevo reel completo.

Antes de un encargo, leer completos `AGENTS.md`, `PROMPT_MAESTRO.md` e `INSTRUCCIONES.md`, resolver sus últimas modificaciones y registrar hashes. Consultar `STYLE_YO.md` y sus evidencias visuales vigentes. Las reglas de b-roll y cuotas de etapas antiguas quedan sustituidas en este motor: no insertar stock, b-roll tradicional ni capturas estáticas como relleno. Tella está excluido. Todo archivo, caché y salida propios permanece dentro de IVAN.

## Entradas del adaptador

El adaptador consume estas entradas comprobadas dentro de `proyectos/<drive-id>/integracion`. `integration_planner.py` dirige cámara y textos mediante una segunda inferencia registrada y tipada; recibe el SceneIR intacto del planner vigente. El helper de geometría aplica sus acciones existentes, sin elegir otra familia. La obtención/alineación de voz y las anclas de barbilla son etapas previas: este primer crudo fue transcrito mediante Parakeet CUDA y reutiliza detección facial comprobada contra su mismo SHA. El adaptador no afirma disponer todavía de ingestión/detección facial autónoma para cualquier crudo.

| Entrada | Datos necesarios | Si falta |
| --- | --- | --- |
| Grabación original | Ruta canónica dentro de IVAN, SHA, resolución, FPS, duración, rotación y rango autorizado | Localizarla en el proyecto; no tomar automáticamente un export anterior |
| Audio original | Ruta/hash, sample rate, duración y correspondencia con cortes | No fabricar narración ni una voz sustituta |
| Texto alineado | Palabras/frases con inicio/fin comprobados, idioma y correcciones ortográficas | Transcribir/alinear; un guion sin audio no permite inventar tiempos exactos |
| Cortes válidos | Mapa de tiempos del crudo a la cronología final | Conservar discurso; documentar cualquier transformación temporal autorizada |
| Anclas de rostro | Tiempo, bbox facial, punto de barbilla y confianza en coordenadas de la grabación | Revisar anclas manualmente; no colocar texto por defecto en el tercio inferior |
| SceneIR | Frase completa, entidades, acciones, relaciones, resultado, objetivo, familia/componentes, parámetros y transiciones | Resolver significado antes de elegir una familia; no selección solo por palabras |
| Recursos y fuentes | Claves en `assets.json`, procedencia, hashes; Sequel/Scholar locales | Registrar bloqueo o nueva recuperación autorizada; no inventar disponibilidad |
| Hook y CTA | Objetivo y contenido suministrados; énfasis visual justificado | No inventar oferta, promesa ni titular genérico |

Formato orientativo de ancla, con coordenadas normalizadas de origen: `{"t":1.2,"bbox":[0.30,0.18,0.42,0.33],"chin":[0.51,0.51],"confidence":0.97}`. Su existencia no demuestra precisión: hay que comprobarla sobre fotogramas nativos. Los intervalos de palabras y capas se remiten a una sola cronología.

## Cámara y split

La presencia **visible** del presentador nunca supera 3 s continuos, contando pantalla completa, split y cualquier superposición. Objetivo orientativo 15–20 % total, adaptado al discurso. Un corte de layout o pasar de full a split no reinicia el contador si el rostro sigue visible. Unir intervalos contiguos/solapados, incluidas las entradas/salidas y sus opacidades visibles.

`camera_mode` describe la pose inicial, `split_first` o `full_first`; no impone full seguido de split. Puede existir una sola ventana. Split-first empieza compuesto desde F0 con transición cero, sin full oculto ni fade/reveal inicial. Full-first también empieza en F0 con transición cero, sin split posterior obligatorio. Los cambios contiguos entre poses, cuando se elijan, tienen 4–10 frames de transición dentro de la ventana entrante.

`split_top` admite 0.5 (50 % motion / 50 % cámara) y 0.55 (55/45). V3 usa 50/50, divisor y960 a 1080 × 1920; split-first 55/45 necesita `split_ratio_reason` de encuadre. Los planes V2 sin campos nuevos conservan su proporción histórica de 55/45. Ninguna proporción permite deformar a Presentador: conservar rostro, frente, barbilla, fondo, iluminación y nitidez. Ajustar crop/posición a la fuente y comprobarlo en movimiento; si no encaja, corregir la composición, no añadir relleno.

Quedan prohibidos vídeo duplicado/desenfocado, blur de relleno, viñetas para esconder bordes, fondos artificiales o recreados detrás del presentador. No reutilizar el presentador ajeno de CLONE. Full → split → expansión es una opción narrativa, no una obligación universal. El límite de 3 s incluye todas las poses, entradas y salidas. El adaptador mide la proporción y presencia ejecutadas; declararlas en JSON no prueba los píxeles.

## Subtítulos, ancla y hook

Los subtítulos tradicionales se centran **dentro de su región**. Su borde superior queda ligeramente bajo la barbilla transformada al encuadre final, con espacio pequeño y consistente. Aplicar primero crop/escala de cámara, después transformar el ancla; no sumar una altura fija de pantalla a una coordenada de origen. Mantener bbox de texto libre de boca, barbilla, ojos y micrófono cuando perjudique lectura. Usar una sola línea corta cuando facilite la composición.

Suavizar el recorrido de las anclas con un filtro determinista calculado previamente, sin reloj ni medición de layout durante el tween. No arrastrar un ancla vieja al siguiente plano ni interpolar sobre un corte abrupto. Baja confianza o pérdida del rostro requiere revisar ese tramo; no corregir un error de detección con una posición inferior arbitraria.

Sequel Sans Bold Disp es principal; Scholar Italic aporta contraste editorial selectivo. Blanco predominante, carbón sobre fondos claros. Sombra negra compacta con separación vertical y desenfoque controlado; arranque a 1080: `2px 4px 5px rgba(0,0,0,0.85)`, seguido de comparación visual con YO. Rojo para pérdida, riesgo, problema, negación o contraste deliberado, nunca para decorar nombres de apps.

Después del hook, usar normalmente bloques de 2–3 palabras alineados con voz y unidades de sentido. Cuando la cámara desaparece, continuar representación textual de narración dentro del motion, salvo una pausa justificada por composición; evitar duplicar un título y su subtítulo. Los textos tipográficos integrados pueden cambiar de posición/tamaño porque forman parte de una acción.

El hook de 4–6 s se dirige como YO: cámara breve, tipografía cinética integrada o secuencia visual que comunica la primera frase. No activar una transcripción de palabras aisladas automáticamente ni insertar un titular como «UNA SKILL» sin relación compositiva/narrativa. Analizar entradas, jerarquía y transiciones reales de YO antes de escoger tratamiento. Los gráficos de CLONE elevan la explicación sin sustituir esa identidad.

Si el alcance autorizado es más corto de cuatro segundos, puede ser completamente hook: V3 declara `hook_end_frame:108` y `caption_blocks:[]`. Todas las doce palabras iniciales siguen representadas; no desactivar cobertura textual para simplificar la muestra. Si queda desarrollo después del hook, captions vacías siguen rechazadas. Los titulares/identidad y el objeto gráfico pertenecen al mismo protagonista; evitar la misma frase duplicada en interfaz y titular.

## Contrato de capas y salida

El compositor emite por escena:

- `start`, `duration` e intervalos de cámara visibles sobre una cronología a 30 FPS; registrar tiempos fraccionarios sin cortes parciales de vídeo.
- Capas `camera_original`, `motion_world`, `narration_text` y audio original, con bbox/crop, z-order y transiciones explícitos.
- Un namespace único por instancia y por escena para IDs, máscaras, filtros y timelines. Una instancia no modifica a otra.
- `asset_refs` con claves canónicas/hash y tramos/estados de uso real, separados de recursos solo empaquetados.
- Texto alineado con voz, anclas transformadas/suavizadas y decisiones de pausa tipográfica.
- Transformaciones de entrada/salida y acciones vinculadas al significado; duración local compatible con la familia.

La prueba incluye proyecto editable, cronología, render del alcance autorizado, recursos realmente visibles y QC enlazado al SHA del MP4. Audio original conservado; efectos/music se mezclan con voz clara y riser principal culmina entre 2–6 s en transformación relevante cuando se produzca la muestra narrativa. No atribuir escucha a una mera lectura de niveles. Si el crudo no contiene diez segundos de voz, registrar su duración real y cualquier cierre sin voz autorizado; no inventar frases para rellenarlo.

## Controles antes de integrar o promover

Revisar frames consecutivos de todas las apariciones y transiciones: duración visible ≤3 s, rostro/crop completos, split fiel a YO, anclas/texto centrados bajo barbilla, sombra legible, rojo semántico, continuidad de narración, causalidad del motion y ausencia de blur de relleno. Decodificar todos los frames; enlazar cualquier informe a SHA y código actuales. Comparar con YO para cámara/textos y con CLONE para motion; una correlación HTML/MP4 solo verifica reproducción técnica.

La biblioteca puede producirse sin aprobación por componente. La edición narrativa y el completo conservan el alcance que el usuario autorice después: esta documentación no amplía por sí misma el permiso. Registrar problemas pendientes y continuar componentes independientes sin afirmar integración, seguimiento facial o revisión perceptiva que aún no se hayan ejecutado.

## Ejecución reproducible

Desde IVAN, con `proyecto.json`, `narration.json` alineado y anclas comprobadas preparados:

```bash
python3 -B sistema/clone/integration.py plan <drive-id>
python3 -B sistema/clone/integration.py prepare <drive-id>
python3 -B sistema/clone/integration.py compile <drive-id>
python3 -B sistema/clone/integration.py render <drive-id>
node sistema/clone/tests/integration_browser.mjs <drive-id>
```

`plan` reutiliza inferencias comprobadas sin volver a elegir escenas. Si falta un plan completo llama al planner vigente y al director YO; un plan incompleto u obsoleto se rechaza. `prepare` conserva píxeles decodificados en proxy H264 lossless y copia AAC; `render` repone los paquetes AAC exactos del original, valida todos los fotogramas y publica el MP4 local atómicamente. El reloj de la instancia se alinea mediante cues declarados; el adapter no modifica fuentes aprobadas ni SceneIR.

El crop de cámara depende de las anclas del crudo, nunca de un blur de relleno. V2 de esta fuente 1080×1920 conservaba el ancho y trasladaba y711, con recorte y345..1209. Ese encuadre histórico no es un crop universal ni debe imponerse al split 50/50 de V3. Revisar la pose/proporción elegidas sobre la grabación real. El próximo paso de automatización es conectar la detección de rostro para nuevas fuentes y verificar más familias con cámara: una sola integración no valida toda la biblioteca.

Esta primera prueba mantiene exclusivamente la pista original para medir identidad temporal y sonora. No afirma mezcla musical, riser, efectos ni escucha perceptiva. Su diseño sonoro adicional continúa como mejora pendiente, sin cambiar el audio del crudo.

## Corrección V2: recursos y ritmo

La revisión V2 conserva la primera integración y sus componentes aprobados. El planner evalúa el catálogo con `brand_context` explícito; los recursos oficiales de `brand_registry.py` amplían el mapa sin modificar `assets.json`. Las vinculaciones semánticas documentan qué marca representa cada recurso. El contexto `private_review` prepara el test; no concede permiso de publicación. Consultar `BRAND_ASSETS.md` y `brand_assets.json`.

El contrato opcional `scene.rhythm` define puntos de progreso y permanencias sobre acciones nativas existentes. `phase_clock` combina estos puntos con los cues de voz en un reloj monótono; un hold repite un estado terminado, conserva duración y no altera AAC. Las ventanas de fases de familias fijas son aproximaciones hasta comprobar el movimiento real. Las salidas nativas extendidas durante un reveal conservan su reloj; no se eliminan al retimar la parte lógica.

Las permanencias de 0,7–1,3 s son una referencia editorial. Se miden después de entradas, recortes y opacidades, junto con tamaño legible. Los logos de una lista pueden permanecer acumulativamente mientras se nombra otra plataforma. No introducir acciones repetidas para simular dinamismo. El inspector compara V1 y V2 y registra excepciones justificadas.

El director puede solicitar una identidad oficial en `hook_blocks[].brand_asset`, vinculada a `brand_entity_id` y con `brand_reason`. El compositor mantiene la frase y su jerarquía YO; un wordmark puede representar la palabra de la marca y un símbolo acompaña su nombre. Se decodifica el archivo antes de habilitar el render. No se redibuja ni se añade sombra al icono. La cámara inicial no se reduce para alcanzar una cuota: el 20 % es orientativo, el máximo continuo de 3 s sigue siendo obligatorio.

La colocación bajo barbilla se exige cuando el rostro está visible. No crear una aparición tardía por obligación si la narración se resuelve mejor con motion. Los avisos de verificación y rótulos internos permanecen en informes. Suprimirlos por instancia no modifica los módulos aprobados.

Para revisar V2, ejecutar `node sistema/clone/tests/integration_v2_browser.mjs <drive-id>` después de compilar. Su PASS técnico no sustituye la inspección del MP4 y la comparación con CLONE/YO. Conservar V1 y publicar el archivo V2 separado, según `proyecto.json.output_name`, sin crear otro proyecto por la misma fuente.


## Dirección reutilizable verificada en V2

1. Resolver entidades del texto alineado mediante Brand Asset Registry antes de inferir; pasar el contexto de uso explícito y las capacidades reales al planner. Registrar alternativas por bloque y conservar la respuesta original.
2. Compilar esas familias, sin elegirlas manualmente ni modificar sus módulos aprobados. Los adaptadores pueden aumentar la escala de un recurso auténtico, ajustar puertos y mantener sus curvas/progresos originales.
3. Combinar los cues de voz con el reloj de cada instancia. Separar entradas breves de los movimientos explicativos; no acelerar globalmente. Medir lectura después de opacidad, crop y tamaño, sin confundir presencia con legibilidad.
4. Cargar las fuentes en el padre y medir todos los prefijos tipográficos una sola vez. Interpolar mediante transformaciones x/y, nunca left/top. Los glifos futuros no ocupan espacio invisible; el glifo nuevo acompaña el desplazamiento de su línea para conservar separación.
5. Medir obstáculos gráficos en todos los fotogramas del intervalo de texto. En split, reservar la altura completa del titular arriba del divisor; durante el reveal, pausar texto hasta que esa región quede libre. Durante la salida, llevar el texto hacia la zona gráfica libre sin atravesar la cámara ni retroceder a su pose anterior.
6. Conservar superficies claras al pasar a otra escena clara si la salida oscura del componente no tiene función narrativa. Este ajuste por instancia no elimina la transformación del objeto ni modifica el archivo aprobado.
7. Ejecutar HyperFrames check/keyframes y render GPU. Decodificar todos los fotogramas y comprobar paquetes AAC contra la fuente. Recorrer las timelines adelante, atrás y con seeks desordenados; registrar fuente, SceneIR y MP4 actuales.
8. Revisar el MP4 mediante secuencias consecutivas completas y planos mayores. El primer PASS técnico de V2 no detectó todas las oclusiones tipográficas ni un destello de fondo: se corrigieron mediante inspección real. Los límites del inspector deben permanecer documentados.
9. Generar comparación V1/V2 a tiempos equivalentes, informe y editable con los medios y las fuentes locales. Mantener V1 intacta. `integration_v2_report.py` rechaza QA de otra fuente/export o problemas visuales bloqueantes. Preparar una prueba para revisión no concede permiso público de las marcas ni aprobación estética del usuario.

## Hook V3: contrato, procedencia y comandos

El director recibe V2 íntegro y constraints explícitas. Deriva un prefijo en la frontera existente de 3,6 s sin modificar familia, params, actions o steps. No solicita otra inferencia primaria ni vuelve a seleccionar escenas. Persiste `integracion/hook/scene.json`, `narration.json`, `scope_provenance.json` e `integration_plan.json`. El recibo enlaza SHA del origen/derivados, palabras 0–11, primera escena reutilizada, escena radial excluida del alcance y prueba primaria histórica. El manual V3 de la dirección permanece separado del manual V2 del origen; no fingir que la inferencia histórica leyó modificaciones posteriores.

```bash
python3 -B sistema/clone/integration_planner.py \
  --scene proyectos/<drive-id>/integracion/scene.json \
  --narration proyectos/<drive-id>/integracion/narration.json \
  --source proyectos/<drive-id>/original.mp4 \
  --out proyectos/<drive-id>/integracion/hook/integration_plan.json \
  --camera-mode split_first --split-top .5 --scope-end-frame 108 \
  --max-primary 1 --max-support 1
python3 -B sistema/clone/integration.py compile <drive-id> --component hook
python3 -B sistema/clone/integration.py render <drive-id> --component hook
```

Para `--component hook` los medios y `proyecto.json` del componente deben estar preparados. `plan`/`prepare` completos no se ejecutan con ese flag: la dirección deriva las decisiones conservadas, y compile/render operan únicamente en `integracion/hook`. La prueba conserva movimientos/velocidad y audio de la fuente desde cero; el recorte AAC se mide por paquetes y no se declara exactamente igual a 3,6 s sin evidencia. No reemplazar V2 ni la escena posterior.

`focus_windows` contiene `{scene_id,start_frame,end_frame,primary_target,support_target:null|ID,reason}`. Con límites explícitos cubre el hook sin huecos/solapamientos, con un protagonista y como máximo un apoyo. IDs existentes, sin código, fuera de escena o activación antes de enter según el único reloj solicitado. El adaptador aplica la jerarquía por instancia, suprime texto repetido cuando corresponde y conserva los módulos. V2 sin focos nuevos mantiene `focus_windows:[]`. La ejecución permanece pendiente hasta QA: la validación de IDs/intervalos no prueba jerarquía o lectura pintada.

La inferencia V3 actual pasó en el primer intento, con split-first 50/50 y focos Google en frames 0–36, Claude en 36–70 y Claude+Internet en 70–108. Su recibo y `scope_provenance.json` permiten verificar la reutilización; no constituyen aprobación estética ni de permisos públicos. `contrato_camara_v3.json` exporta el esquema local, la copia estricta de proveedor y la función de constraints del código congelado. `TESTS_CONTRATO_CAMARA.txt` registra la ejecución actual de las pruebas de CPU, su comando y resultado. Las pruebas de contrato/fixtures no reemplazan inspección del MP4, capturas y continuidad a 30 FPS.

## Producción completa

Invocar el director con `constraints={"profile":"production_complete","camera_mode":"split_first","split_top":0.5}` o CLI `--profile production_complete --camera-mode split_first --split-top .5`. El perfil no admite recortar un prefijo ni sustituir el SceneIR que seleccionó el planner real. No impone diversidad de familias, cuotas de apariciones ni una única receta de escenas. Hasta 24 ventanas permiten dirigir una narración larga; ninguna unión visible de rostro supera 90 fotogramas. La pose inicial está compuesta desde F0, sin transición previa. Las nuevas apariciones y cambios contiguos de pose/ratio usan 9–18 frames; las salidas a ausencia usan 6–18 frames, dentro del intervalo contabilizado. El esquema legacy conserva hasta ocho ventanas y sus límites anteriores de 4–10 frames.

Cada `camera_windows` puede declarar `split_top:null` para heredar el ratio global, o `0.5/0.55` para adaptar esa aparición. Cambiarlo necesita `split_ratio_reason` concreto. El perfil emplea `camera_poses` calculadas desde bbox/barbilla, dimensiones y anclas del original: unión del rostro durante la aparición, frente conservada, margen para caption y escala uniforme. Se comprueba orientación vertical; una fuente sin normalización verificable se rechaza. Las coordenadas históricas y315/345 no sirven como valores por defecto de producción.

`diagnostico_yo/anclas_55_45.json` es la entrada canónica del detector existente. Incluye `original.sha256/width/height/fps`, `anchors[].t/segment_id/source_normalized.bbox/chin/smooth_chin` y procedencia. Una confianza numérica ausente permanece `null`; el adaptador no la inventa. Los resets conservadores de tracking son fronteras para el filtro, aunque no sean cortes editoriales certificados. Se evita interpolar entre segmentos; el crop se calcula por ventana y la barbilla se transforma después por escala/posición de cámara. El micrófono aproximado requiere inspección visual de legibilidad.

Las familias fijas conservan sus componentes y timelines. `CloneIntegrationFamilyLayout` mide los objetos visibles en todos los frames de cada intersección con split y encuadra su superficie vectorial por escena; el fondo gráfico permanece a tamaño completo. Los grupos de texto editorial existentes —incluidos `caption0` y variantes CANCELLED— se reemplazan por la representación de palabras originales. El grafo conserva su reflow instancial, evitando una segunda compresión global cuando comparte reel con otras familias. Tamaños principales y cajas reales se comprueban antes del render; una instancia que se miniaturice requiere corregir su encuadre, no redibujar un componente o declarar calidad por el simple número de animaciones. Las fuentes y las 15 familias originales/CANCELLED permanecen protegidas.

Los cues de narración y `scene.rhythm` forman un solo mapa monótono con endpoints 0/d y velocidades 0–6x. Un mapa solicitado que no pueda ejecutarse se rechaza; no se afirma sincronización mientras se conserva silenciosamente otro reloj. El perfil no recorta ni acelera la voz. Las ventanas descriptivas de fases de familias fijas continúan siendo aproximadas hasta comprobar su movimiento real. El render/QA debe confirmar entradas, transformaciones y lectura fluida; las guardas de contrato no certifican equivalencia estética con YO/CLONE.

Para sonido adicional, el proyecto puede aportar `audio_mix={path,sha256,provenance_path,provenance_sha256,voice_source_sha256}`. Todos los archivos residen en IVAN. El recibo exige SHA del crudo original, hash de paquetes del AAC original, conservación del stem de voz y SHA de la mezcla. El mux final conserva el vídeo de 1533 frames y utiliza la mezcla comprobada, sin apad/retime. Su AAC final es nuevo: `audio_original_bit_exact:false`, aunque `original_voice_stem_unchanged:true` describa el stem preservado antes de sumar FX/música. Sin mezcla verificada, se conserva AAC original por stream-copy como en legacy. Licencias, sincronización de cues y escucha perceptiva tienen evidencia independiente; un hash o un pico de volumen no acredita calidad sonora.

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3 -B -m unittest discover \
  -s sistema/clone/tests -p 'test_integration*.py' -v
node sistema/clone/tests/integration_layout_contract.mjs
```

El primer comando verifica reglas de cámara/textos/tiempo y compatibilidad legacy; el segundo prueba los wrappers contra builders reales en Chromium CPU, con recursos locales y sin exportar un vídeo, captura o demo. Sus rechazos de legibilidad son explícitos. La aceptación final corresponde al reel entero: ver todos sus fotogramas, continuidad y movimiento, comprobar el audio mezclado y comparar identidad con YO y dinámica con CLONE. Compilar, revisar, corregir y renderizar se realiza sobre el mismo proyecto canónico del nuevo crudo.

## Correcciones de instancia con procedencia

El proyecto de producción puede aportar `camera_framing={target_face_width_px:300,max_scale:1.5,reason:"…"}`. El adaptador mide la mediana del ancho facial de cada aparición, centra horizontalmente la unión de sus bbox y aplica una escala uniforme constante durante esa aparición. Su crop mantiene frente, barbilla y espacio para texto; no es un zoom de énfasis ni un movimiento continuo. La escala máxima relativa al encaje original es 1,5. Ausencia del campo conserva el encaje anterior. El recibo registra crop, escala, ancho medido y ancho resultante; una cifra objetivo todavía necesita comparación visual con YO.

`instance_overrides` permite exclusivamente correcciones cerradas, opt-in y con razón explícita, sin reescribir SceneIR, respuesta original del proveedor, transcripción ni módulos aprobados:

- `pixel_functional_roles`: escena existente `pixel_agents`, `hide_count:true` y `labels` breves sustentadas por las etiquetas originales. Envuelve el numeral de fondo y «N ROLES COORDINADOS» en gates independientes de GSAP para evitar presentar funciones de un plugin como un número de agentes. Conserva sprites, roles, reacciones y reorganización. Registra etiqueta original y abreviada; el opt-in mide la abreviatura con un máximo de 24 unidades nativas y la encaja en la misma pill. Los defaults originales permanecen intactos.
- `spotlight_hook_identity`: escena inicial `spotlight_agent`, `asset` oficial ya declarado por la dirección real, `painted_major_px` entre 200–240, `support_major_px` entre 90–110, `primary_until_frame`, `transform_frames` entre 9–21 y `entrance_s` entre 0,2–0,4. Una misma placa neutra contiene el logo auténtico, presente desde F0; se mueve y escala con `power2.inOut` hacia identidad de apoyo. El archivo, proporciones, arte y orientación permanecen intactos; la sombra pertenece a la placa. El sprite original se revela mediante gate independiente durante esa transformación. Se suprime únicamente el logo inline duplicado, conservando la palabra de la narración. El objetivo nativo se reserva hasta finalizar el hook para evitar repetir la capacidad mientras la explica el texto YO.
- `graph_brand_surface`: nodo existente `message`/`result` de `composition_graph`, con el mismo recurso oficial declarado en SceneIR. `painted_major_native` entre 72–104 amplía ese archivo sobre una superficie propia dentro de la tarjeta original. La sombra pertenece al contenedor; se conservan arte, proporciones, fuente y reloj. Se reserva una zona lateral y se comprueba que todos los estados originales de texto encajen en la zona restante; si no caben, se rechaza la adaptación.

La segunda corrección mide la altura real del titular con las fuentes cargadas y reserva esa zona inferior de la composición superior. El logo queda fuera del wrapper nativo, por lo que no recibe otra compresión. La instancia acorta solamente los tweens de entrada de luz, personaje y command; mantiene sus inicios, gestos y fases restantes. Registra duración nativa anterior/nueva y duración de salida realmente ejecutable con el reloj de palabras; un hold incompatible se rechaza. Los tests comprueban búsquedas directas/inversas, gates que permanecen cerrados, bytes auténticos y parámetros intactos. No sustituyen la inspección del reel completo ni autorizan publicar marcas de contexto privado.

La reserva del hook utiliza solamente los prefijos ya pronunciados dentro de la intersección real con split. No incluye la altura de palabras futuras ni frases que aparecerán cuando la cámara ya haya salido. Su alineación inferior sigue la altura visible con la misma interpolación del prefijo. Las captions nativas convertidas a líneas `<tspan>` se comparan uniendo esas líneas con espacios; se evita que una caption editorial no detectada entre por error en la medición. El cono de luz de spotlight es ambiente, no objeto de foco. El identificador original de herramienta puede reencuadrarse como apoyo junto a la marca, conservando texto, escala uniforme y coreografía; el recibo registra la matriz y bbox de origen.

Algunos nodos de grafo sólo realizan escritura, entradas y transferencias: su punto constante permanece dentro del closure de repaints y no aparece entre los targets de GSAP. El adaptador los admite exclusivamente si su matriz local/opacidad son idénticas en todos los fotogramas nativos y límites de acciones. Registra `verified_constant_native_pose_bindings` separado de `native_point_mapping`. Cualquier cambio de esa pose sin un target verificable falla antes de render. Para esos nodos aplica la matriz adaptada después del repaint y recalcula rutas/paquetes desde los mismos relojes/progresos existentes. No afirma que el punto está vinculado a GSAP ni sustituye las transferencias por imágenes estáticas.

En producción, las etiquetas originales de `terminal_install` pueden repartirse en dos líneas, en el punto de separación entre palabras con menor ancho máximo. Se conservan palabras y tamaño tipográfico, celdas, sprites y gestos. La medición con las fuentes cargadas exige separación horizontal entre etiquetas y registra cualquier desplazamiento dentro de la ventana original. Esta adaptación no cambia el módulo ni inventa comandos.

La zona de cada caption se calcula tras buscar explícitamente el reloj nativo y aplicar los repaints y encuadres de instancia. Se incluyen las escenas salientes durante su cola visible. Un fondo entrante sólo descuenta un obstáculo si realmente lo cubre mediante superficie opaca y clips rectangulares/circulares comprobados; una máscara desconocida no acredita oclusión. Los atributos SVG de opacidad pueden conservar valores anteriores cuando GSAP aplica CSS: la medición utiliza la opacidad efectiva. Las transiciones se inspeccionan también en su frontera exacta, no sólo unos fotogramas después.

Para `spotlight_agent` posterior al hook, un objetivo editorial de al menos tres palabras se oculta únicamente cuando coincide con palabras consecutivas de la narración de esa escena y sus índices/tiempos están cubiertos por los bloques de subtítulos existentes. Un gate independiente conserva actor, command, gestos, fases y parámetros. `source_caption_owns_literal_editorial_goal` registra frase, prueba literal, anclas y IDs de captions. Un objetivo parafraseado, cobertura incompleta, interfaz de otra familia o contexto del hook conserva su presentación original.

El contraste lee el `fill` CSS ejecutado del fondo y registra su normalización por escena. Un negro abreviado como `#000` se convierte en `rgb(0, 0, 0)` antes de calcular luminancia; no se sustituye por el fondo claro de reserva. La guardia requiere revisar el color realmente pintado del texto sobre su superficie, además del contraste declarado.

Cuando una caption cruza la frontera real entre superficies de luminancia opuesta, producción permite una pausa editorial inicial de hasta seis fotogramas (0,2 s; límite de contrato 0,201 s). Se mide el fondo compositado sobre nueve puntos de su caja: clips y desplazamientos de las superficies saliente/entrante, más el film que puede cubrir el hueco entre ambas. La pausa termina al quedar legible la caja completa; una máscara desconocida requiere cobertura opaca total entrante. Si supera ese límite o elimina toda la presencia pronunciada de una palabra, la integración falla. No se añaden halos ni se recolorea una mitad de la frase. El recibo `brief_type_pause_during_scene_reveal` contiene escena/texto, frames inicial/final, geometría comprobada y presencia conservada por palabra. P1/P2, bloques, narración y tiempos originales permanecen intactos. `tests/integration_reveal_evidence.mjs` verifica los fotogramas reales de esas fronteras y rechaza evidencia obsoleta respecto al freeze.

El editable y Studio reproducen una sola pista: `media/voice_original.m4a` si no existe mezcla verificada, o un enlace canónico `media/audio_mix.<ext>` a la mezcla validada. `audio_playback` registra la elección, SHA y procedencia. El vídeo de cámara permanece silenciado y no se reproduce la voz por segunda vez. Un test de contrato de mezcla sólo verifica la selección de archivo; la mezcla real, sus FX y escucha se validan cuando exista.
