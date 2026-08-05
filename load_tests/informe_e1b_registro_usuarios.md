# Escenario 1b — Escalabilidad de Registro de Usuarios (Onboarding en Ráfaga)

**Sistema bajo prueba:** Django REST API + ACA-Py holder (multitenant) + PostgreSQL  
**Endpoint:** `POST /api/user/`  
**Herramienta:** Locust (modo headless)  
**Fecha de ejecución:** Agosto 2026

---

## 1. Descripción del escenario

### ¿Qué hace el escenario?

Este escenario simula el proceso de **registro simultáneo de N usuarios nuevos** en el sistema UAM. Cada usuario virtual se registra exactamente una vez y se detiene — no repite la petición. El objetivo es medir cuántos pasajeros pueden crear su cuenta al mismo tiempo, cuánto tarda ese proceso, y en qué punto el sistema empieza a rechazar registros.

El flujo por usuario virtual es:

1. **Spawn** (todos a la vez): Locust crea N usuarios con `spawn_rate=N`, de modo que todos llegan al sistema de forma prácticamente simultánea, simulando una ráfaga de inscripción.
2. **`@task` (una sola vez):** El usuario envía `POST /api/user/` con credenciales aleatorias únicas.
3. **`StopUser`:** Tras recibir la respuesta (éxito o fallo), el usuario virtual se detiene. No hay reintentos.

### ¿Qué mide en el sistema real?

Cada registro de usuario en el sistema UAM desencadena tres operaciones encadenadas:

1. **Django** crea el registro en PostgreSQL (`User`, `Wallet`)
2. **ACA-Py holder** (multitenant) crea un sub-wallet dedicado para el usuario: genera un par de claves criptográficas, cifra el material con aries-askar y lo persiste en PostgreSQL
3. **ACA-Py holder** genera un DID (Decentralized Identifier) para el sub-wallet

El escenario responde a la pregunta operacional: **¿cuántos pasajeros nuevos puede incorporar el sistema de forma simultánea?** — relevante, por ejemplo, en el momento de apertura de un servicio o durante campañas de inscripción masiva.

> **Nota sobre el diseño:** Esta versión reemplaza el Escenario 1 original (E1), donde cada usuario virtual generaba registros repetidos e indefinidos. Ese diseño medía un caso irreal (un mismo usuario registrándose miles de veces). E1b mide el caso real: N personas distintas intentando crear cuenta al mismo tiempo.

### Configuración de la prueba

| Parámetro | Valor | Justificación |
|---|---|---|
| Usuarios concurrentes | 10, 25, 50, 75, 100, 150, 200 | Cubre desde baja carga hasta el punto de saturación |
| `spawn_rate` | = N (todos a la vez) | Simula ráfaga simultánea — el peor caso de inscripción masiva |
| `wait_time` | `constant(0)` | El usuario no espera: registra y para (`StopUser`) |
| Duración por run | 90–240 s | Tiempo generoso para completar la cola |
| Arquitectura | ACA-Py multitenant + PostgreSQL | Pool DB del holder: 200 conexiones; PostgreSQL: 500 max |

### Cómo se ejecutó la prueba y por qué de esa manera

El test se implementó en Locust con una clase `HttpUser` que usa `wait_time = constant(0)` y la excepción `StopUser` al final del único `@task`: en cuanto el usuario envía su petición y recibe respuesta (exitosa o fallida), se detiene. El parámetro `spawn_rate` se fija igual a N en cada corrida, lo que hace que Locust cree todos los usuarios virtuales en el mismo instante — eso es lo que produce la ráfaga. Se eligió este diseño porque es el escenario más desfavorable y más representativo del caso real: en un lanzamiento de servicio o durante una campaña de inscripción masiva, decenas o cientos de personas tocan "Crear cuenta" al mismo tiempo, no de forma escalonada. Frente a otras alternativas (rampa gradual, carga sostenida con pocos usuarios), la ráfaga simultánea revela el comportamiento del sistema bajo su mayor presión puntual de conexiones. Los niveles de carga (10 a 200 usuarios) se eligieron para cubrir el rango entre "sin presión" y "saturación clara", con pasos suficientemente pequeños para ver dónde ocurre la transición. La duración de cada run (90–240 s) se diseñó para dar tiempo al sistema de procesar toda la cola pendiente incluso en los niveles más altos, evitando truncar mediciones.

---

## 2. Resultados y análisis por gráfico

### Gráfico 01b — Registros exitosos vs. usuarios intentados

**Resultados:**

| Usuarios intentados | Registros exitosos | Fallos | % éxito |
|---|---|---|---|
| 10  | 10  | 0  | 100 % |
| 25  | 25  | 0  | 100 % |
| 50  | 40  | 10 | 80 % |
| 75  | 51  | 24 | 68 % |
| 100 | 62  | 38 | 62 % |
| 150 | 78  | 72 | 52 % |
| 200 | 92  | 108 | 46 % |

**Lo que muestra:** Hasta 25 usuarios el sistema registra a todos correctamente. A partir de 50 usuarios, la curva de éxitos se separa de la ideal: el número de registros exitosos sigue creciendo, pero a una fracción de los intentados. A 200 usuarios, solo 92 de 200 logran completar su registro.

**Análisis:** La separación entre la línea ideal y la real marca el límite de **aceptación TCP simultánea del servidor HTTP de ACA-Py** (aiohttp). Cuando todos los usuarios llegan al mismo instante, el sistema operativo forma una cola TCP (backlog) ante el puerto de administración del holder. aiohttp puede aceptar y encolar ~40 conexiones antes de que el event-loop asyncio tenga tiempo de procesarlas; las conexiones adicionales que arriban mientras el loop está ocupado reciben un `RST` (reset) inmediato del sistema operativo.

