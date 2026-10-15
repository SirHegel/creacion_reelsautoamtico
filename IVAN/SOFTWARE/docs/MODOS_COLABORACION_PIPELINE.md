# Modos de edición, colaboración y flujo del crudo completo

Ascendia conserva un proyecto editable y recursos privados por espacio de usuario. El modo Automático prepara el crudo completo y obtiene planes por API propia o por un agente conectado mediante MCP. El modo Manual permite construir y exportar la cronología directamente. Ambos producen borradores técnicos pendientes de revisión; un trabajo completado no acredita fidelidad a CLONE, escucha ni autorización para publicar.

Este procedimiento describe los contratos de `studio/pipeline.py`, `jobs.py`, `mcp.py`, `sharing.py` y `gateway.py`. El [workflow declarativo](../workflows/reel_multiservice.json) conserva el orden operativo; escribirlo no inicia trabajos, despliega modelos ni demuestra que se ejecutaron sus etapas. Los recibos y el estado actual se consultan en el servidor del espacio. Las pruebas y entregas anteriores conservan su alcance histórico.

## Cuenta, almacenamiento y proyecto

1. Entrar en el portal con una cuenta propia. El registro crea un espacio privado; un correo registrado todavía no acredita una identidad verificada.
2. Configurar nombre, colores, fuentes reales, logo e instrucciones de marca. Los proyectos usan un snapshot del servidor. Cambiar la marca general no altera un proyecto existente: aplicar la marca a ese proyecto exige su revisión vigente y la revisión de marca.
3. Importar el crudo y conservar su SHA, duración y pistas reales. La deduplicación ocurre dentro del espacio; no hereda recursos, credenciales ni aprobaciones de IVAN u otras cuentas. Abrir el proyecto existente del crudo evita montajes duplicados.
4. Leer el perfil editorial completo del software. YO orienta cámara, subtítulos y split; CLONE orienta motion. Las fuentes OFL iniciales y el branding propio quedan declarados. No se redistribuyen Sequel/Scholar privadas ni materiales de las referencias. Encargos temporales del padre, como B_V2 o su hook de 3,6 s, no limitan todos los proyectos de los usuarios.

El almacenamiento actual es del servidor local: `provider:local`, `remote:false`. Archivos, proyectos y evidencias permanecen dentro de SOFTWARE. El administrador puede configurar respaldo S3/R2 mediante el contrato de [Nube](NUBE.md); este respaldo captura un snapshot completo, verifica sus archivos y actualiza el manifiesto mediante CAS. Esta instalación no tiene conexión de nube, sincronización periódica, integración Drive ni publicación remota. La restauración produce staging separado y no aplica proyectos o aprobaciones. Las cuentas compartidas no convierten el prototipo local en un SaaS público desplegado. TLS, verificación de correos, recuperación de cuentas, cuotas, facturación y registros OAuth propios requieren trabajo adicional.

Las peticiones de navegador usan `/w/ID_ESPACIO/api/...`, cookie HttpOnly y `X-Workspace-ID` del actor. Las mutaciones requieren `X-CSRF-Token`. Un recurso compartido conserva el propietario en su URL y lleva el proyecto y el espacio del actor en la consulta. No copiar un token, una API key o una cookie dentro de una URL, proyecto, ZIP o instrucciones del agente.

## Voz, fuentes y recursos antes de dirigir

En Configuración elegir `settings.voice_audio_stream` usando el índice GLOBAL real de FFprobe, no el ordinal de una lista de pistas. `null` usa la selección predeterminada del motor. El análisis de actividad de hasta 30 s mediante `audio_tracks` sugiere candidatos; un tono activo no demuestra voz ni identidad del narrador. En un crudo multipista, la vista Original del navegador puede reproducir su pista predeterminada; la selección explícita se aplica a transcripción y render. Comprobarla escuchando el resultado.

Elegir y adjuntar las caras TTF/OTF reales, con sus hashes y avisos. El editor no sustituye silenciosamente una fuente ausente ni sintetiza bold/italic. El texto conserva grafemas y reloj al recortar/dividir; glifos disponibles, desbordamiento, sombra y legibilidad se revisan sobre el archivo exportado. Véase [Tipografía](TIPOGRAFIA.md).

