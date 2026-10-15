# Alcance de fidelidad y comparación

Esta biblioteca deriva sus familias de CLONE completo. Un componente parametrizable es una reconstrucción/adaptación editable; no se afirma que sea el proyecto original ni una copia exacta de todos sus frames. La aprobación del diseño CANCELLED revisión2 se refiere exclusivamente a esa base y su intervalo animado. No se extiende automáticamente al resto del catálogo.

Las evidencias canónicas del original están en `inventario_escenas.json`: frames de estados, límites a 30 FPS y contactos de todo el vídeo. El diseño central registra qué colores se muestrearon, qué medidas se estimaron y qué fuentes locales son aproximaciones. La cobertura a 5 Hz de los hitos internos tiene una precisión diferente de las secuencias de límites revisadas a 30 FPS.

## Familias de personajes

| Familia | Qué conserva | Qué adapta y debe compararse |
| --- | --- | --- |
| `pixel_agents` | Once sprites/props originales, roles recon/architect/design/build/backend/test/diff/entrepreneur/brand/launch/deploy, disposición 4+4+3, número grande detrás y labels de comando | Labels nuevas y estado de activación; coordinación/convergencia a resultado es una variante generativa. Tamaño, tipografía, posiciones y tiempos no se declaran idénticos al original |
| `spotlight_agent` | Canvas negro, foco/pool de luz, sprite auténtico con su prop y énfasis de rol | Objetivo, chispas y salida conectada son parametrizables. Comparar peso visual, escala del personaje, densidad, sombra y ritmo; no confundir render estable con equivalencia estética |
| `agent_marquee` | Avatares originales en desfile horizontal finito, distintas funciones y movimiento interno | Fuente muestra banda de sprites sobre cámara ajena. La biblioteca ofrece composición full-motion sin reutilizar ese rostro, selección de rol y CTA opcional; no afirma reproducir el layout completo del CTA original |

Los recortes de sprites/props se verificaron sobre contacto de fondo contrastante; se corrigieron avatar de repo y máscara del cuerpo blanco del cohete. El fondo se volvió transparente mediante extracción del exterior claro; no se generaron personajes ni se reconstruyeron con IA. Es un único raster original por rol y los aliases no crean copias.

## Cámara y fuentes ajenas

Las tres secuencias `presenter_contract` se inventariaron sin omitirlas, pero su material de cámara no entra como asset del motor. Lo mismo aplica a la mitad inferior de los splits observados. La futura cámara de Presentador se incorpora mediante el contrato YO 55/45, máximo 3 s continuos y texto bajo barbilla. Omitir al presentador extranjero es una decisión de alcance; no demuestra que ese futuro split ya esté implementado o validado.

Las marcas recuperadas son las realmente visibles: Airbnb, Uber, GitHub, AppStore, G2, Reddit, Trustpilot, Slotly y los seis logos aprobados existentes. Las rutas del componente aprobado permanecen intactas; para el motor, Duolingo/Notion/Spotify utilizan recortes nativos mayores de la comparación. El calendario azul del hub se extrajo correctamente de F720, con icono blanco visible, reemplazando el círculo del header móvil que no representaba ese nodo. Google no se identificó en esta referencia y no se inventó. El terminal muestra una mascota como identificador de Claude Code; no se atribuye a CLONE un símbolo corporativo que no aparece ahí. Una demo posterior puede nombrar Claude y representar un proceso conceptual sin fingir interfaz auténtica ejecutada.

## Cómo comparar una pieza

Para reconstrucciones, elegir los mismos estados narrativos: composición inicial, acción principal, reacción, resultado y salida. Cuando las duraciones sean diferentes, registrar la correspondencia de hitos y la diferencia temporal; no presentar dos frames elegidos arbitrariamente como comparación equivalente. Revisar geometría/escala, jerarquía, fuentes aproximadas, color, sombras, props, trayectorias, velocidad y continuidad.

Para variantes nuevas, comparar reglas de sistema y causalidad: un cambio de estado explica una acción y entrega un resultado. No exigir un frame literal inexistente ni reutilizar cifras del original como resultado comprobado. Los resultados/cifras suministrados mantienen su fuente y los ejemplos conceptuales se declaran como tales.

Guardar cada revisión sobre los hashes vigentes de spec, HTML, MP4 y assets. La decodificación de todos los frames acredita lectura técnica; la correlación HTML/MP4 acredita reproducción; ninguna de las dos aprueba por sí sola dirección de arte o fidelidad a CLONE. Registrar separadamente `fidelidad_visual`, `movimiento`, `reutilizacion`, `consistencia` y pendientes. Aún no se afirma aquí aprobación visual de los nuevos renders.
