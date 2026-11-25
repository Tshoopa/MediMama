// MediMama conversational client. All API/user text is rendered with textContent.

const API_BASE = (window.MEDIMAMA_CONFIG?.apiBase ?? "").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 120000;

const COPY = {
  en: {
    brandSubtitle: "Pediatric Health Guidance", languageLabel: "Language", prototype: "Prototype",
    introEyebrow: "PEDIATRIC CARE, MADE CLEARER", introTitle: "A clearer next step for your child’s health.",
    introCopy: "Share what is happening. MediMama can gather a little more context when needed, then provide information grounded in its clinical safety workflow.",
    trustNote: "MediMama is a research prototype, not a substitute for a qualified healthcare professional or emergency care.",
    supportedLanguages: "English · فارسی · العربية", stepOne: "STEP 01", intakeTitle: "Tell us about your child",
    intakeDescription: "A few details will help us understand the concern.", ageLabel: "Child’s age", months: "Months", years: "Years",
    ageHelp: "Enter a value from birth to 18 years.", symptomsLabel: "What is concerning you?",
    symptomsPlaceholder: "Describe what you have noticed...", symptomsHelp: "Use your own words. You do not need medical terminology.",
    additionalLabel: "Additional context", optional: "Optional", additionalPlaceholder: "Anything else that may be useful...",
    beginAssessment: "Begin assessment", formDisclaimer: "For emergencies, contact your local emergency service now. Do not wait for an online response.",
    caseSummary: "CASE SUMMARY", patientContext: "Patient context", awaitingInformation: "Awaiting information",
    contextDisclaimer: "Only information provided in this conversation is considered. Unmentioned symptoms are not assumed to be absent.",
    startNew: "Start new conversation", stepTwo: "STEP 02", conversationTitle: "Your conversation",
    conversationDescription: "MediMama may ask a focused follow-up before completing its assessment.", privateSession: "Private demo session",
    processing: "Reviewing the information…", customAnswerLabel: "Or write your answer", replyPlaceholder: "Type a response…",
    uncertainHint: "It is okay to say you are not sure.", sendAnswer: "Send answer", guidanceTitle: "Clinical guidance",
    supportingSources: "Supporting sources", medicalDisclaimer: "This is informational guidance from a research prototype, not a diagnosis. It does not replace professional assessment and cannot rule out illness.",
    startAnother: "Start another conversation", footerDisclaimer: "Research prototype · Not clinically validated",
    user: "You", assistant: "MediMama", ageSummary: "Child’s age", concernSummary: "Main concern", languageSummary: "Language",
    monthsUnit: "months", yearsUnit: "years", pendingStatus: "Assessment pending", completedStatus: "Assessment complete",
    urgentStatus: "Urgent escalation", incompleteStatus: "Assessment incomplete", refusedStatus: "Request not assessed",
    errorStatus: "Unable to complete", completedOverline: "TRIAGE RESULT", pendingOverline: "INFORMATION NEEDED",
    urgentOverline: "URGENT ACTION", incompleteOverline: "NO FINAL TRIAGE LEVEL", refusedOverline: "NOT CLINICALLY TRIAGED", errorOverline: "SERVICE UNAVAILABLE",
    validationAge: "Enter a valid age from birth to 18 years.", validationSymptoms: "Please describe the concern in a little more detail.",
    validationReply: "Choose an option or enter an answer before sending.", requestError: "We could not reach MediMama. Check your connection and try again.",
    retry: "Retry", newSessionPrompt: "The conversation is no longer available. Start a new conversation to continue.",
    responseMissing: "No guidance was returned. This is not a low-risk assessment.", unknownAge: "Not provided",
  },
  fa: {
    brandSubtitle: "راهنمای سلامت کودکان", languageLabel: "زبان", prototype: "نسخهٔ آزمایشی",
    introEyebrow: "مراقبت کودکان، شفاف‌تر", introTitle: "گام بعدی برای سلامت فرزندتان را روشن‌تر کنید.",
    introCopy: "شرح دهید چه اتفاقی افتاده است. در صورت نیاز، مدی‌ماما اطلاعات تکمیلی محدودی می‌پرسد و سپس بر اساس روند ایمنی بالینی خود اطلاعات ارائه می‌کند.",
    trustNote: "مدی‌ماما یک نمونهٔ پژوهشی است و جایگزین متخصص سلامت واجد صلاحیت یا خدمات اورژانسی نیست.",
    supportedLanguages: "English · فارسی · العربية", stepOne: "مرحلهٔ ۱", intakeTitle: "دربارهٔ فرزندتان بگویید",
    intakeDescription: "چند اطلاعات ساده به درک بهتر موضوع کمک می‌کند.", ageLabel: "سن کودک", months: "ماه", years: "سال",
    ageHelp: "سن را از بدو تولد تا ۱۸ سال وارد کنید.", symptomsLabel: "چه چیزی باعث نگرانی شما شده است؟",
    symptomsPlaceholder: "آنچه مشاهده کرده‌اید توضیح دهید...", symptomsHelp: "با کلمات خودتان توضیح دهید؛ نیازی به اصطلاحات پزشکی نیست.",
    additionalLabel: "اطلاعات تکمیلی", optional: "اختیاری", additionalPlaceholder: "هر نکتهٔ دیگری که ممکن است مفید باشد...",
    beginAssessment: "شروع ارزیابی", formDisclaimer: "در شرایط اورژانسی همین حالا با خدمات اورژانس محلی تماس بگیرید. منتظر پاسخ آنلاین نمانید.",
    caseSummary: "خلاصهٔ پرونده", patientContext: "اطلاعات کودک", awaitingInformation: "در انتظار اطلاعات",
    contextDisclaimer: "فقط اطلاعاتی بررسی می‌شود که در این گفتگو ارائه شده است. علامت‌های ذکرنشده، نبودِ علامت فرض نمی‌شوند.",
    startNew: "شروع گفتگوی جدید", stepTwo: "مرحلهٔ ۲", conversationTitle: "گفتگوی شما",
    conversationDescription: "مدی‌ماما ممکن است پیش از تکمیل ارزیابی، یک پرسش مشخص و تکمیلی مطرح کند.", privateSession: "نشست آزمایشی خصوصی",
    processing: "در حال بررسی اطلاعات…", customAnswerLabel: "یا پاسخ خود را بنویسید", replyPlaceholder: "پاسخ خود را بنویسید…",
    uncertainHint: "اشکالی ندارد اگر مطمئن نیستید.", sendAnswer: "ارسال پاسخ", guidanceTitle: "راهنمای بالینی",
    supportingSources: "منابع پشتیبان", medicalDisclaimer: "این اطلاعات از یک نمونهٔ پژوهشی ارائه شده و تشخیص پزشکی نیست. جایگزین ارزیابی تخصصی نمی‌شود و بیماری را رد نمی‌کند.",
    startAnother: "شروع گفتگوی دیگر", footerDisclaimer: "نمونهٔ پژوهشی · فاقد اعتبارسنجی بالینی",
    user: "شما", assistant: "مدی‌ماما", ageSummary: "سن کودک", concernSummary: "موضوع اصلی", languageSummary: "زبان",
    monthsUnit: "ماه", yearsUnit: "سال", pendingStatus: "ارزیابی در انتظار تکمیل", completedStatus: "ارزیابی تکمیل شد",
    urgentStatus: "نیازمند اقدام فوری", incompleteStatus: "ارزیابی ناتمام", refusedStatus: "درخواست ارزیابی نشد",
    errorStatus: "تکمیل ارزیابی ممکن نشد", completedOverline: "نتیجهٔ تریاژ", pendingOverline: "اطلاعات تکمیلی لازم است",
    urgentOverline: "اقدام فوری", incompleteOverline: "سطح تریاژ نهایی نشده است", refusedOverline: "تریاژ بالینی انجام نشد", errorOverline: "سرویس در دسترس نیست",
    validationAge: "سن معتبری از بدو تولد تا ۱۸ سال وارد کنید.", validationSymptoms: "لطفاً موضوع را کمی با جزئیات بیشتر توضیح دهید.",
    validationReply: "پیش از ارسال، یک گزینه انتخاب کنید یا پاسخ خود را بنویسید.", requestError: "ارتباط با مدی‌ماما برقرار نشد. اتصال را بررسی و دوباره تلاش کنید.",
    retry: "تلاش دوباره", newSessionPrompt: "این گفتگو دیگر در دسترس نیست. برای ادامه، گفتگوی جدیدی آغاز کنید.",
    responseMissing: "راهنمایی دریافت نشد. این وضعیت به معنی ارزیابی کم‌خطر نیست.", unknownAge: "ارائه نشده",
  },
  ar: {
    brandSubtitle: "إرشادات صحة الأطفال", languageLabel: "اللغة", prototype: "نسخة تجريبية",
    introEyebrow: "رعاية الأطفال بوضوح أكبر", introTitle: "خطوة أوضح لصحة طفلك.",
    introCopy: "اشرح ما يحدث. قد تطلب ميدي ماما بعض المعلومات الإضافية عند الحاجة، ثم تقدم معلومات وفق مسار السلامة السريرية لديها.",
    trustNote: "ميدي ماما نموذج بحثي أولي، وليست بديلاً عن مختص صحي مؤهل أو الرعاية الطارئة.",
    supportedLanguages: "English · فارسی · العربية", stepOne: "الخطوة ١", intakeTitle: "أخبرنا عن طفلك",
    intakeDescription: "ستساعدنا بعض التفاصيل على فهم المشكلة.", ageLabel: "عمر الطفل", months: "أشهر", years: "سنوات",
    ageHelp: "أدخل عمراً من الولادة حتى ١٨ سنة.", symptomsLabel: "ما الأمر الذي يقلقك؟",
    symptomsPlaceholder: "صف ما لاحظته...", symptomsHelp: "استخدم كلماتك الخاصة؛ لا تحتاج إلى مصطلحات طبية.",
    additionalLabel: "معلومات إضافية", optional: "اختياري", additionalPlaceholder: "أي تفاصيل أخرى قد تكون مفيدة...",
    beginAssessment: "بدء التقييم", formDisclaimer: "في حالات الطوارئ، اتصل بخدمات الطوارئ المحلية الآن. لا تنتظر رداً عبر الإنترنت.",
    caseSummary: "ملخص الحالة", patientContext: "معلومات الطفل", awaitingInformation: "بانتظار المعلومات",
    contextDisclaimer: "يُؤخذ في الاعتبار ما ورد في هذه المحادثة فقط. لا تُعد الأعراض غير المذكورة أعراضاً منفية.",
    startNew: "بدء محادثة جديدة", stepTwo: "الخطوة ٢", conversationTitle: "محادثتك",
    conversationDescription: "قد تطرح ميدي ماما سؤالاً توضيحياً محدداً قبل إكمال التقييم.", privateSession: "جلسة تجريبية خاصة",
    processing: "جارٍ مراجعة المعلومات…", customAnswerLabel: "أو اكتب إجابتك", replyPlaceholder: "اكتب إجابتك…",
    uncertainHint: "لا بأس إن لم تكن متأكداً.", sendAnswer: "إرسال الإجابة", guidanceTitle: "الإرشادات السريرية",
    supportingSources: "المصادر الداعمة", medicalDisclaimer: "هذه إرشادات معلوماتية من نموذج بحثي أولي وليست تشخيصاً. لا تحل محل التقييم المهني ولا تستبعد المرض.",
    startAnother: "بدء محادثة أخرى", footerDisclaimer: "نموذج بحثي · لم يخضع للتحقق السريري",
    user: "أنت", assistant: "ميدي ماما", ageSummary: "عمر الطفل", concernSummary: "المشكلة الرئيسية", languageSummary: "اللغة",
    monthsUnit: "أشهر", yearsUnit: "سنوات", pendingStatus: "التقييم قيد الانتظار", completedStatus: "اكتمل التقييم",
    urgentStatus: "تصعيد عاجل", incompleteStatus: "التقييم غير مكتمل", refusedStatus: "لم يُقيّم الطلب",
    errorStatus: "تعذر إكمال التقييم", completedOverline: "نتيجة الفرز", pendingOverline: "معلومات إضافية مطلوبة",
    urgentOverline: "إجراء عاجل", incompleteOverline: "لم يُحدد مستوى الفرز النهائي", refusedOverline: "لم يتم الفرز السريري", errorOverline: "الخدمة غير متاحة",
    validationAge: "أدخل عمراً صالحاً من الولادة حتى ١٨ سنة.", validationSymptoms: "يرجى وصف المشكلة بمزيد من التفصيل.",
    validationReply: "اختر إجابة أو اكتبها قبل الإرسال.", requestError: "تعذر الاتصال بميدي ماما. تحقق من الاتصال وحاول مرة أخرى.",
    retry: "إعادة المحاولة", newSessionPrompt: "لم تعد المحادثة متاحة. ابدأ محادثة جديدة للمتابعة.",
    responseMissing: "لم يتم إرجاع إرشادات. هذا لا يعني أن التقييم منخفض الخطورة.", unknownAge: "لم يُذكر",
  },
};

