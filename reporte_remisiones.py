"""
Reporte de remisiones del día anterior (hora de Ciudad de México) -> Excel,
y script SQL para completar fk_department en ItemRemision.

Uso:
    python reporte_remisiones.py                     # día de ayer
    python reporte_remisiones.py --fecha 2026-11-15  # un día concreto
    python reporte_remisiones.py --salida mi_reporte.xlsx --sql mi_update.sql
"""

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pymysql
from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pymysql.converters import escape_item

TZ_MX = ZoneInfo("America/Mexico_City")

# Rango calculado en Python (en UTC) y pasado como parámetros.
# Equivale a la consulta original, pero:
#  - no depende de que MySQL tenga cargadas las tablas de zonas horarias,
#  - no depende de la zona horaria del servidor para CURDATE(),
#  - evita el error de CURDATE()-1 el día 1 de cada mes (20261201-1 = 20261200),
#  - "fk_department IN (0, NULL)" nunca coincide con NULL; se usa IS NULL.
QUERY = """
SELECT ir.IDItemRemision,
       r.order_number,
       ir.material_sku,
       fk_department,
       r.Created_At,
       ir.IDRemisionTrackingStep
FROM Remision r
LEFT JOIN ItemRemision ir ON ir.IDRemision = r.IDRemision
WHERE r.Created_At >= %s
  AND r.Created_At <  %s
  AND (fk_department = 0 OR fk_department IS NULL)
  AND ir.IDRemisionTrackingStep = 1
  AND ir.Activo = 1
"""

# Departamento de un SKU: se toma de otro item con el mismo SKU que sí tenga
# departamento (se ignoran 0 y NULL, que son justo los que queremos corregir).
# Se usa el item más reciente por si el SKU cambió de departamento.
QUERY_DEPARTAMENTO = """
SELECT fk_department
FROM ItemRemision ir
WHERE material_sku = %s
  AND fk_department IS NOT NULL
  AND fk_department <> 0
ORDER BY IDItemRemision DESC
LIMIT 1
"""


def rango_utc(dia: date) -> tuple[datetime, datetime]:
    """Devuelve [inicio, fin) del día `dia` en hora de CDMX, convertido a UTC (naive)."""
    inicio = datetime.combine(dia, time.min, tzinfo=TZ_MX)
    fin = datetime.combine(dia + timedelta(days=1), time.min, tzinfo=TZ_MX)
    a_utc = lambda d: d.astimezone(timezone.utc).replace(tzinfo=None)
    return a_utc(inicio), a_utc(fin)


def conectar():
    faltan = [v for v in ("DB_HOST", "DB_USER", "DB_NAME") if not os.getenv(v)]
    if faltan:
        sys.exit(f"Faltan variables de entorno: {', '.join(faltan)} (revisa el archivo .env)")
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        connect_timeout=15,
    )


def consultar_remisiones(cur, dia: date):
    desde, hasta = rango_utc(dia)
    print(f"Consultando remisiones del {dia} (UTC {desde} a {hasta})...")
    cur.execute(QUERY, (desde, hasta))
    columnas = [c[0] for c in cur.description]
    return columnas, list(cur.fetchall())


def buscar_departamentos(cur, skus) -> dict:
    """Devuelve {sku: fk_department o None} consultando una vez por SKU distinto."""
    departamentos = {}
    skus = sorted({s for s in skus if s is not None})
    print(f"Buscando departamento de {len(skus)} SKU distintos...")
    for sku in skus:
        cur.execute(QUERY_DEPARTAMENTO, (sku,))
        fila = cur.fetchone()
        departamentos[sku] = fila[0] if fila else None
    return departamentos


def generar_sql(columnas, filas, departamentos: dict, ruta: str, dia: date):
    """Escribe un script con un UPDATE por item. Devuelve (actualizables, sin_departamento)."""
    i_id = columnas.index("IDItemRemision")
    i_sku = columnas.index("material_sku")

    actualizables, sin_departamento = [], []
    for fila in filas:
        id_item, sku = fila[i_id], fila[i_sku]
        if id_item is None:
            continue
        depto = departamentos.get(sku)
        (actualizables if depto is not None else sin_departamento).append((id_item, sku, depto))

    q = lambda v: escape_item(v, "utf8mb4")
    comentario = lambda v: str(v).replace("\n", " ").replace("\r", " ")

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(f"-- Actualización de fk_department en ItemRemision\n")
        f.write(f"-- Remisiones del {dia.isoformat()} (hora CDMX)\n")
        f.write(f"-- Generado: {datetime.now(TZ_MX):%Y-%m-%d %H:%M:%S}\n")
        f.write(f"-- Items a actualizar: {len(actualizables)}\n")
        f.write(f"-- Items sin departamento encontrado: {len(sin_departamento)}\n\n")
        f.write("START TRANSACTION;\n\n")
        for id_item, sku, depto in actualizables:
            # La condición extra evita sobrescribir un item que alguien ya corrigió.
            f.write(
                f"UPDATE ItemRemision SET fk_department = {q(depto)} "
                f"WHERE IDItemRemision = {q(id_item)} "
                f"AND (fk_department = 0 OR fk_department IS NULL); "
                f"-- SKU {comentario(sku)}\n"
            )
        f.write("\n-- Revisa el resultado y ejecuta COMMIT; para confirmar o ROLLBACK; para deshacer.\n")
        f.write("-- COMMIT;\n")
        if sin_departamento:
            f.write("\n-- Items sin departamento en ningún otro registro con el mismo SKU (no se actualizan):\n")
            for id_item, sku, _ in sin_departamento:
                f.write(f"--   IDItemRemision {id_item}, SKU {comentario(sku)}\n")

    return actualizables, sin_departamento


