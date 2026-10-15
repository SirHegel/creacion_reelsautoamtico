# Investigación para Ascendia Studio

Consulta de fuentes primarias: 12 de octubre de 2026. Se investigaron documentación oficial y repositorios de sus propietarios. Las capacidades comerciales sirven como referencia funcional; no se incorpora código, recursos premium ni servicios privados de CapCut o Adobe. El alcance construido y sus pruebas deben comprobarse en el código y la auditoría de Ascendia Studio.

## Qué aportan las referencias comerciales

**CapCut Pro.** La documentación oficial describe una línea de tiempo, animaciones por keyframes, subtítulos, color, estabilización, seguimiento de cámara, eliminación de ruido, mejoras de voz, separación de audio, efectos y recursos. La clasificación premium varía entre planes, dispositivos y disponibilidad; por eso no se congela una promesa de equivalencia completa. La traducción y generación de contenido requieren motores independientes y evaluación. [CapCut Pro: funciones y procedimiento](https://www.capcut.com/resource/how-to-download-capcut-pro), [Standard frente a Pro](https://www.capcut.com/help/capcut-standard-vs-pro), [herramientas de IA](https://www.capcut.com/resource/capcut-ai).

**Adobe Premiere.** El modelo funcional incluye montaje multitrack, edición basada en transcripción, títulos/captions, efectos, color, mezcla y exportación. La edición por texto vincula palabras a intervalos del medio; eliminar una frase es una operación destructiva del montaje y debe respetar la directiva local de conservar narración/cortes válidos. [Funciones oficiales de Premiere](https://www.adobe.com/products/premiere/features.html), [edición basada en texto](https://helpx.adobe.com/premiere/desktop/edit-projects/edit-video-using-text-based-editing/overview-of-text-based-editing.html).

**Adobe After Effects.** El patrón útil para motion es composición por capas, propiedades animables, keyframes, expresiones, máscaras y seguimiento. Ascendia requiere escenas que cambien de estado y conecten acciones, además de títulos animados. El seguimiento avanzado y la rotoscopia no quedan resueltos por dibujar una tarjeta o interpolar una escala. [Workflow de After Effects](https://helpx.adobe.com/after-effects/desktop/get-started/understand-after-effects-workflow/workflows.html), [Mask Tracker](https://helpx.adobe.com/after-effects/using/rigid-mask-tracking.html).

**Adobe Audition.** La referencia de audio incluye pistas y clips, mezcla editable, restauración y visualización de waveform/espectro. Un filtro de ruido convencional y ducking no equivalen a restauración neuronal o reparación espectral. [Editor multitrack](https://helpx.adobe.com/audition/desktop/mixing-multitrack-sessions/multitrack-editor-overview.html), [reducción de ruido/restauración](https://helpx.adobe.com/fi/audition/desktop/effects-reference/noise-reduction-restoration-effects.html), [waveform y espectro](https://helpx.adobe.com/audition/desktop/editing-audio-files/displaying-audio-waveform-editor.html).

## Repositorios y licencias revisados

Una licencia de código no concede automáticamente derechos sobre música, fuentes, b-roll, pesos de modelos o marcas. El software registra procedencia y estado de derechos de cada recurso. No se distribuyen las fuentes privadas del cliente como si fueran una dependencia libre.

| Proyecto y fuente primaria | Función útil | Licencia verificada y consideración | Decisión |
|---|---|---|---|
| [FFmpeg](https://github.com/FFmpeg/FFmpeg), [licencia](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md) | Probe, decode, escala/crop, efectos, audio y encode | Base LGPL-2.1 o posterior; módulos/compilación con GPL pueden convertir el binario a GPL. `libx264` requiere configuración GPL. `--enable-nonfree` produce binarios no redistribuibles según el proyecto. Revisar cada build antes de empaquetarlo. | Motor local inicial por proceso CLI; no se copia un binario del pipeline activo. |
| [Pillow](https://github.com/python-pillow/Pillow), [licencia actual](https://github.com/python-pillow/Pillow/blob/main/LICENSE) | Dibujar capas raster y tipografía en frames deterministas | MIT-CMU según LICENSE de la rama actual consultada; conservar avisos y comprobar licencia de la versión instalada y bibliotecas incluidas. | Dibujo inicial de motion local; no reemplaza un compositor libre completo. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | ASR multilingüe, timestamps de palabra y VAD | MIT para el código; pesos y CTranslate2/PyAV tienen licencias propias. El ASR puede errar nombres y tiempos. | Adaptador CPU opcional con modelo local; no hay descarga de modelos sin solicitud explícita de la operación. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | ASR local alternativo y cuantización | MIT; comprobar la licencia de pesos y build elegido. | Alternativa futura para despliegues sin Python/CT2. |
| [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO), [licencia](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/main/LICENSE.txt) | Intercambio de cortes, pistas, rangos y referencias | Apache-2.0. OTIO es formato/API editorial; no renderiza medios ni reproduce todos los efectos de un NLE. | Intercambio futuro con metadatos Ascendia, sin prometer importación lossless en Adobe/CapCut. |
| [MLT](https://github.com/mltframework/mlt), [COPYING](https://github.com/mltframework/mlt/blob/master/COPYING) | Timeline, productores/filtros/transiciones y preview | Framework LGPL-2.1; módulos/dependencias deben comprobarse individualmente. | Adaptador futuro para preview/render multitrack más amplio. |
| [Kdenlive](https://github.com/KDE/kdenlive), [manual oficial](https://docs.kdenlive.org/en/getting_started/introduction.html) | NLE completo sobre MLT, subtítulos, efectos y animación | Repositorio principal GPL-3.0; confirmar SPDX por archivo si se incorpora código. Desarrollo principal en KDE Invent. | Referencia de arquitectura e integración mediante formatos; no se copia su GUI al núcleo. |
| [Blender](https://github.com/blender/blender), [COPYING](https://github.com/blender/blender/blob/main/COPYING) | Composición, 2.5D/3D, cámara, geometría y VSE | GPL; archivo canónico remite a `doc/license/GPL-license.txt`. Dependencias y extensiones requieren revisión específica. | Adaptador headless futuro para escenas complejas; no se invoca durante el proceso ajeno. |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) | Landmarks faciales, barbilla y segmentación de personas | Código Apache-2.0; modelos conservan sus avisos. | Seguimiento CPU implementado en0.2 y segmentación CPU implementada en0.3, con recibos separados. |
| [OpenCV](https://github.com/opencv/opencv), [licencia](https://github.com/opencv/opencv/blob/4.x/LICENSE) | Histogramas, detección de cortes, tracking y análisis temporal | Apache-2.0 en rama actual; algoritmos/componentes externos pueden tener condiciones adicionales. | Visión futura; núcleo inicial no requiere instalarlo. |
| [PyAV](https://github.com/PyAV-Org/PyAV), [licencia](https://github.com/PyAV-Org/PyAV/blob/main/LICENSE.txt) | Acceso Python a FFmpeg | BSD de tres cláusulas para binding; FFmpeg y build mantienen licencias propias. | Utilizado indirectamente si el adaptador faster-whisper lo requiere. |
| [Demucs](https://github.com/facebookresearch/demucs), [licencia](https://github.com/facebookresearch/demucs/blob/main/LICENSE) | Separación de voz/instrumentos | MIT para código. Repositorio oficial archivado el 1 de enero de 2025; revisar soporte y pesos antes de elegirlo. | Investigación futura; no etiquetar como restauración de voz disponible. |
| [Audacity](https://github.com/audacity/audacity), [licencia](https://github.com/audacity/audacity/blob/master/LICENSE.txt) | Edición de audio, waveform y plugins | GPL; componentes externos conservan condiciones propias. | Referencia para audio e interoperabilidad; no es motor de UI inicial. |
| [HyperFrames](https://github.com/heygen-com/hyperframes) | Composiciones HTML/CSS y animación seekable determinista | Apache-2.0 en repositorio oficial consultado; dependencias/versión elegida deben comprobarse. | Motor de motion futuro compatible con la ambición del manual; la implementación inicial genera frames locales. |
| [GSAP: licencia oficial](https://gsap.com/community/standard-license/) | Timelines, transformaciones y plugins de movimiento para un adaptador HyperFrames | Licencia propia gratuita; permite proyectos comerciales y código generado por IA, pero restringe ciertos constructores visuales competidores de Webflow. No es licencia OSI ni hereda Apache-2.0 de HyperFrames. | Separar cualquier adaptador de la base libre y evaluar su distribución; no declarar GSAP implementado en el editor actual. |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp), [licencia](https://github.com/microsoft/playwright-mcp/blob/main/LICENSE) | Inspección/captura real de fuentes oficiales | Apache-2.0 para servidor; permiso de capturar/usar cada web sigue siendo independiente. | Adaptador opt-in de captura futura; nunca fabrica autenticidad. |
| [NVIDIA Parakeet v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) | ASR multilingüe con tiempos | Model card indica CC-BY-4.0; runtime NeMo y CUDA tienen sus propias condiciones. | Adaptador futuro, aislado y con control de recursos. No se toca la GPU ocupada. |
| [Remotion](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) | Composiciones React y render programable | Licencia propia con elegibilidad y licencia empresarial; prohíbe ciertas ventas/relicenciamientos de derivados. No es una base libre sin restricciones para cualquier equipo. | No incluir en el núcleo abierto. Integración externa solo tras revisar licencia aplicable. |

## Mapa de capacidades para la entrega inicial

Esta tabla describe el alcance actual de la primera implementación y separa lo que precisa un motor adicional. **No es evidencia de ejecución:** la comprobación final debe enlazar pruebas y artefactos reales. La presencia de un botón, una plantilla o un paquete instalado no demuestra la función.

| Capacidad | Núcleo inicial de Ascendia Studio | Trabajo adicional para equivalencia amplia |
|---|---|---|
| Ingesta de formatos | FFprobe detecta streams; FFmpeg procesa formatos/decoders que soporte su build. Original preservado y dedup SHA-256. | Ensayos con corpus de MOV/MP4/MKV/WebM/MXF, rotación, VFR, multiaudio, HDR y archivos corruptos. No prometer «todos los formatos». |
| Audio/voz | Extraer audio, waveform, silencios; importar transcript; ASR CPU opcional. | Diarización, corrección lexical/alineación forzada, separación neuronal y evaluación en habla ruidosa. |
| Timeline editable | Proyecto JSON canónico, escenas/clips, texto, recursos y audio; UI y CLI/API sobre el mismo modelo. | Ripple/roll/slip completos, multicámara, nesting, J/L cuts, velocidad variable y preview de baja latencia. |
| Estilo YO | Reglas V5 explícitas, perfil tipográfico, límites de presencia, split y gate de diez segundos. | Seguimiento facial automático fiable, comparación perceptiva, dirección específica por frase y validación humana sostenida. |
| Motion | Frames deterministas con capas, curvas y acciones conectadas parametrizadas. | Editor libre de curvas/máscaras/trayectorias, rigs 2.5D, rotoscopia y adaptación HyperFrames/Blender. |
| B-roll semántico | Almacén local, procedencia, decisiones, tramos y evidencia por frase. | Inventario Drive autorizado, búsqueda multimodal local, preview y verificación visual efectiva de cada clip. No seleccionar por nombre/logo. |
| Audio final | Voz preservada, música/SFX temporalizados, ducking y encode AAC mediante FFmpeg. | Restauración espectral/neuronal, mixer completo, buses, plugins y audición perceptiva registrada. |
| Color/efectos | Exponer solo filtros implementados y comprobados. | LUT/OCIO/HDR, scopes, correcciones secundarias, estabilización y superresolución evaluada. |
| Exportación | Prueba de diez segundos con proyecto y reporte; CPU limitada; archivos dentro de SOFTWARE. | Presets amplios, NVENC coordinado, entrega Drive opt-in y formatos de intercambio. |
| Agentes | Workflows con tareas por rol, dependencias, leases y evidencia; MCP/CLI para agentes reales. | Proveedor LLM configurable, decisiones semánticas evaluadas y seguimiento de coste. Un DAG no equivale a ejecutar un modelo. |
| Aprobación | Revisión técnica separada de revisión editorial; invalidación por hashes/revisión. | Ver la secuencia, escuchar audio y confirmar prueba en términos del usuario. No se autoaprueba. |

## Decisiones prácticas

El motor inicial debe funcionar localmente con Python, FFmpeg y una librería de dibujo, mantener el modelo editable independiente del renderer y permitir adaptadores opcionales. La UI y los agentes usan el mismo contrato; ninguna función esencial queda enterrada en clics de interfaz. Esto permite automatizar sin introducir credenciales globales ni ejecutar comandos arbitrarios desde el navegador.

La primera prueba funcional demuestra ingesta, edición editable, texto/motion, mezcla y exportación controlada. Una demo sintética valida mecánica, no fidelidad audiovisual a YO. La calidad semántica, autenticidad de demos, tipografía exacta y contenido son criterios independientes. No hay base para declarar «toda la suite premium» o «sin errores» únicamente con una primera batería de pruebas.

Antes de publicar una distribución, se deben fijar versiones, conservar atribuciones y documentar el build de FFmpeg y cada dependencia realmente incluida. Los motores investigados que no se instalaron/ejecutaron permanecen como integración futura.

## Requisito de motion observado el 12 de octubre a las 23:45 UTC

La modificación posterior del manual de IVAN, observada el 12 de octubre de 2026, asigna motion exclusivamente a CLONE y cámara/subtítulos/split a YO. Exige primero una prueba técnica de tres segundos con HyperFrames/GSAP y registros de doce skills, además de la posterior prueba narrativa de diez segundos. El requisito no acredita implementación del adaptador en Ascendia Studio; el detalle, las huellas y la separación entre evidencia del padre y del software están en `PROCESO_IVAN.md`.

La licencia Apache-2.0 del [repositorio HyperFrames](https://github.com/heygen-com/hyperframes/blob/main/LICENSE) no relicencia GSAP. Su [licencia propia](https://gsap.com/community/standard-license/) distingue uso de código generado por IA y ciertos constructores visuales. **Inferencia para este proyecto:** el editor visual abierto merece una evaluación específica antes de distribuir una integración GSAP; no basta su gratuidad para describir toda la dependencia como código abierto. La lectura del manual y el registro de evidencias pueden implementarse sin incorporar ese runtime.

## Última precedencia observada: diseño estático aprobado

El snapshot del 13 de octubre de 2026, 00:10:29 UTC, incorpora la regla 20: la arquitectura GSAP del padre ya está comprobada y no se repite. El alcance actual es reconstruir un fotograma de CLONE 1,6–3,2 s y entregar PNG reconstruido/comparativo. Animar requiere aprobación explícita del diseño; después se conserva ese diseño y se comparan instantes equivalentes, separando fidelidad visual, movimiento, ritmo y continuidad. Las fuentes, líneas y huellas vigentes están en el tercer snapshot de `PROCESO_IVAN.md`.

Para Ascendia Studio, la adaptación necesaria es un registro de diseño/aprobación ligado a sus hashes y evidencias comparativas. La correlación HTML/MP4 y los laboratorios técnicos propios no prueban semejanza ni aprobación CLONE. Esto no incorpora GSAP/HyperFrames al editor ni declara ejecutado el nuevo flujo. No se instala nada ni se interviene en el proceso paralelo; las observaciones anteriores permanecen históricas.

## Integración propia en0.2

HyperFrames/GSAP y MediaPipe tienen adaptadores propios, con recibos de CPU,
versiones y hashes. La composición libre añade curvas, máscaras y trayectorias.
Los motores y fuentes conservan sus licencias propias; el código original del
editor es MIT. Los ensayos técnicos no acreditan paridad con las suites ni
fidelidad CLONE/YO. La regla22 autoriza animación del diseño revisión2 en el
proceso padre; SOFTWARE no hereda esa aprobación. Las secciones anteriores
son snapshots de investigación e implementación inicial, conservados como historia.

## Segmentación local en 0.3 — fuentes verificadas el 13 de octubre

La [guía oficial Image Segmenter](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter)
describe máscaras de confianza y modos de ejecución. Se fijó el peso
[SelfieSegmenter float16, versión 1](https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/1/selfie_segmenter.tflite),
de 249537 bytes y SHA-256
`191ac9529ae506ee0beefa6b2c945a172dab9d07d1e802a290a4e4038226658b`.
Su [model card oficial](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Selfie%20Segmentation.pdf)
declara Apache-2.0, entrada 256×256 RGB y salida de un canal con confianza
de persona. Advierte sobre detalles finos, movimiento, oclusiones y varias
personas; no garantiza máscaras perfectas.

La inspección del peso fijado y la ejecución propia confirmaron un tensor
256×256×1, etiqueta `selfie` y un solo `confidenceMask`, con índice 0 para
persona. La descripción general de dos categorías no implica dos tensores
en este peso. `qualityScores` no se utiliza como confianza del rostro/persona.
El runtime Tasks Vision 1.1.0 y sus archivos WASM se reutilizan desde la caché
privada del seguimiento, con hashes, sin importar MediaPipe Python ni usar GPU.

Se implementó MOV con alfa, audio PCM original, parámetros cerrados y evidencia
de decodificación. El ensayo real fue de 1 s a 360×640/15 FPS; no acredita
recorte perfecto en otros videos ni rotoscopia manual. El contacto visual
detectó objetos próximos conservados y variación de borde. Investigación y
procedencia quedan en `.estado/validacion/background_research.json` y
`.estado/models/segmentation/local/provenance.json`. No se incorporó código
ni contenido premium de Adobe/CapCut. La auditoría separa preparación,
inferencia real y revisión perceptiva.