const elements = {
  language: document.getElementById("language"),
  intakeView: document.getElementById("intakeView"),
  conversationView: document.getElementById("conversationView"),
  askForm: document.getElementById("askForm"),
  ageValue: document.getElementById("ageValue"),
  ageUnit: document.getElementById("ageUnit"),
  symptoms: document.getElementById("symptoms"),
  additionalContext: document.getElementById("additionalContext"),
  submitBtn: document.getElementById("submitBtn"),
  formError: document.getElementById("formError"),
  summaryList: document.getElementById("summaryList"),
  assessmentStatus: document.getElementById("assessmentStatus"),
  assessmentStatusText: document.getElementById("assessmentStatusText"),
  newConversationBtn: document.getElementById("newConversationBtn"),
  newConversationFinalBtn: document.getElementById("newConversationFinalBtn"),
  chatHistory: document.getElementById("chatHistory"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loadingText"),
  conversationError: document.getElementById("conversationError"),
  replyForm: document.getElementById("replyForm"),
  quickReplies: document.getElementById("quickReplies"),
  replyText: document.getElementById("replyText"),
  sendReplyBtn: document.getElementById("sendReplyBtn"),
  finalSection: document.getElementById("finalSection"),
  urgencyBox: document.getElementById("urgencyBox"),
  urgencyOverline: document.getElementById("urgencyOverline"),
  urgencyLabel: document.getElementById("urgencyLabel"),
  answerText: document.getElementById("answerText"),
  urgencyAdvice: document.getElementById("urgencyAdvice"),
  citationsBlock: document.getElementById("citationsBlock"),
  citationsList: document.getElementById("citationsList"),
};

const state = {
  language: "en",
  conversationId: null,
  activeQuestionId: null,
  currentAgeMonths: null,
  currentConcern: "",
  retryAction: null,
  busy: false,
};

function t(key) {
  return COPY[state.language]?.[key] ?? COPY.en[key] ?? key;
}

function applyLocale(language) {
  state.language = Object.hasOwn(COPY, language) ? language : "en";
  document.documentElement.lang = state.language;
  document.documentElement.dir = state.language === "fa" || state.language === "ar" ? "rtl" : "ltr";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    const key = node.dataset.i18n;
    if (COPY[state.language][key]) node.textContent = COPY[state.language][key];
  }
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    const key = node.dataset.i18nPlaceholder;
    if (COPY[state.language][key]) node.setAttribute("placeholder", COPY[state.language][key]);
  }
  elements.language.setAttribute("aria-label", t("languageLabel"));
  document.title = state.language === "fa"
    ? "مدی‌ماما — راهنمای سلامت کودکان"
    : state.language === "ar" ? "ميدي ماما — إرشادات صحة الأطفال" : "MediMama — Pediatric Health Guidance";
}