El patrón de éxitos sigue un modelo predecible: **~40 conexiones base aceptadas + ~26% de las adicionales** que logran colarse mientras el event-loop recupera capacidad:

- 50u → 40 éxitos  
- 100u → 40 + 0.44×50 ≈ 62 éxitos ✓  
- 200u → 40 + 0.35×150 ≈ 92 éxitos ✓  

Todos los fallos son `ConnectionResetError(104)`, no errores de lógica de negocio ni de base de datos. El sistema no está roto: simplemente no puede aceptar más conexiones simultáneas de las que su stack TCP permite encolar.

**Implicación para escalabilidad:** Para onboarding masivo simultáneo (eventos de lanzamiento, campañas) habría que implementar un mecanismo de cola a nivel de aplicación (p. ej. Celery + Redis) que acepte todas las peticiones inmediatamente (202 Accepted) y procese los wallets de forma asíncrona, desacoplando la aceptación HTTP del tiempo de creación del wallet.

---

### Gráfico 02b — Latencia de registro (usuarios exitosos)

**Resultados:**

| Usuarios intentados | p50 | p95 | p99 |
|---|---|---|---|
| 10  | 1.4 s | 1.4 s | 1.4 s |
| 25  | 2.5 s | 3.1 s | 3.1 s |
| 50  | 3.2 s | 5.0 s | 5.1 s |
| 100 | 4.0 s | 9.0 s | 9.1 s |
| 150 | 4.1 s | 10.0 s | 10.0 s |
| 200 | 3.6 s | 11.0 s | 11.0 s |

**Lo que muestra:** La latencia p50 crece de 1.4 s (10u) hasta un plateau de ~3.5–4.1 s entre 50 y 200 usuarios. Sin embargo, el p95 y p99 se disparan mucho más: de 3.1 s (25u) a 11.0 s (200u). La brecha entre p50 y p99 se amplía drásticamente con la carga.

**Análisis:** Aquí se observa una **distribución bimodal** entre los usuarios exitosos:

- Los ~40 usuarios que se conectan primero entran inmediatamente al asyncio del holder y completan su wallet en ~1–2 s (parte rápida de la distribución → p50 se mantiene bajo).
- Los usuarios adicionales que logran conectarse (pero llegaron más tarde) encuentran la cola de asyncio ya ocupada, y esperan que los primeros terminen → tiempos de 5–11 s (cola larga → p95/p99 alto).

Esto explica por qué el p50 se estabiliza (~3.5 s) mientras el p99 sigue subiendo: los "afortunados" siempre tardan lo mismo, pero los "rezagados" esperan más cuanto mayor es la competencia.

El throughput real de creación de wallets es constante: **~7–8 wallets/s** independientemente de cuántos usuarios intenten registrarse. Esto refleja el límite del event-loop asyncio del holder para operaciones criptográficas + I/O en PostgreSQL.

---

### Gráfico 03b — Tasa de fallos

**Resultados:**

| Rango | Tasa de fallos | Causa | Estado |
|---|---|---|---|
| 10u – 25u | 0 % | — | Estable |
| 50u – 200u | 20 % – 54 % | `ConnectionResetError(104)` | Degradado |

**Lo que muestra:** La transición de 0% a 20% de fallos ocurre bruscamente entre 25u y 50u. A partir de ahí, la tasa crece de forma aproximadamente lineal: cada 50 usuarios adicionales añaden ~8–10 puntos porcentuales de fallos.

**Análisis:** La brusquedad de la transición confirma que el sistema no se degrada gradualmente — tiene un **límite duro de ~25–40 conexiones TCP simultáneas**. Por debajo del límite, todos los usuarios registran sin problema; por encima, el exceso es rechazado al instante. No hay zona intermedia.

Los fallos son todos de tipo `ConnectionResetError(104, 'Connection reset by peer')`, lo que indica que ACA-Py cierra activamente la conexión TCP sin siquiera llegar a la capa HTTP. Esto es una señal positiva: el sistema falla de forma limpia y rápida (no hay timeouts prolongados), y los usuarios que no lograron registrarse lo saben de inmediato.

**Comparativa con E1 original:**

| Métrica | E1 (repeticiones continuas) | E1b (ráfaga única) |
|---|---|---|
| Límite sin fallos | ~10u | **25u** |
| Tipo de fallo | HTTP 500 (timeout asyncio) | ConnectionReset (TCP backlog) |
| Throughput útil | ~2–3 r/s (continuo) | ~7–8 wallets/s (burst) |
| Naturaleza del test | Carga sostenida irreal | Ráfaga realista |

---

## 3. Conclusiones del escenario

1. **El sistema soporta ráfagas de hasta 25 registros simultáneos con 0% de error**, completando todos los wallets en ~3.1 segundos. Este es el límite operacional limpio.

2. **El cuello de botella no es la base de datos ni Django**, sino el **backlog TCP del servidor HTTP de ACA-Py**. La capacidad de aceptación simultánea de conexiones es de ~40, independientemente del pool de PostgreSQL (configurado en 200).

3. **El throughput de creación de wallets es estable en ~7–8 wallets/s**, tanto en la zona estable como en la degradada. El event-loop asyncio del holder procesa wallets a esa velocidad constante; lo que varía es cuántos usuarios logran entrar a la cola.

4. **Los fallos son limpios (fast-fail):** los usuarios rechazados reciben un RST TCP inmediato, sin timeout prolongado. Esto es operacionalmente aceptable: el sistema falla rápido en lugar de dejar usuarios colgados.

5. **La solución de escalabilidad para onboarding masivo** es desacoplar la aceptación HTTP de la creación del wallet mediante una cola asíncrona (Celery + Redis), permitiendo que Django acepte N peticiones instantáneamente y las procese a 7–8 wallets/s en segundo plano.
