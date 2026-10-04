# CLAUDE.md — Guía Maestra de Proyecto

Este archivo define cómo Claude debe comportarse, razonar y generar código en este proyecto. Es una fuente de verdad viva: actualízala cuando cambien decisiones de arquitectura, tecnología o proceso.

---

## 🧠 Filosofía General

* **Claridad sobre inteligencia**: El código debe ser obvio, no ingenioso. Si necesita un comentario para entenderse, reescríbelo.
* **Explícito sobre implícito**: Sin magia oculta, sin dependencias globales invisibles, sin efectos secundarios sorpresa.
* **Simplicidad primero**: No over-engineerices. La arquitectura debe crecer con el problema, no anticiparlo.
* **Trabajador solitario**: Las decisiones deben estar documentadas porque no hay equipo que recuerde el contexto. Si no está escrito, no existe.
* **Deuda técnica como ciudadana de primera clase**: Nómbrala, regístrala y trátala como un ticket real, no como vergüenza.

---

## 📐 Arquitectura — Decisión por Contexto

Elige la arquitectura más simple que resuelva el problema. Usa este árbol de decisión:

```
¿Es un script / pipeline de datos / exploración?
  → Script plano + funciones puras. Sin clases innecesarias.

¿Es una API o servicio con lógica de negocio moderada?
  → Layered Architecture (routes → services → repositories → models)

¿Es un sistema con múltiples dominios, alta complejidad o necesita testabilidad extrema?
  → Clean Architecture / Hexagonal (domain / application / infrastructure / interfaces)

¿Es un sistema distribuido con equipos o servicios independientes?
  → Microservicios (pero justifícalo, no lo asumas)
```

### Reglas Universales de Arquitectura

1. **Separación de capas**: Nunca mezcles lógica de negocio con I/O (DB, HTTP, filesystem).
2. **Dependency Inversion**: Las capas internas no dependen de las externas. Usa interfaces/protocolos.
3. **Un solo lugar de verdad**: Sin duplicación de configuración, sin constantes mágicas dispersas.
4. **Módulos cohesivos**: Agrupa por dominio/feature, no por tipo técnico (`users/` no `models/controllers/views/`).
5. **Boundaries explícitos**: Define claramente qué entra y sale de cada módulo (DTOs, schemas, contratos).

### Estructura Base de Proyecto Python

```
project/
├── CLAUDE.md                  # Este archivo
├── README.md                  # Qué es, cómo correr, cómo contribuir
├── pyproject.toml             # Config unificada (deps, linting, testing)
├── .env.example               # Variables de entorno documentadas (nunca .env real)
├── Makefile                   # Comandos del día a día
├── Dockerfile
├── docker-compose.yml
│
├── src/
│   └── {project_name}/
│       ├── __init__.py
│       ├── main.py            # Entrypoint
│       ├── config.py          # Settings centralizados (pydantic-settings)
│       ├── domain/            # Entidades, value objects, interfaces (sin dependencias externas)
│       ├── application/       # Casos de uso, servicios, orquestación
│       ├── infrastructure/    # DB, APIs externas, filesystem, cache
│       └── interfaces/        # HTTP (FastAPI/Flask), CLI, workers
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── conftest.py
│
├── scripts/                   # Scripts de utilidad (migraciones, seeds, etc.)
├── docs/                      # ADRs, diagramas, decisiones
│   └── adr/                   # Architecture Decision Records
└── .github/
    └── workflows/             # CI/CD pipelines
```

---

## 🐍 Python — Estándares de Código

### Estilo y Formato

* **Formatter**: `ruff format` (o `black`). Sin discusión, sin excepciones.
* **Linter**: `ruff` con reglas estrictas (ver `pyproject.toml`).
* **Type hints**: Siempre. En funciones públicas es obligatorio. En privadas, fuertemente recomendado.
* **Docstrings**: Google style para funciones públicas. Una línea si es obvio, completo si tiene efectos secundarios.
* **Línea máxima**: 100 caracteres.

```python
# ✅ CORRECTO
def calculate_discount(price: float, rate: float) -> float:
    """Calculate the discounted price.

    Args:
        price: Original price in euros.
        rate: Discount rate between 0.0 and 1.0.

    Returns:
        Price after applying the discount.

    Raises:
        ValueError: If rate is not between 0 and 1.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"Rate must be between 0 and 1, got {rate}")
    return price * (1 - rate)

# ❌ INCORRECTO
def calc(p, r):
    return p * (1-r)
```

