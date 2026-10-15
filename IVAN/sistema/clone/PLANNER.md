# Guion → dirección semántica → SceneIR CLONE

El planner utiliza realmente la CLI Codex autenticada, con respuesta estructurada y validación local. No selecciona por palabras clave, no tiene un plan manual de reemplazo y falla si el proveedor o el contrato no producen una respuesta utilizable. La inferencia usa el servicio de modelos de Codex; la NVIDIA interviene después en el render.

## Invocación

Ejecutar desde IVAN, sin instalar dependencias:

```bash
python3 -B sistema/clone/planner.py \
  --script 'Una herramienta convierte un diseño de agenda en una aplicación. Construye la interfaz, permite elegir un horario y añade reprogramación y recordatorios.' \
  --duration 9 \
  --out proyectos/clone_motor/creatividad/demo_a/scene.json
```

`--script-file` acepta una ruta dentro de IVAN. `--narration` recibe anclas reales `{start,end,text}` o `words`/`segments`: deben cubrir el guion completo. Sin ellas se proponen tiempos visuales, nunca sincronización de voz ficticia.

API estable:

```python
import planner
scene_ir = planner.plan(script, output=path, narration=None, duration=9,
                        timeout=180, retries=1, compile_to=None,
                        brand_context='editorial_reel', visual_requirements=None)
```

Sin `compile_to` no compila, anima, renderiza ni publica. `--compile-to` permite compilar después de validar; el render continúa en el workflow coordinado del motor. Los tres conceptos A/B/C tienen estados privados distintos; no ejecutar simultáneamente el mismo encargo y directorio. `PlannerError` indica rechazo, sin proveedor o plan sustituto. `retries` admite 0 o 1; el segundo intento puede corregir un contrato, sin cambiar autenticación/modelo ni ocultar el recibo del primer fallo.

## Selección creativa sin familia universal

Versión del prompt: `3.5.CONFIGURE_RECURSO_1193`. Se eliminó `PREFERIR composition_graph` y se expone el catálogo completo con 16 familias, formas tipadas de parámetros, recursos disponibles y capacidades/límites auditados contra su código. Los ejemplos estructurales contienen tipos y marcadores, no los valores del vídeo de referencia. El catálogo también publica perfiles de composición, puertos y pares de continuidad implementados por el compositor; no convierte metadata en prueba de movimiento.

El modelo identifica la estructura narrativa y propone una estrategia visual antes de elegir. Cada escena relaciona hechos mediante `fact_ids`, explica la pertinencia en `semantic_reason`, explica dirección/jerarquía/lectura en `visual_reason` y evalúa alternativas concretas. Las alternativas muestran razonamiento; no imponen diversidad en el resultado. Una sola escena suficiente es válida. El grafo sigue disponible cuando representa mejor relaciones o pasos nuevos; no es una ruta universal ni una familia prohibida.

| Capacidad | Familias | Límite narrativo relevante |
|---|---|---|
| Roles, coordinación y relevo | `pixel_agents`, `spotlight_agent`, `agent_marquee` | Los sprites representan funciones; no personas reales ni ejecución comprobada. |
| Apps que se duplican/reorganizan | `apps_clone_orbit` | Repite el mismo icono; no comparar herramientas distintas con un clon ficticio. |
| Investigación desde fuentes | `radial_research` | Contador aportado u omitido; ajustar etiqueta fija cuando cambia el objetivo. |
| Evidencia organizada por criterios | `feedback_bars` | Resultados explícitos, sin inventar reseñas/ganador/benchmark. |
| Agenda móvil inspeccionada, construida o probada | `phone_recon`, `phone_rebuild`, `phone_qa` | Conservan calendario y reservas; no son interfaces genéricas de cualquier software. |
| App original y réplica | `phone_compare` | Ocultar el porcentaje no cambia esa estructura; no representar dos herramientas arbitrarias. |
| Necesidades que se convierten en funciones | `problem_resolution` | Cada problema/función procede de la narración. |
| Repositorio o producto | `github_cards`, `product_card` | No inventar owner/repositorio, reputación, precio o publicación. |
| Instrucción que activa un proceso | `terminal_install` | Acepta lenguaje natural conceptual; no inventa shell, URL ni instalación real. |
| Costes y cancelación | `cancelled` | Diseño aprobado inmutable, USD/mes, apps/textos originales; necesita pertinencia y coste aportado. |
| Relaciones y acciones abiertas | `composition_graph` | Pasos causales editables; justificar frente a las capacidades especializadas. |

