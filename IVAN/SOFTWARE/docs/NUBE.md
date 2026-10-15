# Almacenamiento privado: base técnica desactivada

El almacenamiento operativo de Ascendia Studio continúa siendo local al servidor,
con `remote:false`. `studio/cloud_storage.py` aporta contratos de almacenamiento
privado para una integración posterior. Durante su desarrollo no se conectó un
bucket, no se utilizaron claves reales y no se subieron proyectos a un servicio.
La colaboración actual utiliza los proyectos del servidor local.

`status()` devuelve por defecto `configured:false`, `enabled:false`,
`live_remote_execution_verified:false`, `automatic_sync:false` y
`restore_applies_project:false`. Leer ese estado no crea una llave ni inicia una
conexión. Aunque un operador configure el adaptador, el estado general conserva
`remote:false`: la configuración por sí sola no acredita una ejecución remota.

## Autoridad y configuración

La configuración pertenece al administrador del servidor. No hay un formulario
ni endpoint para introducir credenciales de almacenamiento. Existe un job explícito
de respaldo por proyecto, accesible al propietario; no hay sincronizador automático
que observe todos los cambios del workspace.
`configure(config, credentials, expected_revision=0, root=None)` es un contrato
Python para el operador; cualquier integración futura debe comprobar su autoridad
antes de llamarlo. Un usuario o colaborador no elige el bucket, el endpoint ni el
workspace de otro propietario.

La configuración y las credenciales se cifran con AES-GCM en
`.estado/cloud_storage/config.enc`. La llave independiente de 32 bytes se genera
únicamente al configurar y se conserva en `.estado/cloud_storage/master.key` con
permisos privados. No se reutilizan credenciales de IA, sesiones, claves de otros
clientes ni la configuración de IVAN. La llave permite descifrar la configuración:
proteger ambos archivos y planificar su recuperación sigue siendo responsabilidad
del operador.

El objeto de configuración es cerrado:

| Proveedor | Campos admitidos | Host derivado |
|---|---|---|
| `aws_s3` | `provider`, `bucket`, `region`, `enabled` | `s3.<region>.amazonaws.com` |
| `cloudflare_r2` | `provider`, `bucket`, `account_id`, `enabled` | `<account_id>.r2.cloudflarestorage.com` |

`enabled` debe ser booleano. El bucket admite un nombre simple de 3–63 caracteres,
sin puntos ni aliases. AWS usa una lista explícita de regiones; R2 exige un
identificador hexadecimal de 32 caracteres y firma con región `auto`. No se admite
una URL de usuario, un proveedor genérico ni endpoints S3 compatibles arbitrarios.
La configuración tiene revisión optimista: una revisión antigua produce conflicto.

## Contratos existentes

`CloudStorage(root=None, transport=None)` usa el transporte HTTPS propio o un
transporte inyectado para pruebas. El llamador autorizado debe obtener el
workspace del contexto del servidor, conservar los controles de sesión/ACL y
aplicar CAS del proyecto; estos métodos no sustituyen al gateway.

| Método | Comportamiento actual |
|---|---|
| `put_blob(workspace_id, path, expected_sha256)` | Lee un medio canónico propio, comprueba sus bytes y escribe una clave inmutable con `If-None-Match:*`. Si existe, descarga y compara los bytes antes de reutilizarla. |
| `get_blob(workspace_id, sha256)` | Comprueba el SHA de todos los bytes recibidos y los guarda únicamente en staging privado. |
| `put_manifest(workspace_id, project_id, document, expected_etag=None)` | Crea el manifiesto con `If-None-Match:*` o actualiza con `If-Match`. Un conflicto exige recargar; no se fuerza la sobrescritura. |
| `enqueue_project(workspace_id, project_id, expected_project_revision, expected_revision=0, expected_etag=None, include_outputs=True, progress=None, cancel=None)` | Captura el proyecto canónico completo dentro del contrato portable y sella su cola. Requiere configuración activa, revisión actual y `include_outputs` booleano. No hace llamadas remotas. |
| `run_outbox(workspace_id, project_id, expected_revision, progress=None, cancel=None)` | Ejecuta explícitamente la cola: blobs y snapshot inmutables → GET íntegro de cada objeto → manifiesto por CAS → GET del manifiesto → recibo privado sellado. |
| `outbox_status(workspace_id, project_id)` | Estado público del propietario, con revisión, SHA del snapshot/recibo, `manifest_etag` e indicadores de integridad/transporte. Sin contenido del snapshot, endpoint ni credenciales. |
| `enqueue_snapshot(workspace_id, project, assets, expected_revision=0)` | Contrato histórico de snapshot parcial, conservado por compatibilidad. No se utiliza para el respaldo completo nuevo. |
| `outbox(workspace_id, project_id)` | Lee el registro privado y verifica su sello, propietario y SHA del snapshot. |
| `stage_restore(workspace_id, snapshot_sha256, progress=None, cancel=None)` | Verifica tabla completa, bytes, variantes tipográficas, avisos y ZIP editable; genera un recibo de staging. Devuelve `applied:false`; no crea ni reemplaza un proyecto. |

