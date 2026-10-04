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