elements.language.addEventListener("change", () => {
  if (state.conversationId) return;
  applyLocale(elements.language.value);
});

function setBusy(busy, messageKey = "processing") {
  state.busy = busy;
  elements.loading.hidden = !busy;
  elements.loadingText.textContent = t(messageKey);
  elements.submitBtn.disabled = busy;
  elements.sendReplyBtn.disabled = busy || !state.activeQuestionId || !elements.replyText.value.trim();
  for (const option of elements.quickReplies.querySelectorAll("button")) option.disabled = busy;
}

async function requestJson(path, method, payload) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
      },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: controller.signal,
    });
    let data = {};
    try { data = await response.json(); } catch { /* response may have no JSON body */ }
    if (!response.ok) {
      const error = new Error(data.detail || `${response.status}`);
      error.status = response.status;
      throw error;
    }
    return data;
  } finally {
    window.clearTimeout(timeout);
  }
}

function showFormError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = !message;
}

function clearConversationError() {
  elements.conversationError.replaceChildren();
  elements.conversationError.hidden = true;
  state.retryAction = null;
}

function showConversationError(message, retryAction = null) {
  elements.conversationError.replaceChildren();
  const text = document.createElement("span");
  text.textContent = message;
  elements.conversationError.appendChild(text);
  if (retryAction) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "quick-reply retry-button";
    retry.textContent = t("retry");
    retry.addEventListener("click", () => retryAction());
    elements.conversationError.appendChild(retry);
    state.retryAction = retryAction;
  }
  elements.conversationError.hidden = false;
}