### Typing Avanzado

```python
from typing import TypeAlias, Protocol, runtime_checkable
from collections.abc import Sequence, Callable, AsyncIterator

# Usa TypeAlias para tipos complejos
UserId: TypeAlias = str
EventHandler: TypeAlias = Callable[[str, dict], None]

# Usa Protocol para interfaces (no ABC cuando sea posible)
@runtime_checkable
class Repository(Protocol[T]):
    def get(self, id: UserId) -> T | None: ...
    def save(self, entity: T) -> None: ...
    def delete(self, id: UserId) -> bool: ...
```

### Manejo de Errores

```python
# ✅ Errores de dominio propios, nunca strings genéricos
class DomainError(Exception):
    """Base para errores de dominio."""

class UserNotFoundError(DomainError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User '{user_id}' not found")
        self.user_id = user_id

# ✅ Captura específica, nunca except Exception genérico en producción
try:
    user = repo.get(user_id)
except UserNotFoundError:
    return Response(status=404)
except DatabaseConnectionError as e:
    logger.error("DB connection failed", exc_info=e)
    raise  # Re-raise si no puedes manejarla aquí
```

### Configuración (nunca hardcodear)

```python
# config.py — Usa pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "my-app"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str  # Requerido, sin default

    # Secrets (nunca loggear)
    api_key: str
    secret_key: str

settings = Settings()  # Singleton, importar desde aquí
```

### Gestión de Dependencias — `uv`

El gestor de paquetes es `uv` en todos los entornos. Nunca usar `pip` directamente.

```bash
# Instalar uv (una sola vez)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Iniciar proyecto
uv init my-project
uv python pin 3.11            # Fijar versión de Python

# Gestión de dependencias
uv add fastapi pydantic        # Añadir deps de producción
uv add --dev pytest ruff mypy  # Añadir deps de desarrollo
uv remove package-name         # Eliminar dependencia

# Sincronizar entorno
uv sync                        # Solo producción
uv sync --dev                  # Con dependencias de desarrollo

# Ejecutar comandos en el entorno virtual
uv run pytest
uv run python src/main.py

# Actualizar dependencias
uv lock --upgrade              # Actualiza uv.lock
uv sync                        # Aplica el lock file
```

El archivo `uv.lock` siempre se commitea al repositorio para garantizar reproducibilidad exacta entre entornos.

```toml
# pyproject.toml — sección de dependencias gestionada por uv
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.3",
    "mypy>=1.8",
    "bandit>=1.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### `pyproject.toml` Estándar

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH", "ANN", "S", "PTH"]
ignore = ["ANN101", "ANN102"]

[tool.ruff.per-file-ignores]
"tests/**" = ["S101", "ANN"]  # Permite assert y sin type hints en tests

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:"]
```

---

## 🧪 Testing — TDD y Calidad

### Filosofía de Tests

* **Test-first cuando sea posible**: Escribe el test antes que la implementación para nuevas features.
* **Pirámide de tests**: Muchos unitarios → pocos de integración → muy pocos e2e.
* **Tests como documentación**: El nombre del test debe explicar el comportamiento, no la implementación.
* **Sin lógica en tests**: Si tu test necesita un `if`, algo está mal.

### Nomenclatura

```python
# Patrón: test_{unidad}_{escenario}_{resultado_esperado}
def test_calculate_discount_with_zero_rate_returns_original_price(): ...
def test_calculate_discount_with_rate_above_one_raises_value_error(): ...
def test_user_repository_get_nonexistent_user_returns_none(): ...
```

### Estructura de un Test (AAA)

```python
import pytest
from unittest.mock import MagicMock, patch

def test_order_service_creates_order_and_sends_notification():
    # Arrange
    repo = MagicMock(spec=OrderRepository)
    notifier = MagicMock(spec=Notifier)
    service = OrderService(repo=repo, notifier=notifier)
    user = UserFactory.build()

    # Act
    order = service.create_order(user_id=user.id, items=[...])

    # Assert
    repo.save.assert_called_once()
    notifier.send.assert_called_once_with(user.email, order.id)
    assert order.status == OrderStatus.PENDING
```

### Fixtures y Factories

