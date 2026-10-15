# Inventario visual completo — CLONE

Fuente canónica: `recursos/B2_CLONE.mp4`; 720 × 1280, 30 FPS, 1.269 frames y **42,300 s de video**. El contenedor/audio dura 42,388 s; su cola no añade otro frame visual. CLONE es la única referencia de motion.

**18 escenas, cobertura continua de 0 a 42,300 s.** Se inspeccionaron 213 muestras consecutivas a 5 Hz, 119 frames adicionales alrededor de 17 cambios de composición a 30 FPS y ocho detalles nativos. Los hitos internos generales son muestras aproximadas; los límites se fijan por frame.

| Escena | Entrada–salida (s) | Familia | Transformación observada |
|---|---|---|---|
| CLONE_001 | 0.000–1.467 | apps_clone_orbit | Un icono Airbnb se duplica; la copia recibe CLONE y se incorporan otras aplicaciones alrededor del par. |
| CLONE_002 | 1.467–3.300 | subscription_cancelled | Las filas suman el precio, son tachadas progresivamente y reciben el sello CANCELLED. |
| CLONE_003 | 3.300–5.933 | github_cards | La tarjeta de repositorio destaca el título y transforma su contenido en About con sello100% FREE. |
| CLONE_004 | 5.933–7.933 | presenter_contract | Texto cambia de and it’s not a one skill/either; dos agentes ilustran pluralidad. |
| CLONE_005 | 7.933–11.133 | pixel_agent_grid | Se construye la plantilla de 11 roles, aparecen sus nombres y las herramientas identifican cada función. |
| CLONE_006 | 11.133–12.733 | phone_recon | Un círculo de inspección recorre la interfaz de reservas y aparecen resultados de la revisión. |
| CLONE_007 | 12.733–13.867 | phone_rebuild | La interfaz pasa de una capa azul esquemática a una interfaz crema/coral manteniendo su estructura. |
| CLONE_008 | 13.867–15.367 | phone_qa | Bugs rojos aparecen sobre la interfaz; la lista se completa con checks y el resultado comunica0 bugs/all flows pass. |
| CLONE_009 | 15.367–18.567 | phone_compare | Entran los dos teléfonos; la métrica llega a100% y las pantallas se sustituyen por cinco pares de aplicaciones. |
| CLONE_010 | 18.567–20.333 | presenter_contract | El texto but the/craziest part cambia la jerarquía del argumento. |
| CLONE_011 | 20.333–21.600 | spotlight_agent | Enciende el foco, entra el agente y caen pequeñas partículas cálidas antes de asentarse. |
| CLONE_012 | 21.600–24.200 | radial_research | Se añaden nodos, se conectan al agente, circulan partículas y el contador llega a140 reviews read. |
| CLONE_013 | 24.200–28.733 | feedback_bars | Las reseñas se apilan/desplazan; etiquetas clasifican problemas y las barras se construyen por categoría. |
| CLONE_014 | 28.733–31.600 | problem_resolution | Los problemas aparecen en cápsulas rojas, desaparecen al activarse toggles verdes y se muestra4 problems solved. |
| CLONE_015 | 31.600–32.967 | presenter_contract | Texto you don’t just get y a clone enfatiza el cambio de resultado. |
| CLONE_016 | 32.967–34.900 | product_card | La ficha de producto entra; agentes de marca/lanzamiento/despliegue la acompañan y aparece el estado publicado. |
| CLONE_017 | 34.900–38.967 | terminal_install | Se escribe la URL de GitHub y una instrucción; avanza Installing 11/11 y los agentes se activan con checks. |
| CLONE_018 | 38.967–42.300 | agent_marquee | La fila de agentes se mueve continuamente; el texto pasa de save this a andcomment/clone y promesa de envío. |

## Familias y evidencia

Las escenas se distinguen por composición y propósito, no por cada frame o título. Las cuatro escenas de cámara son contratos/puentes; el motor no reutiliza su footage. Los móviles comparten carcasa e interfaz, pero inspección, reconstrucción, QA, comparación y resolución requieren acciones y variantes independientes.

Evidencias en `.estado/tmp/clone_inventario`: `vista_completa_1fps.jpg`, `secuencia_00.jpg` a `secuencia_04.jpg` y `limites_0.jpg` a `limites_3.jpg`. Cada escena del JSON incluye rutas, frames y hashes de evidencia.

Roles legibles en frame 0300: `/recon`, `/architect`, `/design`, `/build`, `/backend`, `/test`, `/diff`, `/entrepreneur`, `/brand`, `/launch`, `/deploy`. Recon muestra **18 screens**, 7 flows y data model. QA termina con 0 bugs / all flows pass. Slotly muestra 4.9★ / Flat / Live; la terminal representa la instalación 11/11 y el estado Ready. Son datos del diseño fuente, no métricas verificadas de un reel nuevo.

## Lenguaje observado

- Escenas blancas de exploración y proceso contrastan con escenas negras de costo, comparación y producto; los cambios se vinculan a acciones.
- Pixelart naranja consistente con herramientas distintas para funciones: grid, nodos, mockups, producto y marquee.
- Móviles con carcasa, notch, calendario, controles y estados internos; la acción transforma la interfaz.
- Editoriales inferiores con serif italic de alto contraste; UI sans y terminal monoespaciada. Las fuentes originales no están identificadas.
- Contadores, tachados, máscaras, scroll, trayectorias, toggles, checks y despliegue construyen estados conectados; una entrada aislada de tarjeta no reproduce toda la secuencia.

## Alcance y límites

El componente CANCELLED aprobado permanece intacto; el inventario amplía la referencia al video completo. No se utilizaron AGENT/EDIT, stock ni b-roll. La biblioteca, cada preview y el generador requieren implementación y QC posteriores; este documento completa únicamente la etapa A. YO queda como contrato futuro de split 55/45, cámara auténtica y subtítulos bajo la barbilla.

No se escuchó audio. No se identificaron fuentes originales ni curvas de animación. Las cifras y reseñas del render se tratan como datos de referencia; las variantes deben recibir datos explícitos, sin fabricar resultados.
