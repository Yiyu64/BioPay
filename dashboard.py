import sqlite3
import time
import html

BASE_DATOS = "biopay.db"
ARCHIVO_HTML = "dashboard.html"

RECHAZOS_SENSOR = "('LECTURA_INVALIDA', 'DEDO_INVALIDO', 'HUELLA_SECA')"

NOMBRES = {
    "REGISTRO_OK": "Huella registrada",
    "YA_REGISTRADO": "Ya registrado",
    "PAGO_OK": "Pago aprobado",
    "NO_REGISTRADO": "No registrado",
    "SIN_FONDOS": "Fondos insuficientes",
    "LECTURA_INVALIDA": "Lectura inválida",
    "DEDO_INVALIDO": "Dedo inválido",
    "HUELLA_SECA": "Huella muy seca",
    "COMANDO_INVALIDO": "Comando inválido",
    "ERROR_BD": "Error interno",
    "PAY": "Pago",
    "REGISTER": "Registro",
}

ESTILO = """
body { font-family: Arial, sans-serif; background: #f4f6f8; color: #222; max-width: 900px; margin: 20px auto; padding: 0 12px; }
h1 { margin-bottom: 4px; }
h2 { margin-top: 28px; font-size: 18px; }
.sub { color: #555; margin-top: 0; }
.tarjetas { display: flex; gap: 12px; flex-wrap: wrap; }
.tarjeta { background: white; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 150px; box-shadow: 0 1px 3px #0002; }
.tarjeta span { display: block; font-size: 34px; font-weight: bold; }
.principal { border-left: 6px solid #2a7de1; }
table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; }
td, th { padding: 6px 10px; text-align: left; border-bottom: 1px solid #e3e6ea; font-size: 14px; }
.ancha { width: 50%; }
.barra { background: #e3e6ea; border-radius: 4px; height: 14px; width: 100%; }
.barra div { background: #2a7de1; height: 14px; border-radius: 4px; }
.alerta { background: #fde8e8; color: #a40000; padding: 8px 12px; border-radius: 6px; margin: 6px 0; }
.ok { background: #e6f4ea; color: #1b5e20; padding: 8px 12px; border-radius: 6px; }
"""

def consultar(sql, parametros=()):
    with sqlite3.connect("file:" + BASE_DATOS + "?mode=ro", uri=True) as conexion:
        return conexion.execute(sql, parametros).fetchall()

def barra(valor, maximo):
    if maximo == 0:
        return '<div class="barra"></div>'
    ancho = 100 * valor / maximo
    return f'<div class="barra"><div style="width:{ancho:.0f}%"></div></div>'