Los b-rolls y demostraciones deben proceder de la biblioteca propia y representar la frase concreta. Preparar muestras con `resource_review_prepare`, observarlas y registrar contenido, tramo, revisor y evidencias mediante `resource_review_record`. Un registro `observed_samples` acredita puntos vistos; no acredita todo un video. La dirección automática de un tramo móvil exige una observación vigente `scope:sequence`, `coverage:continuous_declared` y un intervalo que cubra el tramo seleccionado. Una declaración de derechos del usuario no es una certificación jurídica. El número de recursos no impone una cuota de b-roll; evitar relleno y duplicados del presentador.

El registro de marcas usa `brand_assets_origins`, `brand_assets_fetch`, `brand_assets_catalog`, `brand_assets_register` y `brand_assets_resolve`. La descarga desde un origen fijado comprueba los bytes y queda pendiente de observación. Una URL declarada sin descarga verificada sigue siendo declarada. Registrar requiere los hashes actuales de fuente, observación y registro, además de contenido observado. `private_review` y `publication` son contextos separados; una declaración documentada de publicación no concede aprobación editorial ni autoridad legal. PNG/WebP pueden convertirse en medios del editor; SVG pasivo se registra únicamente como metadata, sin render SVG implícito. No inventar ni sustituir un logo ausente por un dibujo o texto como si fuera auténtico.

## Automático con API propia

El propietario configura una conexión en su cuenta. La API key del proveedor y la credencial MCP del editor son canales distintos. El modelo de la conexión debe ser real y estar disponible; un adaptador con pruebas de transporte simulado no acredita una llamada externa completada. Configurar la suscripción de un cliente no transfiere automáticamente crédito API al servidor.

Iniciar desde el portal o enviar al proyecto propio:

```http
POST /w/ID_ESPACIO/api/projects/ID_PROYECTO/pipeline
Content-Type: application/json
```

```json
{
  "mode": "full",
  "channel": "api",
  "provider": "openai",
  "confirmed": true,
  "instructions": "Explica la idea del crudo con mis recursos y mi marca.",
  "asr_model": "small",
  "language": "es",
  "max_tokens": 8192,
  "max_repairs": 0
}
```

`provider` debe coincidir con una conexión propia configurada. `confirmed:true` confirma el envío de narración, instrucciones y contexto al proveedor y su posible coste; no aprueba el video. El servidor devuelve un job en cola, no un MP4 inmediato. Consultar `job_get` o `/api/jobs/ID_JOB` hasta que la preparación avance.

El pipeline admite una fuente real de 0,1 a 600 s. Alinea la pista elegida con ASR CPU, mide rostro/cámara con runtime local y prepara tramos de hasta 10 s con el contexto de toda la narración. Para cada tramo solicita un plan cerrado `ivan-plan/1`, valida su contenido, compila una cronología editable, aplica QC determinista y confirma el proyecto mediante CAS. Los callbacks propios generan el render HyperFrames técnico completo y el ZIP editable, revalidando los recibos. La ejecución depende de los modelos/runtime locales requeridos y de la disponibilidad efectiva del proveedor.

Opciones cerradas: `mode`, `channel`, `provider`, `confirmed`, `instructions`, `asr_model`, `language`, `max_tokens` y `max_repairs`. `asr_model` admite `tiny`, `base` o `small`; el peso debe estar disponible localmente. `language` es un código de dos o tres letras minúsculas. `instructions` admite hasta 12.000 caracteres; `max_tokens` es entero de 1.024 a 8.192; `max_repairs` es entero de 0 a 2. El backend usa 2 reparaciones por defecto; el portal permite elegirlas y presenta el coste antes de iniciar. El límite de llamadas del flujo es `ceil(duración/10)+max_repairs`; también pueden consumir crédito intentos enviados que fallen. No se cobra dirección si la pista elegida no produjo palabras ASR utilizables. ASR puede equivocar nombres o expresiones: corregirlos exige volver a revisar los planes y sus tiempos.

## Automático con Codex, Claude u otro cliente MCP

El propietario crea una credencial revocable de agente en su cuenta y configura su cliente nativo contra `/mcp`, usando `Authorization: Bearer ...` en la cabecera. El transporte es HTTP JSON-RPC por POST, sin SSE. El cliente dirige la edición; el servidor recibe datos acotados y no ejecuta shell ni HTML/JS suministrados por el agente. La suscripción, modelo y acceso del cliente pertenecen a ese cliente; Ascendia no hereda el acceso de la terminal de IVAN.

