# 📥 Telegram Chat Downloader

Script em Python para autenticar na sua conta do Telegram e baixar **todo o conteúdo** (mensagens, fotos, vídeos, áudios, documentos e arquivos) de qualquer chat, canal ou grupo organizado em subpastas dentro de `./baixado/<Nome_do_Chat>`.

---

## 🚀 Recursos

- **Protocolo MTProto Oficial:** Conecta-se diretamente à sua conta via [Telethon](https://github.com/LonamiWebs/Telethon) (sem as restrições da API de bots).
- **Pastas Dedicadas por Chat:** Cada chat/canal baixado é organizado em sua própria subpasta dentro de `./baixado/`.
- **Seleção Flexível:** Escolha o chat através de um menu interativo no terminal ou informe diretamente por `--chat` (nome, link `t.me/...`, `@username` ou ID numérico).
- **Exportação Completa:**
  - **Mídias:** Fotos, vídeos, mensagens de voz, áudios e documentos salvos em `./baixado/<Chat>/midias/`.
  - **Histórico Legível:** Formato texto amigável em `./baixado/<Chat>/mensagens.txt`.
  - **Dados Estruturados:** Formato JSON com metadados detalhados em `./baixado/<Chat>/mensagens.json`.
  - **Resumo do Chat:** Estatísticas e metadados em `./baixado/<Chat>/info_chat.json`.
- **Retomada Inteligente:** Se o download for interrompido, ao rodar novamente os arquivos já baixados não serão baixados de novo.
- **Barra de Progresso:** Monitoramento em tempo real do download de cada arquivo (velocidade e tamanho).

---

## 📋 Pré-requisitos: Obter API_ID e API_HASH

O Telegram exige credenciais de desenvolvedor para permitir o login na conta:

1. Acesse **[my.telegram.org](https://my.telegram.org)**.
2. Faça login com o número do seu Telegram e insira o código de confirmação recebido no aplicativo.
3. Acesse **API development tools**.
4. Crie uma aplicação (qualquer nome/título).
5. Copie o **`App api_id`** (número) e o **`App api_hash`** (chave de 32 caracteres).

---

## ⚙️ Configuração

1. Clone o repositório ou navegue até a pasta do projeto:
   ```bash
   git clone <URL_DO_SEU_REPOSITORIO>
   cd Telegram
   ```

2. Crie o arquivo `.env` a partir do modelo:
   ```bash
   cp .env.example .env
   ```

3. Preencha o `.env` com suas credenciais:
   ```env
   API_ID=12345678
   API_HASH=0123456789abcdef0123456789abcdef
   PHONE_NUMBER=+5511999999999
   ```

> 💡 **Nota de Segurança:** O arquivo `.env` e os arquivos de sessão `*.session` estão no `.gitignore` para nunca serem enviados ao GitHub.

---

## ▶️ Como Usar

### 1. Modo Interativo (Recomendado)
Basta executar:
```bash
./run.sh
```
ou diretamente com python:
```bash
python3 baixador.py
```

O script cuidará de criar o ambiente virtual, instalar as dependências e listará suas conversas recentes numeradas no terminal para você escolher.
> 💡 **Seleção múltipla:** Você pode digitar um único número (ex: `1`), múltiplos separados por vírgula (ex: `1, 3, 5`) ou intervalos (ex: `1-4`) para enfileirar vários chats de uma vez!

---

### 2. Passando Chats Diretamente (Único ou Fila)

**Chat único:**
```bash
./run.sh --chat "Nome do Canal"
./run.sh --chat "@canal_exemplo"
./run.sh --chat "-1001234567890"
./run.sh --chat "https://t.me/nomedocanal"
```

**Enfileirando múltiplos chats:**

No formato de lista `[chat1, chat2]`:
```bash
./run.sh --chat "[Canal 1, Canal 2]"
```

Múltiplos argumentos separados por espaço:
```bash
./run.sh --chat "Canal 1" "Canal 2" "@canal3"
```

Separados por vírgula:
```bash
./run.sh --chat "Canal 1, @canal2, Canal 3"
```

O script processará cada chat da fila em sequência, criando a pasta correspondente de cada um dentro de `./baixado/`. Se houver falha em algum chat específico, o erro será exibido e a fila continuará automaticamente para os próximos!

---

## 🎛️ Opções Adicionais

| Parâmetro | Descrição |
|---|---|
| `--chat`, `-c` | Nome(s), `@username(s)`, link(s) ou ID(s) dos chats. Suporta chat único, lista `[chat1, chat2]` ou múltiplos valores. |
| `--output`, `-o` | Pasta base de destino (padrão: `./baixado`) |
| `--limit`, `-l` | Limite de mensagens a baixar por chat (ex: `--limit 100`) |
| `--no-media` | Baixa apenas o histórico de mensagens (sem baixar arquivos pesados) |
| `--no-reverse` | Baixa da mais recente para a mais antiga (padrão é cronológico) |

**Exemplo baixando apenas as últimas 50 mensagens sem mídias:**
```bash
./run.sh --chat "@canal" --limit 50 --no-media
```

---

## 📁 Estrutura dos Arquivos Baixados

Ao finalizar o download, cada chat tem sua pasta isolada:

```
baixado/
└── Nome_do_Chat/
    ├── info_chat.json       # Dados gerais do chat e resumo do download
    ├── mensagens.txt        # Histórico de conversas formatado para leitura
    ├── mensagens.json       # Todas as mensagens estruturadas com IDs e datas
    └── midias/              # Todas as mídias salvas
        ├── 101_foto.jpg
        ├── 102_relatorio.pdf
        ├── 103_audio_voz.ogg
        └── 104_video.mp4
```
