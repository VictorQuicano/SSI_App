# Escenario 3c — Reservas Besu con Llegadas Poisson (1 → 100 usuarios)

**Sistema bajo prueba:** Hyperledger Besu (QBFT) + contrato `FlightReservation`  
**Operaciones medidas:** `createReservation` → `startTrip` → `completeTrip`  
**Herramienta:** Locust 2.46.2, modo headless, `PoissonSteppedShape`  
**Fecha:** Agosto 2026  

---

## 1. Objetivo del escenario

Este escenario mide el comportamiento de la red Besu QBFT y sus contratos inteligentes bajo una carga que aproxima las condiciones de producción: usuarios que llegan de forma aleatoria e independiente, no coordinada. Se busca responder tres preguntas:

1. **¿Hasta qué nivel de concurrencia el sistema mantiene 0% de fallos y latencia predecible?**
2. **¿Qué ocurre con la latencia cuando la tasa de llegada de transacciones supera la capacidad del bloque?**
3. **¿Qué límites del sistema se hacen visibles bajo carga real que no aparecen bajo carga artificial?**

---

## 2. Diseño de la prueba

### 2.1 Modelo de llegadas: proceso de Poisson

En un sistema de transporte real, los usuarios no se coordinan para reservar simultáneamente. Cada usuario toma la decisión de reservar de forma independiente, en un momento aleatorio. Este comportamiento se modela como un proceso de Poisson: los intervalos entre llegadas consecutivas siguen una distribución exponencial.

En Locust, esto se implementa asignando a cada usuario un `wait_time` con distribución exponencial (media 3 segundos) entre ciclos:

```python
def wait_time(self):
    return random.expovariate(1.0 / 3.0)   # media = 3 s
```

El resultado práctico: después de 2–3 ciclos, los 100 usuarios están completamente desfasados entre sí. Las transacciones llegan al mempool distribuidas en el tiempo, no en ráfagas sincronizadas. El sistema experimenta una presión continua y variable, no pulsátil.

### 2.2 Escala: por qué hasta 100 usuarios

La capacidad máxima de procesamiento de la red está determinada por el gas limit del bloque:

```
TXs/bloque = gas_limit / gas_por_TX = 16,234,336 / 400,000 = 40 TXs
Velocidad   = 40 TXs / 5 s de bloque = 8 TXs/s
Trips/s     = 8 TXs/s / 3 TXs/trip = 2.67 trips/s (techo máximo)
```

Con `exponential(3)`, el tiempo de ciclo medio por usuario es ~18 s (3 TXs × 5 s + 3 s de espera). La tasa de llegada por usuario es 3/18 ≈ 0.167 TXs/s. El techo se alcanza cuando:

```
N × 0.167 TXs/s = 8 TXs/s → N ≈ 48 usuarios
```

Al ir hasta 100 usuarios se entra en la zona de saturación clara (~2× el techo), lo que permite observar cómo se degradan las métricas y qué límites del sistema se activan.

### 2.3 Estructura de carga (stepped load)

Los usuarios se acumulan en pasos, nunca se destruyen entre pasos. Esto garantiza que los eVTOLs no queden en estados intermedios entre niveles de carga.

| Paso | Usuarios | Duración | Tiempo acumulado |
|---|---|---|---|
| 1 | 1   | 180 s | 0–180 s |
| 2 | 5   | 180 s | 180–360 s |
| 3 | 10  | 180 s | 360–540 s |
| 4 | 20  | 200 s | 540–740 s |
| 5 | 30  | 200 s | 740–940 s |
| 6 | 40  | 240 s | 940–1 180 s |
| 7 | 50  | 300 s | 1 180–1 480 s |
| 8 | 70  | 300 s | 1 480–1 780 s |
| 9 | 100 | 360 s | 1 780–2 140 s |

**Duración total:** ~2 140 s (~35 min).

### 2.4 Infraestructura de prueba

**Recursos Besu** registrados exclusivamente para este escenario mediante setup previo con envío batch de TXs:

| Recurso | Detalle |
|---|---|
| eVTOLs | 100 (IDs 300–399), todos iniciando en VP1 |
| Vertiport 1 | `e3c-vp1-453090`, 50 airstrips, 200 parkings, 50 ocupados al inicio |
| Vertiport 2 | `e3c-vp2-453090`, 50 airstrips, 200 parkings, vacío al inicio |
| Cuentas Ethereum | 100 (una por eVTOL), autorizadas con `setRiderPermission(addr, True)` |

