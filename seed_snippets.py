import nmct_db_manager

# Seed Snippet 1: Python - Ask (Ollama chat client template)
ask_code = """import asyncio
import ollama

async def ask_local_slm(prompt: str, model: str = "gemma2:2b", system_prompt: str = "You are Moe."):
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': prompt}
    ]
    response = await asyncio.to_thread(ollama.chat, model=model, messages=messages)
    return response['message']['content']
"""

nmct_db_manager.store_snippet(
    name="ollama_ask_client",
    language="python",
    performative="ask",
    description="Asynchronously queries local Ollama models with a system prompt.",
    code=ask_code,
    fitness_score=0.95,
    lifespan_days=60
)

# Seed Snippet 2: Python - Achieve (Excel update agent template)
achieve_code = """import openpyxl
from datetime import datetime

def update_excel_db_inventory(file_path: str, db_name: str, status: str, size_gb: float):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    
    # Header: Name | Status | Size (GB) | Last Checked
    # Find existing database row or append
    found_row = None
    for row in range(2, sheet.max_row + 1):
        if sheet.cell(row=row, column=1).value == db_name:
            found_row = row
            break
            
    row_to_write = found_row if found_row else (sheet.max_row + 1)
    
    sheet.cell(row=row_to_write, column=1, value=db_name)
    sheet.cell(row=row_to_write, column=2, value=status)
    sheet.cell(row=row_to_write, column=3, value=size_gb)
    sheet.cell(row=row_to_write, column=4, value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    
    wb.save(file_path)
    return f"Database '{db_name}' updated in row {row_to_write}"
"""

nmct_db_manager.store_snippet(
    name="excel_inventory_updater",
    language="python",
    performative="achieve",
    description="Updates database entries in the Excel master inventory catalog.",
    code=achieve_code,
    fitness_score=0.98,
    lifespan_days=90
)

# Seed Snippet 3: JavaScript - Tell (stdio JSON streaming output)
tell_code = """const readline = require('readline');

function tellGuiClient(performative, content, ontology = "database-management") {
    const message = {
        timestamp: new Date().toISOString(),
        performative: performative.toLowerCase(),
        content: content,
        ontology: ontology
    };
    // Dual-write: stdout for client bridge, stderr for logs
    console.log(JSON.stringify(message));
    console.error(`[TELL] ${JSON.stringify(message)}`);
}
"""

nmct_db_manager.store_snippet(
    name="js_tell_stdio_streamer",
    language="javascript",
    performative="tell",
    description="Formats and streams a KQML tell message to the parent JavaFX GUI over stdout.",
    code=tell_code,
    fitness_score=0.92,
    lifespan_days=45
)
