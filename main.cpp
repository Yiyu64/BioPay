#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

const int PIN_BOTON_REGISTRO = 26;
const int PIN_BOTON_PAGO = 27;
const int PIN_DHT = 4;
DHT dht(PIN_DHT, DHT22);
Adafruit_SSD1306 pantalla(128, 64, &Wire, -1);

const char* nombreWiFi = "Wokwi-GUEST";
const char* servidorMQTT = "host.wokwi.internal"; 
int puertoMQTT = 1883;

WiFiClient clienteWifi;
PubSubClient conexionMQTT(clienteWifi);
const char* topicPeticiones = "biopay/request";
const char* topicRespuestas = "biopay/response";

String ultimaRta = "";
bool llegoRta = false;

enum Estado { LISTO, ESPERANDO_RTA, MOSTRANDO_RTA };
Estado estadoActual = LISTO;
unsigned long inicioTiempo = 0;

void printPantalla(String linea1, String linea2, String linea3) {
  pantalla.clearDisplay();
  pantalla.setTextColor(SSD1306_WHITE);
  pantalla.setTextSize(1);
  
  pantalla.setCursor(0, 0);  
  pantalla.println(linea1);
  
  pantalla.setCursor(0, 16); 
  pantalla.println(linea2);
  
  pantalla.setCursor(0, 32); 
  pantalla.println(linea3);
  
  pantalla.display();
}

void callback(char* tema, byte* payload, unsigned int longitud) {
  String mensajeTexto = "";
  for (int i = 0; i < longitud; i++) {
    mensajeTexto += (char)payload[i];
  }
  ultimaRta = mensajeTexto;
  llegoRta = true;
}

void conectarRed() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.begin(nombreWiFi, "", 6);
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
    }
  }
  if (!conexionMQTT.connected()) {
    conexionMQTT.setServer(servidorMQTT, puertoMQTT);
    conexionMQTT.setCallback(callback);
    if (conexionMQTT.connect("Placa_BioPay")) {
      conexionMQTT.subscribe(topicRespuestas);
    }
  }
}

void enviarSolicitud(String comando) {
  if (!conexionMQTT.connected()) {
    printPantalla("SIN CONEXION", "Pago no disponible", "");
    estadoActual = MOSTRANDO_RTA;
    inicioTiempo = millis();
    return;
  }

  printPantalla("Procesando...", "Leyendo huella...", "");
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  
  if (isnan(t) || isnan(h)) {
    printPantalla("ERROR SENSOR", "Revisar el lector", "");
    estadoActual = MOSTRANDO_RTA;
    inicioTiempo = millis();
    return;
  }

  String payload = "{\"com\":\"" + comando + "\","
                   "\"disp\":\"ESP32_01\","
                   "\"huella\":\"wokwi_sim_01\","
                   "\"temp\":" + String(t, 1) + ","
                   "\"hum\":" + String(h, 1) + "}";
  llegoRta = false;
  conexionMQTT.publish(topicPeticiones, payload.c_str());
  estadoActual = ESPERANDO_RTA;
  inicioTiempo = millis();
}

void setup() {
  Wire.begin(21, 22);
  dht.begin();
  pantalla.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  pinMode(PIN_BOTON_REGISTRO, INPUT_PULLUP);
  pinMode(PIN_BOTON_PAGO, INPUT_PULLUP);
  
  printPantalla("INICIANDO...", "Conectando red...", "");
  conectarRed();
  printPantalla("BIOPAY LISTO", "Azul: Registro", "Verde: Pagar");
}

void loop() {
  conectarRed();
  conexionMQTT.loop();

  switch (estadoActual) {
    case LISTO:
      if (digitalRead(PIN_BOTON_REGISTRO) == LOW) {
        enviarSolicitud("REGISTER");
      } 
      else if (digitalRead(PIN_BOTON_PAGO) == LOW) {
        enviarSolicitud("PAY");
      }
      break;

    case ESPERANDO_RTA:
      if (llegoRta == true) {
        printPantalla("RESULTADO:", ultimaRta, "");
        estadoActual = MOSTRANDO_RTA;
        inicioTiempo = millis();
      } 
      else if (millis() - inicioTiempo > 4000) {
        printPantalla("ERROR", "Gateway no responde", "");
        estadoActual = MOSTRANDO_RTA;
        inicioTiempo = millis();
      }
      break;

    case MOSTRANDO_RTA:
      if (millis() - inicioTiempo > 4000) { 
        printPantalla("BIOPAY LISTO", "Azul: Registro", "Verde: Pagar");
        estadoActual = LISTO;
      }
      break;
  }

  delay(50);
}
