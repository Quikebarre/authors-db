# Conversación con Claude (claude.ai) — planteamiento y arranque del repo

- **Herramienta**: Claude (claude.ai), modelo Claude Opus 5.5
- **Fechas**: 2026-10-03 y 2026-10-04
- **Alcance**: discusión del enfoque, alternativas con IA (embeddings, SLM), creación del repo,
  subida de la semilla y prompt de arranque.
- Las acciones con herramientas (crear el repo, hacer commits) aparecen resumidas entre corchetes.

---

## Turno 1 — Usuario

> [Adjunta el PDF del enunciado: "Prueba Técnica Senior Data Engineer – Base de datos de autores"]
>
> Me han pasado esto, como lo afrontarías?

## Turno 1 — Claude

Lo plantearía como un problema de **resolución de entidades con trazabilidad**, no de scraping masivo.
Lo que evalúan es cómo decides qué es un "match" fiable y cómo lo demuestras.

**1. Acotar el alcance (decirlo explícitamente en el README)**
- Fuentes: **Wikidata** (SPARQL/API) y **Open Library Authors API**. Son públicas, estructuradas,
  tienen IDs estables y no hay que scrapear HTML. Wikidata además enlaza a Open Library (P648), VIAF e
  ISNI, así que puedes cruzar una fuente con la otra.
- Campos limitados: QID, ID de Open Library, nombre canónico, fechas de nacimiento y muerte,
  nacionalidad, idioma, 3 obras principales, nº de obras.
- No usaría un LLM para generar datos. Como mucho, para revisar casos dudosos, y documentado.

**2. Pipeline**
1. **Normalizar la semilla**: trim, Unicode NFC, detectar "Apellido, Nombre", deduplicar y conservar
   siempre el `seed_name` original.
2. **Buscar candidatos** en Wikidata y filtrarlos por ocupación escritor/novelista/poeta (P106) o por
   tener obras o ID de Open Library.
3. **Puntuar cada candidato** según similitud de nombre (rapidfuzz), ocupación, si existe enlace cruzado
   con Open Library y el número de sitelinks como desempate.
4. **Clasificar** cada autor como `matched`, `ambiguous` o `not_found`, con `confidence` y
   `match_reason`. Es mejor dejar un caso como ambiguo que forzar el match.
5. **Enriquecer** desde Open Library y registrar los conflictos (por ejemplo, fechas distintas entre
   fuentes) en lugar de resolverlos en silencio.

**3. Almacenamiento**
- **SQLite o DuckDB** con tres tablas: `authors`, `author_works` y `match_candidates` (todos los
  candidatos con su puntuación, para poder auditar).
- Procedencia por campo: `source` y `retrieved_at`.
- Caché en disco de las respuestas HTTP crudas (JSON). Así el proceso es reproducible sin red y
  cualquiera puede verificar de dónde salió cada dato.
- Export en CSV o Parquet.

**4. Calidad (el informe que más pesa)**
- Cobertura: % matched, % ambiguous y % not found.
- Lista de casos dudosos con el motivo: homónimos, seudónimos (Fernando Pessoa, Elena Ferrante),
  autorías colectivas, nombres en otros alfabetos, conflictos entre fuentes.
- Validación manual de una muestra de unos 20 matches, con la precisión estimada.
- Algunos tests unitarios de normalización y scoring.

**5. Reproducibilidad y entrega**
- Repo con `uv`/`requirements`, un único comando (`make all` o `python -m pipeline`), rate limiting y
  User-Agent identificable.
- `DECISIONS.md` y `QUALITY.md` cortos.
- Carpeta `ai-usage/` con los prompts relevantes y, sobre todo, qué validaste y qué descartaste.

**Reparto de las 2-3 h:** 20 min de exploración de la semilla y las fuentes, 75 min de pipeline y
matching, 30 min de almacenamiento y export, 30 min de calidad y revisión manual, 15 min de
documentación.

---

## Turno 2 — Usuario

