# Brand Asset Registry

Seis archivos originales de cinco marcas, guardados una sola vez en `recursos/brands`. Descargados de fuentes oficiales, inspeccionados visualmente y verificados por SHA, dimensiones y transparencia. Las dos variantes de Claude son Spark y wordmark, no copias del mismo archivo.

La autenticidad y el permiso de publicación son estados separados. `private_review` prepara la prueba y los mockups autorizados por el usuario; no concede permiso para publicarlos. El contexto predeterminado `editorial_reel` conserva la restricción hasta revisar una excepción aplicable o registrar una autorización real.

| Marca | Recurso canónico | Fuente oficial | Estado de publicación actual |
| --- | --- | --- | --- |
| Google | `google_wordmark.svg` | [Brand Resource Center](https://about.google/brand-resource-center/guidance/) y CDN de branding de Google | Clasificar contexto y revisar aprobación aplicable. |
| Claude | `claude_spark.svg`, `claude_wordmark.svg` | [Press kit de Anthropic](https://www.anthropic.com/news) | Aprobación previa de materiales pendiente según [su guía](https://www.anthropic.com/legal/trademark-guidelines). |
| LinkedIn | `linkedin_icon.png` | [Downloads oficial](https://brand.linkedin.com/downloads) | El uso del [icono](https://brand.linkedin.com/in-logo) tiene excepciones específicas; el contexto de video no está autorizado automáticamente. |
| YouTube | `youtube_icon.png` | [Pack oficial](https://brand.youtube/youtube-icon/) | [Media/entretenimiento](https://brand.youtube/entertainment-and-media/) requiere revisión, con excepción para prensa; no se presume esa excepción. |
| Instagram | `instagram_glyph.png` | [Pack y reglas de Meta](https://www.meta.com/brand/resources/instagram/instagram-brand/) | Revisar restricciones del contexto concreto; no se afirma que todo reel requiera solicitud. |

```python
import brand_registry

catalogo = brand_registry.catalog(context="private_review")
entidades = brand_registry.resolve_entities(guion)
assets = brand_registry.assets_for_engine(
    entities=entidades, context="private_review", data_uri=True,
)
```

`catalog()` devuelve una lista sin blobs: identidad, estado, razones, fuentes y condiciones, incluidas las marcas pendientes. `resolve_entities()` reconoce marcas registradas; no decide familias ni reemplaza la comprensión narrativa del planner. `assets_for_engine()` devuelve el mapa por ID y verifica el SHA antes de leerlo. Con `data_uri=True`, la clave `data` contiene una URI compatible con `C.image`; no hay red durante render.

```bash
python3 -B sistema/clone/brand_registry.py verify
python3 -B sistema/clone/brand_registry.py catalog --context private_review
```

El flujo de incorporación es:

1. Recuperar el archivo de una fuente oficial, inspeccionarlo y conservar sus bytes, MIME, dimensiones y transparencia.
2. Registrar SHA, fuente, condiciones y decisión para el contexto concreto. Separar autenticidad, preparación privada y permiso de publicación.
3. Entregar el catálogo al planner; enlazar sus parámetros mediante `asset_id` y entidad. La familia se decide por significado, con la procedencia del binding conservada.
4. Compilar recursos locales y verificar sus hashes. Respetar las restricciones de cada marca al animar la composición.
5. Comprobar el MP4 real: que el logo aparece, se reconoce en móvil y no está deformado, recoloreado o afectado por una transformación prohibida. Un archivo empaquetado no demuestra uso visible.
6. Registrar tiempos realmente usados y el SHA del render. Revisar los permisos de publicación pendientes antes de publicar; la entrega privada para revisión no los sustituye.

Para otra marca, incorporar primero un archivo auténtico de fuente oficial y revisar sus condiciones; luego agregar una entrada al JSON canónico. Un logo no registrado o sin verificación no se inventa ni se reemplaza silenciosamente por texto. Registrar por contexto la decisión y su evidencia. La preparación privada nunca cambia automáticamente `publication_authorized`.

Preservar colores, proporciones y archivos originales. En particular, YouTube prohíbe contornos, sombras sobre el icono, recolor, rotación, inclinación y deformación. La sombra de una tarjeta y las transformaciones de la composición requieren mantener intacta y legible la marca. Ningún contacto con las marcas fue enviado; los permisos pendientes permanecen en [brand_assets.json](brand_assets.json).

La skill local `media-use` se aplicó a congelar identidad, reutilización y procedencia. Se excluyeron su cascada de proveedores ajenos y la caché global porque este encargo exige fuentes oficiales y escrituras exclusivamente en IVAN. No se instalaron herramientas ni se modificaron las familias, el motor o el adaptador.
