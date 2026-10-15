# Sistema visual CLONE

CLONE es la única referencia de motion de esta biblioteca. YO define la futura integración de cámara y subtítulos. Esta fase produce componentes y un motor generativo; no un reel completo. La producción por lotes está autorizada: registrar piezas pendientes y continuar las independientes, sin solicitar aprobación de cada unidad.

La fuente es [B2_CLONE.mp4](../../recursos/B2_CLONE.mp4), 720 × 1280, 30 FPS, 1.269 fotogramas y 42,300 s de vídeo. Se inspeccionaron 213 fotogramas a 5 Hz que cubren todo el vídeo, seis contactos y fotogramas nativos adicionales. El sello de cancelación también se contrastó en 48 fotogramas consecutivos. Esto no significa que se hayan revisado a 30 FPS los 42 segundos completos. Los límites de escenas refinados a 30 FPS proceden del inventario independiente.

Los tokens consumibles están en [design-system.json](design-system.json). Sus valores distinguen muestreo real del MP4, implementación aprobada y aproximaciones nuevas. No se han recuperado las fuentes ni el proyecto original de CLONE.

## Paleta y composición

| Función | Color | Evidencia |
| --- | --- | --- |
| Lienzo claro | `#f3f3f5` | F264/366, esquinas y márgenes |
| Centro claro | `#f6f6f9` | F264, x350/y90 |
| Lienzo oscuro | `#000000` | F462, comparación |
| Panel oscuro | `#19191b` | F798, barras; F1020, producto |
| Terminal | `#171712` | F1080, superficie interior |
| Clay de clasificación | `#d77357` | F804, barra de funciones |
| Ámbar de problemas | `#dd8302` | F804, barra de problemas |
| Rojo de riesgo | `#ff3529` | F852, barra de críticas |

Son colores de vídeo comprimido, no valores originales de CSS. Negro, gris claro y clay alternan según el argumento. No añadir retículas de AGENT, glow cian, texturas o fondos por costumbre. El espacio negativo observado es deliberado: un objeto principal, sus estados y una conclusión editorial mantienen la jerarquía. Las marcas conservan sus colores auténticos.

Trabajar en 720 × 1280 y escalar el lienzo entero 1,5× para 1080 × 1920. Tarjetas, móviles, avatares y textos se solapan y se reorganizan; no utilizar una cuadrícula de tarjetas iguales como respuesta universal. Las sombras suaves y la oclusión producen profundidad 2.5D. Una apariencia inclinada no demuestra que la referencia utilice modelos 3D.

## Tipografía

| Rol | Recurso local | Relación con la fuente |
| --- | --- | --- |
| Interfaz y cuerpo | Inter 400/700 de `hyperframes-creative` | Aproximación; nombre original no identificado |
| Display e identidad | Sequel Sans Bold Disp | Fuente solicitada; aproximación ya aprobada en CANCELLED |
| Énfasis editorial | Scholar Italic | Aproximación: CLONE presenta una serif cursiva más estrecha |
| Comandos y roles | JetBrains Mono 400/700 | Aproximación local con OFL |

Los textos editoriales de CLONE son grandes, altos, en ocasiones en mayúsculas, con contraste serif y zona inferior independiente del objeto. Los ejemplos observados suelen ocupar y1040–1180. No convertir la interfaz entera en titulares ni generalizar la altura de sus textos a los subtítulos de YO. El contorno de **AGAIN** es una palabra SVG fija; no una fuente válida para textos arbitrarios.

Medir texto una vez al construir. Reducir tamaño dentro de límites o distribuir contenido antes de aceptar desbordamientos. La posición del subtítulo de YO será centrada bajo la barbilla al integrar grabación; su sombra negra compacta es un contrato distinto de la tipografía editorial CLONE.

## Familias y secuencias observadas

