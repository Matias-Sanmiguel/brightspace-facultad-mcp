# Verificación

Las pruebas automáticas usan Chromium real con páginas sintéticas representativas
de Brightspace. Cubren referencias y cursores, perfil exclusivo y persistente,
inicio de sesión pendiente, shadow DOM, tareas cerradas, noticias en tabla y en
artículos, carga demorada, documentos HTML/PDF/DOCX/PPTX, límites de descarga,
cancelación y proceso de extracción. Se prueban clientes stdio de las dos APIs
del SDK MCP instalado.

El 11 de noviembre de 2026 se completó el login en el Chromium propio en Linux,
se cerró y se volvió a abrir el perfil en modo sin ventana. La consulta real
recuperó una materia visible y siete actividades. Se leyó una consigna de 1.319
caracteres y un PDF de 2.426 caracteres con extracción completa. La tabla de
noticias muestra trece enlaces del curso; los tutoriales generales se excluyen.
Se abrieron dos detalles de noticias de más de 1.700 caracteres y se comprobó
su paginación. También se entró a un módulo y se extrajo el texto de una página
HTML. Las consignas con adjuntos enlazados se verificaron con un DOCX sintético.
Las pruebas reales no forman parte de la suite y no se guardan contenidos de la
cuenta en el proyecto.

Windows y macOS tienen instaladores y rutas preparadas, pero no se ejecutaron
en esos sistemas. No se verificaron con la cuenta otros cursos, documentos
cifrados, OCR, foros ni cuestionarios; estos últimos no se abren como documentos.

Los resultados de pruebas, compilación y revisión de esta entrega se registran
en el historial local de Git y en el informe de entrega. Que una prueba sintética
pase no garantiza compatibilidad con todas las variantes de interfaz de D2L.

La revisión independiente identificó cargas de iframe, resúmenes de noticias y
marcadores vacíos ocultos que podían producir falsos completos. Se añadieron
regresiones y se corrigieron esos casos, además de la espera de selección de
módulo y la lectura de adjuntos. El origen se verifica antes de elegir un enlace
y después de la redirección del navegador; no se ofrece aislamiento de red.

Entrega final: 52 pruebas aprobadas en Linux (29,03 s), wheel y sdist compilados.
Cliente MCP real iniciado desde la configuración de Codex: ocho herramientas
descubiertas y consultas autenticadas de materia, actividades, consigna, PDF
y anuncio verificadas. Los tres paquetes se inspeccionaron sin encontrar
perfiles, entorno virtual ni configuración personal.