function ageToMonths() {
  if (!elements.ageValue.value.trim()) return null;
  const value = Number(elements.ageValue.value);
  if (!Number.isInteger(value) || value < 0) return null;
  if (elements.ageUnit.value === "years") {
    if (value > 18) return null;
    return value * 12;
  }
  if (value > 216) return null;
  return value;
}

function formatAge(months) {
  if (!Number.isInteger(months)) return t("unknownAge");
  if (months >= 12 && months % 12 === 0) return `${months / 12} ${t("yearsUnit")}`;
  return `${months} ${t("monthsUnit")}`;
}

function renderSummary() {
  elements.summaryList.replaceChildren();
  const rows = [
    [t("ageSummary"), formatAge(state.currentAgeMonths)],
    [t("concernSummary"), state.currentConcern],
    [t("languageSummary"), elements.language.selectedOptions[0]?.textContent ?? state.language],
  ];
  for (const [label, value] of rows) {
    const wrapper = document.createElement("div");
    wrapper.className = "summary-item";
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    wrapper.append(term, description);
    elements.summaryList.appendChild(wrapper);
  }
}

function appendMessage(role, messageText) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const meta = document.createElement("span");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? t("user") : t("assistant");
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = messageText;
  wrapper.append(meta, bubble);
  elements.chatHistory.appendChild(wrapper);
  wrapper.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setAssessmentStatus(status) {
  elements.assessmentStatus.className = "assessment-status";
  let label = t("awaitingInformation");
  if (status === "completed") {
    label = t("completedStatus");
    elements.assessmentStatus.classList.add("is-complete");
  } else if (status === "urgent_escalation") {
    label = t("urgentStatus");
    elements.assessmentStatus.classList.add("is-urgent");
  } else if (status === "assessment_incomplete") label = t("incompleteStatus");
  else if (status === "refused") label = t("refusedStatus");
  else if (status === "error") label = t("errorStatus");
  elements.assessmentStatusText.textContent = label;
}

