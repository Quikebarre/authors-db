# Prompt inicial (generado con Claude a partir de la conversación de planteamiento)

````markdown
# Contexto
Estoy haciendo una prueba técnica de Senior Data Engineer. Objetivo: construir una base de datos
enriquecida de autores de libros a partir de información pública, partiendo de un fichero semilla.
Valoran una solución ACOTADA, TRAZABLE y DEFENDIBLE por encima de una grande y difícil de verificar.
Tiempo recomendado: 2-3 horas.

Repo: https://github.com/Quikebarre/authors-db (privado, rama main)
Input: data/input/authors_seed.csv — una columna `author_name`, 499 nombres + una línea vacía.

Entregables exigidos:
- Código para generar la base de datos
- Base de datos o export resultante
- Instrucciones de ejecución (README)
- Breve explicación de decisiones técnicas (docs/DECISIONS.md)
- Breve informe de calidad, limitaciones y casos dudosos (docs/QUALITY.md)
- Registro de uso de IA en ai-usage/ (prompts, qué se validó, qué se decidió). Sin claves ni tokens.

Estructura actual (solo carpetas): src/authors_db/sources/, tests/, data/{input,cache,output}/, docs/, ai-usage/

# Enfoque acordado
Tratarlo como RESOLUCIÓN DE ENTIDADES con trazabilidad, no como scraping masivo.

1. Fuentes: Wikidata (API wbsearchentities + SPARQL) como fuente principal y Open Library Authors API
   para obras. Ambas públicas y estructuradas, con IDs estables. Wikidata enlaza a Open Library (P648),
   VIAF (P214) e ISNI (P213). Nada de scraping HTML.
2. Campos acotados: QID, Open Library ID, nombre canónico, fecha de nacimiento/muerte, nacionalidad (P27),
   idioma, nº de obras, hasta 3 obras principales.
3. Pipeline:
   a. Normalizar: trim, Unicode NFC, "Apellido, Nombre" → orden natural, match_key sin acentos ni
      puntuación, dedupe exacto. Conservar SIEMPRE el seed_name original.
   b. Candidatos en Wikidata, considerando alias.
   c. Scoring explícito y explicable: similitud de nombre (rapidfuzz, máx. entre label y alias),
      ocupación de escritor (P106), tiene Open Library ID, sitelinks solo como desempate.
   d. Clasificar en matched / ambiguous / not_found con confidence y match_reason legible. Umbral +
      margen sobre el segundo candidato. Ante la duda, ambiguous: mejor visible que un falso positivo.
   e. Enriquecer desde Open Library. Los conflictos entre fuentes se registran, no se resuelven en silencio.
4. Deduplicación: dos seed_name son el mismo autor si resuelven al MISMO QID u Open Library ID
   (evidencia externa). Marcar duplicate_of, no borrar filas.
5. Almacenamiento: DuckDB con tablas authors, author_works, match_candidates (todos los candidatos
   con puntuación, para auditoría) y field_provenance (source + retrieved_at por campo, flag de
   conflicto). Export a CSV y Parquet en data/output/.
6. Reproducibilidad: caché en disco de todas las respuestas HTTP crudas (JSON con url, params,
   retrieved_at) en data/cache/, modo --offline que solo usa la caché, rate limiting, User-Agent
   identificable, un único comando para ejecutar (make all / python -m authors_db run), opción --limit.
7. Calidad: % matched / ambiguous / not_found, validación manual de una muestra de ~20 matches con
   precisión estimada, lista de casos dudosos con motivo, tests unitarios de normalización y scoring.

# Decisiones sobre IA en el pipeline
- Embeddings para deduplicar: NO en el pipeline principal. Los nombres son cadenas cortas sin semántica;
  un embedding mide parecido, no identidad, y da falsos positivos con homónimos. Documentar en
  DECISIONS.md como alternativa considerada; como mucho serviría para señalar possible_duplicate
  entre los not_found, sin fusionar.
- SLM como árbitro: OPCIONAL (flag --adjudicate), solo si sobra tiempo y solo sobre los ambiguous.
  Recibe la evidencia de los candidatos (nombre, descripción, fechas, obras) y elige entre ellos o
  responde "ninguno"; nunca genera ni rellena campos. Modelo local con versión fijada (p. ej. Qwen 2.5 7B
  o Llama 3.x 8B en Ollama), temperatura 0, prompt versionado, salida JSON validada con Pydantic,
  respuestas cacheadas en el repo, resolved_by = slm con confianza menor. Medir el acuerdo con 20-30 casos
  etiquetados a mano y documentar los fallos.
- Ningún LLM se usa como fuente de datos.

# Casos especiales detectados en la semilla
- Seudónimos en pareja (el mismo autor dos veces): J. K. Rowling / Robert Galbraith, Lewis Carroll /
  Charles Lutwidge Dodgson, Mark Twain / Samuel Clemens, George Eliot / Mary Ann Evans,
  Karen Blixen / Isak Dinesen, Romain Gary / Émile Ajar, Dr. Seuss / Theodor Seuss Geisel.
- No son autores: "Anonymous", "Various Authors", línea vacía final → marcar como invalid/not_an_author.
- Nombres de una sola palabra o muy ambiguos: Homer, Azorín, Colette, Adonis, Rumi, Hafez, Premchand,
  Stendhal, Molière, Virgil, Petrarch, Pepetela, Plato, Voltaire, Laozi, Confucius.
- Autores de no ficción (Hawking, Kahneman, Chomsky, Harari, Sun Tzu…): cuentan como autores de libros
  si tienen obras; no filtrar solo por novelista/poeta.
- Transliteraciones y diacríticos: Dostoevsky, Ngũgĩ wa Thiong'o, Nguyễn Du, Kenzaburō Ōe,
  Natsume Soseki (vs. Sōseki).
- Grafías especiales: "bell hooks" en minúsculas, "Calderón de la Barca", "Leopoldo Alas Clarín",
  "Inca Garcilaso de la Vega".

# Stack
Python 3.11+, uv, httpx, rapidfuzz, unidecode, duckdb, pandas, pyarrow, pydantic, typer, pytest, ruff.

# Reparto de tiempo orientativo
20 min de exploración de la semilla y las APIs · 75 min de pipeline y matching · 30 min de
almacenamiento y export · 30 min de calidad y revisión manual · 15 min de documentación.

# Forma de trabajar
- Avanza por pasos pequeños y verificables; haz commit en cada paso.
- Prioriza el pipeline determinista completo; el SLM va al final y es opcional.
- Explícame las decisiones relevantes para que yo las valide; no cierres umbrales sin mostrarme
  ejemplos reales.
- Ve registrando en ai-usage/ qué se pidió, qué propuso la IA y qué validé o descarté yo.

Empieza por: normalización + tests, y un script de exploración que busque 15-20 nombres
representativos (incluidos los casos especiales) en Wikidata para calibrar el scoring.
````
