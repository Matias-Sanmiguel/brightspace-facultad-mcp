# Brightspace Facultad MCP

Consultá materias, actividades, consignas, noticias y materiales de
[Brightspace UADE](https://virtualbsp.uade.edu.ar/d2l/home) desde un asistente MCP.
Corre en tu computadora con tu cuenta y un Chromium dedicado, como
[Teams Facultad MCP](https://github.com/Matias-Sanmiguel/teams-facultad-mcp),
del que reutiliza infraestructura bajo licencia MIT.

## Instalación

Necesitás Python 3.11+, Internet y un cliente MCP con transporte stdio.

**Linux / macOS**

```sh
sh install.sh
.venv/bin/python -m brightspace_facultad_mcp login
```

**Windows — PowerShell**

```powershell
py -3 scripts/install.py
& .\.venv\Scripts\python.exe -m brightspace_facultad_mcp login
```

El instalador crea `.venv`, instala dependencias fijadas con hashes desde PyPI,
descarga Chromium y genera `mcp-config.json` con las rutas de tu equipo.
En Linux, si Playwright informa bibliotecas faltantes, seguí su diagnóstico de
[dependencias de sistema](https://playwright.dev/python/docs/browsers#install-system-dependencies).
Completá el ingreso y MFA de UADE en la ventana del navegador. Al confirmar
la sesión, el comando cierra el navegador y libera el perfil para el MCP.

Copiá la entrada `brightspace-facultad` de `mcp-config.json` a tu cliente
conservando sus otros servidores. Para Codex, el formato correspondiente es:

```toml
[mcp_servers.brightspace-facultad]
command = "/RUTA/brightspace-facultad-mcp/.venv/bin/python"
args = ["-m", "brightspace_facultad_mcp", "serve"]
startup_timeout_sec = 30
tool_timeout_sec = 180

[mcp_servers.brightspace-facultad.env]
BRIGHTSPACE_MCP_HEADLESS = "1"
```

En Windows, `command` termina en `.venv\\Scripts\\python.exe`; usá las rutas
reales que genera `config`. Si el JSON incluye variables gráficas, trasladalas
también al bloque `env`. Recargá los servidores o reiniciá el cliente.
[Configuración oficial de MCP en Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Herramientas

| Herramienta | Consulta |
|---|---|
| `estado_conexion` | Navegador y estado del ingreso; no abre Chromium por sí sola |
| `iniciar_sesion` | Abre el ingreso si el servidor funciona en modo visible |
| `listar_materias` | Cursos visibles en Mis cursos |
| `listar_tareas` | Actividades de una materia: estado, fecha original y puntuación visible |
| `leer_tarea` | Consigna y referencias a adjuntos; avisa si la actividad cerrada solo permite ver un resumen |
| `leer_anuncios` | Noticias de una materia y sus textos; predeterminado 10 por página |
| `listar_archivos` | Unidades, módulos y temas de Contenido |
| `leer_documento` | Texto de HTML, PDF, DOCX y PPTX, por fragmentos |

Ejemplos:

> Listá mis materias de Brightspace y las actividades de Aplicaciones Interactivas.
>
> Leé la consigna de la actividad y las últimas dos noticias de la materia.
>
> Buscá en los módulos el apunte de React y resumilo indicando la fuente.

Los IDs y cursores se obtienen de resultados anteriores y vencen al reiniciar.
Usá `materia_id` al consultar tareas, noticias y materiales; `carpeta_id` permite
entrar a un módulo. Si hay `cursor`, repetí la misma consulta con ese cursor.
Las fechas se conservan como aparecen en la plataforma; no se inventan fechas
para tareas que no las muestran.

## Sesión local

El perfil se guarda fuera del proyecto, en el directorio de datos de tu usuario
(`~/.local/share/brightspace-facultad-mcp` en Linux por defecto). Cada alumno
instala su copia e ingresa con su propia cuenta. No se usa el perfil de Teams
ni el navegador cotidiano. Un solo proceso puede usar el perfil a la vez.

El cliente usa `BRIGHTSPACE_MCP_HEADLESS=1` para consultar sin ventana. Si la
sesión vence, cerrá el cliente MCP, ejecutá `login` en una terminal gráfica y
reabrí el cliente. El comando `login` necesita modo visible: no lo ejecutes con
`BRIGHTSPACE_MCP_HEADLESS=1`. Para diagnóstico podés cambiar esa variable a `0`.
`BRIGHTSPACE_MCP_DATA_DIR` permite elegir un directorio de perfil independiente.

```sh
.venv/bin/python -m brightspace_facultad_mcp doctor
.venv/bin/python -m brightspace_facultad_mcp config
```

No compartas el perfil ni `mcp-config.json`. Los resultados enviados a tu
asistente quedan sujetos a la configuración del cliente y su proveedor de IA.

## Alcance

Las herramientas consultan: no envían mensajes, entregan trabajos ni responden
cuestionarios. Abrir un tema puede actualizar el progreso de lectura y abrir
noticias puede marcarlas como leídas. No se usan endpoints internos ni se
interceptan tokens. Los enlaces de lectura se limitan a Brightspace UADE.
Se comprueba el destino inicial y el final antes de devolver o procesar contenido.
El navegador puede cargar recursos externos de una página y seguir redirecciones
antes de que el conector rechace un destino inesperado; no es un aislamiento de red.

Mis cursos puede mostrar solo una selección de tus inscripciones. El listado
inicial de Contenido combina módulos visibles y temas del módulo seleccionado;
entrar a cada carpeta permite consultar sus materiales. El MCP indica listas
parciales mediante `completo`, `aviso` y `cursor`. Una actualización de Brightspace
puede requerir adaptar los selectores.

Los documentos admiten hasta 25 MiB y 10.000 caracteres por fragmento. PDF/DOCX/PPTX
se procesan en un subproceso con límites y se borran los archivos temporales.
No hay OCR ni extracción de audio, video, imágenes o diagramas; no se ejecutan
archivos de código, ZIP ni RAR. Una lectura parcial del visor se identifica.

## Desarrollo

```sh
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pytest -q
.venv/bin/python -m build
.venv/bin/python scripts/package.py
```

Las pruebas usan Chromium real sobre páginas sintéticas, sin iniciar sesión.
El paquete de fuentes no contiene entorno virtual, perfiles ni documentos
personales. Después de modificar el código instalado, ejecutá nuevamente
`scripts/install.py` para actualizar el paquete de la instalación.

[Verificación y límites](docs/VERIFICACION.md) · [Licencia MIT](LICENSE).
Proyecto independiente, sin afiliación con UADE ni D2L. Se ofrece tal cual,
sin garantías; verificá fechas y entregas directamente en la plataforma.