```python
# conftest.py
import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

class UserFactory(ModelFactory[User]):
    __model__ = User
    email = "test@example.com"

@pytest.fixture
def db_session():
    """In-memory DB session for integration tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()

@pytest.fixture
def mock_external_api(respx_mock):
    """Mock de APIs externas para evitar llamadas reales."""
    respx_mock.get("https://api.external.com/v1/data").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )
    return respx_mock
```

### Cobertura Mínima

| Capa | Cobertura mínima |
|------|-----------------|
| Domain / lógica de negocio | 95% |
| Application / servicios | 85% |
| Infrastructure / adapters | 70% |
| Interfaces / HTTP | 60% (e2e cubre el resto) |
| **Global** | **80%** |

---

## 📚 Documentación — Estándares

### Qué documentar siempre

1. **README.md**: Propósito, requisitos, cómo instalar, cómo correr, cómo testear, variables de entorno.
2. **ADRs** (`docs/adr/`): Cada decisión técnica importante con contexto, alternativas consideradas y consecuencias.
3. **Docstrings**: Todas las funciones y clases públicas.
4. **`.env.example`**: Cada variable con su descripción y valor de ejemplo.
5. **`Makefile`**: Cada target con descripción (`## Descripción`).
6. **Inline comments**: Solo para explicar el por qué, nunca el qué.

### Plantilla ADR

```markdown
# ADR-001: Título de la Decisión

**Fecha**: YYYY-MM-DD
**Estado**: Propuesta | Aceptada | Deprecada | Supersedida por ADR-XXX

## Contexto
¿Qué problema o situación fuerza esta decisión?

## Decisión
¿Qué decidimos hacer exactamente?

## Alternativas Consideradas
- **Opción A**: Descripción. Pros/Cons.
- **Opción B**: Descripción. Pros/Cons.

## Consecuencias
- ✅ Positivas: ...
- ⚠️ Negativas / trade-offs: ...
- 📋 Pendientes: ...
```

### README.md Mínimo

```markdown
# Nombre del Proyecto

> Una línea describiendo qué hace.

## Requisitos
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes)
- Docker & Docker Compose

## Instalación rápida
\`\`\`bash
uv sync --dev          # Instala dependencias y crea el venv
uv run pre-commit install
cp .env.example .env
# Edita .env con tus valores
make dev
\`\`\`

## Comandos útiles
\`\`\`bash
make test        # Correr tests
make lint        # Lint y format check
make migrate     # Aplicar migraciones
\`\`\`

## Variables de entorno
Ver `.env.example` con descripción de cada variable.

## Arquitectura
Ver `docs/adr/` para decisiones de diseño.
```

---

## 🔐 Seguridad y Secretos

### Reglas de Oro (irrompibles)

1. **NUNCA** commitear secretos. Ni en ramas de feature, ni "temporalmente".
2. **NUNCA** loggear secretos, tokens, passwords o PII.
3. **NUNCA** usar credenciales hardcodeadas, ni para testing.
4. **SIEMPRE** usar `.env` local + gestor de secretos en producción.
5. **SIEMPRE** rotar credenciales si hay sospecha de exposición.

### Gestión de Secretos por Entorno

```
Local dev   → .env (en .gitignore) + .env.example (en git, sin valores reales)
CI/CD       → Variables de entorno del runner (GitHub Actions Secrets, etc.)
Staging     → AWS Secrets Manager / GCP Secret Manager / Vault
Production  → Mismo que staging, con acceso restringido
```

### `.gitignore` Mínimo Obligatorio

```gitignore
# Secretos
.env
.env.*
!.env.example
*.pem
*.key
*.p12
secrets/

# Python
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/

# uv
.uv-cache/

# Tools
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks  # Detecta secretos antes del commit

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff --fix
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
```

### Validaciones de Seguridad en Código

```python
# ✅ Nunca loggear objetos que contengan secretos
logger.info("User login", extra={"user_id": user.id})  # SÍ
logger.info(f"User: {user}")  # NO si user tiene campos sensibles

# ✅ Sanitizar inputs siempre
from pydantic import BaseModel, validator

class CreateUserRequest(BaseModel):
    email: EmailStr  # Pydantic valida formato
    password: str

    @field_validator("password")
    @classmethod
    def password_strong_enough(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v  # Nunca loggear esto

# ✅ Timing-safe comparisons para tokens
import hmac
def verify_token(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode(), expected.encode())
```

---

## ⚙️ CI/CD — Automatización

