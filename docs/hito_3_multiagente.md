# Hito 3: orquestación multiagente consolidada

Base: F02 del repositorio oficial. Integra el Researcher conectado a `cargar_vectorstore()` y Writer de Javi, la evaluación tridimensional y feedback de Ivon, y las correcciones de aprobación/límites/pruebas de Nicolás. Fuentes: `javdlg/proyecto-nuevamente-sandbox` (9da6945), `ivonnenegreteR5/proyecto-nuevamente-sandbox`, rama `feature/agente-revisor` (b8568e2).

## Flujo de consulta acordado en la weekly del 6 de octubre

La indexación ocurre previamente: PDF/MD/TXT → limpieza → chunks → embeddings → FAISS. La consulta no reindexa. El grafo recibe `query`, `user_profile`, `output_format` y `niche`; Researcher obtiene los chunks, Writer adapta el texto y Reviewer contrasta contra las fuentes.

Reviewer devuelve tres métricas validadas entre 0 y 1. La aprobación se calcula en código: fidelidad >= 0.80, pedagogía >= 0.75 y formato >= 0.75. Una salida estructurada no garantiza la corrección factual: estos scores son evaluaciones del modelo.

El feedback vuelve al Writer, con un máximo de tres evaluaciones. Los intentos de API son independientes: hasta cuatro llamadas para errores temporales, espera exponencial y jitter; errores no temporales y agotamiento se propagan.

La flecha del diagrama «sí, o al tercer intento» se representa sin aprobación forzada: al agotar revisiones se conserva `current_draft`, `approved=False`, `review_status=max_attempts_reached`, `requires_admin_review=True` y `final_content` vacío. El consumidor puede derivar el borrador al admin, pero no debe presentarlo como contenido aprobado al estudiante. Sin fuentes o sin borrador se termina sin llamar al Reviewer LLM.

`AgentState` conserva fuentes (`retrieved_docs`), borrador, feedback, scores e intentos. `final_content` se publica únicamente al aprobar. El nombre interno es `source_anchoring_score`; el contrato de Hito 4 puede mapearlo a `anclaje_fuente_score`.

JSON pedagógico final/metadatos (F06), paneles/admin (F07) y persistencia OCI (F09) quedan para sus respectivas features. Este PR expone el estado que necesitarán; no implementa esos componentes ni sube archivos a OCI.

## Ejecución

Desde la raíz, Python 3.12, instalar `requirements.txt`, copiar `.env.example` a `.env` y configurar `GEMINI_API_KEY`. Mantener `.env` y `vectorstore/` fuera de Git.

```bash
python src/main.py
python tests/test_fase3.py
python tests/validate_live_review.py
```

Los comandos anteriores envían documentos/chunks al proveedor Gemini y consumen llamadas de API. Fase 3 falla si no obtiene aprobación. La validación adicional verifica la fuente de VCN/reembolsos e inyecta un borrador falso de Starlink para verificar rechazo y autocorrección; el resultado probabilístico puede variar entre ejecuciones.

Pruebas sin API key ni FAISS:

```bash
python -m unittest discover -s tests -p test_review_flow.py -v
```

Comprueban el grafo real con respuestas simuladas: umbral, feedback, agotamiento, aprobación en tercera revisión, límites de las tres métricas, fuentes/borrador vacíos y reintentos de API.

## Integración

La entrega se divide en PR encadenados: F02 → develop; F03 → F02; F04 → F03; F05 → F04; orquestación E03 → F05. Cada diff muestra solamente su entrega. Los PR posteriores están bloqueados por la integración anterior: al integrar F02 en develop, redirigir F03 a develop; repetir con F04, F05 y E03 cuando su dependencia esté en develop. No fusionar los PR posteriores sobre las ramas anteriores: sus bases provisionales sirven para revisar sin mezclar los diffs.

Referencias Kanban: F03 #12/PBI #15; F04 #13/PBI #16; F05 #14/PBI #17; orquestación #4. Estos PR están en revisión, no Done. Se conserva el PR monolítico original como referencia histórica, reemplazado por las entregas separadas. No fusionar saltándose la revisión del equipo.

## Validación del 6 de octubre de 2026

11 pruebas offline pasaron con Python 3.12, LangGraph 1.2.12, langchain-google-genai 4.4.0 y Pydantic 2.13.5. Ingesta del PDF/Markdown oficial y embeddings Gemini generaron FAISS correctamente. La consulta VCN recuperó cuatro chunks y produjo contenido aprobado con fidelidad, pedagogía y formato de 1.0. La recuperación seleccionó la fuente correcta para VCN y reembolsos. En la prueba de Starlink, el borrador falso recibió 0.0/0.1/0.5, volvió al Writer y la corrección obtuvo 1.0/1.0/1.0. No hubo 503 en estas llamadas. El agotamiento de revisiones y los errores temporales se verificaron con respuestas/errores simulados; estas pruebas no garantizan ausencia de alucinaciones ni disponibilidad futura del proveedor.
