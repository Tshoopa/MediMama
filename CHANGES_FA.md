# MediMama — تغییرات نسخه دوحالته

این نسخه یک کدبیس دارد و با متغیر `INFERENCE_MODE` در `.env` بین دو حالت انتخاب می‌شود. فایل‌های مدل و وزن‌ها داخل ZIP قرار نگرفته‌اند.

## انتخاب حالت اجرا

```env
# حالت ۱: مدل محلی برای GitHub / Portfolio / Colab
INFERENCE_MODE=local
TRANSLATION_BACKEND=auto

# حالت ۲: فقط API برای سرور کم‌منبع
# INFERENCE_MODE=api
# TRANSLATION_BACKEND=auto
```

- **حالت ۱ (`local`)**: تولید پاسخ و ترجمه با Google MedGemma 1.5 4B روی سیستم محلی؛ Embeddingهای PubMedBERT، reranker و semantic helperها هم محلی هستند. برای اجرای پیش‌فرض این حالت، کلید OpenAI لازم نیست. دسترسی Hugging Face به مدل، پذیرش شرایط استفاده و سخت‌افزار متناسب لازم است.
- **حالت ۲ (`api`)**: تولید پاسخ، ترجمه و embedding با OpenAI API؛ reranker و semantic modelهای محلی خاموش می‌شوند. فایل `requirements.txt` و Dockerfile مخصوص این حالت‌اند و PyTorch، Transformers و Sentence Transformers نصب نمی‌شوند.
- `TRANSLATION_BACKEND=auto` از همان حالت اصلی پیروی می‌کند؛ در صورت نیاز می‌توان در حالت local با مقدار `openai` ترجمه را به API سپرد. در حالت api انتخاب `local` مجاز نیست.

**نکته مهم:** عوض‌کردن `.env` به‌تنهایی کافی نیست؛ باید وابستگی متناسب با حالت انتخابی هم نصب شود و دیتابیس برداری برای همان embedding دوباره ingest شود. نام collection به‌صورت پیش‌فرض برای دو حالت جداست: `medimama_local` و `medimama_api`.

## فهرست فایل‌های تغییرکرده و ارتباط آن‌ها با حالت‌ها

### فایل‌های اصلی مشترک (هر دو حالت)

| فایل | حالت | تغییر |
|---|---|---|
| `backend/config.py` | مشترک | اضافه‌شدن سوییچ `INFERENCE_MODE`، سوییچ ترجمه، تنظیمات دو مدل، نام collection مستقل و اعتبارسنجی ناسازگاری تنظیمات |
| `backend/main.py` | مشترک | انتخاب موتور پاسخ بر اساس حالت، readiness، تشخیص زبان و توقف ایمن در صورت شکست ترجمه ورودی |
| `backend/translation.py` | هر دو | ترجمه بالینی با زبان مبدأ صریح؛ local با MedGemma و api با OpenAI؛ شکست ترجمه ورودی باعث عبور متن ترجمه‌نشده به تریاژ نمی‌شود |
| `backend/llm_provider.py` | هر دو | آداپتر واحد برای MedGemma محلی یا OpenAI API؛ وزن مدل فقط در local بارگذاری می‌شود |
| `backend/openai_client.py` | API و assist اختیاری | کلاینت OpenAI به‌صورت lazy؛ کلید از backend و متغیر محیطی خوانده می‌شود |
| `backend/audit_logger.py` | مشترک | حذف متن خام سؤال، سن کودک، پاسخ و متن شواهد از لاگ به‌صورت پیش‌فرض |
| `backend/triage/engine.py` | مشترک | LLM safety-net فقط اجازه افزایش فوریت دارد و نمی‌تواند سطح تعیین‌شده با قواعد قطعی را پایین بیاورد |
| `backend/triage/safety_config.py` | مشترک | خواندن تنظیمات تریاژ از Pydantic settings و `.env` به‌جای `os.getenv` ناسازگار |
| `backend/triage/llm_safety_net.py` | assist اختیاری در هر دو | تغییر ارائه‌دهنده به OpenAI؛ خاموش به‌صورت پیش‌فرض |
| `backend/triage/llm_feature_assist.py` | assist اختیاری در هر دو | تغییر ارائه‌دهنده به OpenAI؛ خاموش به‌صورت پیش‌فرض و محدود به شواهد متن |
| `backend/triage/llm_orchestrator.py` | مشترک | هماهنگ‌سازی توضیحات پیش‌فرض اجرای assistها با تنظیمات واقعی |
| `backend/rag/embeddings.py` | هر دو | انتخاب embedding محلی در local و OpenAI در api، با بارگذاری lazy |
| `backend/rag/retriever.py` | هر دو | استفاده از collection و embedding فعال، و RRF پیش از reranking |
| `backend/rag/vector_store.py` | هر دو | پشتیبانی Qdrant محلی یا Qdrant Cloud و کنترل ابعاد بردار |
| `backend/rag/ingestor.py` | هر دو | ingestion با embedding متناسب با حالت، chunking بدون مدل محلی در api و ذخیره نام backend/model در payload |
| `backend/rag/reranker.py` | هر دو | Cross-Encoder فقط در local؛ در api مرحله rerank بدون دانلود مدل محلی رد می‌شود |
| `backend/semantic_concepts.py` | هر دو | بارگذاری semantic encoder فقط در local؛ خاموش در api؛ اصلاح ارجاع دستگاه محاسباتی |
| `backend/triage/semantic_feature_detector.py` | هر دو | semantic model فقط در local؛ خروج زودهنگام در api |
| `backend/triage/semantic_backup.py` | هر دو | مدل sentence-transformer فقط در local؛ fallback قطعی و محافظه‌کار در api |
| `backend/triage/triage_rules.json` | مشترک | اصلاح قاعده تب در نوزاد زیر سه ماه از L1 احیا به L2 مراجعه اورژانسی فوری، مطابق تست‌ها و holdoutهای پروژه |

