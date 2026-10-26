# Modelos de Gemini usados en el proyecto.
# Los modelos 1.5 fueron retirados por Google; 2.5-flash solo funciona en cuentas que ya lo usaban.

# Generación principal: redactar el contenido pedagógico (agentes del hito 3).
GEMINI_GENERACION = "gemini-3.8-flash"

# Generación rápida y barata: evaluaciones, metadatos y tareas cortas.
GEMINI_LIGERO = "gemini-3.5-flash-lite"

# Embeddings: si se cambia este modelo hay que borrar vectorstore/ y regenerar el índice.
# No se pueden mezclar vectores de modelos distintos.
GEMINI_EMBEDDINGS = "models/gemini-embedding-001"
