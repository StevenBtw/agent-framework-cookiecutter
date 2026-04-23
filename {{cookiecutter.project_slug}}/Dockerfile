FROM python:{{ cookiecutter.python_version }}-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ src/

# Install the project
RUN uv sync --frozen --no-dev

RUN mkdir -p /app/uploads

EXPOSE 8000

{%- if cookiecutter.interface in ["fastapi", "both"] %}
CMD ["uv", "run", "uvicorn", "{{ cookiecutter.package_name }}.interfaces.server:app", "--host", "0.0.0.0", "--port", "8000"]
{%- else %}
CMD ["uv", "run", "{{ cookiecutter.project_slug }}"]
{%- endif %}
