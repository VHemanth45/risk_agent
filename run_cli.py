import requests
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box
from rich.markup import escape
from rich.text import Text

console = Console()
API_URL = "http://localhost:8000/analyze_risk/"

def display_header():
    console.clear()
    title = Text(" ScamShield Risk Agent CLI", style="bold cyan")
    subtitle = Text("\nMultimodal Financial Fraud Detection System", style="dim")
    hint = Text("\n(Supports multiple files: image1.png, audio.mp3, chat.txt)", style="dim italic")
    
    header_content = Text.assemble(title, subtitle, hint)
    
    console.print(Panel.fit(
        header_content,
        box=box.DOUBLE,
        border_style="cyan"
    ))

def get_file_paths():
    while True:
        raw_input = Prompt.ask("\nEnter path(s) to files (separated by commas) (or 'q' to quit)")
        if raw_input.lower() == 'q':
            sys.exit(0)
        
        paths = [p.strip().strip('"\'') for p in raw_input.split(",")]
        valid_paths = [p for p in paths if os.path.exists(p) and os.path.isfile(p)]
        
        if valid_paths:
            return valid_paths
        else:
            console.print("[bold red] No valid files found from provided paths.[/bold red]")

def analyze_files(file_paths):
    upload_list = []
    for path in file_paths:
        filename = os.path.basename(path)
        mime_type = "application/octet-stream"
        lf = filename.lower()
        if lf.endswith(('.jpg', '.jpeg')): mime_type = "image/jpeg"
        elif lf.endswith('.png'): mime_type = "image/png"
        elif lf.endswith('.webp'): mime_type = "image/webp"
        elif lf.endswith('.mp3'): mime_type = "audio/mp3"
        elif lf.endswith('.wav'): mime_type = "audio/wav"
        elif lf.endswith('.m4a'): mime_type = "audio/mp4"
        elif lf.endswith('.txt'): mime_type = "text/plain"
        
        f = open(path, 'rb')
        upload_list.append(('files', (filename, f, mime_type)))

    with console.status(f"[bold green] Uploading & Analyzing {len(file_paths)} file(s)...[/bold green]", spinner="dots"):
        try:
            response = requests.post(API_URL, files=upload_list)
            for _, file_data in upload_list: file_data[1].close()

            if response.status_code == 200:
                return response.json()
            else:
                safe_text = escape(response.text)
                console.print(f"[bold red] API Error {response.status_code}:[/bold red] {safe_text}")
                return None
        except Exception as e:
            console.print(f"[bold red] Error:[/bold red] {e}")
            return None

def display_results(data):
    if not data: return

    verdict = data.get("final_verdict", {})
    evidence = data.get("detailed_evidence", {})
    memory_context = evidence.get("memory_context", "")
    aggregated_text = evidence.get("aggregated_text", "")
    
    risk_level = verdict.get("risk_level", "Unknown")
    probability = verdict.get("probability", 0.0)
    color = "green"
    if risk_level == "Medium": color = "yellow"
    if risk_level == "High": color = "red"
    
    console.print()
    
    # 1. Long-term Memory Section
    if memory_context:
        console.print(Panel(
            escape(memory_context.strip()),
            title="🧠 Long-term Memory Context",
            border_style="magenta",
            box=box.ROUNDED
        ))

    # 2. Main Verdict
    safe_analysis = escape(verdict.get('analysis', 'No analysis provided.'))
    console.print(Panel(
        f"[bold {color}]RISK LEVEL: {risk_level.upper()} ({probability*100:.1f}%)[/bold {color}]\n\n"
        f"{safe_analysis}",
        title=" Agent Verdict",
        border_style=color,
        box=box.ROUNDED
    ))
    
    # 3. Evidence Table
    table = Table(title=" Detected Evidence", box=box.SIMPLE_HEAD)
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Source", style="magenta")
    table.add_column("Details/Match", style="white")

    for visual in evidence.get("visual_analysis", []):
        risk = visual['visual_risk']
        table.add_row(" Visual", escape(visual['filename']), f"[{color}]{risk['risk_level']} Risk[/{color}]: {escape(risk['analysis'])}")

    for text_case in evidence.get("text_matches", []):
         table.add_row(" Database", f"Risk: {text_case['risk_label']}", f"Similarity: {text_case['score']:.2f} | {escape(text_case['text_snippet'][:60])}...")
        
    console.print(table)
    
    # 4. Recommendations Section
    recs = verdict.get("recommendations", [])
    if recs:
        rec_list = "\n".join([f"• {r}" for r in recs])
        
        # Style based on risk level
        rec_border_style = "white"
        if risk_level == "High": rec_border_style = "red bold"
        elif risk_level == "Medium": rec_border_style = "yellow"
        
        console.print(Panel(
            rec_list,
            title="🛡️ Recommended Actions",
            border_style=rec_border_style,
            box=box.ROUNDED
        ))

    if aggregated_text:
         safe_content = Text(aggregated_text.strip())
         console.print(Panel(safe_content, title=" Extracted Metadata / Transcripts", border_style="blue", box=box.SIMPLE))
    
    console.print()

def main():
    display_header()
    while True:
        paths = get_file_paths()
        result = analyze_files(paths)
        display_results(result)
        if Prompt.ask("Analyze another set? (y/n)", choices=["y", "n"], default="y") == "n": break
    console.print("[bold cyan] Stay Safe![/bold cyan]")

if __name__ == "__main__": main()
