"""
Language and framework profiles used to tailor agent prompts and
post-processing to the target technology stack.

Each profile captures the conventions, tooling, and idioms of a specific
language+framework combination.  Agents consume profiles to:
  - Adjust their system prompts with ecosystem-specific instructions
  - Choose the right libraries (ORM, test runner, etc.)
  - Inject mandatory NFRs (type safety, linting, coverage)
  - Validate that generated code uses the correct package manager
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LanguageProfile:
    language: str
    primary_frameworks: list[str]
    test_frameworks: list[str]
    package_manager: str
    linters: list[str]
    type_system: str                  # "static" | "dynamic" | "gradual"
    async_pattern: str
    dependency_file: str
    coding_standards_url: str
    orm_options: list[str]
    di_pattern: str
    api_conventions: str
    code_style_guide: str
    agent_prompt_addendum: str
    additional_tags: list[str] = field(default_factory=list)


LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    # ── Python ────────────────────────────────────────────────────────────────
    "python-fastapi": LanguageProfile(
        language="Python",
        primary_frameworks=["FastAPI"],
        test_frameworks=["pytest", "pytest-asyncio", "httpx"],
        package_manager="pip / poetry",
        linters=["ruff", "mypy"],
        type_system="gradual",
        async_pattern="async/await with asyncio",
        dependency_file="requirements.txt / pyproject.toml",
        coding_standards_url="https://peps.python.org/pep-0008/",
        orm_options=["SQLAlchemy (asyncio)", "Tortoise ORM"],
        di_pattern="FastAPI Depends() injection; no IoC container",
        api_conventions=(
            "FastAPI path operations with type-annotated parameters. "
            "Pydantic v2 BaseModel for request/response schemas. "
            "HTTPException for error responses. APIRouter for modular routing."
        ),
        code_style_guide="PEP 8 + Google Python Style Guide",
        agent_prompt_addendum="""
Use Python 3.11+ features (match statements, Self type, tomllib).
Type-annotate every function signature. Use Pydantic v2 BaseModel for all schemas.
Use async/await throughout; never block the event loop with sync I/O.
Use SQLAlchemy 2.0 with async engine and async_sessionmaker.
All configuration via pydantic-settings and environment variables.
Use structlog for structured logging. Add health-check endpoint at /health.
pytest with pytest-asyncio (asyncio_mode="auto"). Use httpx.AsyncClient for API tests.
""",
    ),
    "python-django": LanguageProfile(
        language="Python",
        primary_frameworks=["Django", "Django REST Framework"],
        test_frameworks=["pytest-django", "factory-boy"],
        package_manager="pip / poetry",
        linters=["ruff", "mypy"],
        type_system="gradual",
        async_pattern="Django async views with sync_to_async",
        dependency_file="requirements.txt",
        coding_standards_url="https://docs.djangoproject.com/en/stable/internals/contributing/writing-code/coding-style/",
        orm_options=["Django ORM"],
        di_pattern="Django dependency injection is implicit via settings and apps",
        api_conventions=(
            "DRF ViewSets and Serializers. Use routers for URL registration. "
            "ModelSerializer for CRUD. Permission classes for auth."
        ),
        code_style_guide="Django Coding Style",
        agent_prompt_addendum="""
Django 4.2+ LTS. Use class-based views / ViewSets. Apps for feature separation.
Settings via django-environ. Use select_related/prefetch_related to avoid N+1.
Custom User model from the start. Use django-filter for query filtering.
pytest-django with @pytest.mark.django_db. factories with factory-boy.
""",
    ),

    # ── TypeScript / Node ─────────────────────────────────────────────────────
    "typescript-nestjs": LanguageProfile(
        language="TypeScript",
        primary_frameworks=["NestJS"],
        test_frameworks=["Jest", "@nestjs/testing", "Supertest"],
        package_manager="npm",
        linters=["ESLint", "Prettier"],
        type_system="static",
        async_pattern="async/await with RxJS Observables",
        dependency_file="package.json",
        coding_standards_url="https://docs.nestjs.com/",
        orm_options=["TypeORM", "Prisma", "MikroORM"],
        di_pattern=(
            "NestJS IoC container. @Injectable() services, @Controller() endpoints. "
            "Module imports for DI scope. Constructor injection throughout."
        ),
        api_conventions=(
            "NestJS @Controller/@Get/@Post/@Put/@Delete decorators. "
            "DTOs with class-validator @IsString()/@IsEmail() etc. "
            "Guards for auth. Interceptors for logging/transform. "
            "Pipes for validation. Exception filters for error handling."
        ),
        code_style_guide="Google TypeScript Style Guide",
        agent_prompt_addendum="""