Las claves siguen `v1/<workspace>/blobs/<sha256>` y
`v1/<workspace>/projects/<project>/manifest.json`. Los IDs y hashes se validan.
Los blobs tienen un máximo de 64 MiB por archivo; los documentos JSON, 4 MiB.
El snapshot completo admite hasta 256 recursos adjuntos, 512 archivos y 256 MiB
de contenido seleccionado. Si un archivo necesario excede el límite, falla el
respaldo completo: no se omite silenciosamente. No hay multipart ni streaming de
archivos arbitrariamente grandes.

El acuse de un PUT nuevo no demuestra una descarga íntegra posterior:
`full_remote_bytes_verified` indica si se compararon realmente los bytes devueltos.
Un ETag sirve para concurrencia y se mantiene separado del SHA del contenido.
El manifiesto declara `referenced_blobs_verified:false` y
`snapshot_bytes_verified:false`: esta operación de bajo nivel no verifica que sus
referencias ya existan. No debe presentarse como un backup completo. AWS documenta
las [escrituras condicionales](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
y los distintos [checksums y ETags](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html).

El snapshot nuevo, `ascendia.cloud-snapshot/2`, conserva el JSON editable de
configuración, montaje, texto, transcripción, audio y escenas; todos los recursos
adjuntos canónicos; ambas fuentes reales, metadata y avisos de licencia; y el
descriptor de branding que coincide con el binding del servidor. Captura las
evidencias de dirección y tracking explícitamente referenciadas del propio
proyecto, con nombres por contenido. No recorre todo el workspace ni copia modelos,
cachés, llaves, cuentas, sesiones, colaboradores o materiales de IVAN.

La captura se serializa con el StoreLock real del workspace. Comprueba revisión,
catálogo, bytes y fuentes antes de confirmar. Las credenciales anidadas conocidas,
comandos y rutas privadas se eliminan de la representación portable. Se vacían
revisiones/gates/autorizaciones y se mantienen `editorial_approved:false`,
`production_conformant:false` y la obligación de reinspección. Los avisos de
licencia conservan sus bytes y procedencia; incluirlos no crea permisos nuevos.

Con `include_outputs:true`, conserva los últimos 16 renders referenciados que
tengan archivos propios y SHA correctos, y el ZIP editable canónico existente si
está vigente. El ZIP se inspecciona sin importarlo ni ejecutar HTML: miembros
permitidos, CRC, cobertura de medios, fuentes y montaje. Su `project.json` se
reconstruye con revisiones pendientes. Los recibos anteriores son información
histórica, sin aprobación ni derecho a reutilizar sus verificaciones; los que no
incluyen bytes se marcan como archivo documental. Si no existe ZIP generado, el
JSON de escenas/motion permanece editable para regenerar con el motor instalado;
no se inventa un editable HyperFrames que no se haya producido.

Los blobs locales se conservan una sola vez por SHA dentro de la cola privada.
Repetir una captura pendiente idéntica conserva su revisión. El runner serializa
el mismo proyecto, permite reanudar después de una interrupción y valida también
los objetos ya existentes. No confirma el manifiesto hasta verificar todos los
bytes. Una revisión remota distinta produce conflicto; no se fuerza el ETag.
Un fallo o cancelación conserva el outbox pendiente. Los objetos inmutables ya
enviados no se borran como efecto de cancelar.

El recibo confirmado se direcciona por SHA y se vincula al outbox sellado. El
reintento de una operación confirmada vuelve a leer los objetos y el manifiesto;
no repite las escrituras. `integrity_verified:true` con `transport:injected` y
`live_remote_execution_verified:false` significa prueba del contrato con un
transporte simulado. Sólo el transporte HTTPS real puede emitir el indicador de
ejecución remota tras esas lecturas; todavía no se realizó esa prueba.

La restauración deja un árbol íntegro y un recibo privado bajo
`.estado/cloud_storage/restores/`. Comprueba SHA/tamaño, referencia de cada escena
y pista, fuentes reales y ZIP. No escribe catálogo, branding global ni
`projects/<id>/project.json`; aplicar el staging requiere importación canónica del
propietario, validación nueva y CAS. No hereda aprobación, observación visual ni
escucha. El ZIP editable sigue disponible como entrega portable independiente.

## Transporte y aislamiento comprobados

El transporte deriva el host del proveedor, firma con SigV4 y usa TLS con
verificación de certificado y nombre. Resuelve DNS con plazo acotado y exige que
todas las direcciones sean públicas; conecta a una de esas IP usando el nombre
oficial para TLS. Rechaza respuestas DNS mixtas con IP privada, redirecciones,
cookies, cabeceras arbitrarias, claves fuera del prefijo y respuestas demasiado
grandes. No usa proxies del entorno. Cada transferencia tiene plazo de 60 segundos.

Las rutas locales permanecen dentro de SOFTWARE. Se rechazan enlaces simbólicos,
hardlinks y cambios de bytes durante la lectura. La configuración administradora
queda fuera de los workspaces; los medios de un blob deben pertenecer a
`workspaces/<workspace>/assets`. Los archivos privados usan permisos restringidos,
escritura atómica y locks para la revisión local. El staging no sobrescribe un
archivo existente que haya cambiado.

La base inicial conserva sus **89 pruebas históricas**. La ampliación supera
**155 pruebas propias aisladas**, con credenciales sintéticas, transporte de
objetos en memoria y conexiones HTTPS/DNS simuladas. Cubren campos cerrados,
concurrencia CAS, cifrado, aislamiento, enlaces, alteración de fuentes/configuración,
integridad de blobs, snapshot/branding/TTF/OFL reales en fixtures privadas, ZIP CRC,
referencias completas, reanudación, dos runners concurrentes, cambio de
configuración/cancelación durante commit y restauración íntegra en staging.
La integración de cola/API añade pruebas de protocolo con mocks: la pasada
conjunta de tres archivos tuvo 177 casos correctos. No prueban aceptación de SigV4
por AWS/R2, latencia real, disponibilidad de un bucket, aplicación de un proyecto
restaurado ni sincronización real. Un transporte inyectado
no puede declarar ejecución remota real mediante su propia metadata.

## Integración posterior y costes

El propietario consulta `GET /api/projects/<id>/cloud-backup` y solicita
`POST /api/projects/<id>/cloud-backup` con `expected_revision` del proyecto,
`expected_outbox_revision`, `expected_etag` opcional e `include_outputs` booleano.
La primera copia usa ETag ausente; una nueva copia emplea el `manifest_etag`
confirmado y la revisión del outbox. Las herramientas MCP son `cloud_backup_get`
y `cloud_backup_start`. El worker deriva el propietario de su workspace fijo;
viewer/editor compartidos no administran el respaldo. Sin configuración activa,
la solicitud se rechaza y no se simula un job completado.

La cancelación utiliza los controles existentes de jobs propios. No hay
configuración de credenciales por HTTP/MCP. Faltan una prueba con proveedor real,
la aplicación segura de una restauración, multipart, historial/retención y
contabilidad de cuotas/costes. El módulo no se conecta por el mero arranque ni por
consultar su estado.

La primera integración debe conservar un único servidor como autoridad de
proyectos, permisos y jobs. Un bucket no proporciona locks del editor ni convierte
esta aplicación en un sistema distribuido. Los archivos deben servirse por el
gateway autorizado para mantener el control de revocación; no se implementaron
URLs firmadas entregadas al cliente.

En AWS, restringir los permisos a los prefijos y mantener el bloqueo de acceso
público del bucket. Son decisiones de operación pendientes, documentadas en las
[condiciones IAM por prefijo](https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html)
y el [bloqueo público](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html).
R2 no implementa todas las operaciones S3, incluido el versionado de buckets en la
[tabla oficial de compatibilidad](https://developers.cloudflare.com/r2/api/s3/api/);
un historial futuro de la aplicación debe tener su propio contrato.

Calcular almacenamiento, historial, operaciones y transferencia por workspace,
separando el alojamiento del servidor. Las franquicias gratuitas del proveedor
son compartidas por su cuenta, no una asignación automática para cada usuario.
Consultar los precios vigentes de [AWS S3](https://aws.amazon.com/s3/pricing/)
y [Cloudflare R2](https://developers.cloudflare.com/r2/pricing/) antes de definir
cuotas o tarifas. No hay facturación, bucket contratado ni coste remoto medido.
