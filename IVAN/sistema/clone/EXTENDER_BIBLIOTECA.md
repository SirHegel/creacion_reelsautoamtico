# Ampliar la biblioteca CLONE

La biblioteca es infraestructura editable, no una lista cerrada de plantillas. Un concepto nuevo puede combinar primitivas, cambiar su organización y construir una secuencia distinta, manteniendo el sistema visual CLONE. YO solo aporta el contrato de futura cámara/textos en [INTEGRACION_YO.md](INTEGRACION_YO.md).

Leer los manuales completos y las skills locales aplicables antes de implementar; registrar decisiones y evidencias. No instalar por rutina. Mantener un único componente canónico por familia, reutilizar código funcional y preservar hashes de CANCELLED aprobado. No usar AGENT/EDIT, b-roll/stock o capturas estáticas como relleno.

## Organización y fuente visual

| Archivo | Papel |
| --- | --- |
| `inventario_escenas.json` | Secuencias observadas, tiempos, estados y evidencias de CLONE completo |
| `design-system.json` / `DESIGN_SYSTEM.md` | Tokens centrales, origen de mediciones y aproximaciones honestas |
| `assets.json` | Clave → recurso original, ruta, medidas, frame/crop y SHA; aliases sin copias |
| `runtime.js` | Registro, contexto de instancia y utilidades SVG/GSAP |
| `components/*.js` | Familias independientes con defaults, parámetros y `build(C)` |
| `engine.py` | Catálogo, validación/compilación SceneIR, revisión técnica, render y galería |
| `proyectos/clone_motor/` | Ejemplos editables, previews reales, QC y galería; sin versiones repetidas |

Un recurso extraído de la referencia conserva procedencia y aspecto; no se declara por ello una licencia general de redistribución comercial. Registrar que lo suministró el usuario y el uso autorizado. Conservar logos auténticos; no recolorearlos como marca oficial ni fingir que una UI conceptual es una demo ejecutada. Las cifras del vídeo original son contenido de referencia, no nuevos resultados comprobados.

## API vigente

Un módulo registra una familia con `window.Clone.register(id, definition)`. `definition.build(C)` coloca su DOM/SVG en `C.root` y devuelve una timeline GSAP pausada. Requiere `durationRange`; puede incluir `defaults`, `parameters`, `description`, `reference` y `source`. El runtime rechaza IDs repetidos, build ausente, duración fuera de rango y timeline inválida. Añadir validación semántica de parámetros dentro de la familia, no asumir que el límite genérico de texto/listas resuelve el layout.

Ejemplo de estructura, no un componente avanzado suficiente:

```javascript
(() => {
  const Clone = window.Clone;
  Clone.register('nombre_unico', {
    description: 'Acción, reacción y resultado que comunica esta familia',
    durationRange: [2.4, 8],
    defaults: { entity: 'Ejemplo conceptual', caption: '' },
    parameters: { entity: 'texto validado' },
    reference: [{ source: 'recursos/B2_CLONE.mp4', entry_s: 0, exit_s: 1.4 }],
    build(C) {
      // Dibujar grupos, máscara, estados y contenido con IDs de instancia.
      // Añadir entrada → acción → reacción → resultado → salida.
      const tl = gsap.timeline({ paused: true });
      return tl;
    }
  });
})();
```

Usar `Clone.build(family, root, params, duration, prefix)` devuelve `{tl, definition, context}`. Cada prefix debe ser único y estable. En una escena, el compilador integra la timeline en el reloj principal. Con varias escenas crea archivos HTML independientes con `<template>`, estilos y scripts locales, montados mediante `data-composition-src`; el transporte HyperFrames convierte el tiempo global en tiempo local para cada timeline. No anidar estas timelines en la principal ni ejecutar un segundo seek manual. No iniciar `play()` ni registrar una instancia vacía antes de completar fuentes/DOM.

Utilidades del contexto actual:

- `id(name)`, `q(name)`: IDs y consulta limitados a la instancia; máscaras/gradientes también llevan namespace.
- `svg(inner)`, `text(x,y,value,options)`, `escape(value)`: composición nativa 720 × 1280 y texto seguro; no aceptar HTML/script del guion.
- `image(key,...)`, `sprite(key,...)`: recurso canónico; sprite respeta proporción y raster pixelado original.
- `fit`, `editorial`, `caption`: ajuste tipográfico y jerarquía. Comprobar límites legibles; no encoger indefinidamente.
- `counter`, `draw`: estados numéricos y trazado sobre la timeline. Revisar ida/vuelta del seek, no solo reproducción desde cero.
- `colors`, `design`, `shadow`, `soft`, `t(fraction)`: tokens/tiempo local; no reconstruir la paleta por componente.

Alias de fuente usados por los módulos deben coincidir con `font_css()` del compilador. Una fuente disponible en disco pero no cargada con el nombre solicitado puede producir fallback silencioso; comprobar el texto renderizado.

## Contrato de movimiento

Crear objetos independientes para movimiento de cámara, entrada de grupo y acción interna; no superponer transforms conflictivos del mismo nodo. Mantener posición base del SVG en una envoltura estática y mover su hijo animado, o definir una única secuencia de transforms. Evitar sobrescribir un `translate` de posición con un `x:0` de entrada.

Precalcular rutas y tamaños antes del tween. La timeline debe depender solo del tiempo local: sin `Math.random`, timers, reloj de pared, red durante render ni loops infinitos. Añadir callbacks de contador idempotentes y verificar seek no lineal. Preferir transforms a layout; máscaras y morphs deben revelar o transformar información, no ocultar fallos de encuadre. Evitar `rotationY`/preserve-3d que recorten capas en Chrome GPU; comprobar cualquier profundidad en MP4 nativo.

