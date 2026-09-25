import re
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_postgres import PostgresChatMessageHistory
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import create_client, Client
import psycopg
import uuid
import asyncio
from config import settings

# Trava global para enfileirar as requisições à API do Gemini e evitar bloqueios de concorrência
agent_lock = asyncio.Lock()
# Inicializando Supabase Client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

# Inicializando Embeddings
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=settings.GOOGLE_API_KEY
)

# Vector Store no Supabase
vector_store = SupabaseVectorStore(
    client=supabase,
    embedding=embeddings,
    table_name="documents",
    query_name="match_documents"
)

# LLM Gemini (para chat e agentes)
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.2,
    google_api_key=settings.GOOGLE_API_KEY,
    max_retries=3,
    timeout=90
)

@tool
def consult_agricultural_manual(query: str) -> str:
    """
    Consulte esta ferramenta OBRIGATORIAMENTE sempre que precisar responder a dúvidas técnicas sobre cafeicultura.
    Ela busca em nossa base de dados oficial e confiável.
    Você não deve inventar informações.
    """
    # 1. Gera o vetor matemático (embedding) a partir do texto puro
    embedding_gerado = embeddings.embed_query(query)
    
    # 2. Chama a procedure RPC match_documents direto no cliente Supabase (Busca Híbrida)
    response = supabase.rpc(
        "match_documents", 
        {
            "query_text": query, 
            "query_embedding": embedding_gerado, 
            "match_count": 4
        }
    ).execute()
    
    docs = response.data
    if not docs:
        return "Nenhuma informação técnica encontrada nos manuais para esta pergunta."
        
    # 3. Processa e concatena apenas o campo "content" para leitura do LLM
    return "\n\n".join([doc['content'] for doc in docs])

# Tool injetada no LangChain para combater alucinações (RAG)
tools = [consult_agricultural_manual]

# Prompt Estrito
SYSTEM_PROMPT = """Você é um Engenheiro Agrônomo e assistente virtual especializado em cafeicultura do Sul de Minas Gerais, atuando no Projeto Raízes Digitais.
Seu objetivo é orientar pequenos produtores de café de forma clara, prestativa e técnica.

REGRAS ESTRITAS DE COMPORTAMENTO:
1. Anti-alucinação: NUNCA invente informações. Você deve OBRIGATORIAMENTE utilizar a ferramenta `consult_agricultural_manual` para buscar conhecimentos técnicos antes de responder a perguntas sobre plantio, pragas, manejo, defensivos, etc.
2. Seja direto e objetivo, mas acolhedor como um típico mineiro.
3. Formatação: PROIBIDO o uso de Markdown. Não use asteriscos, itálico, negrito ou qualquer formatação especial. Retorne apenas texto puro.
4. Caso a pergunta fuja completamente da agricultura (café) ou do contexto de pequenos produtores, informe educadamente que sua especialidade é a cafeicultura e você não pode ajudar com outros temas.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Criando o Agente e o Executor
agent = create_tool_calling_agent(llm, tools, prompt)

class AgriculturalAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        
        # Memória persistente no PostgreSQL via LangChain
        # Converte o ID numérico do Telegram em um UUID válido e constante (determinístico)
        session_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram_{session_id}"))
        
        # Grava a relação UUID <-> Telegram ID para futura recuperação
        try:
            supabase.table("chat_mapping").upsert({
                "uuid_session_id": session_uuid,
                "telegram_chat_id": int(session_id)
            }).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Erro ao salvar mapping: {e}")
        
        conn = psycopg.connect(settings.POSTGRES_CONNECTION_STRING)
        self.history = PostgresChatMessageHistory(
            "chat_memory",
            session_uuid,
            sync_connection=conn
        )
        
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True
        )

    def append_chemical_warning(self, text: str) -> str:
        """
        Gatilho para adicionar aviso legal se a resposta envolver defensivos químicos.
        """
        keywords = ['agrotóxico', 'defensivo', 'herbicida', 'fungicida', 'inseticida', 'pulverização', 'veneno', 'químico', 'aplicar', 'dosagem']
        if any(keyword in text.lower() for keyword in keywords):
            return text + """

Aviso: Esta é uma orientação baseada em literatura técnica. A avaliação presencial de um agrônomo é indispensável antes de qualquer aplicação."""
        return text

    def clean_markdown(self, text: str) -> str:
        """
        Garante a remoção de formatação Markdown.
        """
        # Remove asteriscos, underlines, sustenidos
        text = re.sub(r'(\*\*|\*|__|_|#)', '', text)
        return text.strip()

    async def ainvoke(self, user_input: str) -> str:
        """
        Processa a entrada do usuário através do agente com memória.
        """
        chat_history = self.history.messages
        
        # Garante que apenas uma requisição acesse o LLM por vez
        async with agent_lock:
            result = await self.agent_executor.ainvoke({
                "input": user_input,
                "chat_history": chat_history
            })
        
        output = result['output']
        
        # Extrai a string se o modelo retornar uma lista de blocos estruturados
        if isinstance(output, list) and len(output) > 0 and isinstance(output[0], dict):
            output = output[0].get('text', str(output))
        elif not isinstance(output, str):
            output = str(output)
        
        # Pós-processamento estrito
        output = self.clean_markdown(output)
        output = self.append_chemical_warning(output)
        
        # Salva as mensagens manualmente para garantir a persistência correta
        self.history.add_user_message(user_input)
        self.history.add_ai_message(output)
        
        return output

async def process_pdf_for_admin(text: str):
    """
    Fluxo do Administrador: Processa o PDF, fatia em pedaços e converte em embeddings.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    docs = text_splitter.create_documents([text])
    
    # Salvar no Vector Store
    await vector_store.aadd_documents(docs)

async def ask_pdf_for_user(text: str, question: str) -> str:
    """
    Fluxo do Produtor (PDF): Lê um PDF enviado e responde à pergunta com base no texto.
    Utiliza LLM diretamente no modo chat para analisar o contexto local.
    """
    from langchain_core.prompts import PromptTemplate
    
    prompt_pdf = PromptTemplate.from_template(
        "Baseado EXCLUSIVAMENTE no texto a seguir (extraído de um PDF), responda à pergunta do usuário.\n\n"
        "Texto:\n{context}\n\n"
        "Pergunta: {question}\n\n"
        "REGRAS ESTRITAS:\n"
        "1. PROIBIDO o uso de Markdown. Não use asteriscos, itálico, negrito.\n"
        "2. Retorne apenas texto puro.\n"
        "3. Não invente nada fora do texto fornecido."
    )
    
    chain = prompt_pdf | llm
    
    # Protege a chamada do modelo para respeitar o limite de concorrência da API gratuita
    async with agent_lock:
        res = await chain.ainvoke({"context": text, "question": question})
    
    output = res.content
    output = re.sub(r'(\*\*|\*|__|_|#)', '', output).strip()
    
    keywords = ['agrotóxico', 'defensivo', 'herbicida', 'fungicida', 'inseticida', 'pulverização', 'veneno', 'químico', 'aplicar', 'dosagem']
    if any(keyword in output.lower() for keyword in keywords):
        output += """

Aviso: Esta é uma orientação baseada em literatura técnica. A avaliação presencial de um agrônomo é indispensável antes de qualquer aplicação."""
    
    return output
