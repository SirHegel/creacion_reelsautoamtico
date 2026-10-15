# Adaptación multiservicio y multiusuario

Observación: 2026-10-13T20:41:48.862878+00:00. Este informe revisa IVAN por lectura y propone la adaptación del editor. No ejecuta el workflow padre, no importa sus módulos ni comparte sus credenciales. La investigación no aprueba una edición, no acredita escucha y no certifica fidelidad a CLONE. El detalle con huellas está en `SOFTWARE/.estado/validacion/multiservice_parent_audit.json`.

## Base editorial común y configuración por cuenta

La última preferencia del usuario para el producto es que **todas las cuentas utilicen el estilo IVAN**, con branding configurable. Esa preferencia se registra separadamente del manual de producción. La base común combina identidad YO y motion CLONE; cada cuenta conserva sus originales, recursos, proyectos, revisiones y conexión de IA.

| Capa | Configuración replicable | Qué debe permanecer independiente |
| --- | --- | --- |
| Identidad YO | Hook como frase/composición integrada, cámara original, split55/45, rostro máximo3s continuos incluso durante split/transiciones, texto centrado bajo barbilla | Rostro/crudo propio, geometría y tracking verificados; no reutilizar el presentador de las referencias |
| Tipografía | Referencias originales Sequel/Scholar, blanco/carbón, rojo semántico, sombra compacta; jerarquía medida | Branding explícito con familia/variante/SHA reales; ningún fallback silencioso ni redistribución supuesta de fuentes privadas |
| Motion CLONE | Estados conectados de entrada, acción, reacción, transformación y salida; tiempos/curvas deterministas | Referencia/variantes verificadas y recursos originales propios; una marca o interfaz conceptual no demuestra una función ejecutada |
| Branding | Nombre, logo autorizado, acentos y CTA aportada; overlay sobre el mismo lenguaje editorial | Los colores oficiales de terceros, datos, precios y afirmaciones no se inventan por branding |
| Recursos | Catálogos con fuente, hash, tramo, significado y uso real en render | Biblioteca privada de cada cuenta; un alias/hash no concede acceso ni derechos |
| Revisión | Evidencias vinculadas a crudo/manual/código/diseño/recursos actuales; prueba antes de promover completo | No transferir aprobación de IVAN a otro usuario ni cambiar recibos históricos |
| IA | Proveedor, modelo y límites por cuenta, con inferencia y errores reales | Credencial/costo/consentimiento propios; un token guardado no equivale a conexión comprobada |

El paquete inicial de las cuentas usa seis caras OFL públicas: Source Sans3, Anton, DM Serif Display e IBM Plex Mono, con nombres y avisos reales. Sequel/Scholar privados no se redistribuyen; el override de branding se declara y vincula mediante un snapshot del servidor. Esto conserva el lenguaje editorial común y no certifica identidad tipográfica exacta con la referencia.

Los ajustes de branding deben versionarse y entrar en el digest editorial. Un cambio de perfil, fuente, logo, manual o motor invalida promociones nuevas si afecta al candidato. La configuración no debe contener `approved:true`, rutas arbitrarias, HTML/JS ni claves secretas.

## Precedencia y alcance padre observados

Se leyeron completos AGENTS44 líneas, PROMPT1037, INSTRUCCIONES151, STYLE49 y las reglas de SOFTWARE. Huellas actuales:

| Documento | SHA256 |
| --- | --- |
| AGENTS | `8ef00cd18f9ca503b0d6e3c1d097798445d1031d6f52662901f494c81a1fda1a` |
| PROMPT | `004ee0a58b48a498e8afa03362cbcda0efec00c989cdc918f21d393f3c56df9b` |
| INSTRUCCIONES | `f29b4c02d5d2ae7d49d6348eb0f9f2291a5fd77fa32646844e0e1b9f2b460dc2` |
| STYLE | `2175af58e3625978cbe818a03a79b222e16e98484f143f82ef1d453443e65d39` |

La regla26 autoriza la **primera muestra de integración real CLONE+YO del padre**. Conserva duración/audio/narración del crudo autorizado y exige planner real con decisiones preservadas. El nombre `ascendia_integracion_test_10s.mp4` no autoriza extender un crudo más corto. Esa autorización, su ID de Drive y su destino pertenecen a ese encargo; el editor no los ejecuta ni los asigna a todas las cuentas.

B_V2 es historia autorizada para comparación B_V1/B_V2. Su cierre6.9–9s, cifras, secuencia de familias, prohibición temporal de integrar YO y obligación de conservar sus archivos no son reglas universales del producto. Los pasos estáticos1.6–3.2 y las búsquedas/cuotas de b-roll que todavía aparecen en secciones antiguas de INSTRUCCIONES ceden frente al append vigente. No reinstalar ni repetir la arquitectura GSAP ya comprobada.

