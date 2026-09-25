import asyncio
import re
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext

async def humanized_send_message(update: Update, context: CallbackContext, text: str):
    """
    Fatia a resposta por \n\n e envia cada parágrafo com delay simulando digitação,
    criando um loop interativo e humano.
    """
    # Quebra o texto por quebras de linha (seja \n ou \n\n) e remove espaços em branco extras
    paragraphs = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    
    for p in paragraphs:
        # Envia ação de 'digitando' para a API do Telegram
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action=ChatAction.TYPING
        )
        
        # Delay dinâmico baseado no tamanho do texto fatiado
        delay = max(len(p) * 0.02, 0.5)
        await asyncio.sleep(delay)
        
        # Dispara a mensagem
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=p
        )

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Lê um arquivo PDF, extrai todo o texto e limpa as quebras de linha duplicadas.
    """
    import pdfplumber
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
    # Limpar quebras de linha duplicadas
    text = re.sub(r'\n+', '\n', text)
    return text
