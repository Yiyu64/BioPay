import sqlite3
import json
import paho.mqtt.client as mqtt

ID_DISPOSITIVO_PRUEBA = "ESP32_02"
ID_UBICACION_PRUEBA = "U02"
HUELLA_PRUEBA = "wokwi_sim_03"
UBICACION_PRUEBA = "San Telmo"
COMERCIO_PRUEBA = "Mc Donald's"
USUARIO_PRUEBA = "Matias Del Soto"
TARIFA = 500.0
SALDO_INICIAL = 1200.0

BROKER = "localhost"
PUERTO = 1883
TOPIC_REQ = "biopay/request"
TOPIC_RES = "biopay/response"
BASE_DATOS = "biopay.db"

HUM_MIN, HUM_MAX = 0.0, 100.0
TEMP_MIN, TEMP_MAX = -40.0, 80.0

UMBRAL_TEMP_MIN, UMBRAL_TEMP_MAX = 30.0, 38.0   # °C
UMBRAL_HUM_MIN = 10.0

MENSAJES = {
    "REGISTRO_OK": "Huella registrada",
    "YA_REGISTRADO": "Ya registrado",
    "PAGO_OK": "Pago aprobado",
    "NO_REGISTRADO": "No registrado",
    "SIN_FONDOS": "Fondos insuficientes",
    "LECTURA_INVALIDA": "Lectura invalida",
    "DEDO_INVALIDO": "Dedo invalido",
    "HUELLA_SECA": "Huella muy seca",
    "COMANDO_INVALIDO": "Comando invalido",
    "ERROR_BD": "Error interno",
}

def inicializar_base_datos():
    with sqlite3.connect(BASE_DATOS) as conexion:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_huella TEXT PRIMARY KEY,
                nombre TEXT,
                saldo REAL
            )
        """)
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS ubicaciones (
                id TEXT PRIMARY KEY,
                nombre TEXT,
                zona TEXT
            )
        """)
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS dispositivos (
                id TEXT PRIMARY KEY,
                id_ubicacion TEXT
            )
        """)
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP,
                dispositivo TEXT,
                id_ubicacion TEXT,
                comando TEXT,
                temperatura REAL,
                humedad REAL,
                resultado TEXT
            )
        """)
        conexion.execute("INSERT OR REPLACE INTO ubicaciones VALUES (?, ?, ?)",(ID_UBICACION_PRUEBA, COMERCIO_PRUEBA, UBICACION_PRUEBA))
        conexion.execute("INSERT OR REPLACE INTO dispositivos VALUES (?, ?)",(ID_DISPOSITIVO_PRUEBA, ID_UBICACION_PRUEBA))

def consultar(sql, parametros):
    with sqlite3.connect(BASE_DATOS) as conexion:
        return conexion.execute(sql, parametros).fetchone()

def ejecutar(sql, parametros):
    with sqlite3.connect(BASE_DATOS) as conexion:
        conexion.execute(sql, parametros)

def guardar_historial(disp, ubicacion, com, temp, hum, resultado):
    ejecutar("""
        INSERT INTO historial (dispositivo, id_ubicacion, comando, temperatura, humedad, resultado)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (disp, ubicacion, com, temp, hum, resultado))

def buscar_ubicacion(dispositivo):
    fila = consultar("SELECT id_ubicacion FROM dispositivos WHERE id = ?", (dispositivo,))
    if fila:
        return fila[0]
    return None

def validar_temphum(temperatura, humedad):
    if temperatura < TEMP_MIN or temperatura > TEMP_MAX or humedad < HUM_MIN or humedad > HUM_MAX:
        print(f"[ERROR SENSOR] Lectura fuera de rango físico: {temperatura}°C, {humedad}%")
        return "LECTURA_INVALIDA"
    if temperatura < UMBRAL_TEMP_MIN or temperatura > UMBRAL_TEMP_MAX:
        print(f"[ALERTA] Temperatura fuera del umbral ({UMBRAL_TEMP_MIN}-{UMBRAL_TEMP_MAX}°C): {temperatura}°C")
        return "DEDO_INVALIDO"
    if humedad < UMBRAL_HUM_MIN:
        print(f"[ALERTA] Humedad fuera del umbral (<{UMBRAL_HUM_MIN}%): {humedad}%")
        return "HUELLA_SECA"
    return "OK"

def registrar(id_huella):
    if consultar("SELECT 1 FROM usuarios WHERE id_huella = ?", (id_huella,)):
        return "YA_REGISTRADO"
    ejecutar("INSERT INTO usuarios (id_huella, nombre, saldo) VALUES (?, ?, ?)",
             (id_huella, USUARIO_PRUEBA, SALDO_INICIAL))
    return "REGISTRO_OK"

def pagar(id_huella):
    fila = consultar("SELECT saldo FROM usuarios WHERE id_huella = ?", (id_huella,))
    if fila is None:
        return "NO_REGISTRADO"
    if fila[0] < TARIFA:
        return "SIN_FONDOS"
    ejecutar("UPDATE usuarios SET saldo = saldo - ? WHERE id_huella = ?", (TARIFA, id_huella))
    return "PAGO_OK"

def al_conectar(cliente, userdata, flags, reason_code, properties):
    print("Conectado al Broker MQTT. Escuchando en:", TOPIC_REQ)
    cliente.subscribe(TOPIC_REQ)

def al_recibir_mensaje(cliente, userdata, mensaje):
    try:
        datos = json.loads(mensaje.payload.decode("utf-8"))
        comando = datos.get("com", "")
        dispositivo = datos.get("disp", "DESCONOCIDO")
        huella = datos.get("huella", HUELLA_PRUEBA)
        temp = float(datos.get("temp", 0.0))
        hum = float(datos.get("hum", 0.0))
    except (ValueError, TypeError, AttributeError):
        print("[ERROR] Llegó un mensaje inválido.")
        return

    print(f"\nSolicitud recibida -> Com: {comando} | Disp: {dispositivo} | Temp: {temp}°C | Hum: {hum}%")

    try:
        estado_temphum = validar_temphum(temp, hum)

        if estado_temphum != "OK":
            respuesta = estado_temphum
        elif comando == "REGISTER":
            respuesta = registrar(huella)
        elif comando == "PAY":
            respuesta = pagar(huella)
        else:
            respuesta = "COMANDO_INVALIDO"

        guardar_historial(dispositivo, buscar_ubicacion(dispositivo), comando, temp, hum, respuesta)
    except sqlite3.Error as e:
        print(f"[ERROR BD] {e}")
        respuesta = "ERROR_BD"

    cliente.publish(TOPIC_RES, MENSAJES[respuesta])
    print(f"Respuesta enviada  -> {respuesta} ({MENSAJES[respuesta]})")

inicializar_base_datos()

cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Gateway_BioPay")
cliente.on_connect = al_conectar
cliente.on_message = al_recibir_mensaje

cliente.connect(BROKER, PUERTO)
print("Gateway BioPay encendido. Esperando huellas...")
cliente.loop_forever()
