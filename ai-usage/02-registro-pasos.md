# Registro de pasos (IA)

| Hora (UTC) | Transcurrido | Tipo | Descripción |
|---|---|---|---|
| 18:26:08 | 00:02:23 | PEDIDO | Prompt inicial: prueba técnica Senior Data Engineer (ver 00-prompt-inicial.md). Pide empezar por normalización + tests y exploración en Wikidata, paralelizando. |
| 18:26:08 | 00:02:23 | PROPUESTA | Clonar repo, crear rama feat/normalization-and-exploration (regla: nunca trabajar en main). |
| 18:26:08 | 00:02:23 | PROPUESTA | Verificar entorno: uv 0.11.19 disponible, python3 del sistema no (uv gestionará Python); API de Wikidata accesible (HTTP 200). |
| 18:26:08 | 00:02:23 | DECISION | User-Agent identificable con URL del repo, sin email personal. |
| 18:26:09 | 00:02:24 | PROPUESTA | Crear pyproject.toml, .gitignore, scripts/log_step.sh; lanzar uv sync (lento en /mnt/c, en segundo plano). |
| 18:26:09 | 00:02:24 | PEDIDO | Usuario pide registrar todos los pasos en ai-usage/ y mostrar tiempo transcurrido desde el inicio. Inicio tomado = momento del git clone. |
| 18:26:24 | 00:02:39 | VALIDADO | Scaffold commiteado (87c7ab5); uv sync en curso. |
| 18:27:15 | 00:03:29 | PROPUESTA | normalize.py (NFC, inversión 'Apellido, Nombre' salvo sufijos Jr., match_key con unidecode, marca Anonymous/Various Authors/vacío como inválidos) + 19 tests pasando. |
| 18:27:15 | 00:03:30 | VALIDADO | Semilla real: 500 filas de autor (el prompt decía 499+vacía; no hay línea vacía), sin comas, sin espacios raros, sin duplicados exactos. Solo 2 inválidos: Anonymous, Various Authors. |
| 18:28:08 | 00:04:23 | PROPUESTA | http.py (caché en disco, rate limit, offline, retries) + scripts/explore_wikidata.py (21 nombres, 4 hilos). Primera pasada: 14s. |
| 18:28:26 | 00:04:41 | VALIDADO | Exploración: 'H+W+OL' (humano P31=Q5, ocupación escritor, tiene P648) aísla al autor correcto en 18/20 casos; el ruido (obras, asteroides, apellidos, artículos) nunca cumple las 3. |
| 18:28:26 | 00:04:41 | VALIDADO | Seudónimos: 'Robert Galbraith' -> wbsearchentities devuelve Q34660 (J.K. Rowling) por alias con sim=100 y además un ítem-seudónimo Q110929251 (no humano). Hay que filtrar a humanos y dejar que el QID colapse el duplicado. |
| 18:28:26 | 00:04:41 | DESCARTADO | Mi prueba con 'Dostoevsky' falló por entrada errónea mía; la semilla real dice 'Fyodor Dostoevsky' (línea 222). No es un problema del buscador. |
| 18:28:26 | 00:04:41 | PROPUESTA | Añadir segunda búsqueda CirrusSearch (list=search + haswbstatement:P31=Q5): recupera 'Leopoldo Alas Clarín' (Q312747, sim solo 78.8 por label 'Leopoldo Alas') y 'Samuel Clemens' -> Q7245 (alias no devuelto antes). Candidatos = unión de ambas búsquedas. |
| 18:28:43 | 00:04:58 | PEDIDO | Usuario pide copiar el CLAUDE.md global a ai-usage/ como instrucciones, y mostrar resultados a medida que avance la normalización. |
| 18:28:43 | 00:04:58 | VALIDADO | Copiado CLAUDE.md a ai-usage/03-claude-md-instrucciones.md (revisado: sin claves ni tokens, solo placeholders). |
| 18:28:43 | 00:04:58 | VALIDADO | normalize() sobre la semilla real: 500 filas, 498 válidas, 2 inválidas (Anonymous, Various Authors), 0 cambios de clean_name, 0 colisiones de match_key (sin duplicados por grafía; los seudónimos se detectarán por QID). |
| 18:37:48 | 00:14:03 | DECISION | Usuario valida: (1) candidatos = unión wbsearchentities + Cirrus humanos; (2) humano como filtro duro, traduciendo ítems-seudónimo al humano; (3) seguir con scoring y mostrar ejemplos antes de fijar umbrales. |
| 18:39:18 | 00:15:33 | PROPUESTA | wikidata.py (unión de 2 búsquedas, filtro humano, seudónimo->persona vía P1535/P460, nombres extra P742/P1477), scoring.py (0.65*sim + writer 15 + OL 15 + sitelinks<=3) y explore_scoring.py. |
| 18:39:18 | 00:15:33 | VALIDADO | 30 nombres casos especiales: top-1 correcto en 30/30. Los 6 pares de seudónimos probados (Rowling/Galbraith, Twain/Clemens, Eliot/Evans, Blixen/Dinesen, Gary/Ajar, Seuss/Geisel) colapsan al mismo QID. Márgenes top1-top2 de aciertos: 6.4 (Inca Garcilaso vs Garcilaso de la Vega) hasta >30; homónimos con OL+writer (Homer/Winslow Homer 16.7). |
| 18:39:19 | 00:15:33 | PROPUESTA | Lanzado score_seed.py sobre las 500 filas en segundo plano para ver la distribución real de score/margen antes de fijar umbrales. |
| 18:39:42 | 00:15:57 | VALIDADO | 11 tests nuevos (scoring + parseo Wikidata); 30 tests en total pasando, ruff limpio. |
