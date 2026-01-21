import os
import re
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def main():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🛠️  ScamShield Environment Fixer[/bold cyan]\n"
        "[dim]Cleans and validates your .env configuration[/dim]",
        border_style="cyan"
    ))

    # 1. Ask for API Key
    print("\nStep 1: Configure Google Gemini API Key")
    raw_key = Prompt.ask("[yellow]Paste your GOOGLE_API_KEY here[/yellow]")
    
    # Clean the key (Remove quotes, spaces)
    clean_key = raw_key.strip().replace('"', '').replace("'", "")
    
    # 2. Validation
    if not clean_key.startswith("AIza"):
        console.print("[bold red]Error:[/bold red] That doesn't look like a valid Google API Key. (Should start with 'AIza')")
        if not Prompt.confirm("[yellow]Do you want to save it anyway?[/yellow]"):
            console.print("[red]Aborted.[/red]")
            return

    # 3. Read existing .env to preserve other variables
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    env_vars[key.strip()] = value.strip()

    # 4. Update the key
    env_vars["GOOGLE_API_KEY"] = clean_key
    
    # Ensure defaults for other critical keys if missing
    if "USE_CLOUD" not in env_vars: env_vars["USE_CLOUD"] = "True"
    
    # 5. Write back clean .env
    with open(".env", "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    console.print(Panel(
        f"[bold green]Success![/bold green] Your .env file has been updated and cleaned.\n\n"
        f"[bold white]IMPORTANT:[/bold white]\n"
        f"You MUST restart the uvicorn server for the changes to take effect.\n"
        f"Command: [cyan]uvicorn risk_agent.main:app --reload[/cyan]",
        border_style="green"
    ))

if __name__ == "__main__":
    main()