> Para deduplicacion también se podría aplicar una última capa de embedings y buscar similitudes?

## Turno 2 — Claude

Se podría, pero la usaría como mucho para **señalar pares a revisar**, nunca para fusionar
automáticamente. En este caso aporta poco y resta defendibilidad.

**Por qué aporta poco aquí**
- Los nombres son cadenas cortas sin semántica. Un embedding mide parecido, no identidad, así que
  "John Smith" y "John Smyth" quedan muy cerca aunque sean personas distintas. Con homónimos genera
  falsos positivos justo donde más duele.
- Para erratas y variantes funcionan mejor, y se explican mejor, la similitud por caracteres
  (rapidfuzz, Jaro-Winkler) y la fonética (Metaphone/Soundex con `jellyfish`).
- Las variantes difíciles (seudónimos, transliteraciones como Достоевский/Dostoevsky, "Gabo") ya las
  resuelve Wikidata con sus alias.

**La deduplicación más fuerte va después de resolver la entidad.** Si dos `seed_name` acaban en el
mismo QID o en el mismo ID de Open Library, son el mismo autor, con evidencia externa. Eso es mucho más
defendible que un coseno de 0,87.

**Dónde sí tendría sentido**
- Como bloqueo o generación de candidatos sobre los `not_found`, para encontrar posibles duplicados que
  ninguna fuente resolvió.
- Con un modelo multilingüe, para variantes entre alfabetos que no estén en los alias.
- Marcando los pares como `possible_duplicate` en una tabla aparte, con umbral documentado y unos
  cuantos ejemplos validados a mano.

Para una prueba de 2-3 horas, lo dejaría en `DECISIONS.md` como mejora futura justificada: "lo
consideré, por esto no lo apliqué, así lo añadiría".

---

## Turno 3 — Usuario

> Si se aplica una slm después de las similitudes

## Turno 3 — Claude

Eso sí tiene más sentido que los embeddings, siempre que el SLM haga de **árbitro con evidencia** y no
de fuente de datos.

**Cómo lo plantearía**
- **Solo sobre el subconjunto `ambiguous`**: pares de posibles duplicados o autores con varios
  candidatos cerca en puntuación. El resto lo deciden reglas e IDs.
- **Le das la evidencia, no le preguntas lo que sabe.** Por ejemplo: "Seed: 'J. Marías'. Candidato A:
  Javier Marías, novelista, 1951–2022, obras [...]. Candidato B: Julián Marías, filósofo, 1914–2005,
  obras [...]". Así decide con contexto en lugar de tirar de memoria, que es donde alucina.
- **Salida estructurada y validada**: un JSON con `decision` (A/B/none/same/different),
  `evidence_fields` y `rationale`, validado con Pydantic. Siempre debe existir la opción "no lo sé".
- **Reproducible**: modelo local con versión fijada (Qwen 2.5 7B o Llama 3.x 8B en Ollama, por
  ejemplo), temperatura 0, prompt versionado y respuestas cacheadas en el repo.
- **Trazable**: cada decisión se guarda con `resolved_by = slm` y una confianza menor que la de un
  match por ID, para que se pueda filtrar.

**Lo que lo hace defendible**
- Etiquetar a mano unos 20-30 casos ambiguos y medir el acuerdo del SLM con tu criterio. Ese número va
  al `QUALITY.md`.
- Documentar los fallos: sesgo hacia el autor más famoso, nombres no occidentales, casos donde dijo
  "same" sin evidencia.
- Nunca dejar que rellene campos (fechas, nacionalidad). Solo elige entre candidatos que ya existen.

**El riesgo, en una prueba de 2-3 horas**, es el tiempo de montarlo y validarlo. Pipeline determinista
completo primero y, si sobran unos 30-40 minutos, el SLM como capa opcional (`--adjudicate`) solo sobre
los ambiguos, con la tabla de acuerdo. Si no da tiempo, queda descrito en `DECISIONS.md`.

---

## Turno 4 — Usuario

