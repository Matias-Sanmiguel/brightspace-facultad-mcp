# Instalación con tu agente de IA

Copiá el siguiente prompt en un agente con acceso a la terminal de tu computadora
(por ejemplo, Codex, Claude Code o Cursor). El inicio de sesión y la verificación
MFA los completás vos en el navegador que abre el programa.

## Prompt listo para pegar

```text
Instalá y conectá Brightspace Facultad MCP en esta computadora.
Repositorio oficial del proyecto:
https://github.com/Matias-Sanmiguel/brightspace-facultad-mcp

USE AT YOUR OWN RISK: este proyecto se ofrece sin garantías. Al pedirme que lo
instales, acepto usarlo bajo mi propia responsabilidad. Las políticas de acceso
de mi institución siguen vigentes.

Objetivo: dejar el MCP local instalado, configurado en el cliente que estoy
usando y probado. Ejecutá el trabajo y verificá el resultado.

1. Identificá el sistema operativo, el cliente MCP y la disponibilidad de
   Python 3.11 o posterior. Revisá las instrucciones del proyecto y del cliente.
   Si no podés identificar el cliente, preguntame solo ese dato y avanzá con
   la instalación mientras tanto.
2. Descargá el repositorio en una carpeta permanente dentro de mi usuario.
   Si ya existe, revisá su estado y conservá los cambios locales. Leé README.md,
   docs/VERIFICACION.md e INSTALL_WITH_AI.md antes de ejecutar los instaladores.
3. Instalá las dependencias con scripts/install.py usando Python 3.11+.
   En Windows: py -3 scripts/install.py.
   En macOS/Linux: sh install.sh.
   Usá el entorno .venv creado por el instalador. Si falta Python o una
   biblioteca del sistema, explicá exactamente qué falta y usá el procedimiento
   de instalación apropiado para este sistema y sus permisos disponibles.
4. Ejecutá `-m brightspace_facultad_mcp doctor` con el Python de .venv y resolvé
   los problemas de instalación que reporte.
5. Abrí `-m brightspace_facultad_mcp login` con ese mismo Python. Pedime completar
   personalmente el ingreso y MFA en el navegador dedicado; esperá mi respuesta
   y comprobá que el comando confirme la sesión. No me pidas contraseñas,
   códigos MFA, cookies ni tokens. Respetá cualquier restricción institucional;
   si impide el acceso, informá el bloqueo.
6. Leé mcp-config.json y agregá únicamente el servidor brightspace-facultad al cliente
   MCP local que uso. Conservá las otras entradas y hacé una copia de seguridad
   antes de editar la configuración. Usá las rutas absolutas, command, args y
   env generados para ESTA máquina; adaptá solo el formato al cliente.
   Asegurá BRIGHTSPACE_MCP_HEADLESS=1 en env para las consultas sin ventana. El ingreso
   del paso 5 se hace en modo visible, antes de iniciar el cliente MCP.
   En Codex podés usar `codex mcp add brightspace-facultad ... -- COMANDO ARGUMENTOS`.
   Para clientes que admitan esos ajustes, asigná 30 segundos al inicio y
   180 segundos a las llamadas. La comunicación es local por stdio.
7. Liberá el perfil del proceso de login antes de iniciar el servidor MCP.
   Verificá el arranque, el descubrimiento de las ocho herramientas y una
   consulta de estado. Si el cliente necesita reiniciarse, indicámelo; no
   afirmes que las herramientas ya están cargadas en mi chat sin comprobarlo.
   Con mi sesión activa, comprobá listar_materias sin guardar contenido privado
   en el repositorio ni en un reporte compartible.
8. Decime dónde quedó instalado, qué cliente configuraste, qué verificaste
   y si queda alguna acción manual. Mostrame tres ejemplos de pedidos sobre
   mis tareas, anuncios y materiales.

Cada persona usa su propia cuenta y perfil local. No compartas .venv,
mcp-config.json, el perfil del navegador, documentos privados ni credenciales.
No subas archivos a GitHub ni publiques nada como parte de esta instalación.
```

Un agente que solo pueda conversar, o un cliente que solo admita MCP remoto por
URL, necesita acceso adicional para instalar y ejecutar un servidor local.
