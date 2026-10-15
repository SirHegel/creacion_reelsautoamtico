# Composición, continuidad y cierre

El compositor adapta instancias nuevas sin editar las 15 familias ni CANCELLED. Sus contratos están en `composition.py`; ejecución en `layout.js`, `continuity.js` y `engine.py`. El catálogo publica únicamente perfiles, puertos y pares implementados. Planner3.4 los consulta y puede solicitarlos según la narración; no impone diversidad ni una transición por obligación.

## Distribución 1080×1920

`scene.layout` usa píxeles de salida. Los originales siguen en720×1280 y se convierten por1,5. Eje central y tercios figuran como guías; `anchor_x/y` son preferencias. La geometría se limita por ancho disponible, márgenes, altura del contenido y escala uniforme. No se crean fondos ni cajas de relleno.

```json
{"profile":"compact_stack","gap_px":96,"body_px":54,"secondary_px":36,"anchor_y":0.5}
```

- `compact_stack`, feedback_bars: agrupa evidencia, panel/personaje y tipografía; usa el tamaño real del texto. Hasta cuatro observaciones; para más se conserva el carrusel original. Reseñas en dos líneas con margen reservado para el tag. Las categorías existentes sustituyen tags largos únicamente cuando coinciden con su prefijo.
- `centered_actor`, spotlight_agent: centra el personaje mediante su padre geométrico; conserva la trayectoria y los demás elementos.
- `centered_primary`, phone_rebuild/terminal_install: organiza la interfaz original, ajusta anchura y escala para que una terminal grande no rebase el lienzo. No convierte el mismo valor de ancla en una posición rígida para todas las proporciones.

Los wrappers adicionales contienen los nodos originales; las animaciones locales no pelean con una transformación CSS de layout. Texto que no cabe se rechaza antes de publicar el render, en lugar de reducirlo indefinidamente.

## Fronteras ejecutables

`handoff` conserva descripción/procedencia semántica. **No es una prueba de animación.** `continuity` solicita una operación real mediante puertos cerrados. `transition_in` dirige el reveal; `transition_out` se deriva de la frontera siguiente para evitar decisiones contradictorias.

```json
{"from_scene":"planteamiento","reason":"La misma IA acompaña el resultado",
 "operations":[{"kind":"actor_pose_match","source_port":"actor","target_port":"actor",
 "asset":"agent_diff","entity_ids":["ia"],"duration":0.6}]}
```

La operación exige recurso efectivo igual, entidades narrativas compartidas, escenas adyacentes, duración0,2–0,6s alineada a30FPS y combinación publicada. Para actores se soportan corte o máscara del wrapper. Un corte deliberado puede conservar continuidad del objeto; no todos los cambios necesitan un efecto.

El puente de actor es una subcomposición real y transparente. Mide los puertos de ambas timelines con sus matrices, mueve el mismo sprite por una curva, cambia su escala y lo entrega al actor nativo. El original se oculta durante el traslado y no repite su entrada. La máscara se ejecuta sobre la escena entrante; los clips y relojes siguen bajo control de HyperFrames.

`device_pose_match` utiliza la identidad vectorial `native:calendar_phone`, no un PNG inventado. Exige la misma app, framing compatible y ausencia de layout que invalide sus poses nativas. Su existencia en catálogo y sus contratos no certifican todos los pares visualmente: la revisión actual valida el actor de B. Las otras combinaciones deben pasar su propio control de render.

El recibo runtime describe poses, tiempos y trayectoria con `execution:gsap_timeline`. Su `execution_verified:false` inicial se verifica aparte mediante QA vinculada a fuentes y MP4; no se convierte en aprobación estética.

## Conclusión de cobertura

```json
{"kind":"coverage_conclusion","at":4.5,"headline":"Cobertura de respuestas"}
```

El tiempo es local a feedback_bars; en B inicia a6,9s. El compositor completa la clasificación con las cifras originales, retira el último titular, desplaza el grupo conjuntamente y revela una conclusión y el límite del guion. No reinicia contadores, añade porcentajes ni crea un ganador. Requiere layout compacto y contexto de cobertura sin inferencia de calidad; no es un cierre universal para todo guion.

## Uso y verificación

```bash
# Revisión editorial explícita del B ya existente, sin nueva inferencia:
python3 -B sistema/clone/b_v2.py render
python3 -B sistema/clone/b_v2.py compare
# Después de inspección actual y QA:
python3 -B sistema/clone/b_v2.py report
```

`b_v2.py` rechaza cambios de familias, parámetros, hechos y tiempos respecto a B_V1. Para un guion nuevo usar `generate.py create`: selecciona capacidades según significado. No usar `generate.py resume` para atribuir esta revisión editorial a la inferencia original; ese comando exige igualdad con su plan privado.

La validación independiente comprueba por separado lectura móvil, colisiones, trayectorias, entrega del actor, estados del cierre, búsqueda directa/inversa y preservación de fuentes. Dos fixtures CPU con dos instancias de teléfono/terminal comprobaron reutilización sin generar otros MP4. La prueba detectó y corrigió una terminal fuera de encuadre; no se cambió su familia. La cobertura corresponde a estas muestras y valores, no a toda combinación posible.