> creame un repo en mi github para empezar a trabajar
>
> (mensaje intermedio) solo el esqueleto para emprezar a trabajar, no crees ficheros

## Turno 4 — Claude

[Comprobó la CLI de GitHub: el token del entorno no era válido. Empezó a generar ficheros de código y
documentación; tras la indicación del usuario, los eliminó y dejó solo la estructura de carpetas con
`.gitkeep`.]

[Abrió github.com/new en el navegador integrado. El usuario inició sesión él mismo. Claude rellenó el
formulario y pidió confirmación antes de crearlo:]

- Propietario: Quikebarre
- Nombre: `authors-db`
- Descripción: "Base de datos enriquecida de autores a partir de fuentes públicas (Wikidata, Open
  Library)"
- Visibilidad: privado
- Sin README, `.gitignore` ni licencia

**Usuario**: ok

[Repo creado. Primer commit "Estructura inicial del proyecto" con:]

```
src/authors_db/sources/
tests/
data/{input,cache,output}/
docs/
ai-usage/
```

---

## Turno 5 — Usuario

> [Adjunta authors_seed.csv] Este es el .csv subelo

## Turno 5 — Claude

[Commit "Añade fichero semilla authors_seed.csv" en `data/input/`, sin modificar.]

Casos a tener en cuenta en el matching y en el informe de calidad:

- **Seudónimos en pareja** (el mismo autor dos veces): J. K. Rowling / Robert Galbraith, Lewis Carroll
  / Charles Lutwidge Dodgson, Mark Twain / Samuel Clemens, George Eliot / Mary Ann Evans, Karen Blixen /
  Isak Dinesen, Romain Gary / Émile Ajar, Dr. Seuss / Theodor Seuss Geisel. Justo el caso de deduplicar
  por QID.
- **Valores que no son autores**: `Anonymous`, `Various Authors` y una última línea vacía.
- **Nombres de una sola palabra o muy ambiguos**: Homer, Azorín, Colette, Adonis, Rumi, Hafez,
  Premchand, Stendhal, Molière, Virgil, Petrarch, Pepetela, Plato.
- **Autores de no ficción** (Hawking, Kahneman, Chomsky, Harari, Sun Tzu…): propuesta de contarlos como
  autores de libros si tienen obras en Open Library, en lugar de filtrar solo por novelista.
- **Transliteraciones y diacríticos**: Dostoevsky, Ngũgĩ wa Thiong'o, Nguyễn Du, Kenzaburō Ōe, Natsume
  Soseki frente a Sōseki.
- **Grafías especiales**: `bell hooks` en minúsculas, "Calderón de la Barca", "Leopoldo Alas Clarín",
  "Inca Garcilaso de la Vega".

En total, 499 nombres más la línea vacía.

---

## Turno 6 — Usuario

> dame un prompt con lo hablado

## Turno 6 — Claude

Prompt de arranque generado para continuar el trabajo con un asistente de código. Se guarda aparte en
[`00-prompt-inicial.md`](00-prompt-inicial.md).

---

## Turno 7 — Usuario

> guarda esta conversacion entera

[Este fichero.]

---

## Turno 8 — Usuario

> no has incluido en las intrucciones de que en la base de datos genere tablas intermedias donde se
> almacenen datos procesados pero que no son el resultado final

## Turno 8 — Claude

[Actualizado el punto 5 del prompt inicial: almacenamiento en capas `raw_*` → `stg_*` → tablas
finales, más `pipeline_runs` con `run_id`. Las finales se construyen con SQL desde `stg_*`, los pasos
son idempotentes y solo se exportan las finales.]

---

## Qué he validado / decidido yo (completar)

- [ ] Fuentes: Wikidata + Open Library
- [ ] Embeddings descartados para dedupe; documentados como alternativa
- [ ] SLM como árbitro opcional solo para ambiguos
- [ ] Criterio sobre autores de no ficción
- [ ] Tratamiento de "Anonymous" / "Various Authors"