Cada familia importante tiene composición inicial, acción, reacción, resultado y salida conectada. Fade, scale-in, tarjetas secuenciales o una línea entre logos son herramientas secundarias. Si al quitar esos elementos no queda una explicación visual, la pieza no cumple. Una variante nueva no puede validar su estilo usando solo correlación con su propio HTML.

## SceneIR y compilación

El SceneIR actual utiliza `schema_version: 1` y una lista `scenes`. Cada escena contiene `id`, `family`, `start` opcional, `duration`, `content`, `objective`, `params`, `actions`, `composition` y `transition_in/out`. El engine comprueba familias, IDs, tiempos, parámetros y acciones locales; no supone que la intención editorial ya esté resuelta.

```json
{
  "schema_version": 1,
  "id": "equipo_conceptual",
  "scenes": [{
    "id": "roles_en_accion",
    "family": "pixel_agents",
    "duration": 3.2,
    "content": "Un equipo investiga, diseña y construye una respuesta.",
    "objective": "Mostrar funciones distintas que coordinan un resultado",
    "params": {
      "roles": ["recon", "design", "build"],
      "result": "RESPUESTA PREPARADA",
      "caption": "FUNCIONES COORDINADAS"
    },
    "actions": [],
    "composition": "full_motion",
    "transition_in": {"kind": "cut", "duration": 0},
    "transition_out": {"kind": "cut", "duration": 0}
  }]
}
```

Los contenidos conceptuales y sus tiempos no afirman narración grabada ni ejecución de software. El generador debe comprender frase completa y relaciones, escoger/combinar componentes y producir parámetros/acciones causales. Con audio real se incorpora la alineación comprobada; sin audio no inventar word timestamps.

Desde IVAN, las operaciones implementadas por `engine.py` son:

```bash
python3 -B sistema/clone/engine.py catalog
python3 -B sistema/clone/engine.py compile proyectos/clone_motor/ejemplo.scene.json --out proyectos/clone_motor/ejemplo
python3 -B sistema/clone/engine.py render proyectos/clone_motor/ejemplo
python3 -B sistema/clone/engine.py gallery
```

`defaults` prepara ejemplos y `batch --workers 1` procesa los ejemplos con aislamiento. No usar esa operación para afirmar que un registro sin preview/QC ya está construido o validado. Serializar renders si el pipeline/hardware comparte buffers; no llenar RAM/VRAM por obligación. Los fallos de una pieza se registran pendientes y no impiden preparar las independientes.

## Correspondencia con el inventario

Hay 18 secuencias continuas: 15 familias de motion y tres puentes de cámara `presenter_contract`. El sistema de diseño agrupa recon/build como una familia lógica, mientras el catálogo implementa sus dos estados por separado. Esa diferencia de granularidad no es una omisión.

| Familia del inventario | Implementación canónica |
| --- | --- |
| `apps_clone_orbit` | `research.js` → `apps_clone_orbit` |
| `subscription_cancelled` | Adaptador `engine.py` → `cancelled`, también incluido en catálogo; reutiliza componente aprobado |
| `github_cards` | `proof_cards.js` → `github_cards` |
| `pixel_agent_grid` | `agents.js` → `pixel_agents` |
| `phone_recon`, `phone_rebuild`, `phone_qa`, `phone_compare` | `devices.js`, mismos IDs |
| `spotlight_agent` | `agents.js`, mismo ID |
| `radial_research`, `feedback_bars` | `research.js`, mismos IDs |
| `problem_resolution` | `devices.js`, mismo ID |
| `product_card` | `proof_cards.js`, mismo ID |
| `terminal_install` | `terminal.js`, mismo ID; comprobar su preview y QC antes de declarar validación |
| `agent_marquee` | `agents.js`, mismo ID |
| `presenter_contract` | Contrato futuro YO; no capturar ni reutilizar presentador ajeno |

CANCELLED conserva el intervalo aprobado 1,6–3,2 s y sus archivos fuente. El inventario registra la escena original más amplia, 1,467–3,300 s: reutilizar el segmento aprobado no demuestra por sí solo reproducción de los bordes adicionales. No rediseñar la base para esconder esa diferencia ni contar una ruta especial como una segunda implementación.

## QC y estados de validación

Guardar por componente y variante: spec/código/recursos/hash actuales, MP4, decodificación completa, fotogramas consecutivos, estados significativos y pendientes. Separar:

1. **Técnica:** duración, resolución/FPS, ausencia de frames corruptos/bandas, timeline determinista y estados correctos al seek.
2. **Movimiento:** curvas, rutas, interacción, ritmo, transformación, continuidad y salida; no aceptar diapositivas.
3. **Fidelidad:** comparación con los estados y composición de CLONE para reconstrucciones. Aproximaciones de fuentes y trazos declaradas.
4. **Reutilización:** cambiar textos/números/roles/recursos y duración dentro del rango; comprobar overflow, legibilidad, causalidad y ausencia de IDs compartidos.
5. **Consistencia de variante:** evaluar concepto nuevo frente al sistema CLONE; no exigir una escena literal inexistente ni presentarla como prueba real de software.

Usar estados distintos de render técnico, revisión visual pendiente, verificado en su alcance y fallido/pendiente con motivo. No convertir métricas automáticas en aprobación estética ni aprobar retroactivamente una pieza tras cambiar código/manuales. La autorización de producción por lotes ya existe; continuar sin prompts redundantes de aprobación individual. Registrar lo que todavía no cumple y reconstruir la pieza antes de promoverla como final.
