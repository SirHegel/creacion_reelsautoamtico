Ascendia Studio permite elegir una fuente local para un elemento de texto, ajustar su apariencia y animarlo con un reloj determinista. Son herramientas propias de composición técnica. No certifican fidelidad CLONE ni equivalencia con CapCut Pro o Adobe. En ASCENDIA se conservan Sequel Sans Bold Disp y Scholar Italic; una fuente adicional no las sustituye automáticamente.

El pack local contiene cuatro familias y seis caras estáticas sin modificar. Sus archivos se registran una vez por SHA-256 en `assets/fonts`; los cuatro avisos se conservan en `assets/fonts/licenses`. No se instalan fuentes del sistema ni se consulta un CDN durante el render.

| Familia y variantes | Uso posible | Origen congelado | Licencia y nombres reservados |
|---|---|---|---|
| Source Sans 3 Regular y Bold, OTF | Texto funcional e interfaces | [Adobe, commit ed1808970eb3c7301c9a523bee26473ba0bb62fa](https://github.com/adobe-fonts/source-sans/tree/ed1808970eb3c7301c9a523bee26473ba0bb62fa/OTF), release 3.052R | [OFL 1.1](https://raw.githubusercontent.com/adobe-fonts/source-sans/ed1808970eb3c7301c9a523bee26473ba0bb62fa/LICENSE.md); RFN `Source` |
| Anton Regular, TTF | Titular condensado | [Google Fonts, commit 66928797f271fed5ee428544e7229685e2d90127](https://github.com/google/fonts/tree/66928797f271fed5ee428544e7229685e2d90127/ofl/anton) | [OFL 1.1](https://raw.githubusercontent.com/google/fonts/66928797f271fed5ee428544e7229685e2d90127/ofl/anton/OFL.txt); sin RFN en este aviso |
| DM Serif Display Regular e Italic, TTF | Contraste editorial | [Google Fonts, mismo commit congelado](https://github.com/google/fonts/tree/66928797f271fed5ee428544e7229685e2d90127/ofl/dmserifdisplay) | [OFL 1.1](https://raw.githubusercontent.com/google/fonts/66928797f271fed5ee428544e7229685e2d90127/ofl/dmserifdisplay/OFL.txt); RFN `Source` heredado en el aviso |
| IBM Plex Mono Regular, TTF | Código y texto monoespaciado | [Google Fonts, mismo commit congelado](https://github.com/google/fonts/tree/66928797f271fed5ee428544e7229685e2d90127/ofl/ibmplexmono) | [OFL 1.1](https://raw.githubusercontent.com/google/fonts/66928797f271fed5ee428544e7229685e2d90127/ofl/ibmplexmono/OFL.txt); RFN `Plex` |

Los archivos de fuentes suman 1.132.700 bytes. Se comprobaron nombres, variantes, versiones, SHA, carga con Pillow y una muestra española con tildes, ñ y ¡¿. Eso no acredita todos los idiomas, emoji ni calidad del shaping. Las fuentes permanecen bajo OFL; no reciben la licencia del código del editor. Conservar copyright y licencia al distribuir el pack y sus editables. La OFL tiene condiciones sobre nombres reservados si se modifica una fuente: este pack no convierte, recorta ni altera los archivos. [FAQ oficial de SIL](https://openfontlicense.org/ofl-faq/).

El catálogo distingue `source_verified` —registro local del pack descargado de su origen—, `bundled_notice_unverified` —aviso aportado por un editable— y `supplied_by_user_unverified`. Un aviso incluido en un ZIP no demuestra por sí solo los permisos. La suscripción Adobe Fonts tampoco concede automáticamente permiso para empaquetar sus archivos en un editor; estas familias abiertas tienen licencias independientes. [Condiciones oficiales de Adobe Fonts](https://helpx.adobe.com/fonts/web/font-licensing/font-licensing.html).

Cada elemento puede conservar `font: "primary"` o `"accent"`, o seleccionar explícitamente `font_asset_id`. El ID debe corresponder a un recurso canónico de tipo `font` adjunto al proyecto y con bytes actuales. Se admiten TTF y OTF individuales hasta 16 MiB; WOFF y colecciones TTC quedan fuera. No se sintetizan variantes en negrita o cursiva. `font_info` y `metadata.font_notice` son datos protegidos: editar el JSON de un proyecto no permite reemplazarlos ni inventar una licencia verificada.

`text_style` acepta únicamente estos campos. Las unidades en px1080 se escalan según la anchura del lienzo; las cajas del elemento siguen usando coordenadas normalizadas.

| Campo | Valores o rango | Default |
|---|---|---|
| `align` | `left`, `center`, `right` | `left` |
| `vertical_align` | `top`, `middle`, `bottom` | `top` |
| `letter_spacing` | −16 a 80 px1080; rechazar avances ilegibles | 0 |
| `line_height` | 0,8 a 3 | 1,15 |
| `stroke.width` | 0 a 16 px1080 | 0 |
| `stroke.color` | `#RRGGBB` | `#000000` |
| `shadow.enabled` | booleano | `true` |
| `shadow.x`, `shadow.y` | −40 a 40 px1080 | 2, 4 |
| `shadow.blur` | 0 a 20 px1080 | 0 |
| `shadow.color` | `#RRGGBB` | `#000000` |
| `shadow.opacity` | 0 a 1 | 0,85 |

`font_size` conserva su rango de 8 a 400 px1080 y `color` es el relleno del elemento. No se admiten CSS, URLs de fuente, HTML, scripts, propiedades desconocidas ni números booleanos, NaN o infinitos. Los textos usan una caja explícita: un desbordamiento no activa reducción automática de la fuente. Ajustar la caja o el texto y revisar la captura cuando exista recorte. El fondo del texto puede componerse con una forma editable separada; no existe todavía un control de fondo/padding dentro de `text_style`.

El catálogo ofrece siete valores de entrada, incluido el estado sin animación, y tres de salida. Ninguno procede de una plantilla comercial copiada.

| Entrada | Comportamiento |
|---|---|
| `none` | Texto visible sin entrada |
| `fade_up` | Opacidad y elevación corta |
| `slide` | Entrada desde la izquierda con opacidad |
| `pop` | Énfasis de escala moderado |
| `wipe` | Revelación mediante máscara horizontal |
| `typewriter` | Revelación por grafemas |
| `word_reveal` | Revelación por palabras |

Las salidas son `none`, `fade` y `slide`. `duration` y `exit_duration` admiten 0,01–10 s y deben caber, sumadas cuando están activas, en el reloj original. Estos presets actúan dentro del texto y se combinan con la posición, escala, máscara, trayectoria y keyframes del elemento; no reemplazan su cronología.

El tiempo se evalúa como `elapsed = scene_time - clock_start + clock_offset`. `clock_duration` conserva el intervalo original. Al recortar o dividir, se materializa ese reloj y se desplaza `clock_start`; las mitades mantienen la fase existente. Reiniciar la animación del tramo es una acción explícita distinta. Seek en orden arbitrario debe producir el mismo estado. Las capturas de diseño base ignoran la entrada/salida para permitir revisar el texto completo; cambiar apariencia o fuente invalida su prueba, y los cambios de código/manual invalidan nuevas promociones de renders antiguos.

Pillow/RAQM mide líneas y baselines; el render nativo, SVG/GSAP y canvas consumen esas coordenadas compartidas. `regex` aporta grafemas extendidos para conservar acentos combinados y secuencias de varios puntos de código. Se mantienen espacios y saltos; los tabuladores se expanden a cuatro espacios. El límite es de 2.000 caracteres/grafemas por texto y 8.000 unidades de texto por escena. Expandir tabs puede alcanzar antes el límite efectivo. El layout de vista previa tiene además límites de lienzo y memoria.

Se valida el mapa Unicode de la fuente antes de registrarla. Si falta un glifo visible solicitado, se devuelve un error y no se busca una fuente del sistema ni se declara éxito con un carácter vacío. Un cmap válido no acredita sustituciones contextuales, ligaduras, RTL, shaping complejo o emoji en color. Los avances con kerning tampoco equivalen a sumar anchuras de letras aisladas. El espaciado por unidades puede alterar ligaduras y scripts contextuales: revisar esos casos y no prometer soporte universal. [Medición de texto de Pillow](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html), [segmentación Unicode](https://www.unicode.org/reports/tr29/).

La UI permite importar una fuente, consultar archivo/variante/licencia, aplicarla al texto seleccionado y editar estilo y entrada/salida. La biblioteca no cambia automáticamente crudo, fuente narrativa ni escenas. Para automatización se usan:

- HTTP: `GET /api/font-library`, `GET /api/text-presets`, `POST /api/text-layout`; el último requiere exactamente `project_id`, `element`, `scene_duration`, `width`, `height`.
- CLI: `font-library`, `text-presets` y `text-layout PROJECT_ID ELEMENT_JSON --width 540 --height 960 --duration 5`, ejecutados con `python3 -B -m studio` y el JSON dentro de SOFTWARE.
- MCP: `font_library`, `text_presets`, `text_layout`; el proyecto se modifica por sus herramientas existentes y revisión optimista.

El layout HTTP es una medición sin guardar ni aprobar: devuelve revisión de proyecto y `persisted: false`, `approved: false`. Anchura de vista 64–1080, altura 64–1920, píxeles enteros y duración de escena 0,01–7200 s. Reserva el worker CPU del software antes de medir; no usa GPU, inferencia ni procesos del padre.

El ZIP editable incluye las fuentes utilizadas y sus avisos, comprueba CRC/SHA y remapea `font_asset_id` al reabrir, también en el origen SceneIR. La importación conserva los bytes y deja revisiones y permisos por comprobar. Un paquete HTML/GSAP verificado incluye `fonts/font_manifest.json`, fuentes adicionales por SHA y avisos por SHA; no empaqueta un archivo ajeno al manifiesto de ejecución. No se ejecuta HTML importado ni se heredan aprobaciones.

La comparación funcional sirve para priorizar el desarrollo, no para anunciar paridad:

| Referencia oficial | Disponible en este editor | Pendiente o limitado |
|---|---|---|
| CapCut: entradas, salidas y loops de texto | Entradas/salidas propias, editable y determinista | No biblioteca comercial de plantillas ni loops de texto; no se ha verificado qué recursos pertenecen actualmente al plan Pro. [CapCut](https://www.capcut.com/resource/text-animation-online) |
| CapCut: biblioteca y filtros de fuentes/plantillas | Catálogo local, importación, SHA y avisos de licencia | No copia del catálogo propietario, recursos por región ni acceso remoto. [Ayuda oficial](https://www.capcut.com/help/material-of-text) |
| Premiere: tipografía y estilos | Alineación, espaciado, interlineado, contorno y sombra | Fondo/padding integrado, estilos vinculados globales, rich-text runs y kerning por par editable. [Adobe Premiere](https://helpx.adobe.com/premiere/desktop/add-text-images/stylize-text/parameters-when-applying-as-linked-style-or-track-style.html) |
| After Effects: selectores por carácter, palabra y línea | Revelación por grafema/palabra y movimiento del bloque | Animadores arbitrarios por unidad/línea, rangos combinados, expresiones, 3D por carácter, texto sobre trayectoria y motion blur. La trayectoria actual mueve el elemento completo. [Adobe After Effects](https://helpx.adobe.com/after-effects/desktop/animating-text/text-animation/animating-text.html) |

Las pruebas de `tests/test_typography_audit.py` usan fuentes reales copiadas a un almacén privado y archivos malformados fabricados allí. Cubren SFNT/nombres/cmap, límites, rutas, caché mutable, ausencia de fallback, campos protegidos, errores de payload, reserva CPU y transporte ZIP. Las pruebas de paquete motion simulan únicamente el verificador externo: no afirman ejecución de navegador. La suite del motor comprueba disposición y estados; una captura en navegador y un render real se documentan por separado cuando están disponibles. Ninguna de esas pruebas acredita escucha del audio, estética aprobada ni fidelidad CLONE.

Las huellas y la investigación de origen están en `.estado/validacion/typography_research.json`; ese informe conserva su snapshot histórico de la regla24. La regla25 actual del padre centra su trabajo en B_V2 y mantiene pendiente la estética del usuario: este módulo técnico no ejecuta ese encargo ni reutiliza su aprobación.
