## Purpose

为 CampusClaw 规定可重复启动、可部署验证的服务运行契约，使开发和验收环境能够通过 Docker Compose 启动应用，并用健康检查确认服务可用。

## ADDED Requirements

### Requirement: Docker Compose startup

The system SHALL provide a Docker Compose configuration that starts a frontend service, a Flask API service, and a PostgreSQL service using documented server-side environment configuration. The Compose project SHALL expose exactly the three course-practice ports: frontend `5173`, API `8080`, and PostgreSQL `5432`.

#### Scenario: Clean environment starts the stack

- **WHEN** an operator supplies the required environment configuration and runs the documented Docker Compose startup command
- **THEN** the frontend, API, and PostgreSQL services start without requiring manual in-container setup, initialize the PostgreSQL schema/seed mode according to configuration, and expose the documented login entry point at the frontend port

#### Scenario: Runtime data persists across restart

- **WHEN** an operator stops and restarts the Compose stack without deleting its database and upload volumes
- **THEN** the preset class/user data and previously accepted material and knowledge-base records remain queryable after PostgreSQL and upload volumes are reused

#### Scenario: Three service ports have distinct responsibilities

- **WHEN** the Compose stack is running
- **THEN** port `5173` serves browser pages, port `8080` serves the Flask API and `GET /health`, and port `5432` accepts PostgreSQL connections; the services do not substitute SQLite or an unlisted database port

### Requirement: Health endpoint

The Flask API SHALL provide `GET /health` on port `8080` as a lightweight health endpoint that returns HTTP 200 when the API, PostgreSQL connection, and required upload storage are ready to serve requests.

#### Scenario: Healthy application responds

- **WHEN** a running API receives `GET /health` on port `8080`
- **THEN** it returns HTTP 200 with a machine-readable response indicating the service is healthy, without requiring authentication or redirecting to the login page

#### Scenario: Application dependency is unavailable

- **WHEN** a required dependency prevents the application from serving requests normally
- **THEN** the health endpoint does not report a healthy HTTP 200 state

### Requirement: Server-only environment secrets

The system SHALL read required application secrets and PostgreSQL connection settings from server-side environment variables or equivalent server-only runtime configuration and SHALL keep those values out of the repository and client-visible responses.

#### Scenario: Application starts with configured secret

- **WHEN** the required secret is provided through the server runtime environment
- **THEN** the application can use the secret without embedding it in source-controlled files or frontend assets

#### Scenario: Secret configuration is missing

- **WHEN** a required secret is absent from the server runtime environment
- **THEN** startup or the dependent operation fails explicitly rather than falling back to a hard-coded or plaintext secret

### Requirement: Documented local runtime artifacts

The system SHALL document the required environment variables and Compose startup flow, and SHALL provide the runtime artifacts needed by that flow, including frontend/API images, `docker-compose.yml`, PostgreSQL volume configuration, and an `.env.example` containing placeholders rather than real secrets.

#### Scenario: Operator follows the documented startup flow

- **WHEN** an operator copies `.env.example` to the runtime environment, supplies a secret, and runs `docker compose up --build`
- **THEN** the services become healthy, `GET http://localhost:8080/health` returns HTTP 200 JSON, the login page is reachable at `http://localhost:5173/login`, and PostgreSQL is reachable at the documented `5432` port for local inspection