Cada usuario Locust tiene asignado un eVTOL y una cuenta Ethereum exclusivos, lo que elimina cualquier conflicto entre usuarios por el mismo recurso — los únicos recursos compartidos son la cuenta admin (nonce serializado bajo lock) y los vertiports (estado de capacidad compartido).

### 2.5 Ciclo de operación por usuario

Cada usuario ejecuta indefinidamente:

```
createReservation(tripId, rider, origin, dest, evtolId)
  → startTrip(tripId)
    → completeTrip(tripId)
      → [wait_time exponencial ~3s]
        → (invierte dirección VP1↔VP2)
          → repite
```

Todas las transacciones se envían desde la cuenta admin (única cuenta con saldo suficiente para gas) mediante un nonce lock global — asegura que las firmas se emiten con nonces consecutivos correctos incluso con 100 usuarios concurrentes. La espera del receipt ocurre fuera del lock, por lo que no bloquea a otros usuarios.

---

## 3. Resultados

### 3.1 Métricas por nivel de carga

Las métricas de cada paso se calcularon sobre la segunda mitad del intervalo correspondiente (evitando el transitorio de rampa inicial).

| Usuarios | TXs/s (total) | Trips/s | p50 (ms) | p95 (ms) | Fallos |
|---|---|---|---|---|---|
| 1   | 0.19  | 0.063 | 5 000 | 5 100  | **0.0%** |
| 5   | 0.92  | 0.308 | 5 000 | 5 100  | **0.0%** |
| 10  | 1.81  | 0.604 | 5 000 | 5 100  | **0.0%** |
| 20  | 3.64  | 1.212 | 5 000 | 5 100  | **0.0%** |
| 30  | 5.62  | 1.874 | 5 000 | 5 100  | **0.0%** |
| 40  | 7.23  | 2.411 | 5 000 | 5 100  | **0.0%** |
| 50  | 9.31  | 3.104 | 5 000 | 5 100  | **0.0%** |
| 70  | 12.71 | 4.237 | 5 000 | 5 100  | **10.8%** |
| 100 | 3.91  | 1.302 | 5 000 | 24 292 | **36.6%** |

### 3.2 Resumen de errores del test completo

De 12 139 transacciones totales, 892 fallaron (7.35% general):

| Tipo de error | Cantidad | % de fallos |
|---|---|---|
| `createReservation` revertida on-chain | 592 | 66.4% |
| `ConnectionError` — RPC rechazó conexión | 282 | 31.6% |
| `startTrip` revertida on-chain | 18 | 2.0% |
| **Total** | **892** | **100%** |

Los fallos se concentran en los pasos de 70 y 100 usuarios. A 40 usuarios y por debajo: 0 fallos en todos los niveles.

---

## 4. Análisis

### 4.1 Zona lineal (1–50 usuarios): el sistema bajo su capacidad

En los primeros siete pasos (1 a 50 usuarios), el throughput crece de forma casi perfectamente lineal:

- 1 usuario → 0.063 trips/s
- 5 usuarios → 0.308 trips/s (×5)
- 50 usuarios → 3.104 trips/s (×49)

La pendiente es ~0.062 trips/s por usuario, equivalente a un ciclo cada ~16 s (coherente con 3 TXs × ~5 s de bloque + ~1 s de overhead de red).

**Por qué la latencia es constante a 5 000 ms:** la latencia de confirmación en Besu es, fundamentalmente, el tiempo de bloque. Una TX entra al mempool y es incluida en el siguiente bloque disponible. Con hasta 50 usuarios, la tasa de llegada (~9.3 TXs/s) no supera constantemente el techo de 8 TXs/s, por lo que la mayoría de las TXs caben en el primer bloque disponible. La variabilidad de llegadas de Poisson distribuye las TXs en el tiempo de forma que el bloque raramente está completamente lleno → latencia = 1 bloque = 5 000 ms, constante.

