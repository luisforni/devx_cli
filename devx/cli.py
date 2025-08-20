from devx.core.logging import setup as setup_logging
import typer
from devx.services.health.cli import app as health_app
from devx.services.loadtest.cli import app as loadtest_app
from devx.services.linkscan.cli import app as linkscan_app
from devx.services.secrets.cli import app as secrets_app
from devx.services.docgen.cli import app as docgen_app
from devx.services.securityscan.cli import app as security_app
from devx.services.sbom.cli import app as sbom_app
from devx.services.lint.cli import app as lint_app
from devx.services.depgraph.cli import app as depgraph_app
from devx.services.perf.cli import app as perf_app
from devx.services.coverage.cli import app as coverage_app
from devx.services.dockercheck.cli import app as docker_app

setup_logging()

app = typer.Typer(help="DevX – Modular console toolkit")

app.add_typer(health_app, name="health", help="Project health inspector")
app.add_typer(loadtest_app, name="loadtest", help="API load tester")
app.add_typer(linkscan_app, name="linkscan", help="Broken-links crawler")
app.add_typer(secrets_app, name="secrets", help="Secrets detector")
app.add_typer(docgen_app, name="docgen", help="Markdown doc generator")
app.add_typer(security_app, name="securityscan", help="Web security scanner")
app.add_typer(sbom_app, name="sbom", help="Software Bill of Materials (SBOM) generator")
app.add_typer(lint_app, name="lint", help="Linter + Formatter + Complexity")
app.add_typer(depgraph_app, name="depgraph", help="Dependency graph (imports)")
app.add_typer(perf_app, name="perf", help="Performance profiler")
app.add_typer(coverage_app, name="coverage", help="Test coverage analyzer")
app.add_typer(docker_app, name="dockercheck", help="Docker image auditor")

def main():
    setup_logging()
    app()
