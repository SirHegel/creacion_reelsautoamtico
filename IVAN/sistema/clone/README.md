# Motor generativo CLONE

**Encargo vigente: integración Ascendia + CLONE V2.** Mantener las quince familias, CANCELLED y V1. Leer el manual completo y `INTEGRACION_YO.md`; replanificar con el Brand Asset Registry auténtico y contexto explícito. Los tiempos de lectura se adaptan mediante `phase_clock`, sin retimar voz. El director YO mantiene cámara, hook y split 55/45. Recursos, familias y permanencias se verifican en el render; no se aprueba estética por un PASS técnico. Guía de marcas en `BRAND_ASSETS.md`.

**Historia B_V2:** conserva la estructura elegida de B, añade composición flexible, continuidad ejecutable de personaje y conclusión de cobertura. Abrir `proyectos/clone_motor/creatividad/comparacion/B_V2.html`; controles y API en `COMPOSITOR.md`. `python3 -B sistema/clone/b_v2.py render/compare/report` reanuda la revisión editorial sin repetir inferencia. B_V1 se conserva para comparar; las 15 familias y CANCELLED siguen intactos. La aprobación estética de B_V2 está pendiente.

La revisión actual del generador está en `proyectos/clone_motor/creatividad/galeria.html`: tres pruebas de nueve segundos, planes, comparaciones con CLONE y pendientes editoriales. Se reutilizan seis familias seleccionadas por significado; `composition_graph` ya no tiene prioridad universal. La biblioteca anterior de 15 familias y CANCELLED se conserva. Estas tres pruebas esperan aprobación estética antes de integrar YO. Consulta `proyectos/clone_motor/creatividad/INFORME_FINAL.md`.

Ejecutar desde la carpetaIVAN. Reutiliza HyperFrames0.8.147, GSAP3.15, Chrome/Playwright, FFmpeg9/NVENC y la instalación local de Codex ya existentes. No ejecutar `npm install`, no actualizar dependencias globales. Los directorios privados y render se confinan a IVAN mediante los wrappers existentes.

## Generar desde un guion

```bash
python3 -B sistema/clone/generate.py create \
  --script 'Describe aquí el concepto completo que se debe explicar.' \
  --duration 10 \
  --out proyectos/clone_motor/mi_encargo
```

La herramienta comprueba primero el manual vigente y el registro de las12skills locales. Si cambian, exige actualizar la auditoría documentada antes de renderizar. Después realiza inferencia semántica real, valida el SceneIR, compila HTML/SVG/GSAP, renderiza y comprueba la timeline mediante navegador. Guarda `generation.json`, `scene.json`, `index.html`, `preview.mp4`, `poster.png`, recibos deQC y diagnóstico. En composiciones de varias escenas también conserva los archivos hijos editables.

`--script-file` acepta un guion local. `--narration` acepta alineación real de voz; sin ella los tiempos se declaran propuestos. `--plan-only` termina tras la inferencia. Si falla el proveedor o un contrato, queda un motivo pendiente; no se construye una infografía de sustitución silenciosa.

Para reanudar un render después de corregir un defecto sin repetir la inferencia: `python3 -B sistema/clone/generate.py resume proyectos/clone_motor/mi_encargo`. Verifica el recibo y el plan canónico privado; rechaza modificaciones semánticas no justificadas.

Un resultado nuevo se registra como `pending_editorial_review`. La revisión por un agente inspecciona el MP4, compara el lenguaje visual con CLONE y guarda observaciones y límites por separado. Para promover una variante ya revisada:

```bash
python3 -B sistema/clone/generate.py promote proyectos/clone_motor/mi_encargo \
  --review proyectos/clone_motor/mi_encargo/style_review.json
```

El recibo exige SHAactual del MP4 y la composición, evidencia de referencia, revisor y los cinco checks editoriales. No hay aprobación automática basada únicamente en correlación con HTML.

## Editar/renderizar una composición existente

```bash
python3 -B sistema/clone/engine.py catalog
python3 -B sistema/clone/engine.py compile proyectos/clone_motor/mi_encargo/scene.json \
  --out proyectos/clone_motor/mi_encargo
python3 -B sistema/clone/engine.py render proyectos/clone_motor/mi_encargo
node sistema/clone/review.mjs proyectos/clone_motor/mi_encargo
python3 -B sistema/clone/report.py
```

Los previews son ejemplos independientes editables; no hay duplicados de módulos por escena. La galería se abre en `proyectos/clone_motor/galeria.html`. El registro distingue familias verificadas en su alcance, aproximaciones de diseño y variantes pendientes. Cada comparación de reconstrucción utiliza fotogramas del CLONEoriginal a fases equivalentes.

## Rutas principales

- `inventario_escenas.json` / `INVENTARIO_CLONE.md`: cobertura completa y movimientos observados.
- `design-system.json` / `DESIGN_SYSTEM.md`: paleta, tipos, proporciones, espacios, profundidad y reglas de movimiento.
- `assets.json` / `recursos/clone`: sprites y recursos extraídos originales, claves y procedencia.
- `runtime.js` / `components`: registro común y familias configurables.
- `planner.py` / `scene_schema.json` / `PLANNER.md`: significado del guion, guardas y proveedor real.
- `engine.py` / `review.mjs` / `compare.py`: compilación, render local, relojes y comparación con referencia.
- `variantes.json`: nuevas composiciones verificadas o pendientes; una receta sigue usando los módulos canónicos.
- `EXTENDER_BIBLIOTECA.md`: cómo agregar primitivas/familias sin romper el contrato.
- `INTEGRACION_YO.md`: entradas, cámara, split55/45, barbilla, subtítulos y audio futuros. Aún no implementa el reel completo.

## Uso futuro

Leer siempre `AGENTS.md`, `PROMPT_MAESTRO.md` e `INSTRUCCIONES.md` completos y sus modificaciones antes de editar. Consultar el registro actual y las12skills locales. Separar guion/voz comprobados de ejemplos conceptuales; no heredar precios, métricas o repositorios de los ejemplos como hechos de otro cliente. ConservarCANCELLED aprobado.

La biblioteca reutiliza la identidad gráfica deCLONE sin copiar su presentador. Las fuentes exactas deCLONE no están identificadas: las aproximaciones se documentan. Sequel/Scholar sí se usan como fuentes reales del proyecto; la futura narración sigueYO. No se promete que cualquier longitud de texto quepa: el motor rechaza valores fuera de límites y pide dividir una idea demasiado grande.
