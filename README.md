Reporte de Remisiones a Excel
Aplicación en Python que se conecta a una base de datos MySQL, consulta los items de remisión creados el día anterior (hora de Ciudad de México) y genera un archivo Excel con el resultado.

Requisitos
Python 3.9 o superior
Acceso de red a la base de datos MySQL
Un usuario de MySQL con permiso de lectura (SELECT) sobre las tablas Remision e ItemRemision
Instalación
Entra a la carpeta del proyecto:

cd reporte_remisiones
(Recomendado) Crea y activa un entorno virtual:

Linux / macOS

python3 -m venv venv
source venv/bin/activate
Windows

python -m venv venv
venv\Scripts\activate
Instala las dependencias:

pip install -r requirements.txt
Configuración
Copia el archivo de ejemplo:

Linux / macOS

cp .env.example .env
Windows

copy .env.example .env
Edita .env con los datos de tu servidor:

Variable	Descripción	Ejemplo
DB_HOST	Servidor MySQL	192.168.1.10
DB_PORT	Puerto (opcional, por defecto 3306)	3306
DB_USER	Usuario	reportes
DB_PASSWORD	Contraseña	********
DB_NAME	Nombre de la base de datos	mi_base
No subas el archivo .env a un repositorio, porque contiene la contraseña.

Ejecución
Reporte del día de ayer (hora de Ciudad de México):

python reporte_remisiones.py
Reporte de un día concreto:

python reporte_remisiones.py --fecha 2026-11-15
Indicar el nombre o la ruta del archivo de salida:

python reporte_remisiones.py --salida reportes/remisiones.xlsx
Ver la ayuda:

python reporte_remisiones.py --help
Si todo sale bien verás algo como:

Consultando remisiones del 2026-11-18 (UTC 2026-11-18 06:00:00 a 2026-11-19 06:00:00)...
Listo: 42 registros -> /ruta/reporte_remisiones/remisiones_2026-11-18.xlsx
Contenido del Excel
El archivo se llama remisiones_AAAA-MM-DD.xlsx por defecto y tiene dos hojas:

Remisiones: los resultados de la consulta, con las columnas IDItemRemision, order_number, material_sku, fk_department, Created_At e IDRemisionTrackingStep. Incluye filtros y la fila de encabezados fija.
Resumen: el día consultado, el total de registros y la fecha y hora de generación.
Consulta que se ejecuta
SELECT ir.IDItemRemision, r.order_number, ir.material_sku, fk_department,
       r.Created_At, ir.IDRemisionTrackingStep
FROM Remision r
LEFT JOIN ItemRemision ir ON ir.IDRemision = r.IDRemision
WHERE r.Created_At >= :inicio_dia_utc
  AND r.Created_At <  :fin_dia_utc
  AND (fk_department = 0 OR fk_department IS NULL)
  AND ir.IDRemisionTrackingStep = 1
  AND ir.Activo = 1;
El inicio y el fin del día se calculan en Python con la zona horaria America/Mexico_City y se convierten a UTC. Por eso no hace falta que MySQL tenga cargadas las tablas de zonas horarias.

Ejecución automática (opcional)
Linux (cron): todos los días a las 7:00 a. m.

0 7 * * * cd /ruta/reporte_remisiones && /ruta/reporte_remisiones/venv/bin/python reporte_remisiones.py >> reporte.log 2>&1
Windows: crea una tarea en el Programador de tareas con:

Programa: C:\ruta\reporte_remisiones\venv\Scripts\python.exe
Argumentos: reporte_remisiones.py
Iniciar en: C:\ruta\reporte_remisiones
Solución de problemas
Mensaje	Causa probable
Faltan variables de entorno: ...	No existe el archivo .env o le faltan valores.
Can't connect to MySQL server	El host o el puerto son incorrectos, o un firewall bloquea la conexión.
Access denied for user	El usuario o la contraseña son incorrectos, o el usuario no tiene permiso desde tu IP.
Unknown database	DB_NAME es incorrecto.
ZoneInfoNotFoundError (Windows)	Ejecuta pip install tzdata.
Listo: 0 registros	No hay datos para ese día; prueba otro con --fecha.
