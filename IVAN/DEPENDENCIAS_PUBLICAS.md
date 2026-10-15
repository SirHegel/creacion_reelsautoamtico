# Dependencias y recursos propios

La publicación incluye motores, contratos, pruebas y plantillas. El directorio `.estado/` guarda configuración privada, entornos, cachés y herramientas locales y se excluye de Git. Los campos `CONFIGURE_RECURSO_*` son valores de ejemplo sin acceso a ninguna cuenta. Configure sus propias referencias en `sistema/perfil.json` y en los scripts que las requieren antes de cualquier operación remota.

## Herramientas

Las dependencias JavaScript están enumeradas con versión en `sistema/node_package.json`; se instalan en `.estado/herramientas/`. Las de Python están en `sistema/requirements.txt`, con el destino aislado `.estado/python/`. FFmpeg, ffprobe, rclone, Chrome y las herramientas de GPU se obtienen por separado. La disponibilidad depende del sistema y del hardware.

## Guías de terceros

Las guías y recursos de `.agents/skills` se excluyen: su copia local no incluía una licencia de redistribución verificable. El instalador existente `python3 -B sistema/skills.py actualizar` obtiene las guías oficiales mediante la CLI HyperFrames instalada. Revise las condiciones del proveedor antes de usar o redistribuir sus recursos. El código no incluye esas guías, fuentes, música ni sprites.

GSAP y sus plugins deben obtenerse desde la dependencia declarada. Los scripts esperan sus archivos locales en las rutas indicadas por cada motor; el repositorio no distribuye copias minificadas.

## Recursos y pruebas

Los manifiestos de diseño, escenas y recursos describen el contrato del motor. Sus archivos binarios no se distribuyen y sus estados históricos no otorgan derechos de uso. Las marcas de terceros requieren su propia revisión de condiciones; los registros separan autenticidad y autorización de publicación.

Las pruebas unitarias de contrato funcionan sobre entradas sintéticas. Las pruebas de navegador, render, comparativas y publicación necesitan entradas locales, herramientas y recursos propios. No se declaran validadas sin esos insumos.