**Por qué 50 usuarios no produce fallos aun estando sobre el techo teórico:** el techo de 8 TXs/s es el promedio máximo sostenible. Con llegadas Poisson, la variabilidad hace que algunos intervalos de bloque reciban más TXs que el límite y otros menos. El mempool actúa como buffer de corta duración. A 50 usuarios (~9.3 TXs/s promedio, ~1.3 TXs/s sobre el techo), el exceso es lo suficientemente pequeño como para que el mempool no crezca de forma sostenida durante los 300 s del paso. La p95 permanece en 5 100 ms, lo que indica que prácticamente todas las TXs siguen entrando en el primer bloque disponible.

### 4.2 Zona de saturación temprana (70 usuarios): inicio del colapso de conexiones

A 70 usuarios, la tasa de llegada escala a ~12.7 TXs/s, un 58% por encima del techo. Aquí aparece el primer tipo de fallo: 10.8% de las transacciones fallan, pero la latencia p50 y p95 de las exitosas se mantiene en 5 000 / 5 100 ms.

**¿Por qué fallan pero los que pasan son rápidos?** A 70 usuarios, cada usuario mantiene al menos una conexión HTTP abierta al nodo Besu JSON-RPC, esperando el receipt de su TX actual. El receipt puede tardar 5–25 s (según cuántos bloques espera la TX). Con 70 conexiones activas simultáneas, el pool de conexiones del servidor RPC empieza a agotarse. Nuevas TXs que intentan conectar reciben "Connection aborted" y retornan inmediatamente (< 200 ms) — esas son las 10.8% de fallos. Las que logran conexión compiten por el mempool y muchas aún caben en el primer bloque → sus receipts llegan en 5 000 ms.

Esta es una característica del servidor HTTP de Besu, no del protocolo blockchain. El parámetro `--rpc-http-max-active-connections` (por defecto 80 en Besu) es el límite operativo.

### 4.3 Saturación severa (100 usuarios): colapso de throughput y bifurcación de latencia

A 100 usuarios se observan tres fenómenos simultáneos que definen el techo real del sistema:

**Colapso de throughput:** El throughput cae de 4.237 trips/s (70u) a 1.302 trips/s (100u), a pesar de haber 43% más usuarios. El 36.6% de las TXs no llegan al mempool (connection errors) y el 18.78% de las `createReservation` que sí llegan son revertidas. El throughput efectivo está limitado por la disponibilidad de conexiones, no por la capacidad de procesamiento de la cadena.

**Bifurcación de latencia — el indicador más importante:** La p50 se mantiene en 5 000 ms, pero la p95 salta a 24 292 ms (~5 bloques de espera). Esto refleja una distribución bimodal:
- ~36.6% de TXs: fallan en < 200 ms (connection error, devuelven inmediatamente)
- ~50% de TXs exitosas: entran al primer o segundo bloque disponible → 5 000–10 000 ms
- ~5–10% de TXs exitosas: quedan varios bloques en cola → 15 000–25 000 ms

El p50 no detecta el problema porque las fast-failures compensan numéricamente a las TXs lentas. La p95 sí lo detecta: 1 de cada 20 transacciones espera aproximadamente 5 bloques (~25 s) para confirmarse. Desde la perspectiva de un usuario real, el sistema parece funcionar (p50 ≈ 5 s) pero un porcentaje significativo de operaciones experimenta demoras de ~25 s — inaceptable para una plataforma de transporte.

**Saturación de capacidad de vertiport:** Las 592 `createReservation` revertidas tienen una causa diferente: el contrato `checkLandingAvailability(originId)` verifica que `n_free_airstrip > 0`. Con 100 usuarios viajando entre dos vertiports de 50 airstrips cada uno, en intervalos de tiempo concentrados, es posible que los 50 airstrips de un vertiport estén simultáneamente asignados a vuelos en curso. El contrato rechaza correctamente nuevas reservas cuando el aeropuerto está operando a capacidad máxima. Este no es un fallo del sistema — es la lógica de negocio funcionando como debe. En producción, el cliente debería manejar este error y reintentar cuando haya capacidad disponible.

### 4.4 Por qué el p50 engaña y el p95 no

Este resultado tiene una implicación práctica importante para el monitoreo del sistema. Si se usan la mediana (p50) o el promedio como métricas de salud del sistema, el sistema parece estable incluso a 100 usuarios (p50 = 5 000 ms). El problema sólo se hace visible en percentiles altos.