function cleanAnswer(text) {
  return String(text ?? "")
    .replace(/^(?:🚨|🔴|🟠|🟡|🟢|ℹ️)\s*/u, "")
    .replace(/\*\*(.*?)\*\*/gs, "$1")
    .replace(/\n\n⏰\s*/g, "\n\n");
}

function renderCitations(citations) {
  elements.citationsList.replaceChildren();
  const usable = Array.isArray(citations) ? citations : [];
  elements.citationsBlock.hidden = usable.length === 0;
  if (!usable.length) return;
  for (const citation of usable) {
    const item = document.createElement("li");
    const source = document.createElement("strong");
    source.textContent = citation.source || "Source";
    item.appendChild(source);
    if (citation.chunk) {
      const excerpt = document.createElement("span");
      excerpt.className = "citation-snippet";
      excerpt.textContent = citation.chunk;
      item.appendChild(excerpt);
    }
    elements.citationsList.appendChild(item);
  }
}

function renderFollowUp(question) {
  state.activeQuestionId = question.id;
  elements.replyText.value = "";
  elements.quickReplies.replaceChildren();
  for (const option of question.options ?? []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply";
    button.textContent = option.label;
    button.addEventListener("click", () => submitTurn(option.value, option.label));
    elements.quickReplies.appendChild(button);
  }
  elements.replyForm.hidden = false;
  elements.sendReplyBtn.disabled = false;
  elements.replyText.focus({ preventScroll: true });
}