Las capacidades describen posibilidades, no garantizan calidad. Las frases breves deben sobrevivir en móvil. Toda `caption` editable se limita a **48 caracteres** antes de compilar/renderizar, incluidos espacios y saltos de línea. Este presupuesto se comprobó contra el área nativa de 620 px y el wrap determinista del compositor; no es una garantía universal de legibilidad. Usar una idea editorial principal breve y repartir los detalles en interfaz/diagrama. No repetir la narración completa ni apilar avisos en la caption. CANCELLED conserva su texto aprobado inmutable y su API original, sin añadirle un parámetro caption. En `problem_resolution`, `features[].feature` se limita a 12 caracteres y `result` a 20 por sus campos de 123/315 px; abreviar según el significado sin añadir capacidades. Este límite se aplica a nuevas inferencias, sin reescribir planes históricos A/C ni los módulos/defaults de reconstrucción. `feedback_bars` con `presentation` ajusta observaciones hasta 30 px en 470 px de ancho, categorías hasta 28 px en 205 px y contadores a 36 px; el compositor puede reducirlos para encajar. Esos límites no autorizan párrafos largos ni acreditan legibilidad por sí solos. Root y el revisor deben comprobar los fotogramas reales. `radial_research` también dispone de adaptación tipográfica opt-in.

## Coreografía: qué se ejecuta realmente

Las 15 familias especializadas conservan sus módulos y timelines. El proveedor declara `choreography.mode: family_phases`, `execution: component_timeline`, un subconjunto opcional de IDs de fases legítimas y `actions: []`. No debe copiar las fases ocultas ni inventar otras. El normalizador deriva ventanas descriptivas desde las fases del builder y la duración elegida; no convierte esas acciones en órdenes nuevas de animación. El SceneIR registra `actions_execute: false`, `timing_kind: phase_window`, archivo/hash de origen y la distinción entre descripción y ejecución. Conserva `requested_phase_ids`, deriva el conjunto nativo completo y anota `enabled`/`visible`: LIVE oculto conserva su reloj sin afirmar publicación; un deck de feedback con hasta cuatro observaciones no ejecuta reemplazo; pixel_agents sin reorganización conserva cámara, sin fingir una tarjeta de resultado. No afirmar que una acción arbitraria cambia una familia fija.

`composition_graph` tiene otro contrato: `custom_steps`, `execution: params.steps` y `actions` exactamente iguales a `params.steps`. Aquí los pasos sí controlan la timeline. Requiere 2–6 nodos, hasta 10 conexiones y 4–36 acciones causales. Las formas son cerradas: nodo `{id,kind,label,body,role?,asset?}`, conexión **exactamente** `{from,to,label}` (label obligatorio, sin id), paso `{at,duration,op,target,from?,to?,text?,scale?}`. El validador distingue campos extra, claves ausentes y extremos inválidos para que el modelo corrija la causa real. Toda entrada precede a su uso; el destino recibe información antes de resolverla; los resultados/campos escritos empiezan vacíos. Entradas 0,12–0,30 s, cámara 0,15–0,35 s para énfasis o 0,20–0,60 s para transformación y escala 1–1,12. No prolongar zooms ni estados inmóviles para rellenar segundos.

El compositor puede añadir únicamente mejoras autorizadas por su implementación, separadas de los módulos: por ejemplo selección de horario después de la máscara y continuidad geométrica de un teléfono cuando ambas escenas comparten la app. Sus etiquetas/tweens y `render_handoff` se comprueban en el recibo del navegador. No son `params.steps` arbitrarios ni se atribuyen retrospectivamente al CLONE original. El plan conserva la intención; el runtime verifica lo ejecutado.

La duración fija de una familia escala su coreografía existente. Que su rango admita ocho segundos no significa que estirar un movimiento breve hasta ocho segundos sea una buena decisión. La selección de una o varias escenas debe conservar ritmo y comprensión sin cuotas artificiales.

## Parámetros, datos y adaptaciones

[scene_schema.json](scene_schema.json) es el contrato cerrado del proveedor. `params_json` contiene un objeto JSON serializado que se valida con los tipos/formas de la familia y se normaliza a `params`. Todas las claves con default se aportan explícitamente; no heredar contenido de otra app. La validación también comprueba roles/assets, límites, índice seleccionado, cardinalidad real de roles, tiempos, IDs, cobertura de hechos y anclas.

Las métricas visibles llevan `data_bindings` con ruta del parámetro, `fact_id` y motivo. La cifra debe existir en ese hecho, no simplemente en otro lugar del guion. Se reconocen cantidades explícitas en palabras: «dos horarios», «un conflicto», «tres alternativas». Score requiere porcentaje; precio/coste requiere unidad monetaria; rating requiere valoración; pantallas/flujos y forks/estrellas requieren su unidad. «Tres herramientas» no autoriza un score de 3 %. Los valores de distinta naturaleza no representan un ranking de calidad. Textos como `N/D` o `—` solo son desconocidos cuando el parámetro admite texto; cero visible no significa ausencia de dato.

`presentation` adapta una instancia mediante el contrato de `engine.catalog`, sin editar los módulos de las reconstrucciones:

```json
{"labels_json":"{\"panel_title\":\"RESULTADOS POR CRITERIO\"}","omit":[]}
```

