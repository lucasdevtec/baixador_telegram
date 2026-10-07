#!/usr/bin/env python3
"""
Telegram Chat Downloader
Baixa todas as mensagens e arquivos de mídia de um chat/canal/grupo do Telegram para a pasta ./baixado.
"""

import os
import sys
import re
import json
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

from telethon import TelegramClient, errors
from telethon.tl.types import (
    User,
    Chat,
    Channel,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaPoll,
    MessageMediaContact,
    MessageMediaGeo,
    MessageMediaVenue,
    DocumentAttributeFilename,
    DocumentAttributeAudio,
    DocumentAttributeVideo,
)

# Carrega variáveis do arquivo .env caso exista
load_dotenv()


def format_bytes(size):
    """Formata bytes em unidade legível (KB, MB, GB)."""
    if not size:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Remove caracteres inválidos do nome do arquivo."""
    # Remove caracteres reservados em sistemas de arquivos
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # Substitui múltiplos espaços/underscores
    cleaned = re.sub(r'[\s_]+', '_', cleaned).strip(' ._')
    if len(cleaned) > max_length:
        base, ext = os.path.splitext(cleaned)
        cleaned = base[:max_length - len(ext)] + ext
    return cleaned or "arquivo"


def sanitize_folder_name(name: str, max_length: int = 100) -> str:
    """Remove caracteres inválidos para o nome da pasta mantendo espaços e legibilidade."""
    cleaned = re.sub(r'[\\/*?:"<>|\0]', '_', name).strip(' .')
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(' .')
    return cleaned or "chat"


def get_sender_name(sender) -> str:
    """Retorna o nome formatado do remetente."""
    if not sender:
        return "Desconhecido"
    if isinstance(sender, User):
        parts = [p for p in (sender.first_name, sender.last_name) if p]
        name = " ".join(parts) if parts else "Usuário"
        if sender.username:
            return f"{name} (@{sender.username})"
        return name
    elif isinstance(sender, (Chat, Channel)):
        return getattr(sender, 'title', 'Canal/Grupo')
    return "Desconhecido"


def detect_media_type(message) -> str:
    """Retorna o tipo de mídia como string simples."""
    if not message.media:
        return "none"
    if isinstance(message.media, MessageMediaPhoto):
        return "foto"
    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if not doc:
            return "documento"
        for attr in getattr(doc, 'attributes', []):
            if isinstance(attr, DocumentAttributeAudio):
                return "audio_voz" if getattr(attr, 'voice', False) else "audio"
            if isinstance(attr, DocumentAttributeVideo):
                return "video_circular" if getattr(attr, 'round_message', False) else "video"
        return "documento"
    if isinstance(message.media, MessageMediaPoll):
        return "enquete"
    if isinstance(message.media, MessageMediaContact):
        return "contato"
    if isinstance(message.media, (MessageMediaGeo, MessageMediaVenue)):
        return "localizacao"
    return "outro"


def get_media_filename(message) -> str:
    """Gera um nome de arquivo consistente e seguro para a mídia da mensagem."""
    file_info = message.file
    orig_name = getattr(file_info, 'name', None) if file_info else None
    ext = getattr(file_info, 'ext', '') if file_info else ''
    media_type = detect_media_type(message)

    if orig_name:
        safe_name = sanitize_filename(orig_name)
        return f"{message.id}_{safe_name}"

    if not ext:
        # Extensões padrão caso não detectadas
        if media_type == "foto":
            ext = ".jpg"
        elif media_type in ("video", "video_circular"):
            ext = ".mp4"
        elif media_type == "audio_voz":
            ext = ".ogg"
        elif media_type == "audio":
            ext = ".mp3"
        else:
            ext = ".bin"

    return f"{message.id}_{media_type}{ext}"


async def get_credentials():
    """Obtém credenciais da API do Telegram (via .env ou prompt interativo)."""
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone_number = os.getenv("PHONE_NUMBER")

    if not api_id or not api_hash:
        print("=" * 60)
        print(" Configuração da API do Telegram")
        print("=" * 60)
        print("Para baixar dados de sua conta, você precisa de API_ID e API_HASH.")
        print("Como obter gratuitamente em 1 minuto:")
        print(" 1. Acesse: https://my.telegram.org")
        print(" 2. Faça login com o seu número de telefone do Telegram.")
        print(" 3. Clique em 'API development tools'.")
        print(" 4. Preencha qualquer nome nos campos e copie o API ID e API HASH.\n")

        while not api_id:
            val = input("Digite o seu API_ID (somente números): ").strip()
            if val.isdigit():
                api_id = val
            else:
                print("API_ID inválido. Deve conter apenas números.")

        while not api_hash:
            val = input("Digite o seu API_HASH: ").strip()
            if val:
                api_hash = val

        if not phone_number:
            val = input("Digite o seu telefone com código do país (ex: +5511999999999) [opcional]: ").strip()
            if val:
                phone_number = val

        save_to_env = input("\nDeseja salvar estas credenciais no arquivo .env para os próximos usos? (S/n): ").strip().lower()
        if save_to_env != 'n':
            with open(".env", "w", encoding="utf-8") as f:
                f.write(f"API_ID={api_id}\n")
                f.write(f"API_HASH={api_hash}\n")
                if phone_number:
                    f.write(f"PHONE_NUMBER={phone_number}\n")
            print("Credenciais salvas em .env com sucesso!")

    return int(api_id), api_hash, phone_number


async def select_chat_interactively(client):
    """Lista os chats recentes e permite ao usuário escolher interativamente."""
    print("\n🔍 Carregando suas conversas recentes...")
    dialogs = []
    async for dialog in client.iter_dialogs(limit=30):
        dialogs.append(dialog)

    if not dialogs:
        raise RuntimeError("Nenhuma conversa encontrada nesta conta do Telegram.")

    print("\n" + "=" * 60)
    print(" CONVERSAS RECENTES")
    print("=" * 60)
    for idx, d in enumerate(dialogs, 1):
        tipo = "Canal" if d.is_channel else ("Grupo" if d.is_group else "Direto")
        print(f" [{idx:2d}] {d.name:<35} | {tipo:<6} | ID: {d.id}")
    print("=" * 60)

    while True:
        resp = input("\n👉 Escolha o número [1-{}] ou digite o nome/username/ID (ou 's' para sair): ".format(len(dialogs))).strip()
        if not resp:
            continue
        if resp.lower() == 's':
            print("Operação cancelada pelo usuário.")
            sys.exit(0)

        # Selecionou pelo número da lista
        if resp.isdigit():
            idx = int(resp)
            if 1 <= idx <= len(dialogs):
                return dialogs[idx - 1].entity

        # Tentou pesquisar por nome ou ID
        try:
            # Tentar como ID numérico
            chat_id = int(resp)
            return await client.get_entity(chat_id)
        except Exception:
            pass

        # Buscar nas conversas carregadas
        matches = [d for d in dialogs if resp.lower() in d.name.lower()]
        if not matches:
            # Buscar mais a fundo
            print(f"Procurando por '{resp}' em todas as suas conversas...")
            async for d in client.iter_dialogs():
                if resp.lower() in d.name.lower() and d not in matches:
                    matches.append(d)
                    if len(matches) >= 10:
                        break

        if len(matches) == 1:
            return matches[0].entity
        elif len(matches) > 1:
            print(f"\nForam encontrados {len(matches)} resultados:")
            for i, m in enumerate(matches, 1):
                tipo = "Canal" if m.is_channel else ("Grupo" if m.is_group else "Direto")
                print(f" [{i}] {m.name} ({tipo}) [ID: {m.id}]")
            choice = input("Escolha o número do resultado desejado: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(matches):
                return matches[int(choice) - 1].entity
        else:
            print(f"Chat '{resp}' não encontrado. Tente novamente.")


async def resolve_chat(client, chat_target):
    """Localiza a entidade do chat a partir de ID, username, link ou busca."""
    if not chat_target:
        return await select_chat_interactively(client)

    # 1. Tentar resolver como ID inteiro
    try:
        chat_id = int(chat_target)
        return await client.get_entity(chat_id)
    except Exception:
        pass

    # 2. Tentar resolver como @username ou link
    try:
        return await client.get_entity(chat_target)
    except Exception:
        pass

    # 3. Tentar busca textual nas conversas
    print(f"Buscando conversa '{chat_target}'...")
    matches = []
    async for dialog in client.iter_dialogs():
        if chat_target.lower() in dialog.name.lower():
            matches.append(dialog)
            if len(matches) >= 10:
                break

    if len(matches) == 1:
        return matches[0].entity
    elif len(matches) > 1:
        print(f"\nMúltiplos chats encontrados para '{chat_target}':")
        for i, m in enumerate(matches, 1):
            print(f" [{i}] {m.name} [ID: {m.id}]")
        c = input("Escolha o número do chat: ").strip()
        if c.isdigit() and 1 <= int(c) <= len(matches):
            return matches[int(c) - 1].entity
        raise ValueError("Opção inválida.")
    else:
        raise ValueError(f"Não foi possível encontrar o chat '{chat_target}'.")


async def download_chat_content(
    client: TelegramClient,
    entity,
    output_dir: Path,
    download_media: bool = True,
    limit: int = None,
    reverse: bool = True
):
    """Executa o download de mensagens e mídias do chat informado."""
    chat_title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Chat')
    chat_id = getattr(entity, 'id', 'Desconhecido')
    chat_username = getattr(entity, 'username', None)

    # Cria subpasta com o nome do chat dentro do diretório de destino (ex: ./baixado/<nome_do_chat>)
    chat_folder_name = sanitize_folder_name(chat_title)
    output_dir = output_dir / chat_folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    media_dir = output_dir / "midias"
    if download_media:
        media_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print(f" Chat Selecionado: {chat_title}")
    print(f" ID: {chat_id}")
    if chat_username:
        print(f" Username: @{chat_username}")
    print(f" Destino: {output_dir.resolve()}")
    print("=" * 60)

    # Obtém o total estimado de mensagens
    total_messages = (await client.get_messages(entity, limit=0)).total
    limit_text = f" (limitado a {limit})" if limit else ""
    print(f"Total de mensagens no chat: {total_messages}{limit_text}")
    print(f"Baixando mídias: {'Sim' if download_media else 'Não (Apenas texto/JSON)'}")
    print("Iniciando coleta...\n")

    # Arquivos de saída
    txt_file_path = output_dir / "mensagens.txt"
    json_file_path = output_dir / "mensagens.json"
    meta_file_path = output_dir / "info_chat.json"

    # Salva informações gerais
    metadata = {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "chat_username": chat_username,
        "backup_date": datetime.now().isoformat(),
        "total_messages_in_chat": total_messages,
    }
    with open(meta_file_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    all_messages_data = []
    media_download_count = 0
    media_total_bytes = 0
    messages_processed = 0

    # Inicializa cabeçalho do arquivo de texto
    with open(txt_file_path, "w", encoding="utf-8") as txt_out:
        txt_out.write("=" * 60 + "\n")
        txt_out.write(f"Histórico do Chat: {chat_title}\n")
        txt_out.write(f"ID: {chat_id}\n")
        txt_out.write(f"Data do Backup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        txt_out.write("=" * 60 + "\n\n")

    # Cache de nomes de remetentes para performance
    sender_cache = {}

    # Barra de progresso para as mensagens
    total_to_process = min(total_messages, limit) if limit else total_messages
    pbar_msgs = tqdm(total=total_to_process, desc="Processando mensagens", unit="msg")

    try:
        async for message in client.iter_messages(entity, limit=limit, reverse=reverse):
            messages_processed += 1
            pbar_msgs.update(1)

            # Resolve remetente
            sender_id = message.sender_id
            if sender_id not in sender_cache:
                try:
                    sender = await message.get_sender()
                    sender_cache[sender_id] = get_sender_name(sender)
                except Exception:
                    sender_cache[sender_id] = f"ID: {sender_id}"
            sender_name = sender_cache.get(sender_id, "Desconhecido")

            msg_date_str = message.date.strftime("%Y-%m-%d %H:%M:%S") if message.date else "Data desconhecida"
            text_content = message.text or ""
            media_type = detect_media_type(message)
            media_saved_path = None
            media_size = getattr(message.file, 'size', None) if message.file else None

            # Download da mídia, se houver
            if download_media and message.media and media_type not in ("none", "enquete", "localizacao", "contato"):
                filename = get_media_filename(message)
                dest_file = media_dir / filename

                # Verifica se arquivo já existe com o mesmo tamanho (retomada rápida)
                already_downloaded = False
                if dest_file.exists():
                    if media_size and dest_file.stat().st_size == media_size:
                        already_downloaded = True
                    elif not media_size and dest_file.stat().st_size > 0:
                        already_downloaded = True

                if already_downloaded:
                    media_saved_path = f"midias/{filename}"
                else:
                    # Executa download com barra de progresso individual
                    download_success = False
                    for attempt in range(3):
                        try:
                            # Prepara barra de progresso da mídia
                            pbar_media = tqdm(
                                total=media_size or 0,
                                desc=f" Baixando {filename[:25]}",
                                unit="B",
                                unit_scale=True,
                                unit_divisor=1024,
                                leave=False,
                            )

                            def progress_cb(current, total):
                                if pbar_media.total != total and total:
                                    pbar_media.total = total
                                pbar_media.n = current
                                pbar_media.refresh()

                            await message.download_media(file=str(dest_file), progress_callback=progress_cb)
                            pbar_media.close()

                            if dest_file.exists():
                                file_stat = dest_file.stat()
                                media_total_bytes += file_stat.st_size
                                media_download_count += 1
                                media_saved_path = f"midias/{filename}"
                                download_success = True
                            break

                        except errors.FloodWaitError as fwe:
                            pbar_msgs.write(f"\n[Aviso] Limite do Telegram. Aguardando {fwe.seconds}s...")
                            await asyncio.sleep(fwe.seconds)
                        except Exception as e:
                            pbar_msgs.write(f"\n[Erro mídia msg {message.id}]: {e}")
                            if attempt < 2:
                                await asyncio.sleep(2)

                    if not download_success and dest_file.exists():
                        try:
                            dest_file.unlink()
                        except Exception:
                            pass

            # Monta estrutura da mensagem para o JSON
            msg_entry = {
                "id": message.id,
                "date": message.date.isoformat() if message.date else None,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "text": text_content,
                "reply_to_msg_id": message.reply_to_msg_id,
                "media_type": media_type,
                "media_file": media_saved_path,
                "media_size_bytes": media_size,
            }
            all_messages_data.append(msg_entry)

            # Escreve no log legível (mensagens.txt)
            with open(txt_file_path, "a", encoding="utf-8") as txt_out:
                reply_info = f" (em resposta à msg #{message.reply_to_msg_id})" if message.reply_to_msg_id else ""
                txt_out.write(f"[{msg_date_str}] {sender_name}{reply_info}:\n")
                if text_content:
                    txt_out.write(f"{text_content}\n")
                if media_saved_path:
                    size_formatted = format_bytes(media_size) if media_size else ""
                    txt_out.write(f"  📎 Anexo: {media_saved_path} ({size_formatted})\n")
                elif media_type not in ("none", "outro"):
                    txt_out.write(f"  ℹ️ [{media_type.upper()}]\n")
                txt_out.write("\n")

            # Salva o JSON periodicamente a cada 200 mensagens para garantir persistência
            if messages_processed % 200 == 0:
                with open(json_file_path, "w", encoding="utf-8") as jf:
                    json.dump(all_messages_data, jf, ensure_ascii=False, indent=2)

    except KeyboardInterrupt:
        print("\n\nOperação pausada pelo usuário! Salvando dados coletados até agora...")
    finally:
        pbar_msgs.close()

    # Salva o arquivo JSON final completo
    with open(json_file_path, "w", encoding="utf-8") as jf:
        json.dump(all_messages_data, jf, ensure_ascii=False, indent=2)

    # Atualiza metadados finais
    metadata.update({
        "messages_saved": len(all_messages_data),
        "media_files_downloaded": media_download_count,
        "media_total_bytes": media_total_bytes,
        "media_total_formatted": format_bytes(media_total_bytes),
        "completed_at": datetime.now().isoformat(),
    })
    with open(meta_file_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(" 🎉 DOWNLOAD CONCLUÍDO COM SUCESSO!")
    print("=" * 60)
    print(f" Mensagens salvas: {len(all_messages_data)}")
    print(f" Mídias baixadas:  {media_download_count} ({format_bytes(media_total_bytes)})")
    print(f" Arquivo legível:  {txt_file_path}")
    print(f" Arquivo JSON:     {json_file_path}")
    if download_media:
        print(f" Pasta de mídias:  {media_dir}")
    print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Baixa todo o conteúdo de um chat do Telegram para a pasta ./baixado"
    )
    parser.add_argument(
        "--chat", "-c",
        type=str,
        default=None,
        help="Nome, @username, link ou ID do chat. Se omitido, exibirá uma lista interativa."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./baixado",
        help="Diretório de destino (padrão: ./baixado)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limite máximo de mensagens a serem baixadas (padrão: todas)"
    )
    parser.add_argument(
        "--no-media",
        action="store_true",
        help="Não baixar arquivos de mídia (baixa apenas texto e histórico)"
    )
    parser.add_argument(
        "--no-reverse",
        action="store_true",
        help="Baixar da mensagem mais recente para a mais antiga (o padrão é cronológico: mais antiga -> mais recente)"
    )

    args = parser.parse_args()

    api_id, api_hash, phone = await get_credentials()

    output_path = Path(args.output)

    print("\nConectando aos servidores do Telegram...")
    # Cria o cliente do Telethon. A sessão será salva localmente em telegram_session.session
    client = TelegramClient("telegram_session", api_id, api_hash)

    await client.start(phone=phone)

    me = await client.get_me()
    print(f"✅ Conectado com sucesso como: {get_sender_name(me)} (ID: {me.id})")

    try:
        entity = await resolve_chat(client, args.chat)
        await download_chat_content(
            client=client,
            entity=entity,
            output_dir=output_path,
            download_media=not args.no_media,
            limit=args.limit,
            reverse=not args.no_reverse
        )
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrograma finalizado pelo usuário.")
        sys.exit(0)
