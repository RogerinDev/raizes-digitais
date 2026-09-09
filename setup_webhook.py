import os
import httpx
from dotenv import load_dotenv

def setup_webhook():
    # Carrega as variáveis de ambiente do arquivo .env
    load_dotenv()

    # Extrai as variáveis necessárias
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

    # Fast Fail: verifica se as variáveis estão presentes
    if not bot_token or bot_token == "SEU_TOKEN_DO_TELEGRAM":
        print("❌ ERRO: A variável 'TELEGRAM_BOT_TOKEN' não foi encontrada ou não foi configurada no arquivo .env.")
        exit(1)
        
    if not webhook_url or webhook_url == "https://seu-dominio.com/webhook":
        print("❌ ERRO: A variável 'TELEGRAM_WEBHOOK_URL' não foi encontrada ou não foi configurada no arquivo .env.")
        exit(1)

    # Verifica se a URL do Webhook inclui '/webhook' no final, conforme configurado no FastAPI
    if not webhook_url.endswith("/webhook"):
        print("⚠️ AVISO: Sua TELEGRAM_WEBHOOK_URL não termina com '/webhook'. Certifique-se de que a rota no ngrok aponte para o endpoint correto do FastAPI.")

    print(f"🔄 Configurando Webhook para a URL: {webhook_url}...")

    # URL base da API do Telegram
    base_api_url = f"https://api.telegram.org/bot{bot_token}"

    try:
        # Requisição POST para configurar o Webhook
        set_response = httpx.post(
            f"{base_api_url}/setWebhook",
            json={"url": webhook_url}
        )
        
        if set_response.status_code == 200 and set_response.json().get("ok"):
            print("✅ Sucesso: Webhook configurado no Telegram!")
        else:
            print(f"❌ Falha ao configurar Webhook. HTTP Status: {set_response.status_code}")
            print(f"Detalhes: {set_response.text}")
            exit(1)

        print("\n🔍 Validando status atual do Webhook no Telegram...")
        
        # Requisição GET para buscar as informações do Webhook recém configurado
        info_response = httpx.get(f"{base_api_url}/getWebhookInfo")
        
        if info_response.status_code == 200:
            print("✅ Status do Webhook verificado com sucesso. Resposta do Telegram:\n")
            print(info_response.json())
        else:
            print(f"❌ Falha ao obter informações do Webhook. HTTP Status: {info_response.status_code}")
            print(f"Detalhes: {info_response.text}")

    except httpx.RequestError as e:
        print(f"❌ Erro de conexão ao tentar se comunicar com o Telegram: {e}")
        exit(1)

if __name__ == "__main__":
    setup_webhook()
