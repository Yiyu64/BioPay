# BioPay

## Estructura del Proyecto
main.cpp: Código en C++ para la placa ESP32 (máquina de estados, pantalla OLED, botones y sensor de temperatura y humedad).
gateway.py: Servidor en Python que escucha al broker MQTT, valida las lecturas, procesa los pagos y gestiona la base de datos.
diagram.json: Diagrama del circuito en Wokwi.
biopay.db: Base de datos SQLite que almacena ubicaciones, dispositivos, usuarios simulados e historial.

## Ejecucion
1. Ejecutar Start-Service Mosquitto
2. Ejecutar python gateway.py
3. Iniciar la simulación en Wokwi.
4. Ejecutar python dashboard.py y abrir en la web
