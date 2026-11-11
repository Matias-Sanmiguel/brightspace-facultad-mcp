# Brightspace Facultad MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Crear, verificar y conectar un MCP local equivalente a Teams para Brightspace UADE.
**Architecture:** Proyecto hermano independiente, Python y SDK MCP por stdio; Playwright con perfil persistente propio. Reutilizar infraestructura MIT de Teams para referencias, paginación, extracción y CLI, adaptando navegación a las páginas observadas.
**Tech Stack:** Python >=3.11, MCP 2.3.0, Playwright 1.65.0 y dependencias fijadas de Teams.
**Spec:** ../specs/2026-11-11-brightspace-design.txt

## Global Constraints

- Origen de lectura: https://virtualbsp.uade.edu.ar; login interactivo institucional.
- Perfil independiente de Teams fuera del repositorio; consultas serializadas.
- Documentos: máximo 25 MiB, 10.000 caracteres por página; extracción aislada.
- Solo consulta; no abrir cuestionarios para leer documentos ni entregar actividades.
- Cursores firmados por consulta, IDs opacos y resultados parciales explícitos.
- Usuario pidió implementar directamente como Teams el 2026-11-11: ejecución nativa continua.

## Review Focus

- Cursos cargados en componentes con shadow DOM y listas incompletas.
- Actividades cerradas cuyo único enlace es historial o evaluación.
- Material de tipo cuestionario confundido con documento.
- Redirecciones fuera del origen y sesión vencida durante una consulta.
- Descargas grandes o canceladas y páginas de noticias todavía cargando.

### Task 1: Infraestructura y perfil

**Files:** core.py, browser.py, documents.py, document_worker.py, cli.py, __main__.py, __init__.py en src/brightspace_facultad_mcp; tests/test_core.py, test_browser.py, test_documents.py, test_document_worker.py.
**Interfaces:** Settings.from_env(), BrowserSession.require_page()/status()/login()/close(), ReferenceStore, Paginator y extract_async(Path).

- [x] Copiar/adaptar primero las pruebas de infraestructura y escribir pruebas de identidad de origen y sesión de Brightspace.
- [x] Ejecutar pytest: falla por funcionalidad aún ausente.
- [x] Reutilizar infraestructura MIT, cambiar variables a BRIGHTSPACE_MCP y detectar login/estado por origen y navegación del sitio.
- [x] Ejecutar pruebas: pasan con Chromium real sobre páginas sintéticas.

### Task 2: Consultas de Brightspace

**Files:** brightspace.py, navigation.py y tests/test_brightspace.py.
**Interfaces:** BrightspaceService(settings).call(name, **kwargs), ocho métodos del diseño; BrowserSession y referencias de Task 1.

- [x] Escribir fixtures sintéticas de cursos, módulos, noticias y tabla de actividades con y sin enlace.
- [x] Verificar fallo por servicio ausente; implementar navegación por enlaces observados y extracción semántica.
- [x] Probar ID/cursor inválido, cuestionario rechazado antes de navegar, redirección, carga incompleta, actividad cerrada, documentos y descarga limitada.
- [x] Ejecutar suite completa y corregir fallos antes de integrar.

### Task 3: Protocolo, instalación e integración

**Files:** server.py, scripts/install.py, README.md, mcp-config.json local, tests/test_protocol.py y test_cli.py.
**Interfaces:** create_server(Settings) devuelve MCPServer con ocho herramientas, CLI serve/login/doctor/config.

- [x] Escribir prueba stdio real para descubrimiento, estado sin iniciar, headless y validación de límites.
- [x] Verificar fallo por servidor ausente e implementar herramientas con errores sanitizados.
- [x] Instalar entorno aislado con locks de Teams, ejecutar pytest completo, build y doctor.
- [x] Revisar código con agente independiente; resolver hallazgos materiales con regresiones.
- [x] Agregar solo brightspace-facultad al TOML de Codex con copia de respaldo y validar TOML.
- [x] Abrir login propio para que el usuario complete acceso; validar consultas reales si hay sesión.
- [x] Registrar evidencia y límites reales; commit local con identidad de Git ya corregida.
