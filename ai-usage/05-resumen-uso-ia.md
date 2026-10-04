# Resumen del uso de IA

Este fichero resume qué hizo la IA, qué decidió la persona y qué falta por validar.
El registro literal está en los demás ficheros de `ai-usage/`.
Las entradas `VALIDADO` de `02-registro-pasos.md` son comprobaciones del agente, no validación humana.

## Herramientas usadas

| Herramienta | Uso |
|---|---|
| Claude Code (Claude Sonnet 5.5) | Escribió el código, los tests y la documentación, y ejecutó los experimentos. |
| Asesor Claude Opus 5.5 (herramienta `advisor`) | Revisó el plan antes de construir Open Library y el cierre. Se consultó dos veces en este tramo; el registro de pasos solo anota una. |
| Qwen 2.5 7B (`qwen2.5:7b-instruct-q4_K_M`, Ollama, local) | Árbitro dentro del pipeline, solo para filas `ambiguous`. No es fuente de datos. |

## Decisiones tomadas por la persona

- Enfoque de resolución de entidades, con Wikidata y Open Library como fuentes.
- Unión de dos búsquedas de candidatos y filtro duro a humanos.
- Traducir un ítem-seudónimo a la persona.
- Umbral de score 80 y margen 10.
- Orden de resolución: primero el SLM; si no elige, la regla de dominancia.
- Alexandre Dumas se queda `ambiguous`. La solución correcta sería una entrada para el padre y otra para el hijo; queda anotada como decisión abierta y no se implementó.
- Anonymous y Various Authors se quedan en la tabla final con `is_author = false`.
- Marcar las 20 filas de la muestra como correctas (`data/input/human_verdicts.csv`), sin notas por fila.
- El uso del SLM no aporta nada sobre usar solo el score: las 44 filas que resuelve coinciden con el candidato de mayor score. Queda anotado en DECISIONS y QUALITY.
- Almacenamiento en capas `raw_*`, `stg_*` y tablas finales, con `run_id` y pasos idempotentes.
- Documentación en inglés siguiendo las reglas de ASD-STE100, sin afirmar certificación.
- Embeddings descartados para deduplicar; los duplicados se detectan por QID.

## Comprobaciones hechas por el agente

- Normalización sobre la semilla real: 500 filas, 498 válidas, sin colisiones.
- Top-1 correcto en 30 de 30 nombres elegidos a mano (juicio del agente).
- Los 7 pares de seudónimos colapsan al mismo QID.
- El modelo elige "A" en todos los casos; con el orden invertido, 44 de 45 respuestas se mantienen. Dumas es inestable y se descarta.
- Enlace de vuelta de Open Library: 450 de 450 QIDs con enlace coinciden; 0 contradicen.
- Dos fallos propios hallados al revisar conflictos de años: se ignoraba el rango de las declaraciones de Wikidata y se leía "BCE" como año positivo.
- Replay `--offline --adjudicate`: `author_works`, `field_provenance` y `review_sample.csv` idénticos; `authors` difiere solo en la confianza de Dumas, cambiada después.
- Los veredictos del agente sobre la muestra de 20 filas están en `04-agent-verdicts.csv` (19 correctos, 1 plausible).

## Lo que ninguna persona ha comprobado todavía

- La precisión fuera de la muestra de 20 filas. La persona marcó las 20 como correctas (cota inferior 83.9 %, Wilson 95 %).
- Las 34 elecciones del modelo que no están en la muestra.
- Los 40 autores sin enlace de vuelta en Open Library (27 sin Wikidata en OL y 13 sin ID de OL).
- Los 15 autores con 0 obras en Open Library; no se encontró la causa.
