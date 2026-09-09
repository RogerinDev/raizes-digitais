# ☕ Raízes Digitais
> **Cultivando a Inovação com IA Generativa na Cafeicultura Sul-Mineira**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Generative AI](https://img.shields.io/badge/Generative%20AI-000000?style=for-the-badge&logo=openai&logoColor=white)
![CEFET-MG](https://img.shields.io/badge/CEFET--MG-Campus%20Varginha-005312?style=for-the-badge)

## 📌 Sobre o Projeto
O projeto **Raízes Digitais** tem como objetivo democratizar o acesso a informações agronômicas especializadas para pequenos e médios cafeicultores do Sul de Minas Gerais. 

Através do desenvolvimento de um **Assistente Virtual inteligente**, buscamos apoiar a tomada de decisão ágil e segura diretamente no campo. Para garantir a extrema confiabilidade técnica exigida pelo setor agropecuário, o sistema é estruturado com a arquitetura **RAG (Retrieval-Augmented Generation)**. Essa técnica acopla o modelo de Inteligência Artificial a bancos de dados vetoriais contendo apenas evidências e manuais agrícolas validados, mitigando totalmente o risco de "alucinações" algorítmicas e garantindo precisão nas respostas.

## 🚀 Acesse o Portfólio
A apresentação visual e estrutural do projeto está disponível online:
👉 **[Acessar Portfólio do Raízes Digitais](https://rogerindev.github.io/raizes-digitais/)** 

## 🛠️ Tecnologias Empregadas
O desenvolvimento do ecossistema e do Assistente Virtual baseia-se nas seguintes tecnologias e conceitos:
* **Backend Framework:** FastAPI, Python-Telegram-Bot
* **Orquestração de IA:** LangChain, LangChain-Postgres
* **IA Generativa:** Google Gemini (Modelos Flash-Lite e `gemini-embedding-001`)
* **Banco de Dados:** PostgreSQL com suporte a extensão `pgvector` (Supabase)
* **Arquitetura e RAG:** Busca Semântica em Manuais em PDF e Chat Memory atrelada a cada produtor.

---

## ⚙️ Como executar o projeto localmente

Siga o passo a passo rigoroso abaixo para rodar o ecossistema inteligente na sua própria máquina.

### 1. Clonar o repositório
```bash
git clone https://github.com/RogerinDev/raizes-digitais.git
cd raizes-digitais
```

### 2. Configurar o Ambiente Virtual (VENV)
É estritamente recomendado criar um ambiente virtual isolado para proteger as bibliotecas.
```bash
python3 -m venv venv

# Para Linux/MacOS/Fish:
source venv/bin/activate
# Para Windows:
venv\Scripts\activate
```

### 3. Instalar as Dependências
Com o ambiente ativado, instale todas as bibliotecas necessárias:
```bash
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente
Crie uma cópia do arquivo de exemplo `.env.example` e renomeie-a para `.env`.
Em um terminal Unix (ou copie/cole manualmente):
```bash
cp .env.example .env
```
Abra o arquivo `.env` e alimente-o com suas próprias chaves e acessos:
- `TELEGRAM_BOT_TOKEN`: Gerado via BotFather no aplicativo do Telegram.
- `ADMIN_TELEGRAM_ID`: ID numérico do seu usuário administrador (necessário para a IA aceitar PDFs novos para ingestão).
- `GOOGLE_API_KEY`: Chave da API do Google AI Studio para o Gemini.
- `SUPABASE_URL` e `SUPABASE_SERVICE_KEY`: Credenciais restritas do seu projeto no Supabase.
- `POSTGRES_CONNECTION_STRING`: String de conexão SQL do Supabase. Recomendado usar o **Session Pooler** (na porta 5432) apontando para o seu nó (ex: `aws-0-us-east-1`).
- `TELEGRAM_WEBHOOK_URL`: (Veremos no próximo passo como configurar essa chave com o ngrok).

### 5. Configurar o Ngrok (Túnel Local)
Como a API do Telegram exige segurança (HTTPS) para comunicar eventos (Webhook) em tempo real, precisamos expor nossa porta local:
1. Abra um terminal **separado** (mantenha aberto rodando em segundo plano).
2. Inicie o Ngrok na porta 8000, onde o FastAPI do backend rodará:
```bash
ngrok http 8000
```
3. Copie o endereço HTTPS aleatório gerado pelo Ngrok (Ex: `https://quail-revision-scrap.ngrok-free.dev`).
4. Retorne ao arquivo `.env` e cole o endereço. **Não esqueça de adicionar a rota `/webhook`** no final do link:
   ```env
   TELEGRAM_WEBHOOK_URL="https://quail-revision-scrap.ngrok-free.dev/webhook"
   ```

### 6. Ativar e Sincronizar o Webhook no Telegram
Agora que o link seguro existe, rode o script utilitário criado para registrar e sincronizar a sua URL gerada com a API oficial do Telegram:
```bash
python setup_webhook.py
```
> *A resposta deverá ser um "✅ Sucesso" com um log completo retornando as chaves do Telegram validadas.*

### 7. Iniciar a Aplicação (FastAPI)
Com tudo alinhado e conectado com o banco de dados (certifique-se de já ter habilitado a extensão `pgvector` e as tabelas `documents` / `chat_memory` em sua conta Supabase), inicie a rede neural:
```bash
python main.py
```
**Pronto!** O backend estará ativo e de prontidão (`Uvicorn running`). Toda mensagem recebida no Telegram ativará as rotinas de *Background Tasks* e *Humanização*, efetuando RAG em tempo real na cafeicultura.

---

## 👥 Equipe Técnica
O projeto é conduzido no **Laboratório de Apoio à Pesquisa e Inovação em Sistemas de Informação (LAPIS)** do CEFET-MG.

| Membro | Papel no Projeto |
| :--- | :--- |
| **Prof. Bruno Monserrat Perillo** | Coordenador |
| **Prof. Eduardo Gomes Carvalho** | Coorientador |
| **Prof. Lazaro Eduardo da Silva** | Coorientador |
| **Rogerio Otávio Filho** | Bolsista de Projeto de Extensão |
| **Antonio Prado Horta** | Bolsista de Projeto de Extensão |
| **Luiz Henrique Garcia** | Voluntário |

---
📝 *Este projeto é uma iniciativa de extensão universitária voltada à inclusão tecnológica, gestão do conhecimento e fortalecimento do agronegócio local.*