`ESTADO.json` todavía declara `B_V2_revisado_pendiente_usuario` y una siguiente acción sinYO; su SHA es `830c8249adc7266bebdf6f71c33e5acad327e3b59f81237ef8a50f3f17e0ec82`. Es un registro desactualizado respecto a la regla26, no permiso para imponer ese bloqueo a usuarios nuevos.

Sí existen `integracion/scene.json`, recibo del planner, alineación, storyboard automático y diagnóstico de crop/anclas. El plan declara7.9s y una escena `composition_graph`; manual r26 y respuesta del proveedor están registrados en sus recibos. El informe de crop declara revisión pendiente de render; el handoff sigue siendo metadata y no solicita operaciones de continuidad. La existencia del recibo declara inferencia previa; esta auditoría no la repite ni comprueba una nueva ejecución. `INTEGRACION_YO.md` aún describe un adaptador futuro, y no se observó un módulo integrado ejecutable en la inspección de nombres/referencias. No afirmar integración renderizada o audio preservado por un adaptador aún no verificado.

## Motor y datos que conviene traducir al software

`planner.py`3.4 ofrece15 familias especializadas más `composition_graph`. Los parámetros, presentación, composición, framing y continuidad tienen contratos; el catálogo de capacidades procede de los builders. La selección usa significado, entidades, hechos, relaciones y alternativas justificadas. No existe una familia preferida universal ni cuota obligatoria de variedad.

En las familias especializadas, `actions` describe ventanas de su timeline y `actions_execute:false`; no son comandos nuevos del LLM. En `composition_graph`, `params.steps` sí determina acciones. Handoff es metadata: un puerto/asset compartido compatible habilita una propuesta de continuidad, pero la ejecución se acredita con recibo/browser/render vigente. Preservar esta distinción al importar el plan.

El compositor publica perfiles concretos: compact_stack para feedback, centered_actor para spotlight y centered_primary para phone_rebuild/terminal. Los rangos de gap, anclas, márgenes y cuerpos pertenecen a esos perfiles, no a toda edición. El cierre coverage_conclusion sólo tiene sentido al comparar cobertura sin evaluar calidad ni declarar ganador. No copiar cifras de la referencia ni el cierre fijo de B.

`design-system.json` distingue color muestreado, aproximación y diseño aprobado; declara que las fuentes originales CLONE no se han identificado. Trabaja en720×1280 y escala el lienzo a1080×1920; YO tiene un contrato tipográfico distinto. AGAIN es un contorno de una palabra fija, no una fuente general.

`assets.json` contiene37 IDs,28 rutas únicas y aliases. Todos esos registros declaran origen B2_CLONE y ninguno aporta un campo explícito de licencia. La extracción/crop/hash documenta procedencia, no una licencia para redistribuir sprites, logos o retratos. Reutilizar principios y contratos; no copiar recursos privados a cada cuenta ni afirmar que todo el motor/fuentes/referencias es MIT.

## B-roll y herramientas generales

La exclusión de stock, b-roll y video externo de la infraestructura CLONE y de la muestra r26 pertenece a esos encargos del padre. No es una prohibición universal para las cuentas del SaaS. La instrucción posterior del usuario permite b-roll auténtico y recursos contextuales propios para todos los usuarios, con branding y selección configurables; prevalece sobre el alcance temporal del padre. No imponer las antiguas cuotas35–45% ni sustituir automáticamente el crudo por recortes/chroma/segmentación.

El software permite seleccionar b-roll auténtico propio con observación contextual, procedencia, tramo y permisos declarados pendientes de comprobar. Un nombre, logo o clip decorativo no acredita pertinencia. Las muestras aisladas acreditan puntos vistos; una secuencia requiere declarar su visionado y el intervalo cubierto. El planner debe explicar la relación con la frase y el render debe acreditar su uso real. Mantener la cámara original, sin duplicar al presentador para rellenar ni añadir blur. El catálogo distingue capacidad técnica, política del proyecto y evidencia de observación; ningún cambio de brief o recurso aprueba silenciosamente otro proyecto o cuenta.

Comprobación posterior del perfil propio: `profiles/ivan_base.json`, SHA `67d26dc465be5aca0c7fcb3bdf6f91166f48ad3d6b64e968e8a6cd4c8ad06f08`, conserva una cláusula de recursos autorizados con observación, frase, tramos y evidencia. Su frase «Motion primero en la integración actual CLONE+YO; no stock ni relleno estático» describe la integración actual; debe leerse con la autorización posterior del usuario, sin prohibir el b-roll contextual propio del SaaS. Esta observación no reescribe las restricciones ni las auditorías históricas del padre.