Para sistemas blockchain en producción, la métrica de SLA recomendada es el **p95 con threshold de 2 × tiempo_de_bloque** (2 × 5 s = 10 s en este caso). Si el p95 supera ese umbral, significa que las TXs están esperando más de un bloque adicional, lo cual indica inicio de congestión del mempool.

En E3c, el p95 cruza ese umbral entre 70 y 100 usuarios.

---

## 5. Límites del sistema identificados

Este escenario permitió identificar tres límites distintos, con causas y soluciones diferentes:

### Límite 1 — Pool de conexiones RPC (infra, configurable)

**Síntoma:** `ConnectionError: Remote end closed connection without response`  
**Causa:** El servidor JSON-RPC de Besu tiene un máximo de conexiones simultáneas (por defecto 80). Con 70–100 usuarios, cada uno manteniendo conexiones abiertas esperando receipts, el pool se agota.  
**Solución:** Aumentar `--rpc-http-max-active-connections` en la configuración del nodo Besu, o usar un load balancer con múltiples nodos RPC.  
**No es:** un límite del protocolo blockchain. Los nodos validadores QBFT no están involucrados.

### Límite 2 — Gas limit por bloque (protocolo, ajustable)

**Síntoma:** Latencia p95 > 10 s cuando N > 48 usuarios  
**Causa:** La red puede procesar máximo 40 TXs por bloque × 1 bloque/5 s = 8 TXs/s. Con más de ~48 usuarios (a `exponential(3)`), las TXs se encolan y esperan bloques adicionales.  
**Solución:** Reducir gas consumido por TX (optimización de contratos Solidity), reducir `blockperiodseconds` en la configuración QBFT, o agregar nodos para sharding de la carga.  
**Es:** un límite fundamental de la arquitectura QBFT de un solo shard con los contratos actuales.

### Límite 3 — Capacidad de airstrips por vertiport (dominio, diseño)

**Síntoma:** `createReservation` revertida con `checkLandingAvailability = false`  
**Causa:** Con 100 vuelos simultáneos y 50 airstrips por vertiport, el aeropuerto virtual alcanza su capacidad. El contrato rechaza reservas correctamente.  
**Solución:** Aumentar `n_airstrips` en el registro del vertiport, o modificar el modelo para que los airstrips sean temporales (solo durante despegue/aterrizaje, no durante el vuelo completo).  
**Es:** comportamiento correcto del sistema bajo carga de diseño excedida.

---

## 6. Conclusiones

1. **El sistema es estable hasta 50 usuarios concurrentes** con llegadas Poisson y `exponential(3)` de espera. En ese rango: 0 fallos, latencia p50 = 5 000 ms, p95 = 5 100 ms. El throughput máximo alcanzado sin fallos es **3.104 trips/s** (9.31 TXs/s).

2. **La degradación no es gradual sino dual.** Los dos límites (RPC pool y gas limit) actúan en el mismo rango de usuarios (70–100), produciendo un colapso combinado: throughput cae y latencia de cola se dispara simultáneamente.

3. **El p50 de latencia no sirve como alerta de saturación** en sistemas blockchain. El p95 es el indicador correcto. A 100 usuarios, el p50 permanece en 5 000 ms mientras el p95 es 24 292 ms (5× más). El umbral de alerta recomendado es p95 > 2 × tiempo_de_bloque (> 10 000 ms en esta red).

4. **Los fallos de `createReservation` por capacidad de vertiport son correctos.** El contrato rechaza reservas cuando el aeropuerto está lleno — exactamente lo que debe hacer. En producción el cliente debe manejar ese error con reintentos, no considerarlo un fallo del sistema.

5. **El límite operativo inmediato es el RPC pool, no el gas.** El pool de conexiones HTTP se agota antes de que el gas limit se convierta en el factor dominante. Es el primer cambio de configuración que se debe hacer antes de operar con más de 50 usuarios concurrentes.

6. **El throughput máximo sostenible de la red** con los contratos actuales y la configuración de nodo por defecto es de aproximadamente **2.4–3.1 trips/s** (7–9 TXs/s), alcanzable con 40–50 usuarios bajo llegadas Poisson con espera media de 3 s.