### فایل‌های مخصوص حالت ۱ — Local model

| فایل | حالت | تغییر |
|---|---|---|
| `requirements-local.txt` | فقط local | وابستگی‌های PyTorch، Transformers، Accelerate، Sentence Transformers و Pillow را به requirements پایه اضافه می‌کند |
| `requirements-demo.txt` | فقط local | وابستگی‌های اجرای دموی Colab و ngrok را اضافه می‌کند |
| `demo_colab.py` | فقط local | اجرای Colab با MedGemma و بدون نیاز پیش‌فرض به API key |

### فایل‌های مخصوص حالت ۲ — API-only / میزبانی سبک

| فایل | حالت | تغییر |
|---|---|---|
| `requirements.txt` | فقط api | وابستگی‌های سبک؛ بدون PyTorch، Transformers، Sentence Transformers یا llama.cpp |
| `Dockerfile` | فقط api | تصویر سبک Python و پورت قابل تنظیم توسط میزبان از `PORT` |
| `docker-compose.yml` | عمدتاً api | اجرای Backend و Qdrant با پیکربندی API و volume پایدار Qdrant |

### مستندات، پیکربندی و آزمون‌های مشترک

| فایل | حالت | تغییر |
|---|---|---|
| `.env.example` | مشترک | همه متغیرهای سوییچ و تنظیمات لازم برای دو حالت |
| `.dockerignore` | مشترک | جلوگیری از کپی وزن‌ها، cache، secretها و فایل‌های محلی در image |
| `.gitignore` | مشترک | نادیده‌گرفتن `.env`، وزن‌ها، cacheها، لاگ‌ها و فایل ngrok محلی |
| `README.md` | مشترک | توضیح معماری و quick start دوحالته |
| `docs/API.md` | مشترک | مستندسازی خروجی readiness و حالت انتخاب‌شده |
| `docs/ARCHITECTURE.md` | مشترک | توضیح مسیرهای local و api و تفاوت retrieval |
| `docs/CONFIGURATION.md` | مشترک | شرح کلیدهای `.env` و وابستگی‌های جداگانه |
| `docs/LIMITATIONS.md` | مشترک | به‌روزرسانی محدودیت‌های بالینی، فنی و حریم خصوصی |
| `docs/RUNNING.md` | مشترک | دستورهای نصب و اجرا برای هر دو حالت |
| `backend/scripts/debug_assess.py` | مشترک | هماهنگ‌سازی ابزار بررسی با تنظیمات جدید backend |
| `tests/test_translation.py` | هر دو | تست زبان مبدأ صریح، حفظ نفی، شکست ترجمه و انتخاب مسیر محلی |
| `tests/test_runtime_modes.py` | هر دو | تست انتخاب embedding، collection و عدم بارگذاری مدل محلی در API |
| `tests/test_safety_net_monotonic.py` | مشترک | تست عدم کاهش فوریت و مجازبودن افزایش فوریت |
| `tests/test_emergency.py` | مشترک | هماهنگ‌کردن انتظار تست تب نوزاد با قاعده و سطح‌بندی L2 |

## فایل حذف‌شده

- `ngrok.txt`: از ZIP اولیه حذف شد، چون حاوی رشته‌هایی شبیه credential بود. اگر این مقادیر واقعی و قبلاً در GitHub منتشر شده‌اند، توکن‌های متناظر را revoke و مجدداً صادر کن. هرگز توکن ngrok یا OpenAI را در مخزن عمومی commit نکن.

## راه‌اندازی حالت محلی

```bash
pip install -r requirements-local.txt
cp .env.example .env
# در .env:
# INFERENCE_MODE=local
# TRANSLATION_BACKEND=auto
# HF_TOKEN=توکن_خواندن_Hugging_Face
python -m backend.rag.ingestor
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

برای MedGemma 1.5 4B باید در Hugging Face دسترسی مدل را بپذیری و شرایط Google Health AI Developer Foundations را بخوانی. وزن‌ها را در GitHub قرار نده.

## راه‌اندازی API-only

```bash
pip install -r requirements.txt
cp .env.example .env
# در .env:
# INFERENCE_MODE=api
# OPENAI_API_KEY=...
# QDRANT_URL=...
# QDRANT_API_KEY=...
python -m backend.rag.ingestor
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

برای Render یا میزبان مشابه، Dockerfile حالت api را deploy کن و secretها را از پنل محیطی هاست وارد کن. رایگان‌بودن هاست به معنی رایگان‌بودن OpenAI API نیست.

## وضعیت تست در محیط تحویل

- `compileall` برای backend و tests موفق بود.
- 35 تست با موفقیت اجرا شدند؛ برای تست route، چون پکیج `qdrant-client` در محیط بررسی نصب نبود و دسترسی شبکه برای نصب وجود نداشت، کلاینت Qdrant به‌صورت stub جایگزین شد. بنابراین این تعداد، تست integration واقعی با Qdrant Cloud/Server نیست.
- مدل واقعی MedGemma دانلود و اجرا نشد و درخواست واقعی به OpenAI ارسال نشد؛ این کار نیازمند credential و محیط دارای دسترسی است.
- ارزیابی پزشکی/ترجمه توسط پزشک یا مترجم متخصص انجام نشده است. پروژه همچنان prototype تحقیقاتی است و برای استفاده واقعی والدین یا تصمیم پزشکی مناسب نیست.
