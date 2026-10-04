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
