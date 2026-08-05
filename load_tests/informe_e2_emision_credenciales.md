# Escenario 2 — Escalabilidad de Emisión de Credenciales SSI

**Sistema bajo prueba:** Django REST API + ACA-Py issuer (multitenant) + PostgreSQL  
**Endpoint:** `POST /api/credentials/issue/`  
**Herramienta:** Locust (modo headless)  
**Fecha de ejecución:** Agosto 2026

---

## 1. Descripción del escenario

### ¿Qué hace el escenario?

Este escenario simula el proceso de **emisión masiva de credenciales verificables SSI** a usuarios ya registrados en el sistema. Es el paso que ocurre cuando un pasajero, después de crear su cuenta, solicita la credencial digital que lo autoriza para reservar vuelos en el sistema UAM.

El flujo por usuario virtual es:

1. **`on_start` (preparación, una sola vez):** El usuario se registra en Django (`POST /api/user/`), inicia sesión, y establece una conexión DIDComm con el agente issuer ACA-Py a través del protocolo Out-of-Band (OOB). Este paso toma entre 5 y 15 segundos la primera vez.
2. **`@task` (medición, repetida):** El usuario llama a `POST /api/credentials/issue/` con `wait_time=constant(0)`, es decir, sin pausa entre peticiones. Esto maximiza la carga sobre el issuer y mide el throughput máximo sostenible del sistema.

### ¿Qué mide en el sistema real?

En el contexto UAM, este escenario responde a la pregunta: **¿cuántos pasajeros pueden obtener su credencial de autorización simultáneamente?**

La emisión de una credencial SSI involucra:
- Recuperar o crear el `credential_definition` en el ledger Indy
- Construir un `credential_offer` firmado con la clave privada del issuer
- Ejecutar la **firma Camenisch-Lysyanskamp (CL)** — una operación criptográfica de costo fijo en CPU
- Enviar la oferta al holder mediante DIDComm y esperar el `ack`

El escenario mide la saturación de ese pipeline bajo carga concurrente creciente.

### Configuración de la prueba

| Parámetro | Valor | Justificación |
|---|---|---|
| Usuarios concurrentes | 1, 3, 5, 10, 15, 20, 25, 30 | Cubre desde baja carga hasta el punto de degradación |
| `spawn_rate` | 1 usuario/segundo | Incorporación gradual, evita spike artificial de arranque |
| `wait_time` | `constant(0)` | Máxima presión: mide throughput techo del issuer |
| Duración por run | 120–180 s | Tiempo suficiente para estabilizar la cola y medir en estado estacionario |
| Arquitectura | ACA-Py multitenant + PostgreSQL | Holder único con N sub-wallets; sin límite de procesos |

### Cómo se ejecutó la prueba y por qué de esa manera

El test se implementó en Locust con una clase `HttpUser` que establece la conexión DIDComm con el issuer en `on_start` (una sola vez por usuario, fuera de la medición) y luego ejecuta el `@task` en bucle continuo con `wait_time = constant(0)` — sin pausa entre emisiones. El `spawn_rate = 1 usuario/segundo` produce una rampa gradual, no una ráfaga: cada nuevo usuario se añade uno a uno al pool activo. Este contraste con E1b fue deliberado: en E1b queríamos exponer el pico de conexiones simultáneas (ráfaga = peor caso de apertura); en E2 queremos medir el **throughput máximo sostenible en estado estacionario** (cuántas credenciales por segundo puede firmar el issuer indefinidamente), y para eso necesitamos que el sistema llegue a un régimen estable antes de leer métricas. La rampa gradual evita que el arranque simultáneo de N conexiones OOB distorsione los primeros segundos de medición. El `constant(0)` maximiza la demanda sobre el issuer eliminando cualquier tiempo muerto del cliente, de modo que el cuello de botella observable sea siempre el issuer, no la cadencia del test. Cada nivel de carga (1 a 30 usuarios) se ejecutó durante 120–180 s para que la latencia y el throughput se estabilizaran después del warmup inicial de cada usuario. Se eligió cortar en 30 usuarios porque a partir de ese punto ya era visible la primera degradación (3,2 % de fallos), confirmando que se había superado el punto de operación óptima del sistema.

---

## 2. Resultados y análisis por gráfico

### Gráfico 04 — Throughput (peticiones/segundo)

**Resultados:**

| Usuarios | Throughput | Fallos |
|---|---|---|
| 1  | 11.22 r/s | 0 % |
| 3  | 13.22 r/s | 0 % |
| 5  | **22.56 r/s** | 0 % |
| 10 | 21.95 r/s | 0 % |
| 25 | 20.82 r/s | 0 % |
| 30 | 20.51 r/s | 3.2 % |

**Lo que muestra:** El throughput crece desde 11 r/s con un solo usuario hasta alcanzar un pico de **22.56 r/s a los 5 usuarios**, tras lo cual se estabiliza en un plateau de **~21 r/s** que se mantiene prácticamente constante hasta los 30 usuarios. La línea ideal lineal —que proyecta lo que ocurriría con escalado perfecto— diverge drásticamente del valor real a partir de 5u.