NestJS 10+. Every feature has: Module, Controller, Service, DTO (Create/Update/Response), Entity.
Use class-validator + class-transformer for DTO validation. Enable global ValidationPipe.
TypeORM with Repository pattern. Use ConfigModule for configuration.
JWT auth via @nestjs/jwt + @nestjs/passport. Swagger via @nestjs/swagger.
Jest with describe/it/expect. Use TestingModule.createTestingModule() for unit tests.
Supertest for e2e. 90%+ coverage enforced in jest.config.ts.
Strict TypeScript: no 'any', strict: true in tsconfig.
""",
        additional_tags=["node", "nestjs"],
    ),
    "typescript-nextjs": LanguageProfile(
        language="TypeScript",
        primary_frameworks=["Next.js"],
        test_frameworks=["Vitest", "React Testing Library", "Playwright"],
        package_manager="npm",
        linters=["ESLint", "Prettier"],
        type_system="static",
        async_pattern="async/await, React Server Components, SWR/TanStack Query",
        dependency_file="package.json",
        coding_standards_url="https://nextjs.org/docs",
        orm_options=["Prisma", "Drizzle ORM"],
        di_pattern="React Context + custom hooks for client-side DI",
        api_conventions=(
            "Next.js App Router with route.ts API handlers. "
            "Server Components for data fetching. Client Components for interactivity. "
            "Zod for schema validation."
        ),
        code_style_guide="Airbnb React / TypeScript Style Guide",
        agent_prompt_addendum="""
Next.js 14+ App Router. Server Components by default; 'use client' only when needed.
Prisma for database access. Zod for all validation.
API routes in app/api/ as route.ts. Use next-auth for authentication.
TanStack Query for client-side data. Tailwind CSS for styling.
Vitest + React Testing Library for unit/component tests. Playwright for e2e.
Strict TypeScript. No barrel files. Co-locate tests with components.
""",
        additional_tags=["react", "node"],
    ),
    "typescript-express": LanguageProfile(
        language="TypeScript",
        primary_frameworks=["Express", "Fastify"],
        test_frameworks=["Jest", "Supertest"],
        package_manager="npm",
        linters=["ESLint", "Prettier"],
        type_system="static",
        async_pattern="async/await",
        dependency_file="package.json",
        coding_standards_url="https://expressjs.com/",
        orm_options=["Prisma", "TypeORM", "Knex"],
        di_pattern="Manual dependency injection via factory functions or tsyringe",
        api_conventions=(
            "Express Router for modular routing. Middleware for cross-cutting concerns. "
            "express-validator or Zod for input validation."
        ),
        code_style_guide="Airbnb TypeScript Style Guide",
        agent_prompt_addendum="""
Express 4+ or Fastify 4+. Modular router structure (features/auth/index.ts etc.).
Prisma ORM with async/await. Helmet + CORS + rate-limiter middleware.
JWT via jsonwebtoken. Winston or pino for structured logging.
Jest + Supertest for API tests. ts-node-dev or tsx for development.
Strict TypeScript. Zod for all external input validation.
""",
        additional_tags=["node"],
    ),

    # ── Java ─────────────────────────────────────────────────────────────────
    "java-spring": LanguageProfile(
        language="Java",
        primary_frameworks=["Spring Boot"],
        test_frameworks=["JUnit 5", "Mockito", "TestContainers", "MockMvc"],
        package_manager="Maven",
        linters=["Checkstyle", "SpotBugs", "PMD"],
        type_system="static",
        async_pattern="CompletableFuture / @Async / WebFlux reactive",
        dependency_file="pom.xml",
        coding_standards_url="https://google.github.io/styleguide/javaguide.html",
        orm_options=["Spring Data JPA", "Hibernate", "MyBatis"],
        di_pattern=(
            "Spring IoC with @Component/@Service/@Repository/@Controller stereotypes. "
            "Constructor injection (NOT @Autowired field injection)."
        ),
        api_conventions=(
            "@RestController + @RequestMapping. ResponseEntity<t> return types. "
            "@Valid on @RequestBody DTOs. ControllerAdvice for global error handling. "
            "Spring Data repositories extending JpaRepository."
        ),
        code_style_guide="Google Java Style Guide",
        agent_prompt_addendum="""
Spring Boot 3.x, Java 17+. Use record classes for immutable DTOs.
Constructor injection only. Layered architecture: Controller → Service → Repository.
@Transactional at the service layer. MapStruct for DTO ↔ Entity mapping.
application.yml (not .properties). spring-dotenv or @ConfigurationProperties.
TestContainers for integration tests with real DB.
JUnit 5 @ExtendWith(MockitoExtension.class). @WebMvcTest for controller unit tests.
Enforce 90% coverage with JaCoCo in pom.xml. Fail build if threshold not met.
""",
    ),

    # ── C# ─────────────────────────────────────────────────────────────────
    "csharp-aspnet": LanguageProfile(
        language="C#",
        primary_frameworks=["ASP.NET Core", "Minimal API"],
        test_frameworks=["xUnit", "Moq", "FluentAssertions", "WebApplicationFactory"],
        package_manager="NuGet",
        linters=["Roslyn analyzers", "StyleCop.Analyzers"],
        type_system="static",
        async_pattern="async/await with Task and CancellationToken",
        dependency_file=".csproj",
        coding_standards_url="https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/",
        orm_options=["Entity Framework Core", "Dapper"],
        di_pattern=(
            "Microsoft.Extensions.DependencyInjection. "
            "Constructor injection. Register in Program.cs: "
            "Scoped for DbContext/repositories, Transient for validators, "
            "Singleton for caches."
        ),
        api_conventions=(
            "Controllers inheriting ControllerBase with [ApiController]. "
            "ActionResult return types. FluentValidation for DTO validation. "
            "IExceptionHandler middleware for global error handling."
        ),
        code_style_guide="Microsoft C# Coding Conventions",
        agent_prompt_addendum="""
