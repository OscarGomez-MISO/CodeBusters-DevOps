# CodeBusters-DevOps

Microservicio de lista negra global de correos para la primera entrega de DevOps.
Implementa Python, Flask 1.1.4, SQLAlchemy, Flask-RESTful, Marshmallow,
Flask-JWT-Extended, Werkzeug y PostgreSQL. No requiere interfaz grafica.

## Desarrollo local (PowerShell)

Se recomienda Python 3.11 para este conjunto de dependencias de Flask 1.1.x.
Las versiones estan fijadas para conservar la compatibilidad del stack solicitado.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
docker compose up -d --wait
.\.venv\Scripts\python.exe -m flask init-db
.\.venv\Scripts\python.exe -m flask generate-token
.\.venv\Scripts\python.exe application.py
```

API local: http://localhost:5000. PostgreSQL requiere Docker Desktop con
contenedores Linux, o un servidor PostgreSQL existente configurado en `DATABASE_URL`.
El servidor de `application.py` es para desarrollo; Beanstalk usa su servidor WSGI.
`init-db` crea las tablas que faltan y conserva los datos existentes; no es un
sistema de migraciones para futuras modificaciones de tablas.

El token generado es un JWT Bearer reutilizable sin expiracion, como permite la
entrega. Se genera por consola y se usa en Postman; no existe un endpoint de login.
Todas las instancias deben compartir `JWT_SECRET_KEY`. Cambiar esta clave invalida
los tokens anteriores. La clave de `.env.example` es solo para desarrollo.

## Variables de entorno

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Obligatoria. URL SQLAlchemy de PostgreSQL local o RDS. |
| `JWT_SECRET_KEY` | Obligatoria. Clave privada compartida para firmar los JWT. |
| `FLASK_APP` | `application.py` para los comandos Flask. |
| `PORT` | Puerto local, por defecto `5000`. |
| `TRUST_PROXY_HEADERS` | `true` detras del proxy nginx de Beanstalk; `false` localmente. |
| `PROXY_HOPS` | Cantidad de proxies confiables para obtener la IP; `2` para ALB + nginx. |

No subir `.env` ni tokens al repositorio. Si la contrasena RDS tiene caracteres
especiales, codificarlos en la URL de conexion (percent-encoding).

## API

Los endpoints de blacklist exigen `Authorization: Bearer <token>`.

### POST /blacklists

```json
{
  "email": "person@example.com",
  "app_uuid": "4f47a63e-32d9-441b-bf25-7d14b0ca434e",
  "blocked_reason": "Spam"
}
```

`email` y `app_uuid` son obligatorios; `app_uuid` debe ser un UUID valido.
`blocked_reason` es opcional y admite hasta 255 caracteres. Se normaliza el correo
a minusculas y se eliminan espacios exteriores. La base de datos registra la IP
del cliente y la fecha UTC de creacion; estos campos no los proporciona el cliente.

Respuesta `201`:

```json
{"created": true, "message": "Email added to blacklist", "email": "person@example.com"}
```

Un correo duplicado devuelve `409` y `created: false`. Una solicitud invalida
devuelve `400`; tipo de contenido incorrecto, `415`; token ausente o invalido, `401`.

### GET /blacklists/<email>

Respuesta `200` para un correo registrado:

```json
{"email": "person@example.com", "is_blacklisted": true, "blocked_reason": "Spam"}
```

Para un correo no registrado devuelve `is_blacklisted: false` y
`blocked_reason: null`. Un correo invalido devuelve `400`.
Codificar el correo como componente de URL cuando contenga caracteres especiales.

### GET /health

Sin autenticacion. Comprueba conectividad con la base de datos: `200` con
`{"status":"ok"}` o `503` con `{"status":"unavailable"}`.
La ruta `/` ofrece el mismo chequeo.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas usan SQLite en memoria y verifican autenticacion, validaciones,
duplicados, consultas, campos de auditoria y health checks. La entrega debe
ejecutarse y validarse con PostgreSQL/RDS.

Para incluir la prueba de persistencia con el PostgreSQL local:

```powershell
$env:POSTGRES_TEST_URL = "postgresql://blacklists:local-password@localhost:5432/blacklists"
.\.venv\Scripts\python.exe -m pytest -q
```

Esta prueba crea un registro unico, comprueba su persistencia desde otra instancia
de la aplicacion y elimina solo ese registro al finalizar.

## Postman

Importar `postman/Blacklists.postman_collection.json` y
`postman/Local.postman_environment.json`. Seleccionar el ambiente y asignar
`token` al resultado de `flask generate-token`.
La coleccion incluye creacion, consulta, duplicado, correo ausente, validacion,
rechazo sin token y health check. Ejecutarla en orden; genera un correo unico
para evitar duplicados entre ejecuciones.

Para AWS crear un ambiente con `base_url` igual al dominio Beanstalk y un token
firmado con la clave del ambiente. En Postman, compartir la coleccion en el
workspace del equipo, guardar ejemplos de respuesta y publicar la documentacion.
Adjuntar su URL al documento de entrega.

## Despliegue manual en Elastic Beanstalk

1. Crear PostgreSQL en RDS. Permitir puerto 5432 desde el security group de la
   aplicacion y ubicar ambos recursos en redes con conectividad entre si.
2. Crear un ambiente Beanstalk Python 3.11, balanceado, y configurar
   `DATABASE_URL` y `JWT_SECRET_KEY` en las propiedades de entorno.
3. Empaquetar `application.py`, `app/`, `requirements.txt` y `.ebextensions/`
   directamente en la raiz del ZIP. Excluir `.env`, `.venv`, `.git` y pruebas.
   Ejecutar `.\.venv\Scripts\python.exe scripts/package.py` para generar
   `dist/blacklists.zip` con estos archivos.
4. Subir el ZIP como una version de aplicacion. `.ebextensions` configura
   `application:application`, `/health` y crea las tablas en la instancia lider.
   RDS y las variables deben estar disponibles antes del despliegue.
5. Generar un token usando la misma clave del ambiente, probar ambos endpoints
   con Postman y verificar el health check. No es necesario conectar a RDS
   desde el equipo local para generar el token.
6. Para las estrategias, ajustar Auto Scaling a minimo 3 y maximo 6 instancias.
   Desplegar nuevas versiones con una diferencia visible y ejecutar cuatro
   estrategias, por ejemplo All at once, Rolling, Rolling with additional batch
   e Immutable. Registrar instancias, validacion, tiempo, reutilizacion o
   reemplazo de instancias, capturas y hallazgos para cada estrategia.

La configuracion no fija Auto Scaling ni las politicas de despliegue: se cambian
manualmente en AWS como parte del ejercicio. Si falla `init-db`, revisar los logs
de despliegue, variables, credenciales y conectividad hacia RDS.

La confianza en cabeceras de proxy supone que el proceso WSGI solo recibe
trafico desde los proxies del ambiente. Para un ambiente de una sola instancia
con nginx y sin ALB, configurar `PROXY_HOPS=1`.

Referencia: [Desplegar Flask en Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-flask.html).

## Pendientes de la entrega

- Repositorio GitHub con el proyecto en la rama acordada.
- Aplicacion funcionando en Beanstalk con PostgreSQL/RDS y evidencia Postman.
- Documentacion Postman publicada con ejemplos reales.
- `Proyecto 1 entrega 1 - Documento.pdf` con configuracion RDS, Beanstalk,
  health checks y evidencias de las cuatro estrategias.
- Video del equipo, de maximo 10 minutos, mostrando AWS, repositorio, codigo
  y funcionamiento de la API.