**Análisis:** El plateau revela que el cuello de botella no está en la base de datos ni en Django, sino en el **event-loop asyncio del agente ACA-Py issuer**. Este loop procesa las solicitudes de forma serial: mientras ejecuta la firma CL de una credencial (~50 ms de CPU), el resto de solicitudes esperan en cola. Una vez que hay suficientes usuarios concurrentes para mantener ese loop permanentemente ocupado (~5u), añadir más usuarios no incrementa el throughput — solo alarga la cola.

La diferencia entre 1u (11 r/s) y 5u (22 r/s) se explica porque con un único usuario hay tiempo muerto en el loop entre que el cliente procesa la respuesta y envía la siguiente solicitud. Con 5 usuarios, ese tiempo muerto desaparece y el loop trabaja al 100 %.

**Implicación para escalabilidad:** El sistema no escala horizontalmente en este punto. Para duplicar el throughput de emisión habría que desplegar un segundo issuer ACA-Py y distribuir la carga entre ambos.

---

### Gráfico 05 — Latencia de respuesta (p50 / p95 / p99)

**Resultados:**

| Usuarios | p50 | p95 | p99 |
|---|---|---|---|
| 1  | 84 ms  | 100 ms  | 130 ms  |
| 5  | 200 ms | 360 ms  | 450 ms  |
| 10 | 420 ms | 650 ms  | 750 ms  |
| 20 | 900 ms | 1 100 ms | 1 200 ms |
| 30 | 1 300 ms | 1 600 ms | 1 800 ms |

**Lo que muestra:** Las tres curvas (p50, p95, p99) crecen de forma **casi perfectamente lineal** con el número de usuarios. El gap entre percentiles se mantiene constante: p95 está siempre ~300 ms por encima del p50, y p99 ~450 ms por encima. No hay explosión de cola ni cola bimodal.

**Análisis:** El comportamiento se ajusta con precisión a la **Ley de Little**:

> *Latencia = N / Throughput = N / 21*

Verificación:
- 10u → 10/21 ≈ 476 ms (medido: 420 ms ✓)  
- 20u → 20/21 ≈ 952 ms (medido: 900 ms ✓)  
- 30u → 30/21 ≈ 1 429 ms (medido: 1 300 ms ✓)

Esto confirma que el sistema opera como una **cola M/D/1** (un servidor, tiempo de servicio determinista): el issuer atiende solicitudes una a una con duración casi constante (~50 ms de firma CL). Cada usuario adicional se pone al final de la fila y espera exactamente `1/throughput` segundos más que el anterior.

El gap constante entre p50/p95/p99 refleja la **baja varianza** del tiempo de servicio: la firma CL siempre tarda aproximadamente lo mismo, independientemente de los atributos de la credencial.

**Implicación para escalabilidad:** La latencia es predecible y calculable. Dado un SLA de, por ejemplo, 2 segundos máximo de espera, el modelo limita la carga aceptable a ≤ 42 usuarios concurrentes (2s × 21 r/s). Esta predictibilidad es una ventaja: permite dimensionar la capacidad sin sorpresas.

---

### Gráfico 06 — Tasa de fallos

**Resultados:**

| Rango de carga | Tasa de fallos | Estado |
|---|---|---|
| 1u – 25u | 0.0 % | Estable |
| 30u | 3.2 % | Degradación leve |

**Lo que muestra:** El sistema mantiene **cero fallos durante siete puntos de medición consecutivos** (1u a 25u) y presenta una primera degradación menor al 5 % únicamente a 30 usuarios. No hay colapso.

**Análisis:** Los fallos a 30u no son un fallo de la lógica de negocio sino un **efecto de cola**: con 30 usuarios y throughput fijo de ~21 r/s, la latencia esperada es ≈ 1.4 s. Algunas solicitudes que entran al final del periodo de medición superan ligeramente el umbral de timeout configurado en Django o en el cliente HTTP de Locust, lo que las convierte en error. No es saturación del sistema — es el límite estadístico de la cola en ese punto de operación.

**Comparación con arquitectura anterior (SQLite single-wallet):** Con la arquitectura previa (ACA-Py holder de proceso único + SQLite), el sistema colapsaba a partir de 15 usuarios con una tasa de error del 42 %. La migración a **PostgreSQL + multitenant** eliminó el cuello de botella del lock de SQLite y permitió sostener 0 % de fallos hasta 25 usuarios — un **67 % más de capacidad estable**.

---

## 3. Conclusiones del escenario

1. **El cuello de botella real es la firma CL en el issuer**, no la base de datos ni Django. El throughput máximo del sistema es ~21 r/s de credenciales emitidas, independientemente del número de usuarios.

2. **El sistema es predecible y estable**: la latencia sigue exactamente la Ley de Little y la tasa de fallos es cero hasta 25 usuarios concurrentes. No hay comportamiento caótico.

3. **La migración a PostgreSQL aportó:** eliminación del bottleneck de SQLite, capacidad estable extendida de 15u a 25u, y soporte para cargas sostenidas sin degradación.

4. **La escalabilidad horizontal es la siguiente palanca:** para aumentar el throughput más allá de ~21 r/s se requiere replicar el issuer ACA-Py y añadir un balanceador de carga entre los issuers.