El proveedor usa `labels_json` para mantener cerrado su esquema. El SceneIR normalizado entrega `presentation: {labels: {...}, omit: [...]}` al motor. Solo se admiten claves/longitudes de la whitelist. Cada `omit` tiene `hidden_params`: exclusivamente esos datos pueden usar cero neutral sin evidencia porque el grupo entero queda oculto. Un omit inexistente, parcial o ajeno no habilita la excepción. `presentation:null` conserva el original; en familias con contratos también puede usarse `{labels_json:"{}",omit:[]}` para activar legibilidad.

`illustrative_fields` declara una interfaz de ejemplo con ruta y motivo. Admite instrucciones naturales vinculadas al contenido, nombres de workspace ilustrativo, dominio ficticio `.invalid`, mes/horarios de ejemplo y versión de interfaz. No admite cifras de rendimiento, score, precio, rating, repositorios/propietarios inventados ni shell/URLs/rutas inventadas. Una instrucción literal aportada sigue siendo representación conceptual, nunca ejecución autenticada. El renderer marca `EJEMPLO CONCEPTUAL` cuando hay campos ilustrativos. No reutilizar identidades o resultados fuente a través de esa excepción.

`framing` opcional contiene únicamente `view_box:[x,y,w,h]`: recorte 9:16 dentro del lienzo nativo 720×1280, ancho mínimo 600 y zoom máximo 1,2. Cambia el encuadre, no la disposición de cada elemento. La verificación visual debe comprobar que no recorta texto/rostro/elementos; no es un remedio para ocultar fallos.

`layout:null` mantiene la composición nativa. Un perfil opcional se elige exclusivamente entre `engine.catalog().layout.profiles` de esa familia. El proveedor aporta el objeto completo con `profile`, `gap_px`, `anchor_x`, `anchor_y`, `margin_px`, `body_px`, `secondary_px`; los campos numéricos innecesarios usan `null` y se eliminan al normalizar para conservar los defaults del compositor. Los rangos son: separación 36–144px, anclas 0,33–0,67, margen 72–180px, texto principal 48–60px y secundario 30–42px. Las unidades px se refieren a 1080×1920; las anclas son proporciones. Son guías de proximidad, centro y tercios flexibles, no una cuota de layouts ni instrucciones CSS. `compact_stack` de feedback admite hasta cuatro observaciones; no descartar contenido para forzar ese perfil. La validación llama a `composition.validate_composition(scene)` y rechaza perfiles, claves y valores que no pueda ejecutar.

`closing:null` es el valor por defecto. El único cierre publicado es `coverage_conclusion` de `feedback_bars`, para comparar cobertura de respuestas a las mismas solicitudes, sin evaluar calidad ni declarar ganador. Su forma es `{kind:"coverage_conclusion",at,headline:"Cobertura de respuestas"}`. Necesita `layout.profile:"compact_stack"` y caption con el límite de calidad explícito; el compositor exige que incluya «calidad». El tiempo es local, finito y alineado a30FPS, entre `duration*.6` y `duration-1.2`; deja clasificación previa y1,2s de lectura. Usa exclusivamente los datos/categorías aportados y sus bindings. No autoriza otro benchmark ni crea una conclusión para un guion que no trate esa comparación. El modelo debe razonar desde el contenido antes de elegirlo; el validador del compositor y la QA real comprueban contrato y ejecución. Las familias no se fuerzan para obtener un perfil o un cierre.

## Continuidad honesta

`handoff` enlaza la escena anterior real con la siguiente por entidades, recursos y significado. Sus entidades deben existir; los assets compartidos deben aparecer en ambas escenas. La primera escena no hereda recursos de una anterior inexistente. `narrative_link` y `visual_strategy` documentan el propósito del enlace.

Es metadata `execution: metadata_only`, `execution_verified: false`. Se conserva así aunque el plan solicite una operación. Una continuidad narrativa no necesita un efecto complejo ni una cuota de transiciones distintas.

La escena entrante puede añadir `continuity`, o `null` si no solicita continuidad de objetos. La primera escena siempre usa `null`. El contrato cerrado es:

```text
continuity = {
  from_scene: ID de la escena anterior real,
  reason: intención semántica y visual,
  operations: [
    {kind: actor_pose_match | device_pose_match,
     source_port, target_port, asset, entity_ids, duration}
  ]
}
```

Se permiten una o dos operaciones, sin duplicar un puerto. `engine.catalog().continuity` declara `ports` y `accepts` por familia. Cada puerto contiene `id`, `kind`, derivación `asset:{param,prefix?}` o `asset:{literal}`, e `identity_param` cuando hay un dispositivo. Cada regla de `accepts` contiene `kind`, `source_family`, `source_port`, `target_port`, `wrapper_kinds`, `duration_range` y `requires_same_framing`. No hay coordenadas, selectores DOM, curvas, CSS o JavaScript enviados por el modelo. El compositor resuelve poses y grupos desde los vectores originales. La ausencia de un par ejecutable provoca un rechazo específico; nunca sustituir la operación solicitada por un corte silencioso.