.NET 8. C# 12 features: primary constructors, collection expressions.
Record types for DTOs. IOptions for configuration binding.
EF Core 8 with code-first migrations. Repository + Unit of Work pattern.
ILogger for structured logging (Serilog sink in production).
CancellationToken on all async methods. GlobalUsings.cs for common namespaces.
xUnit: [Fact] / [Theory] + [InlineData]. FluentAssertions for assertions.
WebApplicationFactory for integration tests.
Coverlet for coverage; enforce 90% in .csproj.
""",
    ),

    # ── Go ──────────────────────────────────────────────────────────────────
    "go-gin": LanguageProfile(
        language="Go",
        primary_frameworks=["Gin", "Chi", "Echo"],
        test_frameworks=["testing", "testify", "httptest"],
        package_manager="Go Modules",
        linters=["golangci-lint", "staticcheck"],
        type_system="static",
        async_pattern="goroutines and channels",
        dependency_file="go.mod",
        coding_standards_url="https://google.github.io/styleguide/go/",
        orm_options=["GORM", "sqlx", "pgx"],
        di_pattern="Constructor injection via Wire or manual dependency passing",
        api_conventions=(
            "Gin router groups. Handler functions with *gin.Context. "
            "Middleware for auth/logging. Struct binding for request bodies."
        ),
        code_style_guide="Google Go Style Guide",
        agent_prompt_addendum="""
Go 1.21+. Standard project layout: cmd/, internal/, pkg/.
Error wrapping with fmt.Errorf("...: %w", err). No panic in library code.
GORM or pgx for database. Viper or envconfig for configuration.
Structured logging with log/slog (stdlib). Graceful shutdown via context.
Table-driven tests with t.Run(). testify/assert for assertions.
Race detector: go test -race. Enforce 90% coverage with go test -cover.
""",
    ),

    # ── Ruby ─────────────────────────────────────────────────────────────────
    "ruby-rails": LanguageProfile(
        language="Ruby",
        primary_frameworks=["Ruby on Rails"],
        test_frameworks=["RSpec", "FactoryBot", "Capybara"],
        package_manager="Bundler",
        linters=["RuboCop"],
        type_system="dynamic",
        async_pattern="Sidekiq background jobs / ActionCable",
        dependency_file="Gemfile",
        coding_standards_url="https://rubystyle.guide/",
        orm_options=["ActiveRecord"],
        di_pattern="Rails convention over configuration; service objects for complex logic",
        api_conventions=(
            "Rails API mode. RESTful resourceful routes. "
            "Strong parameters. ActiveModel::Serializer or Jbuilder for JSON."
        ),
        code_style_guide="Ruby Style Guide (RuboCop defaults)",
        agent_prompt_addendum="""
Rails 7.1+, Ruby 3.2+. API-only mode (--api flag). Concerns for shared logic.
Service objects in app/services/. Form objects for complex forms.
JWT via devise-jwt or simple_jwt. Pundit for authorization.
RSpec with FactoryBot. Request specs for API tests. SimpleCov for coverage.
""",
    ),
}


def get_profile(
    language: str, framework: str = ""
) -> Optional[LanguageProfile]:
    """
    Return the best-matching LanguageProfile for a language + framework.

    Lookup order:
    1. Exact match on "{language}-{framework}" key (lowercased, spaces removed)
    2. Partial match where the framework key is contained in the profile key
    3. First profile whose language matches (language-only fallback)
    4. None if no match found
    """
    lang_lower = language.lower()
    fw_lower = framework.lower().replace(" ", "").replace(".", "")

    # 1. Exact key match
    if fw_lower:
        exact_key = f"{lang_lower}-{fw_lower}"
        if exact_key in LANGUAGE_PROFILES:
            return LANGUAGE_PROFILES[exact_key]

    # 2. Partial match (e.g. "typescript" + "nestjs" → "typescript-nestjs")
    if fw_lower:
        for key, profile in LANGUAGE_PROFILES.items():
            if lang_lower in key and fw_lower in key:
                return profile

    # 3. Language-only fallback — return first matching profile
    for key, profile in LANGUAGE_PROFILES.items():
        if key.startswith(lang_lower + "-"):
            return profile

    return None


__all__ = ["LanguageProfile", "LANGUAGE_PROFILES", "get_profile"]
