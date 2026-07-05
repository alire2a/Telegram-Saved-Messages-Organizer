# Telegram Saved Messages Organizer

ابزار هوشمند پاک‌سازی و سازماندهی پیام‌های Saved Messages تلگرام با استفاده از Groq AI.

## ویژگی‌ها

- دسته‌بندی هوشمند پیام‌ها با Groq
- ایجاد خودکار تاپیک در گروه
- فوروارد به تاپیک مربوطه
- حذف خودکار از Saved Messages
- تشخیص پیام‌های موقتی/تبلیغاتی و ارسال به تاپیک Delete Only
- مدیریت Rate Limit
- پشتیبانی از پروکسی

## نصب و اجرا

1. **پیش‌نیازها:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install telethon groq python-dotenv
   pip install pysocks
