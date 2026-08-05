# Escenario 3 — Throughput de Reservas de Vuelo en Besu (QBFT)

**Sistema bajo prueba:** Hyperledger Besu (QBFT) + FlightReservation smart contract  
**Operaciones medidas:** `createReservation` → `startTrip` → `completeTrip`  
**Herramienta:** Locust (modo headless, tipo `User` personalizado con eventos ETH)  
**Fecha de ejecución:** Agosto 2026

---

## 1. Descripción del escenario

### ¿Qué hace el escenario?

Este escenario mide la capacidad de la red Besu para procesar el **ciclo completo de un viaje eVTOL** bajo carga concurrente. Cada usuario virtual ejecuta indefinidamente:

1. `createReservation(tripId, rider, VP_origen, VP_destino, evtolId, ...)` — crea la reserva y asigna el eVTOL (estado PARKED → EXPECTING)
2. `startTrip(tripId, ...)` — inicia el vuelo (EXPECTING → IN_USE), libera un parking en el vertiport origen
3. `completeTrip(tripId, ...)` — completa el viaje (IN_USE → PARKED en VP destino), ocupa un parking en el vertiport destino
4. Espera 1–2 s, repite en dirección opuesta (VP1↔VP2 alternando)

### Diseño de concurrencia

| Elemento | Decisión de diseño | Justificación |
|---|---|---|
| **Firmante único (admin key)** | Todas las TXs las firma la misma cuenta Besu | Replica fielmente al backend Django, que actúa como único orquestador on-chain |
| **Nonce serializado (`gevent.lock.Semaphore`)** | Solo un usuario puede obtener nonce + enviar TX a la vez | Evita huecos de nonce que bloquearían el mempool |
| **Receipt wait fuera del lock** | Todos los usuarios esperan sus recibos en paralelo | Maximiza el overlap: múltiples TXs pueden estar en vuelo simultáneamente |
| **eVTOLs independientes** | Cada usuario virtual tiene su propio eVTOL (IDs 90–99) | Elimina contención de estado de eVTOL; mide el cuello de botella de la red |

### Configuración de la prueba

| Parámetro | Valor |
|---|---|
| Usuarios concurrentes | 1, 3, 5, 7, 10 |
| `spawn_rate` | 1 usuario/segundo |
| `wait_time` | `between(1, 2)` segundos entre ciclos |
| Duración por sub-test | 120–240 s (escalado con usuarios) |
| Red Besu | QBFT, 4 validadores + 1 nodo RPC, tiempo de bloque ~1 s |
| Contratos | FlightReservation → UserVerification, VertiportManagement, EVTOLManagement |

---

## 2. Hallazgo crítico: artefacto del batch

### El problema

Los sub-tests se ejecutan en batch **sin limpieza de estado entre corridas**. Cuando Locust termina un sub-test (por `--run-time`), las transacciones que estaban en vuelo siguen siendo minadas por la red Besu. Esto deja eVTOLs en estados intermedios:

- **EXPECTING**: `createReservation` se confirmó pero `startTrip` no llegó a ejecutarse (Locust ya había cerrado).
- **IN_USE**: `startTrip` se confirmó pero `completeTrip` no se ejecutó.

En el sub-test siguiente, los mismos eVTOLs (asignados por índice secuencial) están bloqueados. `isAvailable(evtolId)` devuelve `false` → `createReservation` revierte con "EVTOL no disponible".

**Inspección on-chain al finalizar el batch:**

| eVTOL | Estado final | Causa |
|---|---|---|
| 90 | EXPECTING | Stuck al final del sub-test u=10 |
| 91 | EXPECTING | Stuck al final del sub-test u=10 |
| 92 | EXPECTING | Stuck al final del sub-test u=10 |
| 93 | EXPECTING | Stuck al final del sub-test u=7 o u=10 |
| 94–98 | PARKED | Limpios ✓ |
| 99 | IN_USE | Stuck (startTrip sin completeTrip) |

**Conclusión**: Los fallos de `createReservation` al 43–66% en los sub-tests u=3 a u=10 son un **artefacto del diseño del batch**, no una limitación del sistema. El único punto de datos limpio (sin contaminación de estado previo) es **u=1** con **0% de fallos**.