def _formatear_hoja(ws, columnas, n_filas):
    encabezado = PatternFill("solid", fgColor="1F4E78")
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = encabezado
        celda.alignment = Alignment(horizontal="center")
    for i, nombre in enumerate(columnas, start=1):
        letra = get_column_letter(i)
        if nombre == "Created_At":
            for celda in ws[letra][1:]:
                celda.number_format = "yyyy-mm-dd hh:mm:ss"
        largo = max([len(str(nombre))] + [len(str(c.value)) for c in ws[letra][1:] if c.value is not None])
        ws.column_dimensions[letra].width = min(largo + 2, 50)
    ws.freeze_panes = "A2"
    if n_filas:
        ws.auto_filter.ref = ws.dimensions


def generar_excel(columnas, filas, departamentos: dict, ruta: str, dia: date):
    wb = Workbook()
    ws = wb.active
    ws.title = "Remisiones"

    i_sku = columnas.index("material_sku")
    columnas_excel = columnas + ["fk_department_sugerido"]
    ws.append(columnas_excel)
    for fila in filas:
        ws.append(list(fila) + [departamentos.get(fila[i_sku])])
    _formatear_hoja(ws, columnas_excel, len(filas))

    skus = wb.create_sheet("SKU - Departamento")
    skus.append(["material_sku", "fk_department"])
    for sku, depto in sorted(departamentos.items()):
        skus.append([sku, depto if depto is not None else "SIN DEPARTAMENTO"])
    _formatear_hoja(skus, ["material_sku", "fk_department"], len(departamentos))

    sin_depto = sum(1 for f in filas if f[i_sku] is not None and departamentos.get(f[i_sku]) is None)
    resumen = wb.create_sheet("Resumen")
    resumen.append(["Fecha consultada (CDMX)", dia.isoformat()])
    resumen.append(["Total de registros", len(filas)])
    resumen.append(["SKU distintos", len(departamentos)])
    resumen.append(["Items sin departamento encontrado", sin_depto])
    resumen.append(["Generado", datetime.now(TZ_MX).strftime("%Y-%m-%d %H:%M:%S")])
    resumen.column_dimensions["A"].width = 34
    resumen.column_dimensions["B"].width = 22

    wb.save(ruta)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Exporta remisiones a Excel y genera el script de actualización.")
    parser.add_argument("--fecha", help="Día a consultar YYYY-MM-DD (por defecto: ayer en CDMX)")
    parser.add_argument("--salida", help="Ruta del archivo Excel de salida")
    parser.add_argument("--sql", help="Ruta del script SQL de actualización")
    args = parser.parse_args()

    if args.fecha:
        dia = date.fromisoformat(args.fecha)
    else:
        dia = datetime.now(TZ_MX).date() - timedelta(days=1)

    salida = args.salida or f"remisiones_{dia.isoformat()}.xlsx"
    salida_sql = args.sql or f"update_fk_department_{dia.isoformat()}.sql"

    try:
        conn = conectar()
        try:
            with conn.cursor() as cur:
                columnas, filas = consultar_remisiones(cur, dia)
                i_sku = columnas.index("material_sku")
                departamentos = buscar_departamentos(cur, (f[i_sku] for f in filas))
        finally:
            conn.close()
    except pymysql.MySQLError as e:
        sys.exit(f"Error de base de datos: {e}")

    generar_excel(columnas, filas, departamentos, salida, dia)
    actualizables, sin_depto = generar_sql(columnas, filas, departamentos, salida_sql, dia)

    print(f"Excel: {len(filas)} registros -> {os.path.abspath(salida)}")
    print(f"SQL:   {len(actualizables)} UPDATE, {len(sin_depto)} sin departamento -> {os.path.abspath(salida_sql)}")


if __name__ == "__main__":
    main()