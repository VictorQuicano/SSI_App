# agents/

Infraestructura de agentes ACA-Py y scripts de prueba del sistema SSI.

---

## Archivos

```
agents/
├── docker-compose.yml      Define los 5 contenedores ACA-Py
├── genesis/
│   └── genesis.txn         Genesis file de la VON Network local (Indy)
├── start.sh                Registra DID del issuer + levanta los 5 agentes
└── scripts/
    ├── test_all.py         Test de integración completo (4 agentes)
    └── connect_and_issue.py  Herramienta CLI: emite una credencial a un agente
```

---

## Agentes definidos

| Contenedor | Rol | Inbound | Admin |
|------------|-----|---------|-------|
| `acapy-issuer` | Emisor de credenciales | 8030 | 8031 |
| `acapy-user1` | Holder — usuario | 8040 | 8041 |
| `acapy-evtol1` | Holder — eVTOL | 8050 | 8051 |
| `acapy-vertiport1` | Holder — vertiport | 8060 | 8061 |
| `acapy-vertiport2` | Holder — vertiport | 8070 | 8071 |

---

## Arranque

```bash
# Desde SSI_App/agents/
bash start.sh
```

El script:
1. Descarga el genesis file si no existe en `genesis/`
2. Registra el DID del issuer en la VON Network (idempotente)
3. Levanta los 5 contenedores con `docker compose up -d`
4. Espera a que los 5 admin APIs respondan

Opciones:
```bash
bash start.sh --down      # baja los contenedores y borra volúmenes
bash start.sh --rebuild   # reconstruye imágenes antes de arrancar
```

---

## Scripts de prueba

### `test_all.py` — Test de integración del sistema completo

Verifica que el sistema SSI entero funciona de extremo a extremo.
Corre 4 secciones en secuencia y al final imprime un resumen.

**Cuándo usarlo:** antes de hacer cambios importantes, o para confirmar
que el sistema está operativo tras un reinicio.

**Prerequisitos:** VON Network + 5 agentes + Django corriendo.

```bash
# Desde SSI_App/
python agents/scripts/test_all.py
```

Salida esperada:

```
  SECCIÓN 1 — Flujo Django: Registro + Credencial de Usuario (user1)
  ✅ Usuario creado (id=X)
  ✅ Login OK
  ✅ Credencial emitida (cred_ex_id=XXXXXXXX...)

  SECCIÓN 2 — Credencial eVTOL → evtol1 (admin: 8051)
  ✅ cred_def_id=Utwqp5cpEATQpGZL5WSQZJ:3:CL:8:default

  SECCIÓN — Credencial Vertiport → vertiport1 (admin: 8061)
  ✅ cred_def_id=Utwqp5cpEATQpGZL5WSQZJ:3:CL:10:default

  SECCIÓN — Credencial Vertiport → vertiport2 (admin: 8071)
  ✅ cred_def_id=Utwqp5cpEATQpGZL5WSQZJ:3:CL:10:default

  RESUMEN
  user1 (Django)    2.0   ✅
  evtol1            3.0   ✅
  vertiport1        4.0   ✅
  vertiport2        4.0   ✅

  Sistema SSI operativo — todos los agentes tienen credenciales.
```

Retorna exit code `0` si todo pasa, `1` si algo falla.

---

### `connect_and_issue.py` — Herramienta CLI para emitir una credencial

Emite **una** credencial de cualquier tipo a **un** agente específico.
Muestra cada paso del proceso: invitación OOB, conexión DIDComm, schema,
credential definition, oferta y confirmación en wallet.

**Cuándo usarlo:** para depurar un agente individual, re-emitir una
credencial específica, o probar un nuevo tipo de credencial.

```bash
# Desde SSI_App/
python agents/scripts/connect_and_issue.py \
  --holder <URL_ADMIN> \
  --schema-name <NOMBRE> \
  --schema-version <VERSION> \
  --attributes '<JSON>'
```

**Ejemplos:**

```bash
# Credencial de usuario -> user1
python agents/scripts/connect_and_issue.py \
  --holder http://localhost:8041 \
  --schema-name user_credential --schema-version 2.0 \
  --attributes '{"nombres":"Ana","apellidos":"Lopez","fecha_nacimiento":"1995-05-01","can_ride":"true"}'

# Credencial eVTOL -> evtol1
python agents/scripts/connect_and_issue.py \
  --holder http://localhost:8051 \
  --schema-name evtol_credential --schema-version 3.0 \
  --attributes '{"id_puerto":"p1","state":"ACTIVE","version":"v1","name":"EVTOL-1","can_fly":"true"}'

# Credencial vertiport -> vertiport1
python agents/scripts/connect_and_issue.py \
  --holder http://localhost:8061 \
  --schema-name vertiport_credential --schema-version 4.0 \
  --attributes '{"id_vertiport":"vp1","name":"Vertiport Norte","location":"Lima","capacity":"10","state":"ACTIVE"}'

# Credencial vertiport -> vertiport2
python agents/scripts/connect_and_issue.py \
  --holder http://localhost:8071 \
  --schema-name vertiport_credential --schema-version 4.0 \
  --attributes '{"id_vertiport":"vp2","name":"Vertiport Sur","location":"Lima","capacity":"8","state":"ACTIVE"}'
```

---

## Ver instrucciones completas de arranque

`../../docs/08_como_ejecutar_prueba_ssi.md`