Los assets efectivos deben coincidir en ambos puertos y estar compartidos en `handoff`; el rol deriva el sprite real `agent_` + rol. `entity_ids` son únicos, existentes y compartidos por handoff. `device_pose_match` exige la misma identidad de app publicada; no transforma dos productos diferentes en uno. La duración es finita, alineada a 30FPS, de 0,2–0,6s, dentro del contrato del par y menor o igual a un tercio de ambas escenas. El wrapper y framing también deben ser compatibles con esa regla. El planner valida significado/capacidad y llama a `composition.validate_continuity(plan,definitions)` antes de entregar una solicitud ejecutable. Si el compositor no está disponible, la solicitud queda rechazada como capacidad pendiente.

`native:calendar_phone` es la identidad de un componente SVG nativo publicada por el puerto device. Se permite en `handoff.shared_assets` solo cuando el puerto de cada escena la publica y existe la identidad de app; no es un PNG, una descarga ni `calendar_blue` utilizado. `scene_assets` sigue enumerando solo assets efectivos de los parámetros. `scene_continuity_resources` añade por separado esa identidad vectorial al conjunto permitido para handoff. No se añade a `used_assets` de bitmaps ni al manifest de imágenes; un dispositivo con layout necesita una capacidad geométrica específica y la continuidad nativa actual lo rechaza.

Cada frontera tiene un solo dueño: `transition_in` de la escena siguiente. El proveedor envía `transition_out:null`; el normalizador lo deriva de esa entrada, y la última salida es `cut/0`. Una propuesta antigua de salida se reemplaza por la derivación; la respuesta original permanece en el recibo privado. `cut` requiere duración cero. `wipe`, `push`, `mask` y `match` requieren duración positiva, hasta 0,6s y un tercio de ambas escenas. La primera entrada usa `cut/0`. `match` describe reveal/continuidad de cámara, **no** morph de un objeto. La extensión visible saliente y los relojes locales los controla el compositor, sin que el modelo duplique los movimientos.

`planner.continuity_execution` registra el número de operaciones solicitadas, validación de capacidad y `execution_verified:false`. No declara aprobación del vídeo. El recibo compilado debe vincular operación, recurso, puertos, poses y ventanas a los SHA vigentes. La búsqueda directa e inversa, los fotogramas consecutivos de la frontera y la revisión editorial comprueban la ejecución y estabilidad. La integración de actor/máscara pertenece al compositor; no modifica ni atribuye nuevas fases a las 15 familias especializadas o CANCELLED.

## Aislamiento y recibos

El proveedor existente permanece intacto. `bwrap` monta `/` en lectura y permite escritura física solo dentro de `.estado/clone/planner/<encargo>/attempt_N` en IVAN. Mantiene HOME/CODEX_HOME; autenticación global de lectura. Los mapas virtuales estrechos de `installation_id` y `tmp/arg0` apuntan a respaldos privados de arranque; no copian tokens ni modifican originales. CLI efímera, sin herramientas/apps/shell/browser/plugins. Una llamada a herramientas, falta de `turn.completed`, timeout, error de servicio o salida inválida impide el plan.

Se conservan prompt/respuesta y recibos privados con hashes, versión, uso y retorno. Los errores de capacidad/autenticación no son validaciones semánticas exitosas. Los planes válidos incluyen huellas de AGENTS, PROMPT_MAESTRO e INSTRUCCIONES vigentes. Leer completos esos archivos sigue siendo obligatorio; calcular hashes no sustituye leerlos.

## Pruebas y límites

```bash
python3 -B sistema/clone/tests/test_planner.py
```

Las fixtures son pruebas de guardas, no planes manuales utilizados en demos. Las 40 pruebas comprueban una escena especializada sin cuota, tipos, acciones no ejecutables, instrucción natural, shell inventado, cifra/unidad/evidencia, datos ocultos, framing y handoff, grafos sin campos extra, diagnóstico preciso, fases legítimas/ocultas/condicionales y límites de copy, incluida la frontera caption48/49 antes de GPU. Las guardas de continuidad comprueban alias de asset original, puerto/par publicado, frontera única, recurso/entidad compartidos, dispositivo con identidad igual, duración finita/alineada, wrapper/framing compatible y rechazo de código/puertos duplicados/primera escena. También separan identidad SVG/bitmap, rechazan perfiles desconocidos, valores no finitos, eliminación de observaciones, código y cierres sin composición/tiempo/copy permitidos. Incluyen llamadas a los validadores reales del compositor y una normalización completa phone→phone con identidad vectorial, sin compilar ni renderizar. No sustituyen la prueba visual del compositor. La prueba de inferencia real pertenece a los recibos de cada demo: esos recibos deben existir antes de atribuir uso al modelo.

