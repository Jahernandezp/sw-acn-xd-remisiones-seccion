import html
import mimetypes
import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

PLANTILLA = """Buenos días equipo.

Solicito de su apoyo para ejecutar los siguientes scripts:

Proyecto GCP: {proyecto}
Servicio: Cloud SQL
Base de datos: {base_datos}
IP (Mediante DBeaver): {ip}

La solicitud corresponde a la actualización de los registros específicos referentes a remisiones que se quedaron con un valor NULL o 0 en la sección.

Dicha actualización busca asignarles la sección correspondiente a sus respectivas remisiones.

Impacto positivo: Corrección del valor de la sección para {n_remisiones} {txt_remisiones}.
Impacto Negativo: La operación no puede continuar con el proceso.
Urgencia: Es necesario y prioritario para que dichas remisiones puedan continuar con el flujo.

-- scripts a ejecutar --

{scripts}

Saludos cordiales,
{usuario}
{grupo}
"""


def _lista(valor: str) -> list[str]:
    """'a@x.com, b@x.com; c@x.com' -> ['a@x.com', 'b@x.com', 'c@x.com']"""
    return [c.strip() for c in (valor or "").replace(";", ",").split(",") if c.strip()]


def _requerida(nombre: str) -> str:
    valor = os.getenv(nombre, "").strip()
    if not valor:
        raise ValueError(f"falta la variable {nombre} en el archivo .env")
    return valor


def _adjuntar(msg: EmailMessage, ruta: str):
    tipo, _ = mimetypes.guess_type(ruta)
    if ruta.endswith(".sql"):
        tipo = "text/plain"
    principal, secundario = (tipo or "application/octet-stream").split("/", 1)
    with open(ruta, "rb") as f:
        msg.add_attachment(f.read(), maintype=principal, subtype=secundario,
                           filename=os.path.basename(ruta))


def construir_mensaje(ruta_sql: str, ruta_excel: str | None, remisiones: list[str], dia: date) -> EmailMessage:
    para = _lista(_requerida("MAIL_TO"))
    cc = _lista(os.getenv("MAIL_CC", ""))
    remitente = os.getenv("MAIL_FROM") or _requerida("SMTP_USER")

    with open(ruta_sql, encoding="utf-8") as f:
        scripts = f.read().strip()

    n = len(remisiones)
    datos = {
        "proyecto": os.getenv("GCP_PROJECT", ""),
        "base_datos": os.getenv("DB_NAME", ""),
        "ip": os.getenv("DB_IP") or os.getenv("DB_HOST", ""),
        "n_remisiones": n,
        "txt_remisiones": "remisión" if n == 1 else "remisiones",
        "scripts": scripts,
        "usuario": os.getenv("MAIL_FIRMA_USUARIO", "Usuario solicitante"),
        "grupo": os.getenv("MAIL_FIRMA_GRUPO", "Grupo solicitante"),
    }
    texto = PLANTILLA.format(**datos)

    msg = EmailMessage()
    asunto = os.getenv("MAIL_SUBJECT", "Solicitud de ejecución de scripts - Actualización de sección en remisiones")
    msg["Subject"] = f"{asunto} ({dia.isoformat()})"
    msg["From"] = remitente
    msg["To"] = ", ".join(para)
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.set_content(texto)

    # Versión HTML: igual al texto, con los scripts en bloque monoespaciado.
    cuerpo_html = html.escape(PLANTILLA.format(**{**datos, "scripts": "@@SCRIPTS@@"})).replace("\n", "<br>\n")
    bloque = ('<pre style="background:#f4f4f4;border:1px solid #ddd;padding:10px;'
              'font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap">'
              f"{html.escape(scripts)}</pre>")
    msg.add_alternative(
        f'<div style="font-family:Arial,sans-serif;font-size:14px">{cuerpo_html.replace("@@SCRIPTS@@", bloque)}</div>',
        subtype="html",
    )

    _adjuntar(msg, ruta_sql)
    if ruta_excel and os.getenv("MAIL_ADJUNTAR_EXCEL", "true").lower() in ("1", "true", "si", "sí", "yes"):
        _adjuntar(msg, ruta_excel)

    return msg


def enviar_solicitud(ruta_sql: str, ruta_excel: str | None, remisiones: list[str], dia: date) -> list[str]:
    """Envía el correo y devuelve la lista de destinatarios (To + Cc)."""
    msg = construir_mensaje(ruta_sql, ruta_excel, remisiones, dia)

    host = _requerida("SMTP_HOST")
    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    seguridad = os.getenv("SMTP_SECURITY", "starttls").lower()  # starttls | ssl | none
    contexto = ssl.create_default_context()

    if seguridad == "ssl":
        servidor = smtplib.SMTP_SSL(host, puerto, context=contexto, timeout=30)
    else:
        servidor = smtplib.SMTP(host, puerto, timeout=30)
    with servidor:
        if seguridad == "starttls":
            servidor.starttls(context=contexto)
        if usuario:
            servidor.login(usuario, password)
        servidor.send_message(msg)  # incluye automáticamente To y Cc

    return _lista(msg["To"]) + _lista(msg.get("Cc", ""))