## Aislamiento de cuentas y workspaces

En la base anterior, `core.ROOT` y sus aliases gobiernan catálogos, proyectos, jobs, previews, pruebas y exportados. Cambiar ese global por petición sería inseguro con ThreadingHTTPServer. El código nuevo usa `runtime.py` y un backend separado por workspace, con root inmutable; `gateway.py` verifica la cuenta antes de elegirlo. La inspección de este código y los tests de protocolo no sustituyen una prueba real del arranque/render de todos los backends.

El gateway debe verificar identidad y propiedad para cada recurso/operación, incluso GET/HEAD/Range, fonts/notices, ZIP, audio, evidencias, jobs y cancelaciones. Una URL o ID opaco selecciona el recurso, pero no concede permiso. Ese criterio sigue la [guía multiusuario de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html).

El código crea datos y conexiones privadas bajo `SOFTWARE/workspaces/<id>` y su `.estado`. Sólo modelos/runtime y fuentes públicas con licencia conocida pueden compartirse por lectura controlada. Deduplicar un mismo archivo dentro de un workspace no revela si otro usuario lo posee. Los originales y proyectos anteriores del editor no se asignan automáticamente a una cuenta nueva.

Los backends separados deben conservar **un lock CPU común en SOFTWARE**, antes del StoreLock privado; locks distintos por workspace permitirían paralelismo accidental. CLI/MCP/jobs también necesitan un principal y un workspace resueltos por servidor. El manual/skills y las dependencias se resuelven contra un root fuente estable; usar `ROOT.parent` de un workspace anidado apuntaría al lugar equivocado.