La selección estructurada no certifica fidelidad a CLONE, ritmo, lectura móvil ni continuidad. El alcance actual corrige la integración CLONE+YO V2 del crudo ya autorizado; conserva las 15 familias, CANCELLED, las demos y V1. El render candidato requiere inspección editorial aparte del check técnico. El planner no renderiza ni publica. La preparación privada conserva los permisos de publicación pendientes. Logs y credenciales quedan fuera del entregable.


## Auditoría de la selección V1 y actualización V2

V1 usó una sola `composition_graph` de 7,9 s. Su recibo real está en `.estado/clone/planner/20c16b663e44f16f/attempt_1/provider_proof.json`; su decisión permanece como historial. La respuesta evaluó radial_research, terminal_install, spotlight_agent y cancelled. No había un selector universal de graph: el prompt 3.4 ya prohibía esa preferencia. Había límites concretos:

- `current_catalog`, `normalize_response` y `make_prompt` leían únicamente `assets.json`; Google, Claude y las tres plataformas no figuraban allí como marcas auténticas. El modelo descartó radial porque `sources.asset` no disponía de esos recursos y porque por sí sola no cubría la reacción de Google y la condición final.
- La lista de IDs no explicaba identidad, procedencia, restricciones ni contexto. Los campos anidados de `sources/apps/reviews` tampoco tenían un enum exhaustivo. Eso limitaba la evaluación y facilitaba pedir un asset inexistente.
- Las otras alternativas conservan significado específico: terminal escribe una instrucción; spotlight presenta un actor; cancelled expresa costes de suscripciones y cancelación. No corresponde forzarlas por variedad o reutilizar cifras de CLONE.
- Las fases de una familia fija son ventanas descriptivas de su timeline, no órdenes de movimiento libre. Estirar una sola escena a ocho segundos no mejora la dirección; la selección y el ritmo necesitan reevaluación con el catálogo real.

V2 elimina la carencia de información, sin reescribir la decisión histórica ni imponer una familia. Los logos resueltos actualizan los enums y el contexto; sus dimensiones y restricciones se exponen al modelo. `node.asset` de graph se pinta únicamente en message/result, como icono nativo de 21 px; otros skins no lo pintan y el planner rechaza declarar un logo invisible. Radial tiene fuentes de 72 px/target de 76 px y product_card icono de 154 px. El tamaño de un slot no garantiza legibilidad móvil: el compositor y la revisión comprueban la aparición efectiva y cualquier adaptación de instancia. Apps orbit rota sus iconos; un logo que prohíbe rotación no puede tratarse así sin un adaptador autorizado. Conservar arte, proporciones y colores, sin sombra directa sobre la marca.

## Registro de marcas y contexto explícito

`resolved_assets(brand_context)` combina los recursos originales con `brand_registry.assets_for_engine(entities=None,data_uri=False,context=brand_context)`. No descarga ni redibuja. El registro valida archivos, hashes y contexto; cualquier error falla con causa explícita, sin sustituir un logo por otro. `brand_registry.catalog(context)` expone también pendientes y razones; no equivale a ponerlos en los enums disponibles.

```python
scene_ir = planner.plan(script, output=canonical_scene, narration=aligned_words,
                        duration=7.9, brand_context='private_review')
```

`private_review` está autorizado para preparar esta prueba/mockup privado. `editorial_reel` mantiene las condiciones de publicación. La preparación privada registra `publication_authorized: false`; la autenticidad del archivo no resuelve permisos públicos. `planner.asset_resolution` conserva contexto, snapshot SHA y comprobantes de identidad. El compilador consume el mismo contexto al empaquetar assets. Un cambio del registro durante la inferencia invalida ese intento antes de compilar.

Cada logo usado requiere `scene.asset_bindings` con `{path,asset,entity_id,reason}`: path relativo a params, ID exacto del campo, entidad real y nombre de la misma marca. Un quote amplio que menciona varias herramientas no permite vincular un logo a otra entidad. El recibo añade hash/fuente y declara identidad únicamente; la aparición en vídeo se valida después. Sin logos verificados, la lista queda vacía. No dar por usado un archivo porque esté empaquetado.

## Ritmo solicitado y preservación de la voz

`scene.rhythm:null` conserva la timeline nativa. El contrato opcional es:

```text
{mode:'phase_clock', reason,
 points:[{cue_id:'phase:<ID>'|'step:<index>', at, native_progress, hold_s, reason}]}
```

Solo usa fases existentes y visibles, o índices reales de steps. `at` y `hold_s` son segundos locales a 30 FPS; `native_progress` recorre 0–1 de esa ventana. Un hold declarado dura al menos 7 frames y como máximo 1,3 s, con progreso exactamente 1. No congela una entrada a mitad. El normalizador persiste `native_at=round30(action.at+action.duration*native_progress)`; no cambia la fase al interpretar un label diferente. `clock_knots` añade el final del hold con el mismo native_at, además de endpoints 0/duración. Rechaza source/output no monótonos, dos estados diferentes en el mismo tiempo, holds superpuestos, endpoints incompatibles y velocidad gráfica superior a 6x.

