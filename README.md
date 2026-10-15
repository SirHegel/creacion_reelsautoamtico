# Creación automática de reels

Herramientas de producción de video vertical, composición y motion graphics,
junto con Ascendia Studio: un editor local con cuentas, espacios de trabajo,
API, CLI y servidor MCP.

## Contenido

- [`IVAN/SOFTWARE/`](IVAN/SOFTWARE/README.md): aplicación, interfaz web,
  automatización, pruebas, perfil base y fuentes públicas OFL con sus licencias.
- [`IVAN/sistema/`](IVAN/sistema/): workflow del operador, análisis audiovisual,
  composición, render y biblioteca de componentes de motion.
- [`IVAN/ejemplos/`](IVAN/ejemplos/README.md): fuentes de montaje y animación
  con nombres y datos de ejemplo.
- Los manuales y ejemplos conservados son versiones depuradas para distribución
  pública. Las referencias audiovisuales y la configuración de cada operador
  se proporcionan por separado.

## Ejecutar Ascendia Studio

```bash
cd IVAN/SOFTWARE
./instalar.sh
./iniciar_multiservice.sh
```

Consulta el [README de la aplicación](IVAN/SOFTWARE/README.md) para requisitos,
modos de edición, automatización y limitaciones. Las herramientas del operador
requieren configurar sus propias conexiones y aportar los medios y fuentes
necesarios; los valores de ejemplo no permiten acceder a servicios reales.
El [mapa de dependencias](IVAN/DEPENDENCIAS_PUBLICAS.md) describe la preparación
del entorno del operador y los recursos que se obtienen por separado.

## Privacidad de esta publicación

El repositorio conserva las fuentes revisadas. Se excluyen credenciales,
sesiones, cuentas, bases de datos, identificadores privados de Drive, archivos
de clientes, grabaciones, transcripciones, exportados, fuentes comerciales,
modelos, cachés e instalaciones locales. Tampoco incluye respaldos.

Las capturas y fuentes incluidas en Ascendia Studio pertenecen a su lista
explícita de recursos públicos revisados. La publicación del código no concede
derechos sobre materiales externos ni acredita una aprobación editorial.

El inventario [`PUBLIC_SOURCE_MANIFEST.json`](PUBLIC_SOURCE_MANIFEST.json)
registra tamaños y SHA-256 de las fuentes publicadas. Para revisar privacidad:

```bash
python3 -B scripts/check_publication.py
python3 -B IVAN/SOFTWARE/scripts/security_check.py --git-tree
```

Consulta también la [política de seguridad](IVAN/SOFTWARE/SECURITY.md) y la
[licencia de Ascendia Studio](IVAN/SOFTWARE/LICENSE). Las dependencias y sus
recursos mantienen sus propias condiciones de uso.
