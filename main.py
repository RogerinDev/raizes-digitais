import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from config import settings
from utils import humanized_send_message, extract_text_from_pdf
from ai_service import AgriculturalAgent, process_pdf_for_admin, ask_pdf_for_user

# Configuração de Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuração do Bot e Application (Python-Telegram-Bot)
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

import psycopg
import asyncio

async def recuperar_mensagens_pendentes(app: Application):
    """
    Varre o banco de dados em busca de mensagens que ficaram sem resposta do bot (última mensagem == 'human')
    e as processa em background.
    """
    logger.info("Iniciando varredura de mensagens pendentes no banco...")
    try:
        conn = psycopg.connect(settings.POSTGRES_CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Query para buscar a última mensagem de cada sessão cruzando com o chat_mapping
        query = """
        WITH RankedMessages AS (
            SELECT session_id, message,
                   ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY id DESC) as rn
            FROM chat_memory
        )
        SELECT rm.session_id, rm.message, cm.telegram_chat_id
        FROM RankedMessages rm
        JOIN chat_mapping cm ON rm.session_id = cm.uuid_session_id
        WHERE rm.rn = 1;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        
        for session_uuid, message_json, telegram_chat_id in results:
            msg_type = message_json.get("type")
            if msg_type == "human":
                # Bot não respondeu a essa mensagem!
                content = message_json.get("data", {}).get("content", "")
                logger.info(f"Recuperando pendência do usuário Telegram ID: {telegram_chat_id}")
                
                try:
                    # Instanciamos o agente passando o ID real numérico para que ele obedeça a lógica local de hash
                    agent = AgriculturalAgent(session_id=str(telegram_chat_id))
                    response = await agent.ainvoke(content)
                    
                    # Usa o telegram_chat_id real recuperado pelo JOIN
                    await app.bot.send_message(chat_id=telegram_chat_id, text=response)
                except Exception as ex:
                    logger.error(f"Falha ao enviar resposta recuperada: {ex}")
                    
        logger.info("Varredura de mensagens pendentes concluída.")
    except Exception as e:
        logger.error(f"Erro geral na recuperação de mensagens: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida do FastAPI, registrando o Webhook do Telegram no início
    e removendo-o no encerramento.
    """
    logger.info("Iniciando aplicação e configurando Webhook...")
    await application.initialize()
    await application.start()
    await bot.set_webhook(url=settings.TELEGRAM_WEBHOOK_URL)
    
    # Executa a recuperação de mensagens como tarefa de fundo na inicialização
    asyncio.create_task(recuperar_mensagens_pendentes(application))
    
    yield
    
    logger.info("Encerrando aplicação e removendo Webhook...")
    await application.stop()
    await application.shutdown()

# Instância do FastAPI
app = FastAPI(title="Raízes Digitais - IA Agrícola", lifespan=lifespan)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lida com mensagens de texto enviadas pelo usuário ou admin.
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    try:
        # Instancia o Agente com a sessão atrelada ao ID do Telegram
        agent = AgriculturalAgent(session_id=str(user_id))
        
        # Envia a ação de digitando imediatamente para dar feedback
        await context.bot.send_chat_action(chat_id=user_id, action="typing")
        
        # Executa o Agente LangChain
        response = await agent.ainvoke(text)
        
        # Envia a resposta de forma humanizada e fatiada
        await humanized_send_message(update, context, response)
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem de texto (Timeout/503/Outros): {e}")
        mensagem_erro = (
            "Amigo produtor, meu sistema está recebendo muitas consultas ao mesmo tempo agora. "
            "Por favor, aguarde uns minutinhos e me pergunte novamente! 🌱"
        )
        await context.bot.send_message(
            chat_id=user_id, 
            text=mensagem_erro
        )

async def handle_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lida com documentos PDF enviados, roteando entre Admin (Ingestão RAG) e Produtor (Análise AdHoc).
    """
    user_id = update.effective_user.id
    document = update.message.document
    
    if not document.file_name.endswith('.pdf'):
        await context.bot.send_message(chat_id=user_id, text="Por favor, envie apenas arquivos PDF.")
        return

    # Download do arquivo temporariamente
    file = await context.bot.get_file(document.file_id)
    file_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(file_path)
    
    try:
        # Extrai e limpa o texto do PDF
        text = extract_text_from_pdf(file_path)
        
        # Roteamento de Fluxo Baseado no ID do Usuário
        if user_id == settings.ADMIN_TELEGRAM_ID:
            # Fluxo Administrador: Ingestão de Conhecimento
            await context.bot.send_message(chat_id=user_id, text="Recebi o manual. Iniciando processamento e ingestão no banco...")
            
            await process_pdf_for_admin(text)
            
            await context.bot.send_message(chat_id=user_id, text="✅ Chefe, manual salvo com sucesso!")
        
        else:
            # Fluxo Produtor Padrão: Perguntas sobre o PDF
            caption = update.message.caption
            
            if not caption:
                await context.bot.send_message(
                    chat_id=user_id, 
                    text="Recebi seu PDF. Por favor, faça uma pergunta sobre ele na legenda do arquivo ou na sua próxima mensagem."
                )
                return
            
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            
            # Chama o LLM passando o conteúdo do PDF
            response = await ask_pdf_for_user(text, caption)
            
            # Envia resposta de forma humanizada
            await humanized_send_message(update, context, response)
            
    except Exception as e:
        logger.error(f"Erro ao processar documento PDF: {e}")
        await context.bot.send_message(
            chat_id=user_id, 
            text="Ocorreu um erro ao ler o documento ou ao contatar os serviços. Tente novamente."
        )
    finally:
        # Limpeza do arquivo temporário
        if os.path.exists(file_path):
            os.remove(file_path)

# Registrando os Handlers na aplicação do Telegram
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
application.add_handler(MessageHandler(filters.Document.ALL, handle_document_message))

@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint chamado pelo Telegram sempre que houver uma atualização.
    """
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, application.bot)
        
        # Envia para a Background Task do FastAPI em vez de esperar a IA concluir
        background_tasks.add_task(application.process_update, update)
        
        # Retorna 200 OK imediatamente para o Telegram
        return {"ok": True}
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/health")
async def health_check():
    """
    Rota de saúde para balanceadores de carga ou monitoramento.
    """
    return {"status": "healthy", "service": "Raízes Digitais AI"}

if __name__ == "__main__":
    import uvicorn
    # Executa a aplicação localmente
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
