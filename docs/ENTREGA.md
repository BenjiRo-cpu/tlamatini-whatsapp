# Material para la entrega en DEV.F

## Descripción breve

Tlamatini es un tutor de historia mexica conectado a WhatsApp que utiliza Llama, memoria conversacional, RAG con Qdrant y function calling para responder con fuentes, crear quizzes y guardar el progreso de cada estudiante. El agente incluye validación del webhook, protección contra inyecciones de prompt, idempotencia, manejo de errores y métricas de operación.

## Problema que resuelve

El acceso a contenidos históricos suele depender de materiales extensos y poco interactivos. Tlamatini transforma esos contenidos en microaprendizaje accesible desde WhatsApp: el estudiante pregunta, profundiza mediante seguimientos y practica sin instalar una aplicación adicional.

## Decisiones técnicas para explicar

- WhatsApp funciona como canal; Llama es el motor de razonamiento.
- El estado se guarda fuera del modelo y se identifica por número telefónico.
- Las respuestas factuales utilizan recuperación de documentos antes de generarse.
- El modelo solicita herramientas, pero el servidor valida y ejecuta cada función.
- Los IDs de Meta impiden procesar dos veces un mismo mensaje.
- El modo de seguridad predeterminado funciona sin servicios adicionales y puede reforzarse con Prompt Guard o Llama Guard.
- Cloudflare Quick Tunnel se utiliza solo para la demostración; no se presenta como infraestructura productiva.

## Resultados técnicos comprobados antes de conectar Meta

- 12 pruebas automatizadas aprobadas.
- Recuperación semántica validada con Qdrant: una consulta indirecta sobre cultivo lacustre recuperó `DOC-04 — Chinampas y agricultura` en primer lugar.
- Ciclo real de function calling probado con un modelo local compatible: búsqueda documental, devolución del resultado a la conversación, respuesta con fuente y registro de métricas.
- Firma HMAC, memoria, quiz, bloqueo de inyección e idempotencia comprobados mediante pruebas automatizadas.

## Resultados de la conexión con Meta

- Webhook verificado por Meta mediante el desafío `hub.challenge` y respuesta HTTP 200.
- Campo `messages` suscrito en la versión v26.0.
- Mensaje real de plantilla recibido desde el número de prueba de WhatsApp.
- Evento `Incoming Message` entregado correctamente desde el panel de Meta al webhook en la prueba final.
- Firma HMAC activada con el App Secret real y validada antes de entregar.

## Pendientes finales

- URL pública final del repositorio de GitHub.

## Descripción para el campus

Tlamatini es un tutor educativo de historia mexica conectado a WhatsApp Cloud API y potenciado por Llama 3.2 mediante Ollama. Utiliza RAG con Qdrant para responder con fuentes, memoria conversacional en SQLite, function calling para quizzes y consulta de progreso, y capas de seguridad para validar firmas, bloquear inyecciones de prompt y evitar mensajes duplicados. Incluye métricas, pruebas automatizadas y ejecución reproducible con Docker.