Entradas aproximadamente 0,18–0,30 s, transformaciones 0,35–0,60 s y lectura protagonista 0,7–1,3 s son orientación por significado, no cuotas ni una reducción de rangos de familia. Retener fuentes acumulativamente puede explicar mejor una enumeración hablada muy rápida. Un hold repite un estado gráfico; jamás retima la voz, crea silencio, agrega una cola o cambia cortes. El archivo original de este encargo conserva 237 frames/7,9 s y AAC de 7,918005 s.

`execution` permanece solicitado, `execution_verified:false`. Las ventanas de familias son aproximadas; completar su ventana no prueba que todos los tweens del estado hayan terminado. El compositor verifica ese estado real, consume los knots, mide permanencia/ritmo y registra la ejecución. Las 15 familias permanecen intactas.

## Dirección de integración y titulares sobre cámara

`integration_planner` realiza una segunda inferencia real sobre el SceneIR canónico: conserva familias, parámetros y decisiones. Sus phase_cues deben poder fusionarse con rhythm en **un único reloj** no decreciente; no atraviesan un hold ni sustituyen un punto del primer modelo. Se guardan timings solicitados, no una falsa sincronización ejecutada.

El hook conserva una presencia inicial suficiente; el 20 % es orientativo y permite justificación, mientras el máximo continuo de 3 s sigue estricto. No se obliga una aparición tardía para demostrar under_chin: el texto adopta barbilla cuando el rostro realmente aparece; el resto permanece en la composición.

Un bloque de hook puede incorporar `brand_asset`, `brand_entity_id` y `brand_reason` para integrar identidad oficial junto a la frase sobre cámara. Son opcionales/null/vacío y se validan con el registro y entidad real. Una sequence incremental conserva la misma identidad desde su primer bloque. No permite posiciones arbitrarias ni fuentes nuevas; el adaptador calcula estilo YO, encuadre y zonas libres. El modelo lo usa si aporta a la frase o evita que cámara full tape la única aparición de un logo, sin imponerlo por cuota.

Las notas internas «Esquema conceptual», «Condición del guion», «Según el guion» y otras verificaciones no se convierten automáticamente en parámetros/títulos visibles si no pertenecen literalmente a la narración. Se conservan en unsupported_claims/reportes. La conceptualidad y los permisos siguen explícitos en los recibos; suprimir un rótulo no convierte una animación en prueba real.

## Esquema estricto del proveedor y pruebas

El primer intento V2 fue rechazado antes de generar un plan: la API exigió que `required` incluyera todas las propiedades de los objetos, incluido asset_bindings. El estado fallido permanece en `.estado/clone/planner/5b555d9d03fc1aa9`. La advertencia de caché global de modelos en solo lectura no fue la causa. No se tocaron cachés globales ni dependencias.

`strict_provider_schema()` crea una copia privada para la API con required exhaustivo y additionalProperties:false, recursivamente. Los opcionales conservan null/lista vacía; el esquema local permanece compatible con fixtures/historia. Se guardan SHA del esquema local y del enviado; no se modifica una escena con este adaptador. La versión 3.5.1 crea un estado nuevo y conserva el fallo anterior.

Las pruebas actuales cubren tipos, métricas/evidencia/unidad, continuidad real, caption móvil, marcas por contexto/hash, IDs anidados, logos vinculados a entidades, restricciones de slot, cambios del registro, rótulos internos, rhythm/holds/endpoints/velocidad, cues compatibles y hook con logo. El test de integración usa fixtures de metadatos inmutables, sin depender de que exista el plan de producción mientras se reconstruye. Ninguna fixture actúa como fallback de una llamada real. Los controles técnicos no aprueban estética ni permisos de publicación.

## Evaluación por bloques y tamaño nativo: versión 3.5.2

El primer plan válido V2, recibo `.estado/clone/planner/a4dc36aa03540b9c/attempt_1/provider_proof.json`, volvió a elegir un grafo único. Su alternativa radial se descartó porque no explicaba también hook/condición final y porque no introducía cada fuente exactamente con su palabra. Esos requisitos no pertenecen al builder ni al usuario: cada familia se compara con la unidad narrativa que representa, mientras la unión de escenas conserva hechos y voz. El prompt ahora pide ese alcance explícito en razones/alternativas. Agrupar y retener fuentes durante una enumeración permite reconocerlas sin multiplicar tarjetas, pulsos o transferencias por palabra. Sigue siendo válida una sola escena suficiente y no hay cuota de familias.