1. `pipeline_start` recibe `project_id` y `options` con `mode:full`, `channel:external`, instrucciones y opciones locales de ASR. Este canal rechaza `provider` y `confirmed`: no llama a una API propia del servidor.
2. Consultar `job_get` y luego `pipeline_get` con `include_context:true`. Leer todos los contextos, narración, recursos y restricciones; el estado `waiting_external` significa que faltan planes.
3. Diseñar un documento `ivan-plan/1` específico para cada `chunk_id`. No fabricar hechos, resultados, palabras pronunciadas, pertinencia visual, derechos ni uso de recursos. Los tiempos del plan de un tramo son locales a ese tramo; el pipeline compone sus tiempos globales.
4. Entregarlo mediante `pipeline_plan` con `project_id`, `generation`, `chunk_id`, `expected_revision`, `document` y `agent:{name,model,notes}`. Tomar generación y revisión del estado actual. El nombre/modelo es una declaración del cliente: `verified_external_inference:false` permanece explícito.
5. Consultar el estado después de entregar cada plan. Usar `pipeline_resume` con `project_id` y `generation` cuando estén listos. Si aparece `waiting_external_repair`, leer las incidencias de QC y entregar una corrección del tramo antes de volver a reanudar.
6. Verificar jobs, recibo de render y editable actual. `completed` significa producción técnica terminada con `editorial_approved:false` y `audio_listened:false`; revisar el resultado en movimiento y escucharlo.

Los endpoints propios equivalentes son `GET .../pipeline?include_context=true` y `POST .../pipeline-plan`, `.../pipeline-resume`, `.../pipeline-restart` y `.../pipeline-cancel`. El cuerpo de resume/cancel es `{"generation":1}`, sustituyendo 1 por la generación vigente. `pipeline_cancel` y `job_cancel` solicitan una salida en un punto seguro; conservan originales y evidencias registradas. No cancelan el trabajo externo de otra terminal.

`ivan_prepare` → `ivan_apply_plan` y `ivan_automate` siguen disponibles para pruebas de hasta diez segundos; no confundir ese flujo anterior con `pipeline_start` del crudo completo. `workflow_create` y las tareas director/recursos/motion/audio/QA ayudan a repartir trabajo con leases y evidencias. No despliegan un modelo automáticamente ni conceden acceso al espacio de otra persona.

## Reanudar y corregir sin duplicar

El estado y sus artefactos privados son canónicos por proyecto. El flujo conserva etapas `asr`, `tracking`, `context`, `direction`, `compile`, `qc`, `commit`, `render` y `export`, con hashes y firmas de entrada. Reutilizar una etapa exige que su evidencia y entrada continúen vigentes; no basta con que exista el archivo. No crear otra carpeta de versiones para reintentar.

La revisión del proyecto, fuente, branding, pista de voz, biblioteca, registro de marcas, perfil, modelo o código puede invalidar la entrada. Un 409 exige recargar y revisar, no forzar el guardado ni regenerar un recibo a mano. Un pipeline cancelado/fallido conserva su causa; `waiting_commit`, `waiting_render` o `waiting_export` indican una integración incompleta que debe resolverse. Un plan ya aplicado no puede reemplazarse silenciosamente.

Para un pipeline cancelado o con voz, perfil, modelo, marca u otra entrada cambiada, usar `pipeline_restart` con `project_id`, `generation` vigente y `options` completas. Por HTTP, `POST .../pipeline-restart` recibe exactamente `generation` y `options`. La generación se comprueba al encolar y al ejecutar; una obsoleta produce 409. El reinicio conserva historia, crea la generación siguiente y reutiliza ASR/tracking únicamente si sus firmas y evidencias siguen vigentes. No borra automáticamente derivados ni retira una cancelación de la misma generación silenciosamente. No editar `.estado` para reiniciar.

Ejemplo de reinicio externo, usando la generación obtenida de `pipeline_get`:

```json
{
  "generation": 1,
  "options": {
    "mode": "full",
    "channel": "external",
    "asr_model": "small",
    "language": "es",
    "instructions": "Conserva la nueva selección de voz y mi marca actual.",
    "max_repairs": 0
  }
}
```