---

## 3. Resultados y análisis por gráfico

### Gráfico 07 — Throughput por operación

**Datos:**

| Usuarios | createRes. (total) | createRes. (éxitos) | startTrip | completeTrip | Fallos createRes. |
|---|---|---|---|---|---|
| 1  | 0.07 r/s | 0.07 r/s | 0.07 r/s | 0.07 r/s | 0% |
| 3  | 0.34 r/s | 0.14 r/s | 0.14 r/s | 0.13 r/s | 60% |
| 5  | 0.61 r/s | 0.21 r/s | 0.21 r/s | 0.19 r/s | 66% |
| 7  | 0.74 r/s | 0.34 r/s | 0.33 r/s | 0.33 r/s | 55% |
| 10 | 0.94 r/s | 0.54 r/s | 0.53 r/s | 0.51 r/s | 43% |

**Lo que muestra:** El throughput de `startTrip` y `completeTrip` (operaciones sin fallo) crece de forma **sub-lineal** con el número de usuarios: de 0.07 r/s con 1 usuario hasta 0.51 r/s con 10 usuarios (×7.3, no ×10). La línea ideal lineal diverge a partir de 5u.

**Análisis — Cuello de botella: serialización de nonce**

Toda la actividad on-chain pasa por una única cuenta Ethereum (admin key). El nonce debe ser estrictamente incremental, lo que fuerza la **serialización de la fase de envío**. Aunque múltiples TXs pueden estar esperando su recibo en paralelo (la espera está fuera del lock), el envío es serial.

El throughput efectivo de viajes completos está acotado por:

> *throughput ≤ capacidad_bloque / tiempo_bloque*

En QBFT con tiempo de bloque de ~1 s y capacidad de bloque suficiente, la red puede procesar múltiples TXs por bloque. La sub-linealidad refleja que:

1. **El tiempo de ciclo total es largo** (~15 s por trip completo = createRes.+start+complete+wait), por lo que 10 usuarios no generan 10× la demanda de manera uniforme.
2. **El overhead de la espera de receipt** (polling del nodo RPC) introduce latencia extra.

La siguiente palanca de escalabilidad sería usar **múltiples cuentas admin** (firmantes paralelos), cada una con su propio rango de nonces, eliminando la contención del semáforo.

---

### Gráfico 08 — Latencia por operación (u=1, línea de base limpia)

**Datos (percentiles de u=1, 0% fallos):**

| Operación | p50 | p95 | p99 |
|---|---|---|---|
| `createReservation` | 3 700 ms | 3 900 ms | 3 900 ms |
| `startTrip` | 5 000 ms | 5 000 ms | 5 000 ms |
| `completeTrip` | 5 000 ms | 5 000 ms | 5 100 ms |

**Lo que muestra:** La latencia es **determinista y de baja varianza** (p50 ≈ p95 ≈ p99). `createReservation` es más rápida (~3.7 s) que `startTrip` y `completeTrip` (~5 s).

**Análisis — Block time como piso de latencia**

En QBFT la única fuente de latencia es el tiempo entre que una TX se envía y su bloque se finaliza. La diferencia entre las operaciones:

- `createReservation` se envía en estado "vacío" (sin TX previa en vuelo): el nodo puede incluirla en el siguiente bloque casi inmediatamente. Tiempo observado: **3.7 s** (~3–4 ciclos de bloque a ~1 s).
- `startTrip` y `completeTrip` se envían justo después de recibir el receipt de la TX anterior. Eso los posiciona ligeramente después del inicio del ciclo de bloque actual, obligándolos a esperar el siguiente bloque completo. Tiempo observado: **5.0 s** (~5 ciclos de bloque).

La baja varianza (p99 - p50 < 200 ms) confirma que el sistema opera sin cola: con 1 usuario no hay espera; el único determinante es el protocolo de consenso.