### Pipeline Estándar (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with: { version: "latest" }
      - name: Install deps
        run: uv sync --dev
      - name: Lint
        run: uv run ruff check . && uv run ruff format --check .
      - name: Type check
        run: uv run mypy src/
      - name: Security scan
        run: uv run bandit -r src/ -ll
      - name: Test
        run: uv run pytest --cov --cov-fail-under=80
        env:
          DATABASE_URL: sqlite:///:memory:
          API_KEY: ${{ secrets.TEST_API_KEY }}
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  build:
    needs: quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t ${{ github.repository }}:${{ github.sha }} .
      - name: Security scan image
        run: docker run --rm aquasec/trivy image ${{ github.repository }}:${{ github.sha }}
```

### Makefile Estándar

```makefile
.PHONY: help install dev test lint format type-check clean migrate

## Mostrar ayuda
help:
	@grep -E '^## ' Makefile | sed 's/## //'

## Instalar dependencias de desarrollo
install:
	uv sync --dev
	uv run pre-commit install

## Correr en modo desarrollo
dev:
	uv run uvicorn src.main:app --reload --port 8000

## Ejecutar todos los tests
test:
	uv run pytest

## Solo tests unitarios (rápido)
test-unit:
	uv run pytest tests/unit/ -x

## Lint y format check
lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src/

## Formatear código
format:
	uv run ruff check --fix . && uv run ruff format .

## Verificar tipos
type-check:
	uv run mypy src/

## Escaneo de seguridad
security:
	uv run bandit -r src/ -ll && uv run pip-audit

## Limpiar artefactos
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

## Aplicar migraciones
migrate:
	uv run alembic upgrade head

## Crear nueva migración
migration:
	uv run alembic revision --autogenerate -m "$(MSG)"

## Construir imagen Docker
build:
	docker build -t $(PROJECT_NAME):latest .

## Correr con Docker Compose
up:
	docker-compose up -d

## Parar Docker Compose
down:
	docker-compose down
```

---

## 🤖 Data / AI / ML — Prácticas Específicas

### Estructura de Proyecto ML

```
ml_project/
├── data/
│   ├── raw/           # Datos originales (nunca modificar)
│   ├── processed/     # Datos procesados/limpios
│   └── external/      # Datos de fuentes externas
├── notebooks/         # Exploración (nunca código de producción aquí)
│   └── archive/       # Notebooks viejos (no borrar, archivar)
├── src/
│   ├── data/          # Scripts de ingesta y procesamiento
│   ├── features/      # Feature engineering
│   ├── models/        # Definición y entrenamiento
│   ├── evaluation/    # Métricas y evaluación
│   └── serving/       # Inference y API de modelo
├── experiments/       # Runs de MLflow / W&B
└── models/            # Modelos serializados (o referencia a registry)
```

### Reglas de Reproducibilidad

```python
# Siempre fijar seeds
import random, numpy as np, torch

def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

# Siempre registrar experimentos
import mlflow

with mlflow.start_run(run_name="experiment-name"):
    mlflow.log_params({"lr": 0.001, "batch_size": 32, "seed": 42})
    mlflow.log_metrics({"accuracy": 0.94, "f1": 0.92})
    mlflow.log_artifact("model.pkl")
```

### Versionado de Datos y Modelos

* Datos: DVC o referencias a S3/GCS con hash/versión explícita.
* Modelos: MLflow Model Registry o HuggingFace Hub con tags de versión semántica.
* Nunca guardar datasets grandes en git.
* Siempre documentar la procedencia de los datos (fuente, fecha, licencia).

### AI / LLM Apps

```python
# Prompts como constantes versionadas, nunca inline
# src/prompts/classification.py
CLASSIFY_INTENT_PROMPT = """
You are a customer service classifier.
Classify the following message into one of: {categories}

Message: {message}

Respond with only the category name.
"""

# Evaluar outputs de LLMs con tests deterministas cuando sea posible
def test_intent_classifier_returns_valid_category():
    classifier = IntentClassifier(model="gpt-4o-mini")
    result = classifier.classify("I want to cancel my subscription")
    assert result in VALID_CATEGORIES

# Manejo de rate limits y retries
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def call_llm_api(prompt: str) -> str:
    ...
```

---

## 🐳 DevOps / Infraestructura

### Docker Estándar

```dockerfile
# Dockerfile — Multi-stage, mínimo y seguro
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.11-slim AS runtime
# Usuario no-root (seguridad)
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