Reiniciar por el canal API vuelve a exigir proveedor propio y `confirmed:true`, con el coste potencial de su nueva dirección. Consultar después el job y la nueva generación antes de entregar planes.

## Manual y exportación técnica completa

Manual abre un proyecto propio o compartido y deja al editor construir escenas, textos, fuentes, máscaras, trayectorias, cortes, split, música y SFX con los controles disponibles. Guardar usa la revisión optimista del proyecto. Elegir un motor requiere guardar ese mismo motor en `settings.engine` antes del render. Cambiar montaje o configuración invalida revisiones activas.

Un borrador completo de hasta 600 s en un workspace necesita crudo y cronología que cubran el intervalo. La interfaz de render usa `technical:true`, `draft_full:true`, `seconds` y el motor guardado. Por MCP, `draft_render` recibe `project_id`, `seconds` y opcionalmente `engine`. El modo resultante es `manual_full_technical_draft`; no necesita inferencia para exportar y no hereda una aprobación narrativa. La CLI histórica `render --technical` continúa siendo la prueba corta; no atribuirle una opción de borrador completo que no expone.

La voz se toma de la pista seleccionada del original; revisar su relación con los cortes y entradas de medios elegidos. La música, ducking y SFX adicionales necesitan una elección y sincronización contextual; no se inventa una escucha o mezcla editorial terminada a partir de niveles. No promover un derivado de segmentación/chroma como crudo auténtico del estilo de cámara.

## Compartir sin entregar la biblioteca completa

| Acción | Propietario | Editor compartido | Viewer compartido |
|---|---|---|---|
| Leer proyecto y medios adjuntos | Sí | Sí | Sí |
| Exportar editable y descargar adjuntos | Sí | Sí | Sí |
| Guardar cronología con CAS | Sí | Sí | No |
| Encolar render técnico | Sí | Sí | No |
| Cambiar crudo, biblioteca o marca general | Sí | No | No |
| Automatizar, gestionar API keys/tokens y registro de marcas | Sí | No | No |
| Compartir/revocar y cancelar jobs compartidos | Sí | No | No |
| Aprobar editorialmente mediante acceso compartido | No automático | No | No |

Invitar usa una cuenta local existente por correo y un rol `viewer` o `editor`. Confirmar la persona por otro canal mientras la verificación de correos esté pendiente. Viewer incluye descarga y exportación; no es únicamente una vista sin copia. Compartir el proyecto no comparte todo el catálogo, conexiones, tokens, otros proyectos ni automatización del propietario. Los tokens de agentes conservan su espacio propio y no convierten una colaboración de navegador en identidad del dueño.

Crear/cambiar un permiso exige `expected_revision` entero: 0 para uno nuevo, revisión de su fila para modificarlo. Revocar también exige la revisión vigente. Un conflicto recarga la lista antes de confirmar de nuevo. Revocación, cierre de sesión o expiración mientras se recibe un cuerpo bloquean la posterior edición. Una operación ya admitida se serializa con la revocación hasta terminar; otros proyectos pueden continuar. Nuevas peticiones y rangos dejan de acceder después de revocar. No se pueden recuperar los bytes descargados previamente ni deshacer por revocación una exportación ya admitida.

## QC y entrega

QC comprueba datos, geometría de texto, tiempos de pose y posibles oclusiones. Las métricas de permanencia a 10 Hz no demuestran lectura humana, precisión semántica, continuidad percibida o semejanza con CLONE. Los recibos de render acreditan ejecución técnica y decodificación dentro de su alcance, no aprobación artística.

Antes de entregar o publicar: reproducir todas las escenas y transiciones, revisar cara/barbilla, zonas seguras, texto y nombres, fuentes, logos y pertinencia de recursos; escuchar voz, música y efectos; comprobar sincronización, ritmo y continuidad. Separar diseño visual, movimiento, ritmo y continuidad en las observaciones. Conservar errores y pendientes cuando el resultado necesite otra pasada. Comprobar CRC, hashes, fuentes/avisos y medios del editable; un ZIP reabierto conserva revisiones y permisos pendientes, no una aprobación heredada.

El software no publica en Drive ni concede permisos comerciales de marcas por haberlas descargado. La autorización para producir un borrador completo en el workspace y el consentimiento de consumo API no autorizan su publicación. Mantener el render técnico, las observaciones y el editable vinculados a los bytes actuales.
