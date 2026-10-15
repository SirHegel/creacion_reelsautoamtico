> Plantilla pública desidentificada. Las referencias y autorizaciones históricas describen un flujo de ejemplo; configure insumos y accesos propios. Los medios, transcripciones y comprobantes privados no se distribuyen.

# Identidad audiovisual YO — perfil observado para ASCENDIA V5

Referencia: https://example.invalid/recurso Archivo canónico: `recursos/A3_YO.mp4`, SHA256 `e1b65353565fa839e17a35a05b72755524c2551a88afdca25c14431757eac68f`; 720 × 1280, 30 FPS, 51,059 s.

Se examinaron 100 fotogramas del hook a 10 Hz, 41 del resto a 1 Hz y secuencias de transiciones a 30 FPS. Las evidencias y medidas están en `assets/referencias/YO/inspeccion.json`, sus montajes y `medicion_rostro.json`. No se afirma audición perceptiva del audio ni acceso al proyecto original.

## Hook y entrada de texto

YO comienza directamente con b-roll real de Elon Musk arriba e Presentador abajo, ambos a ancho completo, divisor recto cerca de 50/50. Se ven rostro, hombros, micrófono, mesa y fondo auténtico. No hay tarjeta redondeada, márgenes ni duplicado desenfocado.

El titular se construye como una frase: «Elon Musk» desde aproximadamente 0,10 s; se agrega «está» hacia 0,55 s; «furioso» aparece hacia 0,97 s como segunda línea mayor. La frase permanece mientras se completa, con desplazamiento/revelación breve. No se reinicia cada palabra como una transcripción automática. El nombre es amarillo, «está» blanco y «furioso» rojo: son colores observados, no una obligación cromática para V5. La segunda línea roza el divisor; es texto editorial sobre el b-roll, no un subtítulo tradicional del presentador inferior.

Un burn luminoso entra alrededor de 1,267 s; hacia 1,50 s se ve cámara completa. Aparecen textos blancos breves bajo la barbilla: «y todos», «los CEO’s», «de la IA», «del planeta». Otro burn alrededor de 2,767 s conduce a entrevista real con Jensen Huang; entre 3 y 4,2 s la entrevista conserva subtítulos. Desde unos 4,433 s vuelve un split con NVIDIA animado arriba. A 5,800 s hay corte a cámara; a 6,2 s se construye «acceso / gratuito», con segundo término mayor. A 6,767 s entra un artículo real de Medium con acomodo/acercamiento de unos 0,25 s. Un burn hacia 9,267 s devuelve la cámara alrededor de 9,433 s.

## Tipografía, sombra y rostro

La jerarquía distingue subtítulo tradicional, titular y palabra de impacto. Ajustes aproximados de anchura con el archivo real Sequel, escalados a 1080 × 1920:

| Función observada | Tamaño inicial orientativo |
|---|---:|
| Titular «Elon Musk está» | 114–115,5 px |
| Subtítulo «del planeta» | 72 px |
| Énfasis «acceso» | 108 px |
| Énfasis mayor «gratuito» | 142,5 px |
| Identificación de herramienta en split | 90 px |

Son ajustes de apariencia y anchura; el MP4 no permite probar su CSS ni identificar inequívocamente las fuentes. Para la producción son obligatorios los archivos auténticos Sequel Sans Bold Disp y Scholar Italic. Scholar se reserva para contraste editorial selectivo; no se ha identificado con certeza en estas muestras de YO.

MediaPipe midió barbilla y604,8 y comienzo del texto y658 en el fotograma 2,40 s, a resolución 720 × 1280. En 6,30 s son y596,3 y y653. Equivalen a una separación visual aproximada de 80–85 px a 1080, incluyendo el espacio interior del glifo. El centrado es cercano a x360, equivalente a x540. Estas muestras orientan el diseño; no justifican fijar la altura en todo el video. La instrucción V5 exige texto tradicional inmediatamente bajo barbilla, recalculado y suavizado según el rostro.

La sombra visible es negra, corta, marcada debajo/derecha y con borde nítido. No hay nube gris amplia. `2px 4px 5px rgba(0,0,0,.85)` es un punto de partida autorizado y compatible; no son parámetros medidos del original. Comparar visualmente con `assets/referencias/YO/talking_subtitulo.jpg`. La captura exacta «porque ahora» no está disponible; no declarar comparación exacta con ella.

## Composición, b-roll y ritmo

El split combina una grabación humana completa en su región con un recurso reconocible y en movimiento. El recurso superior cambia de función: entrevista, marca, navegación de software, API/código. No depende de un mismo fondo vacío con tarjetas.

Entre aproximadamente 10,63–14,5 s aparecen fichas reales de modelos en split. Entre 15–19 s, página real de NVIDIA con cursor y selección sobre fondo oscuro. Cerca de 19,5–21,8 s, split con API/código; después terminal completa. En 27–31 s se desplazan páginas/listas reales, a veces con texto sobre un pequeño fondo negro. Hay cambios de encuadre en cámara y transiciones luminosas puntuales; no un zoom lineal continuo. Al final se combina cámara, recurso de clase y énfasis grande «YO».

Los cambios de composiciones del hook duran aproximadamente 1–2,5 s. Las fuentes reales permanecen el tiempo necesario para comprender la acción. No se midieron curvas de easing exactas. No se afirma haber evaluado de oído la música o los FX.

## Aplicación a nuevos crudos

V5 exige 55 % superior y 45 % inferior como punto de partida: es una modificación del usuario, no la proporción exacta observada en YO. Exige también máximo 3 s continuos de presencia visible, incluso en split; algunos intervalos históricos de YO son más largos y no se copian. Mantener el fondo auténtico y el tamaño natural del rostro. Prohibidos blur añadido, relleno duplicado y fondos artificiales.

Construir el hook según su frase completa, con titular integrado, demostración o narración visual. Blanco predominante; carbón cuando el recurso es claro; rojo para riesgo, pérdida, conflicto o provocación contextual. No copiar el amarillo/verde ni colorear nombres de herramientas arbitrariamente. Conservar texto durante b-rolls mediante subtítulos o tipografía dinámica, sin duplicar el mismo mensaje.

AGENT, EDIT y CLONE elevan la ambición técnica: estados que se transforman, arrastre de información, cambios de profundidad y reacciones a una acción. Sus secuencias 12–14,75 s, 7–9,75 s y 1,8–3,12 s fueron inspeccionadas. No copiar cifras, paletas ni sustituir la identidad de YO. Un fade de tarjetas no cumple. Cada escena debe resolver una acción visual y enlazar con la siguiente.

Este perfil se reutiliza como criterio de dirección, no como montaje fijo. Cada crudo necesita análisis, selección contextual, storyboard nuevo y revisión en movimiento.