function renderFinal(data) {
  state.activeQuestionId = null;
  elements.replyForm.hidden = true;
  elements.finalSection.hidden = false;
  const effectiveStatus = data.status === "completed" && data.emergency_level == null
    ? "assessment_incomplete" : data.status;
  setAssessmentStatus(effectiveStatus);

  const level = Number.isInteger(data.emergency_level) ? data.emergency_level : null;
  let styleClass = "urgency-pending";
  let overline = t("pendingOverline");
  let statusText = t("pendingStatus");

  if (data.status === "urgent_escalation") {
    styleClass = level === 1 ? "urgency-l1" : level === 2 ? "urgency-l2" : "urgency-incomplete";
    overline = t("urgentOverline");
    statusText = data.emergency_label || t("urgentStatus");
  } else if (data.status === "completed" && level !== null && level >= 1 && level <= 5) {
    styleClass = `urgency-l${level}`;
    overline = t("completedOverline");
    statusText = data.emergency_label || t("completedStatus");
  } else if (data.status === "assessment_incomplete") {
    styleClass = "urgency-incomplete";
    overline = t("incompleteOverline");
    statusText = data.emergency_label || t("incompleteStatus");
  } else if (data.status === "refused") {
    styleClass = "urgency-refused";
    overline = t("refusedOverline");
    statusText = data.emergency_label || t("refusedStatus");
  } else if (data.status === "error") {
    styleClass = "urgency-error";
    overline = t("errorOverline");
    statusText = data.emergency_label || t("errorStatus");
  }

  // A null level is never styled or described as low risk.
  if (level === null && data.status === "completed") {
    styleClass = "urgency-incomplete";
    overline = t("incompleteOverline");
    statusText = t("incompleteStatus");
  }

  elements.urgencyBox.className = `urgency-box ${styleClass}`;
  elements.urgencyOverline.textContent = overline;
  elements.urgencyLabel.textContent = statusText;
  elements.answerText.textContent = cleanAnswer(data.answer) || t("responseMissing");
  elements.urgencyAdvice.textContent = data.see_doctor_urgency || "";
  renderCitations(data.citations);
  elements.finalSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderConversationResponse(data) {
  clearConversationError();
  if (data.language && Object.hasOwn(COPY, data.language) && data.language !== state.language) {
    elements.language.value = data.language;
    applyLocale(data.language);
    elements.language.disabled = true;
    renderSummary();
  }
  if (data.status === "needs_clarification" && data.follow_up_question) {
    setAssessmentStatus("needs_clarification");
    appendMessage("assistant", data.follow_up_question.text);
    renderFollowUp(data.follow_up_question);
    return;
  }
  renderFinal(data);
}

async function performCreate(payload) {
  clearConversationError();
  setBusy(true);
  try {
    const data = await requestJson("/conversations", "POST", payload);
    state.conversationId = data.conversation_id;
    state.activeQuestionId = null;
    elements.language.disabled = true;
    setBusy(false);
    renderConversationResponse(data);
  } catch (error) {
    setBusy(false);
    const message = error.name === "AbortError" ? t("requestError") : t("requestError");
    showConversationError(message, () => performCreate(payload));
  }
}

async function performTurn(payload) {
  clearConversationError();
  setBusy(true);
  try {
    const data = await requestJson(
      `/conversations/${encodeURIComponent(state.conversationId)}/turn`,
      "POST",
      payload,
    );
    setBusy(false);
    renderConversationResponse(data);
  } catch (error) {
    setBusy(false);
    if (error.status === 404 || error.status === 409) {
      showConversationError(t("newSessionPrompt"));
      state.activeQuestionId = null;
      elements.replyForm.hidden = true;
      return;
    }
    showConversationError(t("requestError"), () => performTurn(payload));
  }
}

function submitTurn(answer, displayText) {
  if (!state.conversationId || !state.activeQuestionId || state.busy) return;
  const payload = { question_id: state.activeQuestionId, answer: String(answer).trim() };
  appendMessage("user", displayText || String(answer).trim());
  elements.replyText.value = "";
  performTurn(payload);
}

elements.askForm.addEventListener("submit", (event) => {
  event.preventDefault();
  showFormError("");
  const ageMonths = ageToMonths();
  const symptoms = elements.symptoms.value.trim();
  const additionalContext = elements.additionalContext.value.trim();
  if (ageMonths === null) {
    showFormError(t("validationAge"));
    elements.ageValue.focus();
    return;
  }
  if (symptoms.length < 3) {
    showFormError(t("validationSymptoms"));
    elements.symptoms.focus();
    return;
  }

  state.currentAgeMonths = ageMonths;
  state.currentConcern = symptoms;
  renderSummary();
  elements.chatHistory.replaceChildren();
  elements.finalSection.hidden = true;
  elements.replyForm.hidden = true;
  elements.conversationView.hidden = false;
  elements.intakeView.hidden = true;
  elements.language.disabled = true;
  appendMessage("user", additionalContext ? `${symptoms}\n\n${additionalContext}` : symptoms);

  const payload = {
    symptoms,
    child_age_months: ageMonths,
    language: state.language,
    additional_context: additionalContext || null,
  };
  state.retryAction = () => performCreate(payload);
  performCreate(payload);
});

elements.replyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const answer = elements.replyText.value.trim();
  if (!answer) {
    showConversationError(t("validationReply"));
    elements.replyText.focus();
    return;
  }
  submitTurn(answer, answer);
});

elements.replyText.addEventListener("input", () => {
  elements.sendReplyBtn.disabled = state.busy || !state.activeQuestionId || !elements.replyText.value.trim();
});

async function startNewConversation() {
  const oldId = state.conversationId;
  state.conversationId = null;
  state.activeQuestionId = null;
  state.currentAgeMonths = null;
  state.currentConcern = "";
  state.retryAction = null;
  setBusy(false);
  if (oldId) {
    requestJson(`/conversations/${encodeURIComponent(oldId)}`, "DELETE").catch(() => {});
  }
  elements.askForm.reset();
  elements.chatHistory.replaceChildren();
  elements.summaryList.replaceChildren();
  elements.finalSection.hidden = true;
  elements.replyForm.hidden = true;
  elements.loading.hidden = true;
  elements.conversationError.hidden = true;
  elements.conversationError.replaceChildren();
  elements.intakeView.hidden = false;
  elements.conversationView.hidden = true;
  elements.language.disabled = false;
  applyLocale(elements.language.value);
  showFormError("");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

elements.newConversationBtn.addEventListener("click", startNewConversation);
elements.newConversationFinalBtn.addEventListener("click", startNewConversation);

applyLocale(elements.language.value);
