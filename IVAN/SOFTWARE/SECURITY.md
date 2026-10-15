# Seguridad y privacidad

Ascendia Studio conserva datos de cuentas, proyectos y medios en almacenamiento
local del operador. El código público no incluye cuentas de producción, claves,
sesiones, videos originales, proyectos privados, modelos descargados ni runtimes
instalados. Una versión publicada o una prueba técnica no constituyen una
certificación de seguridad ni una auditoría externa.

## Reportar una vulnerabilidad

Utiliza el canal privado de GitHub del repositorio: **Security and quality →
Advisories → Report a vulnerability**. Incluye versión o commit, impacto,
precondiciones y una reproducción mínima con datos sintéticos. Coordina la
divulgación y la corrección antes de publicar detalles explotables.
Este canal requiere que los administradores habiliten los reportes privados;
este archivo no lo activa. [Guía oficial de reportes privados](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

Si el formulario no aparece, abre una incidencia que solicite un canal privado,
sin describir el exploit ni adjuntar datos sensibles. No publiques contraseñas,
tokens, archivos de sesiones, material de clientes o logs sin depurar, incluso
cuando ayuden a reproducir el problema. No se promete un plazo de respuesta o
soporte de versiones antiguas que no haya sido acordado.

## Datos locales y credenciales

- Mantén `.estado/`, `workspaces/`, proyectos, exportados, bases de datos,
  respaldos y archivos de acceso fuera del repositorio. Cada operador gestiona
  sus propios permisos, conexiones y credenciales; no se heredan las de otros
  clientes ni las de un agente conectado.
- Una regla de `.gitignore` evita incorporaciones accidentales nuevas; no cifra
  datos, no retira archivos ya rastreados y no sustituye controles de acceso.
  Protege también las claves maestras, el equipo y los respaldos locales.
- El paquete público admite únicamente las seis caras OFL y sus cuatro avisos
  declarados en `packs/public_fonts.json`, y las ocho capturas públicas revisadas.
  Las fuentes privadas y evidencias visuales de producción no se redistribuyen.
- Antes de compartir un editable o un respaldo, revisa su contenido y destinatario.
  Un recurso auténtico o una observación técnica no acreditan licencia comercial,
  autorización de publicación ni aprobación editorial.

## Comprobaciones antes de publicar

El script `scripts/security_check.py` revisa rutas y patrones de secretos sin
instalar el editor. En un checkout Git, ejecútalo mediante
`python3 -B scripts/security_check.py --git-tree` desde `IVAN/SOFTWARE`. El
comprobador admite este subdirectorio dentro del repositorio y exige que todo
el checkout coincida con el commit antes y después de revisar sus fuentes.
Usa también el preflight local
del publicador para la lista exacta de archivos: publicar por API no hace que
`.gitignore` se aplique automáticamente.

La plantilla `.github/security-workflow.template.yml` permanece fuera de
`.github/workflows/`, por lo que GitHub no la ejecuta al publicar el repositorio.
Para habilitarla posteriormente, un administrador debe revisar el archivo y
copiarlo a `.github/workflows/security-check.yml` en la raíz del repositorio con una conexión autorizada
para gestionar workflows; un token personal clásico necesita el scope
`workflow`. No añadas el token al código ni a los logs.
[Permisos oficiales para modificar archivos de workflows](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents).

Una vez instalada, **Manual public-source security check** se inicia
exclusivamente con `workflow_dispatch`; no tiene eventos push, pull request ni
tareas programadas. Utiliza permisos de lectura, checkout fijado a un commit
upstream verificado y el mismo script público. No instala modelos, ejecuta
inferencia o renders, ni publica informes o artefactos. Su resultado cubre el
árbol revisado, no todo el historial ni todas las clases de secretos o
vulnerabilidades.

Complementa esa revisión con un escáner de secretos especializado y la protección
de GitHub disponible para el repositorio, especialmente al importar historia.
No se afirma aquí que esas funciones estén activadas o que un escaneo haya
pasado. [Secret scanning de GitHub](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning).

## Si se expone una clave

Revoca o rota primero la credencial en su proveedor y revisa el acceso afectado.
Retirar un archivo del commit no invalida una clave que ya se divulgó.
Después, coordina la retirada del contenido y su historia, identifica copias y
notifica por el canal privado a las personas afectadas. Conserva sólo evidencia
depurada; no copies la clave a incidencias, comentarios, logs o capturas.
[Remediación oficial de secretos detectados](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning).

Antes de desplegar para terceros, evalúa por separado aislamiento de cuentas,
autorización, límites de recursos, conexiones externas, transporte TLS y gestión
de claves. Las pruebas funcionales del proyecto no certifican ese despliegue.