COPY --from=builder /app/.venv .venv
COPY src/ src/

# Sin secretos en la imagen
ENV PATH="/home/app/.venv/bin:$PATH"
ENV PORT=8000
EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:$PORT/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Infrastructure as Code

* **Principio**: Todo lo que se puede romper debe poder reconstruirse desde código.
* Preferir Terraform para cloud resources. Un directorio por entorno (`envs/dev`, `envs/prod`).
* Variables sensibles via `terraform.tfvars` (en `.gitignore`) o Vault.
* Nunca `terraform apply` sin revisar `terraform plan` primero.
* Módulos reutilizables en `modules/`.

```hcl
# Siempre bloquear versiones
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "project/terraform.tfstate"
    region = "eu-west-1"
  }
}
```

### Observabilidad

Toda aplicación desplegada debe tener desde el día 1:

```python
# 1. Health check endpoint
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": settings.app_version}

# 2. Logging estructurado (JSON en producción)
import structlog
logger = structlog.get_logger()
logger.info("order_created", order_id=order.id, user_id=user.id, amount=order.total)

# 3. Métricas (Prometheus)
from prometheus_client import Counter, Histogram
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency")

# 4. Tracing (OpenTelemetry)
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("process_order"):
    ...
```

---

## 🚀 Flujo de Trabajo con Claude

### Flujo de trabajo con git (obligatorio, antes que nada)

* **Siempre que vayas a hacer cambios, crea primero una rama nueva** (`git checkout -b
  <tipo>/<descripción-corta>`) y haz **todos** los cambios ahí. **Nunca** trabajes ni
  commitees directamente sobre `main` (o la rama principal).
* Antes de editar nada, comprueba la rama actual; si es la principal, crea la rama primero.
* Al terminar, commitea en la rama; el **merge a `main` lo decide el usuario** (por defecto
  `git merge --ff-only`). **No hagas push** salvo que se pida explícitamente.

### Al Iniciar un Proyecto Nuevo

Claude debe hacer en orden:

1. Leer este `CLAUDE.md` completo.
2. Preguntar: ¿cuál es el contexto de negocio? ¿Quién lo usa? ¿Cuál es el éxito?
3. Proponer estructura de directorios antes de escribir código.
4. Crear `pyproject.toml` con todas las herramientas configuradas.
5. Crear `Makefile` con los comandos del día a día.
6. Crear `.env.example` con todas las variables necesarias.
7. Crear `README.md` inicial.
8. Solo entonces: escribir código de negocio.

### Al Agregar una Feature

1. Escribir el test primero (o al menos simultáneamente).
2. Implementar la lógica en la capa correcta.
3. Actualizar docstrings y README si hay cambios de interfaz.
4. Verificar que los tests pasen: `make test`.
5. Verificar lint: `make lint`.

### Al Encontrar un Bug

1. Primero escribir un test que reproduce el bug.
2. Luego corregir la implementación.
3. Verificar que el test pase y no haya regresiones.
4. Si el bug existía en producción, documentar en el commit qué pasó.

### Cómo Claude debe responder

* Siempre generar código con type hints completos.
* Siempre incluir tests para código nuevo no trivial.
* Siempre seguir la estructura de directorios definida aquí.
* Nunca usar `Any` sin justificación explícita.
* Nunca dejar credenciales o secretos hardcodeados, ni como ejemplo.
* Nunca generar código sin manejo de errores apropiado.
* Preferir soluciones simples sobre ingeniosas.
* Preguntar si el requisito no está claro antes de asumir.

---

## 📋 Checklist de PR / Entrega

Antes de considerar cualquier cambio "listo":

- [ ] Tests escritos y pasando (`make test`)
- [ ] Cobertura no bajó del umbral (`--cov-fail-under=80`)
- [ ] Lint sin errores (`make lint`)
- [ ] Type check sin errores (`make type-check`)
- [ ] Sin secretos hardcodeados (`gitleaks detect`)
- [ ] Docstrings en funciones/clases públicas nuevas
- [ ] `.env.example` actualizado si hay nuevas variables
- [ ] README actualizado si cambió la interfaz o instalación
- [ ] ADR creado si se tomó una decisión arquitectónica relevante

---

*Última actualización: 2025-04. Actualizar este archivo con cada decisión arquitectónica importante.*