| Familia | Fuente | Acción que debe mantenerse |
| --- | --- | --- |
| Apps en constelación | 0–1,467 s | Protagonista → duplicación → apps relacionadas → reorganización |
| Cancelación | 1,467–3,300 s | Costes → total → tachado consecutivo → sello → resolución |
| Evidencia GitHub | 3,300–5,933 s | Identidad del repo → datos con origen → About/licencia → conclusión |
| Once agentes | 7,933–11,133 s | Equipo de roles 4+4+3 → funciones → activación/reorganización |
| Reconstrucción móvil | 11,133–13,867 s | Original → escaneo → estructura → wireframe → construcción |
| Test móvil | 13,867–15,367 s | Errores sobre UI → tests → validación ligada a errores |
| Comparación | 15,367–18,567 s | Original/clon → estados comparados → indicador → nuevas variantes |
| Agente en foco | 20,333–21,600 s | Foco oscuro → personaje/prop → rol y propósito |
| Fuentes de feedback | 21,600–24,200 s | Fuentes radiales → consulta → transferencias → resultado |
| Clasificación de reseñas | 24,200–28,733 s | Cola de citas → etiquetas → barras y contadores |
| Solución de problemas | 28,733–31,600 s | Problema → acción de UI → cambio de estado → solución |
| Publicación de producto | 32,967–34,900 s | Producto → entrega por agentes → estado de publicación |
| Instalación en terminal | 34,900–38,967 s | Comando → proceso → agentes activos → ready |
| Desfile y CTA | 38,967–42,300 s | Avatares en movimiento → rol destacado → CTA suministrada |

Los puentes con cámara se catalogan en el inventario, pero no se recupera el rostro ajeno como recurso de esta biblioteca. Los sprites originales se extraen por rol y los seis logos previamente aprobados se conservan por ruta; el motor utiliza recortes mayores originales de Duolingo/Notion/Spotify para evitar ampliar60px. El manifest canónico [assets.json](assets.json) registra archivo, recorte, fuente y SHA.

## Movimiento y causalidad

Cada composición debe tener entrada, acción, reacción, resultado y salida. Una búsqueda produce fuentes; fuentes producen datos; datos producen una conclusión. Una toggle solo elimina el problema que resuelve. El gesto del avatar y el cambio de UI deben responder a la misma acción. Fade, scale-in y líneas pueden acompañar la secuencia, pero nunca constituir toda la explicación.

Como arranque: entradas 0,12–0,30 s; tarjetas 0,20–0,40 s; impacto 0,15–0,30 s; transformación 0,20–0,60 s. Son parámetros de las directivas, no keyframes recuperados. Variar duración, dirección y curva según peso/acción. No añadir cámara permanente a todas las piezas. El flash F86–88 y la sacudida del sello son intencionales; no legitiman flashes aleatorios.

Las timelines GSAP son pausadas, finitas y reproducibles al seek. Separar movimiento de cámara y acción interna en nodos distintos; evitar transforms simultáneos conflictivos. No cambiar layout mid-tween ni usar relojes, azar o animaciones CSS externas. No aplicar blur como relleno. Un blur transitorio de un glifo observado es un efecto local diferente.

## Base aprobada y límites

[diseno.svg](../../ejemplos/clone_componente/diseno.svg), su PNG y [frame.md](../../ejemplos/clone_componente/frame.md) permanecen intactos. Sus hashes están fijados en el JSON. Sus medidas, logos, sello y contorno AGAIN son la base aprobada; las variantes paramétricas no la sustituyen silenciosamente.

El motor puede combinar y transformar estas familias para una idea no literal del vídeo. Debe interpretar frase completa, entidades, acciones, relaciones y resultado. Números como 100 % de paridad, 140 reseñas o 4,9 de rating son contenidos de la referencia, no resultados demostrados para un nuevo proyecto. Las interfaces reconstruidas son conceptuales salvo evidencia de una demostración auténtica.

Validar por separado estabilidad técnica, reproducción de estados, ajuste de parámetros, causalidad y fidelidad visual a CLONE. Una coincidencia HTML/MP4 no prueba por sí sola fidelidad estética. Registrar lo pendiente sin atribuir fuentes identificadas, ejecuciones reales ni aprobaciones que no existen.
