from typing import List
from telethon import TelegramClient, events, utils
from telethon.tl.types import Message

import config
from config import *
import asyncio
import os
import json
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib, ssl

client = TelegramClient('bot_session', api_id, api_hash)
loop = asyncio.get_event_loop()


@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply('Добро пожаловать, чем могу помочь?\n/help\n/report')


async def save_json_data(data: dict, file_name: str):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


async def send_mail(report_id, username, reason, description, filename, subject):
    msg = MIMEMultipart("mixed")
    if subject:
        msg['Subject'] = subject
    msg['From'] = bot_email
    msg['To'] = recipient_email

    if filename:
        for file in filename:
            with open(file, 'rb') as f:
                file_data = f.read()
                file_name = f.name
                print(file)
            msg.attach(MIMEImage(file_data, name=file))

    message = f'ID: {report_id}\nUsername: {username}\nReason: {reason}\nDescription: {description}'
    msg.attach(MIMEText(message, 'plain'))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(bot_email, bot_password)
        server.send_message(msg)


@client.on(events.NewMessage(pattern='/report'))
async def report(event):
    report_id = f"{event.sender_id}_{event.message.id}"
    await event.reply('Мы отправили вам форму для написания жалобы в личные сообщения\nПожалуйста, перейдите в личные сообщения и заполните жалобу по форме')
    await client.send_message(entity=event.sender_id, message="Заполните жалобу:")

    conversation = await client.get_entity(event.sender_id)
    async with client.conversation(conversation, timeout=60) as conv:
        await conv.send_message('Причина жалобы')
        reason_message: Message = await conv.get_response()

        await conv.send_message('Описание жалобы')
        description_message: Message = await conv.get_response()

        await conv.send_message('Оправьте скриншоты, после чего напишите "Готово"')

        screenshot_messages: List[Message] = []
        for _ in range(10):
            try:
                screenshot_message: Message = await conv.get_response()
                if screenshot_message.media:
                    screenshot_messages.append(screenshot_message)
                else:
                    break
            except asyncio.TimeoutError:
                break

        await conv.send_message('Спасибо за жалобу, мы обязательно рассмотрим её')

    screenshots: List[str] = []
    for screenshot_message in screenshot_messages:
        if screenshot_message.media is not None:
            path = await client.download_media(screenshot_message, f"reports/{report_id}/{screenshot_message.id}.png")
            screenshots.append(path)

    if len(screenshots) == 0:
        screenshots = None
        os.mkdir(f"reports/{report_id}")

    text = f"**🆔 Номер жалобы: ** `{report_id}`\n\n" \
           f"**👤 Пользователь:**\n[{utils.get_display_name(event.sender)}](tg://user?id={event.sender_id}) (`@{event.sender.username}`)\n\n" \
           f"**❗️Причина:**\n{reason_message.message}\n\n" \
           f"**☁️ Описание:**\n{description_message.message}\n\n"

    await save_json_data({
        "report_id": report_id,
        "user_id": event.sender_id,
        "username": event.sender.username,
        "reason": reason_message.message,
        "description": description_message.message},
        f"reports/{report_id}/report.json")

    await send_mail(report_id=report_id,
                    username=event.sender.username,
                    reason=reason_message.message,
                    description=description_message.message,
                    filename=screenshots,
                    subject=f"Report #{report_id}")
    await client.send_message(entity=config.Channel_id, message=text, file=screenshots)


if __name__ == '__main__':
    if not os.path.exists('reports'):
        os.mkdir('reports')

    client.start()
    client.run_until_disconnected()