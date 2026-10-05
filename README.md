# SIGAVI

Aplicación de escritorio en Python para vigilar alertas sanitarias del INVIMA, guardar sus PDF como evidencia, extraer datos, registrar el proceso en SQLite y sincronizar novedades con una copia de la matriz institucional.

## Flujo de actualización

**ACTUALIZAR ALERTAS INVIMA** ejecuta este flujo:

1. Recorre el listado general paginado del portal del INVIMA, que reúne alertas de sus categorías.
2. Incluye documentos publicados desde la fecha configurada, inclusive. El valor inicial del piloto es `2026-08-20`.
3. Detecta novedades por URL de PDF y conserva los casos dudosos para revisión.
4. Descarga los PDF nuevos; reutiliza el archivo local cuando ya existe.
5. Extrae texto y campos disponibles, sin completar información faltante por inferencia.
6. Clasifica según la lista institucional cuando el documento aporta evidencia suficiente.
7. Guarda documentos, datos, errores, huellas y estado de sincronización en SQLite.
8. Agrega solo registros que aún no estén en la matriz de salida.

Cuando el recorrido de todas las páginas termina correctamente, SIGAVI registra qué alertas ya no aparecen en el listado. Solo las marca como no visibles; nunca las elimina de la base de datos o la matriz.

La plantilla original no se sobrescribe. SIGAVI crea `Matriz_Alertas_INVIMA_ACTUALIZADA.xlsx` en la carpeta de datos. La hoja objetivo es `Matriz de Alertas 2025`; se mantienen sus 18 encabezados y se reutilizan las filas preformateadas antes de la zona de historial.

## Desarrollo en Windows

Requiere Python 3.11 o superior y una conexión a Internet para instalar dependencias y consultar el INVIMA.

1. Conserva `app.py`, la carpeta `sigavi`, `requirements.txt` y la plantilla XLSX en la misma carpeta.
2. Abre `iniciar_sigavi.bat`. En la primera ejecución crea `.venv` e instala las dependencias.
3. En SIGAVI, revisa **Configuración** y selecciona la plantilla y la carpeta de datos.
4. Usa **ACTUALIZAR ALERTAS INVIMA**.

También se puede iniciar desde una terminal:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
python app.py
```

`app.py` usa automáticamente el intérprete de `.venv` si existe, así que no es necesario activar `Activate.ps1`.

## Archivos locales

Por defecto, SIGAVI guarda sus archivos en `%LOCALAPPDATA%\SIGAVI`:

- `BaseDatos\sigavi.db`: alertas y ejecuciones de actualización.
- `Evidencia\<programa>\<año>\<mes>\`: PDF oficiales.
- `Matriz_Alertas_INVIMA_ACTUALIZADA.xlsx`: copia diligenciada de la plantilla.
- `logs\sigavi.log`: actividad técnica y errores.
- `config.json`: rutas y fecha inicial.
- `Plantilla\`: copia persistente de la plantilla incluida con el ejecutable, reemplazable desde Configuración.

Las rutas se pueden cambiar desde **Configuración**. Los campos `SERVICIO QUE UTILIZA` y `RESULTADO Y SEGUIMIENTO` se dejan vacíos hasta que exista información institucional. Si el texto del PDF no permite una clasificación clara, SIGAVI conserva la alerta y la deja pendiente de revisión.

## Crear el ejecutable

En Windows, con el código y la plantilla en la misma carpeta, ejecuta `compilar_windows.bat`. El resultado se guarda en `dist\SIGAVI.exe`. El ejecutable y los archivos de datos son independientes: SQLite, PDFs y la matriz se escriben en la carpeta local elegida por la persona usuaria.

## Alcance

Esta primera entrega cubre captura, PDF, extracción, clasificación inicial, SQLite y sincronización XLSX. El catálogo de productos de la IPS, priorización automática, correos/Spark, evidencias de socialización e informes de comité son etapas posteriores.