En el navegador, rutas de API/medios deben contener el workspace de la pestaña. No usar cookie global de workspace activo: dos pestañas competirían. Invalidar respuestas atrasadas con epoch+AbortController y retirar previews, audio, FontFace, blobURLs, layouts, jobs/polls y selección al salir/cambiar cuenta. Separar historial local por usuario/workspace; no guardar bearer/API keys en localStorage. La sesión requiere expiración/revocación, cookies protegidas y CSRF para mutaciones, conforme a [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

Es aislamiento de la aplicación local. Dos procesos del mismo usuario del sistema operativo no constituyen un sandbox hostil entre sí; este informe no certifica un SaaS público ni despliega un servidor remoto.

## Conexiones IA: cuenta, API y clientes de agentes

| Camino | Contrato actual | Estado del editor durante esta investigación |
| --- | --- | --- |
| API key propia | Clave y modelo del usuario; proveedor fijo; consumo/costo de su cuenta | Adaptadores BYOK en construcción, sin inferencia externa ejecutada por esta auditoría |
| Codex/Claude como cliente MCP | Cliente autentica al usuario del editor con token revocable del workspace; herramientas acotadas | Independiente de cómo ese cliente paga su modelo; no transferir auth global del padre |
| ChatGPT plan en app open-source | Flujo oficial de registro/OAuth/PKCE y permiso de inferencia separado de identidad | No habilitado por guardar una suscripción; integración oficial pendiente |
| Claude Code nativo | Binario original y autenticación propia en el flujo de Anthropic | Adaptador futuro distinto de proxy de credenciales de Claude.ai |

OpenAI documenta acceso al plan de ChatGPT para apps open-source/locales elegibles mediante su flujo oficial. Identidad no concede inferencia, conversaciones ni API keys; se necesita el consentimiento de scopes correspondiente. No conviene afirmar que una suscripción nunca tiene un canal permitido, ni que ese canal ya funciona en nuestro editor. [Quickstart oficial](https://developers.openai.com/siwc/quickstart).

Codex admite login ChatGPT y API key; la facturación y permisos difieren. No leer/copiar su auth global para simular conexiones independientes. Un token MCP del editor autoriza herramientas del editor y no compra inferencia. [Autenticación de Codex](https://learn.chatgpt.com/docs/auth).

Anthropic diferencia app propia por API de Claude Code original: no recolectar ni intermediar tokens/cookies de Claude.ai. El usuario puede iniciar sesión por el flujo nativo del binario sin modificarlo cuando se cumpla su contrato; no presentar ese caso como un proxy OAuth propio. [Contrato oficial de Claude Code](https://code.claude.com/docs/en/legal-and-compliance). Algunos planes elegibles permiten reclamar créditos API en Console: sigue siendo acceso API propio, no una sesión web reutilizada. [Créditos API oficiales](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers).

Propuesta de seguridad: claves cifradas por workspace, permisos privados, vistas públicas sin plaintext, ningún secreto en proyectos/ZIP/URLs/logs, borrado/revocación explícitos y reautorización al usar la conexión. Clave cifrada y llave local protegen almacenamiento accidental; no separan a un administrador que accede al mismo sistema. Véase [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

Para BYOK, endpoints HTTPS del catálogo fijo, sin `base_url` arbitraria, sin proxy heredado y sin redirecciones que transporten credenciales. Si en el futuro se admite un host personalizado, validar DNS/IP/puerto y bloquear loopback, privadas, link-local y metadata; limitar tiempo y tamaño. [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html). JSON del modelo sigue siendo contenido validado: no elegir credenciales, workspace, shell, instalaciones ni HTML ejecutable a partir de instrucciones del guion.

Mostrar `configured`, `tested`, `available` y `unsupported/pending` separadamente. Un modelo/cuenta no comprobados no deben marcarse como inference_executed. Errores de saldo, alcance, expiración y salida truncada son bloqueos concretos; no cambiar silenciosamente a otro proveedor o cuenta.

## Auditoría de código y pruebas propuestas

Cierre de la inspección: 2026-10-13T21:06:23.050114+00:00. Los owners corrigieron los hallazgos de symlinks antes de mkdir, respuesta upstream malformada, handler MCP, lockCPU, logs, fuga de PIDs, CSRF Unicode y reescritura de textos/SceneIR/provenance que parecían URLs. Los guards se verificaron por lectura y las regresiones correspondientes por pruebas independientes; no se ejecutó inferencia, render ni un subprocess real de workspace.

El perfil público canónico es `profiles/ivan_base.json`; su lectura/acknowledgement tiene SHA propio y no acredita lectura de los cuatro documentos privados del padre. Los proyectos nuevos y refresh en workspace usan fase `ivan_multiservice`, integración `YO_plus_CLONE_own_branding` y alcance independiente. La política B_V2 global se conserva como historia legacy, sin migrar ni reescribir sus aprobaciones.

Cobertura prioritaria y límites:

1. Dos cuentas, mismos IDs/hash de fixture: GET/HEAD/Range/ZIP/jobs/cancel/tareas/font/layout nunca cruzan propiedad; root no cambia durante peticiones concurrentes.
2. Dos pestañas y respuestas atrasadas: upload/attach/layout/polls no se aplican tras logout/cambio; medios antiguos no siguen reproduciéndose; localStorage/caches separados.
3. Symlinks de .estado/workspace/preview/notice y traversal: rechazar antes de escribir, chmod, abrir DB o servir bytes. Originales y cuatro proyectos protegidos conservan sus SHA.
4. Cookies/sesiones/token revocado, CSRF faltante, bearer ajeno y renovación de sesión: negar según método y ACL, sin filtrar existencia de recursos privados.
5. Secretos en GET/status/error/ZIP/logs y URLs: sólo hints permitidos; cifrado/llave privados; conexión pertenece al workspace autenticado.
6. Provider redirect/proxy/host personalizado, respuesta grande/lenta, JSON null/list/campos malformados/truncados: error acotado, sin stacktraces ni ejecución ficticia.
7. CPU entre workspaces, cancelación propia y revision/manual/branding/asset mutable: cola serial común, conflicto sin sobrescritura ni aprobación automática.
8. Planner con prompt injection/facts sin evidencia y parámetros mal tipados: esquema cerrado, semántica declarada y lineage original; no shell/red/código arbitrario.

Se ejecutaron **41 pruebas independientes:41 PASS,0 FAIL,1.15s**, con HTTP real local y cuentas/SQLite/AESGCM reales en fixtures privados. Los backends de transporte y las respuestas malformadas de proveedores se simularon; el status MCP usa dispatcher real pero un descriptor de branding/capability de fixture. No prueban media decodificada, inferencia externa, OAuth, arranque/render real de workers, experiencia de navegador ni aprobación editorial. Root informa adicionalmente14 pruebas de branding y36 de cuentas/proveedores con BYOK simulado; esta auditoría no las repitió.

Se rehashearon por lectura el original padre (`ffe94d66…`) y los cuatro proyectos protegidos v04: todos conservan sus SHA. No se tocó la terminal padre ni sus proyectos. El gateway tiene un límite local de12 workers activos; la autenticación del portal no protege automáticamente otros servicios localhost o el editor legacy de operador. La validación real de plataforma debe enlazarse a evidencias nuevas, sin reutilizar las de tipografía como prueba multiusuario.
