import os
import json
import xml.etree.ElementTree as ET

# لیست دقیق بیماری‌ها و موضوعات مخصوص کودکان
STRICT_PEDIATRIC_CONDITIONS = [
    # سرطان‌های کودکان
    "leukemia", "lymphocytic leukemia", "lymphoblastic leukemia",
    "neuroblastoma", "wilms tumor", "retinoblastoma",
    "osteosarcoma", "ewing sarcoma", "rhabdomyosarcoma",
    
    # بیماری‌های مخصوص کودکان
    "growth disorder", "failure to thrive", "developmental delay",
    "cerebral palsy", "spina bifida", "down syndrome",
    "autism", "adhd", "asperger",
    
    # عفونت‌های شایع کودکان
    "croup", "bronchiolitis", "roseola", "hand foot mouth",
    "kawasaki", "scarlet fever", "whooping cough",
    
    # موضوعات مربوط به کودکان
    "adoption", "foster care", "child custody",
    "breastfeeding", "infant formula", "baby bottle",
    "teething", "colic", "diaper rash",
    
    # واکسیناسیون
    "vaccination", "immunization", "vaccine schedule",
    
    # رشد و تکامل
    "child development", "milestones", "pediatric growth",
    "puberty", "adolescent health"
]

# کلمات کلیدی که باید در متن وجود داشته باشد
REQUIRED_KEYWORDS = [
    "child", "children", "infant", "toddler", "newborn", "baby",
    "pediatric", "kids", "teen", "adolescent", "school-age",
    "preschool", "kindergarten"
]

def is_strictly_pediatric(text, focus):
    """بررسی سخت‌گیرانه برای موضوعات مخصوص کودکان"""
    text_lower = text.lower()
    focus_lower = focus.lower()
    
    # شرط ۱: آیا Focus مستقیماً بیماری مخصوص کودکان است؟
    focus_is_pediatric = any(cond in focus_lower for cond in STRICT_PEDIATRIC_CONDITIONS)
    
    # شرط ۲: آیا Focus حاوی کلمات کلیدی کودکان است؟
    focus_has_child_keywords = any(keyword in focus_lower for keyword in REQUIRED_KEYWORDS)
    
    # شرط ۳: آیا متن به اندازه کافی به کودکان اشاره دارد؟
    # (حداقل ۳ بار کلمات کودکان یا حداقل ۵۰٪ متن درباره کودکان است)
    child_word_count = sum(text_lower.count(keyword) for keyword in REQUIRED_KEYWORDS)
    total_words = len(text_lower.split())
    child_word_ratio = child_word_count / max(total_words, 1)
    
    # شرط ۴: آیا بیماری‌های مخصوص کودکان در متن ذکر شده؟
    text_has_pediatric_conditions = any(cond in text_lower for cond in STRICT_PEDIATRIC_CONDITIONS)
    
    # تصمیم نهایی
    return (focus_is_pediatric or 
            focus_has_child_keywords or 
            child_word_count >= 3 or 
            child_word_ratio > 0.1 or
            text_has_pediatric_conditions)

def extract_strict_pediatric_qa(folder_path, source_label):
    """استخراج فقط QAهای مخصوص کودکان"""
    results = []
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return results
    
    for filename in os.listdir(folder_path):
        if not filename.endswith(".xml"):
            continue
        
        filepath = os.path.join(folder_path, filename)
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            url = root.attrib.get("url", "")
            
            focus_elem = root.find("Focus")
            focus = focus_elem.text if focus_elem is not None else ""
            
            # اگر Focus خالی است یا خیلی عمومی است، رد کن
            if not focus or focus.lower() in ["alcohol", "air pollution", "acne", "general"]:
                continue
            
            pediatric_qa_in_file = []
            
            for qa_pair in root.findall(".//QAPair"):
                q_elem = qa_pair.find("Question")
                a_elem = qa_pair.find("Answer")
                
                if q_elem is None or a_elem is None:
                    continue
                
                question = q_elem.text or ""
                answer = a_elem.text or ""
                qid = q_elem.attrib.get("qid", "")
                
                combined_text = f"{question} {answer}"
                
                # بررسی سخت‌گیرانه
                if is_strictly_pediatric(combined_text, focus):
                    pediatric_qa_in_file.append({
                        "id": f"{source_label}_{qid}",
                        "text": f"Q: {question}\nA: {answer}",
                        "source": source_label,
                        "focus": focus,
                        "url": url,
                        "category": "QA",
                        "age_group": "all_ages"
                    })
            
            # اگر این فایل حداقل یک QA مرتبط داشت، اضافه کن
            if pediatric_qa_in_file:
                results.extend(pediatric_qa_in_file)
                print(f"✓ Found {len(pediatric_qa_in_file)} pediatric QA in {filename}")
                
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
    
    return results

# مسیرها را تنظیم کن
MPLUS_FOLDER = r"D:\MedQuAD\4_MPlus_Health_Topics_QA"
CDC_FOLDER = r"D:\MedQuAD\9_CDC_QA"

print("Extracting STRICTLY pediatric QA pairs...")
print("=" * -50)

mplus_pairs = extract_strict_pediatric_qa(MPLUS_FOLDER, "MPlusHealthTopics")
cdc_pairs = extract_strict_pediatric_qa(CDC_FOLDER, "CDC")
all_pairs = mplus_pairs + cdc_pairs

# ذخیره نتایج
output_file = "strict_pediatric_qa.jsonl"
with open(output_file, "w", encoding="utf-8") as f:
    for rec in all_pairs:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print("=" * -50)
print(f"✅ Total: {len(all_pairs)} strictly pediatric QA pairs")
print(f"📁 Saved to: {output_file}")

# نمایش نمونه‌ها
if all_pairs:
    print("\n📋 Sample focuses:")
    unique_focuses = list(set([p["focus"] for p in all_pairs]))
    for focus in unique_focuses[:10]:
        print(f"  - {focus}")
