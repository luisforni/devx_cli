import typer
from devx.services.health.cli import app as health_app
from devx.services.loadtest.cli import app as loadtest_app
from devx.services.linkscan.cli import app as linkscan_app
from devx.services.secrets.cli import app as secrets_app
from devx.services.docgen.cli import app as docgen_app
from devx.services.securityscan.cli import app as security_app

app = typer.Typer(help="DevX – Modular console toolkit")

app.add_typer(health_app,   name="health",       help="Project health inspector")
app.add_typer(loadtest_app, name="loadtest",     help="API load tester")
app.add_typer(linkscan_app, name="linkscan",     help="Broken-links crawler")
app.add_typer(secrets_app,  name="secrets",      help="Secrets detector")
app.add_typer(docgen_app,   name="docgen",       help="Markdown doc generator")
app.add_typer(security_app, name="securityscan", help="Web security scanner")

def main():
    app()
