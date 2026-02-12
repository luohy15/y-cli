import os
import sqlite3
import subprocess
import tempfile
import click

from config import config


@click.command('export')
@click.option('--output', '-o', default=None, help='Output SQLite file path (default: config sqlite_file)')
def export_chats(output: str = None):
    """Export Cloudflare D1 database to a local SQLite file using wrangler."""
    output_path = output or config.get('sqlite_file')

    d1_config = config.get('cloudflare_d1', {})
    database_name = d1_config.get('database_name')
    if not database_name:
        click.echo("Error: cloudflare_d1.database_name is not configured")
        return

    # Export D1 to a temporary SQL dump file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        click.echo(f"Exporting D1 database ({database_name}) via wrangler...")
        env = os.environ.copy()
        api_token = d1_config.get('api_token')
        if api_token:
            env['CLOUDFLARE_API_TOKEN'] = api_token
        account_id = d1_config.get('account_id')
        if account_id:
            env['CLOUDFLARE_ACCOUNT_ID'] = account_id
        subprocess.run(
            ['npx', 'wrangler', 'd1', 'export', database_name,
             '--remote', '--output', tmp_path],
            check=True,
            env=env,
        )

        # Import the SQL dump into a local SQLite file
        click.echo(f"Importing SQL dump into: {output_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if os.path.exists(output_path):
            os.remove(output_path)

        with open(tmp_path, 'r') as f:
            sql = f.read()

        conn = sqlite3.connect(output_path)
        conn.executescript(sql)
        conn.close()

        click.echo("Export completed successfully.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error running wrangler: {e}")
    except Exception as e:
        click.echo(f"Error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