La capacidad auditada de radial admite una a cuatro fuentes generales `{asset,label}`, no exige reseñas ni un clon. Usa entrada agrupada con stagger, rutas hacia el agente y target. Si no se aporta cantidad, `count:0`, `metric:""` y `presentation.omit:["metric"]` ocultan contador/métrica completamente; `target_label` es la etiqueta autorizada para adaptar el significado. El catálogo publica estas capacidades, sus límites, slots y SHA del módulo original. No se reconstruye el componente ni se afirma scraping ejecutado.

`visual_requirements={"brand_logo_min_native_size":64}` es una restricción opcional de esta prueba sobre los logos protagonistas introducidos en params. También puede pasarse con `--brand-logo-min-native-size 64`. El normalizador verifica los slots nominales reales `C.image`: graph21, radial72/76, producto154, comparación móvil148, etc. Son cuadrados de colocación, no dimensión de tinta del wordmark ni garantía de lectura móvil. El recibo conserva fuente/SHA y deja presencia/encuadre pendientes del render. Sin ese mínimo un icono decorativo pequeño sigue permitido; con mínimo el grafo aún puede explicar otro bloque sin introducir una marca de21px. No se excluye una familia universalmente ni se fuerza otra por una keyword.

El catálogo de integración también publica el overlay de identidad oficial ya implementado por el director YO separado. El modelo puede preverlo para una identidad del hook cubierta por cámara; solo la segunda dirección y su ejecución lo hacen visible. El plan primario no cuenta overlays no solicitados/renderizados como apariciones. La restricción de tamaño no justifica una interfaz/acción ajena al significado.

Otra guarda concreta rechaza hub con seis nodos sin centro agent/terminal: el builder nativo solo tiene cinco puestos periféricos. Pipeline/comparison conservan seis posiciones y hub con centro mantiene su capacidad. El validador impide llegar a un fallo de montaje; no inventa un rol ni cambia el módulo para reparar geometría. Los tests comprueban ese rechazo, alternativas válidas, mínimos opt-in por slot, capacidades reales de metric/target y ausencia de selección forzada. La lectura útil del grafo permite hasta1,3s entre acciones, sin obligar pulsos de relleno por el antiguo límite0,8s.

La inferencia real 3.5.2 del crudo canónico terminó válida en `.estado/clone/planner/9b8cad74b1930e47/attempt_2/provider_proof.json`: composition_graph de 0 a 3,6 s sin logos decorativos, seguida por radial_research de 3,6 a 7,9 s con fuentes LinkedIn/YouTube/Instagram a 72 px y target Claude a 76 px. Se documentó por qué otras capacidades no representaban esos bloques, sin prescribir la pareja al proveedor. Google quedó previsto para el overlay de dirección separada, todavía sin contar como visible. El primer intento de ese estado seleccionó también ambos bloques, pero carecía de transferencia en el grafo y fue rechazado; el módulo original exige esa interacción. La reparación fue otra inferencia real, no una escena editada a mano. Ambos recibos y el intento anterior a4dc… quedan como historial privado. Las 71 pruebas de planner pasan; la inferencia no constituye aprobación del render, audio o publicación.

La dirección real posterior pasó en el primer intento, recibo `.estado/clone/planner/integration_1652237a5b34710c/attempt_1/provider_proof.json`. Conservó el SceneIR y seleccionó full en frames 0–29, split contiguo en 29–69, seis frames de reencuadre/salida y ninguna aparición tardía. La unión visible propuesta es 2,3 s, con justificación del 29,1 % para presentar el hook. Solicitó Google oficial en la secuencia inicial del hook, más las cuatro identidades radiales del plan primario; ocho cues existentes, hook hasta el frame 173, captions hasta el frame exclusivo 237 y ninguna omisión de narración. Son decisiones inferidas, no observaciones del MP4: la presencia real de las cinco marcas, su lectura/condiciones, tiempos efectivos, cámara, fuentes y AAC original quedan para el recibo del adaptador y QA del render. No se produjo un vídeo ni se publicó desde este agente.

## Cámara V3: pose inicial y hook acotado

La dirección 2.0.1 imponía en `normalize()` dos ventanas mínimas, full desde el frame 0 y split contiguo obligatorio. `make_prompt()` repetía esa receta y el normalizador fijaba `split_top=.55`. Esa condición era una restricción del sistema, no una necesidad narrativa ni un requisito universal del usuario. La versión 2.1.0 elimina esas obligaciones. Conserva las direcciones V2 y sus recibos históricos sin reescribirlos.

`camera_mode` declara `split_first` o `full_first`: únicamente la pose inicial. Se admite una sola ventana, sin exigir un reencuadre posterior. Split-first empieza con split en F0 y `transition_frames:0`; no parte de un full oculto ni añade fade/reveal inicial. Full-first empieza con full en F0 y también transición cero. Los cambios contiguos entre poses, cuando existan, emplean 4–10 frames dentro de la ventana entrante. Todas las entradas/salidas permanecen dentro de su ventana, sin superposición. El máximo de 90 frames continuos de rostro sigue incluyendo split, reencuadres y salida; cambiar de pose no reinicia el contador.

