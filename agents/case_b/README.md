# Entorno aislado del caso B

Este Compose crea un issuer y un holder ACA-Py con PostgreSQL propio. No reutiliza las wallets ni la base de datos de los agentes principales.

Puertos:

| Componente | Inbound | Admin |
|---|---:|---:|
| Issuer | 8130 | 8131 |
| Holder | 8140 | 8141 |
| PostgreSQL | — | 55432 |

Requiere que VON Indy ya esté disponible en `http://localhost:9000` y que `../genesis/genesis.txn` corresponda a esa red.

## Ejecución del experimento B

El ejecutor usa el schema actual `user_credential:2.0`, crea la credencial
`can_ride=false` si aún no está en el holder y conserva todas las ejecuciones.

```bash
cd SSI_App/agents/case_b
python3 run_case_b.py --runs 3
python3 run_case_b.py --runs 30 --cases B1,B2,B3,B5,B6
```

Cada ejecución crea `results/<UTC>/` con:

- `metadata.json`: identificadores reales del schema y credential definition,
  configuración y límites del entorno;
- `results.csv` y `results.json`: una fila por repetición;
- `summary.json`: conteos y medianas de generación y verificación.

`B1` y `B3` muestran una presentación que revela solo `can_ride`; los otros
tres atributos quedan ocultos por la prueba CL. El atributo actual es texto,
por lo que no expresa un predicado booleano ZK sin revelar su valor. `B2`
separa prueba criptográfica válida de autorización de la política. `B5` y
`B6` miden el rechazo cuando el holder no encuentra una credencial compatible.

La credential definition creada para esta campaña no tiene revocación: `B7`
y `B8` requieren una credential definition revocable y un servidor de tails.
`B4` requiere introducir una prueba manipulada antes de invocar el verificador
AnonCreds, una operación que la API Admin de ACA-Py no expone; se debe ejecutar
con un harness de bajo nivel separado.