def armar_pagina():
    total = consultar("SELECT COUNT(*) FROM historial")[0][0]
    aprobados = consultar("SELECT COUNT(*) FROM historial WHERE resultado = 'PAGO_OK'")[0][0]
    rechazos = consultar(f"SELECT COUNT(*) FROM historial WHERE resultado IN {RECHAZOS_SENSOR}")[0][0]
    if total > 0:
        porcentaje = 100 * rechazos / total
    else:
        porcentaje = 0

    alertas = ""
    for fila in consultar("SELECT DISTINCT dispositivo FROM historial"):
        dispositivo = fila[0]
        ultimos = consultar(f"SELECT COUNT(*) FROM (SELECT resultado FROM historial WHERE dispositivo = ? "
                            f"ORDER BY id DESC LIMIT 3) WHERE resultado IN {RECHAZOS_SENSOR}", (dispositivo,))[0][0]
        if ultimos == 3:
            alertas += (f'<p class="alerta">ALERTA: {html.escape(dispositivo)} tuvo 3 rechazos seguidos por la lectura '
                        f'del sensor. Revisar el sensor o los umbrales.</p>')
    sin_ubicacion = consultar("SELECT COUNT(*) FROM historial WHERE id_ubicacion IS NULL")[0][0]
    if sin_ubicacion > 0:
        alertas += f'<p class="alerta">ALERTA: hay eventos de placas que no figuran en la tabla de dispositivos (cantidad: {sin_ubicacion}).</p>'
    if alertas == "":
        alertas = '<p class="ok">Sin alertas.</p>'

    resultados = ""
    for fila in consultar("SELECT resultado, COUNT(*) FROM historial GROUP BY resultado ORDER BY COUNT(*) DESC"):
        nombre = NOMBRES.get(fila[0], fila[0])
        resultados += f"<tr><td>{html.escape(nombre)}</td><td class='ancha'>{barra(fila[1], total)}</td><td>{fila[1]}</td></tr>"

    horas = consultar("SELECT strftime('%Y-%m-%d %H:00', fecha, 'localtime') AS hora, COUNT(*), SUM(resultado = 'PAGO_OK') "
                      "FROM historial GROUP BY hora ORDER BY hora DESC LIMIT 8")
    horas.reverse()
    maximo = 0
    for fila in horas:
        if fila[1] > maximo:
            maximo = fila[1]
    por_hora = ""
    for fila in horas:
        por_hora += f"<tr><td>{fila[0]}</td><td class='ancha'>{barra(fila[1], maximo)}</td><td>{fila[1]} eventos, {fila[2]} pagos aprobados</td></tr>"

    por_zona = ""
    for fila in consultar("SELECT COALESCE(u.zona, '(sin zona)'), COUNT(*), SUM(h.resultado = 'PAGO_OK'), "
                          f"SUM(h.resultado IN {RECHAZOS_SENSOR}) "
                          "FROM historial h LEFT JOIN ubicaciones u ON h.id_ubicacion = u.id "
                          "GROUP BY u.zona ORDER BY COUNT(*) DESC"):
        por_zona += (f"<tr><td>{html.escape(fila[0])}</td><td>{fila[1]}</td><td>{fila[2]}</td>"
                     f"<td>{100 * fila[3] / fila[1]:.0f}%</td></tr>")

    ultimos_eventos = ""
    for fila in consultar("SELECT datetime(h.fecha, 'localtime'), h.dispositivo, COALESCE(u.zona, '(sin zona)'), h.comando, "
                          "h.temperatura, h.humedad, h.resultado "
                          "FROM historial h LEFT JOIN ubicaciones u ON h.id_ubicacion = u.id ORDER BY h.id DESC LIMIT 10"):
        comando = NOMBRES.get(fila[3], fila[3])
        resultado = NOMBRES.get(fila[6], fila[6])
        ultimos_eventos += (f"<tr><td>{fila[0]}</td><td>{html.escape(fila[1])}</td><td>{html.escape(fila[2])}</td>"
                            f"<td>{html.escape(comando)}</td><td>{fila[4]} °C</td><td>{fila[5]} %</td><td>{html.escape(resultado)}</td></tr>")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>BioPay - Panel</title>
<style>{ESTILO}</style>
</head>
<body>
<h1>BioPay</h1>
Actualizado a las {time.strftime("%H:%M:%S")}.</p>

<div class="tarjetas">
  <div class="tarjeta"><span>{total}</span>Eventos en total</div>
  <div class="tarjeta"><span>{aprobados}</span>Pagos aprobados</div>
  <div class="tarjeta principal"><span>{porcentaje:.0f}%</span>Rechazos por la lectura del sensor ({rechazos} de {total})</div>
</div>

<h2>Alertas</h2>
{alertas}

<h2>Resultados</h2>
<table>{resultados}</table>

<h2>Eventos por hora</h2>
<table>{por_hora}</table>

<h2>Por zona</h2>
<table><tr><th>Zona</th><th>Eventos</th><th>Pagos aprobados</th><th>Rechazos por sensor</th></tr>{por_zona}</table>

<h2>Últimos 10 eventos</h2>
<table><tr><th>Fecha y hora</th><th>Placa</th><th>Zona</th><th>Operación</th><th>Temperatura</th><th>Humedad</th><th>Resultado</th></tr>{ultimos_eventos}</table>
</body>
</html>"""

while True:
    try:
        pagina = armar_pagina()
        with open(ARCHIVO_HTML, "w", encoding="utf-8") as archivo:
            archivo.write(pagina)
    except sqlite3.Error as e:
        print(f"[ERROR BD] {e}")
    time.sleep(10)