**Implicación para SLAs:** Un ciclo completo de reserva (crear + iniciar + completar) tarda **~14 s** en condiciones sin carga. Para aplicaciones donde el usuario espera confirmación en tiempo real, esto sería inaceptable en producción; se requeriría un modelo de optimistic response (responder al usuario inmediatamente con confirmación off-chain y confirmar on-chain en segundo plano).

---

### Gráfico 09 — Análisis de fallos (createReservation)

**Lo que muestra:** La tasa de fallo de `createReservation` oscila entre 43% y 66% para u=3–10, mientras que con u=1 es del 0%. En contradicción aparente: más usuarios → porcentaje de fallo variable, no monótonamente creciente.

**Análisis — Artefacto del batch (no una limitación del sistema)**

La tabla muestra los eVTOLs bloqueados *al inicio* de cada sub-test:

| Sub-test | eVTOLs activos | eVTOLs bloqueados al inicio | % base de fallos |
|---|---|---|---|
| u=1  | 1  | 0 | 0% |
| u=3  | 3  | 1 (de u=1) | ~33% base |
| u=5  | 5  | ~4 (acumulados) | ~80% base |
| u=7  | 7  | ~6 | ~86% base |
| u=10 | 10 | ~5 | ~50% base |

Con eVTOLs bloqueados, esos usuarios *fallan inmediatamente en cada intento* de `createReservation` (revert instantáneo ~326–400 ms), mientras los usuarios con eVTOLs limpios completan ciclos largos (~15 s). El porcentaje de fallo resultante depende de la proporción de tiempo que los usuarios bloqueados pasan intentando (ciclos rápidos de fallo) vs. los usuarios limpios completando ciclos lentos.

**`startTrip` y `completeTrip` mantienen 0% de fallo** en todos los sub-tests: una vez que `createReservation` tiene éxito (eVTOL limpio, viaje creado), el resto del ciclo siempre se completa correctamente. Esto confirma que el contrato y la red funcionan bien; el fallo es exclusivamente en la disponibilidad del eVTOL.

---

## 4. Conclusiones del escenario

1. **El sistema funciona correctamente con 0% de fallos** cuando el estado está limpio (u=1, u=1 es el único punto sin contaminación). Todas las operaciones del ciclo de viaje se completan y los contratos de estado (eVTOL, vertiport, FlightReservation) son consistentes.

2. **El cuello de botella de escalabilidad es la serialización del nonce admin**. Un único firmante (admin key) limita el throughput de viajes a ~0.5 trips/s con 10 usuarios. La solución de escalabilidad es usar **múltiples cuentas admin**, cada una firmando un subconjunto de viajes en paralelo.

3. **La latencia por operación es determinista y baja en varianza** (~3.7 s para `createReservation`, ~5.0 s para `startTrip`/`completeTrip`), dominada por el tiempo de bloque QBFT. Es predecible y calculable para cualquier volumen de carga.

4. **Los fallos de createReservation son un artefacto del diseño del batch**, no del sistema. Para una medición válida de escalabilidad se requiere:
   - Limpiar el estado de todos los eVTOLs entre sub-tests (completar trips pendientes), o
   - Usar vertiports y eVTOLs distintos para cada sub-test, o
   - Diseñar el load test con reintentos inteligentes que detecten eVTOLs bloqueados.

5. **El throughput escala razonablemente** con usuarios limpios: de 0.07 a 0.51 trips/s (×7.3 con ×10 usuarios). La sub-linealidad se debe principalmente al tiempo de ciclo largo (~15 s/trip) que distribuye la carga de forma no uniforme en el tiempo.

---

## 5. Trabajo futuro recomendado

- **Re-ejecutar E3 con limpieza entre sub-tests**: añadir una fase de cleanup (llamar `startTrip`+`completeTrip` para eVTOLs en EXPECTING, y `completeTrip` para los IN_USE) antes de cada sub-test.
- **Probar hasta 50u con estado limpio**: verificar si el throughput satura antes de ×10u (predecible por la serialización de nonce) o si hay otros cuellos de botella.
- **Medir el impacto de múltiples cuentas admin**: ¿cuánto throughput adicional se obtiene con 2 o 3 firmantes paralelos?