`split_top` acepta 0.5 (50/50) y 0.55 (55/45). Split-first prefiere 0.5; 0.55 exige `split_ratio_reason` concreto de encuadre. Sin campos nuevos, un contrato V2 con full inicial conserva `full_first` y 0.55; `focus_windows` queda vacío y el foco nativo permanece. La elección de una pose no prueba que el MP4 la haya ejecutado. El adaptador y su revisión verifican el primer frame, rostro, proporción, continuidad y lectura.

API para esta corrección, ejecutada con los JSON V2 íntegros como origen:

```python
direction = integration_planner.plan_for(
    original_scene_path, original_narration_path, original_raw_path,
    'proyectos/<id>/integracion/hook/integration_plan.json',
    timeout=180, retries=1,
    constraints={'camera_mode':'split_first', 'split_top':0.5,
                 'scope_end_frame':108, 'max_primary':1, 'max_support':1})
```

CLI equivalente: `--camera-mode split_first --split-top .5 --scope-end-frame 108 --max-primary 1 --max-support 1`, junto con `--scene`, `--narration`, `--source` y `--out`. Sin constraints, la dirección elige la pose por significado; no hay secuencia full→split universal. Los constraints son campos cerrados, no código ni opciones libres.

El prefijo autorizado termina exactamente en una frontera existente. `scoped_inputs()` rechaza cortar una escena, steps o palabra alineada y exige que las escenas heredadas cubran exactamente las palabras iniciales. Para este origen deriva 108 frames / 3,6 s y las doce palabras iniciales; conserva sin cambios el diccionario de la primera escena, incluidos familia, params, actions, steps y decisión del modelo. No hace una inferencia primaria nueva ni edita la escena radial posterior. El análisis semántico amplio se conserva como contexto heredado, no se vuelve a atribuir a una planificación nueva. La dirección no puede introducir una marca cuya entidad quede fuera del texto autorizado.

La ejecución de `plan_for()` persiste `hook/scene.json`, `hook/narration.json` y `hook/scope_provenance.json` antes de solicitar la dirección real. El recibo vincula origen, archivos derivados, SHA, frontera, palabras, escena excluida, prueba primaria reutilizada y manual V2 histórico. El manual V3 actual se registra por separado para la dirección nueva. La ruta de salida del prefijo no puede sobrescribir los JSON originales. Se revalidan origen, derivados, fuente, manual, STYLE_YO y módulos protegidos antes de guardar un resultado válido. Un cambio durante la llamada impide promoverlo.

Si el alcance es menor de cuatro segundos, `hook_end_frame=frames` permite un segmento completamente hook y `caption_blocks:[]`. Esto no desactiva la cobertura textual: todas las palabras siguen representadas por titulares integrados o una omisión literal comprobable. Si queda desarrollo, captions vacías siguen rechazadas. La duración visual del prefijo no se hace pasar por duración exacta de AAC: el renderer conserva la fuente/velocidad y mide la granularidad del corte de paquetes.

## Jerarquía solicitada por focos existentes

El proveedor decide `focus_windows` con esta forma cerrada:

```text
{scene_id, start_frame, end_frame, primary_target, support_target:null|ID, reason}
```

Con límites explícitos, las ventanas cubren exactamente el hook, sin huecos/solapamientos y dentro de escenas existentes. Un ID principal y como máximo uno de apoyo; deben ser distintos y no se aceptan terceros objetos ni código. Para composition_graph, `focus_targets` publica únicamente los IDs de sus nodos y sus enter originales. No se inventan puertos para familias que aún no tienen esa capacidad publicada. La validación impide enfocar un nodo antes de su entrada según el único reloj solicitado de cues y rhythm, preservando endpoints y velocidad máxima 6x. Sin límites/focos nuevos, V2 conserva el comportamiento nativo.

El adaptador calcula pose, geometría y jerarquía, sin reescribir la familia. Titular/identidad editorial pertenecen al mismo protagonista; la dirección pide evitar repetir la frase entre interfaz y titular. Los targets elegidos y `focus_execution` permanecen `execution_verified:false` hasta inspeccionar el render. La cobertura del plan no certifica recuento pintado, escala, contraste o texto duplicado.

Las 79 pruebas de planner pasan: legacy V2, full sin split obligatorio, split desde F0 sin reveal, límites de rostro y transiciones, proporción y constraints, hook corto sin perder palabras, foco antes de enter/IDs/cobertura/tercer objeto, derivación sin mutar origen, frontera válida y palabras completas, marca posterior excluida y esquema estricto del proveedor. Las fixtures son metadatos de prueba y no fallback para una inferencia real. Las pruebas de píxeles, audio y estética pertenecen a la revisión del adaptador.
